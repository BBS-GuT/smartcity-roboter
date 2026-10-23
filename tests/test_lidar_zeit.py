#!/usr/bin/env python3
"""L3 (#62): Aufnahmezeit (header.stamp) eines LiDAR-Scans getrennt vom Empfang pruefen.

Frisch empfangen heisst nicht frisch gemessen. Uhr wird ueber Attrappen gesteuert (time.time = ROS-Zeit ohne
use_sim_time, time.monotonic = Empfang). Nur ROS-/Publisherattrappen, kein Geraet.
Aufruf: python3 tests/test_lidar_zeit.py
"""
import os
import sys
import time
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lidar_qualitaet as q  # noqa: E402  (Attrappen und Helfer fuer Scans/Knoten)

lidar = q.lidar


def stamp(sec, nanosec=0):
    return types.SimpleNamespace(stamp=types.SimpleNamespace(sec=sec, nanosec=nanosec))


def mit_aufnahme(aufnahme, werte=3.0):
    m = q.scan(werte)
    m.header = q.kopf(aufnahme)
    return m


KAPUTT = {
    'null': stamp(0, 0),
    'nanosec zu gross': stamp(999, 1_000_000_000),
    'nanosec negativ': stamp(999, -1),
    'sec negativ': stamp(-5, 0),
    'sec NaN': stamp(float('nan'), 0),
    'sec Text': stamp('999', 0),
    'sec bool': stamp(True, 0),
    'kein header': None,
}


class ReineZeitregel(unittest.TestCase):
    """Explizite Uhr: jetzt wird uebergeben."""

    def pruefe(self, kopf, jetzt=1000.0, vorher=None):
        m = types.SimpleNamespace() if kopf is None else types.SimpleNamespace(header=kopf)
        return lidar.aufnahme_pruefen(m, jetzt, vorher)

    def test_aktuell_und_kleine_transportverzoegerung(self):
        for alter in (0.0, 0.05, 0.3, 0.99):
            with self.subTest(alter=alter):
                aufnahme, grund = self.pruefe(q.kopf(1000.0 - alter))
                self.assertIsNone(grund)
                self.assertAlmostEqual(aufnahme, 1000.0 - alter, places=6)

    def test_alt_zukunft_kaputt(self):
        self.assertIn('alt', self.pruefe(q.kopf(970.0))[1])                      # 30 s alter Header
        self.assertIn('Zukunft', self.pruefe(q.kopf(1005.0))[1])                 # unplausibel zukuenftig
        self.assertIn('Zukunft', self.pruefe(q.kopf(1000.001))[1])               # keine erfundene Toleranz
        self.assertIn('Zukunft', self.pruefe(q.kopf(-1000.0 + 2000.0), jetzt=0.5)[1])  # Uhrsprung zurueck
        for name, kopf in KAPUTT.items():
            with self.subTest(name):
                aufnahme, grund = self.pruefe(kopf)
                self.assertIsNone(aufnahme)
                self.assertIsNotNone(grund)

    def test_fortschritt(self):
        kopf = q.kopf(999.9)
        vorher = self.pruefe(kopf)[0]
        self.assertEqual(self.pruefe(kopf, vorher=vorher)[1], 'doppelt')
        self.assertIn('zurueck', self.pruefe(q.kopf(999.8), vorher=vorher)[1])
        self.assertIsNone(self.pruefe(q.kopf(999.95), vorher=vorher)[1])

    def test_alter_bei_auswertung(self):
        self.assertIsNone(lidar.aufnahme_alter(999.5, 1000.0))
        self.assertIn('alt', lidar.aufnahme_alter(998.9, 1000.0))
        self.assertIn('Zukunft', lidar.aufnahme_alter(1000.5, 1000.0))
        self.assertIsNotNone(lidar.aufnahme_alter(None, 1000.0))


