#!/usr/bin/env python3
"""Wegraeumen: kein veralteter Zustand aus frueheren Versuchen oder Phasen.

- Nur der LiDAR meldete etwas ('unbestaetigt', langsam weiter); sieht danach die Tiefenkamera etwas, wird neu
  angeschaut statt dauerhaft langsam darauf zuzufahren.
- Zweiter Versuch nach einer Pruefblick-Kontrolle: entscheidet nicht mit geleerten Zaehlern 'frei'.
- Zweiter Versuch in Fahrstellung nach einem ersten im Pruefblick: Kontrolle wertet die Kamera wieder aus.
- Anschauen zaehlt keine Bilder, solange der Arm noch in die Fahrstellung zurueckfaehrt.
Echter Entscheider, natuerliche Phasen, reiner Planerstub; kein ROS, kein Geraet.
"""
import unittest

from raeum_lauf import POSEN, PRUEF_POSEN, Lauf
from entscheider import STANDARD  # noqa: E402

GREIF = STANDARD['greif_vor']   # Gegenstand liegt in Greifweite

PRUEF = {'quelle': 'tiefe', 'blick': 'pruef', 'vor': 0.17, 'seite': 0.0, 'breite': 0.04, 'hoehe': 0.04}
VORNE = {'quelle': 'tiefe', 'vor': GREIF, 'seite': 0.0, 'breite': 0.04, 'hoehe': 0.04}


def texte(lauf):
    return [t for _, t, _ in lauf.e.ereignisse]


class RaeumenZustand(unittest.TestCase):
    def test_tiefenkamera_nach_lidar_meldung(self):
        lauf = Lauf()
        b = None
        for _ in range(120):
            b = lauf.schritt(lidar=0.40)
        self.assertEqual(b['aktion'], 'langsam')
        obj = dict(VORNE, vor=0.25)
        neu_angeschaut = False
        for _ in range(100):
            b = lauf.schritt(lidar=0.40, objekt=obj, tiefe_hindernis=True)
            neu_angeschaut = neu_angeschaut or lauf.phase() == 'anschauen'
            self.assertNotEqual(b['aktion'], 'langsam', b['grund'])
        self.assertTrue(neu_angeschaut)

    def test_versuch2_nach_pruefblick_nicht_frei_mit_alten_zaehlern(self):
        lauf = Lauf(PRUEF_POSEN)
        ablaeufe, frei = set(), []
        for _ in range(600):
            a = lauf.e.ablauf
            v = a.versuch if a else None
            obj = PRUEF if lauf.phase() in ('pruefblick', 'kontrolle') and v == 1 else None
            b = lauf.schritt(lidar=0.18, objekt=obj)      # LiDAR meldet die ganze Zeit 18 cm
            if lauf.e.ablauf is not None:
                ablaeufe.add(id(lauf.e.ablauf))
            frei.append(b['aktion'] == 'fahren')
        self.assertFalse(any(frei))
        self.assertFalse(any('sehen nichts mehr' in t for t in texte(lauf)), texte(lauf))
        self.assertEqual(len(ablaeufe), 1)                 # kein endloses Neustarten bei Versuch 1

    def test_kontrolle_in_fahrstellung_nach_pruefblick_versuch(self):
        lauf = Lauf(PRUEF_POSEN)
        erst = True
        for i in range(500):
            a = lauf.e.ablauf
            ph, v = lauf.phase(), (a.versuch if a else None)
            lid, obj = float('inf'), None
            if ph is None and i < 5:
                lid = 0.18
            elif v == 1 and ph == 'anschauen':
                if erst:
                    obj, erst = VORNE, False      # einmal kurz gesehen, dann zu nah fuer die Kamera
                lid = 0.18
            elif v == 1 and ph in ('pruefblick', 'kontrolle'):
                obj = PRUEF
            elif v and v >= 2 and ph != 'pruefblick':
                obj = VORNE                       # liegt (in Fahrstellung sichtbar) immer noch da
            lauf.schritt(lidar=lid, objekt=obj)
            if v == 2 and lauf.e.ablauf is not None and lauf.e.ablauf.versuch == 3:
                break
        self.assertIsNotNone(lauf.e.ablauf)
        self.assertEqual(lauf.e.ablauf.versuch, 3)         # Kontrolle 2 hat das Hindernis gesehen
        self.assertFalse(any('Weg ist frei (geprueft)' in t for t in texte(lauf)))

    def test_anschauen_wartet_auf_armrueckkehr(self):
        lauf = Lauf(POSEN)
        a = lauf.e.ablauf
        for _ in range(3):
            lauf.schritt()
        lauf.e.arm_zurueck_noetig = True                   # vorheriger Ablauf liess den Arm verstellt
        gezaehlt_ohne_sicht = 0
        for _ in range(60):
            lauf.schritt(lidar=0.40)
            a = lauf.e.ablauf
            if a is not None and a.phase == 'anschauen' and not lauf.e.arm_in_fahrstellung:
                gezaehlt_ohne_sicht = max(gezaehlt_ohne_sicht, a.bilder)
            if a is None and lauf.t > 101:
                break
        self.assertEqual(gezaehlt_ohne_sicht, 0)

    def test_abbruch_ohne_armbewegung_sperrt_nicht(self):
        """Statusausfall beim Anschauen (Arm nie bewegt), danach Auto am Rand: faehrt weiter wie vorher."""
        lauf = Lauf(POSEN)
        for _ in range(3):
            lauf.schritt()
        for _ in range(3):
            lauf.schritt(lidar=0.40)
        self.assertEqual(lauf.phase(), 'anschauen')
        lauf.e.fahrt_aktiv = False
        lauf.schritt(lidar=0.40)
        lauf.e.fahrt_aktiv = True
        aktionen = [lauf.schritt(akteur='Auto', im_weg=False)['aktion'] for _ in range(100)]
        self.assertIn('fahren', aktionen)

    def test_person_am_rand_haelt_kontrolle_nicht_auf(self):
        """Weggeraeumt, Person neben der Strasse: Kontrolle endet wie bisher, kein 30-s-Warten."""
        lauf = Lauf(POSEN)
        weg, t_kontrolle, b = False, None, None
        for _ in range(400):
            if lauf.phase() == 'kontrolle' and t_kontrolle is None:
                t_kontrolle = lauf.t
            akteur = 'Person' if t_kontrolle is not None else None
            b = lauf.schritt(akteur=akteur, im_weg=False, **({} if weg else {'lidar': GREIF, 'objekt': dict(VORNE)}))
            a = b['arm']
            weg = weg or (isinstance(a, dict) and (a.get('winkel') or [0] * 6)[5] == 130)
            if b['aktion'] == 'fahren':
                break
        self.assertEqual(b['aktion'], 'fahren')
        self.assertLess(lauf.t - t_kontrolle, 6.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
