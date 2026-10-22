#!/usr/bin/env python3
"""C1c (#13): monotone Empfangszeit je Quelle, ohne ROS oder Broker.

Aufruf: python tests/test_c1_empfangszeit.py
Die Zeiten sind synthetisch auf einer gemeinsamen lokalen monotonen Uhr.
Keine Ableitung aus UTC oder aus dem Aufnahmealter.
"""
import json
from decimal import Decimal
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
import grundbetrieb_vertrag as V  # noqa: E402
from c1_testbauwerte import lade_isoliertes_beispiel

try:
    import jsonschema
except ImportError:
    jsonschema = None

FIELD = 'received_mono_s'
PATH = '$.sensors.camera.' + FIELD


def beispiel():
    with (ROOT / 'tests/fixtures/grundbetrieb/fahrt.json').open(encoding='utf-8') as f:
        d = lade_isoliertes_beispiel(f.read())
    # Eigene Testeingabe, unabhaengig von der spaeteren Fixture-Ergaenzung.
    # Ein Empfang 0.005 s vor Erzeugung ist hier ausdruecklich synthetisch gesetzt.
    for q in d['sensors'].values():
        q[FIELD] = None if q['status'] == 'missing' else d['generated_mono_s'] - Decimal('0.005')
    return d


class Empfangszeit(unittest.TestCase):
    def assert_gueltig(self, d):
        self.assertEqual(V.pruefe(d), [])
        self.assertEqual(V.lade_json(V.als_json(d)), d)

    def assert_empfangsfehler(self, d):
        errors = V.pruefe(d)
        self.assertTrue(any(e.startswith(PATH + ':') for e in errors), errors)
        with self.assertRaises(ValueError):
            V.als_json(d)
        with self.assertRaises(ValueError):
            V.lade_json(V._json_wert(d))

    def test_positive_kontrolle_und_json_roundtrip(self):
        self.assert_gueltig(beispiel())

    def test_empfang_nullpunkt_ganzzahl_und_erzeugungsgrenze(self):
        for t in (0, Decimal('0.0'), 1, Decimal('1.25'), beispiel()['generated_mono_s']):
            with self.subTest(zeit=t):
                d = beispiel()
                d['sensors']['camera'].update(captured_mono_s=0, age_s=d['generated_mono_s'])
                d['sensors']['camera'][FIELD] = t
                self.assert_gueltig(d)

    def test_pflichtschluessel_fehlt(self):
        d = beispiel()
        del d['sensors']['camera'][FIELD]
        self.assert_empfangsfehler(d)

    def test_valid_braucht_empfang(self):
        d = beispiel()
        d['sensors']['camera'][FIELD] = None
        self.assert_empfangsfehler(d)

    def test_missing_hat_null(self):
        d = beispiel()
        d['sensors']['camera'].update(status='missing', reason='synthetisch nie empfangen',
                                     captured_at_s=None, captured_mono_s=None, age_s=None, received_mono_s=None)
        self.assert_gueltig(d)
        d['sensors']['camera'][FIELD] = 0
        self.assert_empfangsfehler(d)

    def test_nicht_valid_darf_frueheren_empfang_behalten_oder_null_fuehren(self):
        for status in ('stale', 'invalid', 'unknown'):
            for t in (None, 0, Decimal('1.25')):
                with self.subTest(status=status, zeit=t):
                    d = beispiel()
                    d['sensors']['camera'].update(status=status, reason='synthetische Kontrolle')
                    d['sensors']['camera'].update(captured_mono_s=0, age_s=d['generated_mono_s'])
                    d['sensors']['camera'][FIELD] = t
                    self.assert_gueltig(d)

    def test_ungueltige_zahlen_und_typen_bei_jedem_status(self):
        for status in V.STATUS:
            for t in (True, False, -1, -0.25, float('nan'), float('inf'), float('-inf'),
                      '1.0', [], {}):
                with self.subTest(status=status, zeit=repr(t)):
                    d = beispiel()
                    q = d['sensors']['camera']
                    q.update(status=status, reason=None if status == 'valid' else 'synthetisch')
                    if status == 'missing':
                        q.update(captured_at_s=None, age_s=None)
                    q[FIELD] = t
                    self.assert_empfangsfehler(d)

    def test_zukunft_bei_jedem_status(self):
        for status in V.STATUS:
            with self.subTest(status=status):
                d = beispiel()
                q = d['sensors']['camera']
                q.update(status=status, reason=None if status == 'valid' else 'synthetisch')
                if status == 'missing':
                    q.update(captured_at_s=None, age_s=None)
                q[FIELD] = d['generated_mono_s'] + Decimal('0.125')
                self.assert_empfangsfehler(d)

    def test_empfang_ist_unabhaengig_von_utc_und_aufnahmealter(self):
        d = beispiel()
        d.update(generated_at='2026-10-22T00:00:00Z')
        d['sensors']['camera'].update(captured_at_s=1, captured_mono_s=d['generated_mono_s'] - 99, age_s=99, received_mono_s=d['generated_mono_s'] - 1)
        self.assert_gueltig(d)

    def test_ungueltige_erzeugung_liefert_fehler_statt_absturz(self):
        for t in (None, True, '1200', [], {}, float('nan'), float('inf'), -1):
            with self.subTest(zeit=repr(t)):
                d = beispiel()
                d['generated_mono_s'] = t
                self.assertTrue(V.pruefe(d))

    def test_alle_synthetischen_fixtures_mit_pflichtfeld(self):
        files = sorted((ROOT / 'tests/fixtures/grundbetrieb').glob('*.json'))
        self.assertEqual(len(files), 7)
        for file in files:
            with self.subTest(datei=file.name):
                with file.open(encoding='utf-8') as f:
                    d = lade_isoliertes_beispiel(f.read())
                for q in d['sensors'].values():
                    self.assertIn(FIELD, q)
                self.assert_gueltig(d)

    @unittest.skipIf(jsonschema is None, 'jsonschema nicht installiert')
    def test_schema_struktur_positive_und_negative_kontrollen(self):
        with (ROOT / 'schemas/grundbetrieb-v2.schema.json').open(encoding='utf-8') as f:
            schema = json.load(f)
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
        self.assertEqual(list(validator.iter_errors(beispiel())), [])
        d = beispiel()
        del d['sensors']['camera'][FIELD]
        self.assertTrue(list(validator.iter_errors(d)))
        for t in (True, False, -1, '1.0', [], {}):
            with self.subTest(zeit=repr(t)):
                d = beispiel()
                d['sensors']['camera'][FIELD] = t
                self.assertTrue(list(validator.iter_errors(d)))
        d = beispiel()
        d['sensors']['camera'].update(status='missing', reason='synthetisch',
                                     captured_at_s=None, captured_mono_s=None, age_s=None, received_mono_s=None)
        self.assertEqual(list(validator.iter_errors(d)), [])
        # Endlichkeit, Statusbezug und Vergleich mit generated_mono_s prueft Python;
        # das JSON-Schema beschreibt die Struktur fuer externe Leser.


if __name__ == '__main__':
    unittest.main(verbosity=2)
