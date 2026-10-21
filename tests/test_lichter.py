#!/usr/bin/env python3
"""F1: Lichtlogik (Abblendlicht, Blinker, Blaulicht) und ROS-Knoten mit Attrappen, ohne Hardware."""
import json
import os
import sys
import tempfile
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, 'attrappen'))
sys.path.insert(0, os.path.join(HIER, '..', 'lib'))
import lichtlogik as lichter  # noqa: E402

WEISS, GELB, BLAU, AUS = (255, 255, 255), (255, 120, 0), (0, 0, 255), (0, 0, 0)


def manoever(dreh=0.0, quer=0.0, lin=0.0):
    return {'aktion': 'manoever', 'faktor': 1.0, 'grund': 'Test',
            'manoever': {'lin': lin, 'quer': quer, 'dreh': dreh, 'text': 'Test'}}


FAHREN = {'aktion': 'fahren', 'faktor': 1.0, 'grund': 'frei', 'manoever': None}


class Abblendlicht(unittest.TestCase):
    def test_standard_an_in_der_mitte_weiss_blinker_aus(self):
        z = lichter.Lichter().zustand(0.0)
        self.assertTrue(z['abblendlicht'])
        self.assertIsNone(z['blinker'])
        self.assertEqual(z['leiste'][2:12], [WEISS] * 10)
        self.assertEqual(z['leiste'][:2] + z['leiste'][12:], [AUS] * 4)

    def test_kommando_aus_und_wieder_an(self):
        li = lichter.Lichter()
        self.assertTrue(li.kommando('abblendlicht aus', 0.0))
        self.assertEqual(li.zustand(0.0)['leiste'], [AUS] * 14)
        self.assertTrue(li.kommando('Abblendlicht AN', 1.0))
        self.assertTrue(li.zustand(1.0)['abblendlicht'])


class BlinkerAusKI(unittest.TestCase):
    def test_drehung_links_und_rechts(self):
        for dreh, seite, leds in ((0.8, 'links', [0, 1]), (-0.8, 'rechts', [12, 13])):
            li = lichter.Lichter()
            li.ki_befehl(manoever(dreh=dreh), 10.0)
            z = li.zustand(10.0)
            self.assertEqual(z['blinker'], seite)
            self.assertTrue(z['blinker_an'], 'neuer Blinker beginnt hell')
            self.assertEqual([z['leiste'][i] for i in leds], [GELB, GELB])

    def test_querfahrt_wenn_keine_drehung(self):
        li = lichter.Lichter()
        li.ki_befehl(manoever(quer=-0.1), 0.0)
        self.assertEqual(li.zustand(0.0)['blinker'], 'rechts')

    def test_kleine_lenkkorrektur_und_gerade_zurueck_ohne_blinker(self):
        li = lichter.Lichter()
        li.ki_befehl(manoever(dreh=0.05, lin=-0.1), 0.0)
        self.assertIsNone(li.zustand(0.0)['blinker'])

    def test_normales_fahren_ohne_blinker(self):
        li = lichter.Lichter()
        li.ki_befehl(FAHREN, 0.0)
        self.assertIsNone(li.zustand(0.0)['blinker'])

    def test_takt_1_5_hz(self):
        li = lichter.Lichter()
        t = 0.0
        phasen = []
        while t < 2.0:                       # 20 Hz wie im Knoten
            li.ki_befehl(manoever(dreh=0.8), t)
            phasen.append(li.zustand(t)['blinker_an'])
            t = round(t + 0.05, 2)
        wechsel_zu_an = sum(1 for a, b in zip(phasen, phasen[1:]) if b and not a)
        self.assertEqual(wechsel_zu_an, 2, phasen)   # Start hell + 2 weitere Takte in 2 s = 1,5 Hz
        self.assertAlmostEqual(sum(phasen) / len(phasen), 0.5, delta=0.1)

    def test_nachlauf_dann_aus(self):
        li = lichter.Lichter()
        li.ki_befehl(manoever(dreh=0.8), 0.0)
        li.ki_befehl(FAHREN, 0.1)
        self.assertEqual(li.zustand(0.5)['blinker'], 'links', 'Nachlauf 1 s')
        li.ki_befehl(FAHREN, 1.0)
        self.assertIsNone(li.zustand(1.2)['blinker'])

    def test_veralteter_ki_befehl_loescht_blinker(self):
        li = lichter.Lichter()
        li.ki_befehl(manoever(dreh=0.8), 0.0)
        self.assertIsNone(li.zustand(0.7)['blinker'])

    def test_kaputte_befehle_ohne_absturz_und_ohne_blinker(self):
        li = lichter.Lichter()
        for b in (None, 'stopp', {'aktion': 'manoever', 'manoever': None},
                  manoever(dreh=float('nan')), manoever(dreh='schnell'), manoever(dreh=float('inf'))):
            li.ki_befehl(b, 0.0)
            self.assertIsNone(li.zustand(0.0)['blinker'], b)

    def test_richtungswechsel_startet_hell(self):
        li = lichter.Lichter()
        li.ki_befehl(manoever(dreh=0.8), 0.0)
        li.zustand(0.0)
        li.ki_befehl(manoever(dreh=-0.8), 0.4)       # links waere jetzt dunkel
        z = li.zustand(0.4)
        self.assertEqual((z['blinker'], z['blinker_an']), ('rechts', True))


