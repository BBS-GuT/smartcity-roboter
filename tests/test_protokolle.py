#!/usr/bin/env python3
"""Issue #20: Logs herunterladen (lib/protokolle.py) - ohne Panel, ROS oder echte Prozesse, nur temporaere Dateien.
Aufruf: python3 tests/test_protokolle.py"""
import builtins
import io
import os
import shutil
import sys
import tarfile
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import protokolle  # noqa: E402


def entpacken(daten):
    """Archiv komplett lesen (wie 'tar xzf'): Name -> Inhalt. Wirft bei kaputtem Archiv."""
    with tarfile.open(fileobj=io.BytesIO(daten), mode='r:gz') as tar:
        return {m.name: tar.extractfile(m).read() for m in tar.getmembers()}


class Protokolle(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.ordner)

    def schreibe(self, name, text):
        with open(os.path.join(self.ordner, name), 'w') as f:
            f.write(text)

    def test_normal_aktueller_und_voriger_lauf(self):
        with protokolle.neu_oeffnen(self.ordner, 'ki') as f:
            f.write('erster Lauf\n')
        with protokolle.neu_oeffnen(self.ordner, 'ki') as f:
            f.write('zweiter Lauf\n')
        inhalt = entpacken(protokolle.archiv(self.ordner))
        self.assertEqual(inhalt['logs/ki.log'], b'zweiter Lauf\n')
        self.assertEqual(inhalt['logs/ki.alt.log'], b'erster Lauf\n')
        self.assertNotIn('logs/HINWEISE.txt', inhalt)

    def test_rotation_zwischen_groesse_und_lesen(self):
        """Genau der Fall aus #20: Datei wird nach dem Ermitteln der Liste umbenannt und neu (kuerzer) angelegt."""
        self.schreibe('karte.log', 'x' * 50000)
        echtes_open = builtins.open

        def open_mit_rotation(pfad, *a, **k):
            if str(pfad).endswith('karte.log') and not os.path.exists(os.path.join(self.ordner, 'karte.alt.log')):
                os.replace(pfad, os.path.join(self.ordner, 'karte.alt.log'))   # Prozess startet neu ...
                with echtes_open(pfad, 'w') as f:
                    f.write('neu\n')                                          # ... und schreibt weniger
            return echtes_open(pfad, *a, **k)

        with patch.object(builtins, 'open', open_mit_rotation):
            daten = protokolle.archiv(self.ordner)
        inhalt = entpacken(daten)                     # kein "unexpected end of data"
        self.assertEqual(inhalt['logs/karte.log'], b'neu\n')

    def test_datei_verschwindet(self):
        self.schreibe('a.log', 'a\n')
        self.schreibe('b.log', 'b\n')
        echtes_open = builtins.open

        def open_mit_loeschen(pfad, *a, **k):
            if str(pfad).endswith('a.log'):
                os.remove(pfad)
            return echtes_open(pfad, *a, **k)

        with patch.object(builtins, 'open', open_mit_loeschen):
            inhalt = entpacken(protokolle.archiv(self.ordner))
        self.assertNotIn('logs/a.log', inhalt)
        self.assertEqual(inhalt['logs/b.log'], b'b\n')
        self.assertIn(b'a.log: nicht lesbar', inhalt['logs/HINWEISE.txt'])

    def test_ordner_fehlt(self):
        inhalt = entpacken(protokolle.archiv(os.path.join(self.ordner, 'gibtsnicht')))
        self.assertIn(b'nicht lesbar', inhalt['logs/HINWEISE.txt'])

    def test_grenzen(self):
        self.schreibe('gross.log', 'A' * 3000 + 'ENDE')
        self.schreibe('klein1.log', 'k' * 900)
        self.schreibe('klein2.log', 'k' * 900)
        self.schreibe('zuletzt.log', 'z')
        inhalt = entpacken(protokolle.archiv(self.ordner, max_datei=1000, max_gesamt=2000))
        self.assertEqual(len(inhalt['logs/gross.log']), 1000)
        self.assertTrue(inhalt['logs/gross.log'].endswith(b'ENDE'))      # das Neueste bleibt
        self.assertLessEqual(sum(len(v) for k, v in inhalt.items() if k != 'logs/HINWEISE.txt'), 2000)
        hinweise = inhalt['logs/HINWEISE.txt'].decode()
        self.assertIn('gross.log: nur die letzten 1000 Bytes', hinweise)
        self.assertIn('klein2.log: nur die letzten 100 Bytes', hinweise)
        self.assertIn('zuletzt.log: weggelassen', hinweise)

    def test_parallel_herunterladen_und_neu_starten(self):
        with protokolle.neu_oeffnen(self.ordner, 'ki') as f:
            f.write('lauf 0\n')
        fehler = []

        def herunterladen():
            try:
                for _ in range(20):
                    entpacken(protokolle.archiv(self.ordner))
            except Exception as e:
                fehler.append(e)

        threads = [threading.Thread(target=herunterladen) for _ in range(2)]
        for t in threads:
            t.start()
        for i in range(1, 21):
            with protokolle.neu_oeffnen(self.ordner, 'ki') as f:
                f.write(f'lauf {i}\n')
        for t in threads:
            t.join()
        self.assertEqual(fehler, [])
        inhalt = entpacken(protokolle.archiv(self.ordner))   # Downloads veraendern keine Protokolle
        self.assertEqual(inhalt['logs/ki.log'], b'lauf 20\n')
        self.assertEqual(inhalt['logs/ki.alt.log'], b'lauf 19\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
