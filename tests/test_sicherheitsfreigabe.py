#!/usr/bin/env python3
"""A1: echte Bildannahme und Entscheidung mit ROS-Attrappen, ohne Hardware."""
import math
import os
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'attrappen'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'line_follower'))
import line_follower as lf


_scan_nr = [0]


def scan(abstand):
    _scan_nr[0] += 1                    # jeder Scan neu: Aufnahme 50 ms vor jetzt, je Scan etwas spaeter
    t = lf.time.time() - 0.05 + _scan_nr[0] * 1e-6
    kopf = types.SimpleNamespace(stamp=types.SimpleNamespace(sec=int(t), nanosec=int((t % 1) * 1e9)))
    return types.SimpleNamespace(ranges=[abstand] * 360, angle_min=-math.pi, angle_increment=2 * math.pi / 360,
                                 range_min=0.05, range_max=12.0, header=kopf)


class Sensorfreigabe(unittest.TestCase):
    def setUp(self):
        self.uhr = patch.object(lf.time, 'time', return_value=1000.0)
        self.zeit = self.uhr.start()
        self.addCleanup(self.uhr.stop)
        self.mono = patch.object(lf.time, 'monotonic', return_value=1000.0)   # Empfangszeit der Scans
        self.mono.start()
        self.addCleanup(self.mono.stop)

    def neu(self):
        n = lf.LineFollower()
        n._p.update(show=False, publish_image=False)
        self.lidar(n)
        n.ki = (1000.0, {'aktion': 'fahren', 'faktor': 1.0})
        n.sucher.suche = lambda img, *_, **__: {
            'gefunden': True, 'boden': [(0.05 + k * 0.02, 0.0) for k in range(30)],
            'quer': 0.0, 'kurs': 0.0}
        return n

    def lidar(self, n, abstand=1.0, zeit=1000.0):
        with patch.object(lf.time, 'monotonic', return_value=zeit):
            n.scans.clear()
            n.on_scan(scan(abstand), '/scan0', 0)
            n.on_scan(scan(abstand), '/scan1', 1)

    def bild(self, n, alter=0.1, stamp=None):
        if stamp is None:
            aufnahme = 1000.0 - alter
            sec = int(aufnahme)
            stamp = types.SimpleNamespace(sec=sec, nanosec=round((aufnahme - sec) * 1e9))
        n.on_image(types.SimpleNamespace(header=types.SimpleNamespace(stamp=stamp), img=None))

    def halt(self, n, grund):
        ergebnis = n.entscheide()
        self.assertEqual(ergebnis[:3], (0.0, 0.0, 0.0), ergebnis)
        self.assertIn(grund, ergebnis[3])

    def test_bildalter_und_grenzen(self):
        for alter, faehrt in [(0.1, True), (0.25, True), (0.599, True),
                              (0.601, False), (0.7, False), (5.0, False), (6.0, False)]:
            with self.subTest(alter=alter):
                n = self.neu()
                self.bild(n, alter)
                if faehrt:
                    self.assertGreater(n.entscheide()[0], 0)
                else:
                    self.halt(n, 'STOPP')
        n = self.neu()
        self.bild(n, 0.3)
        self.assertAlmostEqual(n.entscheide()[0], 0.075)
        # Exakte Vergleichsgrenze ohne Rundungsfehler der Epochensubtraktion.
        n.bild_alter = n.p('bild_alter_max')
        self.assertGreater(n.entscheide()[0], 0)

    def test_ungueltige_stempel_ersetzen_keine_aufnahmezeit(self):
        for stamp in [types.SimpleNamespace(sec=1001, nanosec=0),
                      types.SimpleNamespace(sec=0, nanosec=0),
                      types.SimpleNamespace(sec=999, nanosec=-1),
                      types.SimpleNamespace(sec=999, nanosec=1_000_000_000),
                      types.SimpleNamespace(sec=float('nan'), nanosec=0),
                      types.SimpleNamespace(sec=float('inf'), nanosec=0),
                      types.SimpleNamespace(sec='falsch', nanosec=0), object()]:
            with self.subTest(stamp=stamp):
                n = self.neu()
                self.bild(n)
                self.zeit.return_value = 1000.1
                self.bild(n, stamp=stamp)
                self.halt(n, 'ZEITSTEMPEL UNGUELTIG')
                self.assertEqual(n.bild_zeit, 1000.0)
                self.zeit.return_value = 1000.0

    def test_aufnahmealter_waechst_bis_zur_entscheidung(self):
        n = self.neu()
        self.bild(n, 0.4)
        self.zeit.return_value = 1000.3
        self.halt(n, 'ZU ALT')

    def test_aufnahmezeit_bleibt_im_gedaechtnis(self):
        n = self.neu()
        with patch.object(n.gedaechtnis, 'hinzufuegen', wraps=n.gedaechtnis.hinzufuegen) as hinzu:
            self.bild(n, 0.2)
            self.assertAlmostEqual(hinzu.call_args.args[1], 999.8)

    def test_alle_manoever_passieren_pflichtpruefungen(self):
        for wunsch in [{'dreh': 0.8}, {'lin': -0.05}, {'quer': 0.05}]:
            for mangel in ['beide', 'lidar', 'kamera', 'alt', 'stempel', 'kritisch', 'scan_alt']:
                with self.subTest(wunsch=wunsch, mangel=mangel):
                    n = self.neu()
                    if mangel not in ['beide', 'kamera']:
                        self.bild(n, 0.7 if mangel == 'alt' else 0.1)
                    if mangel in ['beide', 'lidar']:
                        n.scans.clear()
                    if mangel == 'scan_alt':
                        self.lidar(n, zeit=998.0)
                    if mangel == 'kritisch':
                        self.lidar(n, 0.1)
                    if mangel == 'stempel':
                        n.stempel_ok = False
                    n.ki = (1000.0, {'aktion': 'manoever', 'manoever': wunsch})
                    self.halt(n, 'STOPP')

    def test_positive_manoever_und_wiederkehr(self):
        for wunsch in [{'dreh': 0.8}, {'lin': -0.05}, {'quer': 0.05}]:
            n = self.neu()
            self.bild(n, 6.0)
            self.halt(n, 'STOPP')
            self.bild(n)
            n.ki = (1000.0, {'aktion': 'manoever', 'manoever': wunsch})
            self.assertEqual(n.entscheide()[:3], tuple(wunsch.get(k, 0.0) for k in ['lin', 'quer', 'dreh']))

    def test_steuerung_veroeffentlicht_null_und_haltgrund(self):
        n = self.neu()
        n._p['drive'] = True
        n.scans.clear()
        n.ki = (1000.0, {'aktion': 'manoever', 'manoever': {'dreh': 0.8}})
        n.steuern()
        cmd = n.pub.letzte
        self.assertEqual((cmd.linear.x, cmd.linear.y, cmd.angular.z), (0.0, 0.0, 0.0))
        self.assertIn('KEIN LIDAR', n.pub_status.letzte.data)


if __name__ == '__main__':
    unittest.main()
