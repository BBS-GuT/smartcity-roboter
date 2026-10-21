#!/usr/bin/env python3
"""#76: Personen-/Tier-/Fahrzeughalt in der Vorpruefung (Ablagesuche vor dem Heranfahren).

Echter Entscheider, natuerliche Phasen, reiner Planerstub; kein ROS, kein Geraet.
"""
import unittest

from raeum_lauf import AKTEURE, Lauf, bewegt

FERN = {'vor': 0.34, 'seite': 0.03, 'breite': 0.04, 'hoehe': 0.045, 'quelle': 'tiefe'}


def bis_vorpruefen():
    lauf = Lauf()
    for _ in range(200):
        lauf.schritt(objekt=dict(FERN), lidar=0.34)
        if lauf.phase() == 'vorpruefen':
            return lauf
    raise AssertionError('vorpruefen nicht regulaer erreicht')


class VorpruefenPersonen(unittest.TestCase):
    def test_freier_gegenfall(self):
        lauf = bis_vorpruefen()
        b = lauf.schritt(objekt=dict(FERN), lidar=0.34)
        self.assertEqual(lauf.phase(), 'abstand')
        b = lauf.schritt(objekt=dict(FERN), lidar=0.34)
        self.assertEqual(b['aktion'], 'manoever')

    def test_halt_wartefenster_und_verlaengerung(self):
        for akteur in AKTEURE:
            for im_weg in (True, False):
                with self.subTest(akteur=akteur, im_weg=im_weg):
                    lauf = bis_vorpruefen()
                    b = lauf.schritt(akteur=akteur, im_weg=im_weg, objekt=dict(FERN), lidar=0.34)
                    self.assertFalse(bewegt(b), b)
                    gesehen = lauf.t
                    # direkt folgende freie Bilder: noch keine Bewegung
                    for _ in range(10):
                        self.assertFalse(bewegt(lauf.schritt(objekt=dict(FERN), lidar=0.34)))
                    # erneute frische Sichtung verlaengert die Frist
                    self.assertFalse(bewegt(lauf.schritt(akteur=akteur, im_weg=im_weg, objekt=dict(FERN), lidar=0.34)))
                    gesehen = lauf.t
                    while lauf.t + 0.1 < gesehen + 2.0 - 1e-6:
                        # Zyklus ohne neues KI-Bild (alter Bildinhalt mit Akteur) zaehlt nicht als neue Sichtung
                        alt = round(lauf.t - gesehen, 1) == 1.0
                        b = lauf.schritt(akteur=akteur if alt else None, neu=not alt, objekt=dict(FERN), lidar=0.34)
                        self.assertFalse(bewegt(b), f'{lauf.t - gesehen:.1f} s danach: {b}')
                    # danach (Frist ab der letzten FRISCHEN Sichtung): regulaer weiter, kein Vorpruefungs-Timeout
                    b = None
                    for _ in range(3):
                        b = lauf.schritt(objekt=dict(FERN), lidar=0.34)
                        if b['aktion'] == 'manoever':
                            break
                    self.assertEqual(b['aktion'], 'manoever', b)
                    texte = [t for _, t, _ in lauf.e.ereignisse]
                    self.assertFalse(any('dauert zu lange' in t for t in texte))

    def test_langer_halt_ohne_timeout_der_phase(self):
        lauf = bis_vorpruefen()
        for _ in range(80):                      # 8 s Person: laenger als die 6-s-Frist der Vorpruefung
            self.assertFalse(bewegt(lauf.schritt(akteur='Person', objekt=dict(FERN), lidar=0.34)))
        self.assertIsNotNone(lauf.e.ablauf)
        texte = [t for _, t, _ in lauf.e.ereignisse]
        self.assertFalse(any('dauert zu lange' in t for t in texte), texte)


if __name__ == '__main__':
    unittest.main(verbosity=2)
