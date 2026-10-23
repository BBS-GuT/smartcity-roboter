"""Supervised operation: measured holes stay unknown; genuine holds remain."""
import json
import math
import sys
import types
import unittest
import numpy as np
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_lidar_fusion_verbraucher as c

q = c.q
f = q.lf.fahrtest


def node(make):
    n = make()
    c.configure(n)
    n._p.update(begleiteter_fahrbetrieb=True, scan_einbau_xy=[-.1, .05, .2, -.05])
    c.feed(n)
    return n


def query(n):
    return n.notbremse(.1, 0, 0) if hasattr(n, 'notbremse') else n.lidar_pruefen()[0]


class SensorGuards(unittest.TestCase):
    def test_measured_small_clock_skew_is_explicit_and_bounded_in_both_consumers(self):
        for make in (q.lf.LineFollower, q.zentrale.Zentrale):
            for mode, skew, allowed in ((True, .03, True), (True, .09, True),
                                         (True, .2, False), (False, .03, False)):
                n = node(make)
                n._p['begleiteter_fahrbetrieb'] = mode
                m = c.message(1)
                m.header = q.kopf(q.time.time() + skew)
                m.header.frame_id = 'laser_b'
                (n.on_scan if hasattr(n, 'notbremse') else n._scan)(m, '/scan1', 1)
                reason = n.scans['/scan1'][2 if hasattr(n, 'notbremse') else 3]
                with self.subTest(make=make.__name__, mode=mode, skew=skew):
                    self.assertEqual(reason is None, allowed)
                    if allowed:
                        self.assertEqual(query(n), None if hasattr(n, 'notbremse') else float('inf'))

    def test_only_explicit_mode_accepts_a_measured_coverage_hole(self):
        for make in (q.lf.LineFollower, q.zentrale.Zentrale):
            n = node(make)
            n._p['begleiteter_fahrbetrieb'] = False
            self.assertTrue(query(n) if hasattr(n, 'notbremse') else query(n) is None)
            n._p['begleiteter_fahrbetrieb'] = True
            self.assertEqual(query(n), None if hasattr(n, 'notbremse') else float('inf'))
            stamps = {t: e[3 if hasattr(n, 'notbremse') else 4] for t, e in n.scans.items()}
            view, _ = n.scan_geometrie.sicht(stamps)
            self.assertFalse(q.lf.lidar_fusion.gemeinsam_frei(view.fields, [[.22, -.05]])[0])

    def test_invalid_sources_geometry_and_times_still_hold(self):
        for make in (q.lf.LineFollower, q.zentrale.Zentrale):
            for fault in ('missing', 'invalid', 'frame', 'future', 'pose', 'stale'):
                n = node(make)
                if fault == 'missing':
                    n.scans.pop('/scan1')
                elif fault == 'pose':
                    n._p['scan_einbau_quelle'] = ['gemessen', 'unbekannt']
                elif fault != 'stale':
                    m = c.message(1)
                    if fault == 'invalid':
                        m.ranges = [0.0] * len(m.ranges)
                    elif fault == 'frame':
                        m.header.frame_id = 'wrong'
                    else:
                        m.header.stamp.sec += 5
                    (n.on_scan if hasattr(n, 'notbremse') else n._scan)(m, '/scan1', 1)
                with q.spaeter(2 if fault == 'stale' else 0), self.subTest(make=make.__name__, fault=fault):
                    value = query(n)
                    self.assertTrue(value if hasattr(n, 'notbremse') else value is None)

    def test_actual_lidar_hit_is_not_bypassed(self):
        n = node(q.lf.LineFollower)
        m = c.message(1)
        k = round(-m.angle_min / m.angle_increment)
        m.ranges[k] = .06  # 6 cm from the front-mounted synthetic sensor, outside the body
        n.on_scan(m, '/scan1', 1)
        self.assertIn('NOTBREMSE', query(n))

    def test_ki_reports_unknown_coverage_instead_of_false_free_distance(self):
        n = node(q.zentrale.Zentrale)
        now, mono = q.time.time(), q.time.monotonic()
        n.wahrnehmung.update(bild_zeit=now, aufnahme=now, blick='fahr', tiefe_aufnahme=now,
                            tiefe_empfang=mono, tiefe_gueltig=True, tiefe_hindernis=False)
        with mock.patch.object(n, 'kamera_lage', return_value=(True, 0)):
            data = q.befehl(n)
        self.assertTrue(data['begleiteter_fahrbetrieb'])
        self.assertEqual(data['aktion'], 'fahren')
        self.assertIsNone(data['lidar'])
        self.assertEqual(data['lidar_abdeckung'], 'unbekannt')
        self.assertIsNotNone(data['lidar_erste_luecke_m'])


