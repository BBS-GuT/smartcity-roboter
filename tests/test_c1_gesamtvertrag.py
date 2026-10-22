"""Gemeinsame synthetische Annahmeprobe aller C1-Teile, keine Geraeteabnahme."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
import grundbetrieb_vertrag as V
from c1_testbauwerte import neutralisiere, synthetischer_raeumkontext
try:
    import jsonschema
except ImportError:
    jsonschema = None


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'), parse_float=Decimal)


class Gesamtvertrag(unittest.TestCase):
    def setUp(self):
        self.context = synthetischer_raeumkontext()
        self.schema = read('schemas/grundbetrieb-v2.schema.json')

    def test_sieben_beispiele_alle_oeffentlichen_eingaenge(self):
        for path in sorted((ROOT / 'tests/fixtures/grundbetrieb').glob('*.json')):
            with self.subTest(name=path.name):
                d = V.lade_json(path.read_text(encoding='utf-8'), raeum_kontext=self.context)
                original = copy.deepcopy(d)
                self.assertEqual(V.pruefe(d, raeum_kontext=self.context), [])
                text = V.als_json(d, raeum_kontext=self.context)
                self.assertEqual(V.lade_json(text, raeum_kontext=self.context), d)
                self.assertEqual(d, original)

    def test_fahrende_ausgabe_braucht_expliziten_annahmekontext(self):
        d = read('tests/fixtures/grundbetrieb/fahrt.json')
        self.assertEqual(V.pruefe(d, raeum_kontext=self.context), [])
        self.assertTrue(V.pruefe(d))
        with self.assertRaises(ValueError):
            V.als_json(d)
        with self.assertRaises(ValueError):
            V.lade_json(V._json_wert(d))
        wrong = V.RaeumKontext(bindings=self.context.bindings, requests=self.context.requests)
        self.assertTrue(V.pruefe(d, raeum_kontext=wrong))

    def test_unbekannt_bleibt_ohne_erfundene_pakete_darstellbar(self):
        d = neutralisiere(read('tests/fixtures/grundbetrieb/stillstand.json'))
        self.assertEqual(V.pruefe(d), [])
        self.assertIsNone(d['motion']['output'])
        self.assertIsNone(d['runtime']['stop_latched'])
        self.assertEqual(V.lade_json(V.als_json(d)), d)

    def test_historienkontext_wird_durch_python_und_json_weitergereicht(self):
        d = neutralisiere(read('tests/fixtures/grundbetrieb/stillstand.json'))
        h = read('tests/fixtures/c1_history/two.json')
        context = read('tests/fixtures/c1_history/context.json')
        # Explizite, synthetische gemeinsame Testbindung, kein Kandidatenregister.
        clock = 'synthetic-device-clock-0001'
        h['time_basis_id'] = clock
        context['binding']['time_basis_id'] = clock
        context['binding']['robot_id'] = 'RM02'
        context['map']['map_version'] = 'smartcity-v1'
        d['route']['history'] = h
        self.assertTrue(V.pruefe(d))
        self.assertEqual(V.pruefe(d, historie_kontext=context), [])
        text = V.als_json(d, historie_kontext=context)
        self.assertEqual(V.lade_json(text, historie_kontext=context), d)
        with self.assertRaises(ValueError):
            V.lade_json(text)

    def test_vier_raeumfaelle_auch_als_vollstaendiger_zustand(self):
        clock = 'synthetic-device-clock-0001'
        context = V.RaeumKontext(bindings={'clearing': dict(robot_id='RM02',
            producer_id='b', producer_boot_id='b-start', time_basis_id=clock)})
        for path in sorted((ROOT / 'tests/fixtures/c1_clearing').glob('*.json')):
            with self.subTest(name=path.name):
                partial = json.loads(path.read_text(), parse_float=Decimal)
                d = neutralisiere(read('tests/fixtures/grundbetrieb/stillstand.json'))
                d['clearing'] = partial['clearing']
                d['clearing']['time_basis_id'] = clock
                self.assertEqual(V.pruefe(d, raeum_kontext=context), [])
                text = V.als_json(d, raeum_kontext=context)
                self.assertEqual(V.lade_json(text, raeum_kontext=context), d)
                self.assertTrue(V.pruefe(d))

    def test_doppelte_jsonfelder_werden_auch_eingebettet_abgelehnt(self):
        d = neutralisiere(read('tests/fixtures/grundbetrieb/test.json'))
        text = V.als_json(d)
        for modified in (text.replace('"request_seq":42', '"request_seq":42,"request_seq":99'),
                         text.replace('"schema_version":"2.0"', '"schema_version":"2.0","schema_version":"1.0"')):
            self.assertNotEqual(modified, text)
            with self.assertRaisesRegex(ValueError, 'doppeltes JSON-Feld'):
                V.lade_json(modified)

    @unittest.skipIf(jsonschema is None, 'jsonschema nicht installiert')
    def test_schema_und_nanosekundenobergrenze_der_details(self):
        validator = jsonschema.Draft202012Validator(self.schema)
        for path in (ROOT / 'tests/fixtures/grundbetrieb').glob('*.json'):
            self.assertEqual(list(validator.iter_errors(json.loads(path.read_text(), parse_float=Decimal))), [])
        for field in ('captured_mono_s', 'received_mono_s', 'age_s'):
            prop = self.schema['$defs']['detailreferenz']['properties'][field]
            v = jsonschema.Draft202012Validator(prop)
            self.assertTrue(v.is_valid(Decimal('9223372036.854775807')))
            self.assertFalse(v.is_valid(Decimal('9223372036.854775808')))


if __name__ == '__main__':
    unittest.main()
