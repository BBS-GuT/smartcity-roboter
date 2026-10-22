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

    def schreibe_bytes(self, pfad, daten):
        voll = os.path.join(self.wurzel, pfad)
        os.makedirs(os.path.dirname(voll), exist_ok=True)
        with open(voll, 'wb') as f:
            f.write(daten)

    def binaer_prozess(self, pid, cmdline, ticks, name=b'python3'):
        """Fremder Prozess mit beliebigen Bytes in cmdline/stat, z. B. ungueltigem UTF-8 (Issue #35)."""
        self.schreibe_bytes(f'proc/{pid}/cmdline', cmdline)
        self.schreibe_bytes(f'proc/{pid}/stat', f'{pid} ('.encode() + name + b') S ' + b'0 ' * 10
                            + f'{ticks} 0 0 0\n'.encode())

    def test_ungueltiges_utf8_im_prozessnamen(self):
        """Regression #35: ungueltige UTF-8-Bytes in einem fremden Skriptnamen beendeten messen() mit
        UnicodeDecodeError, sobald der Prozess im CPU-Ranking erschien. Jetzt: Ersatzname und weitere Messungen."""
        kaputt = b'python3\0/r/skript_\xff\xfe.py\0'
        self.schreibe('proc/stat', 'cpu 1000 0 1000 8000 0 0 0 0 0 0\n')
        self.binaer_prozess(10, kaputt, 100)
        self.prozess(11, ['python3', '/r/ki/zentrale.py'], 50)
        m = systemlast.Systemlast(self.wurzel, kerne=1)
        m.messen()
        gesamt, eigen = 1000, 100
        for runde in range(3):                       # die vormals abbrechende zweite und zwei weitere Messungen
            gesamt += 1000
            eigen += 300
            self.schreibe('proc/stat', f'cpu {gesamt} 0 1000 8000 0 0 0 0 0 0\n')
            self.binaer_prozess(10, kaputt, eigen)
            self.prozess(11, ['python3', '/r/ki/zentrale.py'], 50 + 100 * (runde + 1))
            z = m.messen()
            text = systemlast.zeile(z)
            self.assertEqual(z['cpu_prozent'], 100.0)
            self.assertEqual(z['top'][0], ('skript_\\xff\\xfe.py', 30))   # lesbarer Ersatz, Rechenzeit stimmt
            self.assertEqual(z['top'][1], ('zentrale.py', 10))             # gueltiger Name unveraendert
            self.assertIn('skript_\\xff\\xfe.py 30%', text)
            text.encode('ascii')                                           # Ersatz schreibt sich in jede Logdatei

    def test_ungueltiges_utf8_in_comm_und_threadnamen(self):
        """Kernel-Thread ohne cmdline: Name aus comm; auch stat-Name und Threadname mit ungueltigen Bytes."""
        self.schreibe('proc/stat', 'cpu 1000 0 1000 8000 0 0 0 0 0 0\n')
        self.binaer_prozess(20, b'', 100, name=b'kw\xc3(')
        self.schreibe_bytes('proc/20/comm', b'kw\xc3\n')
        self.schreibe_bytes('proc/20/task/20/stat', b'20 (kw\xc3() S ' + b'0 ' * 10 + b'100 0 0 0\n')
        self.schreibe_bytes('proc/20/task/20/comm', b'thr\xff\n')
        m = systemlast.Systemlast(self.wurzel, kerne=2)    # 1000 Ticks = 2 Kerne a 500
        m.messen()
        for runde in range(1, 4):
            self.schreibe('proc/stat', f'cpu {1000 + 1000 * runde} 0 1000 8000 0 0 0 0 0 0\n')
            self.binaer_prozess(20, b'', 100 + 900 * runde, name=b'kw\xc3(')
            self.schreibe_bytes('proc/20/task/20/stat', b'20 (kw\xc3() S ' + b'0 ' * 10
                                + f'{100 + 900 * runde} 0 0 0\n'.encode())
            z = m.messen()
            self.assertEqual(z['top'], [('kw\\xc3', 180)])      # 900 Ticks / 500 je Kern, Name aus comm
            if runde > 1:                                       # Threads erst ab dem zweiten Vergleich bekannt
                self.assertEqual(z['threads'], [('thr\\xff', 180)])
                self.assertIn('Threads von kw\\xc3: thr\\xff 180%', systemlast.zeile(z))
            systemlast.zeile(z).encode('ascii')

    def test_ohne_proc(self):
        m = systemlast.Systemlast(os.path.join(self.wurzel, 'gibtsnicht'))
        z = m.messen()
        self.assertIsNone(z.get('cpu_prozent'))
        self.assertIsInstance(systemlast.zeile(z), str)


if __name__ == '__main__':
    unittest.main(verbosity=2)