class HandBlinkerUndWarnblinker(unittest.TestCase):
    def test_hand_blinker_hat_vorrang_vor_ki(self):
        li = lichter.Lichter()
        li.kommando('blinker rechts', 0.0)
        li.ki_befehl(manoever(dreh=0.8), 0.0)
        self.assertEqual(li.zustand(0.0)['blinker'], 'rechts')
        li.kommando('blinker aus', 0.1)
        self.assertEqual(li.zustand(0.1)['blinker'], 'links')

    def test_warnblinker_beide_seiten(self):
        li = lichter.Lichter()
        li.kommando('warnblinker an', 0.0)
        z = li.zustand(0.0)
        self.assertEqual([z['leiste'][i] for i in (0, 1, 12, 13)], [GELB] * 4)
        li.kommando('warnblinker aus', 0.1)
        self.assertIsNone(li.zustand(0.1)['blinker'])

    def test_unbekannte_kommandos(self):
        li = lichter.Lichter()
        for k in ('', 'blinker', 'blinker oben', 'nebel an', 'blaulicht an sofort', 42):
            self.assertFalse(li.kommando(k, 0.0), k)


class Blaulicht(unittest.TestCase):
    def test_wechselt_haelften_und_ersetzt_abblendlicht(self):
        li = lichter.Lichter()
        li.kommando('blaulicht an', 5.0)
        z1, z2 = li.zustand(5.0), li.zustand(5.2)      # 2,5 Hz: Halbperiode 0,2 s
        self.assertEqual(z1['leiste'][2:7], [BLAU] * 5)
        self.assertEqual(z1['leiste'][7:12], [AUS] * 5)
        self.assertEqual(z2['leiste'][2:7], [AUS] * 5)
        self.assertEqual(z2['leiste'][7:12], [BLAU] * 5)
        self.assertNotIn(WEISS, z1['leiste'])

    def test_blaulicht_und_blinker_gleichzeitig(self):
        li = lichter.Lichter()
        li.kommando('blaulicht an', 0.0)
        li.kommando('blinker links', 0.0)
        z = li.zustand(0.0)
        self.assertEqual(z['leiste'][0:2], [GELB, GELB])
        self.assertIn(BLAU, z['leiste'])

    def test_aus_bringt_abblendlicht_zurueck(self):
        li = lichter.Lichter()
        li.kommando('blaulicht an', 0.0)
        li.kommando('blaulicht aus', 1.0)
        self.assertEqual(li.zustand(1.0)['leiste'][2:12], [WEISS] * 10)


class Einstellungen(unittest.TestCase):
    def test_falsche_belegung_wird_abgelehnt(self):
        for falsch in ({'anzahl_leds': 0}, {'blinker_links': [14]}, {'blinker_rechts': [-1]},
                       {'blinker_links': [0, 1], 'blinker_rechts': [1, 2]}, {'blink_hz': 0}):
            with self.assertRaises(ValueError, msg=falsch):
                lichter.Lichter(falsch)

    def test_mitgelieferte_konfiguration_ist_gueltig(self):
        knoten = _lade_knotenmodul()
        werte = knoten.lade_einstellungen()
        self.assertEqual(werte.pop('ausgang'), 'keiner')
        lichter.Lichter(werte)

    def test_lokale_datei_ueberschreibt(self):
        knoten = _lade_knotenmodul()
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'config', 'lokal'))
            with open(os.path.join(d, 'config', 'lichter.yaml'), 'w') as f:
                f.write('lichter:\n  anzahl_leds: 14\n  blink_hz: 1.5\n')
            with open(os.path.join(d, 'config', 'lokal', 'lichter.yaml'), 'w') as f:
                f.write('lichter:\n  anzahl_leds: 20\n')
            self.assertEqual(knoten.lade_einstellungen(d), {'anzahl_leds': 20, 'blink_hz': 1.5})


def _lade_knotenmodul():
    """lichter/lichter.py ueber den Pfad laden (Ordner und Datei heissen gleich)."""
    import importlib.util
    pfad = os.path.join(HIER, '..', 'lichter', 'lichter.py')
    spec = importlib.util.spec_from_file_location('lichter_knoten', pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class Knoten(unittest.TestCase):
    def test_veroeffentlicht_zustand_und_wertet_ki_aus(self):
        knoten = _lade_knotenmodul()
        n = knoten.Lichtsteuerung(knoten.lade_einstellungen())
        self.assertIn('/ki/befehl', n.subs)
        self.assertIn('/lichter/kommando', n.subs)
        self.assertNotIn('/cmd_vel', n.pubs, 'Lichter duerfen keine Fahrbefehle senden')
        n.subs['/ki/befehl'](knoten.String(data=json.dumps(manoever(dreh=-0.8))))
        n._takt()
        z = json.loads(n.pubs['/lichter/zustand'].letzte.data)
        self.assertEqual(z['blinker'], 'rechts')
        self.assertEqual(len(z['leiste']), 14)
        n.subs['/ki/befehl'](knoten.String(data='{kaputt'))
        n.subs['/lichter/kommando'](knoten.String(data='quatsch'))

    def test_unbekannter_ausgang_wird_abgelehnt(self):
        knoten = _lade_knotenmodul()
        with self.assertRaises(ValueError):
            knoten.Lichtsteuerung({'ausgang': 'raten'})


if __name__ == '__main__':
    unittest.main()
