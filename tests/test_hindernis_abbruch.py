#!/usr/bin/env python3
"""#52: Hinderniserinnerung bleibt, wenn das Wegraeumen abgebrochen wird (Statusausfall, Arm aus, Notbremse).

Echter Entscheider, natuerliche Phasen, Radstrecke aus den Fahrwuenschen; kein ROS, kein Geraet.
"""
import unittest

from raeum_lauf import Lauf
from entscheider import STANDARD

START = STANDARD['greif_vor'] + 0.06   # Hindernis liegt so weit voraus (m)
SICHT = STANDARD['greif_vor'] + 0.04   # naeher sieht die Kamera es (in diesem Test) nicht mehr


class Welt:
    def __init__(self):
        self.lauf = Lauf()

    def rest(self):
        return START - self.lauf.strecke

    def schritt(self, sehen=True, **kw):
        rest = self.rest()
        w = {'objekt': {'vor': rest, 'seite': 0.0, 'breite': 0.04, 'hoehe': 0.045, 'quelle': 'tiefe'}
             if sehen and rest >= SICHT else None,
             'lidar': rest if sehen and rest >= SICHT else float('inf')}
        w.update(kw)
        return self.lauf.schritt(**w)

    def bis_abstand_und_verloren(self):
        for _ in range(200):
            self.schritt()
            if self.lauf.phase() == 'abstand' and self.rest() < SICHT - 0.005:
                break
        assert self.lauf.phase() == 'abstand', self.lauf.phase()
        for _ in range(3):                    # Kamera und LiDAR melden nichts mehr
            self.schritt(sehen=False)
        assert self.lauf.phase() == 'abstand'

    def danach(self, n=80):
        aktionen = [self.schritt(sehen=False)['aktion'] for _ in range(n)]
        return aktionen


class HindernisAbbruch(unittest.TestCase):
    def pruefe_gesperrt(self, w, abgebrochen=True):
        aktionen = w.danach()
        self.assertNotIn('fahren', aktionen)
        if abgebrochen:
            self.assertNotIn('manoever', aktionen)      # kein neuer Raeumversuch nach der Armrueckkehr
        self.assertIsNotNone(w.lauf.e.hindernis_merk)
        self.assertIn('zu nah fuer die Kamera', w.lauf.letzter['grund'])

    def test_kontrolle_ohne_abbruch(self):
        """Verloren in Greifweite (laut Radstrecke): greift blind, faehrt zur Kontrolle hinter die letzte Sichtung
        zurueck. Liegt es danach noch da (Welt nimmt es hier nie weg), faehrt er nie drueber."""
        w = Welt()
        w.bis_abstand_und_verloren()
        aktionen = [w.schritt()['aktion'] for _ in range(1500)]
        self.assertNotIn('fahren', aktionen)
        texte = [t for _, t, _ in w.lauf.e.ereignisse]
        self.assertTrue(any('greife nach der letzten Messung' in t for t in texte), texte)
        self.assertTrue(any('Weg noch nicht frei' in t for t in texte), texte)

    def test_blind_ohne_platz_hinten(self):
        """Blind gegriffen, hinten nicht frei: Kontrolle saehe die Stelle nicht -> nicht 'frei', sondern warten."""
        w = Welt()
        w.bis_abstand_und_verloren()
        aktionen = [w.schritt(lidar_hinten=0.1)['aktion'] for _ in range(300)]
        self.assertNotIn('fahren', aktionen)

    def test_blind_nicht_ueber_die_greifweite(self):
        """Kamera verliert es beim Heranfahren: mit der Radstrecke weiterrechnen statt mit der alten Messung."""
        w = Welt()
        w.bis_abstand_und_verloren()
        w.danach()
        self.assertGreaterEqual(w.rest(), STANDARD['greif_vor'] - STANDARD['greif_toleranz'] / 2 - 0.005)

    def test_statusausfall_ohne_start(self):
        w = Welt()
        w.bis_abstand_und_verloren()
        w.lauf.e.fahrt_aktiv = False           # Linienfolgerstatus kurz veraltet (setzt sonst die Zentrale)
        w.schritt(sehen=False)
        w.lauf.e.fahrt_aktiv = True            # Status wieder frisch, KEIN START
        self.pruefe_gesperrt(w)

    def test_arm_ausgeschaltet(self):
        w = Welt()
        w.bis_abstand_und_verloren()
        w.lauf.e.arm_freigabe = False          # Panel -> Arm -> "KI darf den Arm bewegen" aus
        self.pruefe_gesperrt(w)

    def test_notbremse_zu_lange(self):
        w = Welt()
        w.bis_abstand_und_verloren()
        for _ in range(60):                    # 6 s Notbremse (> notbremse_abbruch)
            w.schritt(sehen=False, lidar=0.10)
        self.assertIsNone(w.lauf.e.ablauf)
        self.pruefe_gesperrt(w)

    def test_start_quittiert(self):
        w = Welt()
        w.bis_abstand_und_verloren()
        w.lauf.e.fahrt_aktiv = False
        w.schritt(sehen=False)
        w.lauf.e.fahrt_aktiv = True
        w.lauf.e.kommando(w.lauf.t, 'start')   # ausdrueckliche Quittung durch den Bediener
        self.assertIn('fahren', w.danach())


if __name__ == '__main__':
    unittest.main(verbosity=2)