class DepthAndArm(unittest.TestCase):
    def test_simulated_aligned_rgb_and_depth_use_the_same_optical_frame(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'sim'))
        import sensor_msgs.msg
        with mock.patch.object(sensor_msgs.msg, 'CameraInfo', types.SimpleNamespace, create=True):
            import simulator
        rgb, depth = [], []
        def message(image, encoding):
            return types.SimpleNamespace(header=types.SimpleNamespace(
                stamp=types.SimpleNamespace(sec=0, nanosec=0), frame_id=''), encoding=encoding)
        n = types.SimpleNamespace(
            _frueher=lambda: (1000., (0., 0., 0.), 90.),
            welt=types.SimpleNamespace(kamera=lambda *a, **kw:
                (np.zeros((480, 640, 3), dtype=np.uint8), np.full((240, 320), .4))),
            bridge=types.SimpleNamespace(cv2_to_imgmsg=message), rng=np.random.default_rng(1),
            pub_bild=types.SimpleNamespace(publish=rgb.append),
            pub_tiefe=types.SimpleNamespace(publish=depth.append),
            pub_info_c=types.SimpleNamespace(publish=lambda m: None),
            pub_info_d=types.SimpleNamespace(publish=lambda m: None))
        simulator.Simulator.kamera(n)
        simulator.Simulator.tiefe(n)
        self.assertEqual(rgb[0].header.frame_id, depth[0].header.frame_id)
        self.assertEqual(depth[0].header.frame_id, 'camera_color')

    def test_depth_needs_the_visible_corridor_not_one_valid_pixel(self):
        from tiefe import Bodenmodell
        model = Bodenmodell({'kamera_x': .12, 'kamera_hoehe': .2769,
                             'kamera_neigung': 52.18, 'kamera_fov': 67.4425782457611})
        image = np.full((480, 640), .4, dtype=np.float32)
        self.assertTrue(f.tiefe_messung_gueltig(image, model))
        sparse = np.zeros_like(image)
        sparse[200, 300] = .4
        self.assertFalse(f.tiefe_messung_gueltig(sparse, model))
        partial = image.copy()
        partial[320:, :] = 0.
        self.assertFalse(f.tiefe_messung_gueltig(partial, model))
        image[:] = np.nan
        self.assertFalse(f.tiefe_messung_gueltig(image, model))

    def setUp(self):
        self.w = dict(lidar=float('inf'), blick='fahr', tiefe_gueltig=True,
                      tiefe_hindernis=False, tiefe_aufnahme=100., tiefe_empfang=20., aufnahme=100.)
        self.command = dict(aktion='fahren', faktor=1., grund='Linie', arm=None, manoever=None)

    def checked(self, w=None, cmd=None):
        return f.befehl_sichern(cmd or self.command, w or self.w, 100.1, 20.1, True)

    def test_fresh_depth_and_clear_scene_allow_the_driving_decision(self):
        self.assertEqual(self.checked()['aktion'], 'fahren')

    def test_depth_obstacle_or_failed_measurement_stop(self):
        for change in ({'tiefe_hindernis': True}, {'tiefe_hindernis': None}, {'tiefe_gueltig': False},
                       {'tiefe_aufnahme': 99.}, {'tiefe_aufnahme': 101.}, {'tiefe_empfang': None},
                       {'tiefe_empfang': 19.}, {'aufnahme': 99.}, {'blick': 'pruef'}, {'lidar': None}):
            with self.subTest(change=change):
                cmd = self.checked(dict(self.w, **change))
                self.assertEqual((cmd['aktion'], cmd['faktor'], cmd['arm'], cmd['manoever']),
                                 ('stopp', 0.0, None, None))

    def test_arm_and_ki_manoeuvres_are_never_executed(self):
        for extra in ({'arm': 'fahrstellung'}, {'arm': 'pruefblick'}, {'manoever': {'lin': .1}}):
            cmd = self.checked(cmd=dict(self.command, **extra))
            self.assertEqual((cmd['aktion'], cmd['arm'], cmd['manoever']), ('stopp', None, None))


