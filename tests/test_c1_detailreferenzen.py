#!/usr/bin/env python3
"""#150: explicit historical detail context; no ROS, broker, or payload storage.

Run preparation checks: python tests/test_c1_detailreferenzen.py Vorbereitung -v
Run all acceptance cases:
    python tests/test_c1_detailreferenzen.py -v
The preparation originally failed on 1.0; runtime now uses assigned #149 + #150.

Public API:
  pruefe_detailreferenz(detail, *, zustand, detail_kontext=None)
    -> {status, reason, age_s, context}
  pruefe(state, *, detail_kontext=None) -> existing error list
  als_json(state, *, detail_kontext=None) -> validating numeric JSON
  lade_json(text, *, detail_kontext=None) -> validating exact state

context is explicitly supplied, never created from a candidate. context_id names
the supplied context; registrations/records are independent historical evidence,
age_budgets_s are explicit per-channel limits. Return context identifies at least
context_id, robot_id, state_boot_id, time_basis_id, plus used historical frame/data
key and budget when available. Missing context must not certify asserted valid.
The standalone assessment does not mutate status, candidate, or context. Strict
state/JSON paths reject an asserted valid if the assessment cannot confirm it;
honest unknown/missing remain representable without inventing evidence.

Assigned foundation: PR #151, head
1a90143f98c0d78c7bb7b944e5facb8a6b285de1 (not a full C1 acceptance).
Reuse its public sekunden_aus_ns(integer_ns), zeit_ns(exact_seconds),
alter_s(state, now), lade_json(text), als_json(state). No parallel number parser,
ns conversion, or JSON writer. Candidate vector files are deliberately read with
standard json.loads(parse_float=Decimal); public state acceptance/roundtrips use
V.pruefe / V.lade_json / V.als_json. Do not call its private _json_wert.

Detail structure/null rules and contextual records/budgets are separate; strict
context forwarding covers all three public entries. Fixture formats/budgets are
synthetic. Schema checks below are full-state checks, not a substitute
for contextual evidence. No payload store, global registration, or adapter.
"""
import copy
from decimal import Decimal, localcontext, Inexact, Rounded
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests' / 'fixtures' / 'c1_details'
sys.path.insert(0, str(ROOT / 'lib'))
import grundbetrieb_vertrag as V  # noqa: E402
from c1_testbauwerte import neutralisiere


def read_fixture(name):
    return json.loads((FIXTURES / (name + '.json')).read_text(encoding='utf-8'),
                      parse_float=Decimal)


def frame_key(d):
    return tuple(d[k] for k in ('robot_id', 'source', 'producer_id',
                                'producer_boot_id', 'frame_id'))


def data_key(d):
    return frame_key(d) + (d['channel'], d['data_id'])


class Vorbereitung(unittest.TestCase):
    """Fixture integrity only; these tests make no runtime acceptance claim."""

    def test_separate_context_and_candidates(self):
        context = read_fixture('context')
        original = copy.deepcopy(context)
        candidate = read_fixture('candidates')['camera']
        candidate.update(producer_boot_id='untrusted', format='changed')
        self.assertEqual(context, original)
        self.assertNotIn(frame_key(candidate), [frame_key(x) for x in context['records']])

    def test_six_cases_have_exact_times_and_explicit_quality(self):
        cases = read_fixture('candidates')
        self.assertEqual(set(cases), {'camera', 'lidar', 'stale', 'old_clock',
                                     'missing', 'unknown'})
        for name, d in cases.items():
            with self.subTest(case=name):
                for field in ('captured_mono_s', 'received_mono_s', 'age_s'):
                    self.assertTrue(d[field] is None or
                                    type(d[field]) in (int, Decimal))
                if d['status'] != 'valid':
                    self.assertTrue(d['reason'])

    def test_known_records_are_independent_and_unique(self):
        context = read_fixture('context')
        records = context['records']
        self.assertEqual(len({data_key(x) for x in records}), len(records))
        for name in ('camera', 'lidar', 'stale', 'old_clock'):
            candidate = read_fixture('candidates')[name]
            match = [r for r in records if data_key(r) == data_key(candidate)]
            self.assertEqual(len(match), 1)
            self.assertEqual({k: candidate[k] for k in match[0]}, match[0])

    def test_synthetic_age_boundaries(self):
        cases, state = read_fixture('candidates'), read_fixture('state_context')
        for name in ('camera', 'lidar', 'stale'):
            d = cases[name]
            self.assertEqual(state['generated_mono_s'] - d['captured_mono_s'], d['age_s'])
        self.assertEqual(cases['camera']['age_s'], Decimal('0.2'))
        self.assertGreater(cases['stale']['age_s'], Decimal('0.2'))

    def test_missing_retains_known_identity_without_fake_frame(self):
        d = read_fixture('candidates')['missing']
        for field in ('robot_id', 'source', 'source_id', 'producer_id',
                      'producer_boot_id', 'state_boot_id', 'time_basis_id'):
            self.assertTrue(d[field])
        for field in ('frame_id', 'data_id', 'format', 'captured_at_s',
                      'captured_mono_s', 'received_mono_s', 'age_s'):
            self.assertIsNone(d[field])


