#!/usr/bin/env python3
"""Issue #19: "Neue Karte" im Kartografen - mit ROS-Attrappen, ohne Roboter, nur in temporaeren Ordnern.
Aufruf: python3 tests/test_kartenwechsel.py"""
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, 'attrappen'))
sys.path.insert(0, os.path.join(HIER, '..', 'kartograf'))
from rclpy.node import Node  # noqa: E402  (Attrappe)
import kartograf as KG       # noqa: E402

_deklarieren = Node.declare_parameter


def kartograf(ordner, **param):
    """Kartograf, dessen Karten in <ordner>/test liegen."""
    werte = dict({'ordner': ordner, 'karte': 'test'}, **param)
    with patch.object(Node, 'declare_parameter', lambda self, n, v: _deklarieren(self, n, werte.get(n, v))):
        return KG.Kartograf()


def gesichert(ordner):
    return sorted(d for d in os.listdir(ordner) if d.startswith('test_alt_'))


class Kartenwechsel(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.ordner)

    def test_ungelernter_einbau_speichern_neu_und_neustart(self):
        k = kartograf(self.ordner)
        self.assertFalse(k.kr.kal.einbau_gelernt)
        k._speichern()                                  # schreibt 'einbau': None
        erg = k.neue_karte('a1')
        self.assertTrue(erg['ok'], erg)
        k._speichern()
        k2 = kartograf(self.ordner)                     # Neustart mit gespeicherter Karte: kein Absturz
        self.assertEqual(k2.kr.kal.einbau, (0.0, 0.0, 0.0))

    def test_neue_karte_setzt_kalibrierung_zurueck(self):
        k = kartograf(self.ordner)
        k.kr.kal.einbau, k.kr.kal.einbau_gelernt, k.kr.kal.odom_skala = (0.1, -0.02, 0.05), True, 1.07
        self.assertTrue(k.neue_karte('a2')['ok'])
        self.assertEqual(k.kr.kal.einbau, (0.0, 0.0, 0.0))
        self.assertFalse(k.kr.kal.einbau_gelernt)
        self.assertEqual(k.kr.kal.odom_skala, 1.0)

    def test_gespeicherte_kalibrierung_nur_wenn_eingeschaltet(self):
        k = kartograf(self.ordner)
        k.kr.kal.imu_vorzeichen, k.kr.kal.spiegeln, k.kr.kal.imu_skala = -1.0, True, 1.3
        k._speichern()
        self.assertFalse(kartograf(self.ordner).kr.kal.spiegeln)          # Standard: aus -> Rohwerte
        self.assertEqual(kartograf(self.ordner).kr.kal.imu_vorzeichen, 1.0)
        k2 = kartograf(self.ordner, selbst_kalibrieren=True)
        self.assertTrue(k2.kr.kal.spiegeln)
        self.assertEqual(k2.kr.kal.imu_vorzeichen, -1.0)

    def test_sicherung_hat_aktuellen_stand(self):
        k = kartograf(self.ordner)
        k._speichern()
        k.karte.fahrten = 99                            # nach dem letzten Autosave dazugekommen
        erg = k.neue_karte('a3')
        self.assertTrue(erg['ok'])
        alt = KG.K.Karte(os.path.join(self.ordner, erg['sicherung']))
        self.assertTrue(alt.laden())
        self.assertEqual(alt.fahrten, 99)
        self.assertEqual(k.karte.fahrten, 0)
        self.assertIs(k.kr.karte, k.karte)

    def test_zwei_schnelle_anfragen_eindeutig(self):
        k = kartograf(self.ordner)
        with patch.object(KG.time, 'strftime', return_value='_alt_20261020_101010'):
            self.assertTrue(k.neue_karte('b1')['ok'])
            self.assertTrue(k.neue_karte('b2')['ok'])
        alte = gesichert(self.ordner)
        self.assertEqual(len(alte), 2, alte)
        for d in alte:     # keine verschachtelte Sicherung
            self.assertFalse(any(x.startswith('test_alt_') for x in os.listdir(os.path.join(self.ordner, d))))

    def test_fehler_vor_dem_sichern_laesst_alles_wie_es_war(self):
        k = kartograf(self.ordner)
        k.karte.fahrten = 5
        karte, kr = k.karte, k.kr
        with patch.object(KG.KR, 'Kartierer', side_effect=RuntimeError('kaputt')):
            erg = k.neue_karte('c1')
        self.assertFalse(erg['ok'])
        self.assertIn('kaputt', erg['text'])
        self.assertIs(k.karte, karte)
        self.assertIs(k.kr, kr)
        self.assertIs(k.kr.karte, k.karte)
        self.assertEqual(gesichert(self.ordner), [])

    def test_fehler_beim_verschieben_laesst_alte_karte_aktiv(self):
        k = kartograf(self.ordner)
        k.karte.fahrten = 7
        karte = k.karte
        with patch.object(KG.shutil, 'move', side_effect=OSError('keine Rechte')):
            erg = k.neue_karte('c2')
        self.assertFalse(erg['ok'])
        self.assertIsNone(erg['sicherung'])
        self.assertIs(k.karte, karte)
        self.assertIs(k.kr.karte, k.karte)
        alt = KG.K.Karte(k.ordner)                     # alter Ordner ist noch da, mit aktuellem Stand
        self.assertTrue(alt.laden())
        self.assertEqual(alt.fahrten, 7)

    def test_bestaetigung_gehoert_zum_auftrag(self):
        k = kartograf(self.ordner)
        self.assertIsNone(k.karte_neu)                 # nur gestartet: keine Bestaetigung
        k._kommando(KG.String(data='neu:xyz'))
        self.assertEqual(k.karte_neu['auftrag'], 'xyz')
        self.assertTrue(k.karte_neu['ok'])
        k2 = kartograf(self.ordner)                    # Neustart: alte Bestaetigung ist nicht mehr da
        self.assertIsNone(k2.karte_neu)


if __name__ == '__main__':
    unittest.main(verbosity=2)
