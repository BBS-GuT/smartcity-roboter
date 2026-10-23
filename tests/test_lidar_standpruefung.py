#!/usr/bin/env python3
"""#67: Bewertung der statischen LiDAR-Etappe, ohne ROS und ohne Geraet.

Die Statusmeldungen stammen aus dem ECHTEN Linienfolger-Code (ROS-Attrappen) im Testmodus, damit die Bewertung
dieselben Haltegruende erkennt, die der Roboter tatsaechlich sendet. Bewegte Faelle werden nie bestanden.
Aufruf: python3 tests/test_lidar_standpruefung.py
"""
import json
import os
import sys
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, '..', 'scripts'))
import test_lidar_qualitaet as q  # noqa: E402
import lidar_standpruefung as P  # noqa: E402

QUELLEN = ('/scan0', '/scan1')
FALL = {f.id: f for f in P.FAELLE}


def lf_status(scans=None, **param):
    """Ein echter Statusdatensatz des Linienfolgers im Testmodus (drive=False)."""
    n = q.linienfolger()
    n._p.update(drive=False, **param)
    if scans is not None:
        n.scans.clear()
        n.scan_stempel.clear()       # die Scans dieses Falls wurden vor dem Linienfolger erzeugt
        for topic, index, msg in scans:
            n.on_scan(msg, topic, index)
    n.steuern()
    return json.loads(n.pub_status.letzte.data)


def proben(lf, ki=None, start=100.0, dauer=6.0, schritt=0.2):
    """Gleichbleibende Meldungen ueber das Beobachtungsfenster."""
    ergebnis, t = [], start
    while t < start + dauer:
        ergebnis.append((t, 'lf', lf))
        if ki is not None:
            ergebnis.append((t, 'ki', ki))
        t += schritt
    return ergebnis


KI_FREI = {'lidar': 99.0, 'arm_erlaubt': False}
KI_UNBEKANNT = {'lidar': None, 'arm_erlaubt': False}


class Bewertung(unittest.TestCase):
    def test_echte_meldungen_frei_und_quelle_fehlt(self):
        frei = lf_status()
        self.assertIsNone(P.lidar_grund(frei['status']))
        self.assertEqual(P.bewerten(FALL['S01'], proben(frei, KI_FREI), 100.0, QUELLEN)['status'], 'bestanden')
        # Nur /scan1 frisch: der echte Linienfolger nennt /scan0 - S04a besteht, S04b nicht (falsche Quelle)
        fehlt = lf_status([('/scan1', 1, q.scan(3.0))])
        self.assertIn('/scan0', P.lidar_grund(fehlt['status']))
        self.assertEqual((fehlt['linear'], fehlt['quer'], fehlt['angular']), (0.0, 0.0, 0.0))
        e = P.bewerten(FALL['S04a'], proben(fehlt, KI_UNBEKANNT), 100.0, QUELLEN)
        self.assertEqual(e['status'], 'bestanden', e)
        e = P.bewerten(FALL['S04b'], proben(fehlt, KI_UNBEKANNT), 100.0, QUELLEN)
        self.assertEqual(e['status'], 'nicht bestanden')
        self.assertTrue(any('/scan1' in f for f in e['fehler']))
        # ...und S01 darf mit dieser Meldung nicht bestehen
        self.assertEqual(P.bewerten(FALL['S01'], proben(fehlt, KI_UNBEKANNT), 100.0, QUELLEN)['status'],
                         'nicht bestanden')

    def test_echte_meldungen_ungueltig_notbremse_geometrie(self):
        ungueltig = lf_status([(t, i, q.scan(0.0)) for t, i in q.KANAELE])
        self.assertEqual(P.bewerten(FALL['S02a'], proben(ungueltig, KI_UNBEKANNT), 100.0, QUELLEN)['status'],
                         'bestanden')
        nah = lf_status([(t, i, q.hindernis_vorne(0.10)) for t, i in q.KANAELE])
        self.assertIn('NOTBREMSE', nah['status'])
        self.assertEqual(P.bewerten(FALL['S09a'], proben(nah, KI_FREI), 100.0, QUELLEN)['status'], 'bestanden')
        # Ein Halt ohne NOTBREMSE besteht S09a nicht (Ziel im falschen Bezug nicht erkannt)
        self.assertEqual(P.bewerten(FALL['S09a'], proben(ungueltig, KI_FREI), 100.0, QUELLEN)['status'],
                         'nicht bestanden')
        geo = lf_status(scan_frames=['laser_x', 'base_link'])
        e = P.bewerten(FALL['S07'], proben(geo, KI_UNBEKANNT), 100.0, QUELLEN)
        self.assertEqual(e['status'], 'bestanden', e)

    def test_kurzer_halt_im_freifall_oder_luecke_im_haltfall_faellt_durch(self):
        frei, halt = lf_status(), lf_status([('/scan1', 1, q.scan(3.0))])
        gemischt = proben(frei, KI_FREI)
        gemischt[20] = (gemischt[20][0], 'lf', halt)
        self.assertEqual(P.bewerten(FALL['S01'], gemischt, 100.0, QUELLEN)['status'], 'nicht bestanden')
        gemischt = proben(halt, KI_UNBEKANNT)
        gemischt[20] = (gemischt[20][0], 'lf', frei)
        self.assertEqual(P.bewerten(FALL['S04a'], gemischt, 100.0, QUELLEN)['status'], 'nicht bestanden')

    def test_befehl_bei_halt_muss_null_sein(self):
        halt = dict(lf_status([('/scan1', 1, q.scan(3.0))]), linear=0.1)
        e = P.bewerten(FALL['S04a'], proben(halt, KI_UNBEKANNT), 100.0, QUELLEN)
        self.assertEqual(e['status'], 'nicht bestanden')
        self.assertTrue(any('nicht 0' in f for f in e['fehler']))

    def test_einschwingen_und_erkennungszeit(self):
        frei, halt = lf_status(), lf_status([('/scan1', 1, q.scan(3.0))])
        p = [(t, s, frei if t < 101.2 else halt) for t, s, _ in proben(frei)]
        e = P.bewerten(FALL['S04a'], p, 100.0, QUELLEN)
        self.assertEqual(e['status'], 'bestanden')
        self.assertAlmostEqual(e['werte']['erster_halt_nach_s'], 1.2, delta=0.21)

    def test_fahrbetrieb_oder_armfreigabe_brechen_ab(self):
        faehrt = dict(lf_status(), drive=True)
        e = P.bewerten(FALL['S01'], proben(faehrt, KI_FREI), 100.0, QUELLEN)
        self.assertEqual((e['status'], e.get('abbruch')), ('blockiert', True))
        e = P.bewerten(FALL['S01'], proben(lf_status(), dict(KI_FREI, arm_erlaubt=True)), 100.0, QUELLEN)
        self.assertEqual((e['status'], e.get('abbruch')), ('blockiert', True))
        self.assertEqual(P.bewerten(FALL['S01'], [], 100.0, QUELLEN)['status'], 'blockiert')

    def test_ki_abstand(self):
        frei = lf_status()
        ki = {'lidar': 0.52, 'arm_erlaubt': False}
        self.assertEqual(P.bewerten(FALL['S09b'], proben(frei, ki), 100.0, QUELLEN, 0.50)['status'], 'bestanden')
        self.assertEqual(P.bewerten(FALL['S09b'], proben(frei, ki), 100.0, QUELLEN, 0.40)['status'],
                         'nicht bestanden')
        self.assertEqual(P.bewerten(FALL['S09b'], proben(frei, KI_FREI), 100.0, QUELLEN, 0.50)['status'],
                         'nicht bestanden')
        self.assertEqual(P.bewerten(FALL['S09b'], proben(frei, ki), 100.0, QUELLEN)['status'], 'blockiert')


