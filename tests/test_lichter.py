#!/usr/bin/env python3
"""Abblendlicht und Blinker (lib/lichter.py) und ihre Panel-Knoepfe, ohne ROS und Roboter."""
import json
import math
import os
import sys
import threading
import unittest
import urllib.request

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, 'attrappen'))
sys.path.insert(0, os.path.join(HIER, '..', 'panel'))
sys.path.insert(0, os.path.join(HIER, '..', 'lib'))
from http.server import ThreadingHTTPServer  # noqa: E402
import lichter  # noqa: E402
import panel  # noqa: E402

GERADE = [(0.05 * i, 0.0) for i in range(1, 17)]
ECKE_LINKS = [(0.05 * i, 0.0) for i in range(1, 9)] + [(0.4, 0.05 * i) for i in range(1, 9)]
ECKE_RECHTS = [(x, -y) for x, y in ECKE_LINKS]
# sanfte Kurve: Kreis mit 1,5 m Radius, 80 cm davon = ca. 30 Grad
SANFT = [(1.5 * math.sin(0.05 * i / 1.5), 1.5 * (1 - math.cos(0.05 * i / 1.5))) for i in range(1, 17)]


SOFORT = {'bestaetigen': 0.0, 'wechsel': 0.0}   # ohne Entprellung (fuer Tests anderer Eigenschaften)


def lf(weg):
    return {'drive': True, 'weg': weg}


def fahre(li, von, bis, weg):
    """10 Schritte je Sekunde mit gleicher Linie, Rueckgabe: Blinker nach jedem Schritt."""
    return [li.schritt(von + i / 10, lf(weg), None)['blinker'] for i in range(round((bis - von) * 10))]


class Blinker(unittest.TestCase):
    def test_knick_richtung(self):
        self.assertAlmostEqual(lichter.knick(GERADE), 0.0)
        self.assertGreater(lichter.knick(ECKE_LINKS), 1.2)
        self.assertLess(lichter.knick(ECKE_RECHTS), -1.2)
        self.assertIsNone(lichter.knick([]))
        self.assertIsNone(lichter.knick([(0.05, 0.0), (0.1, 0.0)]))

    def test_ecke_blinkt_vorher_und_nicht_bei_sanfter_kurve(self):
        li = lichter.Lichter(SOFORT)
        self.assertIsNone(li.schritt(0.0, lf(GERADE), None)['blinker'])
        self.assertIsNone(li.schritt(0.1, lf(SANFT), None)['blinker'])
        self.assertEqual(li.schritt(0.2, lf(ECKE_RECHTS), None)['blinker'], 'rechts')
        self.assertEqual(li.schritt(0.3, lf(ECKE_LINKS), None)['blinker'], 'links')
        self.assertEqual(set(fahre(lichter.Lichter(), 0.0, 3.0, SANFT)), {None})

    def test_entprellt_vor_kreuzung(self):
        # RM02 21.10.: vor der Kreuzung springt der Knick zwischen links und rechts -> darf nicht blinken
        li = lichter.Lichter()
        for i in range(30):
            self.assertIsNone(li.schritt(i / 10, lf(ECKE_LINKS if i % 3 else ECKE_RECHTS), None)['blinker'])
        # echte Ecke: erst nach 0,5 s gleicher Richtung
        b = fahre(li, 3.0, 4.0, ECKE_RECHTS)
        self.assertIsNone(b[4])
        self.assertEqual(b[5:], ['rechts'] * 5)
        # kurz andere Seite: bleibt rechts, keine Seitenwechsel
        self.assertEqual(set(fahre(li, 4.0, 5.0, ECKE_LINKS)), {'rechts'})
        # andere Seite lange genug (1,5 s): wechselt
        self.assertEqual(fahre(li, 5.0, 7.0, ECKE_LINKS)[-1], 'links')

    def test_nachlauf_und_mindestdauer(self):
        li = lichter.Lichter(SOFORT)
        li.schritt(0.0, lf(ECKE_LINKS), None)
        self.assertEqual(li.schritt(0.5, lf(GERADE), None)['blinker'], 'links')   # Nachlauf
        self.assertEqual(li.schritt(1.5, lf(GERADE), None)['blinker'], 'links')   # Mindestdauer 2 s
        self.assertIsNone(li.schritt(2.1, lf(GERADE), None)['blinker'])

    def test_takt(self):
        li = lichter.Lichter(SOFORT)
        self.assertTrue(li.schritt(0.0, lf(ECKE_LINKS), None)['blink_an'])
        self.assertFalse(li.schritt(0.4, lf(ECKE_LINKS), None)['blink_an'])      # 1,5 Hz: dunkel ab 0,33 s
        self.assertTrue(li.schritt(0.7, lf(ECKE_LINKS), None)['blink_an'])

    def test_ki_vorrang_und_manoever(self):
        li = lichter.Lichter()
        self.assertEqual(li.schritt(0.0, lf(ECKE_LINKS), {'blinker': 'rechts'})['blinker'], 'rechts')
        li = lichter.Lichter()
        wenden = {'aktion': 'manoever', 'manoever': {'lin': 0.0, 'dreh': -0.8, 'text': 'wenden'}}
        z = li.schritt(0.0, lf(GERADE), wenden)
        self.assertEqual((z['blinker'], z['grund']), ('rechts', 'Manoever: wenden'))
        zurueck = {'aktion': 'manoever', 'manoever': {'lin': -0.05, 'dreh': 0.0, 'text': 'zurueck'}}
        self.assertIsNone(lichter.Lichter().schritt(0.0, lf(GERADE), zurueck)['blinker'])

    def test_ohne_linienfolger_aus(self):
        li = lichter.Lichter(SOFORT)
        li.schritt(0.0, lf(ECKE_LINKS), None)
        self.assertIsNone(li.schritt(0.1, None, None)['blinker'])          # STOPP: Linienfolger beendet

    def test_leds(self):
        li = lichter.Lichter(dict(SOFORT, leds=6, blink_leds=2))
        self.assertEqual(li.leds(), [lichter.AUS] * 6)
        li.abblend = True
        self.assertEqual(li.leds(), [lichter.WEISS] * 6)
        z = li.schritt(0.0, lf(ECKE_RECHTS), None)
        self.assertEqual(z['leds'], [lichter.WEISS] * 4 + [lichter.GELB] * 2)


