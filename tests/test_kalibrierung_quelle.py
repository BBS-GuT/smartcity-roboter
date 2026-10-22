#!/usr/bin/env python3
"""Quellbindung mit synthetischen Werten und echtem Kartograf-Speicherpfad."""
import os
import sys
import tempfile
import unittest
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from test_kartenwechsel import kartograf


class Kalibrierungsquelle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def node(self, quelle='/scan0', an=True, **cfg):
        return kartograf(self.tmp.name, selbst_kalibrieren=an,
                         haupt_lidar=quelle, **cfg)

    def gelernt(self):
        k = self.node()
        k.kr.kal.einbau = (0.2, 0.0, 0.0)
        k.kr.kal.einbau_gelernt = True
        k.kr.kal.spiegeln = True
        k.kr.kal.imu_skala = 1.1
        k.kr.kal.odom_skala = 1.2
        k._speichern()
        return k

    def test_gleiche_quelle_aus_speichern_ein(self):
        k = self.gelernt()
        erwartet = k.karte.kalibrierung
        self.assertEqual(erwartet.get('lidar_quelle'), '/scan0')
        aus = self.node(an=False)
        self.assertFalse(aus.kr.kal.spiegeln)
        aus._speichern()
        ein = self.node()
        self.assertEqual(ein.kr.kal.speichern(), erwartet)
        ein.kr.lok.pose = (1.0, 2.0, 0.0)
        self.assertEqual(ein.kr.roboter_pose_bei(), (0.8, 2.0, 0.0))

    def test_wechsel_pose_spiegelung_und_diagnose(self):
        self.gelernt()
        k = self.node('/scan1')
        k.kr.lok.pose = (1.0, 2.0, 0.0)
        self.assertEqual(k.kr.roboter_pose_bei(), (1.0, 2.0, 0.0))
        self.assertFalse(k.kr.kal.spiegeln)
        self.assertEqual(k.kr.kal.imu_skala, 1.1)
        self.assertEqual(k.kr.kal.odom_skala, 1.2)
        self.assertTrue(any('/scan0' in w and '/scan1' in w for w in k.kr.warnungen()))

    def test_wechsel_aus_roundtrip_etikettiert_nicht_um(self):
        vorher = self.gelernt().karte.kalibrierung
        self.node('/scan1', an=False)._speichern()
        self.assertEqual(self.node().kr.kal.speichern(), vorher)
        fremd = self.node('/scan1')
        fremd._speichern()
        self.assertEqual(self.node().kr.kal.speichern(), vorher)

    def test_legacy_ohne_herkunft_bleibt_erhalten_aber_unangewendet(self):
        k = self.gelernt()
        k.karte.kalibrierung.pop('lidar_quelle', None)
        k.karte.speichern()
        for an in (False, True):
            neu = self.node('/scan1', an=an)
            self.assertFalse(neu.kr.kal.einbau_gelernt)
            self.assertFalse(neu.kr.kal.spiegeln)
            if an:
                self.assertTrue(any('Herkunft' in w for w in neu.kr.warnungen()))
            neu._speichern()
            self.assertIsNone(neu.karte.kalibrierung.get('lidar_quelle'))
            self.assertEqual(neu.karte.kalibrierung['einbau'], [0.2, 0.0, 0.0])

    def test_hauptwahl_und_listenparameter_bleiben_zugeordnet(self):
        self.gelernt()
        for haupt, erwartet in (('/scan1', '/scan1'), ('unbekannt', '/scan0')):
            k = self.node(haupt, scan_topics=['/scan0', '/scan1'],
                          scan_front_deg=[10.0, 20.0], scan_spiegeln=[True, False])
            self.assertEqual(k.kr.haupt, erwartet)
            self.assertEqual(k.kr.namen, ['/scan0', '/scan1'])
            self.assertEqual(k.kr.c['scan_front_deg'], [10.0, 20.0])
            self.assertEqual(k.kr.c['scan_spiegeln'], [True, False])
            self.assertEqual(k.kr.kal.einbau_gelernt, erwartet == '/scan0')

    def test_gelernte_spiegelung_gilt_nur_fuer_hauptquelle(self):
        self.gelernt()
        k = self.node()
        d = {'stamp': 10.0, 'amin': 0.5, 'ainc': 0.01, 'r': [1.0] * 10}
        k.kr.scan(10.0, '/scan1', d)
        self.assertGreater(k.kr.scans['/scan1'][-1][1][0, 1], 0.0)
        # Listenbezogene Konfiguration bleibt zusaetzlich wirksam.
        k.kr.c['scan_spiegeln'] = [False, True]
        k.kr.scan(10.1, '/scan1', dict(d, stamp=10.1))
        self.assertLess(k.kr.scans['/scan1'][-1][1][0, 1], 0.0)

    def test_neu_gelernt_nach_wechsel_bekommt_tatsaechliche_quelle(self):
        self.gelernt()
        k = self.node('/scan1')
        # Synthetisches Ergebnis einer neuen Einbauschaetzung, kein Messnachweis.
        k.kr.kal.einbau, k.kr.kal.einbau_gelernt = (0.1, 0.0, 0.0), True
        self.assertFalse(any('passt nicht zu Hauptquelle' in w for w in k.kr.warnungen()))
        k._speichern()
        self.assertEqual(k.karte.kalibrierung['lidar_quelle'], '/scan1')
        neu = self.node('/scan1')
        np.testing.assert_allclose(neu.kr.kal.einbau, (0.1, 0.0, 0.0))
        self.assertFalse(neu.kr.kal.spiegeln)

    def test_ohne_gelernte_lidarwerte_keine_erfundene_herkunft(self):
        k = self.node()
        k._speichern()
        self.assertIsNone(k.karte.kalibrierung['lidar_quelle'])
        self.assertFalse(k.kr.kal.einbau_gelernt)

    def test_nur_spiegelung_ist_ebenfalls_quellgebunden(self):
        k = self.node()
        k.kr.kal.spiegeln = True
        k._speichern()
        self.assertTrue(self.node().kr.kal.spiegeln)

    def test_neue_spiegelung_entfernt_alten_herkunftshinweis(self):
        self.gelernt()
        k = self.node('/scan1')
        self.assertTrue(any('passt nicht zu Hauptquelle' in w for w in k.kr.warnungen()))
        k.kr.kal.spiegeln = True
        self.assertFalse(any('passt nicht zu Hauptquelle' in w for w in k.kr.warnungen()))
        fremd = self.node('/scan1')
        self.assertFalse(fremd.kr.kal.spiegeln)
        fremd._speichern()
        self.assertTrue(self.node().kr.kal.spiegeln)


if __name__ == '__main__':
    unittest.main(verbosity=2)
