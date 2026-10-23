#!/usr/bin/env python3
"""#25: Personen-/Tier-/Fahrzeughalt beim Wegraeumen; nur kuenstliche Daten, kein ROS/Geraet."""
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ki'))
from ablaeufe import Wegraeumen  # noqa: E402
from entscheider import STANDARD  # noqa: E402

AKTEURE = ('Person', 'Hund', 'Auto')
NEUE_PHASEN = ('abstand', 'zurueck')
FERN = {'vor': 0.34, 'seite': 0.07, 'breite': 0.04, 'hoehe': 0.045, 'quelle': 'tiefe'}
PASSEND = dict(FERN, vor=STANDARD['greif_vor'], seite=0.0)


class Lauf:
    """Reale Ablaufmethoden mit Testuhr, Messwerten und kleinem reinem Planerstub."""
    def __init__(self, zielphase):
        self.ms, self.jetzt, self.strecke, self.letzter = 100000, 100.0, 0.0, None
        self.planungen = 0
        self.naeher_noetig = zielphase in ('naeher', 'rueckweg')
        self.objekt = None if zielphase == 'zurueck' else dict(FERN if zielphase == 'abstand' else PASSEND)
        self.lidar = 0.15 if zielphase == 'zurueck' else 0.34
        self.ablauf = Wegraeumen(self.jetzt, dict(STANDARD), planer=self.planer)
        self.phasen = [self.ablauf.phase]
        for _ in range(200):
            self.schritt()
            if self.ablauf.phase == zielphase:
                return
            if self.ablauf.ergebnis is not None:
                break
        raise AssertionError(f'{zielphase} nicht regulaer erreicht: {self.phasen}')

    def planer(self, objekt, seite):
        # Die Vorpruefung bekommt einen machbaren Plan; naeher erst bei der eigentlichen Planung.
        if self.ablauf.phase == 'planen':
            self.planungen += 1
            if self.naeher_noetig and self.planungen == 1:
                return {'naeher': 0.03}
        return {'schritte': [('heben', [90, 120, 10, 20, 90, 130], 1.0),
                             ('fahrstellung', [90, 120, 10, 20, 90, 30], 1.5)]}

    def schritt(self, akteur=None, dt=0.1, neu=True, im_weg=True):
        # Messstrecke folgt nur im Test dem vorherigen Wunsch; keine echte Bewegung.
        m = (self.letzter or {}).get('manoever') or {}
        self.strecke += m.get('lin', 0.0) * dt
        self.ms += round(dt * 1000)
        self.jetzt = self.ms / 1000
        w = {'neues_bild': neu, 'objekte': [] if akteur is None else [{'name': akteur, 'im_weg': im_weg}],
             'objekt': None if self.objekt is None else dict(self.objekt), 'lidar': self.lidar,
             'lidar_hinten': 1.0, 'strecke': self.strecke, 'strecke_gemessen': True}
        self.letzter = self.ablauf.schritt(self.jetzt, w)
        if self.phasen[-1] != self.ablauf.phase:
            self.phasen.append(self.ablauf.phase)
        # Planerthread wirklich rechnen lassen, ohne die kuenstliche Testuhr weiterzudrehen.
        if self.ablauf.phase in ('vorpruefen', 'planen'):
            ende = time.monotonic() + 2
            while self.ablauf.plan is None and time.monotonic() < ende:
                time.sleep(0.001)
            if self.ablauf.plan is None:
                raise AssertionError('Reiner Testplaner wurde nicht fertig')
        return self.letzter


