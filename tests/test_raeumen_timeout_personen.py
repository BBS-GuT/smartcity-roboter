#!/usr/bin/env python3
"""#74: Personen-/Tier-/Fahrzeughalt auch bei der Armrueckkehr nach dem 30-s-Raeumabbruch.

Echter Entscheider bis 'ausfuehren', natuerliche Phasen, reiner Planerstub; kein ROS, kein Geraet.
"""
import unittest

from raeum_lauf import AKTEURE, Lauf, bewegt, planer as raeum_planer

FAHR = [90, 120, 10, 20, 90, 30]
OBJ = {'vor': 0.28, 'seite': 0.02, 'quer': 0.02, 'breite': 0.045, 'hoehe': 0.045, 'quelle': 'tiefe'}


def planer(objekt, seite):
    return {'schritte': [('Testschritt', [90, 100, 60, 60, 90, 80], 1.5)]}


def bis_erster_arm():
    lauf = Lauf({'fahrstellung': FAHR}, planer)
    for _ in range(200):
        b = lauf.schritt(lidar=0.28, objekt=dict(OBJ), tiefe_hindernis=True)
        if b['arm'] is not None:
            assert lauf.phase() == 'ausfuehren', lauf.phase()
            return lauf
    raise AssertionError('ausfuehren nicht regulaer erreicht')


class TimeoutPersonen(unittest.TestCase):
    def test_kein_neuer_armwunsch_bei_dauerhafter_sichtung(self):
        for akteur in AKTEURE:
            for im_weg in (True, False):
                with self.subTest(akteur=akteur, im_weg=im_weg):
                    lauf = bis_erster_arm()
                    neue = []
                    for _ in range(330):
                        b = lauf.schritt(akteur=akteur, im_weg=im_weg, lidar=0.28, objekt=dict(OBJ),
                                         tiefe_hindernis=True)
                        if bewegt(b):
                            neue.append((round(lauf.t - 100, 1), b))
                    self.assertIsNone(lauf.e.ablauf)          # 30-s-Grenze bleibt: Ablauf endet als Fehler
                    texte = [t for _, t, _ in lauf.e.ereignisse]
                    self.assertTrue(any('bleibt in Sicht' in t for t in texte))
                    self.assertEqual(neue, [])

    def test_ausbleibende_bilder_sind_keine_freipruefung(self):
        """Nach dem Abbruch kommen keine neuen KI-Bilder (Nummer UND Aufnahmezeit eingefroren): kein Armwunsch."""
        for akteur in AKTEURE:
            for im_weg in (True, False):
                with self.subTest(akteur=akteur, im_weg=im_weg):
                    lauf = bis_erster_arm()
                    for _ in range(330):
                        lauf.schritt(akteur=akteur, im_weg=im_weg, lidar=0.28, objekt=dict(OBJ), tiefe_hindernis=True)
                    self.assertIsNone(lauf.e.ablauf)
                    eingefroren = lauf.bild_zeit
                    for _ in range(50):                 # 5 s ohne neues Bild
                        b = lauf.schritt(neu=False, lidar=0.28, objekt=dict(OBJ), tiefe_hindernis=True)
                        self.assertEqual(lauf.bild_zeit, eingefroren)
                        self.assertFalse(bewegt(b), f'{lauf.t - eingefroren:.1f} s nach dem letzten Bild: {b}')
                    armwunsch = None
                    for _ in range(40):                 # frische freie Bilder: jetzt darf er zurueck
                        b = lauf.schritt(lidar=0.28, objekt=dict(OBJ), tiefe_hindernis=True)
                        if b['arm'] is not None:
                            armwunsch = b['arm']
                            break
                    self.assertEqual(armwunsch, 'fahrstellung')

    def test_freier_gegenfall_kehrt_zurueck(self):
        lauf = bis_erster_arm()
        for _ in range(330):
            lauf.schritt(akteur='Person', lidar=0.28, objekt=dict(OBJ), tiefe_hindernis=True)
        gesehen = lauf.t
        armwunsch = None
        for _ in range(40):
            b = lauf.schritt(lidar=0.28, objekt=dict(OBJ), tiefe_hindernis=True)
            if b['arm'] is not None:
                armwunsch = (lauf.t - gesehen, b['arm'])
                break
        self.assertIsNotNone(armwunsch)                       # Rueckkehrbedarf geht nicht verloren
        self.assertGreaterEqual(armwunsch[0], 2.0 - 1e-6)     # erst nach der bestehenden Zwei-Sekunden-Freipruefung
        self.assertEqual(armwunsch[1], 'fahrstellung')

    def test_ohne_akteur_wie_bisher(self):
        """Ohne Person: Plan laeuft durch (letzter Schritt Fahrstellung), Kontrolle frei -> weiter wie bisher."""
        lauf = Lauf({'fahrstellung': FAHR}, raeum_planer)
        arme, b = [], None
        for _ in range(200):
            da = not any(isinstance(a, dict) and a.get('winkel', [0] * 6)[5] == 130 for a in arme)
            b = lauf.schritt(lidar=0.28 if da else float('inf'), objekt=dict(OBJ) if da else None,
                             tiefe_hindernis=da)
            if b['arm'] is not None:
                arme.append(b['arm'])
            if b['aktion'] == 'fahren':
                break
        self.assertEqual(b['aktion'], 'fahren')
        self.assertEqual(arme[-1]['winkel'], FAHR)


if __name__ == '__main__':
    unittest.main(verbosity=2)
