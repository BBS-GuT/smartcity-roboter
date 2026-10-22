#!/usr/bin/env python3
"""Routenabgleich ohne Broker oder Roboter pruefen."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import robot_communication as rc  # noqa: E402


class FakeClient:
    def __init__(self):
        self.subscriptions = []
        self.publications = []

    def subscribe(self, topic):
        self.subscriptions.append(topic)

    def publish(self, topic, payload):
        self.publications.append((topic, json.loads(payload)))
        return self.publications[-1]


class RoutenKoordinator(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.koordinator = rc.StreckenKoordinator('RM02', 'broker', client=self.client)
        self.koordinator.on_connect(self.client, None, None, 0, None)
        self.koordinator.setze_eigene_route(['K1', 'K2'], timestamp=10.0)

    def test_erzeugung_und_import_verbinden_nicht(self):
        koordinator = rc.StreckenKoordinator('RM02')
        self.assertIsNone(koordinator.client)
        with self.assertRaisesRegex(RuntimeError, 'SMARTCITY_MQTT_BROKER_HOST'):
            koordinator.starte()

    def test_paho_start_konfiguriert_client_ohne_echten_broker(self):
        koordinator = rc.StreckenKoordinator('RM02', 'broker-test', 1884)
        with patch('paho.mqtt.client.Client') as client_factory:
            koordinator.starte()
        client_factory.assert_called_once()
        koordinator.client.connect.assert_called_once_with('broker-test', 1884, 60)
        koordinator.client.loop_start.assert_called_once_with()

    def test_fremder_vorrang_blockiert_bis_konflikt_weg(self):
        fremd = {'robot_id': 'RM01', 'pfad': ['K2', 'K3'], 'timestamp': 9.0}
        self.assertEqual(self.koordinator.verarbeite_nachricht(fremd), 'warten')
        self.assertFalse(self.koordinator.warte_auf_freigabe(0))
        fremd['pfad'] = ['K3', 'K4']
        self.assertEqual(self.koordinator.verarbeite_nachricht(fremd), 'frei')
        self.assertTrue(self.koordinator.warte_auf_freigabe(0))

    def test_gleichstand_nach_robot_id(self):
        self.assertEqual(self.koordinator.verarbeite_nachricht(
            {'robot_id': 'RM01', 'pfad': ['K2'], 'timestamp': 10.0}), 'warten')
        eigener_vorrang = rc.StreckenKoordinator('RM01', 'broker', client=FakeClient())
        eigener_vorrang.on_connect(eigener_vorrang.client, None, None, 0, None)
        eigener_vorrang.setze_eigene_route(['K1', 'K2'], timestamp=10.0)
        self.assertEqual(eigener_vorrang.verarbeite_nachricht(
            {'robot_id': 'RM02', 'pfad': ['K2'], 'timestamp': 10.0}), 'vorrang')
        self.assertTrue(eigener_vorrang.warte_auf_freigabe(0))

    def test_veroeffentlichter_pfad_wird_fuer_vergleiche_verwendet(self):
        self.koordinator.sende_strecken_daten('Station_B', ['K5', 'K6'])
        self.assertEqual(self.koordinator.eigner_pfad, ['K5', 'K6'])
        self.assertEqual(self.client.publications[0][0], 'smartcity/robots/RM02/strecke')
        self.assertEqual(self.client.publications[0][1]['pfad'], ['K5', 'K6'])

    def test_route_aenderung_bewertet_konflikt_neu(self):
        self.assertEqual(self.koordinator.verarbeite_nachricht(
            {'robot_id': 'RM01', 'pfad': ['K2'], 'timestamp': 9.0}), 'warten')
        self.koordinator.setze_eigene_route(['K4', 'K5'], timestamp=11.0)
        self.assertTrue(self.koordinator.warte_auf_freigabe(0))

    def test_ungueltige_nachricht_aendert_freigabe_nicht(self):
        self.assertEqual(self.koordinator.verarbeite_nachricht(
            {'robot_id': 'RM01', 'pfad': ['K2'], 'timestamp': 'alt'}), 'ungueltig')
        self.assertTrue(self.koordinator.warte_auf_freigabe(0))

    def test_verbindungsausfall_sperrt_freigabe(self):
        self.koordinator.on_disconnect(self.client, None, None, 1, None)
        self.assertFalse(self.koordinator.warte_auf_freigabe(0))


if __name__ == '__main__':
    unittest.main(verbosity=2)