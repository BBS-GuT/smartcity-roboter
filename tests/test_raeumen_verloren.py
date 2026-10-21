#!/usr/bin/env python3
"""RM02 21.10.: Wegraeumen brach fast immer mit "beim Heranfahren aus den Augen verloren" ab.

- Person in Sicht waehrend des Heranfahrens: die Wartezeit zaehlte als "nicht gesehen" -> sofort Abbruch.
- Verloren, blind greifen geht nicht (Winkel unbekannt): jetzt etwas zurueck und nochmal hinschauen, hoechstens zweimal.
- Zebrastreifen: nur Spielfiguren in der Naehe zaehlen, nicht Zuschauer irgendwo im Raum.

Echter Entscheider, kuenstliche Uhr, Planerstub. Kein ROS, kein Geraet.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
from raeum_lauf import Lauf  # noqa: E402
from entscheider import STANDARD  # noqa: E402
from tiefe import spielfigur  # noqa: E402

GREIF = STANDARD['greif_vor']
WUERFEL = {'seite': 0.0, 'breite': 0.03, 'hoehe': 0.05, 'quelle': 'tiefe'}


class Welt:
    """Wuerfel liegt fest; die Kamera sieht ihn nur weiter als 'sicht' (m) und solange keine Person davor steht."""

    def __init__(self, start=0.345, sicht=0.0):
        self.lauf = Lauf()
        self.x, self.sicht = start, sicht
        self.person = False
        self.aktionen, self.gruende = [], []

    def vor(self):
        return self.x - self.lauf.strecke

    def schritt(self, **kw):
        sieht = not self.person and self.vor() > self.sicht
        w = {'objekt': dict(WUERFEL, vor=self.vor()) if sieht else None, 'tiefe_hindernis': sieht,
             'objekte': [{'name': 'Person', 'im_weg': False, 'nah': True}] if self.person else []}
        w.update(kw)
        b = self.lauf.schritt(**w)
        self.aktionen.append(b['aktion'])
        self.gruende.append(b['grund'])
        return b

    def texte(self):
        return [t for _, t, _ in self.lauf.e.ereignisse]


class Verloren(unittest.TestCase):
    def test_person_waehrend_heranfahren_ist_kein_verlieren(self):
        w = Welt(start=0.345)
        for _ in range(200):
            w.schritt()
            if w.lauf.phase() == 'abstand':
                break
        self.assertEqual(w.lauf.phase(), 'abstand')
        w.person = True                       # Person kommt ins Bild und verdeckt den Wuerfel 5 s lang
        for _ in range(50):
            w.schritt()
        w.person = False
        for _ in range(40):
            w.schritt()
        self.assertFalse(any('aus den Augen verloren' in t for t in w.texte()), w.texte())
        self.assertIn(w.lauf.phase(), ('planen', 'naeher', 'ausfuehren', 'kontrolle', 'rueckweg', None))

    def test_verloren_ohne_winkel_faehrt_zurueck_und_schaut_nochmal(self):
        # Kamera verliert ihn kurz vor der Greifweite; ohne Linie (Winkel unbekannt) darf er nicht blind greifen
        w = Welt(start=GREIF + 0.07, sicht=GREIF + 0.025)
        w.lauf.e.c['tiefe_halt'] = GREIF + 0.10       # haelt schon weiter weg an (Test: Start ausserhalb Greifweite)
        for _ in range(600):
            w.schritt(weg=None)
        texte = w.texte()
        self.assertTrue(any('fahre etwas zurueck und schaue nochmal hin' in t for t in texte), texte)
        self.assertGreaterEqual(sum('Hindernis gesehen' in t for t in texte), 2, texte)   # nach dem Zurueckfahren
        self.assertNotIn('fahren', w.aktionen)                                            # nie drueber
        # hoechstens zweimal zurueck, dann wartet er wie bisher
        self.assertEqual(sum('fahre etwas zurueck und schaue nochmal hin' in t for t in texte), 2, texte)
        self.assertTrue(any('aus den Augen verloren -> warte' in t for t in texte), texte)

    def test_verloren_hinten_nicht_frei_wartet(self):
        w = Welt(start=GREIF + 0.07, sicht=GREIF + 0.025)
        w.lauf.e.c['tiefe_halt'] = GREIF + 0.10
        for _ in range(200):
            w.schritt(weg=None, lidar_hinten=0.1)
        texte = w.texte()
        self.assertFalse(any('fahre etwas zurueck und schaue' in t for t in texte), texte)
        self.assertTrue(any('aus den Augen verloren -> warte' in t for t in texte), texte)
        self.assertNotIn('fahren', w.aktionen)

    def test_kein_rueckwaerts_heranfahren_ohne_platz_hinten(self):
        w = Welt(start=GREIF - 0.03)          # zu nah: er muesste zum Greifen zurueck
        for _ in range(100):
            b = w.schritt(lidar_hinten=0.1)
            m = b.get('manoever') or {}
            self.assertGreaterEqual(m.get('lin', 0.0), 0.0, b['grund'])


ZEBRA_POSEN = {'fahrstellung': [90, 120, 10, 20, 90, 30], 'blick_links': [135, 120, 10, 20, 90, 30],
               'blick_rechts': [45, 120, 10, 20, 90, 30]}


def zebra(person):
    """Am Zebrastreifen umschauen; person = Objektliste, die die KI dabei die ganze Zeit sieht."""
    lauf = Lauf(posen=ZEBRA_POSEN)
    b = None
    for _ in range(150):
        b = lauf.schritt(zebra={'abstand': 0.3}, objekte=person)
    return b


class ZebraFiguren(unittest.TestCase):
    def test_spielfigur_nah_wartet(self):
        b = zebra([{'name': 'Person', 'im_weg': False, 'abstand': 0.6, 'spielfigur': True}])
        self.assertEqual(b['aktion'], 'stopp', b['grund'])

    def test_ohne_abstand_wartet(self):
        b = zebra([{'name': 'Person', 'im_weg': False}])
        self.assertEqual(b['aktion'], 'stopp', b['grund'])

    def test_zuschauer_im_raum_haelt_nicht_auf(self):
        b = zebra([{'name': 'Person', 'im_weg': False, 'abstand': 0.8, 'spielfigur': False}])
        self.assertEqual(b['aktion'], 'fahren', b['grund'])

    def test_weit_weg_haelt_nicht_auf(self):
        b = zebra([{'name': 'Person', 'im_weg': False, 'abstand': 3.0, 'spielfigur': True}])
        self.assertEqual(b['aktion'], 'fahren', b['grund'])


class Spielfigur(unittest.TestCase):
    BILD = (480, 640)
    FOV = 70.0

    def test_kleine_figur(self):
        self.assertTrue(spielfigur((300, 200, 30, 60), 0.6, self.BILD, self.FOV))       # ca. 8 cm gross

    def test_echter_mensch(self):
        self.assertFalse(spielfigur((300, 50, 120, 400), 2.0, self.BILD, self.FOV))     # ca. 1,7 m

    def test_beine_am_oberen_rand(self):
        self.assertFalse(spielfigur((400, 0, 150, 470), 0.5, self.BILD, self.FOV))

    def test_ohne_abstand_unbekannt(self):
        self.assertIsNone(spielfigur((300, 200, 30, 60), None, self.BILD, self.FOV))


if __name__ == '__main__':
    unittest.main(verbosity=2)
