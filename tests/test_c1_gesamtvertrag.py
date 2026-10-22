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


def arm_bauwert():
    d = neutralisiere(read('tests/fixtures/grundbetrieb/stillstand.json'))
    clock = 'synthetic-device-clock-0001'
    owner = dict(robot_id='RM02', producer_id='synthetic-arm-a', producer_boot_id='synthetic-arm-a-start')
    command_ref = dict(robot_id='RM02', producer_id='synthetic-arm-b', producer_boot_id='synthetic-arm-b-start', command_seq=1)
    operation = dict(robot_id='RM02', producer_id='synthetic-arm-b', producer_boot_id='synthetic-arm-b-start', operation_id='synthetic-op')
    obj = dict(robot_id='RM02', producer_id='synthetic-objects', producer_boot_id='synthetic-objects-start', object_id='synthetic-object')
    target = dict(coord_frame='robot', calibration_version='synthetic-cal',
        values={'x': {'value': Decimal('.1'), 'unit': 'm'}}, status='valid', reason=None)
    command = dict(contract_version='2.0', **command_ref, time_basis_id=clock,
        generated_mono_s=1199, valid_until_mono_s=1201, operation_ref=operation,
        object_ref=obj, action='greifen', target=target)
    eref = dict(**owner, domain='arm', evaluation_seq=1)
    output_ref = dict(robot_id='RM02', producer_id='synthetic-arm-output', producer_boot_id='synthetic-arm-output-start', output_seq=1)
    arm = d['arm']
    arm['request'] = copy.deepcopy(command)
    arm['output'] = dict(**output_ref, time_basis_id=clock, issued_mono_s=1200,
        action='greifen', target=copy.deepcopy(target), command_ref=command_ref, command_reason=None,
        operation_ref=operation, object_ref=obj, evaluation_ref=eref, status='valid', reason=None)
    arm['release'] = dict(owner_ref=owner, decision_seq=1, evaluation_ref=eref,
        time_basis_id=clock, evaluated_mono_s=1200, decision='allowed', command_ref=command_ref,
        command_reason=None, output_ref=output_ref, output_reason=None, status='valid', reason=None)
    arm['blocks'] = dict(producer_id=owner['producer_id'], producer_boot_id=owner['producer_boot_id'],
        seq=1, evaluation_ref=eref, time_basis_id=clock, evaluated_mono_s=1200, entries=[],
        stop_latched=dict(value=False, status='valid', reason=None),
        fault_latched=dict(value=False, status='valid', reason=None), status='valid', reason=None)
    arm['package_use'] = dict(mode='current', reason=None, evaluation_ref=eref)
    context = dict(bindings={'arm': {**owner, 'time_basis_id': clock}, 'arm_command': {'targetless_actions': []}},
        commands=(copy.deepcopy(command),), current_command_ref=command_ref,
        component_units={('robot', 'synthetic-cal'): {'x': 'm'}})
    return d, context


