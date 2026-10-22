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


def bild(linien, cfg=None):
    """Kamerabild (BGR) mit schwarzen Linien [((x, y), (x, y)), ...] in Metern (x vorne, y links)."""
    s = linie.LinienSucher(cfg)
    s._vogel(B, H)
    bw, bh = s.vogel_groesse
    boden = np.full((bh, bw), 255, np.uint8)
    for a, b in linien:
        cv2.line(boden, tuple(int(v) for v in s._zu_raster(*a)), tuple(int(v) for v in s._zu_raster(*b)), 0,
                 int(0.025 / s.RASTER))
    img = cv2.warpPerspective(boden, np.linalg.inv(s.H), (B, H), borderValue=255)
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


def bild_bei_pose(linien, pose):
    """Dieselbe synthetische Welt aus einer neuen Pose aufnehmen (keine Fahrphysik/Messung)."""
    x, y, gier = pose

    def lokal(p):
        dx, dy = p[0] - x, p[1] - y
        return math.cos(gier) * dx + math.sin(gier) * dy, -math.sin(gier) * dx + math.cos(gier) * dy

    return bild([(lokal(a), lokal(b)) for a, b in linien])


# Die Kamera sieht den Boden ca. 25-47 cm vor der Robotermitte
T = bild([((0.0, 0.0), (0.36, 0.0)), ((0.36, -0.5), (0.36, 0.5))])
ABZWEIG = bild([((0.0, 0.0), (0.9, 0.0)), ((0.33, 0.0), (0.6, 0.4))])
GERADE = bild([((0.0, 0.0), (0.9, 0.05))])
U = bild([((0.0, 0.0), (0.30, 0.0)), ((0.30, 0.12), (0.0, 0.12))]
         + [((0.30 + 0.06 * math.sin(math.pi * k / 40), 0.06 - 0.06 * math.cos(math.pi * k / 40)),
             (0.30 + 0.06 * math.sin(math.pi * (k + 1) / 40), 0.06 - 0.06 * math.cos(math.pi * (k + 1) / 40)))
            for k in range(40)])

