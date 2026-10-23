#!/usr/bin/env python3
"""Synthetic model/configuration and actual consumers, no ROS execution/device."""
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import test_lidar_qualitaet as q  # noqa: E402
sys.path.insert(0, str(ROOT / 'sim'))
import lidar_geometrie as simgeo  # noqa: E402
import einstellungen  # noqa: E402


def feed(node, values, configure=True):
    if configure:
        node._p.update(values)
    for index, topic in enumerate(values['scan_topics']):
        # A known base_link target at (.45, 0) generated from the model pose.
        x, y = values['scan_einbau_xy'][2 * index:2 * index + 2]
        angle = math.atan2(-y, .45 - x) + math.radians(values['scan_front_deg'][index])
        msg = q.scan(3.0, n=1440, angle_min=angle - math.pi, angle_increment=2 * math.pi / 1440)
        msg.header.frame_id = values['scan_frames'][index]
        if index == 1:
            msg.ranges[720] = math.hypot(.45 - x, y)
        (node._scan if hasattr(node, '_scan') else node.on_scan)(msg, topic, index)


class SyntheticModel(unittest.TestCase):
    def test_model_chain_and_driving_hull_include_arm(self):
        with open(ROOT / 'sim' / 'arm_sim.yaml', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        bounds = simgeo.parameter()['fahrzeug_grenzen']
        for geo in (data['geometrie'], dict(data['geometrie'], **data['geometrie_simulator'])):
            points = simgeo.arm_punkte(data['posen']['fahrstellung'], geo)
            expected = simgeo.arm.Kinematik(geo).vorwaerts(data['posen']['fahrstellung'])[0]
            np.testing.assert_allclose(points[-1], expected[:2], atol=1e-12)
            radius = simgeo.GREIFER_RADIUS_PX * simgeo.AUFLOESUNG
            self.assertLessEqual(points[-1, 0] + radius, bounds[0] + 1e-12)
            self.assertTrue(((points[:, 0] >= -bounds[1]) & (points[:, 0] <= bounds[0])
                             & (points[:, 1] >= -bounds[3]) & (points[:, 1] <= bounds[2])).all())
        self.assertGreater(bounds[0], simgeo.FAHRZEUG_GRENZEN[0])  # arm actually projects past body

    def test_standard_and_schwer_geometry_reach_both_actual_consumers(self):
        for schwer in (False, True):
            values = simgeo.parameter(schwer)
            if schwer:
                self.assertIn('lidar1_einbau:=[-0.12,0.0,4.0]', simgeo.schwer_argumente())
                self.assertEqual(values['scan_front_deg'][1], -4.0)
            for make in (q.lf.LineFollower, q.zentrale.Zentrale):
                node = make()
                feed(node, values)
                stamps = {t: e[3 if hasattr(node, 'notbremse') else 4] for t, e in node.scans.items()}
                view, reason = node.scan_geometrie.sicht(stamps)
                with self.subTest(schwer=schwer, consumer=make.__name__):
                    self.assertIsNone(reason)
                    self.assertTrue(np.any(np.linalg.norm(view.points - [.45, 0], axis=1) < 1e-8))
                    if hasattr(node, 'notbremse'):
                        self.assertIsNone(node.notbremse(.05, 0, 0))  # target beyond short guard
                        node._p['notbremse_dist'] = .3
                        self.assertIn('NOTBREMSE', node.notbremse(.05, 0, 0))
                    else:
                        _, obj, _ = node.lidar_pruefen()
                        self.assertAlmostEqual(obj['vor'], .45, places=6)

    def test_fault_overrides_are_not_confirmed_automatically(self):
        values = simgeo.parameter(True)
        for make in (q.lf.LineFollower, q.zentrale.Zentrale):
            node = make()
            feed(node, values)
            msg = q.scan(3.0)
            msg.header.frame_id = 'wrong_frame'
            (node._scan if hasattr(node, '_scan') else node.on_scan)(msg, '/scan1', 1)
            if hasattr(node, 'notbremse'):
                self.assertIn('UNBEKANNT', node.notbremse(.05, 0, 0))
            else:
                self.assertEqual(node.lidar_pruefen(), (None, None, None))


class ExplicitConfiguration(unittest.TestCase):
    def test_no_opt_in_keeps_device_defaults_even_in_domain77(self):
        with mock.patch.dict(os.environ, {'ROS_DOMAIN_ID': '77'}):
            os.environ.pop('SMARTCITY_SIM_PARAMETER', None)
            self.assertEqual(einstellungen.dateien(), [p for p in (einstellungen.STANDARD, einstellungen.AMPEL,
                                                                   einstellungen.LOKAL) if os.path.exists(p)])
            self.assertNotIn('scan_frames', einstellungen.lade('line_follower'))

    def test_wrong_domain_missing_unreadable_and_incomplete_configuration_hold(self):
        for domain in ('0', '30', '31', '78'):
            with mock.patch.dict(os.environ, ROS_DOMAIN_ID=domain, SMARTCITY_SIM_PARAMETER='not-a-file.yaml'):
                with self.assertRaises(ValueError):
                    einstellungen.ros_argumente()
                with self.assertRaises(ValueError):
                    simgeo.schreibe_parameter()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'sim.yaml'
            with mock.patch.dict(os.environ, ROS_DOMAIN_ID='77', SMARTCITY_SIM_PARAMETER=str(path)):
                with self.assertRaises(FileNotFoundError):
                    einstellungen.dateien()
                path.write_text('/**: [broken', encoding='utf-8')
                with self.assertRaises(yaml.YAMLError):
                    einstellungen.lade('line_follower')
                path.write_text('/**:\n  ros__parameters:\n    scan_frames: [laser0, laser1]\n', encoding='utf-8')
                values = einstellungen.lade('line_follower')
                node = q.lf.LineFollower()
                node._p.update(values)
                feed(node, simgeo.parameter(), configure=False)
                self.assertIn('UNBEKANNT', node.notbremse(.05, 0, 0))

    def test_real_parameter_generator_and_loader_share_the_explicit_file(self):
        env = dict(os.environ, ROS_DOMAIN_ID='77', SIM_SCHWER='1',
                   SMARTCITY_ARM_YAML=str(ROOT / 'sim' / 'arm_sim.yaml'))
        result = subprocess.run([sys.executable, str(ROOT / 'sim' / 'lidar_geometrie.py')],
                                env=env, text=True, capture_output=True, check=True)
        path = Path(result.stdout.strip())
        try:
            with mock.patch.dict(os.environ, ROS_DOMAIN_ID='77', SMARTCITY_SIM_PARAMETER=str(path)):
                args = einstellungen.ros_argumente()
                self.assertEqual(args[-2:], ['--params-file', str(path)])
                self.assertNotIn(einstellungen.LOKAL, args)
                values = einstellungen.lade('line_follower')
                node = q.lf.LineFollower()
                feed(node, values)
                self.assertIsNone(node.notbremse(.05, 0, 0))
        finally:
            path.unlink()


if __name__ == '__main__':
    unittest.main()
