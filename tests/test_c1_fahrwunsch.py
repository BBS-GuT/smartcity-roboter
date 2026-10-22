#!/usr/bin/env python3
"""C1k / BBS #152: VORBEREITUNG, noch keine Produktimplementierung.

Geplanter oeffentlicher API-Vertrag (Namen vor Umsetzung mit O abgleichen):
* pruefe_fahrwunsch(dict) -> Fehlerliste; dieselbe Definition wird unter
  motion.request benutzt. contract_version=SCHEMA_VERSION='2.0', exakt 13 Felder.
* fahrwunsch_als_json(dict) / lade_fahrwunsch_json(text) -> strikter separater
  JSON-Rundlauf; ValueError bei Fehlern. Exakten #149-Pfad wiederverwenden.
* FahrwunschAnnahme(**bindung): robot_id, producer_id, producer_boot_id,
  time_basis_id, bind_mono_s, max_duration_s explizit; None bleibt unbestaetigt.
  Kein Standardbudget, keine Bindung aus Nachrichten oder C-Zustandskopf.
* annehmen(dict, *, jetzt_mono_s), annehmen_json(text, *, jetzt_mono_s)
  -> neues Diagnose-dict mit status, reason, verwendbar, neu, kontext,
     angenommen, hoechststand. Die letzten beiden sind abgetrennte vollstaendige
     Requestkopien oder None, nicht bloss Sequenzen. status beschreibt den Eingang
     (accepted/duplicate/expired/replay/invalid/unknown). verwendbar und neu sind
     nur bei frischer neuer Annahme true; kein Freigabe-/Motorfeld.
  aktueller_wunsch(*, jetzt_mono_s) -> isolierte aktuelle Requestkopie oder None;
  prueft Frist und Ueberholung erneut, unabhaengig vom letzten Eingangsergebnis.
* binde(**vollstaendige_bindung): ausdruecklicher bestaetigter A-/B-Kontextwechsel,
  Vergleichspaare neu initialisieren; alte Eingangsstarts koennen nicht umschalten.
  C-boot_id ist absichtlich kein Parameter. Keine C-Neustart-Resetfunktion.

Umsetzung NACH zweiter Freigabe und Uebernahme #149/#150: Requestdefinition in
bestehendem Modul/Schema $defs/fahrwunsch teilen, keine Parallelvalidierung.
Zuerst Struktur/Bindung/exakte Zeiten und Budget/Regression pruefen, dann nur
ansonsten gueltige neue Sequenz im HWM speichern; Ablauf entscheidet danach
ueber Annahmepaar und Verwendbarkeit. HWM-Inhalt und Annahmepaar deep-copyen;
Objektfeldreihenfolge ist irrelevant. Ungueltige hohe Werte vergiften nichts.
Nur motion.request der sieben aktiven Fixtures und notwendige bisherige
Request-Testaufbauten anpassen; keine fremden Assertions/Adapter/Motorlogik.

Vorbereitung: FixtureSelbstkontrolle laeuft ohne neue API. Die uebrigen Klassen
scheitern am fehlenden API-/Schema-Einstieg explizit, keine erwarteten Fehler
oder Skips. Spaeter alle Klassen, bisherige C1-Suite, Vertragssuite und D1
ausfuehren. Schema nutzt vorhandenes requirements-test.txt, kein neues Paket.
"""
import copy
from decimal import Decimal, Inexact, Rounded, localcontext
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
import grundbetrieb_vertrag as V  # noqa: E402

FIXTURES = ROOT / 'tests' / 'fixtures' / 'c1_requests'
FIELDS = set(('contract_version robot_id producer_id producer_boot_id request_seq '
              'request_id time_basis_id generated_mono_s valid_until_mono_s '
              'v_m_s w_rad_s maneuver hold_reasons').split())
BINDUNG = dict(robot_id='RM02', producer_id='synthetisch-b',
               producer_boot_id='synthetisch-b-start-001',
               time_basis_id='synthetisch-uhr-001', bind_mono_s=99,
               max_duration_s=2)


def fixture(name='frisch8'):
    # Nur Fixtureaufbau. Oeffentlicher Produkt-JSON-Pfad wird separat geprueft.
    return json.loads((FIXTURES / (name + '.json')).read_text(encoding='utf-8'),
                      parse_float=Decimal)


def request(**changes):
    d = fixture()
    d.update(changes)
    return d