class RaeumenPersonen(unittest.TestCase):
    def still(self, befehl):
        self.assertIsNotNone(befehl)
        self.assertEqual(befehl['aktion'], 'stopp')
        self.assertEqual(befehl['faktor'], 0.0)
        self.assertIsNone(befehl['manoever'])
        self.assertIsNone(befehl['arm'])

    def bewegung(self, befehl, phase):
        self.assertIsNotNone(befehl)
        self.assertEqual(befehl['aktion'], 'manoever')
        self.assertIsNone(befehl['arm'])
        if phase == 'abstand':
            self.assertGreater(befehl['manoever']['lin'], 0)
            self.assertGreater(befehl['manoever']['quer'], 0)
        else:
            self.assertLess(befehl['manoever']['lin'], 0)

    def test_freie_kontrollen_beider_phasen(self):
        for phase in NEUE_PHASEN:
            with self.subTest(phase=phase):
                lauf = Lauf(phase)
                erwartet = ['anschauen', 'vorpruefen', phase] if phase == 'abstand' else ['anschauen', phase]
                self.assertEqual(lauf.phasen, erwartet)
                self.assertGreater(lauf.lidar, STANDARD['notbremse_dist'])
                self.bewegung(lauf.schritt(), phase)

    def test_frischer_akteur_haelt_im_selben_zyklus(self):
        for phase in NEUE_PHASEN:
            for akteur in AKTEURE:
                for im_weg in (True, False):
                    with self.subTest(phase=phase, akteur=akteur, im_weg=im_weg):
                        lauf = Lauf(phase)
                        self.bewegung(lauf.schritt(), phase)
                        self.still(lauf.schritt(akteur, im_weg=im_weg))
                        self.assertEqual(lauf.ablauf.phase, phase)
                        self.assertEqual(lauf.ablauf.lebend_name, akteur)
                        self.assertIsNone(lauf.ablauf.ergebnis)

    def test_halt_pausiert_phasenuhr_und_streckenfortschritt(self):
        for phase in NEUE_PHASEN:
            for akteur in AKTEURE:
                with self.subTest(phase=phase, akteur=akteur):
                    lauf = Lauf(phase)
                    lauf.schritt()
                    lauf.schritt()
                    alter = lauf.ablauf.dauer(lauf.jetzt)
                    fortschritt = lauf.ablauf.zurueck_gefahren
                    if phase == 'zurueck':
                        self.assertGreater(fortschritt, 0.0)
                    for _ in range(40):  # 20 s: laenger als der 15-s-Abstandstimeout, unter dem 30-s-Abbruch
                        self.still(lauf.schritt(akteur, dt=0.5))
                        self.assertEqual(lauf.ablauf.phase, phase)
                        self.assertAlmostEqual(lauf.ablauf.dauer(lauf.jetzt), alter)
                        self.assertEqual(lauf.ablauf.zurueck_gefahren, fortschritt)
                        self.assertIsNone(lauf.ablauf.ergebnis)

    def test_frische_sichtung_verlaengert_bestehendes_wartefenster(self):
        for phase in NEUE_PHASEN:
            for akteur in AKTEURE:
                with self.subTest(phase=phase, akteur=akteur):
                    lauf = Lauf(phase)
                    lauf.schritt()
                    self.still(lauf.schritt(akteur))
                    zuletzt = lauf.ablauf.lebend_zuletzt
                    self.still(lauf.schritt(akteur, dt=0.4, neu=False))
                    self.assertEqual(lauf.ablauf.lebend_zuletzt, zuletzt)
                    self.still(lauf.schritt(dt=1.5))  # 1,9 s seit letzter frischer Sichtung
                    self.still(lauf.schritt(akteur))  # neue Sichtung setzt die bestehende Frist neu
                    self.assertGreater(lauf.ablauf.lebend_zuletzt, zuletzt)
                    self.still(lauf.schritt(dt=1.9))
                    self.bewegung(lauf.schritt(dt=0.2), phase)  # 2,1 s, frisches freies Bild
                    self.assertIsNone(lauf.ablauf.lebend_seit)

    def test_bestehende_schutzphasen_bleiben_wirksam(self):
        for phase in ('planen', 'naeher', 'ausfuehren', 'rueckweg'):
            for akteur in AKTEURE:
                with self.subTest(phase=phase, akteur=akteur):
                    lauf = Lauf(phase)
                    alter = lauf.ablauf.dauer(lauf.jetzt)
                    self.still(lauf.schritt(akteur))
                    self.assertEqual(lauf.ablauf.phase, phase)
                    self.assertAlmostEqual(lauf.ablauf.dauer(lauf.jetzt), alter)

    def test_armwartezeit_wird_waehrend_halt_nicht_verbraucht(self):
        for akteur in AKTEURE:
            with self.subTest(akteur=akteur):
                lauf = Lauf('ausfuehren')
                self.assertIsNotNone(lauf.letzter['arm'])  # regulaer bereits gestarteter erster Testschritt
                self.still(lauf.schritt(dt=0.4))
                for _ in range(20):
                    self.still(lauf.schritt(akteur, dt=0.5))
                    self.assertEqual(lauf.ablauf.nr, 0)
                self.still(lauf.schritt(dt=1.9))
                self.still(lauf.schritt(dt=0.2))  # Freigabe, aber erste Armwartezeit noch nicht abgelaufen
                self.assertEqual(lauf.ablauf.nr, 0)
                for _ in range(10):
                    b = lauf.schritt()
                    if b['arm'] is not None:
                        break
                self.assertIsNotNone(b['arm'])
                self.assertEqual(lauf.ablauf.nr, 1)

    def test_fortsetzung_nach_freipruefung_kann_regulaer_abschliessen(self):
        for phase in NEUE_PHASEN:
            for akteur in AKTEURE:
                with self.subTest(phase=phase, akteur=akteur):
                    lauf = Lauf(phase)
                    self.still(lauf.schritt(akteur))
                    for _ in range(19):
                        self.still(lauf.schritt())
                    self.bewegung(lauf.schritt(dt=0.2), phase)
                    arme = []
                    for _ in range(200):
                        if lauf.ablauf.phase in ('anschauen', 'abstand'):
                            lauf.objekt, lauf.lidar = dict(PASSEND), PASSEND['vor']
                        if lauf.ablauf.phase == 'kontrolle':
                            lauf.objekt, lauf.lidar = None, 1.0
                        b = lauf.schritt()
                        if b is None:
                            break
                        if b['arm'] is not None:
                            arme.append(b['arm'])
                    self.assertEqual(lauf.ablauf.ergebnis, 'frei')
                    self.assertEqual(len(arme), 2)
                    self.assertIn('planen', lauf.phasen)
                    self.assertIn('ausfuehren', lauf.phasen)
                    self.assertIn('kontrolle', lauf.phasen)

    def test_bestehender_abbruch_bei_dauerhafter_sichtung(self):
        for phase in NEUE_PHASEN:
            for akteur in AKTEURE:
                with self.subTest(phase=phase, akteur=akteur):
                    lauf = Lauf(phase)
                    self.still(lauf.schritt(akteur))
                    for _ in range(29):
                        self.still(lauf.schritt(akteur, dt=1.0))
                    self.still(lauf.schritt(akteur, dt=0.9))
                    self.assertIsNone(lauf.schritt(akteur, dt=0.2))
                    self.assertEqual(lauf.ablauf.ergebnis, 'fehler')


if __name__ == '__main__':
    unittest.main(verbosity=2)
