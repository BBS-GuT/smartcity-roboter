#!/usr/bin/env python3
"""C1b (#12): echte UTC-Kalenderwerte, ohne ROS oder Broker.

Aufruf aus der Projektwurzel: python tests/test_c1_zeitformat.py
"""
import copy
from decimal import Decimal
import json
import os
import sys
import unittest
from unittest.mock import patch

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, '..', 'lib'))
import grundbetrieb_vertrag as V  # noqa: E402
from c1_testbauwerte import lade_isoliertes_beispiel

with open(os.path.join(HIER, 'fixtures', 'grundbetrieb', 'test.json')) as datei:
    BEISPIEL = lade_isoliertes_beispiel(datei.read())


class UtcKalender(unittest.TestCase):
    def pruefe_zeit(self, zeit, gueltig):
        d = copy.deepcopy(BEISPIEL)
        d['generated_at'] = zeit
        fehler = V.pruefe(d)
        if gueltig:
            self.assertEqual(fehler, [])
            self.assertEqual(V.lade_json(V.als_json(d))['generated_at'], zeit)
        else:
            self.assertTrue(any(f.startswith('$.generated_at:') for f in fehler), fehler)
            with self.assertRaises(ValueError):
                V.als_json(d)
            with self.assertRaises(ValueError):
                V.lade_json(V._json_wert(d))

    def test_positive_kontrolle_und_grenzen(self):
        for zeit in ('2026-10-22T10:00:00Z', '0001-01-01T00:00:00Z',
                     '9999-12-31T23:59:59Z'):
            with self.subTest(zeit=zeit):
                self.pruefe_zeit(zeit, True)

    def test_alle_erlaubten_nachkommastellen_bleiben_erhalten(self):
        for anzahl in range(1, 10):
            with self.subTest(anzahl=anzahl):
                self.pruefe_zeit('2026-10-22T10:00:00.' + '123456789'[:anzahl] + 'Z', True)

    def test_urspruenglicher_fehler(self):
        self.pruefe_zeit('2026-99-99T99:99:99Z', False)

    def test_ungueltige_kalenderwerte(self):
        for zeit in ('2026-99-22T10:00:00Z', '2026-02-30T10:00:00Z',
                     '2026-04-31T10:00:00Z', '2026-00-22T10:00:00Z',
                     '2026-10-00T10:00:00Z', '0000-01-01T00:00:00Z'):
            with self.subTest(zeit=zeit):
                self.pruefe_zeit(zeit, False)

    def test_schaltjahre(self):
        for jahr, gueltig in ((2024, True), (2026, False), (2000, True), (1900, False)):
            with self.subTest(jahr=jahr):
                self.pruefe_zeit(f'{jahr}-02-29T12:00:00.123456789Z', gueltig)

    def test_ungueltige_uhrzeit_und_keine_schaltsekunden(self):
        for uhrzeit in ('99:00:00', '24:00:00', '10:99:00', '10:60:00',
                        '10:00:60', '23:59:60', '10:00:99'):
            with self.subTest(uhrzeit=uhrzeit):
                self.pruefe_zeit('2026-10-22T' + uhrzeit + 'Z', False)

    def test_uhrzeitgrenzen_auch_mit_permissivem_kalenderparser(self):
        # Native Regression #144: Parser koennen 24:00:00 auf den Folgetag normalisieren.
        with patch.object(V, 'datetime') as parser:
            for zeit in ('2026-10-22T24:00:00Z', '2026-10-22T24:00:00.000000000Z',
                         '2026-10-22T23:60:00Z', '2026-10-22T23:59:60Z'):
                with self.subTest(zeit=zeit):
                    self.pruefe_zeit(zeit, False)
            parser.fromisoformat.assert_not_called()
            self.pruefe_zeit('2026-10-22T23:59:59.123456789Z', True)
            parser.fromisoformat.assert_called_with('2026-10-22T23:59:59')

    def test_nur_das_vertragliche_utc_format(self):
        for zeit in ('2026-10-22T10:00:00', '2026-10-22T10:00:00+00:00',
                     '2026-10-22T10:00:00z', '2026-10-22 10:00:00Z',
                     '2026-10-22T10:00:00.Z', '2026-10-22T10:00:00.1234567890Z',
                     '2026-10-22T10:00:00Z\n', '2026-10-22T10:00:00Zrest',
                     '２０２６-10-22T10:00:00Z'):
            with self.subTest(zeit=zeit):
                self.pruefe_zeit(zeit, False)

    def test_fehlend_und_falsche_typen(self):
        for zeit in (None, True, 2026, [], {}, ''):
            with self.subTest(zeit=zeit):
                self.pruefe_zeit(zeit, False)
        d = copy.deepcopy(BEISPIEL)
        del d['generated_at']
        self.assertIn('$.generated_at: fehlt', V.pruefe(d))


if __name__ == '__main__':
    unittest.main(verbosity=2)
