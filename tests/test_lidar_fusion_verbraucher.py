#!/usr/bin/env python3
"""Synthetic complementary scans through actual KI/final-stop consumers; no hardware."""
import math
import sys
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_lidar_qualitaet as q


def configure(node):
    # Deliberately synthetic: physical device measurements stay outside product defaults.
    node._p.update(scan_frames=['laser_a', 'laser_b'], scan_einbau_xy=[-.1, .05, .1, -.05],
                   scan_einbau_quelle=['gemessen', 'gemessen'], fahrzeug_grenzen=[.2, .2, .15, .15])


def message(index, distance=3.0):
    lo = 0.0 if index == 0 else -math.pi
    msg = q.scan(distance, n=500, angle_min=lo, angle_increment=1.5 * math.pi / 499,
                 angle_max=lo + 1.5 * math.pi)
    msg.header.frame_id = 'laser_a' if index == 0 else 'laser_b'
    return msg


def feed(node, missing=None, distance=3.0):
    for i, topic in enumerate(['/scan0', '/scan1']):
        if topic == missing:
            continue
        msg = message(i, distance)
        (node._scan if hasattr(node, '_scan') else node.on_scan)(msg, topic, i)


class ConsumerGeometry(unittest.TestCase):
    def follower(self):
        n = q.lf.LineFollower()
        configure(n)
        return n

    def central(self):
        n = q.zentrale.Zentrale()
        configure(n)
        return n

    def test_main_counterexample_is_fixed_in_both_consumers(self):
        n = self.follower()
        feed(n)
        self.assertIsNone(n.notbremse(.1, 0, 0))
        z = self.central()
        feed(z)
        self.assertEqual(z.lidar_pruefen()[0], float('inf'))
        self.assertIsNotNone(z.lidar_sicht)

    def test_final_guard_all_motion_directions(self):
        n = self.follower()
        for command in ((.1, 0, 0), (-.1, 0, 0), (0, .05, 0), (0, -.05, 0), (0, 0, .2), (.1, .05, 0)):
            feed(n)
            with self.subTest(command=command):
                self.assertIsNone(n.notbremse(*command))

    def test_missing_and_stale_required_source_still_hold(self):
        for make in (self.follower, self.central):
            n = make()
            feed(n, missing='/scan0')
            result = n.notbremse(.1, 0, 0) if hasattr(n, 'notbremse') else n.lidar_pruefen()[0]
            self.assertTrue(result if hasattr(n, 'notbremse') else result is None)
            feed(n)
            with q.spaeter(1.1):
                result = n.notbremse(.1, 0, 0) if hasattr(n, 'notbremse') else n.lidar_pruefen()[0]
                self.assertTrue(result if hasattr(n, 'notbremse') else result is None)

    def test_wrong_frame_and_factory_pose_hold(self):
        for make in (self.follower, self.central):
            for kind in ('frame', 'source', 'hull'):
                n = make()
                if kind == 'source':
                    n._p['scan_einbau_quelle'][0] = 'werksmodell'
                elif kind == 'hull':
                    n._p['fahrzeug_grenzen'] = [0.0] * 4
                feed(n)
                if kind == 'frame':
                    msg = message(0)
                    msg.header.frame_id = 'wrong'
                    (n._scan if hasattr(n, '_scan') else n.on_scan)(msg, '/scan0', 0)
                result = n.notbremse(.1, 0, 0) if hasattr(n, 'notbremse') else n.lidar_pruefen()[0]
                self.assertTrue(result if hasattr(n, 'notbremse') else result is None)

    def test_new_config_cannot_reuse_old_coordinate_fields(self):
        n = self.follower()
        feed(n)
        n._p['scan_einbau_xy'] = [-.15, .05, .1, -.05]
        self.assertIn('Geometrie', n.notbremse(.1, 0, 0))

    def test_actual_obstacle_has_priority_over_unknown(self):
        n = self.follower()
        feed(n)
        m = message(1)
        # Hit at x=.25, y=0, in front of synthetic hull x=.20.
        angle = math.atan2(.05, .15)
        k = round((angle - m.angle_min) / m.angle_increment)
        m.ranges[k] = math.hypot(.15, .05)
        n.on_scan(m, '/scan1', 1)
        self.assertIn('NOTBREMSE', n.notbremse(.1, 0, 0))

    def test_common_blind_sector_is_not_filled(self):
        n = self.follower()
        for i, topic in enumerate(['/scan0', '/scan1']):
            m = message(i)
            for k in range(len(m.ranges)):
                angle = m.angle_min + k * m.angle_increment
                if abs(math.atan2(math.sin(angle), math.cos(angle))) < .8:
                    m.ranges[k] = 0.0
            n.on_scan(m, topic, i)
        self.assertIn('UNBEKANNT', n.notbremse(.1, 0, 0))

    def test_diagonal_movement_protects_outer_corner(self):
        n = self.follower()
        feed(n)
        m = message(1)
        # Outside both straight side strips, inside the diagonal swept corner.
        angle = math.atan2(.25, .15)
        k = round((angle - m.angle_min) / m.angle_increment)
        m.ranges[k] = math.hypot(.15, .25)
        n.on_scan(m, '/scan1', 1)
        self.assertIn('NOTBREMSE', n.notbremse(.1, .05, 0))

    def test_slow_query_cannot_release_expired_snapshot(self):
        for make, method in ((self.follower, 'schutz'), (self.central, 'pfad')):
            n = make()
            feed(n)
            original = getattr(q.lf.lidar_fusion.Sicht, method)
            monotonic, walltime = q.time.monotonic(), q.time.time()

            def slow(view, *args, **kwargs):
                result = original(view, *args, **kwargs)
                # New callbacks cannot make the snapshot just calculated fresh.
                with q.spaeter(2):
                    feed(n)
                q.time.monotonic = lambda: monotonic + 2
                q.time.time = lambda: walltime + 2
                return result

            with mock.patch.object(q.lf.lidar_fusion.Sicht, method, slow), \
                    mock.patch.object(q.time, 'monotonic', q.time.monotonic), \
                    mock.patch.object(q.time, 'time', q.time.time):
                result = n.notbremse(.1, 0, 0) if hasattr(n, 'notbremse') else n.lidar_pruefen()[0]
                self.assertTrue(result if hasattr(n, 'notbremse') else result is None)

    def test_acquisition_time_is_required_with_geometry(self):
        for make in (self.follower, self.central):
            n = make()
            feed(n)
            msg = message(0)
            msg.header.stamp.sec += 5
            (n._scan if hasattr(n, '_scan') else n.on_scan)(msg, '/scan0', 0)
            result = n.notbremse(.1, 0, 0) if hasattr(n, 'notbremse') else n.lidar_pruefen()[0]
            self.assertTrue(result if hasattr(n, 'notbremse') else result is None)

    def test_crossing_uses_the_same_measured_origin_area(self):
        from ablaeufe import Zebrastreifen
        from entscheider import STANDARD
        z = self.central()
        feed(z)
        self.assertEqual(z.lidar_pruefen()[0], float('inf'))
        crossing = Zebrastreifen(0, STANDARD, .45)
        perception = {'lidar_xy': z.lidar_xy, 'lidar_fusionssicht': z.lidar_sicht}
        self.assertIsNone(crossing._zone_ungemessen(perception))
        # A genuinely unmeasured zone, not an empty/free area, must still hold.
        feed(z, distance=.5)
        stamps = {t: e[4] for t, e in z.scans.items()}
        short, reason = z.scan_geometrie.sicht(stamps)
        self.assertIsNone(reason)
        perception['lidar_fusionssicht'] = short
        self.assertIn('nicht gemeinsam gemessen', crossing._zone_ungemessen(perception))

    def test_oversized_or_empty_query_never_means_free(self):
        z = self.central()
        feed(z)
        stamps = {t: e[4] for t, e in z.scans.items()}
        view, _ = z.scan_geometrie.sicht(stamps)
        self.assertFalse(view.zone_frei((-1000, 1000, -1000, 1000)))
        self.assertFalse(view.zone_frei((-.05, .05, -.05, .05)))

    def test_actual_ki_includes_front_overhang(self):
        z = self.central()
        feed(z)
        m = message(1)
        angle = math.atan2(.05, .8)
        k = round((angle - m.angle_min) / m.angle_increment)
        m.ranges[k] = math.hypot(.8, .05)
        z._scan(m, '/scan1', 1)
        self.assertNotEqual(z.lidar_pruefen()[0], float('inf'))

    def test_actual_ki_preserves_known_obstacle_instead_of_no_lidar(self):
        z = self.central()
        feed(z)
        m = message(1)
        angle = math.atan2(.05, .5)
        k = round((angle - m.angle_min) / m.angle_increment)
        m.ranges[k] = math.hypot(.5, .05)
        z._scan(m, '/scan1', 1)
        distance, obj, _ = z.lidar_pruefen()
        self.assertIsNotNone(distance)
        self.assertIsNotNone(obj)
        self.assertGreater(distance, .55)
        self.assertLessEqual(distance, .61)
        self.assertAlmostEqual(obj['vor'], .6, delta=.01)

    def test_actual_ki_sees_outer_curve_corner(self):
        z = self.central()
        z.weg_voraus = lambda: [(0.4, 0.0), (0.4, 0.4)]
        feed(z)
        m = message(1)
        angle = math.atan2(.1, .52)
        k = round((angle - m.angle_min) / m.angle_increment)
        m.ranges[k] = math.hypot(.52, .1)
        z._scan(m, '/scan1', 1)
        distance, obj, _ = z.lidar_pruefen()
        self.assertIsNotNone(distance)
        self.assertIsNotNone(obj)
        self.assertLess(distance, float('inf'))

    def test_a_genuine_gap_before_an_obstacle_still_holds_unknown(self):
        z = self.central()
        feed(z)
        m = message(1)
        angle = math.atan2(.05, .5)
        k = round((angle - m.angle_min) / m.angle_increment)
        m.ranges[k] = math.hypot(.5, .05)
        for j in range(len(m.ranges)):
            a = m.angle_min + j * m.angle_increment
            if math.radians(-15) < a < math.radians(-5):
                m.ranges[j] = 0.0
        z._scan(m, '/scan1', 1)
        self.assertIsNone(z.lidar_pruefen()[0])

    def test_actual_ki_reports_partial_rear_clearance(self):
        z = self.central()
        feed(z)
        m = message(0)
        for k in range(len(m.ranges)):
            angle = m.angle_min + k * m.angle_increment
            if math.cos(angle) < -.01:
                m.ranges[k] = min(3.0, -.6 / math.cos(angle))
        z._scan(m, '/scan0', 0)
        z.lidar_d = z.lidar_pruefen()[0]
        self.assertEqual(z.lidar_d, float('inf'))
        distance = z.lidar_hinten()
        self.assertIsNotNone(distance)
        self.assertGreater(distance, .5)
        self.assertLessEqual(distance, .7)


if __name__ == '__main__':
    unittest.main()