def required_api():
    names = ('pruefe_fahrwunsch', 'fahrwunsch_als_json', 'lade_fahrwunsch_json',
             'FahrwunschAnnahme', 'zeit_ns', 'sekunden_aus_ns')
    missing = [name for name in names if not hasattr(V, name)]
    if missing:
        raise AssertionError('Vorbereitung: Produkt-API noch ausstehend: ' + ', '.join(missing))


class FixtureSelbstkontrolle(unittest.TestCase):
    def test_genau_fuenf_vollstaendige_synthetische_nachrichten(self):
        self.assertEqual(len(list(FIXTURES.glob('*.json'))), 5)
        for path in FIXTURES.glob('*.json'):
            with self.subTest(datei=path.name):
                d = fixture(path.stem)
                self.assertEqual(set(d), FIELDS)
                self.assertEqual(d['contract_version'], '2.0')
                self.assertTrue(d['producer_id'].startswith('synthetisch-'))
                self.assertIsInstance(d['generated_mono_s'], Decimal)

    def test_umordnungsdaten_sind_tatsaechlich_frisch_bzw_abgelaufen(self):
        for name, fresh in (('frisch8', True), ('abgelaufen10', False),
                            ('frisch9', True), ('frisch11', True)):
            with self.subTest(name=name):
                d = fixture(name)
                self.assertEqual(d['generated_mono_s'] <= 101 < d['valid_until_mono_s'], fresh)


