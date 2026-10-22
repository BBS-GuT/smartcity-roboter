#!/usr/bin/env python3
"""LiDAR-Datenqualitaet in KI-Zentrale und Linienfolger:
L1 (#60) vollstaendig ungueltige Scans sind unbekannt, nie frei.
L2 (#61) jeder Kanal in scan_topics ist Pflicht; ein frischer zweiter Kanal verdeckt keinen fehlenden/alten.

Nur ROS-Attrappen und die lokale Publisherattrappe, kein Motor/Geraet.
Aufruf: python3 tests/test_lidar_qualitaet.py
"""
import json
import math
import os
import sys
import time
import types
import unittest
from unittest import mock

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, 'attrappen'))
for _d in ('lib', 'line_follower', 'ki'):
    sys.path.insert(0, os.path.join(HIER, '..', _d))
import lidar  # noqa: E402
import line_follower as lf  # noqa: E402
import zentrale  # noqa: E402
from lidar_testdaten import geometrie  # noqa: E402

KANAELE = (('/scan0', 0), ('/scan1', 1))


_scan_nr = [0]


def kopf(aufnahme=None):
    """header mit Aufnahmezeit (Standard 50 ms vor jetzt, je Scan etwas spaeter = jeder Scan ist neu)."""
    _scan_nr[0] += 1
    t = time.time() - 0.05 + _scan_nr[0] * 1e-6 if aufnahme is None else aufnahme
    return types.SimpleNamespace(frame_id='base_link',
                                 stamp=types.SimpleNamespace(sec=int(t), nanosec=int((t % 1) * 1e9)))


def scan(werte=3.0, n=360, **meta):
    """LaserScan-Attrappe: 'werte' = Zahl fuer alle Strahlen oder Liste. Index n/2 = vorne."""
    m = types.SimpleNamespace(ranges=list(werte) if isinstance(werte, (list, tuple)) else [werte] * n,
                              angle_min=-math.pi, angle_increment=2 * math.pi / n, range_min=0.05, range_max=12.0,
                              header=kopf())
    m.__dict__.update(meta)
    if 'angle_max' not in meta:             # passend zur Strahlgeometrie (wie ein korrekter Treiber)
        m.angle_max = m.angle_min + (len(m.ranges) - 1) * m.angle_increment
    return m


def spaeter(sekunden):
    """Uhren (Wand- und monotone Zeit) um 'sekunden' vorstellen: Scans altern ohne neue Nachricht."""
    echt_t, echt_m = time.time, time.monotonic
    return mock.patch.multiple(time, time=lambda: echt_t() + sekunden, monotonic=lambda: echt_m() + sekunden)


