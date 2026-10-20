#!/usr/bin/env python3
"""Karte bei Rechner-Aussetzern (Roboter-Aufnahme 20.10.: 50 Luecken von 0,6-2,3 s in IMU, Odometrie, LiDAR).
Ohne ROS, nur lib/kartierer.py und lib/karte.py. Aufruf: python3 tests/test_kartenluecken.py"""
import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import karte as K        # noqa: E402
import kartierer as KR   # noqa: E402


def drehfahrt(kr, dauer=6.0, wz=0.5, luecke=(2.0, 3.5), t0=1000.0):
    """Roboter dreht sich auf der Stelle (wz rad/s). IMU 50 Hz, Odometrie 20 Hz (mit Position), in 'luecke'
    kommt NICHTS an (wie beim Haenger auf dem Roboter). Rueckgabe: wahre Drehung."""
    ereignisse = []
    for i in range(int(dauer * 50)):
        ereignisse.append((t0 + i / 50, 'imu'))
    for i in range(int(dauer * 20)):
        ereignisse.append((t0 + i / 20 + 0.003, 'odom'))
    for t, art in sorted(ereignisse):
        if luecke[0] <= t - t0 < luecke[1]:
            continue
        w = wz * (t - t0)
        if art == 'imu':
            kr.imu(t, {'stamp': t, 'g': [0.0, 0.0, wz], 'a': [0.0, 0.0, 9.8]})
        else:
            kr.odom(t, {'stamp': t, 'vx': 0.0, 'vy': 0.0, 'wz': wz, 'x': 0.0, 'y': 0.0, 'w': K.winkel(w)})
    return wz * (dauer - 1 / 50)


class Luecken(unittest.TestCase):
    def test_drehung_ueber_luecke_geht_nicht_verloren(self):
        kr = KR.Kartierer(K.Karte('/nicht/benutzt'), {'selbst_kalibrieren': False})
        wahr = drehfahrt(kr)
        gerechnet = kr.roboter[2]
        # vorher fehlten die 1,5 s der Luecke (0,75 rad = 43 Grad)
        self.assertLess(abs(K.winkel(gerechnet - wahr)), math.radians(4),
                        f'gerechnet {math.degrees(gerechnet):.1f}, wahr {math.degrees(wahr):.1f} Grad')

    def test_strecke_ueber_luecke_geht_nicht_verloren(self):
        kr = KR.Kartierer(K.Karte('/nicht/benutzt'), {'selbst_kalibrieren': False})
        t0, v = 1000.0, 0.15
        for i in range(120):                     # 6 s geradeaus, Odometrie 20 Hz, 1,5 s Luecke
            t = t0 + i / 20
            if 2.0 <= t - t0 < 3.5:
                continue
            kr.imu(t, {'stamp': t, 'g': [0.0, 0.0, 0.0], 'a': [0.0, 0.0, 9.8]})
            kr.odom(t + 0.003, {'stamp': t + 0.003, 'vx': v, 'vy': 0.0, 'wz': 0.0, 'x': v * (t - t0), 'y': 0.0, 'w': 0.0})
        self.assertAlmostEqual(kr.roboter[0], v * 119 / 20, delta=0.03)


class NeuesGebiet(unittest.TestCase):
    """Unsichere Position darf keine Scans als 'neues Gebiet' in die Karte malen (verdrehtes zweites Zimmer)."""

    def raum(self, seite=2.0, n=400):
        t = np.linspace(0, 4 * seite, n, endpoint=False)
        pts = []
        for s in t:
            k, r = divmod(s, seite)
            pts.append([(r - seite / 2, -seite / 2), (seite / 2, r - seite / 2),
                        (seite / 2 - r, seite / 2), (-seite / 2, seite / 2 - r)][int(k)])
        return np.array(pts)

    def test_kein_eintrag_lange_nach_dem_letzten_sicheren(self):
        karte = K.Karte('/nicht/benutzt')
        lok = K.Lokalisierung(karte)
        punkte = self.raum()
        lok.scan(punkte, 0.0)                         # erster Scan: Karte entsteht
        vorher = karte.belegung.lo.copy()
        lok.zuletzt_sicher = 0.0
        # 10 s spaeter, Position voellig falsch (z. B. umgesetzt): Scan landet an falscher Stelle im Unbekannten
        lok.pose = (5.0, 5.0, 1.0)
        lok.unsicher_seit = 1.0
        lok.scan(punkte, 10.0)
        self.assertTrue(np.array_equal(karte.belegung.lo, vorher), 'Geister-Scan wurde eingetragen')

    def test_kurz_nach_sicher_darf_neues_gebiet(self):
        karte = K.Karte('/nicht/benutzt')
        lok = K.Lokalisierung(karte)
        lok.scan(self.raum(), 0.0)
        self.assertTrue(lok._kurz_nach_sicher(0.5))


if __name__ == '__main__':
    unittest.main(verbosity=2)
