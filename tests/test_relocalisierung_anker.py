#!/usr/bin/env python3
"""#31: echte globale Suchpfade mit ROS-Attrappen, ohne Roboter."""
import math
import os
import sys
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, 'attrappen'))
sys.path.insert(0, os.path.join(HIER, '..', 'kartograf'))
import kartograf as KG  # noqa: E402
K = KG.K
PUNKTE = np.array([[1.0, 0.0], [0.0, 1.0]])


class Wiederortungsanker(unittest.TestCase):
    def vorbereiten(self, pfad, scanzeit=10.0, empfang=10.0):
        bel = SimpleNamespace(bekannt=lambda: True, c={'min_guete': 0.35},
                              abgleichen=Mock(return_value=(None, 0.0)),
                              bekannt_anteil=lambda *a: 0.1, eintragen=Mock(),
                              global_suchen=Mock(return_value=((2.0, 3.0, 0.0), 0.9, True)))
        karte = SimpleNamespace(belegung=bel, einbau={}, fahrten=0)
        lok = K.Lokalisierung(karte)
        lok.bewegen(0, 0, 0, zeit=scanzeit)
        lok.scan(PUNKTE, empfang, scan_zeit=scanzeit)
        lok.bewegen(0.1, 0, 0, zeit=empfang + 0.1)
        node = KG.Kartograf.__new__(KG.Kartograf)
        node.kr = SimpleNamespace(lok=lok)
        node.karte, node.lock = karte, threading.Lock()
        node.fehlversuche, node.suche_laeuft = 0, True
        node.get_logger = lambda: SimpleNamespace(info=lambda *a: None)

        def suchen():
            with patch.object(KG.time, 'sleep'), patch.object(K.time, 'monotonic', return_value=100.0):
                return lok.global_suchen() if pfad == 'bibliothek' else node._global_suchen()
        return lok, bel, node, suchen

    def test_frische_suche_erlaubt_nahes_neues_gebiet(self):
        for pfad in ('bibliothek', 'thread'):
            with self.subTest(pfad=pfad):
                lok, bel, _, suchen = self.vorbereiten(pfad)
                suchen()
                self.assertEqual(lok.zuletzt_sicher, 10.0)
                self.assertEqual(lok.odom_sicher, (0, 0, 0))
                np.testing.assert_allclose(lok.pose, (2.1, 3, 0), atol=1e-12)
                bel.eintragen.reset_mock()
                lok.scan(PUNKTE, 10.5)
                bel.eintragen.assert_called_once()

    def test_zeit_und_bewegungsgrenzen_bleiben(self):
        for pfad in ('bibliothek', 'thread'):
            for zeit, dx, dw, erlaubt in ((11.5, 0, 0, True), (11.5001, 0, 0, False),
                                          (10.5, 0.299, 0, True), (10.5, 0.301, 0, False),
                                          (10.5, 0, math.radians(14.9), True),
                                          (10.5, 0, math.radians(15.1), False)):
                with self.subTest(pfad=pfad, zeit=zeit, dx=dx, dw=dw):
                    lok, bel, _, suchen = self.vorbereiten(pfad)
                    suchen()
                    lok.bewegen(dx, 0, dw, zeit=zeit)
                    bel.eintragen.reset_mock()
                    lok.scan(PUNKTE, zeit)
                    self.assertEqual(bel.eintragen.call_count, int(erlaubt))

    def test_mehrdeutig_und_fehlgeschlagen_setzen_keinen_anker(self):
        for pfad in ('bibliothek', 'thread'):
            for ergebnis in ((None, 0.1, False), ((2, 3, 0), 0.9, False)):
                with self.subTest(pfad=pfad, ergebnis=ergebnis):
                    lok, bel, _, suchen = self.vorbereiten(pfad)
                    bel.global_suchen.return_value = ergebnis
                    suchen()
                    self.assertIsNone(lok.pose)
                    self.assertIsNone(lok.zuletzt_sicher)
                    self.assertIsNone(lok.odom_sicher)
                    bel.eintragen.assert_not_called()

    def test_alter_messzeitpunkt_wird_nicht_empfangszeit(self):
        for pfad in ('bibliothek', 'thread'):
            with self.subTest(pfad=pfad):
                lok, bel, _, suchen = self.vorbereiten(pfad, scanzeit=8, empfang=10)
                suchen()
                self.assertIsNone(lok.zuletzt_sicher)
                bel.eintragen.reset_mock()
                lok.scan(PUNKTE, 10.5)
                bel.eintragen.assert_not_called()

    def test_neue_scans_waehrend_suche_aendern_nicht_suchbezug(self):
        for pfad in ('bibliothek', 'thread'):
            with self.subTest(pfad=pfad):
                lok, bel, _, suchen = self.vorbereiten(pfad)
                def waehrend(punkte):
                    lok.bewegen(0.35, 0, 0, zeit=10.4)
                    lok.scan(PUNKTE * 2, 10.4, scan_zeit=10.4)
                    return (2, 3, 0), 0.9, True
                bel.global_suchen.side_effect = waehrend
                suchen()
                self.assertEqual(lok.zuletzt_sicher, 10)
                self.assertEqual(lok.odom_sicher, (0, 0, 0))
                np.testing.assert_allclose(lok.pose, (2.45, 3, 0), atol=1e-12)
                bel.eintragen.reset_mock()
                lok.scan(PUNKTE, 10.5)
                bel.eintragen.assert_not_called()

    def test_spaetes_ende_ohne_neuen_scan_macht_daten_nicht_frisch(self):
        for pfad in ('bibliothek', 'thread'):
            with self.subTest(pfad=pfad):
                lok, bel, node, _ = self.vorbereiten(pfad)
                with patch.object(KG.time, 'sleep'), patch.object(K.time, 'monotonic', side_effect=[100, 102]):
                    lok.global_suchen() if pfad == 'bibliothek' else node._global_suchen()
                self.assertIsNone(lok.zuletzt_sicher)
                self.assertIsNone(lok.odom_sicher)

    def test_kartenwechsel_waehrend_threadsuche_verwirft_ergebnis(self):
        lok, bel, node, suchen = self.vorbereiten('thread')
        neu = K.Lokalisierung(SimpleNamespace(einbau={}))
        def wechseln(punkte):
            node.kr.lok = neu
            return (2, 3, 0), 0.9, True
        bel.global_suchen.side_effect = wechseln
        suchen()
        self.assertIsNone(neu.pose)
        self.assertIsNone(lok.pose)
        self.assertIsNone(lok.zuletzt_sicher)
        bel.eintragen.assert_not_called()

    def test_verzoegerter_scan_nutzt_interpolierte_odometrie(self):
        for pfad in ('bibliothek', 'thread'):
            with self.subTest(pfad=pfad):
                lok, bel, _, suchen = self.vorbereiten(pfad)
                lok.bewegen(0.2, 0, 0, zeit=11.0)
                lok.scan(PUNKTE, 11.0, scan_zeit=10.5)
                erwartet = lok.odom_bei(10.5)
                suchen()
                self.assertEqual(lok.zuletzt_sicher, 10.5)
                np.testing.assert_allclose(lok.odom_sicher, erwartet, atol=1e-12)
                np.testing.assert_allclose(lok.pose, K.verknuepfen((2, 3, 0), K.relativ(erwartet, lok.odom)),
                                           atol=1e-12)

    def test_echter_thread_mit_neuen_scans_und_bewegung(self):
        for wechsel in (False, True):
            for scanzeit in (10.4, 12.0):
                with self.subTest(wechsel=wechsel, scanzeit=scanzeit):
                    lok, bel, node, _ = self.vorbereiten('thread')
                    gestartet, weiter = threading.Event(), threading.Event()
                    def warten(punkte):
                        gestartet.set()
                        if not weiter.wait(3):
                            raise RuntimeError('Suchtest wurde nicht freigegeben')
                        return (2, 3, 0), 0.9, True
                    bel.global_suchen.side_effect = warten
                    fehler = []
                    def arbeit():
                        try:
                            node._global_suchen()
                        except BaseException as error:
                            fehler.append(error)
                    with patch.object(KG.time, 'sleep'), patch.object(K.time, 'monotonic', return_value=100):
                        thread = threading.Thread(target=arbeit)
                        thread.start()
                        try:
                            self.assertTrue(gestartet.wait(3))
                            with node.lock:
                                lok.bewegen(0.35, 0, 0, zeit=scanzeit)
                                lok.scan(PUNKTE * 2, scanzeit, scan_zeit=scanzeit)
                                if wechsel:
                                    node.kr.lok = K.Lokalisierung(SimpleNamespace(einbau={}))
                        finally:
                            weiter.set()
                            thread.join(3)
                    self.assertFalse(thread.is_alive())
                    self.assertEqual(fehler, [])
                    if wechsel:
                        self.assertIsNone(node.kr.lok.pose)
                        self.assertIsNone(lok.pose)
                        self.assertIsNone(lok.zuletzt_sicher)
                        bel.eintragen.assert_not_called()
                    else:
                        self.assertEqual(lok.zuletzt_sicher, 10 if scanzeit == 10.4 else None)
                        np.testing.assert_allclose(lok.pose, (2.45, 3, 0), atol=1e-12)
                        bel.eintragen.reset_mock()
                        lok.scan(PUNKTE, scanzeit + 0.1)
                        bel.eintragen.assert_not_called()


if __name__ == '__main__':
    unittest.main()
