"""C1l #153: vorbereitete Vertragstests, noch keine Laufzeitimplementierung.

Geplanter API-Einstieg: pruefe_historie(history, *, robot_id, map_version,
time_basis_id, generated_mono_s, kontext=None, vorher=None) -> Fehlerliste.
Details des expliziten synthetischen Kontextes: fixtures/c1_history/README.md.
Kein Skip/ExpectedFailure fuer die auf der Vorbereitungsbasis fehlende API.
"""
import copy
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
import grundbetrieb_vertrag as V  # noqa: E402

FIXTURES = Path(__file__).parent / 'fixtures' / 'c1_history'


def fixture(name):
    # Nur isolierte Testdaten, kein zweiter oeffentlicher JSON-Zeitpfad.
    return json.loads((FIXTURES / (name + '.json')).read_text(encoding='utf-8'),
                      parse_float=Decimal)


def snapshot(history):
    return dict(robot_id='RM01', map_version='demo-history-map-v1',
                time_basis_id='demo-clock-a', generated_mono_s=Decimal('100'),
                history=copy.deepcopy(history))


class FixtureVorbereitung(unittest.TestCase):
    """Prueft nur vorbereitete Eingaben; kein bestandener Produktnachweis."""

    def test_synthetischer_kontext_ist_von_kandidaten_getrennt(self):
        context = fixture('context')
        self.assertEqual(context['map']['map_version'], 'demo-history-map-v1')
        self.assertEqual(len(context['map']['sections']), 3)
        self.assertNotIn('entries', context)
        self.assertTrue(context['binding']['initialized'])

    def test_zwei_abschnitte_und_getrennte_startkennung(self):
        history = fixture('two')
        self.assertEqual([e['entry_seq'] for e in history['entries']], [0, 1])
        self.assertEqual(history['producer_boot_id'], 'demo-b-history-a')
        self.assertEqual(history['entries'][1]['approach_from'], 'demo-B')

    def test_kapazitaetsbeispiele_16_und_17(self):
        before, after = fixture('full16'), fixture('after17')
        self.assertEqual([e['entry_seq'] for e in before['entries']], list(range(16)))
        self.assertEqual([e['entry_seq'] for e in after['entries']], list(range(1, 17)))
        self.assertEqual(after['dropped_entries'], 1)
        self.assertEqual(before['entries'][1:], after['entries'][:-1])


