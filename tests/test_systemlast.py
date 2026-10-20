#!/usr/bin/env python3
"""logs/system.log (lib/systemlast.py) mit nachgebautem /proc und /sys. Aufruf: python3 tests/test_systemlast.py"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))
import systemlast  # noqa: E402


class Systemlast(unittest.TestCase):
    def setUp(self):
        self.wurzel = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.wurzel)
        self.schreibe('proc/meminfo', 'MemTotal: 8000000 kB\nMemAvailable: 2000000 kB\nSwapTotal: 4000000 kB\n'
                                      'SwapFree: 3000000 kB\n')
        self.schreibe('proc/loadavg', '5.20 4.00 3.00 2/300 1234\n')
        self.schreibe('sys/class/thermal/thermal_zone0/temp', '71500\n')
        self.schreibe('sys/devices/gpu.0/load', '450\n')

    def schreibe(self, pfad, text):
        voll = os.path.join(self.wurzel, pfad)
        os.makedirs(os.path.dirname(voll), exist_ok=True)
        with open(voll, 'w') as f:
            f.write(text)

    def prozess(self, pid, cmdline, ticks):
        self.schreibe(f'proc/{pid}/cmdline', '\0'.join(cmdline) + '\0')
        # Feld 14/15 (utime/stime) nach dem Namen in Klammern (der Leerzeichen enthalten darf)
        self.schreibe(f'proc/{pid}/stat', f'{pid} (python 3) S ' + ' '.join(['0'] * 10) + f' {ticks} 0 0 0\n')

    def test_messung(self):
        self.schreibe('proc/stat', 'cpu 1000 0 1000 8000 0 0 0 0 0 0\n')
        self.prozess(10, ['python3', '/r/ki/zentrale.py', '--ros-args'], 100)
        self.prozess(11, ['/usr/bin/component_container'], 50)
        m = systemlast.Systemlast(self.wurzel, kerne=1)
        erste = m.messen()
        self.assertIsNone(erste.get('cpu_prozent'))                 # erste Messung: noch kein Vergleich
        self.schreibe('proc/stat', 'cpu 1600 0 1200 8100 100 0 0 0 0 0\n')   # +1000 Ticks, davon 200 frei
        self.prozess(10, ['python3', '/r/ki/zentrale.py', '--ros-args'], 400)
        self.prozess(11, ['/usr/bin/component_container'], 100)
        z = m.messen()
        self.assertAlmostEqual(z['cpu_prozent'], 80.0)
        self.assertAlmostEqual(z['iowait_prozent'], 10.0)
        self.assertEqual(z['top'][0][0], 'zentrale.py')                # Skriptname statt python3
        self.assertEqual(z['ram_belegt_mb'], round(6000000 / 1024))
        self.assertEqual(z['swap_mb'], round(1000000 / 1024))
        self.assertEqual(z['temperatur'], 71.5)
        self.assertEqual(z['gpu_prozent'], 45.0)
        text = systemlast.zeile(z, zu_spaet=1.4)
        for teil in ('HING 1.4s', 'CPU 80%', 'IO-Warten 10%', 'Swap 977 MB', 'GPU 45%', '72 Grad', 'zentrale.py'):
            self.assertIn(teil, text)

    def test_threads_des_staerksten_programms(self):
        self.schreibe('proc/stat', 'cpu 1000 0 1000 8000 0 0 0 0 0 0\n')
        self.prozess(10, ['python3', '/r/line_follower/line_follower.py'], 100)
        for tid, t in (('10', 50), ('11', 20), ('12', 20)):
            self.schreibe(f'proc/10/task/{tid}/stat', f'{tid} (x) S ' + ' '.join(['0'] * 10) + f' {t} 0 0 0\n')
            self.schreibe(f'proc/10/task/{tid}/comm', 'python3\n' if tid == '10' else 'openblas\n')
        m = systemlast.Systemlast(self.wurzel, kerne=4)
        m.messen()
        self.schreibe('proc/stat', 'cpu 1100 0 1000 8000 0 0 0 0 0 0\n')
        self.prozess(10, ['python3', '/r/line_follower/line_follower.py'], 110)
        m.messen()                                   # zweite Messung: Threads des staerksten Programms gemerkt
        self.schreibe('proc/stat', 'cpu 2100 0 1000 8000 0 0 0 0 0 0\n')       # +1000 Ticks = 4 Kerne a 250
        self.prozess(10, ['python3', '/r/line_follower/line_follower.py'], 700)
        for tid, t in (('10', 250), ('11', 220), ('12', 220)):
            self.schreibe(f'proc/10/task/{tid}/stat', f'{tid} (x) S ' + ' '.join(['0'] * 10) + f' {t} 0 0 0\n')
        z = m.messen()
        self.assertEqual(z['top'][0], ('line_follower.py', 236))      # 590 Ticks / 250 je Kern
        self.assertEqual(len(z['threads']), 3)
        self.assertEqual(sorted(z['threads']), [('openblas', 80), ('openblas', 80), ('python3', 80)])
        self.assertIn('Threads von line_follower.py:', systemlast.zeile(z))

    def test_ohne_proc(self):
        m = systemlast.Systemlast(os.path.join(self.wurzel, 'gibtsnicht'))
        z = m.messen()
        self.assertIsNone(z.get('cpu_prozent'))
        self.assertIsInstance(systemlast.zeile(z), str)


if __name__ == '__main__':
    unittest.main(verbosity=2)
