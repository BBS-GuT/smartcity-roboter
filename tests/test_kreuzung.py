#!/usr/bin/env python3
"""Kreuzungen: zufaellig einen Ast waehlen und bis hinter die Kreuzung dabei bleiben (Zieldefinition 4.2).

Kamerabilder werden aus einer gezeichneten Draufsicht erzeugt (Linien 2,5 cm breit). Kein ROS, kein Geraet.
"""
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'line_follower'))
import linie  # noqa: E402

B, H = 640, 480


def bild(linien):
    """Kamerabild (BGR) mit schwarzen Linien [((x, y), (x, y)), ...] in Metern (x vorne, y links)."""
    s = linie.LinienSucher()
    s._vogel(B, H)
    bw, bh = s.vogel_groesse
    boden = np.full((bh, bw), 255, np.uint8)
    for a, b in linien:
        cv2.line(boden, tuple(int(v) for v in s._zu_raster(*a)), tuple(int(v) for v in s._zu_raster(*b)), 0,
                 int(0.025 / s.RASTER))
    img = cv2.warpPerspective(boden, np.linalg.inv(s.H), (B, H), borderValue=255)
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


# Die Kamera sieht den Boden ca. 25-47 cm vor der Robotermitte
T = bild([((0.0, 0.0), (0.36, 0.0)), ((0.36, -0.5), (0.36, 0.5))])
ABZWEIG = bild([((0.0, 0.0), (0.9, 0.0)), ((0.33, 0.0), (0.6, 0.4))])
GERADE = bild([((0.0, 0.0), (0.9, 0.05))])
U = bild([((0.0, 0.0), (0.30, 0.0)), ((0.30, 0.12), (0.0, 0.12))]
         + [((0.30 + 0.06 * math.sin(math.pi * k / 40), 0.06 - 0.06 * math.cos(math.pi * k / 40)),
             (0.30 + 0.06 * math.sin(math.pi * (k + 1) / 40), 0.06 - 0.06 * math.cos(math.pi * (k + 1) / 40)))
            for k in range(40)])

# Haltelinie: Querbalken (je 18 cm zur Seite, laenger als ast_min), endet im Bild -> keine Abzweigung
HALTELINIE = bild([((0.0, 0.0), (0.9, 0.0)), ((0.36, -0.18), (0.36, 0.18))])
# Zebrastreifen quer ueber die Strasse: Balken in Fahrtrichtung, Begrenzungen quer und laenger als das Bild breit
ZEBRA = bild([((0.0, 0.0), (0.9, 0.0)), ((0.36, -0.5), (0.36, 0.5)), ((0.44, -0.5), (0.44, 0.5))]
             + [((0.36, y), (0.44, y)) for y in (-0.21, -0.14, -0.07, 0.07, 0.14, 0.21)])

# Echte T-Kreuzung (30 cm) und daneben ein Zebrastreifen auf der linken Strasse (nicht an der Kreuzung)
T_MIT_ZEBRA = bild([((0.0, 0.0), (0.30, 0.0)), ((0.30, -0.5), (0.30, 0.5))]
                   + [((0.40, y), (0.46, y)) for y in (0.10, 0.15, 0.20, 0.25)])


def ende(erg):
    """Weitester gefundener Linienpunkt (x, y)."""
    return max(erg['boden'], key=lambda p: math.hypot(*p))


