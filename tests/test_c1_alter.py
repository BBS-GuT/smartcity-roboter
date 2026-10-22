#!/usr/bin/env python3
"""C1a (#11): lokale monotone Alterspruefung, ohne ROS oder Broker.

Aufruf aus der Projektwurzel: python tests/test_c1_alter.py
Ungueltige Zeiten duerfen niemals als frische Daten (Alter 0) erscheinen.
"""
from decimal import Decimal
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'))
from grundbetrieb_vertrag import alter_s  # noqa: E402


class MonotonesAlter(unittest.TestCase):
    def test_positive_kontrolle(self):
        self.assertEqual(alter_s({'generated_mono_s': 10}, Decimal('10.25')), Decimal('0.25'))

    def test_gleiche_zeiten_und_nullpunkt(self):
        for zeit in (0, Decimal('0.0'), 10, Decimal('10.25')):
            with self.subTest(zeit=zeit):
                self.assertEqual(alter_s({'generated_mono_s': zeit}, zeit), 0)

    def test_ganze_und_gemischte_zahlen(self):
        for erzeugt, jetzt, erwartet in ((0, 10, 10), (10, Decimal('10.25'), Decimal('0.25')), (Decimal('10.0'), 11, 1)):
            with self.subTest(erzeugt=erzeugt, jetzt=jetzt):
                self.assertEqual(alter_s({'generated_mono_s': erzeugt}, jetzt), erwartet)

    def test_erzeugung_in_der_zukunft(self):
        for erzeugt, jetzt in ((Decimal('10.0'), Decimal('9.75')), (1, 0)):
            with self.subTest(erzeugt=erzeugt, jetzt=jetzt):
                with self.assertRaises(ValueError):
                    alter_s({'generated_mono_s': erzeugt}, jetzt)

    def test_ungueltige_erzeugungszeit(self):
        for zeit in (float('nan'), float('inf'), float('-inf'), True, False,
                     '10', None, [], {}, 1j, -1, -0.25):
            with self.subTest(zeit=repr(zeit)):
                with self.assertRaises(ValueError):
                    alter_s({'generated_mono_s': zeit}, Decimal('10.25'))

    def test_ungueltiges_jetzt(self):
        for zeit in (float('nan'), float('inf'), float('-inf'), True, False,
                     '10', None, [], {}, 1j, -1, -0.25):
            with self.subTest(zeit=repr(zeit)):
                with self.assertRaises(ValueError):
                    alter_s({'generated_mono_s': 0}, zeit)


if __name__ == '__main__':
    unittest.main(verbosity=2)
