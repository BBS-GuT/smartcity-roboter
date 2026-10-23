"""Synthetic floor reference uses real renderer geometry and strict production matching."""
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import yaml
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'lib'), str(ROOT / 'sim')]
from welt import Welt, KAMERA
from tiefe import Bodenmodell
from tiefenstatus import tiefe_messung_gueltig

import lidar_geometrie as simgeo
ns = vars(simgeo)

class SimulatorReference(unittest.TestCase):
    def test_rendered_reference_matches_actual_grid_frame_intrinsics_and_floor(self):
        pose = [90, 120, 10, 20, 90, 30]
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / 'sim-floor.npz')
            cfg = ns['simulations_bodenreferenz'](path, pose)
            camera = {k: v for k, v in cfg.items() if k.startswith('kamera_')}
            model = Bodenmodell(camera)
            model.lade_referenz(path, pose)
            world = Welt.__new__(Welt); world._cache = {}
            _, rays, focal, depth, _, _, _ = world._vorberechnet(0., 2)
            k = ns['kamera_intrinsik'](320, 240)
            self.assertTrue(model.referenz_passt(depth.shape, 'camera_color', pose, k))
            self.assertAlmostEqual(focal, k[0])
            for row, col in ((0, 0), (120, 160), (239, 319)):
                expected = ((col-k[2])/k[0], (row-k[5])/k[4], 1.)
                origin, forward, right, down = world.kamera_achsen()
                np.testing.assert_allclose(rays[row, col],
                    expected[0]*right + expected[1]*down + forward, atol=1e-12)
            _, _, z = model.punkte(depth)
            valid = np.isfinite(z)
            np.testing.assert_allclose((z-model.korrektur)[valid], 0., atol=1e-6)
            self.assertFalse(model.referenz_passt((480, 640), 'camera_color', pose, k))
            self.assertFalse(model.referenz_passt(depth.shape, 'camera_color_optical_frame', pose, k))
            self.assertFalse(model.referenz_passt(depth.shape, 'camera_color', pose, [0.]*9))
            self.assertTrue(tiefe_messung_gueltig(depth, model))
            self.assertFalse(model.pruefe(depth, lernen=False)[0])
            self.assertTrue(model.eingefroren)
            self.assertIn('synthetisch', model.referenz['quellen'][0])

    def test_simulation_parameter_file_selects_own_reference_before_consumers_start(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, ROS_DOMAIN_ID='77'), \
             mock.patch.object(simgeo.tempfile, 'tempdir', tmp):
            parameter_path = simgeo.schreibe_parameter(arm_datei=ROOT / 'sim/arm_sim.yaml')
            with open(parameter_path, encoding='utf-8') as f:
                values = yaml.safe_load(f)['/**']['ros__parameters']
            with open(ROOT / 'sim/arm_sim.yaml', encoding='utf-8') as f:
                pose = yaml.safe_load(f)['posen']['fahrstellung']
            self.assertTrue(Path(values['bodenreferenz']).is_file())
            self.assertNotEqual(Path(values['bodenreferenz']).resolve(), (ROOT/'lib/bodenreferenz_rm01.npz').resolve())
            camera = {k: v for k, v in values.items() if k.startswith('kamera_')}
            model = Bodenmodell(camera)
            model.lade_referenz(values['bodenreferenz'], pose)
            self.assertTrue(model.referenz_passt((240, 320), 'camera_color', pose,
                simgeo.kamera_intrinsik(320, 240)))

    def test_real_rm01_reference_stays_rejected_for_simulated_camera_metadata(self):
        path = ROOT / 'lib/bodenreferenz_rm01.npz'
        with np.load(path, allow_pickle=False) as data:
            meta = json.loads(str(data['metadaten'].item()))
        model = Bodenmodell(meta['kamera'])
        model.lade_referenz(path, meta['pose'])
        self.assertFalse(model.referenz_passt((240, 320), 'camera_color',
            meta['pose'], ns['kamera_intrinsik'](320, 240)))
        self.assertTrue(model.referenz_passt(meta['bild_shape'], meta['frame'], meta['pose'], meta['k']))


if __name__ == '__main__':
    unittest.main()
