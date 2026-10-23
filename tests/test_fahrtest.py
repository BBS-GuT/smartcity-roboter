"""Supervised short test: measured holes stay unknown; genuine holds remain."""
import json
import math
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_lidar_fusion_verbraucher as c

q = c.q
f = q.lf.fahrtest


def node(make):
    n = make()
    c.configure(n)
    n._p.update(begleiteter_fahrtest=True, scan_einbau_xy=[-.1, .05, .2, -.05])
    c.feed(n)
    return n


def query(n):
    return n.notbremse(.1, 0, 0) if hasattr(n, 'notbremse') else n.lidar_pruefen()[0]


class SensorGuards(unittest.TestCase):
    def test_only_explicit_mode_accepts_a_measured_coverage_hole(self):
        for make in (q.lf.LineFollower, q.zentrale.Zentrale):
            n = node(make)
            n._p['begleiteter_fahrtest'] = False
            self.assertTrue(query(n) if hasattr(n, 'notbremse') else query(n) is None)
            n._p['begleiteter_fahrtest'] = True
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
        self.assertTrue(data['begleiteter_fahrtest'])
        self.assertEqual(data['aktion'], 'fahren')
        self.assertIsNone(data['lidar'])
        self.assertEqual(data['lidar_abdeckung'], 'unbekannt')
        self.assertIsNotNone(data['lidar_erste_luecke_m'])


class DepthAndArm(unittest.TestCase):
    def setUp(self):
        self.w = dict(lidar=float('inf'), blick='fahr', tiefe_gueltig=True,
                      tiefe_hindernis=False, tiefe_aufnahme=100., tiefe_empfang=20., aufnahme=100.)
        self.command = dict(aktion='fahren', faktor=1., grund='Linie', arm=None, manoever=None)

    def checked(self, w=None, cmd=None):
        return f.befehl_sichern(cmd or self.command, w or self.w, 100.1, 20.1, True)

    def test_fresh_depth_and_clear_scene_allow_only_the_test_decision(self):
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
    def ready(self):
        n = node(q.lf.LineFollower)
        n._p.update(drive=True, show=False, publish_image=False)
        n.ki = (q.time.time(), {'aktion': 'fahren', 'begleiteter_fahrtest': True})
        return n

    def test_actual_publisher_is_speed_limited_and_latches_after_six_seconds(self):
        n = self.ready()
        with mock.patch.object(n, '_wunsch', return_value=(.15, 0., .5, 'Linie')):
            n.steuern()
            t = n.pub.letzte
            radius = math.hypot(.2, .15)
            self.assertGreater(t.linear.x, 0)
            self.assertLessEqual(abs(t.linear.x) + abs(t.angular.z)*radius, .0500001)
            with q.spaeter(7):
                c.feed(n)  # even genuinely NEW valid scans cannot extend the six-second attempt
                n.steuern()
            t = n.pub.letzte
            self.assertEqual((t.linear.x, t.linear.y, t.angular.z), (0., 0., 0.))
            n.steuern()
            self.assertEqual(n.pub.letzte.linear.x, 0.)
            self.assertIn('beendet', json.loads(n.pub_status.letzte.data)['status'])

    def test_missing_source_reaches_zero_even_with_valid_motion_request(self):
        n = self.ready()
        n.scans.pop('/scan1')
        with mock.patch.object(n, '_wunsch', return_value=(.15, 0., 0., 'Linie')):
            n.steuern()
        self.assertEqual(n.pub.letzte.linear.x, 0.)

    def test_mode_mismatch_and_disabled_required_checks_stop(self):
        for change in ({'ki_pflicht': False}, {'obstacle_check': False}, {}):
            n = self.ready()
            n._p.update(change)
            if not change:
                n.ki[1]['begleiteter_fahrtest'] = False
            with mock.patch.object(n, '_wunsch', return_value=(.15, 0., 0., 'Linie')):
                n.steuern()
            self.assertEqual(n.pub.letzte.linear.x, 0.)

    def test_hold_after_motion_prevents_automatic_restart(self):
        attempt = f.Kurzfahrt()
        attempt.begrenze(.1, 0, 0, 'Linie', [.2, .2, .15, .15], 10., True)
        attempt.begrenze(0, 0, 0, 'Hindernis', [.2, .2, .15, .15], 10.2, True)
        self.assertEqual(attempt.begrenze(.1, 0, 0, 'frei', [.2, .2, .15, .15], 10.3, True)[:3], (0, 0, 0))

    def test_monitoring_without_drive_does_not_consume_the_attempt(self):
        attempt = f.Kurzfahrt()
        attempt.begrenze(.1, 0, 0, 'TEST', [.2, .2, .15, .15], 10., False)
        self.assertIsNone(attempt.beginn)
        self.assertGreater(attempt.begrenze(.1, 0, 0, 'START', [.2, .2, .15, .15], 100., True)[0], 0)

    def test_live_mode_changes_are_rejected_in_both_consumers(self):
        p = types.SimpleNamespace(name='begleiteter_fahrtest', value=True)
        self.assertFalse(f.parameter_aenderung([p]).successful)
        n = self.ready()
        self.assertFalse(n._parameter_geaendert([p]).successful)


if __name__ == '__main__':
    unittest.main()
