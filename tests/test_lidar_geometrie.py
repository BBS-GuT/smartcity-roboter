#!/usr/bin/env python3
"""L4 (#63): reine Sensor-zu-Roboter-Transformation mit Frame- und Quellenbezug (noch ohne Verbraucher).

p_basis = R(-scan_front_deg) * p_sensor + (x, y). Werks-URDF-Werte nur als ausdruecklicher Modellbezug
('werksmodell'), nie als vermessene Pose. Aufruf: python3 tests/test_lidar_geometrie.py
"""
import math
import os
import sys
import types
import unittest

import numpy as np
import yaml

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, '..', 'lib'))
import lidar  # noqa: E402

# Werks-URDF (M3Pro.urdf, docs/pruefungen/lidar-20261021/historische_geometrie.py): Rechenbezug, KEINE Vermessung
MODELL = {'laser0_frame': (-0.11617, 0.09156), 'laser1_frame': (0.10766, -0.09078)}


def modell(frame):
    return lidar.Einbau(frame, *MODELL[frame], 'werksmodell')


def scan_mit_punkt(x, y, frame):
    """Ein Strahl, der genau den Sensorpunkt (x, y) misst."""
    return types.SimpleNamespace(ranges=[math.hypot(x, y)], angle_min=math.atan2(y, x), angle_increment=0.01,
                                 range_min=0.05, range_max=12.0, header=types.SimpleNamespace(frame_id=frame))


class Transformation(unittest.TestCase):
    def nah(self, a, b):
        np.testing.assert_allclose(np.asarray(a).reshape(-1, 2), np.asarray(b).reshape(-1, 2), atol=1e-9)

    def test_nullpose(self):
        e = lidar.Einbau('laser0_frame', 0.0, 0.0, 'gemessen')
        self.nah(lidar.sensor_zu_basis([[0.5, -0.2]], 0.0, e), [[0.5, -0.2]])

    def test_reine_verschiebung(self):
        e = lidar.Einbau('laser0_frame', 0.1, -0.05, 'gemessen')
        self.nah(lidar.sensor_zu_basis([[0.5, -0.2]], 0.0, e), [[0.6, -0.25]])

    def test_reine_drehung(self):
        # scan_front_deg 90: der LiDAR sieht die Roboter-Vorderrichtung bei Sensorwinkel +90 Grad
        e = lidar.Einbau('laser0_frame', 0.0, 0.0, 'gemessen')
        self.nah(lidar.sensor_zu_basis([[0.0, 1.0], [1.0, 0.0]], 90.0, e), [[1.0, 0.0], [0.0, -1.0]])

    def test_drehung_und_verschiebung(self):
        e = lidar.Einbau('laser0_frame', 0.2, 0.1, 'gemessen')
        self.nah(lidar.sensor_zu_basis([[0.0, 1.0]], 90.0, e), [[1.2, 0.1]])
        self.nah(lidar.sensor_zu_basis([[1.0, 0.0]], 180.0, e), [[-0.8, 0.1]])

    def test_gleiche_drehung_wie_punkte_xy(self):
        # punkte_xy dreht schon mit scan_front_deg -> nach_basis verschiebt nur noch (keine doppelte Drehung)
        e = lidar.Einbau('laser0_frame', 0.2, 0.1, 'gemessen')
        m = scan_mit_punkt(0.0, 1.0, 'laser0_frame')
        self.nah(lidar.nach_basis(lidar.punkte_xy(m, 90.0), e), lidar.sensor_zu_basis([[0.0, 1.0]], 90.0, e))
        xy, grund = lidar.punkte_basis(m, 90.0, e)
        self.assertIsNone(grund)
        self.nah(xy, [[1.2, 0.1]])

    def test_abstaende_bleiben_unveraendert(self):
        # Koordinatenabbildung ist keine Distanzkorrektur: Abstand zum Sensorursprung bleibt gleich
        e = lidar.Einbau('laser1_frame', 0.10766, -0.09078, 'gemessen')
        p = np.array([[0.498, 0.0], [0.0, 1.002], [-0.7, 0.3]])
        b = lidar.sensor_zu_basis(p, 37.0, e) - [e.x, e.y]
        np.testing.assert_allclose(np.hypot(b[:, 0], b[:, 1]), np.hypot(p[:, 0], p[:, 1]))

    def test_schon_im_roboterbezug_nicht_nochmal_verschieben(self):
        e = lidar.Einbau('base_link', 0.0, 0.0, 'gemessen')
        m = scan_mit_punkt(0.3, 0.2, 'base_link')
        xy, grund = lidar.punkte_basis(m, 0.0, e)
        self.assertIsNone(grund)
        self.nah(xy, [[0.3, 0.2]])


