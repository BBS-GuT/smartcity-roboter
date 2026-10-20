#!/usr/bin/env python3
"""Panel ohne ROS (Attrappen): Schutz gegen fremde Webseiten (CSRF) und Greifer einmessen.

Eigener temporaerer Port und eigene temporaere config/lokal/arm.yaml; kein Geraet.
"""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

HIER = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix='panel_greifer_')
os.environ['SMARTCITY_ARM_YAML'] = os.path.join(TMP, 'arm.yaml')
sys.path.insert(0, os.path.join(HIER, 'attrappen'))
sys.path.insert(0, os.path.join(HIER, '..', 'panel'))
sys.path.insert(0, os.path.join(HIER, '..', 'lib'))
from http.server import ThreadingHTTPServer  # noqa: E402
import panel  # noqa: E402
import arm as armlib  # noqa: E402


class Args:
    port = 0
    kein_netz = False
    tiefe_topic = '/camera/depth/image_raw'
    karte = 'test_panel_greifer'


class PanelGreifer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = panel.PanelNode(Args())
        handler, _ = panel.mache_handler(cls.node, panel.Prozesse())
        cls.srv = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        cls.url = f'http://127.0.0.1:{cls.srv.server_address[1]}'
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def post(self, name, daten, typ='application/json', origin=None):
        req = urllib.request.Request(self.url + '/api/' + name, data=json.dumps(daten).encode(), method='POST')
        if typ:
            req.add_header('Content-Type', typ)
        if origin:
            req.add_header('Origin', origin)
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())['antwort']
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()

    def test_fremde_seite_abgelehnt(self):
        self.assertEqual(self.post('greifer_einmessen_stand', {}, typ='text/plain')[0], 403)
        self.assertEqual(self.post('greifer_einmessen_stand', {}, typ=None)[0], 403)
        self.assertEqual(self.post('greifer_einmessen_stand', {}, origin='http://boese.example')[0], 403)
        code, text = self.post('greifer_einmessen_stand', {}, origin=self.url)
        self.assertEqual(code, 200)
        self.assertIn('NICHT eingemessen', text)

    def test_einmessen(self):
        self.post('greifer_messpunkte_loeschen', {})
        self.post('arm_pose', {'winkel': [90, 120, 10, 20, 90, 30], 'zeit': 1000})
        for _ in range(5):
            self.post('greifer_schritt', {'grad': 10})
        code, text = self.post('greifer_schritt', {'grad': 2})
        self.assertEqual((code, text), (200, 'Servo 6 (Greifer) jetzt 82'))
        code, text = self.post('greifer_messen', {'breite_cm': 4.5})
        self.assertEqual(code, 200)
        self.assertIn('4.5 cm -> Servo 6 = 82', text)
        self.assertEqual(armlib.greifer_messpunkte(), [(0.045, 82.0)])
        g = armlib.greifer_plan(0.04)                 # Kamera misst 4 cm: nah genug am eingemessenen Wuerfel
        self.assertEqual((g['anlegen'], g['zu']), (72, 90))
        self.assertIn('eingemessen (4,5 cm)', g['text'])
        self.assertEqual(self.post('greifer_messen', {'breite_cm': 20})[0], 200)
        self.assertEqual(len(armlib.greifer_messpunkte()), 1)     # ungueltige Breite nicht gespeichert
        self.post('greifer_messpunkte_loeschen', {})
        self.assertEqual(armlib.greifer_messpunkte(), [])


class Kennlinie(unittest.TestCase):
    E = {'greifer_auf': 30, 'greifer_zu': 130, 'greifer_druecken': 8}

    def test_geschaetzt_wie_bisher(self):
        g = armlib.greifer_plan(0.03, dict(self.E))
        self.assertEqual((g['anlegen'], g['zu']), (117, 130))
        self.assertIn('geschaetzt', g['text'])

    def test_messpunkte(self):
        e = dict(self.E, greifer_messpunkte=[[0.0, 172], [0.03, 138]])
        g = armlib.greifer_plan(0.027, e)                       # eingemessener Wuerfel, Kamera misst etwas zu klein
        self.assertEqual((g['anlegen'], g['zu']), (128, 146))   # ueber greifer_zu: Anliegen ist nachgewiesen
        g = armlib.greifer_plan(0.05, e)                        # zwischen den Punkten: gerade Linie
        self.assertAlmostEqual(g['beruehrt'], 138 - 34 / 0.03 * 0.02)
        g = armlib.greifer_plan(0.004, e)                       # nie weiter zu als "Backen beruehren sich"
        self.assertLessEqual(g['zu'], 172)

    def test_greifer_andersherum(self):
        e = {'greifer_auf': 130, 'greifer_zu': 30, 'greifer_druecken': 8, 'greifer_messpunkte': [[0.03, 50]]}
        g = armlib.greifer_plan(0.03, e)
        self.assertEqual((g['anlegen'], g['zu']), (60, 42))

    def test_ungueltige_punkte_ignoriert(self):
        e = dict(self.E, greifer_messpunkte=[['x', 1], [0.03], [0.5, 100], [0.03, 999]])
        self.assertEqual(armlib.greifer_messpunkte(e), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
