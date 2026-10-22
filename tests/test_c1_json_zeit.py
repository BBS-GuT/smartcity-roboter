#!/usr/bin/env python3
"""C1i: oeffentlicher exakter Standardbibliothekpfad; synthetische ns-Grenzen."""
from decimal import Decimal, localcontext, Inexact, Rounded
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
import grundbetrieb_vertrag as V
from c1_testbauwerte import lade_isoliertes_beispiel


def beispiel():
    return lade_isoliertes_beispiel((ROOT / 'tests/fixtures/grundbetrieb/fahrt.json').read_text(encoding='utf-8'))


class ExakterZeitpfad(unittest.TestCase):
    def test_sekunden_ns_und_kontextunabhaengigkeit(self):
        d = beispiel()
        with localcontext() as ctx:
            ctx.prec = 2
            ctx.traps[Inexact] = ctx.traps[Rounded] = True
            for ns in (0, 1, 199999999, 200000000, 200000001, 2**63-1):
                self.assertEqual(V.zeit_ns(V.sekunden_aus_ns(ns)), ns)
            self.assertEqual(V.zeit_ns(Decimal('120.20000000000000000000')), 120200000000)
            self.assertEqual(V.alter_s({'generated_mono_s': 120}, Decimal('120.20')), Decimal('0.20'))
            self.assertEqual(V.zeit_ns(Decimal('0E-999999')), 0)
            self.assertEqual(V.lade_json(V.als_json(d)), d)
            for t in (Decimal('0.0000000001'), Decimal('9223372036.854775808'),
                      Decimal('1E+999999'), Decimal('1E-999999')):
                with self.assertRaises(ValueError):
                    V.zeit_ns(t)

    def test_ns_bauhelfer_ist_eindeutig(self):
        self.assertEqual(V.sekunden_aus_ns(1), Decimal('0.000000001'))
        self.assertEqual(V.zeit_ns(1), 1000000000)
        for ns in (True, False, -1, 2**63, 1.0, Decimal(1), '1', None):
            with self.subTest(ns=ns), self.assertRaises(ValueError):
                V.sekunden_aus_ns(ns)

    def test_json_dezimal_und_exponent_ohne_float(self):
        d = beispiel()
        d['motion']['request']['valid_until_mono_s'] = Decimal('120.2')
        text = V.als_json(d)
        for token in ('120.2', '120.200000000', '1.202e2'):
            gelesen = V.lade_json(text.replace('"valid_until_mono_s":120.2', '"valid_until_mono_s":'+token))
            self.assertIsInstance(gelesen['motion']['request']['valid_until_mono_s'], Decimal)
            self.assertEqual(V.zeit_ns(gelesen['motion']['request']['valid_until_mono_s']), 120200000000)
        with self.assertRaises(ValueError):
            V.lade_json(text.replace('"valid_until_mono_s":120.2', '"valid_until_mono_s":120.2000000001'))

    def test_rundlauf_bewahrt_ns_rand_ohne_fristgewinn(self):
        for ns in (119999999999, 120000000000, 120000000001, 120199999999,
                   120200000000, 120200000001, 2**63-1):
            d = beispiel()
            d['motion']['request']['valid_until_mono_s'] = V.sekunden_aus_ns(ns)
            text = V.als_json(d)
            roh = json.loads(text, parse_float=Decimal)
            self.assertIsInstance(roh['motion']['request']['valid_until_mono_s'], Decimal)
            gelesen = V.lade_json(text)
            self.assertEqual(V.zeit_ns(gelesen['motion']['request']['valid_until_mono_s']), ns)
        for delta, erwartet in ((199999999, '0.199999999'), (200000000, '0.20'), (200000001, '0.200000001')):
            self.assertEqual(V.alter_s({'generated_mono_s':120}, V.sekunden_aus_ns(120000000000+delta)), Decimal(erwartet))

    def test_direkte_float_bool_null_und_fehlende_zeiten(self):
        d = beispiel()
        for zeit in (0.0, 1.25, True, False, '1.25', None, [], {}, -1,
                     Decimal('-0.000000001'), Decimal('9223372036.854775808'), Decimal('0.0000000001')):
            with self.subTest(zeit=zeit):
                d['generated_mono_s'] = zeit
                self.assertTrue(V.pruefe(d))
                with self.assertRaises(ValueError):
                    V.als_json(d)
                with self.assertRaises(ValueError):
                    V.alter_s({'generated_mono_s':zeit}, 10)
                with self.assertRaises(ValueError):
                    V.alter_s({'generated_mono_s':0}, zeit)
        del d['generated_mono_s']
        self.assertTrue(any('generated_mono_s: fehlt' in f for f in V.pruefe(d)))

    def test_alle_lokalen_zeitfelder_nutzen_raster(self):
        paths = [('generated_mono_s',), ('motion','request','valid_until_mono_s'),
                 ('sensors','camera','captured_mono_s'), ('sensors','camera','received_mono_s'),
                 ('sensors','camera','age_s'), ('communication','last_broker_ack_mono_s')]
        for path in paths:
            for wert in (1.0, True, Decimal('0.0000000001')):
                d=beispiel()
                block=d
                for k in path[:-1]:
                    block=block[k]
                block[path[-1]]=wert
                with self.subTest(path=path, wert=wert):
                    self.assertTrue(any('.'.join(path) in f for f in V.pruefe(d)))
        d=beispiel()
        d['diagnostics']['events']=[dict(event_id='synthetic', mono_s=0.5, kind='info', text='synthetic')]
        self.assertTrue(any('mono_s' in f for f in V.pruefe(d)))

    def test_nichtendliche_decimals_zeit_und_nichtzeit(self):
        for token in ('NaN', 'sNaN', 'Infinity', '-Infinity'):
            for zeitfeld in (True, False):
                with self.subTest(token=token, zeitfeld=zeitfeld):
                    d=beispiel()
                    if zeitfeld:
                        d['generated_mono_s']=Decimal(token)
                    else:
                        d['motion']['measured_w_rad_s']['value']=Decimal(token)
                    self.assertTrue(V.pruefe(d))
                    with self.assertRaises(ValueError):
                        V.als_json(d)
                    if zeitfeld:
                        with self.assertRaises(ValueError):
                            V.alter_s(d, 10)
                        with self.assertRaises(ValueError):
                            V.alter_s({'generated_mono_s':0}, Decimal(token))

    def test_endliche_nichtzeit_decimals_floats_und_json_escaping(self):
        d=beispiel()
        d['motion']['measured_w_rad_s']['value']=Decimal('-0.2000000000000000000000000001')
        d['lane']['offset_m']=0.004  # weiterhin erlaubter direkter Nichtzeit-Float
        d['diagnostics']['warnings']=['Anfuehrung: " \\ \n ü', '"value":NaN']
        text=V.als_json(d)
        roh=json.loads(text,parse_float=Decimal)
        self.assertEqual(roh['motion']['measured_w_rad_s']['value'],d['motion']['measured_w_rad_s']['value'])
        self.assertIsInstance(roh['motion']['measured_w_rad_s']['value'],Decimal)
        self.assertEqual(roh['diagnostics']['warnings'],d['diagnostics']['warnings'])
        self.assertEqual(V.lade_json(text)['lane']['offset_m'],Decimal('0.004'))
        for token in ('NaN','Infinity','-Infinity','1e999999'):
            with self.assertRaises(ValueError):
                V.lade_json(text.replace('"offset_m":0.004','"offset_m":'+token))


if __name__ == '__main__':
    unittest.main(verbosity=2)