# Haltelinie: Querbalken (je 18 cm zur Seite, laenger als ast_min), endet im Bild -> keine Abzweigung.
# Grenze: ein Balken, der bis an den seitlichen Bildrand reicht (ab ca. 20 cm), sieht wie eine Ausfahrt aus.
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
    def test_unbestaetigtes_einlenken_loescht_wahl_nicht(self):
        for gier in (0.0, None, float('nan'), math.pi):
            with self.subTest(gier=gier):
                s = linie.LinienSucher()
                with patch.object(s.zufall, 'choice', side_effect=lambda a: max(a, key=lambda p: p[0])):
                    s.suche(T, 0.0, pos=(0.0, 0.0))
                # Auch Strecke und viele Bilder beweisen ohne passende Richtung keine Ausfahrt.
                for _ in range(25):
                    erg = s.suche(GERADE, gier, pos=(0.30, 0.0))
                    self.assertFalse(erg['gefunden'])
                    self.assertEqual(erg['boden'], [])
                self.assertAlmostEqual(s.wahl, math.pi / 2, delta=0.2)

    def test_gegenrichtung_der_wahl_wird_nicht_uebernommen(self):
        """Nativer Review P1: links gewaehlt, rechts eingelenkt (und Spiegelung)."""
        for seite in (-1, 1):
            s = linie.LinienSucher()
            with patch.object(s.zufall, 'choice', side_effect=lambda a: max(a, key=lambda p: seite * p[0])):
                s.suche(T, 0.0)
            for _ in range(25):
                erg = s.suche(GERADE, -seite * math.pi / 2, pos=(0.36, -seite * 0.30))
                self.assertFalse(erg['gefunden'])
                self.assertEqual(erg['boden'], [])
            self.assertAlmostEqual(s.wahl, seite * math.pi / 2, delta=0.2)
            # Richtige Drehung: normale Linie wieder aufnehmen.
            self.assertTrue(s.suche(GERADE, seite * math.pi / 2)['gefunden'])

    def test_ungerichtete_querlinie_bestaetigt_keinen_ast(self):
        for seite in (-1, 1):
            s = linie.LinienSucher()
            with patch.object(s.zufall, 'choice', side_effect=lambda a: max(a, key=lambda p: seite * p[0])):
                s.suche(T, 0.0)
            img = bild([((0.36, -0.5), (0.36, 0.5))])
            # Pruefe den Pfad OHNE erkannte Verzweigung: die Querachse allein reicht nicht.
            with patch.object(s, 'aeste', return_value=None):
                erg = s.suche(img, 0.0)
            self.assertFalse(erg['gefunden'])
            self.assertIsNotNone(s.wahl)

    def test_ast_im_nahen_blindbereich_gerade_ueberschreibt_nicht(self):
        """Echte Bildfolge bei Annaeherung: der Seitenast verschwindet unter dem Bildrand."""
        for seite in (-1, 1):
            with self.subTest(seite=seite):
                s = linie.LinienSucher()
                g = linie.Gedaechtnis()
                with patch.object(s.zufall, 'choice', side_effect=lambda a: max(a, key=lambda p: seite * p[0])):
                    for p in (0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.14, 0.16):
                        img = bild([((-p, 0.0), (0.9 - p, 0.0)),
                                    ((0.36 - p, 0.0), (0.36 - p, seite * 0.5))])
                        g.pose = [p, 0.0, 0.0]
                        erg = s.suche(img, 0.0, pos=(p, 0.0))
                        g.hinzufuegen(erg['boden'])
                        self.assertIsNotNone(s.wahl)
                        # Keine neue Gerade hinter der gewaehlten Abzweigung ins Gedaechtnis.
                        self.assertLess(max(g.punkte[:, 0]), 0.42, (p, erg.get('kreuzung')))
                        self.assertGreater(max(g.punkte[:, 1] * seite), 0.10)
                wahl = s.wahl
                # Halt und weggedrehte Kamera loeschen weder Wahl noch gespeicherten Ast.
                for _ in range(40):
                    erg = s.suche(np.full_like(GERADE, 255), 0.0, kamera_ok=False, pos=(0.16, 0.0))
                    g.bewegen(0.0, 0.0, 0.1)
                    g.hinzufuegen(erg['boden'])
                self.assertEqual(s.wahl, wahl)
                self.assertGreater(max(g.punkte[:, 1] * seite), 0.10)
                welt = [((0.0, 0.0), (0.9, 0.0)), ((0.36, 0.0), (0.36, seite * 0.6))]
                # Dieselbe Welt mit fortschreitender Position UND Drehung aufnehmen.
                for p in ((0.22, 0.0, 0.0), (0.30, seite * 0.02, seite * math.pi / 6),
                          (0.36, seite * 0.04, seite * math.pi / 3),
                          (0.36, seite * 0.12, seite * math.pi / 2)):
                    g.pose = list(p)
                    erg = s.suche(bild_bei_pose(welt, p), p[2], pos=p[:2])
                    g.hinzufuegen(erg['boden'])
                    self.assertEqual(s.wahl, wahl)
                    self.assertLess(max(g.punkte[:, 0]), 0.42)
                self.assertTrue(erg['gefunden'])  # gewaehlte Strasse nach dem Einlenken wieder sichtbar
                for _ in range(20):
                    p = (0.36, seite * 0.30, seite * math.pi / 2)
                    s.suche(bild_bei_pose(welt, p), p[2], pos=p[:2])
                self.assertIsNone(s.wahl)

    def test_plus_und_seitliches_t_mit_spiegelung(self):
        """Geometrische Ausgaenge relativ zur Zufahrt; dies erteilt keine Verkehrserlaubnis."""
        for cfg, x in ((None, 0.36), ({'kamera_hoehe': 0.31, 'kamera_neigung': 28.0}, 0.46)):
            for seiten in ((-1, 1), (-1,), (1,)):
                with self.subTest(cfg=cfg, seiten=seiten):
                    img = bild([((0.0, 0.0), (1.2, 0.0))]
                               + [((x, 0.0), (x, seite * 0.6)) for seite in seiten], cfg)
                    s = linie.LinienSucher(cfg)
                    s._vogel(B, H)
                    teilung = s.aeste(s.vogel(img) > 0, s._zu_raster(0.0, 0.0))
                    self.assertIsNotNone(teilung)
                    _, aeste, _ = teilung
                    richtungen = [math.degrees(r) for r, _ in aeste]
                    self.assertEqual(len(aeste), 1 + len(seiten), richtungen)
                    self.assertEqual(sum(abs(r) < 30 for r in richtungen), 1, richtungen)
                    for seite in seiten:
                        self.assertEqual(sum(60 < r * seite < 110 for r in richtungen), 1, richtungen)
                    # Jeden Ausgang erzwingen und pruefen, dass die jeweils andere Seite
                    # nicht ins Liniengedaechtnis gelangen wuerde (keine Zufallsabdeckung).
                    for index in range(len(aeste)):
                        s = linie.LinienSucher(cfg)
                        with patch.object(s.zufall, 'choice', side_effect=lambda kandidaten, i=index: kandidaten[i]):
                            erg = s.suche(img, 0.0)
                        self.assertTrue(erg['gefunden'])
                        wahl = erg['kreuzung']['wahl']
                        self.assertEqual(len(erg['kreuzung']['aeste']), 1 + len(seiten))
                        if abs(wahl) < 30:
                            self.assertLess(max(abs(y) for _, y in erg['boden']), 0.06)
                        else:
                            seite = 1 if wahl > 0 else -1
                            self.assertGreater(max(y * seite for _, y in erg['boden']), 0.10)
                            self.assertGreater(min(y * seite for _, y in erg['boden']), -0.06)

    def test_querbalken_am_bildrand_ist_bildgleich_mit_plus(self):
        """Informationsgrenze #112: gleiche Pixel koennen keine unterschiedliche Bedeutung liefern."""
        plus = bild([((0.0, 0.0), (0.9, 0.0)), ((0.36, -0.5), (0.36, 0.5))])
        querbalken = bild([((0.0, 0.0), (0.9, 0.0)), ((0.36, -0.4), (0.36, 0.4))])
        self.assertTrue(np.array_equal(plus, querbalken))
        for img in (plus, querbalken):
            erg = linie.LinienSucher().suche(img, 0.0)
            self.assertEqual(len(erg['kreuzung']['aeste']), 3)

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
            self.assertNotIn('kreuzung', s.suche(GERADE, math.radians(erste)))
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
                eingelenkt = s.wahl
                maske = np.full(s.vogel(T).shape, fuellung, np.uint8)
                maske[[0, -1], :] = 0
                maske[:, [0, -1]] = 0
                with patch.object(s, 'vogel', return_value=maske):
                    for _ in range(20):
                        self.assertFalse(s.suche(T, 0.0, kamera_ok=False)['gefunden'])
                    self.assertIsNotNone(s.wahl)  # weggedrehte Kamera zaehlt nie
                    for _ in range(15):
                        self.assertFalse(s.suche(T, eingelenkt)['gefunden'])
                    self.assertIsNotNone(s.wahl)
                    self.assertFalse(s.suche(T, eingelenkt)['gefunden'])
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
        for _ in range(20):                                     # 30 cm weiter und eingelenkt: durchfahren
            s.suche(GERADE, s.wahl or 0.0, pos=(0.30, 0.0))
        self.assertIsNone(s.wahl)

    def test_gewaehlter_ast_nicht_sichtbar_kein_anderer(self):
        """Review PR #101: links gewaehlt, im naechsten Bild nur geradeaus + rechts zu sehen -> keinen davon nehmen."""
        s = linie.LinienSucher()
        s.zufall.seed(1)
        erg = s.suche(T, 0.0)
        while erg['kreuzung']['wahl'] < 0:
            s.wahl = None
            erg = s.suche(T, 0.0)
        ohne_links = bild([((0.0, 0.0), (0.9, 0.0)), ((0.32, 0.0), (0.32, -0.5))])
        erg = s.suche(ohne_links, 0.0)
        self.assertIsNone(erg['kreuzung']['wahl'])
        self.assertGreater(min(y for _, y in erg['boden']), -0.06)      # nichts vom rechten Ast
        self.assertLess(max(x for x, _ in erg['boden']), 0.37)          # nichts vom Ast geradeaus
        self.assertIsNotNone(s.wahl)                                    # Wahl bleibt

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

    def test_abzweig_kurzer_blick(self):
        """RM02 22.10.: nie abgebogen. Die Kamera sieht nur ca. 20 cm Boden; Abzweige wurden nicht erkannt (Aeste zu
        kurz, Suche begann hinter dem Abzweigpunkt, Linie endete knapp vor dem fernen Bildrand)."""
        for name, cfg, abstaende in (('Standard', None, (0.30, 0.40)),       # sichtbar ca. 25-47 cm
                                     ('Kamera 31 cm hoch, 28 Grad', {'kamera_hoehe': 0.31, 'kamera_neigung': 28.0},
                                      (0.40, 0.50))):                       # sichtbar ab ca. 34 cm
            for x in abstaende:
                with self.subTest(name, abzweig_bei=x):
                    img = bild([((0.0, 0.0), (1.2, 0.0)), ((x, 0.0), (x, -0.6))], cfg)
                    erg = linie.LinienSucher(cfg).suche(img, 0.0)
                    self.assertIn('kreuzung', erg)
                    self.assertEqual(len(erg['kreuzung']['aeste']), 2, erg['kreuzung'])

    def test_abschaltbar(self):
        s = linie.LinienSucher({'abbiegen': False})
        erg = s.suche(T, 0.0)
        self.assertNotIn('kreuzung', erg)
        s.wahl = math.pi / 2  # auch nach Abschalten einer schon bestehenden Wahl
        self.assertTrue(s.suche(GERADE, 0.0)['gefunden'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