class Gegenbeispiele(unittest.TestCase):
    """Die drei Faelle aus #59 mit dem Werksmodell als ausdruecklichem Rechenbezug."""

    def basis(self, x, y, frame):
        xy, grund = lidar.punkte_basis(scan_mit_punkt(x, y, frame), 0.0, modell(frame), nur_gemessen=False)
        self.assertIsNone(grund)
        return xy

    def test_vorne_uebersehen(self):
        xy = self.basis(0.30, 0.20, 'laser1_frame')
        np.testing.assert_allclose(xy, [[0.40766, 0.10922]], atol=1e-6)
        self.assertIsNone(lidar.fahrschlauch(lidar.punkte_xy(scan_mit_punkt(0.30, 0.20, 'x')), None, 0.15, 0.80))
        self.assertIsNotNone(lidar.fahrschlauch(xy, None, 0.15, 0.80))

    def test_seitlich_faelschlich_im_fahrschlauch(self):
        xy = self.basis(0.40, -0.10, 'laser1_frame')
        np.testing.assert_allclose(xy, [[0.50766, -0.19078]], atol=1e-6)
        self.assertIsNotNone(lidar.fahrschlauch(lidar.punkte_xy(scan_mit_punkt(0.40, -0.10, 'x')), None, 0.15, 0.80))
        self.assertIsNone(lidar.fahrschlauch(xy, None, 0.15, 0.80))

    def test_hinten_uebersehen(self):
        xy = self.basis(-0.30, -0.20, 'laser0_frame')
        np.testing.assert_allclose(xy, [[-0.41617, -0.10844]], atol=1e-6)

        def im_rueckstreifen(p):
            return bool(np.any((p[:, 0] < -0.05) & (np.abs(p[:, 1]) < 0.15)))
        self.assertFalse(im_rueckstreifen(lidar.punkte_xy(scan_mit_punkt(-0.30, -0.20, 'x'))))
        self.assertTrue(im_rueckstreifen(xy))


class Gueltigkeit(unittest.TestCase):
    def test_ungueltige_bezuege(self):
        gut = lidar.Einbau('laser0_frame', 0.1, 0.0, 'gemessen')
        faelle = {
            'Pose fehlt': (None, 'laser0_frame'),
            'Scan ohne Frame': (gut, ''),
            'Frame None': (gut, None),
            'anderer Frame': (gut, 'laser1_frame'),
            'Pose unbekannt': (lidar.Einbau('laser0_frame', float('nan'), 0.0, 'gemessen'), 'laser0_frame'),
            'Quelle unbekannt': (lidar.Einbau('laser0_frame', 0.1, 0.0, 'unbekannt'), 'laser0_frame'),
            'base_link mit Verschiebung': (lidar.Einbau('base_link', 0.1, 0.0, 'gemessen'), 'base_link'),
            'nur Werksmodell': (modell('laser0_frame'), 'laser0_frame'),
        }
        for name, (einbau, frame) in faelle.items():
            with self.subTest(name):
                self.assertIsNotNone(lidar.einbau_pruefen(einbau, frame))
                m = scan_mit_punkt(0.3, 0.2, frame)
                self.assertEqual(lidar.punkte_basis(m, 0.0, einbau)[0], None)
        self.assertIsNone(lidar.einbau_pruefen(gut, 'laser0_frame'))
        self.assertIsNone(lidar.einbau_pruefen(modell('laser0_frame'), 'laser0_frame', nur_gemessen=False))

    def test_parameter(self):
        topics = ['/scan0', '/scan1']
        einbau, grund = lidar.einbau_aus_parametern(topics, ['laser0_frame', 'laser1_frame'],
                                                    [-0.1, 0.09, 0.1, -0.09], ['gemessen', 'werksmodell'])
        self.assertIsNone(grund)
        self.assertEqual(einbau['/scan1'], lidar.Einbau('laser1_frame', 0.1, -0.09, 'werksmodell'))
        for name, args in {'xy zu kurz': (['a', 'b'], [0.0, 0.0], ['gemessen'] * 2),
                           'Frame leer': (['a', ''], [0.0] * 4, ['gemessen'] * 2),
                           'Quelle falsch': (['a', 'b'], [0.0] * 4, ['gemessen', 'urdf']),
                           'keine Zahl': (['a', 'b'], [0.0, 'x', 0.0, 0.0], ['gemessen'] * 2),
                           'nicht gesetzt': ([], [], [])}.items():
            with self.subTest(name):
                self.assertEqual(lidar.einbau_aus_parametern(topics, *args)[0], None)

    def test_konfiguration_enthaelt_keine_vermessung(self):
        # Solange #66 keine gemessene RM01-Pose liefert, steht keine (Werks-)Pose als Kalibrierung in der Konfig
        with open(os.path.join(HIER, '..', 'config', 'roboter.yaml')) as f:
            werte = yaml.safe_load(f)['/**']['ros__parameters']
        for name in ('scan_frames', 'scan_einbau_xy', 'scan_einbau_quelle'):
            self.assertNotIn(name, werte)


if __name__ == '__main__':
    unittest.main()