class Gesamtvertrag(unittest.TestCase):
    def setUp(self):
        self.context = synthetischer_raeumkontext()
        self.schema = read('schemas/grundbetrieb-v2.schema.json')

    def test_unbestaetigte_ausgabe_ist_keine_falsche_bewegung_im_halt(self):
        for filename in ('stillstand', 'rot_und_hindernis', 'test'):
            for status in ('unknown', 'invalid'):
                d = read('tests/fixtures/grundbetrieb/' + filename + '.json')
                d['motion']['output'].update(v_m_s=None, w_rad_s=None, status=status, reason='UNCONFIRMED_OUTPUT')
                before = copy.deepcopy(d)
                with self.subTest(filename=filename, status=status):
                    self.assertEqual(V.pruefe(d, raeum_kontext=self.context), [])
                    text = V.als_json(d, raeum_kontext=self.context)
                    self.assertEqual(V.lade_json(text, raeum_kontext=self.context), before)
                    self.assertEqual(d, before)
                    if jsonschema:
                        self.assertEqual(list(jsonschema.Draft202012Validator(self.schema).iter_errors(d)), [])
                d['motion']['output'].update(v_m_s=Decimal('.1'), w_rad_s=0, status='valid', reason=None)
                self.assertTrue(V.pruefe(d, raeum_kontext=self.context))
                with self.assertRaises(ValueError): V.als_json(d, raeum_kontext=self.context)
                with self.assertRaises(ValueError): V.lade_json(V._json_wert(d), raeum_kontext=self.context)

    def test_nicht_gueltige_historie_bewahrt_die_bestaetigte_herkunft(self):
        for status in ('missing', 'unknown', 'invalid'):
            for field in ('producer_id', 'producer_boot_id', 'time_basis_id'):
                d = neutralisiere(read('tests/fixtures/grundbetrieb/stillstand.json'))
                context = read('tests/fixtures/c1_history/context.json')
                context['binding']['robot_id'] = 'RM02'
                history = dict(producer_id=context['binding']['producer_id'],
                    producer_boot_id=context['binding']['producer_boot_id'],
                    time_basis_id=context['binding']['time_basis_id'], status=status,
                    reason='UNCONFIRMED_HISTORY', entries=None, dropped_entries=None)
                d['route']['history'] = history
                self.assertEqual(V.pruefe(d, historie_kontext=context), [])
                history[field] = 'foreign-binding'
                with self.subTest(status=status, field=field):
                    self.assertTrue(V.pruefe(d, historie_kontext=context))
                    with self.assertRaises(ValueError): V.als_json(d, historie_kontext=context)
                    with self.assertRaises(ValueError): V.lade_json(V._json_wert(d), historie_kontext=context)

    def test_aktuelle_armziele_und_ausgabeinhalt_durch_alle_einstiege(self):
        d, context = arm_bauwert()
        ctx = V.RaeumKontext(**context)
        self.assertEqual(V.pruefe(d, raeum_kontext=ctx), [])
        self.assertEqual(V.lade_json(V.als_json(d, raeum_kontext=ctx), raeum_kontext=ctx), d)
        if jsonschema:
            self.assertEqual(list(jsonschema.Draft202012Validator(self.schema).iter_errors(d)), [])
        for field in ('action', 'target', 'operation_ref', 'object_ref'):
            bad = copy.deepcopy(d)
            if field == 'action': bad['arm']['output'][field] = 'ablegen'
            elif field == 'target': bad['arm']['output']['target']['values']['x']['value'] = Decimal('.2')
            else: bad['arm']['output'][field][('operation_id' if field == 'operation_ref' else 'object_id')] = 'other'
            with self.subTest(field=field):
                self.assertTrue(V.pruefe(bad, raeum_kontext=ctx))
                with self.assertRaises(ValueError): V.als_json(bad, raeum_kontext=ctx)
                with self.assertRaises(ValueError): V.lade_json(V._json_wert(bad), raeum_kontext=ctx)
        for output in (True, False):
            bad, context = arm_bauwert()
            unknown = dict(coord_frame='robot', calibration_version='synthetic-cal', values=None,
                           status='unknown', reason='TARGET_UNPROVEN')
            bad['arm']['request']['target'] = copy.deepcopy(unknown)
            context['commands'][0]['target'] = copy.deepcopy(unknown)
            if output: bad['arm']['output']['target'] = unknown
            else:
                bad['arm']['output'] = None
                bad['arm']['release'].update(output_ref=None, output_reason='NOT_ISSUED')
            ctx = V.RaeumKontext(**context)
            with self.subTest(output=output):
                self.assertTrue(V.pruefe(bad, raeum_kontext=ctx))
                with self.assertRaises(ValueError): V.als_json(bad, raeum_kontext=ctx)
                with self.assertRaises(ValueError): V.lade_json(V._json_wert(bad), raeum_kontext=ctx)
                if jsonschema:
                    self.assertTrue(list(jsonschema.Draft202012Validator(self.schema).iter_errors(bad)))

    def test_aktuelle_erlaubnis_ignoriert_keine_unbrauchbare_relevante_sperre(self):
        for status in ('invalid', 'unknown', 'missing', 'stale'):
            d = read('tests/fixtures/grundbetrieb/fahrt.json')
            owner = d['motion']['release']['owner_ref']
            d['motion']['blocks']['entries'] = [dict(
                block_ref={**owner, 'block_id': 'front-check'}, code='FRONT_BLOCKED',
                effect='both', frame_ref=None, time_basis_id='synthetic-device-clock-0001',
                reported_mono_s=d['generated_mono_s'], status=status, reason='NOT_TRUSTED')]
            with self.subTest(status=status):
                errors = V.pruefe(d, raeum_kontext=self.context)
                self.assertIsInstance(errors, list)
                self.assertTrue(errors)
                with self.assertRaises(ValueError):
                    V.als_json(d, raeum_kontext=self.context)
                with self.assertRaises(ValueError):
                    V.lade_json(V._json_wert(d), raeum_kontext=self.context)
                if jsonschema:
                    self.assertTrue(list(jsonschema.Draft202012Validator(self.schema).iter_errors(d)))

    def test_falsch_typisierte_haltgruende_bleiben_validierungsfehler(self):
        for value in (True, [{}], [[]]):
            with self.subTest(value=value):
                d = read('tests/fixtures/grundbetrieb/fahrt.json')
                d['runtime']['hold_reasons'] = value
                errors = V.pruefe(d, raeum_kontext=self.context)
                self.assertIsInstance(errors, list)
                self.assertTrue(errors)
                with self.assertRaises(ValueError):
                    V.als_json(d, raeum_kontext=self.context)
                with self.assertRaises(ValueError):
                    V.lade_json(V._json_wert(d), raeum_kontext=self.context)

    def test_falsch_geladene_kontextcontainer_bleiben_validierungsfehler(self):
        d = neutralisiere(read('tests/fixtures/grundbetrieb/stillstand.json'))
        text = V.als_json(d)
        empty = V.RaeumKontext()
        self.assertEqual(V.pruefe(d, raeum_kontext=empty), [])
        self.assertEqual(V.lade_json(text, raeum_kontext=empty), d)
        invalid = [V.RaeumKontext(**{name: None}) for name in
            ('frames', 'details', 'evidences', 'policy_evidences', 'requests', 'commands', 'evaluations')]
        invalid.extend((V.RaeumKontext(evaluations=True), V.RaeumKontext(bindings=[]),
                        V.RaeumKontext(component_units=[]), {'evaluations': []}))
        for context in invalid:
            with self.subTest(context=repr(context)):
                errors = V.pruefe(d, raeum_kontext=context)
                self.assertIsInstance(errors, list)
                self.assertTrue(errors)
                with self.assertRaises(ValueError):
                    V.als_json(d, raeum_kontext=context)
                with self.assertRaises(ValueError):
                    V.lade_json(text, raeum_kontext=context)

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
    def test_fahrwunschgrenzen_gelten_eingebettet_und_separat(self):
        validator = jsonschema.Draft202012Validator(self.schema)
        for field, low, high in (('v_m_s', -1, 1), ('w_rad_s', -10, 10)):
            for value in (low, high):
                d = neutralisiere(read('tests/fixtures/grundbetrieb/test.json'))
                d['motion']['request'][field] = value
                self.assertEqual(V.pruefe(d), [])
                self.assertEqual(list(validator.iter_errors(d)), [])
                self.assertEqual(V.lade_json(V.als_json(d)), d)
            for value in (Decimal(str(low)) - Decimal('.000000001'),
                          Decimal(str(high)) + Decimal('.000000001'), -999, 999):
                with self.subTest(field=field, value=value):
                    d = neutralisiere(read('tests/fixtures/grundbetrieb/test.json'))
                    d['motion']['request'][field] = value
                    self.assertTrue(V.pruefe_fahrwunsch(d['motion']['request']))
                    self.assertTrue(V.pruefe(d))
                    self.assertTrue(list(validator.iter_errors(d)))
                    with self.assertRaises(ValueError):
                        V.als_json(d)
                    with self.assertRaises(ValueError):
                        V.lade_json(V._json_wert(d))

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

    @unittest.skipIf(jsonschema is None, 'jsonschema nicht installiert')
    def test_endgueltige_fahrtausgabe_hat_dieselben_strukturellen_grenzen(self):
        validator = jsonschema.Draft202012Validator(self.schema)
        for field, low, high in (('v_m_s', -1, 1), ('w_rad_s', -10, 10)):
            for value in (low, high):
                d = read('tests/fixtures/grundbetrieb/fahrt.json')
                d['motion']['output'][field] = value
                self.assertEqual(V.pruefe(d, raeum_kontext=self.context), [])
                self.assertEqual(list(validator.iter_errors(d)), [])
            for value in (Decimal(str(low)) - Decimal('.000000001'),
                          Decimal(str(high)) + Decimal('.000000001'), -999, 999):
                with self.subTest(field=field, value=value):
                    d = read('tests/fixtures/grundbetrieb/fahrt.json')
                    d['motion']['output'][field] = value
                    self.assertTrue(V.pruefe(d, raeum_kontext=self.context))
                    self.assertTrue(list(validator.iter_errors(d)))
                    with self.assertRaises(ValueError):
                        V.als_json(d, raeum_kontext=self.context)
                    with self.assertRaises(ValueError):
                        V.lade_json(V._json_wert(d), raeum_kontext=self.context)

    @unittest.skipIf(jsonschema is None, 'jsonschema nicht installiert')
    def test_aktueller_wunschbezug_bleibt_fuer_beide_leser_vollstaendig_eingebettet(self):
        d = read('tests/fixtures/grundbetrieb/fahrt.json')
        self.assertEqual(V.pruefe(d, raeum_kontext=self.context), [])
        d['motion']['request'] = None
        self.assertTrue(V.pruefe(d, raeum_kontext=self.context))
        self.assertTrue(list(jsonschema.Draft202012Validator(self.schema).iter_errors(d)))
        with self.assertRaises(ValueError):
            V.als_json(d, raeum_kontext=self.context)
        with self.assertRaises(ValueError):
            V.lade_json(V._json_wert(d), raeum_kontext=self.context)


if __name__ == '__main__':
    unittest.main()