class HistorienVertrag(unittest.TestCase):
    def setUp(self):
        self.history = fixture('two')
        self.context = fixture('context')
        self.outer = snapshot(self.history)
        self.outer.pop('history')

    def check(self, history=None, *, context=True, vorher=None, **outer):
        candidate = self.history if history is None else history
        args = dict(self.outer, **outer)
        # Fehlende API bleibt ein sichtbarer Vorbereitungsfehler, kein Skip.
        check = getattr(V, 'pruefe_historie', None)
        self.assertTrue(callable(check), 'C1l-API noch nicht implementiert/freigegeben')
        original = copy.deepcopy(candidate)
        errors = check(candidate, kontext=self.context if context else None,
                       vorher=vorher, **args)
        self.assertEqual(candidate, original, 'Pruefung darf keinen Verlauf erzeugen/veraendern')
        self.assertIsInstance(errors, list)
        return errors

    def good(self, history=None, **kwargs):
        self.assertEqual(self.check(history, **kwargs), [])

    def bad(self, history=None, **kwargs):
        self.assertTrue(self.check(history, **kwargs))

    def test_gueltig_leer_und_zwei_bestaetigte_abschnitte(self):
        self.good(fixture('empty'))
        self.good()

    def test_missing_ist_nicht_gueltig_leer(self):
        history = fixture('empty')
        history.update(status='missing', reason='not_initialized', entries=None,
                       dropped_entries=None)
        self.good(history)
        history['entries'] = []
        self.bad(history)

    def test_unknown_ohne_kontext_ist_darstellbar(self):
        history = fixture('empty')
        history.update(status='unknown', reason='context_unconfirmed', entries=None,
                       dropped_entries=None)
        self.good(history, context=False)
        self.bad(context=False)

    def test_gueltig_braucht_bestaetigte_initialisierung(self):
        self.context['binding']['initialized'] = False
        self.bad(fixture('empty'))

    def test_16_und_17_abschluesse_mit_sichtbarem_verlust(self):
        self.good(fixture('full16'))
        self.good(fixture('after17'), vorher=snapshot(fixture('full16')))
        too_long = fixture('full16')
        too_long['entries'].append(fixture('after17')['entries'][-1])
        self.bad(too_long)

    def test_luecke_doppelte_und_ruecklaeufige_sequenz(self):
        for values in ([0, 2], [0, 0], [1, 0]):
            with self.subTest(values=values):
                history = fixture('two')
                for entry, value in zip(history['entries'], values):
                    entry['entry_seq'] = value
                self.bad(history)

    def test_zaehler_und_puffergroesse(self):
        for name, count in (('two', 1), ('after17', 0), ('after17', 2)):
            with self.subTest(name=name, count=count):
                history = fixture(name)
                history['dropped_entries'] = count
                self.bad(history)

    def test_zaehler_und_sequenz_sind_nichtnegative_ganze_zahlen(self):
        for value in (True, -1, Decimal('0.5'), '0'):
            with self.subTest(value=repr(value)):
                history = fixture('empty')
                history['dropped_entries'] = value
                self.bad(history)
                history = fixture('two')
                history['entries'][0]['entry_seq'] = value
                self.bad(history)

    def test_status_grund_und_nutzwerte_muessen_zusammenpassen(self):
        for changes in (dict(reason='capture_gap'), dict(entries=None),
                        dict(dropped_entries=None), dict(status='invented')):
            with self.subTest(changes=changes):
                history = fixture('two')
                history.update(changes)
                self.bad(history)

    def test_exakte_zeit_gleiche_zeit_ist_erlaubt(self):
        self.history['entries'][1]['confirmed_mono_s'] = Decimal('1.000000001')
        self.history['entries'][0]['confirmed_mono_s'] = Decimal('1.000000001')
        self.good()

    def test_zeit_regression_und_zukunft_um_eine_ns(self):
        for value in (Decimal('0.999999999'), Decimal('100.000000001')):
            with self.subTest(value=value):
                self.history['entries'][1]['confirmed_mono_s'] = value
                self.bad()

    def test_exakte_zeittypen_raster_bereich_und_sonderzahlen(self):
        for value in (True, 1.0, '1', Decimal('0.0000000001'),
                      Decimal('9223372036.854775808'), Decimal('NaN'),
                      Decimal('sNaN'), Decimal('Infinity'), Decimal('-Infinity')):
            with self.subTest(value=repr(value)):
                self.history['entries'][1]['confirmed_mono_s'] = value
                # NaN ist nicht gleich sich selbst: Kandidaten-Mutationskontrolle
                # separat fuer regulaere Werte; hier muss sauber Fehlerliste entstehen.
                check = getattr(V, 'pruefe_historie', None)
                self.assertTrue(callable(check), 'C1l-API noch nicht implementiert/freigegeben')
                self.assertTrue(check(self.history, kontext=self.context, vorher=None,
                                      **self.outer))

    def test_fremde_karte_uhr_und_produzentenbindung(self):
        for key, value in (('map_version', 'demo-other-map'),
                           ('time_basis_id', 'demo-other-clock'),
                           ('robot_id', 'RM02')):
            with self.subTest(key=key):
                self.bad(**{key: value})
        for key in ('producer_id', 'producer_boot_id', 'time_basis_id'):
            history = fixture('two')
            history[key] = 'demo-foreign'
            self.bad(history)

    def test_kartenkontext_nicht_aus_kandidaten_ableiten(self):
        for key in ('section', 'node', 'approach_from', 'exit_to'):
            with self.subTest(key=key):
                history = fixture('two')
                history['entries'][0][key] = 'demo-unregistered'
                self.bad(history)

    def test_capture_gap_bleibt_bis_bestaetigtem_b_reset(self):
        broken = fixture('empty')
        broken.update(status='invalid', reason='capture_gap', entries=None,
                      dropped_entries=None)
        self.good(broken)
        self.bad(fixture('empty'), vorher=snapshot(broken))
        self.bad(fixture('two'), vorher=snapshot(broken))
        reset = fixture('empty')
        reset['producer_boot_id'] = 'demo-b-history-b'
        self.bad(reset, vorher=snapshot(broken))
        self.context['binding']['producer_boot_id'] = 'demo-b-history-b'
        self.context['confirmed_new_history_start'] = True
        self.good(reset, vorher=snapshot(broken))

    def test_gleicher_b_start_darf_puffer_nicht_leeren(self):
        self.bad(fixture('empty'), vorher=snapshot(fixture('two')))

    def test_kartenwechsel_braucht_neuen_b_start(self):
        previous = snapshot(fixture('two'))
        self.context['map']['map_version'] = 'demo-history-map-v2'
        self.bad(fixture('empty'), vorher=previous, map_version='demo-history-map-v2')
        history = fixture('empty')
        history['producer_boot_id'] = 'demo-b-history-b'
        self.context['binding']['producer_boot_id'] = 'demo-b-history-b'
        self.context['confirmed_new_history_start'] = True
        self.good(history, vorher=previous, map_version='demo-history-map-v2')

    def test_uhrenwechsel_darf_keine_alten_zeiten_umetikettieren(self):
        self.history['time_basis_id'] = 'demo-clock-b'
        self.context['binding']['time_basis_id'] = 'demo-clock-b'
        self.bad(vorher=snapshot(fixture('two')), time_basis_id='demo-clock-b')

    def test_bekannte_herkunft_nicht_durch_null_verlieren(self):
        self.history.update(status='missing', reason='producer_unavailable',
                            entries=None, dropped_entries=None)
        self.good(vorher=snapshot(fixture('two')))
        self.history['producer_boot_id'] = None
        self.bad(vorher=snapshot(fixture('two')))


if __name__ == '__main__':
    unittest.main()
