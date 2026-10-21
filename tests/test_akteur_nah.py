#!/usr/bin/env python3
"""Wegraeumen: nur NAHE Personen/Tiere/Fahrzeuge halten an; Hintergrund (weiter als akteur_nah) nicht.

Echter Entscheider, natuerliche Phasen, reiner Planerstub; Tiefe-Abstand mit kuenstlichen Tiefenbildern.
Kein ROS, kein Geraet.
"""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
from raeum_lauf import AKTEURE, Lauf, bewegt  # noqa: E402
from tiefe import abstand_im_kasten  # noqa: E402

OBJ = {'vor': 0.28, 'seite': 0.0, 'quer': 0.0, 'breite': 0.04, 'hoehe': 0.04, 'quelle': 'tiefe'}


def durchlauf(akteur=None, nah=True, schritte=400):
    """Wegraeumen bis 'fahren'; ab dem ersten Bild sieht die KI den Akteur (nah oder fern)."""
    lauf = Lauf()
    weg, arme, b = False, [], None
    objekte = [] if akteur is None else [{'name': akteur, 'im_weg': False, 'nah': nah}]
    for _ in range(schritte):
        w = {} if weg else {'lidar': 0.28, 'objekt': dict(OBJ), 'tiefe_hindernis': True}
        b = lauf.schritt(objekte=objekte, **w)
        a = b['arm']
        if a is not None:
            arme.append(a)
        weg = weg or (isinstance(a, dict) and (a.get('winkel') or [0] * 6)[5] == 130)
        if b['aktion'] == 'fahren':
            break
    return lauf, arme, b


class AkteurNah(unittest.TestCase):
    def test_hintergrund_haelt_nicht_auf(self):
        ohne = durchlauf()
        for akteur in AKTEURE:
            with self.subTest(akteur=akteur):
                lauf, arme, b = durchlauf(akteur, nah=False)
                self.assertEqual(b['aktion'], 'fahren')
                self.assertTrue(weggeraeumt(arme))
                self.assertAlmostEqual(lauf.t, ohne[0].t, delta=0.15)    # genauso schnell wie ganz ohne Akteur

    def test_nah_haelt_wie_bisher(self):
        for akteur in AKTEURE:
            with self.subTest(akteur=akteur):
                lauf, arme, b = durchlauf(akteur, nah=True, schritte=200)
                self.assertFalse(weggeraeumt(arme))                       # nicht anfassen
                self.assertNotEqual(b['aktion'], 'fahren')
                self.assertTrue(any(f'Hindernis ist {akteur}' in t for _, t, _ in lauf.e.ereignisse))

    def test_ohne_angabe_zaehlt(self):
        """Fehlt 'nah' (alte Daten, keine Tiefe): zaehlt wie nah - nicht anfassen."""
        lauf = Lauf()
        arme = []
        for _ in range(200):
            b = lauf.schritt(akteur='Person', im_weg=False, lidar=0.28, objekt=dict(OBJ), tiefe_hindernis=True)
            if b['arm'] is not None:
                arme.append(b['arm'])
        self.assertFalse(weggeraeumt(arme))
        self.assertTrue(any('Hindernis ist Person' in t for _, t, _ in lauf.e.ereignisse))

    def test_nah_waehrend_greifen_haelt_fern_nicht(self):
        for nah in (True, False):
            with self.subTest(nah=nah):
                lauf = Lauf()
                for _ in range(200):
                    b = lauf.schritt(lidar=0.28, objekt=dict(OBJ), tiefe_hindernis=True)
                    if lauf.phase() == 'ausfuehren':
                        break
                b = lauf.schritt(objekte=[{'name': 'Person', 'im_weg': False, 'nah': nah}],
                                 lidar=0.28, objekt=dict(OBJ), tiefe_hindernis=True)
                gehalten = 'Arm haelt still' in b['grund']
                self.assertEqual(gehalten, nah, b['grund'])


def weggeraeumt(arme):
    return any(isinstance(a, dict) and (a.get('winkel') or [0] * 6)[5] == 130 for a in arme)


class AbstandImKasten(unittest.TestCase):
    def test_person_vor_hintergrund(self):
        d = np.full((240, 320), 3.0, np.float32)           # Wand 3 m
        d[60:200, 100:160] = 0.8                           # Person 0,8 m, fuellt etwa die Haelfte des Kastens
        box = (180, 100, 180, 320)                          # Kasten im Farbbild 640 x 480 (doppelte Aufloesung)
        self.assertAlmostEqual(abstand_im_kasten(d, box, (480, 640)), 0.8, places=3)

    def test_fern(self):
        d = np.full((240, 320), 2.5, np.float32)
        self.assertAlmostEqual(abstand_im_kasten(d, (0, 0, 100, 100), (480, 640)), 2.5, places=3)

    def test_zu_nah_fuer_die_tiefenkamera_ist_unsicher(self):
        d = np.full((240, 320), 3.0, np.float32)
        d[40:220, 60:200] = 0.0                             # Person naeher als messbar: keine Tiefe
        self.assertIsNone(abstand_im_kasten(d, (100, 60, 320, 400), (480, 640)))

    def test_ohne_tiefenbild(self):
        self.assertIsNone(abstand_im_kasten(None, (0, 0, 10, 10), (480, 640)))


if __name__ == '__main__':
    unittest.main(verbosity=2)
