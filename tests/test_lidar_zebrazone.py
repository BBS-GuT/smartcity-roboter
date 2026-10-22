#!/usr/bin/env python3
"""L8 (#156): Nicht gemessene Teile der Zebrastreifenzone sind unbekannt, nicht frei.

Die Zentrale gibt die Richtungen ohne gueltige Messung als w['lidar_luecken'] weiter; der Ablauf Zebrastreifen prueft
sie gegen seine Ueberwegzone (seitlich bis zebra_seite, in der Tiefe bis abstand + zebra_tiefe).
Nur ROS-Attrappen, kein Geraet. Aufruf: python3 tests/test_lidar_zebrazone.py
"""
import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lidar_qualitaet as q  # noqa: E402  (Attrappen und Helfer fuer Scans/Knoten)
from entscheider import Entscheider, STANDARD  # noqa: E402
from ablaeufe import Zebrastreifen  # noqa: E402

lidar = q.lidar
N = 360                     # Strahl k zeigt nach k - 180 Grad (vorne = 180, links = 270)
GEMESSEN = np.zeros(0)
WAND = np.array([[1.5, y] for y in np.linspace(-0.5, 0.5, 11)])   # Wand weit hinter dem Ueberweg


def scan_mit_luecke(grad, breite=3):
    """Ueberall 3 m, nur um 'grad' (0 = vorne, 45 = vorne links) 'breite' Strahlen ohne Messwert (0)."""
    r = [3.0] * N
    for k in range(breite):
        r[(180 + grad - breite // 2 + k) % N] = 0.0
    return q.scan(r)


class Lauf:
    """Entscheider mit Zebrastreifen in 'abstand' m; jeder Schritt = neues, frisches Kamerabild."""

    def __init__(self, abstand=0.3):
        self.e, self.t, self.nr, self.abstand = Entscheider(), 1000.0, 0, abstand

    def schritt(self, n=1, **w):
        b = None
        for _ in range(n):
            self.t += 0.1
            self.nr += 1
            daten = {'bild_nr': self.nr, 'bild_zeit': self.t, 'aufnahme': self.t, 'objekte': [], 'ampel': None,
                     'stoppschild': False,
                     'lidar': float('inf'), 'lidar_breit': 1.0, 'lidar_hinten': 1.0,
                     'lidar_xy': WAND, 'lidar_luecken': GEMESSEN, 'zebra': {'abstand': self.abstand}}
            daten.update(w)
            b = self.e.update(self.t, daten)
        return b


def zebra(n=60, abstand=0.3, **w):
    lauf = Lauf(abstand)
    lauf.schritt(1)                                   # Zebrastreifen erkannt -> Ablauf startet
    return [lauf.schritt(1, **w) for _ in range(n)]


class Zebrazone(unittest.TestCase):
    def test_gemessen_und_frei_gibt_frei(self):
        folge = zebra()
        self.assertEqual(folge[-1]['aktion'], 'fahren')

    def test_seitliches_band_ungemessen_haelt(self):
        # Richtung 45 Grad: geht am geraden Fahrschlauch (halbe Breite 0,15 m) vorbei, aber durch die Zone
        # (bis 0,28 m seitlich) -> der Fahrschlauch ist gemessen, die Zone nicht
        winkel = lidar.ungueltige_winkel(scan_mit_luecke(45))
        self.assertIsNone(lidar.fahrschlauch_luecke(winkel))
        for name, w in (('leer', {}), ('freie Kamera, leere Objekte', {'objekte': []})):
            with self.subTest(name):
                folge = zebra(200, lidar_luecken=winkel, **w)          # Zeitablauf uebersteuert nicht
                self.assertTrue(all(b['aktion'] == 'stopp' for b in folge))
                self.assertIn('Ueberweg links nicht gemessen', folge[-1]['grund'])
        folge = zebra(200, lidar_luecken=lidar.ungueltige_winkel(scan_mit_luecke(-45)))
        self.assertIn('Ueberweg rechts nicht gemessen', folge[-1]['grund'])

    def test_einzelner_fehlender_strahl_hochaufloesend(self):
        # Codex-Befund zu PR #159: ein einzelner ungueltiger Strahl um 47 Grad aus einem hochaufloesenden Scan
        # (0,25 Grad) schneidet die Zone bei x = 0,20-0,26 m; ein Raster mit Winkelluecken uebersah ihn
        n = 1440
        # 54 Grad (Codex-Befund zu PR #161): schneidet die vordere linke Ecke nur ueber ca. 6 mm
        for grad in (46.5, 47.0, 47.25, 48.0, 52.0, 54.0, 54.25, -47.0, -54.0):
            with self.subTest(grad=grad):
                r = [3.0] * n
                r[int(round((grad + 180) / 360 * n))] = 0.0
                winkel = lidar.ungueltige_winkel(q.scan(r, n=n))
                self.assertIsNone(lidar.fahrschlauch_luecke(winkel))       # Fahrschlauch gemessen
                folge = zebra(80, lidar_luecken=winkel)
                self.assertTrue(all(b['aktion'] == 'stopp' for b in folge), grad)
                self.assertIn('nicht gemessen', folge[-1]['grund'])
        # deutlich ausserhalb der Zone (Ecke bei ca. 54,5 Grad, Pruefrand 1 cm): frei
        r = [3.0] * n
        r[int(round((60 + 180) / 360 * n))] = 0.0
        self.assertEqual(zebra(80, lidar_luecken=lidar.ungueltige_winkel(q.scan(r, n=n)))[-1]['aktion'], 'fahren')

    def test_luecke_hinter_dem_fahrschlauchende_haelt(self):
        # Zebrastreifen in 0,7 m: Zone bis 0,95 m, hinter dem Fahrschlauchende (0,8 m). Richtung geradeaus
        # ohne Messwert. (Im Gesamtsystem meldet die Zentrale das schon ueber den Fahrschlauch, #79; der Ablauf
        # verlaesst sich darauf nicht.)
        # Der Entscheider startet den Ablauf erst unter zebra_halt; hier der Ablauf direkt (gleiche Wahrnehmung).
        for luecken, frei in ((np.array([0.0]), False), (GEMESSEN, True)):
            with self.subTest(frei=frei):
                z, t = Zebrastreifen(0.0, STANDARD, abstand=0.7), 0.0
                folge = []
                for nr in range(1, 61):
                    t += 0.1
                    folge.append(z.schritt(t, {'bild_nr': nr, 'bild_zeit': t, 'aufnahme': t, 'objekte': [], 'lidar_breit': 1.0,
                                               'lidar_xy': WAND, 'lidar_luecken': luecken}))
                if frei:
                    self.assertIsNone(folge[-1])                       # Ablauf fertig: Ueberweg frei
                else:
                    self.assertTrue(all(b is not None and b['aktion'] == 'stopp' for b in folge))
                    self.assertIn('nicht gemessen', folge[-1]['grund'])

    def test_luecken_ausserhalb_der_zone(self):
        # links neben dem Roboter, nach hinten, schraeg hinten: kein zusaetzlicher Halt
        winkel = np.concatenate([lidar.ungueltige_winkel(scan_mit_luecke(g)) for g in (90, -90, 180, 135)])
        self.assertEqual(zebra(lidar_luecken=winkel)[-1]['aktion'], 'fahren')

    def test_fussgaenger_in_der_zone_wartet_mit_seite(self):
        folge = zebra(lidar_xy=np.vstack([WAND, [[0.36, -0.20], [0.37, -0.21]]]))
        self.assertTrue(all(b['aktion'] == 'stopp' for b in folge))
        self.assertTrue(any('rechts (LiDAR)' in b['grund'] for b in folge))

    def test_ohne_luecken_angabe_nicht_frei(self):
        # Vertrag: ohne lidar_xy UND lidar_luecken ist die Zone nicht nachweisbar gemessen
        for name, w in (('nur lidar_breit', {'lidar_xy': None, 'lidar_luecken': None}),
                        ('Punkte ohne Luecken-Angabe', {'lidar_luecken': None})):
            with self.subTest(name):
                folge = zebra(200, **w)
                self.assertTrue(all(b['aktion'] == 'stopp' for b in folge))

    def test_wiederkehr_der_messung_gibt_frei(self):
        lauf = Lauf()
        lauf.schritt(1)
        winkel = lidar.ungueltige_winkel(scan_mit_luecke(45))
        self.assertEqual(lauf.schritt(60, lidar_luecken=winkel)['aktion'], 'stopp')
        # (nach dem Warten neue, gemessene Beobachtung) -> frei
        self.assertEqual(lauf.schritt(60)['aktion'], 'fahren')


class Zentrale(unittest.TestCase):
    def mitschnitt(self, z):
        gesehen = []
        echt = z.entscheider.update

        def update(jetzt, w):
            gesehen.append(dict(w))
            return echt(jetzt, w)
        z.entscheider.update = update
        z._entscheiden()
        return gesehen[-1]

    def test_luecken_kommen_im_wahrnehmungsvertrag_an(self):
        z = q.ki_zentrale(scan_mit_luecke(45))
        w = self.mitschnitt(z)
        self.assertEqual(w['lidar'], float('inf'))                      # Fahrschlauch gemessen und frei
        self.assertTrue(np.any(np.abs(np.asarray(w['lidar_luecken']) - math.radians(45)) < math.radians(2)))

    def test_ohne_lidar_keine_luecken(self):
        z = q.ki_zentrale(q.scan(0.0))                                  # ganz ungueltig -> lidar None
        w = self.mitschnitt(z)
        self.assertIsNone(w['lidar'])
        self.assertIsNone(w['lidar_luecken'])


if __name__ == '__main__':
    unittest.main()
