# C1a (Issue #11): alter_s() lehnt ungueltige und zukuenftige monotone Zeiten ab.
# Eigenstaendig, nur Standardbibliothek, kein ROS:  python tests/test_c1_alter.py
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'))
from grundbetrieb_vertrag import alter_s  # noqa: E402

NAN, INF = float('nan'), float('inf')


def satz(erzeugt):
    return {'generated_mono_s': erzeugt}


class AlterS(unittest.TestCase):
    # positive Kontrolle
    def test_gueltiges_alter(self):
        self.assertEqual(alter_s(satz(10.0), 10.25), 0.25)

    def test_gleiche_zeiten_ergeben_null(self):
        self.assertEqual(alter_s(satz(10.0), 10.0), 0.0)

    def test_ganze_zahlen(self):
        self.assertEqual(alter_s(satz(3), 5), 2.0)

    # Originalfehler: wurde durch max(0.0, ...) zu Alter 0
    def test_erzeugung_nach_jetzt(self):
        with self.assertRaises(ValueError):
            alter_s(satz(10.0), 9.9)

    def test_jetzt_nan(self):
        with self.assertRaises(ValueError):
            alter_s(satz(10.0), NAN)

    def test_jetzt_minus_unendlich(self):
        with self.assertRaises(ValueError):
            alter_s(satz(10.0), -INF)

    # weitere ungueltige Zeitwerte
    def test_jetzt_plus_unendlich(self):
        with self.assertRaises(ValueError):
            alter_s(satz(10.0), INF)

    def test_erzeugung_nicht_endlich(self):
        for wert in (NAN, INF, -INF):
            with self.subTest(wert=wert), self.assertRaises(ValueError):
                alter_s(satz(wert), 10.0)

    def test_bool_und_nichtnumerisch(self):
        for wert in (True, False, '5', None, [1], 1 + 2j):
            with self.subTest(jetzt=wert), self.assertRaises(ValueError):
                alter_s(satz(1.0), wert)
            with self.subTest(erzeugt=wert), self.assertRaises(ValueError):
                alter_s(satz(wert), 10.0)

    def test_negative_werte(self):
        with self.assertRaises(ValueError):
            alter_s(satz(-1.0), 5.0)
        with self.assertRaises(ValueError):
            alter_s(satz(0.0), -5.0)

    def test_zu_grosse_ganze_zahl(self):
        with self.assertRaises(ValueError):
            alter_s(satz(1.0), 10 ** 400)

    def test_feld_fehlt(self):
        for d in ({}, None):
            with self.subTest(d=d), self.assertRaises(ValueError):
                alter_s(d, 5.0)


if __name__ == '__main__':
    unittest.main()