class RequestStruktur(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        required_api()

    def test_alle_fixtures_strukturell_gueltig(self):
        for path in FIXTURES.glob('*.json'):
            with self.subTest(path=path.name):
                self.assertEqual(V.pruefe_fahrwunsch(fixture(path.stem)), [])

    def test_jedes_der_13_felder_verpflichtend(self):
        for field in FIELDS:
            with self.subTest(field=field):
                d = request()
                del d[field]
                self.assertTrue(V.pruefe_fahrwunsch(d))

    def test_kein_motorfeld_oder_paralleles_versionsregime(self):
        for changes in ({'motor_enabled': True}, {'contract_version': '1.0'},
                        {'contract_version': 'c1f-draft'}, {'request_seq': True},
                        {'request_seq': -1}, {'request_seq': Decimal('8.5')},
                        {'hold_reasons': ['RED_LIGHT', 'RED_LIGHT']}):
            with self.subTest(changes=changes):
                self.assertTrue(V.pruefe_fahrwunsch(request(**changes)))

    def test_zeitfehler_auch_nichtendliche_decimal_ohne_absturz(self):
        values = (Decimal('NaN'), Decimal('sNaN'), Decimal('Infinity'),
                  Decimal('-Infinity'), Decimal('-1'), Decimal('100.0000000001'),
                  Decimal('9223372036.854775808'), 100.0, True, '100')
        for field in ('generated_mono_s', 'valid_until_mono_s'):
            for value in values:
                with self.subTest(field=field, value=repr(value)):
                    self.assertTrue(V.pruefe_fahrwunsch(request(**{field: value})))
                    with self.assertRaises(ValueError):
                        V.fahrwunsch_als_json(request(**{field: value}))

    def test_separater_oeffentlicher_json_rundlauf(self):
        for path in FIXTURES.glob('*.json'):
            d = V.lade_fahrwunsch_json(path.read_text(encoding='utf-8'))
            self.assertEqual(d, fixture(path.stem))
            text = V.fahrwunsch_als_json(d)
            self.assertEqual(V.lade_fahrwunsch_json(text), d)
            self.assertIsInstance(V.lade_fahrwunsch_json(text)['generated_mono_s'], Decimal)

    def test_json_exponent_und_raster_ohne_floatvorstufe(self):
        text = (FIXTURES / 'frist120.json').read_text(encoding='utf-8')
        d = V.lade_fahrwunsch_json(text.replace('120.20', '1.202e2'))
        self.assertEqual(V.zeit_ns(d['valid_until_mono_s']), 120200000000)
        for token in ('120.2000000001', 'NaN', 'Infinity', '-Infinity', 'true', '"120.20"'):
            with self.subTest(token=token), self.assertRaises(ValueError):
                V.lade_fahrwunsch_json(text.replace('120.20', token))


class Annahme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        required_api()

    def setUp(self):
        self.ctx = V.FahrwunschAnnahme(**BINDUNG)

    def take(self, d=None, now=101):
        return self.ctx.annehmen(request() if d is None else d, jetzt_mono_s=now)

    def assert_result(self, r, status, binding=None):
        self.assertEqual(r['status'], status)
        self.assertTrue(r['reason'])
        self.assertEqual(r['verwendbar'], status == 'accepted')
        self.assertEqual(r['neu'], status == 'accepted')
        self.assertEqual(r['kontext'], BINDUNG if binding is None else binding)
        self.assertNotIn('motor_enabled', r)

    def test_frischer_wunsch_ist_datenannahme(self):
        r = self.take()
        self.assert_result(r, 'accepted')
        self.assertEqual(r['angenommen'], request())
        self.assertEqual(r['hoechststand'], request())
        self.assertEqual(self.ctx.aktueller_wunsch(jetzt_mono_s=101), request())

    def test_request_id_ist_opak(self):
        self.assert_result(self.take(request(request_id='RM01-andere-uhr-seq-999')), 'accepted')

    def test_fehlender_kontext_oder_budget_ist_unbekannt(self):
        for field in BINDUNG:
            with self.subTest(field=field):
                binding = dict(BINDUNG, **{field: None})
                ctx = V.FahrwunschAnnahme(**binding)
                r = ctx.annehmen(request(), jetzt_mono_s=101)
                self.assertEqual(r['status'], 'unknown')
                self.assertFalse(r['verwendbar'])
                self.assertIsNone(r['hoechststand'])
                self.assertEqual(r['kontext'], binding)
                self.assertTrue(r['reason'])

    def test_fremde_identitaeten_binden_nicht_automatisch(self):
        for field, value in (('robot_id', 'RM01'), ('producer_id', 'fremd'),
                             ('producer_boot_id', 'neuer-start'), ('time_basis_id', 'fremde-uhr')):
            with self.subTest(field=field):
                r = self.take(request(**{field: value}))
                self.assert_result(r, 'invalid')
                self.assertIsNone(r['hoechststand'])
        self.assert_result(self.take(), 'accepted')

    def test_duplikat_und_feldreihenfolge_ohne_neue_annahme(self):
        self.take()
        r = self.take(dict(reversed(list(request().items()))))
        self.assert_result(r, 'duplicate')
        self.assertEqual(r['angenommen'], request())
        self.assertIsNone(self.ctx.aktueller_wunsch(jetzt_mono_s=102))

    def test_gleiche_sequenz_anderer_inhalt_ist_widerspruch(self):
        self.take()
        for changes in ({'v_m_s': Decimal('.1')}, {'valid_until_mono_s': Decimal('101.9')},
                        {'request_id': 'anders'}, {'hold_reasons': []}):
            with self.subTest(changes=changes):
                self.assert_result(self.take(request(**changes)), 'invalid')
                self.assertEqual(self.ctx.aktueller_wunsch(jetzt_mono_s=101), request())

    def test_8_abgelaufene10_frische9_11(self):
        self.assert_result(self.take(fixture('frisch8')), 'accepted')
        expired = self.take(fixture('abgelaufen10'))
        self.assert_result(expired, 'expired')
        self.assertEqual(expired['angenommen']['request_seq'], 8)
        self.assertEqual(expired['hoechststand']['request_seq'], 10)
        self.assertIsNone(self.ctx.aktueller_wunsch(jetzt_mono_s=101))
        replay = self.take(fixture('frisch9'))
        self.assert_result(replay, 'replay')
        self.assertEqual(replay['hoechststand'], expired['hoechststand'])
        self.assertIsNone(self.ctx.aktueller_wunsch(jetzt_mono_s=101))
        self.assert_result(self.take(fixture('frisch11')), 'accepted')

    def test_hwm_duplikat_und_widerspruch_auch_nach_ablauf(self):
        self.take()
        self.take(fixture('abgelaufen10'))
        self.assert_result(self.take(fixture('abgelaufen10')), 'duplicate')
        bad = fixture('abgelaufen10')
        bad['v_m_s'] = Decimal('.2')
        self.assert_result(self.take(bad), 'invalid')
        self.assert_result(self.take(fixture('frisch9'), now=103), 'replay')

    def test_ungueltige_hohe_eingaenge_vergiften_keine_vergleiche(self):
        variants = ({'robot_id': 'RM01'}, {'producer_boot_id': 'fremd'},
                    {'time_basis_id': 'fremd'}, {'generated_mono_s': 102, 'valid_until_mono_s': 103},
                    {'valid_until_mono_s': 104}, {'generated_mono_s': Decimal('99.9')},
                    {'generated_mono_s': Decimal('NaN')})
        for changes in variants:
            with self.subTest(changes=changes):
                self.ctx = V.FahrwunschAnnahme(**BINDUNG)
                before = self.take()
                bad = self.take(request(request_seq=999, **changes))
                self.assert_result(bad, 'invalid')
                self.assertEqual(bad['hoechststand'], before['hoechststand'])
                self.assertEqual(bad['angenommen'], before['angenommen'])
                self.assert_result(self.take(fixture('frisch9')), 'accepted')

    def test_regression_gegen_hwm_statt_nur_annahmepaar(self):
        self.take()
        self.take(fixture('abgelaufen10'))
        bad = request(request_seq=11, generated_mono_s=Decimal('100.3'))
        self.assert_result(self.take(bad), 'invalid')
        for generated in ('100.4', '100.5'):
            with self.subTest(generated=generated):
                self.ctx = V.FahrwunschAnnahme(**BINDUNG)
                self.take()
                self.take(fixture('abgelaufen10'))
                self.assert_result(self.take(request(request_seq=11,
                                   generated_mono_s=Decimal(generated))), 'accepted')

    def test_exakte_frist_und_maximaldauer(self):
        d = fixture('frist120')
        binding = dict(BINDUNG, max_duration_s=Decimal('.20'))
        for now, status in (('120.199999999', 'accepted'), ('120.20', 'expired'),
                            ('120.200000001', 'expired')):
            with self.subTest(now=now):
                ctx = V.FahrwunschAnnahme(**binding)
                self.assertEqual(ctx.annehmen(d, jetzt_mono_s=Decimal(now))['status'], status)
        d['valid_until_mono_s'] = Decimal('120.200000001')
        ctx = V.FahrwunschAnnahme(**binding)
        r = ctx.annehmen(d, jetzt_mono_s=Decimal('120.05'))
        self.assertEqual(r['status'], 'invalid')
        self.assertIsNone(r['hoechststand'])

    def test_json_und_direktpfad_gleiche_datenannahme(self):
        text = (FIXTURES / 'frist120.json').read_text(encoding='utf-8')
        binding = dict(BINDUNG, max_duration_s=Decimal('.20'))
        with localcontext() as dc:
            dc.prec = 3
            dc.traps[Inexact] = dc.traps[Rounded] = True
            direct = V.FahrwunschAnnahme(**binding).annehmen(
                fixture('frist120'), jetzt_mono_s=Decimal('120.199999999'))
            wire = V.FahrwunschAnnahme(**binding).annehmen_json(
                text, jetzt_mono_s=Decimal('120.199999999'))
        self.assertEqual(direct, wire)
        self.assertEqual(wire['status'], 'accepted')

    def test_ungueltiges_jetzt_oder_budget_erzeugt_keinen_hwm(self):
        bad_times = (None, True, 101.0, '101', Decimal('NaN'), Decimal('sNaN'),
                     Decimal('Infinity'), Decimal('-Infinity'), Decimal('-1'),
                     Decimal('101.0000000001'), Decimal('9223372036.854775808'))
        for value in bad_times:
            with self.subTest(now=repr(value)):
                r = V.FahrwunschAnnahme(**BINDUNG).annehmen(request(), jetzt_mono_s=value)
                self.assertIn(r['status'], ('invalid', 'unknown'))
                self.assertFalse(r['verwendbar'])
                self.assertIsNone(r['hoechststand'])
        for value in (0, -1, True, 2.0, Decimal('NaN'), Decimal('sNaN')):
            with self.subTest(budget=repr(value)):
                ctx = V.FahrwunschAnnahme(**dict(BINDUNG, max_duration_s=value))
                r = ctx.annehmen(request(), jetzt_mono_s=101)
                self.assertEqual(r['status'], 'invalid')
                self.assertIsNone(r['hoechststand'])

    def test_bindung_strikt_danach_auch_bei_noch_frischem_puffer(self):
        binding = dict(BINDUNG, bind_mono_s=Decimal('100.1'))
        self.ctx.binde(**binding)
        self.assert_result(self.take(), 'invalid', binding)
        self.assert_result(self.take(request(generated_mono_s=Decimal('100.1'))), 'invalid', binding)
        self.assert_result(self.take(request(generated_mono_s=Decimal('100.100000001'))), 'accepted', binding)

    def test_b_startwechsel_nur_durch_explizite_neubindung(self):
        self.take()
        new = request(producer_boot_id='synthetisch-b-start-002', request_seq=0)
        self.assert_result(self.take(new), 'invalid')
        self.ctx.binde(**dict(BINDUNG, producer_boot_id=new['producer_boot_id']))
        self.assertEqual(self.take(new)['status'], 'accepted')
        self.assertEqual(self.take(request(request_seq=999))['status'], 'invalid')

    def test_c_neustart_erhaelt_b_bindung_und_hwm(self):
        self.take()
        self.take(fixture('abgelaufen10'))
        for c_boot, c_seq in (('synthetisch-c-alt', 99), ('synthetisch-c-neu', 0)):
            # C-Kopf ist nur Einbettung, wird niemals zur A-/B-Neubindung benutzt.
            state = {'boot_id': c_boot, 'seq': c_seq, 'motion': {'request': fixture('frisch9')}}
            self.assert_result(self.take(state['motion']['request']), 'replay')

    def test_original_und_ergebnis_mutation_erreicht_keinen_internen_zustand(self):
        d = request()
        saved = copy.deepcopy(d)
        result = self.take(d)
        d['hold_reasons'].clear()
        d['request_seq'] = 999
        result['angenommen']['hold_reasons'].clear()
        result['hoechststand']['request_seq'] = 999
        result['kontext']['producer_boot_id'] = 'manipuliert'
        current = self.ctx.aktueller_wunsch(jetzt_mono_s=101)
        self.assertEqual(current, saved)
        current['hold_reasons'].clear()
        self.assertEqual(self.ctx.aktueller_wunsch(jetzt_mono_s=101), saved)
        self.assert_result(self.take(saved), 'duplicate')


class SchemaUndEinbettung(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        required_api()
        import jsonschema
        cls.validator = jsonschema.Draft202012Validator
        cls.schema = json.loads((ROOT / 'schemas' / 'grundbetrieb-v2.schema.json').read_text())

    def test_standalone_schema_nutzt_geteilte_definition(self):
        self.validator.check_schema(self.schema)
        separate = {'$schema': self.schema['$schema'], '$defs': self.schema['$defs'],
                    '$ref': '#/$defs/fahrwunsch'}
        for path in FIXTURES.glob('*.json'):
            self.assertEqual(list(self.validator(separate).iter_errors(fixture(path.stem))), [])
        bad = request(motor_enabled=True)
        self.assertTrue(list(self.validator(separate).iter_errors(bad)))

    def test_oeffentlicher_zustands_json_erhaelt_request_unveraendert(self):
        state = V.lade_json((ROOT / 'tests/fixtures/grundbetrieb/test.json').read_text())
        d = fixture('frist120')
        state['motion']['request'] = copy.deepcopy(d)
        self.assertEqual(V.pruefe(state), [])
        self.assertEqual(list(self.validator(self.schema).iter_errors(state)), [])
        roundtrip = V.lade_json(V.als_json(state))
        self.assertEqual(roundtrip['motion']['request'], d)
        self.assertEqual(V.lade_fahrwunsch_json(V.fahrwunsch_als_json(d)), d)
        state['boot_id'], state['seq'] = 'synthetisch-c-neustart', 0
        for key in ('last_publish_requested_seq', 'last_broker_ack_seq', 'last_broker_ack_mono_s'):
            state['communication'][key] = None
        for detail in state['details']:
            # Nur Ausgabekontext darf bei C-Neustart wechseln, nie Ursprungsdaten.
            if 'state_boot_id' in detail:
                detail['state_boot_id'] = state['boot_id']
        self.assertEqual(V.lade_json(V.als_json(state))['motion']['request'], d)
        state['motion']['request'] = None
        self.assertEqual(V.pruefe(state), [])

    def test_eingebettet_und_separat_weisen_fehlende_requestfelder_zurueck(self):
        state = V.lade_json((ROOT / 'tests/fixtures/grundbetrieb/test.json').read_text())
        for field in FIELDS:
            with self.subTest(field=field):
                d = fixture('frist120')
                del d[field]
                state['motion']['request'] = d
                self.assertTrue(V.pruefe_fahrwunsch(d))
                self.assertTrue(V.pruefe(state))
                self.assertTrue(list(self.validator(self.schema).iter_errors(state)))


if __name__ == '__main__':
    unittest.main()
