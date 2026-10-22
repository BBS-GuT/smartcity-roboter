#!/usr/bin/env python3
"""Free-space geometry only, without ROS, model loading or hardware."""
import math
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
import lidar
import lidar_fusion as fusion


def scan(start=-135, count=271, distance=3.0, frame='laser0_frame'):
    return types.SimpleNamespace(
        angle_min=math.radians(start), angle_max=math.radians(start + count - 1),
        angle_increment=math.radians(1), ranges=[distance] * count,
        range_min=.05, range_max=12.0,
        header=types.SimpleNamespace(frame_id=frame))


class FreeSpace(unittest.TestCase):
    def field(self, msg=None, x=0.0, y=0.0, front=0.0):
        msg = msg or scan()
        field, reason = fusion.messfeld(msg, front, lidar.Einbau(msg.header.frame_id, x, y, 'gemessen'))
        self.assertIsNone(reason)
        return field

    def test_free_and_occluded(self):
        f = self.field(scan(distance=.6))
        np.testing.assert_array_equal(f.frei([[.5, 0], [.7, 0], [-.5, 0]]), [True, False, False])

    def test_partial_scan_blind_sector_not_wrapped(self):
        f = self.field(scan(start=0))
        self.assertFalse(f.frei([[.5, -.05]])[0])
        self.assertTrue(f.frei([[.5, .05]])[0])

    def test_invalid_rays_do_not_interpolate(self):
        for value in (0, float('nan'), float('inf'), 12, -1):
            msg = scan()
            msg.ranges[135] = value
            self.assertFalse(self.field(msg).frei([[.5, 0]])[0], value)

    def test_measured_origins_change_visibility(self):
        msg = scan(distance=.5)
        f = self.field(msg, x=.1, y=-.05)
        self.assertTrue(f.frei([[.58, -.05]])[0])
        self.assertFalse(self.field(msg).frei([[.58, -.05]])[0])

    def test_complementary_sources_cover_without_missing_source_release(self):
        rear = self.field(scan(start=0), x=-.1, y=.05)
        front = self.field(scan(start=-180, frame='laser1_frame'), x=.1, y=-.05)
        p = [[.6, 0], [0, .6]]
        np.testing.assert_array_equal(fusion.gemeinsam_frei([rear, front], p), [True, True])
        np.testing.assert_array_equal(fusion.gemeinsam_frei([rear, None], p), [False, False])
        np.testing.assert_array_equal(fusion.gemeinsam_frei([], p), [False, False])

    def test_no_release_behind_both_hits(self):
        a = self.field(scan(distance=.2))
        self.assertFalse(fusion.gemeinsam_frei([a, a], [[.5, 0]])[0])

    def test_wrong_frame_and_factory_model_rejected(self):
        for pose in [lidar.Einbau('other', 0, 0, 'gemessen'),
                     lidar.Einbau('laser0_frame', 0, 0, 'werksmodell')]:
            self.assertIsNone(fusion.messfeld(scan(), 0, pose)[0])

    def test_nonfinite_points_never_free(self):
        f = self.field()
        np.testing.assert_array_equal(f.frei([[float('nan'), 0], [float('inf'), 0]]), [False, False])

    def test_cell_interior_invalid_ray_is_not_hidden_by_corners(self):
        msg = scan()
        msg.ranges[135] = 0.0
        f = self.field(msg)
        self.assertTrue(f.frei([[.5, -.04], [.5, .04], [.55, -.04], [.55, .04]]).all())
        self.assertFalse(f.zellen_frei([[.5, -.04]], [[.55, .04]])[0])

    def test_cells_free_shadow_and_sensor_origin(self):
        f = self.field(scan(distance=.6))
        np.testing.assert_array_equal(
            f.zellen_frei([[.3, -.01], [.7, -.01], [-.01, -.01]],
                          [[.35, .01], [.75, .01], [.01, .01]]),
            [True, False, False])

    def test_cell_crossing_blind_sector_is_unknown(self):
        f = self.field(scan(start=0))
        self.assertFalse(f.zellen_frei([[.3, -.02]], [[.4, .02]])[0])

    def test_near_corridor_outside_hull_has_no_assumed_own_part_cone(self):
        p = np.array([.17, .13])  # outside a synthetic small hull, beyond the old 30-degree cone
        view = fusion.Sicht((self.field(),), (.1, .1, .1, .1), p.reshape(1, 2))
        checked = []

        def coverage(fields, low, high):
            checked.append(np.any(((low <= p) & (p <= high)).all(axis=1)))
            return np.ones(len(low), dtype=bool)

        with mock.patch.object(fusion, 'gemeinsame_zellen', coverage):
            obj, gap = view.pfad(None, .15, .8)
        self.assertTrue(checked[0])
        self.assertIsNotNone(obj)
        self.assertIsNone(gap)

    def test_invalid_direction_never_releases(self):
        view = fusion.Sicht((self.field(),), (.1, .1, .1, .1), np.empty((0, 2)))
        for directions in ((), ('unknown',)):
            self.assertIn('UNBEKANNT', view.schutz(directions, .1))


if __name__ == '__main__':
    unittest.main()
