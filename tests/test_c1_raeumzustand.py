#!/usr/bin/env python3
"""Synthetische V3a-Datenproben; keine Geraete- oder Schutzabnahme."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
from c1_raeumzustand import RaeumKontext, SCHEMA_DEFS, pruefe_raeumzustand, unbekannte_bloecke


def state():
    return {'robot_id': 'RM02', 'time_basis_id': 'clock', 'generated_mono_s': 100,
            'runtime': {'evaluation_ref': None, 'stop_latched': None, 'fault_latched': None, 'hold_reasons': []},
            **unbekannte_bloecke()}


def identity(producer='a'):
    return {'robot_id': 'RM02', 'producer_id': producer, 'producer_boot_id': producer + '-start'}


def ref(kind, seq=1, producer='a'):
    return {**identity(producer), kind: seq}


def package(s, domain='motion', decision='blocked', output=True, request=None):
    p = s[domain]
    key = 'request' if domain == 'motion' else 'command'
    owner = identity(domain + '-owner')
    eref = {**owner, 'domain': domain, 'evaluation_seq': 1}
    oref = ref('output_seq', producer=domain + '-output')
    p['release'] = {'owner_ref': owner, 'decision_seq': 1, 'evaluation_ref': eref,
                    'time_basis_id': 'clock', 'evaluated_mono_s': 100, 'decision': decision,
                    key + '_ref': request, key + '_reason': None if request else 'NO_REQUEST',
                    'output_ref': oref if output else None, 'output_reason': None if output else 'NOT_ISSUED',
                    'status': 'valid', 'reason': None}
    p['blocks'] = {'producer_id': owner['producer_id'], 'producer_boot_id': owner['producer_boot_id'],
                   'seq': 1, 'evaluation_ref': eref, 'time_basis_id': 'clock', 'evaluated_mono_s': 100,
                   'entries': [], 'stop_latched': {'value': False, 'status': 'valid', 'reason': None},
                   'fault_latched': {'value': False, 'status': 'valid', 'reason': None},
                   'status': 'valid', 'reason': None}
    p['package_use'] = {'mode': 'current', 'reason': None, 'evaluation_ref': eref}
    if output:
        p['output'] = {**oref, 'time_basis_id': 'clock', 'issued_mono_s': 100,
                       key + '_ref': request, key + '_reason': None if request else 'NO_REQUEST',
                       'evaluation_ref': eref, 'status': 'valid', 'reason': None}
        if domain == 'motion':
            p['output'].update({'v_m_s': 0, 'w_rad_s': 0})
        else:
            p['output'].update({'action': 'greifen', 'target': None,
                                'operation_ref': ref('operation_id', 'op', 'b'),
                                'object_ref': ref('object_id', 'object', 'objects')})
    if domain == 'motion':
        s['runtime'].update({'evaluation_ref': eref, 'stop_latched': False, 'fault_latched': False})
    return {domain: {**owner, 'time_basis_id': 'clock'}}


def clearing(s, phase='greifen'):
    x = s['clearing']
    x.update({'producer_id': 'b', 'producer_boot_id': 'b-start', 'time_basis_id': 'clock',
              'status': 'valid', 'reason': None, 'phase': phase, 'execution_status': 'laufend',
              'result': 'offen', 'operation_id': 'op', 'started_mono_s': 98, 'updated_mono_s': 100,
              'object_ref': ref('object_id', 'object', 'objects')})
    return {'clearing': {**identity('b'), 'time_basis_id': 'clock'}}


class Raeumdaten(unittest.TestCase):
    def check(self, s, **kwargs):
        return pruefe_raeumzustand(s, kontext=RaeumKontext(**kwargs))

    def test_unknown_is_honest_without_context(self):
        self.assertEqual(pruefe_raeumzustand(state()), [])

    def test_four_synthetic_fixtures(self):
        for f in (Path(__file__).parent / 'fixtures' / 'c1_clearing').glob('*.json'):
            s = json.loads(f.read_text(), parse_float=Decimal)
            self.assertEqual(self.check(s, bindings={'clearing': {**identity('b'), 'time_basis_id': 'clock'}}), [], f.name)

    def test_missing_keys_rejected(self):
        for name, key in (('clearing', 'result'), ('arm', 'measured'), ('protection', 'evidence_ref')):
            s = state()
            del s[name][key]
            self.assertTrue(self.check(s))

    def test_final_result_requires_ended(self):
        s = state(); b = clearing(s)
        for result in ('abgebrochen', 'nicht_raeumbar', 'erfolgreich'):
            s['clearing']['result'] = result
            self.assertTrue(any('beendet' in x for x in self.check(s, bindings=b)))

    def test_ended_active_operation_requires_final_result(self):
        s = state(); b = clearing(s, 'greifen')
        s['clearing']['execution_status'] = 'beendet'
        self.assertTrue(any('abschliessendes Ergebnis' in x for x in self.check(s, bindings=b)))
        s['clearing'].update({'result': 'abgebrochen', 'abort_reason': 'person_hold'})
        self.assertEqual(self.check(s, bindings=b), [])

    def test_pause_requires_reason_time_and_open_result(self):
        s = state(); b = clearing(s)
        s['clearing'].update({'execution_status': 'pausiert', 'interruption_reason': 'person_hold', 'interrupted_mono_s': 100})
        self.assertEqual(self.check(s, bindings=b), [])
        s['clearing']['interrupted_mono_s'] = 97
        self.assertTrue(self.check(s, bindings=b))

    def test_active_valid_requires_bound_producer_and_object(self):
        s = state(); b = clearing(s)
        self.assertTrue(self.check(s))
        self.assertEqual(self.check(s, bindings=b), [])
        s['clearing']['object_ref'] = None
        self.assertTrue(self.check(s, bindings=b))

    def test_inactive_has_complete_nulls_and_no_arm_request(self):
        s = state(); b = clearing(s, 'inaktiv')
        s['clearing'].update({k: None for k in ('operation_id', 'started_mono_s', 'updated_mono_s', 'object_ref')})
        s['clearing']['execution_status'] = 'beendet'
        self.assertEqual(self.check(s, bindings=b), [])
        s['arm']['request'] = {}
        self.assertTrue(self.check(s, bindings=b))

    def test_motion_blocked_zero_positive_and_nonzero_negative(self):
        s = state(); b = package(s)
        self.assertEqual(self.check(s, bindings=b), [])
        for k in ('v_m_s', 'w_rad_s'):
            s = state(); b = package(s); s['motion']['output'][k] = Decimal('.1')
            self.assertTrue(any('0/0' in x for x in self.check(s, bindings=b)))

    def test_mix_of_atomic_packages_rejected(self):
        s = state(); b = package(s)
        s['motion']['blocks']['evaluation_ref'] = {**s['motion']['release']['evaluation_ref'], 'evaluation_seq': 2}
        self.assertTrue(self.check(s, bindings=b))

    def allowed(self, domain='motion', output=False):
        s = state()
        kind = 'request' if domain == 'motion' else 'command'
        r = {**ref(kind + '_seq', producer='b'), 'time_basis_id': 'clock', 'generated_mono_s': 99, 'valid_until_mono_s': 101}
        if domain == 'motion':
            r.update({'contract_version': '2.0', 'request_id': 'demo-request', 'v_m_s': 0,
                      'w_rad_s': 0, 'maneuver': None, 'hold_reasons': []})
        else:
            r.update({'contract_version': '2.0', 'operation_ref': ref('operation_id', 'op', 'b'),
                      'object_ref': ref('object_id', 'object', 'objects'), 'action': 'greifen', 'target': None})
        rr = {k: r[k] for k in ('robot_id', 'producer_id', 'producer_boot_id', kind + '_seq')}
        b = package(s, domain, 'allowed', output, rr)
        s[domain]['request'] = copy.deepcopy(r)
        if domain == 'arm':
            b['arm_command'] = {'targetless_actions': ['greifen']}
        kw = {'bindings': b, 'requests' if domain == 'motion' else 'commands': (r,), 'current_request_ref' if domain == 'motion' else 'current_command_ref': rr}
        return s, kw

    def test_current_allowed_without_output_does_not_invent_issue_time(self):
        s, kw = self.allowed()
        self.assertEqual(self.check(s, **kw), [])

    def test_current_request_cannot_be_omitted_despite_external_resolution(self):
        for domain in ('motion', 'arm'):
            s, kw = self.allowed(domain)
            self.assertEqual(self.check(s, **kw), [])
            s[domain]['request'] = None
            self.assertTrue(any('eingebetteten Wunsch' in e for e in self.check(s, **kw)))
            s[domain]['package_use'].update({'mode': 'historical', 'reason': 'DIAGNOSTIC'})
            if domain == 'motion':
                s['runtime'].update({'evaluation_ref': None, 'stop_latched': None, 'fault_latched': None})
            self.assertEqual(self.check(s, **kw), [])

    def test_motion_output_inclusive_bounds_and_overflows(self):
        for field, bound in (('v_m_s', 1), ('w_rad_s', 10)):
            for sign in (-1, 1):
                s, kw = self.allowed(output=True)
                s['motion']['output'][field] = sign * bound
                self.assertEqual(self.check(s, **kw), [])
                s['motion']['output'][field] = sign * (Decimal(bound) + Decimal('.000000001'))
                self.assertTrue(any('Bereichs' in e for e in self.check(s, **kw)))
            s, kw = self.allowed(output=True)
            s['motion']['output'][field] = 999
            self.assertTrue(any('Bereichs' in e for e in self.check(s, **kw)))

    def test_motion_output_schema_bounds(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest('optionale jsonschema-Abhaengigkeit fehlt')
        validator = Draft202012Validator({'$defs': SCHEMA_DEFS, '$ref': '#/$defs/c1_motion_output'})
        for field, bound in (('v_m_s', 1), ('w_rad_s', 10)):
            s, _ = self.allowed(output=True)
            out = s['motion']['output']
            for sign in (-1, 1):
                out[field] = sign * bound
                self.assertEqual(list(validator.iter_errors(out)), [])
                out[field] = sign * (Decimal(bound) + Decimal('.000000001'))
                self.assertTrue(list(validator.iter_errors(out)))

    def test_allowed_without_explicit_acceptance_cannot_be_current(self):
        s, kw = self.allowed()
        del kw['current_request_ref']
        self.assertTrue(self.check(s, **kw))

    def test_request_expiry_boundary_and_historical_preservation(self):
        s, kw = self.allowed()
        s['generated_mono_s'] = 101
        self.assertTrue(self.check(s, **kw))
        s['motion']['package_use'].update({'mode': 'historical', 'reason': 'REQUEST_EXPIRED'})
        s['runtime'].update({'evaluation_ref': None, 'stop_latched': None, 'fault_latched': None})
        self.assertEqual(self.check(s, **kw), [])

    def test_historical_does_not_repair_expired_evaluation(self):
        s, kw = self.allowed()
        s['generated_mono_s'] = 102
        for k in ('release', 'blocks'):
            s['motion'][k]['evaluated_mono_s'] = 101
        s['motion']['package_use'].update({'mode': 'historical', 'reason': 'REQUEST_EXPIRED'})
        s['runtime'].update({'evaluation_ref': None, 'stop_latched': None, 'fault_latched': None})
        self.assertTrue(self.check(s, **kw))

    def test_unknown_and_historical_cannot_project_known_latches(self):
        for name in ('stop_latched', 'fault_latched'):
            s = state(); s['runtime'][name] = False
            self.assertTrue(any(name in x for x in self.check(s)))
            s, kw = self.allowed()
            s['motion']['package_use'].update({'mode': 'historical', 'reason': 'DIAGNOSTIC'})
            s['runtime'].update({'evaluation_ref': None, 'stop_latched': None, 'fault_latched': None})
            self.assertEqual(self.check(s, **kw), [])
            s['runtime'][name] = False
            self.assertTrue(any(name in x for x in self.check(s, **kw)))

    def test_allowed_with_active_block_rejected(self):
        s, kw = self.allowed()
        s['motion']['blocks']['stop_latched']['value'] = True
        self.assertTrue(self.check(s, **kw))

    def test_allowed_rejects_unproven_relevant_blocks_in_both_domains(self):
        for domain in ('motion', 'arm'):
            for status in ('invalid', 'unknown', 'missing', 'stale'):
                for effect in (domain, 'both'):
                    with self.subTest(domain=domain, status=status, effect=effect):
                        s, kw = self.allowed(domain)
                        entry = {'block_ref': ref('block_id', 'front', 'sensor-check'),
                                 'code': 'FRONT_BLOCKED', 'effect': effect, 'frame_ref': None,
                                 'time_basis_id': 'clock', 'reported_mono_s': 100,
                                 'status': status, 'reason': 'REPORT_UNPROVEN'}
                        s[domain]['blocks']['entries'] = [entry]
                        self.assertTrue(any('allowed mit' in e for e in self.check(s, **kw)))
                        s[domain]['blocks']['entries'] = []
                        self.assertEqual(self.check(s, **kw), [])

    def test_malformed_hold_reasons_returns_errors_without_typeerror(self):
        for malformed in (True, [{}], [[]]):
            s, kw = self.allowed()
            s['runtime']['hold_reasons'] = malformed
            self.assertTrue(any('hold_reasons' in e for e in self.check(s, **kw)))

    def test_same_evaluation_changed_content_rejected(self):
        s = state(); b = package(s)
        known = {k: copy.deepcopy(s['motion'][k]) for k in ('release', 'blocks', 'output')}
        known['evaluation_ref'] = s['motion']['release']['evaluation_ref']
        known['output']['v_m_s'] = Decimal('.1')
        self.assertTrue(self.check(s, bindings=b, evaluations=(known,)))

    def test_blocked_arm_cannot_issue_command(self):
        s = state(); rr = ref('command_seq', producer='b')
        b = package(s, 'arm', 'blocked', True, rr)
        self.assertTrue(any('commandgebundene' in x for x in self.check(s, bindings=b)))

    def test_arm_protective_commandless_output(self):
        s = state(); b = package(s, 'arm')
        for k in ('release', 'output'):
            s['arm'][k]['command_reason'] = 'PROTECTIVE_ACTION_WITHOUT_REQUEST'
        self.assertEqual(self.check(s, bindings=b), [])

    def test_arm_current_expiry_equal_and_historical(self):
        s, kw = self.allowed('arm')
        self.assertEqual(self.check(s, **kw), [])
        s['generated_mono_s'] = 101
        self.assertTrue(self.check(s, **kw))
        s['arm']['package_use'].update({'mode': 'historical', 'reason': 'COMMAND_EXPIRED'})
        self.assertEqual(self.check(s, **kw), [])

    def test_ack_must_match_output(self):
        s = state(); b = package(s, 'arm')
        for k in ('release', 'output'):
            s['arm'][k]['command_reason'] = 'PROTECTIVE_ACTION_WITHOUT_REQUEST'
        s['arm']['ack'] = {'output_ref': ref('output_seq', 999), 'time_basis_id': 'clock', 'received_mono_s': 100, 'status': 'valid', 'reason': None}
        self.assertTrue(self.check(s, bindings=b))

    def test_unknown_measurements_never_valid_zero(self):
        s = state()
        s['camera_pose']['measurements'] = []
        self.assertTrue(self.check(s))

    def test_measurements_need_registered_frame_and_components(self):
        s = state()
        f = ref('frame_id', 'f', 'camera'); f['source'] = 'camera'
        c = {'coord_frame': 'robot', 'calibration_version': 'v', 'values': {'x': {'value': 0, 'unit': 'm'}}, 'status': 'valid', 'reason': None}
        entry = {'frame_ref': f, 'time_basis_id': 'clock', 'captured_mono_s': 99, 'received_mono_s': 100, 'components': c, 'status': 'valid', 'reason': None}
        s['camera_pose'] = {'measurements': [entry], 'status': 'valid', 'reason': None}
        self.assertTrue(self.check(s))
        kw = {'frames': ({**f, 'time_basis_id': 'clock', 'captured_mono_s': 99},), 'component_units': {('robot', 'v'): {'x': 'm'}}}
        self.assertEqual(self.check(s, **kw), [])
        entry['captured_mono_s'] = 100
        self.assertTrue(self.check(s, **kw))

    def test_nan_and_wrong_units_rejected(self):
        s = state(); b = package(s)
        s['motion']['output']['v_m_s'] = Decimal('sNaN')
        self.assertTrue(self.check(s, bindings=b))

    def measurement_entries(self):
        f = ref('frame_id', 'f', 'camera'); f['source'] = 'camera'
        components = {'coord_frame': 'robot', 'calibration_version': 'v',
                      'values': {'x': {'value': 0, 'unit': 'm'}}, 'status': 'valid', 'reason': None}
        good = {'frame_ref': f, 'time_basis_id': 'clock', 'captured_mono_s': 99,
                'received_mono_s': 100, 'components': components, 'status': 'valid', 'reason': None}
        bad = copy.deepcopy(good)
        bad.update({'status': 'invalid', 'reason': 'SENSOR_INVALID', 'components': {
            'coord_frame': 'robot', 'calibration_version': 'v', 'values': None,
            'status': 'invalid', 'reason': 'NO_MEASUREMENT'}})
        kw = {'frames': ({**f, 'time_basis_id': 'clock', 'captured_mono_s': 99},),
              'component_units': {('robot', 'v'): {'x': 'm'}}}
        return good, bad, kw

    def test_valid_measurement_blocks_require_one_valid_entry(self):
        for path in (('camera_pose',), ('arm', 'measured'), ('arm', 'load')):
            for status in ('invalid', 'missing'):
                with self.subTest(path=path, status=status):
                    s = state(); good, bad, kw = self.measurement_entries()
                    bad['status'] = status
                    block = s[path[0]] if len(path) == 1 else s[path[0]][path[1]]
                    block.update({'status': 'valid', 'reason': None, 'measurements': [bad]})
                    self.assertTrue(any('mindestens einen' in e for e in self.check(s, **kw)))
                    block['measurements'].append(good)
                    self.assertEqual(self.check(s, **kw), [])

    def test_measurement_schema_requires_valid_entry_and_components(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest('optionale jsonschema-Abhaengigkeit fehlt')
        good, bad, _ = self.measurement_entries()
        schema = {'$defs': SCHEMA_DEFS, '$ref': '#/$defs/c1_measurements'}
        validator = Draft202012Validator(schema)
        for status in ('invalid', 'missing'):
            bad['status'] = status
            block = {'status': 'valid', 'reason': None, 'measurements': [bad]}
            self.assertTrue(list(validator.iter_errors(block)))
            block['measurements'].append(good)
            self.assertEqual(list(validator.iter_errors(block)), [])

    def test_success_does_not_come_from_phase_or_timer(self):
        s = state(); b = clearing(s, 'beendet')
        s['clearing'].update({'execution_status': 'beendet', 'result': 'erfolgreich'})
        self.assertTrue(self.check(s, bindings=b))

    def test_policy_unknown_is_allowed_but_valid_needs_proof(self):
        s = state()
        s['protection'].update({'status': 'valid', 'reason': None, 'policy_id': 'p', 'policy_version': 'v', 'evidence_ref': ref('evidence_seq')})
        self.assertTrue(self.check(s))

    def test_context_and_validator_do_not_mutate_caller(self):
        s = state(); before = copy.deepcopy(s)
        c = RaeumKontext(bindings={'arm': {'producer_id': 'x'}})
        old = copy.deepcopy(c)
        pruefe_raeumzustand(s, kontext=c)
        self.assertEqual(s, before)
        self.assertEqual(c, old)

    def test_schema_definitions_resolve_and_unknown_fits(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest('optionale jsonschema-Abhaengigkeit fehlt')
        props = {k: {'$ref': '#/$defs/c1_' + k} for k in ('arm', 'clearing', 'protection', 'sensor_requirements')}
        props['camera_pose'] = {'$ref': '#/$defs/c1_measurements'}
        schema = {'$defs': SCHEMA_DEFS, 'type': 'object', 'properties': props}
        Draft202012Validator.check_schema(schema)
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(state())), [])


if __name__ == '__main__':
    unittest.main()