class Linienfolger(unittest.TestCase):
    def halt(self, n, text):
        lin, quer, dreh, status = n.entscheide()
        self.assertEqual((lin, quer, dreh), (0.0, 0.0, 0.0), status)
        self.assertIn(text, status)

    def test_frischer_empfang_mit_altem_header_haelt(self):
        n = q.linienfolger()
        n.on_scan(mit_aufnahme(time.time() - 30.0), '/scan1', 1)
        self.halt(n, '/scan1: Aufnahme 30')

    def test_kaputte_und_zukuenftige_stempel_halten(self):
        for name, kopf in dict(KAPUTT, zukunft=q.kopf(time.time() + 5.0)).items():
            with self.subTest(name):
                n = q.linienfolger()
                m = q.scan(3.0)
                if kopf is None:
                    del m.header
                else:
                    m.header = kopf
                n.on_scan(m, '/scan0', 0)
                self.halt(n, 'LIDAR UNBEKANNT (/scan0')

    def test_scan_altert_bis_zur_entscheidung(self):
        n = q.linienfolger(mit_aufnahme(time.time() - 0.8))          # beim Empfang 0,8 s: noch gut
        self.assertGreater(n.entscheide()[0], 0)
        echt = time.time
        with mock.patch.object(time, 'time', lambda: echt() + 0.3):  # 0,3 s spaeter ohne neuen Scan: 1,1 s
            n.bild_zeit, n.ki = time.time(), (time.time(), n.ki[1])
            self.halt(n, 'Aufnahme 1.1 s alt')

    def test_wiederfreigabe_erst_mit_neuer_gueltiger_nachricht(self):
        n = q.linienfolger()
        alt = mit_aufnahme(time.time() - 30.0)
        n.on_scan(alt, '/scan0', 0)
        self.halt(n, 'Aufnahme 30')
        n.on_scan(alt, '/scan0', 0)                                   # dieselbe alte Nachricht nochmal
        self.halt(n, 'Aufnahme 30')
        n.on_scan(q.scan(3.0), '/scan0', 0)                           # neue gueltige Nachricht
        self.assertGreater(n.entscheide()[0], 0)

    def test_marke_rueckt_nur_mit_akzeptiertem_stempel_vor(self):
        # Codex-Befund zu PR #143: nach einem abgelehnten Ruecklauf darf ein wieder steigender, aber immer noch
        # aelterer Stempel nicht als aktuell gelten (auch nicht nach einem kaputten Stempel dazwischen)
        jetzt = time.time()
        n = q.linienfolger(mit_aufnahme(jetzt - 0.05))               # gueltig, Marke = jetzt - 0,05
        n.on_scan(mit_aufnahme(jetzt - 0.5), '/scan0', 0)
        self.halt(n, 'zurueck')
        n.on_scan(mit_aufnahme(jetzt - 0.4), '/scan0', 0)             # steigt wieder, liegt aber vor der Marke
        self.halt(n, 'zurueck')
        kaputt = q.scan(3.0)
        kaputt.header = stamp(0, 0)
        n.on_scan(kaputt, '/scan0', 0)
        n.on_scan(mit_aufnahme(jetzt - 0.3), '/scan0', 0)
        self.halt(n, 'zurueck')
        n.on_scan(q.scan(3.0), '/scan0', 0)                           # neuer als die Marke: wieder frei
        self.assertGreater(n.entscheide()[0], 0)

    def test_doppelte_nachricht_erneuert_empfang_nicht(self):
        n = q.linienfolger()
        m = q.scan(3.0)
        n.on_scan(m, '/scan0', 0)
        echt = time.monotonic
        with mock.patch.object(time, 'monotonic', lambda: echt() + 1.5):
            n.on_scan(m, '/scan0', 0)                                 # Wiederholung, keine neue Messung
            n.on_scan(q.scan(3.0), '/scan1', 1)
            self.halt(n, 'KEIN LIDAR: /scan0: letzter Scan vor 1.5')


