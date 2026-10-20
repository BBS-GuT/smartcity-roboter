#!/usr/bin/env python3
"""C1 (Issue #14): gemeinsamer Zustandsvertrag. Ohne ROS, Roboter oder Broker.
Prueft die Beispiele in tests/fixtures/grundbetrieb/ mit lib/grundbetrieb_vertrag.py und - falls installiert -
zusaetzlich mit dem JSON-Schema (jsonschema). Aufruf: python3 tests/test_zustandsvertrag.py"""
import copy
import glob
import json
import os
import sys
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, '..', 'lib'))
import grundbetrieb_vertrag as V  # noqa: E402

BEISPIELE = os.path.join(HIER, 'fixtures', 'grundbetrieb')
SCHEMA = os.path.join(HIER, '..', 'schemas', 'grundbetrieb-v1.schema.json')
try:
    import jsonschema
except ImportError:          # auf dem Roboter evtl. nicht installiert: dann nur die eigene Pruefung
    jsonschema = None


def beispiel(name):
    with open(os.path.join(BEISPIELE, name + '.json')) as f:
        return json.load(f)


def schema_fehler(d):
    with open(SCHEMA) as f:
        return [e.message for e in jsonschema.Draft202012Validator(json.load(f)).iter_errors(d)]


class Beispiele(unittest.TestCase):
    def test_alle_beispiele_gueltig(self):
        dateien = sorted(glob.glob(os.path.join(BEISPIELE, '*.json')))
        self.assertGreaterEqual(len(dateien), 7)
        for datei in dateien:
            with open(datei) as f:
                d = json.load(f)
            with self.subTest(datei=os.path.basename(datei)):
                self.assertEqual(V.pruefe(d), [])
                if jsonschema:
                    self.assertEqual(schema_fehler(d), [])

    @unittest.skipIf(jsonschema is None, 'jsonschema nicht installiert')
    def test_schema_selbst_gueltig(self):
        with open(SCHEMA) as f:
            jsonschema.Draft202012Validator.check_schema(json.load(f))

    def test_test_modus_zeigt_fahrwunsch_ohne_motor(self):
        d = beispiel('test')
        self.assertIsNotNone(d['motion']['request'])
        self.assertFalse(d['runtime']['motor_enabled'])
        self.assertEqual(d['motion']['output'], {'v_m_s': 0.0, 'w_rad_s': 0.0})
        self.assertEqual(d['motion']['measured_v_m_s']['status'], 'missing')    # nicht gueltige Null
        d['motion']['output']['v_m_s'] = 0.1
        self.assertTrue(any('R3' in f for f in V.pruefe(d)))

    def test_rot_und_hindernis_gleichzeitig(self):
        d = beispiel('rot_und_hindernis')
        self.assertEqual(d['runtime']['hold_reasons'], ['RED_LIGHT', 'FRONT_BLOCKED'])
        self.assertIsNone(d['obstacles']['objects'][0]['class'])               # gemessen, nicht klassifiziert
        d['runtime']['hold_reasons'] = []
        self.assertTrue(any('R5' in f for f in V.pruefe(d)))

    def test_broker_wiederverbindung(self):
        """Frischer Zustand, sichtbar aeltere bestaetigte Sequenz, STOPP-Sperre unveraendert, keine Motorfreigabe."""
        vorher, nachher = beispiel('broker_unterbrochen'), beispiel('broker_wiederverbunden')
        self.assertEqual(V.vergleiche(vorher, nachher), 'neuer')
        self.assertEqual(nachher['communication']['broker'], 'connected')
        self.assertLess(nachher['communication']['last_broker_ack_seq'], nachher['seq'])
        self.assertEqual(nachher['communication']['reconnects'], vorher['communication']['reconnects'] + 1)
        for d in (vorher, nachher):
            self.assertTrue(d['runtime']['stop_latched'])
            self.assertFalse(d['runtime']['motor_enabled'])
        self.assertEqual(nachher['runtime'], vorher['runtime'])