def hindernis_vorne(abstand, rest=3.0, n=360):
    r = [rest] * n
    for k in range(n // 2 - 3, n // 2 + 4):
        r[k] = abstand
    return scan(r)


def ungueltige():
    """Jedes Mal neue Nachrichten (frische Aufnahmezeit): getestet wird der Inhalt, nicht das Alter."""
    return {
        'alle 0 unter range_min': scan(0.0),
        'leer': scan([]),
        'nur NaN': scan(float('nan')),
        'nur inf': scan(float('inf')),
        'alle ueber range_max': scan(20.0),
        'range_max <= range_min': scan(3.0, range_min=1.0, range_max=0.5),
        'range_min NaN': scan(3.0, range_min=float('nan')),
        'angle_increment 0': scan(3.0, angle_increment=0.0),
        'range_min negativ': scan(3.0, range_min=-1.0),
        'angle_max inf': scan(3.0, angle_max=float('inf')),
        'angle_max widerspruechlich': scan(3.0, angle_max=0.0),       # passend waere pi - 1 Grad
        'Messwerte keine Zahlen': scan(['x'] * 10),
        }


class ReineQualitaet(unittest.TestCase):
    def test_ungueltige_scans_haben_grund(self):
        for name, m in ungueltige().items():
            with self.subTest(name):
                self.assertIsNotNone(lidar.scan_pruefen(m))

    def test_gueltige_scans(self):
        self.assertIsNone(lidar.scan_pruefen(scan(3.0)))
        # Treiber mit angle_increment = Spanne / N statt / (N-1): ein Strahlabstand Spielraum
        self.assertIsNone(lidar.scan_pruefen(scan(3.0, angle_max=math.pi)))
        self.assertIsNotNone(lidar.scan_pruefen(scan(3.0, angle_max=math.pi + math.radians(1.5))))
        # einzelne ungueltige Strahlen machen den Scan nicht insgesamt unbrauchbar (Abdeckung: #79)
        self.assertIsNone(lidar.scan_pruefen(scan([0.0] * 359 + [3.0])))


def linienfolger(m=None):
    """Linienfolger mit gueltiger Kamera/Linie und KI-Freigabe; beide Kanaele bekommen Scan m (Standard 3 m frei)."""
    n = lf.LineFollower()
    geometrie(n)
    n._p.update(show=False, publish_image=False)
    jetzt = time.time()
    n.gedaechtnis.hinzufuegen([(0.05 + 0.02 * k, 0.0) for k in range(30)])
    n.bild_zeit, n.stempel_ok = jetzt, True             # gueltige Kamera/Linie
    n.ki = (jetzt, {'aktion': 'fahren', 'faktor': 1.0, 'grund': 'Weg frei'})   # KI gibt frei
    for t, i in KANAELE:
        n.on_scan(m if m is not None else scan(3.0), t, i)
    return n


def ki_zentrale(m=None, hull=(.06, .06, .06, .06)):
    z = zentrale.Zentrale()
    geometrie(z, hull)
    z.wahrnehmung['bild_zeit'] = time.time()           # frische Kamerabilder
    for t, i in KANAELE:
        z._scan(m if m is not None else scan(3.0), t, i)
    return z


def befehl(z):
    z._entscheiden()
    return json.loads(z.pubs['/ki/befehl'].letzte.data)


class Halt(unittest.TestCase):
    def halt(self, n, text):
        lin, quer, dreh, status = n.entscheide()
        self.assertEqual((lin, quer, dreh), (0.0, 0.0, 0.0), status)
        self.assertIn(text, status)


class Linienfolger(Halt):
    neu = staticmethod(linienfolger)

    def test_ungueltig_haelt_trotz_gueltiger_kamera_und_ki(self):
        for name, m in ungueltige().items():
            with self.subTest(name):
                self.halt(self.neu(m), 'LIDAR UNBEKANNT')

    def test_ein_ungueltiger_kanal_reicht_zum_halt(self):
        n = self.neu()
        n.on_scan(scan(0.0), '/scan1', 1)
        self.halt(n, '/scan1')

    def test_ki_manoever_uebersteuert_nicht(self):
        n = self.neu(scan(0.0))
        for wunsch in ({'lin': 0.05}, {'lin': -0.05}, {'dreh': 0.8}, {'quer': 0.05}):
            with self.subTest(wunsch=wunsch):
                n.ki = (time.time(), {'aktion': 'manoever', 'manoever': wunsch})
                self.halt(n, 'LIDAR UNBEKANNT')

    def test_publisherattrappe_bekommt_nullbefehl(self):
        n = self.neu(scan(0.0))
        n._p['drive'] = True
        n.steuern()
        cmd = n.pub.letzte
        self.assertEqual((cmd.linear.x, cmd.linear.y, cmd.angular.z), (0.0, 0.0, 0.0))
        self.assertIn('LIDAR UNBEKANNT', json.loads(n.pub_status.letzte.data)['status'])

    def test_gueltig_frei(self):
        self.assertGreater(self.neu().entscheide()[0], 0)

    def test_hindernis_10cm_notbremse(self):
        self.halt(self.neu(hindernis_vorne(0.10)), 'NOTBREMSE')

    def test_beide_veraltet_kein_lidar(self):
        n = self.neu()
        with spaeter(2.0):
            n.bild_zeit = time.time()
            n.ki = (time.time(), n.ki[1])
            self.halt(n, 'KEIN LIDAR')

    def test_wiederfreigabe_nach_gueltigem_scan(self):
        n = self.neu(scan(0.0))
        self.halt(n, 'LIDAR UNBEKANNT')
        for t, i in KANAELE:
            n.on_scan(scan(3.0), t, i)
        self.assertGreater(n.entscheide()[0], 0)


class KiZentrale(unittest.TestCase):
    neu = staticmethod(ki_zentrale)
    befehl = staticmethod(befehl)

    def test_ungueltig_ist_unbekannt_und_haelt(self):
        for name, m in ungueltige().items():
            with self.subTest(name):
                z = self.neu(m)
                self.assertEqual(z.lidar_pruefen(), (None, None, None))
                b = self.befehl(z)
                self.assertEqual(b['aktion'], 'stopp')
                self.assertIsNone(b['lidar'])
                self.assertIsNone(z.lidar_hinten())          # kein erfundener 5-m-Rueckraum

    def test_ein_ungueltiger_kanal_reicht(self):
        z = self.neu()
        z._scan(scan(0.0), '/scan1', 1)
        self.assertEqual(z.lidar_pruefen(), (None, None, None))

    def test_gueltig_frei(self):
        z = self.neu()
        self.assertEqual(z.lidar_pruefen()[0], float('inf'))
        self.assertEqual(self.befehl(z)['aktion'], 'fahren')

    def test_hindernis_10cm_notbremse(self):
        b = self.befehl(self.neu(hindernis_vorne(0.10)))
        self.assertEqual(b['aktion'], 'stopp')
        self.assertIn('NOTBREMSE', b['grund'])

    def test_beide_veraltet_kein_lidar(self):
        z = self.neu()
        with spaeter(2.0):
            self.assertEqual(z.lidar_pruefen(), (None, None, None))

    def test_wiederfreigabe_nach_gueltigem_scan(self):
        z = self.neu(scan(0.0))
        self.assertEqual(self.befehl(z)['aktion'], 'stopp')
        for t, i in KANAELE:
            z._scan(scan(3.0), t, i)
        self.assertEqual(z.lidar_pruefen()[0], float('inf'))


def veraltet(sekunden):
    """Nur die monotone Empfangsuhr vorstellen (Kamera/KI bleiben frisch, sie laufen auf time.time)."""
    echt = time.monotonic
    return mock.patch.object(time, 'monotonic', lambda: echt() + sekunden)


class Pflichtkanaele(Halt):
    def test_reine_regel(self):
        jetzt = 100.0
        ok = {'/scan0': (99.9, 'a'), '/scan1': (99.8, 'b')}
        self.assertEqual(lidar.pflichtkanaele(ok, ['/scan0', '/scan1'], jetzt), ([(99.9, 'a'), (99.8, 'b')], None))
        for name, scans, teil in [
                ('fehlt', {'/scan0': (99.9, 'a')}, '/scan1: noch nie'),
                ('20 s alt', {'/scan0': (99.9, 'a'), '/scan1': (80.0, 'b')}, '/scan1: letzter Scan vor 20.0 s'),
                ('beide alt', {'/scan0': (90.0, 'a'), '/scan1': (80.0, 'b')}, '/scan0'),
                ('keiner', {}, '/scan0: noch nie'),
                ('Zukunft (Uhr)', {'/scan0': (99.9, 'a'), '/scan1': (101.0, 'b')}, '/scan1')]:
            with self.subTest(name):
                frisch, grund = lidar.pflichtkanaele(scans, ['/scan0', '/scan1'], jetzt)
                self.assertEqual(frisch, [])
                self.assertIn(teil, grund)
        self.assertIsNotNone(lidar.pflichtkanaele(ok, [], jetzt)[1])          # keine Pflichtquelle festgelegt
        # ein Kanal ausserhalb von scan_topics ist nicht Pflicht (und zaehlt nicht)
        self.assertEqual(lidar.pflichtkanaele(ok, ['/scan0'], jetzt), ([(99.9, 'a')], None))

    def test_linienfolger(self):
        n = linienfolger()
        n.scans.pop('/scan1')                                   # Pflichtkanal fehlt, /scan0 frisch 3 m
        self.halt(n, 'KEIN LIDAR: /scan1: noch nie')
        n = linienfolger()
        with veraltet(20.0):
            n.on_scan(scan(3.0), '/scan0', 0)                   # /scan0 frisch, /scan1 20 s alt
            self.halt(n, 'KEIN LIDAR: /scan1: letzter Scan vor 20')
            n.on_scan(scan(3.0), '/scan1', 1)                   # gueltige Rueckkehr -> wieder frei
            self.assertGreater(n.entscheide()[0], 0)
        n = linienfolger()
        with veraltet(20.0):
            self.halt(n, '/scan0')                # beide alt
        n = linienfolger()
        n.on_scan(hindernis_vorne(0.10), '/scan1', 1)           # beide frisch: tatsaechliches Hindernis zaehlt
        self.halt(n, 'NOTBREMSE')
        n = linienfolger()
        n.on_scan(scan(0.10), '/scan9', 2)                      # kein Pflichtkanal -> egal
        self.assertGreater(n.entscheide()[0], 0)

    def test_ki_zentrale(self):
        z = ki_zentrale()
        z.scans.pop('/scan1')
        self.assertEqual(z.lidar_pruefen(), (None, None, None))
        self.assertEqual(befehl(z)['aktion'], 'stopp')
        z = ki_zentrale()
        with veraltet(20.0):
            z._scan(scan(3.0), '/scan0', 0)
            self.assertEqual(z.lidar_pruefen(), (None, None, None))
            z._scan(scan(3.0), '/scan1', 1)                     # gueltige Rueckkehr
            self.assertEqual(z.lidar_pruefen()[0], float('inf'))
        z = ki_zentrale()
        z._scan(hindernis_vorne(0.10), '/scan1', 1)
        self.assertLess(z.lidar_pruefen()[0], 0.12)


if __name__ == '__main__':
    unittest.main()
