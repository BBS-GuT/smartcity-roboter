import sys
from pathlib import Path
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
from zebra import finde_zebra, ZebraBestaetigung


class ZebraTest(unittest.TestCase):
    def bild(self, rows, starts=(20, 30, 40, 50)):
        v = np.zeros((100, 250), dtype=np.uint8)
        for y in rows:
            for x in starts:
                v[y, x:x+4] = 255
        return v

    def test_echte_zusammenhaengende_reihe(self):
        self.assertIsNotNone(finde_zebra(self.bild(range(20, 40)), .004, .85))

    def test_getrennte_paare_sind_keine_reihe(self):
        self.assertIsNone(finde_zebra(self.bild(range(20, 40), (10, 20, 100, 110, 200, 210)), .004, .85))

    def test_verstreute_zeilen(self):
        self.assertIsNone(finde_zebra(self.bild((10, 20, 30, 40)), .004, .85))

    def test_unterschiedliche_balken_pro_zeile(self):
        v = self.bild((20, 22)) | self.bild((21, 23), (80, 90, 100, 110))
        self.assertIsNone(finde_zebra(v, .004, .85))

    def test_einzelbild_und_aussetzer(self):
        b = ZebraBestaetigung(); z = {'abstand': .3}
        self.assertIsNone(b.aktualisieren(z, 1, 1))
        self.assertIsNone(b.aktualisieren(None, 1.1, 1.1))
        self.assertIsNone(b.aktualisieren(z, 1.2, 1.2))
        self.assertIsNone(b.aktualisieren(z, 1.3, 1.3))
        self.assertEqual(b.aktualisieren(z, 1.4, 1.4), z)

    def test_wiederholte_alte_und_springende_aufnahmen(self):
        b = ZebraBestaetigung(); z = {'abstand': .3}
        for _ in range(5):
            self.assertIsNone(b.aktualisieren(z, 1, 1))
        self.assertIsNone(b.aktualisieren(z, 1.1, 2))
        self.assertIsNone(b.aktualisieren(z, 2, 2))
        self.assertIsNone(b.aktualisieren({'abstand': .6}, 2.1, 2.1))
        self.assertIsNone(b.aktualisieren(z, 2.2, 2.2))


if __name__ == '__main__':
    unittest.main()