class Kreuzung(unittest.TestCase):
    def test_t_beide_seiten_zufaellig(self):
        seiten = set()
        for n in range(20):
            s = linie.LinienSucher()
            s.zufall.seed(n)
            erg = s.suche(T, 0.0)
            self.assertTrue(erg['gefunden'])
            self.assertEqual(len(erg['kreuzung']['aeste']), 2)
            seite = 1 if erg['kreuzung']['wahl'] > 0 else -1
            seiten.add(seite)
            # nur der gewaehlte Ast zaehlt: die Linie endet auf dessen Seite
            self.assertGreater(ende(erg)[1] * seite, 0.1)
        self.assertEqual(seiten, {1, -1})

    def test_abzweig_geradeaus_oder_links(self):
        richtungen = set()
        for n in range(20):
            s = linie.LinienSucher()
            s.zufall.seed(n)
            erg = s.suche(ABZWEIG, 0.0)
            wahl = erg['kreuzung']['wahl']
            richtungen.add('links' if wahl > 30 else 'geradeaus' if abs(wahl) <= 30 else 'rechts')
        self.assertEqual(richtungen, {'links', 'geradeaus'})

    def test_wahl_bleibt_bis_hinter_die_kreuzung(self):
        s = linie.LinienSucher()
        erste = s.suche(T, 0.0)['kreuzung']['wahl']
        for n in range(30):
            s.zufall.seed(n)                                    # neuer Zufall wuerde evtl. anders waehlen
            self.assertEqual(s.suche(T, 0.0)['kreuzung']['wahl'], erste)
        for _ in range(20):                                     # Kreuzung durchfahren, wieder gerade Linie
            self.assertNotIn('kreuzung', s.suche(GERADE, 0.0))
        self.assertIsNone(s.wahl)                               # naechste Kreuzung wird neu gewaehlt

    def test_wahl_folgt_der_drehung(self):
        """Hat er sich schon 90 Grad nach links gedreht (gier), ist der linke Ast nun 'geradeaus' im Bild."""
        s = linie.LinienSucher()
        s.zufall.seed(1)
        erg = s.suche(T, 0.0)
        while erg['kreuzung']['wahl'] < 0:                      # bis er links gewaehlt hat
            s.wahl = None
            erg = s.suche(T, 0.0)
        gedreht = bild([((0.0, 0.0), (0.9, 0.0)), ((0.32, 0.0), (0.32, -0.5))])   # Ast geradeaus + rechts
        erg = s.suche(gedreht, math.radians(90))
        self.assertLess(abs(erg['kreuzung']['wahl']), 30, erg['kreuzung'])

    def test_wahl_verfaellt_auch_ohne_verwertbare_linie(self):
        for fuellung in (0, 255):  # keine Komponente oder nur eine zu breite Flaeche
            with self.subTest(fuellung=fuellung):
                s = linie.LinienSucher()
                s.suche(T, 0.0)
                maske = np.full(s.vogel(T).shape, fuellung, np.uint8)
                maske[[0, -1], :] = 0
                maske[:, [0, -1]] = 0
                with patch.object(s, 'vogel', return_value=maske):
                    for _ in range(20):
                        self.assertFalse(s.suche(T, 0.0, kamera_ok=False)['gefunden'])
                    self.assertIsNotNone(s.wahl)  # weggedrehte Kamera zaehlt nie
                    for _ in range(15):
                        self.assertFalse(s.suche(T, 0.0)['gefunden'])
                    self.assertIsNotNone(s.wahl)
                    self.assertFalse(s.suche(T, 0.0)['gefunden'])
                    self.assertIsNone(s.wahl)
                self.assertTrue(s.suche(T, 0.0)['kreuzung_neu'])

    def test_wahl_bleibt_im_stand(self):
        """Review PR #101 (GB-06): steht er nach der Wahl (Ampel, Hindernis), verfaellt sie nicht - erst nach Fahrstrecke."""
        s = linie.LinienSucher()
        s.suche(T, 0.0, pos=(0.0, 0.0))
        self.assertIsNotNone(s.wahl)
        for _ in range(40):                                     # steht: Kreuzung nicht erkannt, aber keine Bewegung
            s.suche(GERADE, 0.0, pos=(0.0, 0.0))
        self.assertIsNotNone(s.wahl)
        for _ in range(20):                                     # 30 cm weiter: durchfahren
            s.suche(GERADE, 0.0, pos=(0.30, 0.0))
        self.assertIsNone(s.wahl)

    def test_kamera_weggedreht_aendert_nichts(self):
        """Arm dreht die Kamera weg (Zebrastreifen, Greifen): Wahl bleibt, auch nach vielen Bildern."""
        s = linie.LinienSucher()
        erste = s.suche(T, 0.0)['kreuzung']['wahl']
        for _ in range(50):
            erg = s.suche(GERADE, 0.0, kamera_ok=False)
            self.assertNotIn('kreuzung_neu', erg)
        self.assertIsNotNone(s.wahl)
        for n in range(10):
            s.zufall.seed(n)
            self.assertEqual(s.suche(T, 0.0)['kreuzung']['wahl'], erste)

    def test_keine_kreuzung(self):
        for name, img in (('gerade', GERADE), ('enger Bogen (U)', U), ('Haltelinie', HALTELINIE),
                          ('Zebrastreifen-Begrenzung', ZEBRA)):
            with self.subTest(name):
                erg = linie.LinienSucher().suche(img, 0.0)
                self.assertTrue(erg['gefunden'])
                self.assertNotIn('kreuzung', erg)

    def test_zebrastreifen_woanders_hebt_kreuzung_nicht_auf(self):
        s = linie.LinienSucher()
        erg = s.suche(T_MIT_ZEBRA, 0.0)
        self.assertIsNotNone(linie.finde_zebra(erg['vogel'], s.RASTER, s.VORNE[1]))   # Zebrastreifen ist im Bild
        self.assertIn('kreuzung', erg)
        self.assertEqual(len(erg['kreuzung']['aeste']), 2)

    def test_abschaltbar(self):
        erg = linie.LinienSucher({'abbiegen': False}).suche(T, 0.0)
        self.assertNotIn('kreuzung', erg)


if __name__ == '__main__':
    unittest.main(verbosity=2)