class Leiste(unittest.TestCase):
    def test_rgb_befehle(self):
        w, g, x = lichter.WEISS, lichter.GELB, lichter.AUS
        self.assertEqual(lichter.rgb_befehle(None, [w] * 8), [(0, w)])                 # alle gleich: eine Nachricht
        self.assertEqual(lichter.rgb_befehle([w] * 8, [w] * 8), [])                    # nichts geaendert
        neu = [g, g] + [w] * 6
        self.assertEqual(lichter.rgb_befehle([w] * 8, neu), [(1, g), (2, g)])
        self.assertEqual(lichter.rgb_befehle([w] * 8, neu, links_zuerst=False), [(8, g), (7, g)])
        self.assertEqual(len(lichter.rgb_befehle(None, neu)), 8)                      # unbekannt: alle einzeln
        self.assertEqual(lichter.rgb_befehle(None, [x] * 8), [(0, x)])


class Args:
    port = 0
    kein_netz = False
    tiefe_topic = '/camera/depth/image_raw'
    karte = 'test_lichter'


class PanelLichter(unittest.TestCase):
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

    def post(self, name, daten):
        req = urllib.request.Request(self.url + '/api/' + name, data=json.dumps(daten).encode(), method='POST')
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())['antwort']

    def status(self):
        with urllib.request.urlopen(self.url + '/api/status', timeout=5) as r:
            return json.loads(r.read())

    def test_abblend_von_hand(self):
        self.assertEqual(self.post('abblend', {'an': True}), 'Abblendlicht AN')
        self.assertTrue(self.status()['lichter']['abblend'])
        gesendet = json.loads(self.node.licht_pub.letzte.data)
        self.assertTrue(gesendet['abblend'])
        self.assertEqual(self.post('abblend', {'an': False}), 'Abblendlicht AUS')
        self.assertFalse(self.status()['lichter']['abblend'])
        self.assertFalse(json.loads(self.node.licht_pub.letzte.data)['abblend'])

    def test_leiste_am_board(self):
        self.node._set('lf', None)                                                    # kein Blinker
        self.node.lichter_takt()
        self.node.led_gesendet, self.node.led_voll = None, 0.0
        self.post('abblend', {'an': True})
        m = self.node.rgb_pub.letzte
        self.assertEqual((m.a, m.r, m.g, m.b), (0.0, 90.0, 90.0, 90.0))                # alle weiss
        n = self.node.rgb_pub.n
        self.node.lichter_takt()
        self.assertEqual(self.node.rgb_pub.n, n)                                       # unveraendert: nichts senden
        self.node.leiste_aus()
        self.assertEqual((self.node.rgb_pub.letzte.a, self.node.rgb_pub.letzte.r), (0.0, 0.0))

    def test_blinker_im_status_und_ereignis(self):
        self.node.lichter.c.update(SOFORT)
        self.node._set('lf', lf(ECKE_LINKS))
        self.node.lichter_takt()
        s = self.status()
        self.assertEqual(s['lichter']['blinker'], 'links')
        self.assertTrue(any(e['text'].startswith('Blinker links') for e in s['ereignisse']))


if __name__ == '__main__':
    unittest.main()
