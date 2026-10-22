#!/usr/bin/env python3
"""C1i: synthetische Identitaets-/Uhrfaelle, keine physische Uhrbestaetigung."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
import grundbetrieb_vertrag as V
try:
    import jsonschema
except ImportError:
    jsonschema = None


def beispiel():
    return V.lade_json((ROOT / 'tests/fixtures/grundbetrieb/fahrt.json').read_text(encoding='utf-8'))


class IdentitaetUndUhr(unittest.TestCase):
    def setUp(self):
        self.d = beispiel()
        self.q = self.d['sensors']['camera']

    def abgelehnt(self, pfad):
        fehler = V.pruefe(self.d)
        self.assertTrue(any(pfad in f for f in fehler), fehler)
        with self.assertRaises(ValueError):
            V.als_json(self.d)
        with self.assertRaises(ValueError):
            V.lade_json(V._json_wert(self.d))

    def test_c_neustart_bewahrt_aufnahme_und_sensorstart(self):
        vorher = copy.deepcopy(self.d['sensors'])
        self.d.update(boot_id='synthetic-new-c-start', seq=0)
        self.d['communication'].update(last_publish_requested_seq=None, last_broker_ack_seq=None,
                                      last_broker_ack_mono_s=None)
        self.assertEqual(V.pruefe(self.d), [])
        self.assertEqual(V.lade_json(V.als_json(self.d))['sensors'], vorher)
        self.assertNotEqual(self.q['producer_boot_id'], self.d['boot_id'])
        self.assertNotEqual(self.q['time_basis_id'], self.d['boot_id'])

    def test_sensorneustart_aendert_nicht_c_oder_uhr(self):
        boot, basis = self.d['boot_id'], self.d['time_basis_id']
        self.q.update(producer_boot_id='synthetic-new-sensor-start', frame_id='first-frame')
        self.assertEqual(V.pruefe(self.d), [])
        self.assertEqual((self.d['boot_id'], self.q['time_basis_id']), (boot, basis))

    def test_valid_braucht_vollstaendige_identitaet(self):
        original = copy.deepcopy(self.q)
        for key in ('producer_id', 'producer_boot_id', 'time_basis_id'):
            for wert in (None, '', False, 0):
                with self.subTest(key=key, wert=wert):
                    self.q.update(original)
                    self.q[key] = wert
                    self.abgelehnt(key)
            self.q.update(original)
            del self.q[key]
            self.abgelehnt(key)
            self.q.update(original)

    def test_kopfzeitbasis_pflicht(self):
        for wert in (None, '', False, 0):
            self.d['time_basis_id'] = wert
            self.abgelehnt('time_basis_id')
        del self.d['time_basis_id']
        self.abgelehnt('time_basis_id')

    def test_fremde_oder_fehlende_aufnahmeuhr_nicht_frisch(self):
        for basis in ('synthetic-foreign-clock', None):
            with self.subTest(basis=basis):
                self.q.update(time_basis_id=basis, status='valid')
                self.abgelehnt('time_basis_id')
                self.q.update(status='invalid' if basis else 'unknown', reason='Uhr nicht belegt', age_s=None)
                self.assertEqual(V.pruefe(self.d), [])
                self.q['age_s'] = 0
                self.abgelehnt('age_s')
                self.q['age_s'] = Decimal('0.08')

    def test_unbekannte_herkunft_ehrlich_null_bekannte_bleibt(self):
        self.q.update(status='missing', reason='nie empfangen', producer_id=None,
                      producer_boot_id=None, time_basis_id=None, captured_at_s=None,
                      captured_mono_s=None, received_mono_s=None, age_s=None)
        self.assertEqual(V.pruefe(self.d), [])
        self.q.update(producer_id='known-producer', producer_boot_id='known-start',
                      time_basis_id=self.d['time_basis_id'])
        self.assertEqual(V.pruefe(self.d), [])
        self.assertEqual(V.lade_json(V.als_json(self.d))['sensors']['camera']['producer_id'], 'known-producer')

    def test_aufnahme_empfang_erzeugung_und_exaktes_alter(self):
        gen = V.zeit_ns(self.d['generated_mono_s'])
        self.q.update(captured_mono_s=V.sekunden_aus_ns(gen-200000000),
                      received_mono_s=self.d['generated_mono_s'], age_s=Decimal('0.20'))
        self.assertEqual(V.pruefe(self.d), [])
        original = copy.deepcopy(self.q)
        for key, wert in (('captured_mono_s', V.sekunden_aus_ns(gen+1)),
                          ('received_mono_s', V.sekunden_aus_ns(gen+1)),
                          ('received_mono_s', V.sekunden_aus_ns(gen-200000001)),
                          ('age_s', Decimal('0.199999999')),
                          ('age_s', Decimal('0.200000001'))):
            self.q.update(original)
            self.q[key] = wert
            self.abgelehnt('sensors.camera')

    def test_wiederempfang_erneuert_keine_aufnahme(self):
        original = copy.deepcopy(self.q)
        self.q['received_mono_s'] = self.d['generated_mono_s']
        self.assertEqual(V.pruefe(self.d), [])
        self.assertEqual(self.q['age_s'], original['age_s'])
        self.q['age_s'] = 0
        self.abgelehnt('age_s')

    def test_alias_bleibt_unzulaessig(self):
        self.d['motion']['measured_w_rad_s']['source'] = self.d['sensors']['imu']['source_id']
        self.abgelehnt('source')

    def test_aktive_versionen_ohne_schemaabhaengigkeit(self):
        for version in ('1.0', 'unknown', '3.0', None, True):
            self.d['schema_version'] = version
            self.abgelehnt('schema_version')

    @unittest.skipIf(jsonschema is None, 'jsonschema nicht installiert')
    def test_version_und_historisches_schema(self):
        schema = json.loads((ROOT / 'schemas/grundbetrieb-v2.schema.json').read_text(), parse_float=Decimal)
        validator = jsonschema.Draft202012Validator(schema)
        self.assertEqual(list(validator.iter_errors(self.d)), [])
        for version in ('1.0', 'unknown', '3.0', None, True):
            self.d['schema_version'] = version
            self.abgelehnt('schema_version')
            self.assertTrue(list(validator.iter_errors(self.d)))
        alt = json.loads((ROOT / 'schemas/grundbetrieb-v1.schema.json').read_text())
        self.assertEqual(alt['properties']['schema_version']['const'], '1.0')
        self.assertNotIn('received_mono_s', alt['$defs']['quelle']['properties'])
        self.assertNotIn('received_mono_s', alt['$defs']['quelle']['required'])

    @unittest.skipIf(jsonschema is None, 'jsonschema nicht installiert')
    def test_schema_neue_pflichtschluessel_und_typen(self):
        schema = json.loads((ROOT / 'schemas/grundbetrieb-v2.schema.json').read_text(), parse_float=Decimal)
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
        for key in ('producer_id', 'producer_boot_id', 'time_basis_id', 'captured_mono_s'):
            for wert in ('fehlt', False, []):
                d = beispiel()
                if wert == 'fehlt':
                    del d['sensors']['camera'][key]
                else:
                    d['sensors']['camera'][key] = wert
                with self.subTest(key=key, wert=wert):
                    self.assertTrue(list(validator.iter_errors(d)))
        d = beispiel()
        del d['time_basis_id']
        self.assertTrue(list(validator.iter_errors(d)))


if __name__ == '__main__':
    unittest.main(verbosity=2)