class FinalPublisher(unittest.TestCase):
    def heartbeat(self, n):
        ids = dict(session_id='test', generation=1, start_id='test')
        if hasattr(n, 'betrieb'):
            n.betrieb.empfang(dict(ids, angefordert=True))
            n.start_bereit = lambda: True  # Hier wird nur der finale Publisher isoliert.
        n.ki = (q.time.time(), dict(ids, aktion='fahren', begleiteter_fahrbetrieb=True,
                                  sensoren_bereit=True))

    def ready(self):
        n = node(q.lf.LineFollower)
        n._p.update(drive=True, show=False, publish_image=False)
        self.heartbeat(n)
        return n

    def test_actual_publisher_has_no_artificial_speed_or_six_second_limit(self):
        n = self.ready()
        with mock.patch.object(n, '_wunsch', return_value=(.15, 0., .5, 'Linie')):
            for elapsed in (0, 7, 60):
                with q.spaeter(elapsed):
                    c.feed(n)
                    self.heartbeat(n)
                    n.steuern()
                    t = n.pub.letzte
                    self.assertEqual((t.linear.x, t.linear.y, t.angular.z), (.15, 0., .5))

    def test_missing_source_reaches_zero_even_with_valid_motion_request(self):
        n = self.ready()
        n.scans.pop('/scan1')
        with mock.patch.object(n, '_wunsch', return_value=(.15, 0., 0., 'Linie')):
            n.steuern()
        self.assertEqual(n.pub.letzte.linear.x, 0.)

    def test_front_coverage_exception_cannot_authorize_reverse_sideways_or_search_rotation(self):
        for command in ((-.1, 0., 0.), (0., .1, 0.), (0., 0., .5)):
            n = self.ready()
            with mock.patch.object(n, '_wunsch', return_value=(*command, 'keine Vorwaertslinie')):
                n.steuern()
            self.assertEqual((n.pub.letzte.linear.x, n.pub.letzte.linear.y, n.pub.letzte.angular.z), (0., 0., 0.))

    def test_mode_mismatch_and_disabled_required_checks_stop(self):
        for change in ({'ki_pflicht': False}, {'obstacle_check': False}, {}):
            n = self.ready()
            n._p.update(change)
            if not change:
                n.ki[1]['begleiteter_fahrbetrieb'] = False
            with mock.patch.object(n, '_wunsch', return_value=(.15, 0., 0., 'Linie')):
                n.steuern()
            self.assertEqual(n.pub.letzte.linear.x, 0.)

    def test_genuine_hold_is_not_replaced_by_a_timer_or_missing_source_override(self):
        n = self.ready()
        with mock.patch.object(n, '_wunsch', return_value=(.15, 0., 0., 'Linie')):
            n.steuern()
            self.assertGreater(n.pub.letzte.linear.x, 0.)
            n.scans.pop('/scan1')
            n.steuern()
            self.assertEqual(n.pub.letzte.linear.x, 0.)

    def test_live_mode_changes_are_rejected_in_both_consumers(self):
        p = types.SimpleNamespace(name='begleiteter_fahrbetrieb', value=True)
        self.assertFalse(f.parameter_aenderung([p]).successful)
        n = self.ready()
        self.assertFalse(n._parameter_geaendert([p]).successful)


if __name__ == '__main__':
    unittest.main()