class DetailLaufzeit(unittest.TestCase):
    """All negative candidates are mutated after context setup; no implicit trust."""

    def setUp(self):
        self.assertEqual(V.SCHEMA_VERSION, '2.0', '#149 foundation not delivered here')
        self.assertTrue(callable(getattr(V, 'pruefe_detailreferenz', None)),
                        '#150 contextual API not implemented yet')
        for name in ('sekunden_aus_ns', 'zeit_ns', 'lade_json', 'als_json'):
            self.assertTrue(callable(getattr(V, name, None)), name)
        # Freeze trusted evidence BEFORE each candidate is read or mutated.
        self.context = read_fixture('context')
        self.saved_context = copy.deepcopy(self.context)
        self.state = read_fixture('state_context')
        self.cases = read_fixture('candidates')

    def assess(self, d, context='given', state=None):
        ctx = self.context if context == 'given' else context
        before = copy.deepcopy((d, ctx, state or self.state))
        result = V.pruefe_detailreferenz(
            d, zustand=state or self.state, detail_kontext=ctx)
        self.assertEqual((d, ctx, state or self.state), before, 'assessment must be pure')
        self.assertIn(result['status'], V.STATUS)
        if result['status'] != 'valid':
            self.assertTrue(result['reason'])
        return result

    def test_older_camera_with_previous_producer_start_can_be_valid(self):
        d = self.cases['camera']
        self.assertNotEqual(d['frame_id'], self.state['sensors']['camera']['frame_id'])
        self.assertNotEqual(d['producer_boot_id'],
                            self.state['sensors']['camera']['producer_boot_id'])
        result = self.assess(d)
        self.assertEqual(result['status'], 'valid')
        self.assertEqual(result['age_s'], V.sekunden_aus_ns(200000000))
        self.assertEqual(V.zeit_ns(result['age_s']), 200000000)
        self.assertEqual(result['context']['context_id'], self.context['context_id'])
        for key in ('robot_id', 'state_boot_id', 'time_basis_id'):
            self.assertEqual(result['context'][key], self.context[key])

    def test_lidar_and_stale(self):
        for name, status in (('lidar', 'valid'), ('stale', 'stale')):
            with self.subTest(case=name):
                result = self.assess(self.cases[name])
                self.assertEqual(result['status'], status)
                self.assertEqual(result['age_s'], self.cases[name]['age_s'])

    def test_current_source_failure_does_not_rewrite_historical_quality(self):
        self.state['sensors']['camera'].update(status='invalid', reason='current_failure')
        self.assertEqual(self.assess(self.cases['camera'])['status'], 'valid')

    def test_foreign_device_source_and_source_id_alias(self):
        for key, value in (('robot_id', 'RM03'), ('source', 'foreign_camera'),
                           ('source', 'rgb-test'), ('source_id', 'wrong-technical-source'),
                           ('producer_id', 'foreign-driver')):
            with self.subTest(field=key, value=value):
                d = copy.deepcopy(self.cases['camera'])
                d[key] = value
                self.assertEqual(self.assess(d)['status'], 'invalid')
        self.assertEqual(self.context, self.saved_context)

    def test_unconfirmed_start_and_absent_historical_record(self):
        d = copy.deepcopy(self.cases['camera'])
        d['producer_boot_id'] = 'unconfirmed-start'
        self.assertEqual(self.assess(d)['status'], 'unknown')
        self.context['records'] = []
        result = self.assess(self.cases['camera'])
        self.assertEqual(result['status'], 'unknown')
        self.assertIsNone(result['age_s'])

    def test_incomplete_binding_despite_equal_identifier_text(self):
        self.context['registrations'] = []
        result = self.assess(self.cases['camera'])
        self.assertEqual(result['status'], 'unknown')
        self.assertIsNone(result['age_s'])

    def test_conflicting_metadata_of_same_data_key(self):
        for field, value in (('format', 'example/other'),
                             ('captured_at_s', 1),
                             ('captured_mono_s', Decimal('104.7'))):
            with self.subTest(field=field):
                d = copy.deepcopy(self.cases['camera'])
                d[field] = value
                self.assertEqual(data_key(d), data_key(self.cases['camera']))
                self.assertEqual(self.assess(d)['status'], 'invalid')

    def test_time_basis_reset_and_future(self):
        result = self.assess(self.cases['old_clock'])
        self.assertEqual(result['status'], 'invalid')
        self.assertIsNone(result['age_s'])
        for field in ('captured_mono_s', 'received_mono_s'):
            d = copy.deepcopy(self.cases['camera'])
            d[field] = V.sekunden_aus_ns(105000000001)
            self.assertEqual(self.assess(d)['status'], 'invalid')

    def test_missing_budget_and_context_cannot_certify_valid(self):
        del self.context['age_budgets_s']['color']
        result = self.assess(self.cases['camera'])
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(result['reason'], 'age_budget_unknown')
        self.assertIsNone(result['age_s'])
        result = self.assess(self.cases['camera'], context=None)
        self.assertEqual(result['status'], 'unknown')
        self.assertIsNone(result['age_s'])

    def test_public_entries_require_each_piece_of_positive_context(self):
        original = self.full_state([self.cases['camera']])
        text = V.als_json(original, detail_kontext=self.context)
        for absent in ('registrations', 'records', 'age_budgets_s'):
            ctx = copy.deepcopy(self.context)
            ctx[absent] = {} if absent == 'age_budgets_s' else []
            with self.subTest(absent=absent):
                self.assertTrue(V.pruefe(original, detail_kontext=ctx))
                with self.assertRaises(ValueError):
                    V.als_json(original, detail_kontext=ctx)
                with self.assertRaises(ValueError):
                    V.lade_json(text, detail_kontext=ctx)

    def test_free_frame_original_error_is_rejected_in_all_public_entries(self):
        d = self.full_state([self.cases['camera']])
        text = V.als_json(d, detail_kontext=self.context)
        d['details'][0]['frame_id'] = 'freely-claimed-frame'
        self.assertEqual(self.assess(d['details'][0])['status'], 'unknown')
        for ctx in (self.context, None):
            with self.subTest(context=ctx is not None):
                self.assertTrue(V.pruefe(d, detail_kontext=ctx))
                with self.assertRaises(ValueError):
                    V.als_json(d, detail_kontext=ctx)
                with self.assertRaises(ValueError):
                    V.lade_json(text.replace('rgb-10', 'freely-claimed-frame'),
                                detail_kontext=ctx)

    def test_invalid_payload_quality_is_not_upgraded_by_identity(self):
        d = copy.deepcopy(self.cases['camera'])
        d.update(status='invalid', reason='payload_unusable', age_s=None)
        self.assertEqual(self.assess(d)['status'], 'invalid')
        self.assertEqual(V.pruefe(self.full_state([d])), [])

    def test_confirmed_contradiction_cannot_be_hidden_as_unknown(self):
        detail = copy.deepcopy(self.cases['old_clock'])
        detail.update(status='unknown', reason='claimed_unknown')
        self.assertEqual(self.assess(detail)['status'], 'invalid')
        self.assertTrue(V.pruefe(self.full_state([detail]), detail_kontext=self.context))

    def test_wrong_context_binding_and_missing_time_basis(self):
        for field, value in (('robot_id', 'RM03'), ('state_boot_id', 'state-foreign'),
                             ('time_basis_id', 'clock-foreign')):
            ctx = copy.deepcopy(self.context)
            ctx[field] = value
            with self.subTest(field=field):
                result = self.assess(self.cases['camera'], context=ctx)
                self.assertEqual(result['status'], 'invalid')
                self.assertIsNone(result['age_s'])
        d = copy.deepcopy(self.cases['unknown'])
        d.update({k: v for k, v in self.cases['camera'].items()
                  if k not in ('time_basis_id', 'status', 'reason', 'age_s')})
        self.assertEqual(self.assess(d)['status'], 'unknown')

    def test_context_and_direct_time_inputs_fail_cleanly_without_repair(self):
        for value in (True, 0.2, '0.2', Decimal('NaN'), Decimal('sNaN'),
                      Decimal('Infinity'), Decimal('-Infinity'), Decimal('0.0000000001')):
            with self.subTest(value=repr(value)):
                ctx = copy.deepcopy(self.context)
                ctx['age_budgets_s']['color'] = value
                self.assertEqual(self.assess(self.cases['camera'], context=ctx)['status'], 'invalid')
                d = copy.deepcopy(self.cases['camera'])
                d['captured_mono_s'] = value
                self.assertEqual(self.assess(d)['status'], 'invalid')

    def test_conflicting_explicit_registry_is_not_resolved_by_first_match(self):
        for collection, field in (('records', 'format'), ('registrations', 'source_id')):
            ctx = copy.deepcopy(self.context)
            conflicting = copy.deepcopy(ctx[collection][0])
            conflicting[field] = 'conflicting-metadata'
            ctx[collection].append(conflicting)
            with self.subTest(collection=collection):
                self.assertEqual(self.assess(self.cases['camera'], context=ctx)['status'], 'invalid')
    def test_exact_budget_at_boundary_and_one_ns_below(self):
        # Same known frame: changing only explicit budget avoids inventing records.
        self.assertEqual(self.assess(self.cases['camera'])['status'], 'valid')
        self.context['age_budgets_s']['color'] = V.sekunden_aus_ns(199999999)
        self.assertEqual(self.assess(self.cases['camera'])['status'], 'stale')

    def test_reception_does_not_refresh_an_old_capture(self):
        d = copy.deepcopy(self.cases['stale'])
        d['received_mono_s'] = 105
        # A changed immutable record may be invalid; it must never become fresh.
        self.assertNotEqual(self.assess(d)['status'], 'valid')

    def test_small_decimal_context_does_not_change_exact_detail_boundary(self):
        d = self.full_state([self.cases['camera']])
        with localcontext() as ctx:
            ctx.prec = 2
            ctx.traps[Inexact] = ctx.traps[Rounded] = True
            self.assertEqual(self.assess(self.cases['camera'])['age_s'], Decimal('0.2'))
            self.assertEqual(V.pruefe(d, detail_kontext=self.context), [])
            text = V.als_json(d, detail_kontext=self.context)
            self.assertEqual(V.lade_json(text, detail_kontext=self.context), d)

    def test_nonlocal_utc_float_metadata_uses_its_json_value(self):
        # Independently prepared known record and candidate; no local time floats.
        self.context['records'][0]['captured_at_s'] = 1792653604.8
        d = self.full_state([self.cases['camera']])
        d['details'][0]['captured_at_s'] = 1792653604.8
        text = V.als_json(d, detail_kontext=self.context)
        result = V.lade_json(text, detail_kontext=self.context)
        self.assertEqual(result['details'][0]['captured_at_s'], Decimal('1792653604.8'))

    def test_missing_and_unknown_preserve_nulls_without_registration(self):
        for name in ('missing', 'unknown'):
            with self.subTest(case=name):
                d = self.cases[name]
                result = self.assess(d, context=None)
                self.assertEqual(result['status'], name)
                self.assertIsNone(result['age_s'])

    def test_c_restart_changes_only_output_context(self):
        old = copy.deepcopy(self.cases['camera'])
        d = copy.deepcopy(old)
        d['state_boot_id'] = 'state-C-0001'
        self.state.update(boot_id='state-C-0001', seq=0)
        self.context['state_boot_id'] = 'state-C-0001'  # Explicit new C binding only.
        self.assertEqual(data_key(d), data_key(old))
        self.assertEqual(self.assess(d)['status'], 'valid')
        self.assertEqual(self.assess(old)['status'], 'invalid')

    def full_state(self, details):
        # Raw base fixture construction is not public state acceptance: the tests
        # below exercise all three validating public entries with explicit context.
        d = json.loads((ROOT / 'tests/fixtures/grundbetrieb/stillstand.json').read_text(
            encoding='utf-8'), parse_float=Decimal)
        d.update({k: v for k, v in self.state.items() if k != 'sensors'})
        # Unrelated valid fixture sources use the same synthetic local time window.
        for q in d['sensors'].values():
            if q['status'] != 'missing':
                q.update(time_basis_id='clock-1',
                         captured_mono_s=V.sekunden_aus_ns(104900000000),
                         received_mono_s=V.sekunden_aus_ns(104950000000),
                         age_s=V.sekunden_aus_ns(100000000))
        d['sensors'].update(copy.deepcopy(self.state['sensors']))
        neutralisiere(d)
        d['details'] = [copy.deepcopy(detail) for detail in details]
        return d

    def test_public_python_json_roundtrip_and_omitted_context(self):
        d = self.full_state([self.cases['camera']])
        self.assertEqual(V.pruefe(d, detail_kontext=self.context), [])
        text = V.als_json(d, detail_kontext=self.context)
        self.assertEqual(V.lade_json(text, detail_kontext=self.context), d)
        self.assertTrue(V.pruefe(d), 'asserted valid needs positive contextual evidence')
        with self.assertRaises(ValueError):
            V.als_json(d)
        with self.assertRaises(ValueError):
            V.lade_json(text)
        for name in ('missing', 'unknown'):
            diagnostic = self.full_state([self.cases[name]])
            self.assertEqual(V.pruefe(diagnostic), [])
            self.assertEqual(V.lade_json(V.als_json(diagnostic)), diagnostic)

    def test_public_paths_reject_untrusted_mutation_after_context_is_fixed(self):
        d = self.full_state([self.cases['camera']])
        text = V.als_json(d, detail_kontext=self.context)
        d['details'][0]['format'] = 'example/other'
        self.assertTrue(V.pruefe(d, detail_kontext=self.context))
        with self.assertRaises(ValueError):
            V.als_json(d, detail_kontext=self.context)
        with self.assertRaises(ValueError):
            V.lade_json(text.replace('example/rgb', 'example/other'),
                        detail_kontext=self.context)
        self.assertEqual(self.context, self.saved_context)

    def test_duplicate_identity_vs_conflicting_duplicate(self):
        d = self.full_state([self.cases['camera'], self.cases['camera']])
        self.assertEqual(V.pruefe(d, detail_kontext=self.context), [])
        d['details'][1]['format'] = 'example/other'
        self.assertTrue(V.pruefe(d, detail_kontext=self.context))

    def test_diagnostics_keep_outer_identity_and_null_rules(self):
        for name in ('missing', 'unknown', 'old_clock'):
            for field, value in (('state_boot_id', 'other-c-start'),
                                 ('robot_id', 'RM03'), ('source', 'rgb-test'),
                                 ('age_s', Decimal('0.1'))):
                d = self.full_state([self.cases[name]])
                d['details'][0][field] = value
                with self.subTest(case=name, field=field):
                    self.assertTrue(V.pruefe(d))
        for field in ('data_id', 'frame_id', 'format', 'captured_mono_s'):
            d = self.full_state([self.cases['missing']])
            d['details'][0][field] = 0 if field.endswith('_s') else 'fake-missing-id'
            with self.subTest(field=field):
                self.assertTrue(V.pruefe(d))

    def test_v2_schema_really_validates_new_detail_fixtures(self):
        import jsonschema  # Required at implementation delivery; no silent skip.
        schema = json.loads((ROOT / 'schemas/grundbetrieb-v2.schema.json').read_text(
            encoding='utf-8'), parse_float=Decimal)
        validator = jsonschema.Draft202012Validator(schema)
        for name, detail in self.cases.items():
            with self.subTest(case=name):
                d = self.full_state([detail])
                self.assertEqual(list(validator.iter_errors(d)), [])
        # Structure is weaker than contextual evidence, but valid null IDs must fail.
        d = self.full_state([self.cases['camera']])
        d['details'][0]['frame_id'] = None
        self.assertTrue(list(validator.iter_errors(d)))


if __name__ == '__main__':
    unittest.main()