class Ablauf(unittest.TestCase):
    class Attrappe:
        def __init__(self, meldung, ki):
            self.meldung, self.ki = meldung, ki

        def beobachten(self, dauer):
            return 100.0, proben(self.meldung, self.ki, dauer=dauer)

    def test_ueberspringen_beenden_und_bericht(self):
        antworten = iter(['', 'notiz eins', 's Treiber nicht trennbar', 'q'])
        ergebnisse = P.durchfuehren([FALL['S01'], FALL['S04a'], FALL['S04b']], QUELLEN,
                                    self.Attrappe(lf_status(), KI_FREI), frage=lambda _: next(antworten),
                                    ausgabe=lambda *_: None)
        self.assertEqual([(f.id, e['status']) for f, e in ergebnisse],
                         [('S01', 'bestanden'), ('S04a', 'blockiert')])
        self.assertEqual(ergebnisse[0][1]['notiz'], 'notiz eins')
        kopf = {'geraet': 'TEST', 'pruefer': 'p', 'beobachter': 'b', 'datum': '2000-01-01',
                'beginn': 'x', 'git': {'sha': 'abc123', 'aenderungen': ''}, 'quellen': list(QUELLEN),
                'konfiguration': {'dateien': ['config/roboter.yaml'], 'sha256': '0' * 64, 'werte': {}}}
        text = P.bericht(kopf, ergebnisse)
        self.assertIn('`abc123`', text)
        self.assertIn('Treiber nicht trennbar', text)
        for fall, _ in P.BEWEGT:
            zeile = next(z for z in text.splitlines() if z.startswith(f'| {fall} '))
            self.assertIn('nicht durchgefuehrt', zeile)
            self.assertNotIn('bestanden', zeile)

    def test_abbruch_bei_fahrbetrieb(self):
        antworten = iter(['', ''])
        ergebnisse = P.durchfuehren([FALL['S01'], FALL['S04a']], QUELLEN,
                                    self.Attrappe(dict(lf_status(), drive=True), KI_FREI),
                                    frage=lambda _: next(antworten), ausgabe=lambda *_: None)
        self.assertEqual(len(ergebnisse), 1)
        self.assertTrue(ergebnisse[0][1]['abbruch'])

    def test_werkzeug_sendet_nichts(self):
        with open(P.__file__) as f:
            quelle = f.read()
        for verboten in ('create_publisher', 'cmd_vel', 'Twist', 'set_parameters', '/ki/kommando'):
            self.assertNotIn(verboten, quelle)

    def test_konfiguration_liest_lidar_parameter(self):
        cfg = P.konfiguration()
        self.assertIn('config/roboter.yaml', cfg['dateien'])
        self.assertEqual(cfg['werte']['line_follower']['scan_topics'], ['/scan0', '/scan1'])
        self.assertEqual(len(cfg['sha256']), 64)


if __name__ == '__main__':
    unittest.main()