class Regeln(unittest.TestCase):
    def setUp(self):
        self.d = beispiel('fahrt')

    def ungueltig(self, d, regel=None):
        fehler = V.pruefe(d)
        self.assertTrue(fehler, 'haette ungueltig sein muessen')
        if regel:
            self.assertTrue(any(regel in f for f in fehler), fehler)
        return fehler

    def test_unbekannte_messung_ist_keine_null(self):
        self.d['motion']['measured_v_m_s'] = {'value': 0.0, 'status': 'missing', 'source': None}
        self.ungueltig(self.d, 'R2')
        self.d['motion']['measured_v_m_s'] = {'value': None, 'status': 'valid', 'source': 'odom'}
        self.ungueltig(self.d, 'R2')

    def test_kein_nan_kein_unendlich(self):
        self.d['lane']['offset_m'] = float('nan')
        self.ungueltig(self.d)
        with self.assertRaises(ValueError):
            V.als_json(self.d)
        text = json.dumps(beispiel('fahrt')).replace('"offset_m": 0.004', '"offset_m": NaN')
        with self.assertRaises(ValueError):
            V.lade_json(text)
        text = json.dumps(beispiel('fahrt')).replace('"offset_m": 0.004', '"offset_m": Infinity')
        with self.assertRaises(ValueError):
            V.lade_json(text)

    def test_stopp_sperre(self):
        self.d['runtime']['stop_latched'] = True
        fehler = self.ungueltig(self.d, 'R3')
        self.assertTrue(any('R8' in f for f in fehler))                        # STOP_LATCHED fehlt

    def test_bewegung_nur_mit_freigabe_und_im_fahrzustand(self):
        self.d['runtime']['motor_enabled'] = False
        self.ungueltig(self.d, 'R4')
        d = beispiel('fahrt')
        d['runtime']['state'] = 'BEREIT'
        self.ungueltig(d, 'R4')

    def test_fehler_braucht_sperre_und_grund(self):
        d = beispiel('stillstand')
        d['runtime'].update(state='FEHLER')
        self.ungueltig(d, 'R8')
        d['runtime'].update(fault_latched=True, faults=[])
        self.ungueltig(d, 'R8')
        d['runtime']['faults'] = ['Wenden hat nicht geklappt']
        d['runtime']['hold_reasons'] = ['STOP_LATCHED', 'FAULT']
        self.assertEqual(V.pruefe(d), [])

    def test_kommunikation(self):
        self.d['communication']['last_broker_ack_seq'] = self.d['communication']['last_publish_requested_seq'] + 1
        self.ungueltig(self.d, 'R6')
        d = beispiel('fahrt')
        d['communication']['last_publish_requested_seq'] = d['seq'] + 1
        self.ungueltig(d, 'R6')
        d = beispiel('fahrt')
        d['communication'].update(broker='disconnected', last_error=None)
        self.ungueltig(d)

    def test_sensorquellen(self):
        self.d['sensors']['camera']['age_s'] = None
        self.ungueltig(self.d, 'R7')
        d = beispiel('fahrt')
        d['sensors']['lidar_0'].update(status='stale', reason=None)
        self.ungueltig(d, 'reason')
        d = beispiel('sensor_alt_ungueltig')
        self.assertEqual({q['status'] for q in d['sensors'].values()} >= {'stale', 'missing', 'invalid'}, True)

    def test_route_und_korridor(self):
        self.d['route'].update(allowed_exits=['K1', 'K3'], selected_exit='K5')
        self.ungueltig(self.d, 'R9')
        d = beispiel('rot_und_hindernis')
        d['obstacles']['corridor'] = 'free'
        self.ungueltig(d, 'R10')

    def test_signal(self):
        self.d['traffic'].update(signal='unknown', signal_status='valid')
        self.ungueltig(self.d, 'R11')

    def test_struktur_wie_im_schema(self):
        """Eigene Pruefung und JSON-Schema lehnen dieselben Strukturfehler ab."""
        aenderungen = {
            'Pflichtfeld fehlt': lambda d: d.pop('seq'),
            'unbekanntes Feld': lambda d: d.update(extra=1),
            'falsches Geraet': lambda d: d.update(robot_id='RM05'),
            'Sequenz negativ': lambda d: d.update(seq=-1),
            'Sequenz keine ganze Zahl': lambda d: d.update(seq=1.5),
            'Zeit nicht UTC': lambda d: d.update(generated_at='20.10.2026 10:00'),
            'unbekannter Zustand': lambda d: d['runtime'].update(state='FAEHRT'),
            'unbekannter Haltegrund': lambda d: d['runtime'].update(hold_reasons=['IRGENDWAS']),
            'doppelter Haltegrund': lambda d: d['runtime'].update(hold_reasons=['RED_LIGHT', 'RED_LIGHT']),
            'Status unbekannt': lambda d: d['lane'].update(status='ok'),
            'Quelle unvollstaendig': lambda d: d['sensors']['camera'].pop('frame_id'),
            'keine Sensoren': lambda d: d.update(sensors={}),
            'falsche Schemaversion': lambda d: d.update(schema_version='2.0'),
        }
        for name, aendern in aenderungen.items():
            d = copy.deepcopy(self.d)
            aendern(d)
            with self.subTest(name):
                self.assertTrue(V.pruefe(d), 'eigene Pruefung haette ablehnen muessen')
                if jsonschema:
                    self.assertTrue(schema_fehler(d), 'Schema haette ablehnen muessen')


class StartUndSequenz(unittest.TestCase):
    def test_neustart_ist_keine_fortsetzung(self):
        a = V.Start('RM02')
        self.assertEqual([a.naechste(), a.naechste()], [0, 1])
        b = V.Start('RM02')                          # Neustart
        self.assertNotEqual(a.boot_id, b.boot_id)
        self.assertEqual(b.naechste(), 0)
        alt, neu = beispiel('fahrt'), beispiel('fahrt')
        neu.update(boot_id=b.boot_id, seq=0)
        self.assertEqual(V.vergleiche(alt, neu), 'anderer_start')

    def test_geraete_bleiben_getrennt(self):
        rm1, rm2 = beispiel('fahrt'), beispiel('fahrt')
        rm1['robot_id'] = 'RM01'
        self.assertEqual(V.vergleiche(rm1, rm2), 'anderes_geraet')
        with self.assertRaises(ValueError):
            V.Start('RM07')

    def test_duplikat_und_verspaetet(self):
        a = beispiel('fahrt')
        b = copy.deepcopy(a)
        self.assertEqual(V.vergleiche(a, b), 'gleich')
        b['seq'] -= 1
        self.assertEqual(V.vergleiche(a, b), 'aelter')

    def test_alter_nach_monotoner_uhr(self):
        d = beispiel('fahrt')
        self.assertAlmostEqual(V.alter_s(d, d['generated_mono_s'] + 0.25), 0.25)
        self.assertEqual(V.alter_s(d, d['generated_mono_s'] - 5), 0.0)

    def test_panel_und_mqtt_lesen_dasselbe(self):
        """Gleiches Objekt -> byte-gleiches JSON; Lesen ergibt wieder dasselbe Objekt."""
        d = beispiel('rot_und_hindernis')
        text = V.als_json(d)
        self.assertEqual(text, V.als_json(copy.deepcopy(d)))
        self.assertEqual(V.lade_json(text), d)


if __name__ == '__main__':
    unittest.main(verbosity=1)
