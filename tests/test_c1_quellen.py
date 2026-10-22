#!/usr/bin/env python3
"""C1d (#14): Messwertquellen sind sensors-Schluessel, keine source_id-Aliase.

Aufruf: python tests/test_c1_quellen.py (ohne ROS, Broker oder Zusatzpakete).
Die Gegenproben veraendern jeweils nur eine Referenz einer gueltigen Kontrolle.
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
from c1_testbauwerte import lade_isoliertes_beispiel, synthetischer_raeumkontext

FIXTURES = ROOT / 'tests' / 'fixtures' / 'grundbetrieb'
# Explizite fachliche Pfade, unabhaengig von der Implementierung des Pruefers.
MESSWERTE = (
    ('motion', 'measured_v_m_s', 'odometry', Decimal('0.12')),
    ('motion', 'measured_w_rad_s', 'imu', Decimal('-0.2')),
    ('motion', 'odometry_distance_m', 'odometry', Decimal('1.5')),
    ('motion', 'heading_rad', 'imu', Decimal('0.4')),
    ('obstacles', 'front_clearance_m', 'lidar_0', Decimal('1.8')),
    ('diagnostics', 'battery_v', 'board', Decimal('12.1')),
)


def kontrolle():
    """Eigenes synthetisches Messbild; bestehende Fixturedateien bleiben unberuehrt.

    Zeit-/Strukturfelder werden aus der jeweils integrierten C1-Basis erhalten,
    insbesondere spaeter received_mono_s aus C1c. Keine gemessene Bewegung
    wird aus request/output gewonnen.
    """
    d = lade_isoliertes_beispiel((FIXTURES / 'fahrt.json').read_text(encoding='utf-8'))
    board = copy.deepcopy(d['sensors']['imu'])
    board.update(source_id='synthetic/board/voltage', frame_id=None, coord_frame=None)
    d['sensors']['board'] = board
    for bereich, feld, quelle, wert in MESSWERTE:
        d[bereich][feld] = {'value': wert, 'status': 'valid', 'source': quelle}
    return d


class Messwertquellen(unittest.TestCase):
    def setUp(self):
        self.d = kontrolle()
        self.assertEqual(V.pruefe(self.d), [], 'Positive Ausgangskontrolle')

    def abgelehnt(self, d, bereich, feld):
        fehler = V.pruefe(d)
        pfad = f'$.{bereich}.{feld}'
        self.assertTrue(any(f.startswith(pfad + ':') or f.startswith(pfad + '.')
                            for f in fehler), (pfad, fehler))
        with self.assertRaises(ValueError):
            V.als_json(d)
        with self.assertRaises(ValueError):
            V.lade_json(V._json_wert(d))

    def test_registrierte_schluessel_und_json_rundlauf(self):
        self.assertEqual(V.lade_json(V.als_json(self.d)), self.d)
        for bereich, feld, quelle, _ in MESSWERTE:
            with self.subTest(pfad=f'{bereich}.{feld}'):
                self.assertIn(quelle, self.d['sensors'])
                self.assertNotEqual(quelle, self.d['sensors'][quelle]['source_id'])

    def test_valid_ohne_aufloesbaren_schluessel(self):
        for bereich, feld, quelle, _ in MESSWERTE:
            for source in (None, '', 'nicht_registriert',
                           self.d['sensors'][quelle]['source_id']):
                with self.subTest(pfad=f'{bereich}.{feld}', source=source):
                    d = copy.deepcopy(self.d)
                    d[bereich][feld]['source'] = source
                    self.abgelehnt(d, bereich, feld)

    def test_source_fehlt_oder_hat_falschen_typ(self):
        for bereich, feld, _, _ in MESSWERTE:
            for source in (False, 7, [], {}):
                with self.subTest(pfad=f'{bereich}.{feld}', source=source):
                    d = copy.deepcopy(self.d)
                    d[bereich][feld]['source'] = source
                    self.abgelehnt(d, bereich, feld)
            with self.subTest(pfad=f'{bereich}.{feld}', source='fehlendes Feld'):
                d = copy.deepcopy(self.d)
                del d[bereich][feld]['source']
                self.abgelehnt(d, bereich, feld)

    def test_entfernte_registrierung_macht_referenz_ungueltig(self):
        for bereich, feld, quelle, _ in MESSWERTE:
            with self.subTest(pfad=f'{bereich}.{feld}'):
                d = copy.deepcopy(self.d)
                del d['sensors'][quelle]
                self.abgelehnt(d, bereich, feld)

    def test_umbenannter_schluessel_braucht_angepasste_referenz(self):
        for bereich, feld, quelle, _ in MESSWERTE:
            with self.subTest(pfad=f'{bereich}.{feld}'):
                d = copy.deepcopy(self.d)
                neu = 'registrierte_testquelle'
                d['sensors'][neu] = d['sensors'].pop(quelle)
                self.abgelehnt(d, bereich, feld)
                for b, f, q, _ in MESSWERTE:
                    if q == quelle:
                        d[b][f]['source'] = neu
                for detail in d['details']:
                    if detail['source'] == quelle:
                        detail['source'] = neu  # Auch Diagnose-Details benutzen sensors-Schluessel.
                self.assertEqual(V.pruefe(d), [])

    def test_technische_id_umbenennen_aendert_keine_referenz(self):
        d = copy.deepcopy(self.d)
        for quelle in d['sensors'].values():
            quelle['source_id'] = 'synthetic/andere-technische-id'
        self.assertEqual(V.pruefe(d), [])

    def test_auch_gueltiger_zahlenwert_null_braucht_quelle(self):
        for bereich, feld, _, _ in MESSWERTE:
            with self.subTest(pfad=f'{bereich}.{feld}'):
                d = copy.deepcopy(self.d)
                d[bereich][feld]['value'] = 0.0
                self.assertEqual(V.pruefe(d), [])
                d[bereich][feld]['source'] = None
                self.abgelehnt(d, bereich, feld)

    def test_nicht_verfuegbar_bleibt_null_mit_status(self):
        for bereich, feld, quelle, _ in MESSWERTE:
            for status in ('unknown', 'invalid', 'stale', 'missing'):
                for source in (None, quelle):
                    with self.subTest(pfad=f'{bereich}.{feld}', status=status, source=source):
                        d = copy.deepcopy(self.d)
                        d[bereich][feld].update(value=None, status=status, source=source)
                        self.assertEqual(V.pruefe(d), [])
                        d[bereich][feld]['value'] = 0.0
                        self.abgelehnt(d, bereich, feld)

    def test_valid_braucht_weiterhin_einen_messwert(self):
        for bereich, feld, _, _ in MESSWERTE:
            with self.subTest(pfad=f'{bereich}.{feld}'):
                d = copy.deepcopy(self.d)
                d[bereich][feld]['value'] = None
                self.abgelehnt(d, bereich, feld)

    def test_angegebene_quelle_nutzt_auch_ohne_messwert_nur_schluessel(self):
        for bereich, feld, quelle, _ in MESSWERTE:
            for status in ('unknown', 'invalid', 'stale', 'missing'):
                for source in ('nicht_registriert', self.d['sensors'][quelle]['source_id']):
                    with self.subTest(pfad=f'{bereich}.{feld}', status=status, source=source):
                        d = copy.deepcopy(self.d)
                        d[bereich][feld].update(value=None, status=status, source=source)
                        self.abgelehnt(d, bereich, feld)

    def test_fahrbefehl_ersetzt_keine_fehlende_messung(self):
        kontext = synthetischer_raeumkontext()
        d = V.lade_json((FIXTURES / 'fahrt.json').read_text(encoding='utf-8'), raeum_kontext=kontext)
        for feld in ('measured_v_m_s', 'measured_w_rad_s'):
            d['motion'][feld].update(value=None, status='missing', source=None)
        self.assertNotEqual(d['motion']['output']['v_m_s'], 0)
        vorher = copy.deepcopy(d)
        self.assertEqual(V.pruefe(d, raeum_kontext=kontext), [])
        self.assertEqual(V.lade_json(V.als_json(d, raeum_kontext=kontext), raeum_kontext=kontext), vorher)
        self.assertEqual(d, vorher)

    def test_alle_fixtures_verwenden_registrierte_messwertquellen(self):
        for datei in sorted(FIXTURES.glob('*.json')):
            d = lade_isoliertes_beispiel(datei.read_text(encoding='utf-8'))
            for bereich, feld, _, _ in MESSWERTE:
                m = d[bereich][feld]
                if m['status'] == 'valid':
                    with self.subTest(datei=datei.name, pfad=f'{bereich}.{feld}'):
                        self.assertIsInstance(m['source'], str)
                        self.assertTrue(m['source'])
                        self.assertIn(m['source'], d['sensors'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