class SimZeit(unittest.TestCase):
    """Codex-Befund zu PR #143: mit use_sim_time stempeln Treiber/Simulator in ROS-Zeit, nicht in Systemzeit.
    Verglichen wird mit der Uhr des Knotens."""

    def uhr(self, sekunden):
        ns = int(sekunden * 1e9)
        return types.SimpleNamespace(now=lambda: types.SimpleNamespace(nanoseconds=ns))

    def test_linienfolger(self):
        n = q.lf.LineFollower()
        q.geometrie(n)
        n.get_clock = lambda: self.uhr(50.3)                          # Simulationszeit 50,3 s
        for t, i in q.KANAELE:
            n.on_scan(mit_aufnahme(50.2), t, i)                       # 0,1 s alt in ROS-Zeit: gueltig
        self.assertIsNone(n.notbremse(0.05, 0.0, 0.0))
        n.get_clock = lambda: self.uhr(52.0)                          # 1,8 s spaeter ohne neuen Scan
        self.assertIn('Aufnahme 1.8 s alt', n.notbremse(0.05, 0.0, 0.0))

    def test_ki_zentrale(self):
        z = q.zentrale.Zentrale()
        q.geometrie(z)
        z.get_clock = lambda: self.uhr(50.3)
        for t, i in q.KANAELE:
            z._scan(mit_aufnahme(50.2), t, i)
        self.assertEqual(z.lidar_pruefen()[0], float('inf'))
        z.get_clock = lambda: self.uhr(52.0)
        self.assertEqual(z.lidar_pruefen(), (None, None, None))


class KiZentrale(unittest.TestCase):
    def test_frischer_empfang_mit_altem_header(self):
        z = q.ki_zentrale()
        z._scan(mit_aufnahme(time.time() - 30.0), '/scan0', 0)
        self.assertEqual(z.lidar_pruefen(), (None, None, None))
        b = q.befehl(z)
        self.assertEqual(b['aktion'], 'stopp')
        self.assertIsNone(z.lidar_hinten())

    def test_kaputt_und_zukunft(self):
        for name, kopf in dict(KAPUTT, zukunft=q.kopf(time.time() + 5.0)).items():
            with self.subTest(name):
                z = q.ki_zentrale()
                m = q.scan(3.0)
                if kopf is None:
                    del m.header
                else:
                    m.header = kopf
                z._scan(m, '/scan1', 1)
                self.assertEqual(z.lidar_pruefen(), (None, None, None))

    def test_marke_rueckt_nur_mit_akzeptiertem_stempel_vor(self):
        jetzt = time.time()
        z = q.ki_zentrale(mit_aufnahme(jetzt - 0.05))
        z._scan(mit_aufnahme(jetzt - 0.5), '/scan1', 1)
        z._scan(mit_aufnahme(jetzt - 0.4), '/scan1', 1)
        self.assertEqual(z.lidar_pruefen(), (None, None, None))
        z._scan(q.scan(3.0), '/scan1', 1)
        self.assertEqual(z.lidar_pruefen()[0], float('inf'))

    def test_altern_und_wiederfreigabe(self):
        # The 0.2-second remaining budget tests acquisition age, not host CPU
        # speed. Hold both clocks fixed while constructing/querying the node.
        jetzt, mono = time.time(), time.monotonic()
        with mock.patch.object(time, 'time', return_value=jetzt), \
                mock.patch.object(time, 'monotonic', return_value=mono):
            z = q.ki_zentrale(mit_aufnahme(jetzt - 0.8))
            self.assertEqual(z.lidar_pruefen()[0], float('inf'))
            with mock.patch.object(time, 'time', return_value=jetzt + .3), \
                    mock.patch.object(time, 'monotonic', return_value=mono + .3):
                self.assertEqual(z.lidar_pruefen(), (None, None, None))
                for t, i in q.KANAELE:
                    z._scan(q.scan(3.0), t, i)                        # neue gueltige Nachrichten
                self.assertEqual(z.lidar_pruefen()[0], float('inf'))


if __name__ == '__main__':
    unittest.main()
