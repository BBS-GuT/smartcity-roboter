#!/usr/bin/env python3
"""Arm-Gehirn (armgehirn/): Sicherheitsregel, Ablauf, Pruefung, Speichern, lageabhaengiges Lernen.

Nur Software: Attrappen fuer Kamera und Arm, kein ROS, kein Geraet. Belegt NICHT, dass der echte Arm greift.
"""
from pathlib import Path
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest

import numpy as np

REPO = Path(__file__).resolve().parents[1]
for _d in ('lib', 'armgehirn', 'sim'):
    sys.path.insert(0, str(REPO / _d))
import arm as armlib       # noqa: E402
import blick as blicklib   # noqa: E402
import greifen             # noqa: E402
import protokoll as prot   # noqa: E402
import pruefung            # noqa: E402
import sicherheit          # noqa: E402
from gehirn import ArmGehirn  # noqa: E402

FAHR = [90, 120, 10, 20, 90, 30]
KAMERA = {'kamera_hoehe': 0.22, 'kamera_neigung': 32.0, 'kamera_fov': 70.0, 'kamera_x': 0.12}
WUERFEL = {'vor': 0.15, 'seite': 0.0, 'breite': 0.04, 'hoehe': 0.04}
PERSON = {'name': 'Person', 'sicher': 0.6, 'box': (10, 10, 50, 120)}


def bild(objekt=WUERFEL, ki=()):
    return {'objekt': None if objekt is None else dict(objekt), 'objekte': list(ki)}


class Welt:
    """Attrappe: Gegenstand im Roboter-System; Augen liefern ihn je Blick (gedreht), Arm fuehrt Buch und 'greift'
    nach Plan (zugreifen -> gefasst, loslassen -> liegt an der Ablage)."""

    def __init__(self, objekt=WUERFEL, ki=(), greift=True):
        self.objekt, self.ki, self.greift = (dict(objekt) if objekt else None), list(ki), greift
        self.befehle, self.gehalten, self.ki_beim_greifen = [], False, []
        self.gespeichert = {}
        self.schulter_x = armlib.Kinematik().g['schulter'][0]

    # Augen
    def boden_lernen(self, schluessel, kamera, bilder=8):
        self.gespeichert[schluessel] = [0.0]

    def kann(self, schluessel):
        return True

    def messen(self, schluessel, kamera, bilder=6):
        grad = blicklib.drehung_zu((0.10, -0.18), self.schulter_x) if schluessel == 'ablage' else int(schluessel.split('@')[1])
        o = None
        if self.objekt is not None and not self.gehalten:
            # Roboter-System -> System der gedrehten Kamera (Umkehrung von blick.ins_roboter_system)
            a = math.radians(-grad)
            x, y = self.objekt['vor'] + self.objekt['breite'] / 2 - self.schulter_x, self.objekt['seite']
            xm, ym = self.schulter_x + x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
            if abs(ym) < 0.1:
                o = dict(self.objekt, vor=xm - self.objekt['breite'] / 2, seite=ym)
        return [bild(o, self.ki) for _ in range(bilder)]

    def als_dict(self):
        return dict(self.gespeichert)

    # Arm
    def fahre(self, winkel, zeit_ms=1500):
        self.befehle.append(list(winkel))
        if self.objekt is None:
            return None
        if winkel[5] > 60 and not self.gehalten and self.greift and len(self.befehle) > 1 and self.befehle[-2][5] <= 60:
            self.gehalten = True
            self.ki_beim_greifen = list(self.ki)
        elif winkel[5] <= 60 and self.gehalten:
            self.gehalten = False
            self.objekt.update(vor=0.10 - self.objekt['breite'] / 2, seite=-0.18)
        return None

    def warte(self, s):
        pass


def gehirn(welt, tmp, **cfg):
    pol = greifen.Politik('eigene', lokal=os.path.join(tmp, 'greifen.json'))
    return ArmGehirn(welt, welt, armlib.Kinematik(), pol, FAHR, KAMERA, cfg=cfg, auf=30, zu=130,
                     protokoll=prot.Protokoll(os.path.join(tmp, 'armgehirn')),
                     zustand_datei=os.path.join(tmp, 'armgehirn.json'), rng=np.random.default_rng(1))


def zugegriffen(befehle):
    return any(b[5] > 60 for b in befehle)


class Sicherheitsregel(unittest.TestCase):
    def test_wuerfel_darf(self):
        self.assertTrue(sicherheit.entscheide([bild() for _ in range(6)])['darf'])

    def test_person_im_bild_nie(self):
        for sicher in (0.3, 0.9):
            e = sicherheit.entscheide([bild(ki=[dict(PERSON, sicher=sicher)])] + [bild() for _ in range(5)])
            self.assertFalse(e['darf'])
            self.assertEqual(e['art'], 'verboten')

    def test_person_beim_umschauen_in_anderer_richtung_nie(self):
        e = sicherheit.entscheide([bild() for _ in range(6)], umgebung=[PERSON])
        self.assertFalse(e['darf'])

    def test_figur_ohne_ki_erkennung_nie(self):
        figur = dict(WUERFEL, breite=0.025, hoehe=0.075)
        e = sicherheit.entscheide([bild(figur) for _ in range(6)])
        self.assertFalse(e['darf'])

    def test_im_zweifel_nicht(self):
        faelle = {
            'zu selten gesehen': [bild()] * 2 + [bild(None)] * 4,
            'bewegt sich (Hand)': [bild(dict(WUERFEL, vor=0.15 + 0.01 * i)) for i in range(6)],
            'zu gross': [bild(dict(WUERFEL, breite=0.12, hoehe=0.05))] * 6,
            'am Bildrand': [bild(dict(WUERFEL, rand=True))] * 6,
            'Kamera-KI fehlt': [bild(ki=[{'name': 'KI fehlt', 'ki_fehlt': True}])] * 6,
            'keine Bilder': [],
        }
        for name, bilder in faelle.items():
            with self.subTest(name):
                self.assertFalse(sicherheit.entscheide(bilder)['darf'])

    def test_nur_klassen(self):
        cfg = {'raeumbar_klassen': ['Wuerfel'], 'nur_klassen': True}
        self.assertFalse(sicherheit.entscheide([bild()] * 6, cfg)['darf'])
        ki = [{'name': 'Wuerfel', 'sicher': 0.8}]
        self.assertTrue(sicherheit.entscheide([bild(ki=ki)] * 6, cfg)['darf'])


class Ablauf(unittest.TestCase):
    def test_wuerfel_greifen_ablegen_pruefen_lernen(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = Welt()
            g = gehirn(w, tmp)
            e = g.versuch('greifen')
            self.assertEqual(e['ergebnis'], 'abgelegt', e)
            self.assertTrue(e['richtig'])
            self.assertEqual(w.befehle[-1][:5], g.grund[:5])          # zurueck in Grundstellung
            self.assertEqual(g.politik.versuche, 1)
            self.assertTrue(os.path.exists(os.path.join(tmp, 'greifen.json')))
            self.assertEqual(len(prot.Protokoll(os.path.join(tmp, 'armgehirn')).zeilen), 1)

    def test_person_nie_greifen_kein_zugriff(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = Welt(ki=[PERSON])
            e = gehirn(w, tmp).versuch('nicht_greifen')
            self.assertEqual(e['ergebnis'], 'nicht_gegriffen')
            self.assertTrue(e['richtig'])
            self.assertFalse(zugegriffen(w.befehle))
            # nur Blickstellungen (Greifer offen, Hand oben), nie zum Gegenstand hinunter
            self.assertTrue(all(b[5] == 30 for b in w.befehle))

    def test_figur_ohne_ki_nie_greifen(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = Welt(objekt=dict(WUERFEL, breite=0.025, hoehe=0.075))
            e = gehirn(w, tmp).versuch('nicht_greifen')
            self.assertEqual(e['ergebnis'], 'nicht_gegriffen')
            self.assertFalse(zugegriffen(w.befehle))

    def test_mensch_waehrend_greifen_kein_abbruch(self):
        """Projektvorgabe: laeuft waehrend des Greifens ein Mensch ins Bild, wird NICHT abgebrochen."""
        with tempfile.TemporaryDirectory() as tmp:
            w = Welt()
            g = gehirn(w, tmp)
            alt = w.fahre

            def fahre(winkel, zeit_ms=1500):
                if winkel[5] > 60:
                    w.ki = [PERSON]        # Mensch laeuft ins Bild, sobald der Greifer zugeht
                return alt(winkel, zeit_ms)
            w.fahre = fahre
            e = g.versuch('greifen')
            self.assertEqual(w.ki_beim_greifen, [PERSON])
            self.assertEqual(e['ergebnis'], 'abgelegt', e)
            self.assertEqual(g.zustand, 'fertig')

    def test_abbrechen_von_aussen_keine_weitere_bewegung(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = Welt()
            g = gehirn(w, tmp)
            alt = w.fahre

            def fahre(winkel, zeit_ms=1500):
                if winkel[5] > 60:
                    g.abbrechen()          # z. B. Panel: abbrechen, waehrend der Greifer zugeht
                return alt(winkel, zeit_ms)
            w.fahre = fahre
            e = g.versuch('greifen')
            self.assertEqual(e['ergebnis'], 'abgebrochen')
            self.assertEqual(g.zustand, 'abgebrochen')
            self.assertGreater(w.befehle[-1][5], 60)    # danach kein einziger Armbefehl mehr
            self.assertEqual(g.politik.versuche, 0)     # nichts Halbes gelernt

    def test_start_status_schnittstelle(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = gehirn(Welt(), tmp)
            self.assertEqual(g.status()['zustand'], 'bereit')
            self.assertTrue(g.start('greifen'))
            e = g.warte_fertig(30)
            st = g.status()
            self.assertEqual(st['zustand'], 'fertig')
            self.assertEqual(st['ergebnis']['ergebnis'], e['ergebnis'])
            self.assertIn('gesperrt', st['antrieb'])

    def test_unerreichbar_faehrt_nicht(self):
        """Arm reicht nicht hin: er faehrt NICHT naeher heran (Antrieb gesperrt), sondern meldet es."""
        with tempfile.TemporaryDirectory() as tmp:
            w = Welt(objekt=dict(WUERFEL, vor=0.26))
            e = gehirn(w, tmp).versuch('greifen')
            self.assertEqual(e['ergebnis'], 'nicht_erreichbar', e)
            self.assertFalse(zugegriffen(w.befehle))

    def test_nicht_gefasst_wird_als_daneben_gelernt(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = Welt(greift=False)
            g = gehirn(w, tmp)
            e = g.versuch('greifen')
            self.assertEqual(e['ergebnis'], 'unberuehrt')
            self.assertEqual(g.politik.speicher[-1][10], greifen.UNBERUEHRT)


class AntriebGesperrt(unittest.TestCase):
    def test_kein_fahrbefehl_im_arm_gehirn(self):
        """Kein Sender fuer Fahrbefehle: weder /cmd_vel noch Twist in armgehirn/ (ausser in Kommentaren)."""
        for datei in (REPO / 'armgehirn').glob('*.py'):
            code = [z.split('#')[0] for z in datei.read_text().splitlines()]
            code = '\n'.join(z for z in code if not z.strip().startswith(('"', "'")))
            with self.subTest(datei.name):
                self.assertNotIn('cmd_vel', code)
                self.assertNotIn('Twist', code)
                self.assertNotIn("'manoever'", code)

    def test_startet_nicht_neben_fahr_gehirn(self):
        import knoten

        class Knoten:
            def __init__(self, namen):
                self.namen = namen

            def get_node_names(self):
                return self.namen
        self.assertEqual(knoten.fahr_gehirn_laeuft(Knoten(['line_follower', 'panel']), 0), ['line_follower'])
        self.assertEqual(knoten.fahr_gehirn_laeuft(Knoten(['ki_zentrale']), 0), ['ki_zentrale'])
        self.assertEqual(knoten.fahr_gehirn_laeuft(Knoten(['panel']), 0), [])


class Pruefung(unittest.TestCase):
    ABLAGE = (0.10, -0.18)

    def an(self, x, y):
        return [dict(WUERFEL, vor=x - 0.02, seite=y)]

    def test_faelle(self):
        f = [('abgelegt', [], self.an(0.11, -0.17), None),
             ('unberuehrt', self.an(0.17, 0.0), [], None),
             ('verschoben', self.an(0.17, 0.015), [], None),
             ('verschoben', self.an(0.21, 0.05), [], None),            # weggeschoben, aber noch im Bild
             ('unklar', [], [], None),                                 # weg, aber nirgends: nicht lernen
             ('verloren', [], [], True),
             ('unklar', None, [], None)]
        for erwartet, alt, ablage, greifer in f:
            with self.subTest(erwartet):
                self.assertEqual(pruefung.bewerte(WUERFEL, alt, ablage, self.ABLAGE, greifer)['ergebnis'], erwartet)

    def test_frueher_haette_wegschieben_als_erfolg_gezaehlt(self):
        b = pruefung.bewerte(WUERFEL, [], [], self.ABLAGE)
        self.assertTrue(b['alter_ort_frei'])
        self.assertNotEqual(b['ergebnis'], 'abgelegt')
        self.assertIsNone(b['belohnung'])


class Speichern(unittest.TestCase):
    SKRIPT = '''
import sys, json, numpy as np
sys.path.insert(0, {lib!r})
import greifen
p = greifen.Politik('eigene', lokal={datei!r})
if sys.argv[1] == 'lernen':
    rng = np.random.default_rng(4)
    for i in range(12):
        o = {{'vor': 0.13 + 0.005 * i, 'seite': -0.04 + 0.007 * i, 'breite': 0.04, 'hoehe': 0.04}}
        a, _ = p.vorschlag(o, rng)
        p.ergebnis(o, a, ['abgelegt', 'verschoben', 'unberuehrt', False][i % 4])
        p.speichern()
print(json.dumps({{'W': p.W.tolist(), 'versuche': p.versuche, 'speicher': p.speicher}}))
'''

    def test_neustart_lernstand_identisch(self):
        """Prozess beenden, neu starten: Lernstand bit-genau gleich (gleiche Versuche + feste Zufallszahl)."""
        with tempfile.TemporaryDirectory() as tmp:
            datei = os.path.join(tmp, 'lokal', 'greifen.json')
            skript = self.SKRIPT.format(lib=str(REPO / 'lib'), datei=datei)
            a = json.loads(subprocess.run([sys.executable, '-c', skript, 'lernen'], capture_output=True, text=True,
                                          check=True).stdout)
            b = json.loads(subprocess.run([sys.executable, '-c', skript, 'laden'], capture_output=True, text=True,
                                          check=True).stdout)
            self.assertEqual(a['versuche'], 12)
            self.assertEqual(a, b)
            self.assertFalse(os.path.exists(datei + '.neu'))

    def test_andere_modelle_bleiben_und_kaputte_datei_wird_gesichert(self):
        with tempfile.TemporaryDirectory() as tmp:
            datei = os.path.join(tmp, 'greifen.json')
            p1 = greifen.Politik('eigene', lokal=datei)
            p1.ergebnis(WUERFEL, [0.0, 0.0, 0.0], True)
            p1.speichern()
            p2 = greifen.Politik('yahboom', lokal=datei)
            p2.ergebnis(WUERFEL, [0.0, 0.0, 0.0], False)
            p2.speichern()
            with open(datei) as f:
                self.assertEqual(set(json.load(f)['modelle']), {'eigene', 'yahboom'})
            with open(datei, 'w') as f:
                f.write('{kaputt')
            p2.speichern()
            self.assertTrue(any('.kaputt_' in n for n in os.listdir(tmp)))

    def test_alte_datei_wird_weiterbenutzt(self):
        """config/lokal/greifen.json vom bisherigen Verfahren (nur Erfolg 1/0) wird gelesen und weitergelernt."""
        with tempfile.TemporaryDirectory() as tmp:
            datei = os.path.join(tmp, 'greifen.json')
            zeile = list(greifen.merkmale(WUERFEL)) + [0.01, 0.0, 0.0, 0.0225, -0.017, 0.015, 1.0]
            with open(datei, 'w') as f:
                json.dump({'modelle': {'eigene': {'speicher': [zeile] * 5, 'verlauf': [1] * 5, 'versuche': 5,
                                                  'erfolge': 5}}}, f)
            p = greifen.Politik('eigene', lokal=datei)
            self.assertEqual((p.versuche, len(p.speicher)), (5, 5))

    def test_umschauen_und_protokoll_ueberleben_neustart(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = gehirn(Welt(), tmp)
            g.versuch('greifen')
            zaehler = g.blick_lernen.als_dict()
            g2 = gehirn(Welt(), tmp)
            self.assertEqual(g2.blick_lernen.als_dict(), zaehler)
            self.assertEqual(g2.politik.versuche, 1)
            self.assertEqual(g2.protokoll.stand()['versuche'], 1)


class Umschauen(unittest.TestCase):
    def test_blickstellungen_ohne_eingespeicherte_pose(self):
        s = blicklib.blickstellungen(KAMERA, FAHR, armlib.Kinematik().g)
        self.assertTrue(s)
        for x in s:
            nah, fern = x['sicht']
            self.assertLessEqual(nah, blicklib.BEREICH[0])
            self.assertGreaterEqual(fern, blicklib.BEREICH[1])
            self.assertIsNone(armlib.pruefe(x['pose'], 1500))
        # in der Fahrstellung sieht die Kamera den Greifbereich NICHT (Grund fuer das Umschauen)
        self.assertGreater(blicklib.sichtbereich(KAMERA)[0], 0.2)

    def test_findet_gegenstand_seitlich_und_lernt_die_richtung(self):
        with tempfile.TemporaryDirectory() as tmp:
            # liegt weit links: geradeaus nicht im Bild (Attrappe: |seitlich| < 10 cm), erst beim Umschauen
            w = Welt(objekt=dict(WUERFEL, vor=0.12, seite=0.12))
            g = gehirn(w, tmp)
            bilder, blick, _, n = g._umschauen()
            self.assertIsNotNone(blick)
            self.assertNotEqual(blick[3], 0)
            o = bilder[0]['objekt']
            self.assertAlmostEqual(o['seite'], 0.12, places=6)        # zurueck ins Roboter-System gerechnet
            for _ in range(15):
                g._umschauen()
            erste = g.blick_lernen.reihenfolge(g._blicke(), erkunden=False)[0]
            self.assertGreater(erste[3], 0)                            # zuerst nach links schauen (bewaehrt)
            self.assertGreater(g.blick_lernen.zaehler[erste[0]][0], 0)

    def test_mittig_immer_aus_geradem_blick(self):
        """RM02 22.10.: mittiger Wuerfel wurde zufaellig im gedrehten Blick vermessen -> seitlich daneben gegriffen.
        Geradeaus kommt jetzt immer zuerst, egal was das Umschauen gelernt hat."""
        with tempfile.TemporaryDirectory() as tmp:
            g = gehirn(Welt(), tmp)
            for schluessel, *_ in g._blicke():          # gedrehte Blicke als "bewaehrt" vorbelasten
                if not schluessel.endswith('@+0'):
                    g.blick_lernen.zaehler[schluessel] = [50, 50]
            for _ in range(20):
                _, blick, _, _ = g._umschauen()
                self.assertEqual(blick[3], 0, blick[0])

    def test_ins_roboter_system_und_zurueck(self):
        o = dict(WUERFEL, seite=0.03)
        for grad in (25, -50):
            g = blicklib.ins_roboter_system(o, grad, 0.0336)
            r = blicklib.ins_roboter_system(g, -grad, 0.0336)
            self.assertAlmostEqual(r['vor'], o['vor'], places=9)
            self.assertAlmostEqual(r['seite'], o['seite'], places=9)


class LageabhaengigesLernen(unittest.TestCase):
    """Ausgedachte Welt: die richtige Korrektur haengt von der Lage ab (z. B. Massstabsfehler der Tiefe)."""

    @staticmethod
    def richtig(o):
        return np.array([0.004 + 0.25 * (o['vor'] - 0.15), -0.003 + 0.3 * o['seite'], 0.002])

    def lauf(self, lage, n, rng):
        pol = greifen.Politik('test', lokal=None, vortrainiert=None, lage=lage)
        for _ in range(n):
            o = {'vor': rng.uniform(0.11, 0.21), 'seite': rng.uniform(-0.07, 0.07), 'breite': 0.06, 'hoehe': 0.04}
            a, _ = pol.vorschlag(o, rng)
            e = np.array(a) - self.richtig(o) + rng.normal(0, 0.0015, 3)
            r, zlo, zhi = greifen.spielraum(o)
            d = np.hypot(e[0], e[1]) - r
            erg = 'abgelegt' if d < 0 and zlo < e[2] < zhi else ('verschoben' if d < greifen.KNAPP else 'unberuehrt')
            pol.ergebnis(o, a, erg)
        return pol

    def treffer(self, pol, rng, n=200):
        ok = 0
        for _ in range(n):
            o = {'vor': rng.uniform(0.11, 0.21), 'seite': rng.uniform(-0.07, 0.07), 'breite': 0.06, 'hoehe': 0.04}
            e = pol.vorschlag(o, erkunden=False)[0] - self.richtig(o)
            ok += np.hypot(e[0], e[1]) < greifen.spielraum(o)[0] and abs(e[2]) < 0.01
        return ok / n

    def test_konvergiert_und_schlaegt_feste_korrektur(self):
        rng = np.random.default_rng(8)
        mit = self.lauf(True, 80, rng)
        ohne = self.lauf(False, 80, np.random.default_rng(8))
        q_mit, q_ohne = self.treffer(mit, np.random.default_rng(9)), self.treffer(ohne, np.random.default_rng(9))
        # gelernte Steigung seitlich: richtig 0,3 je m = 1,5 cm je 5 cm
        st = mit.lernstand()['lage_cm_je_5cm']['links'][1]
        # (Streuung ueber Zufallszahlen: lageabhaengig 79-100 %, feste Korrektur 40-50 %)
        self.assertGreater(q_mit, 0.75, (q_mit, q_ohne))
        self.assertGreater(q_mit, q_ohne + 0.2, (q_mit, q_ohne))
        self.assertTrue(0.4 < st < 2.5, st)                    # Richtung und Groesse der Lageabhaengigkeit

    def test_grenzen_beim_ausprobieren(self):
        pol = greifen.Politik('test', lokal=None, vortrainiert=None)
        rng = np.random.default_rng(1)
        for _ in range(200):
            a, _ = pol.vorschlag(dict(WUERFEL, seite=0.07), rng)
            self.assertTrue(np.all(np.abs(a) <= greifen.GRENZE + 1e-12))


class Fortschritt(unittest.TestCase):
    def test_quote_und_ziel(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = prot.Protokoll(tmp)
            for i in range(35):
                p.schreiben({'erwartet': 'greifen', 'ergebnis': 'abgelegt' if i % 20 else 'verschoben',
                             'richtig': bool(i % 20), 'zielfehler_cm': 0.8})
            self.assertFalse(p.stand()['ziel_erreicht'])          # noch keine verbotenen Gegenstaende geprueft
            for _ in range(5):
                p.schreiben({'erwartet': 'nicht_greifen', 'ergebnis': 'nicht_gegriffen', 'richtig': True})
            st = p.stand()
            self.assertTrue(st['ziel_erreicht'], st)
            self.assertEqual(len(st['quote_je_10']), 4)
            self.assertTrue(os.path.exists(os.path.join(tmp, 'fortschritt.csv')))
            p.schreiben({'erwartet': 'nicht_greifen', 'ergebnis': 'abgelegt', 'richtig': False})
            self.assertFalse(prot.Protokoll(tmp).stand()['ziel_erreicht'])   # Figur gegriffen: nie "fertig"


class Uebungswelt(unittest.TestCase):
    def test_einige_versuche_in_der_uebungswelt(self):
        import armgehirn_sim as AS
        import greifen_welt as GW
        from augen import Augen
        rng = np.random.default_rng(3)
        welt = AS.SimWelt(GW.zufalls_roboter(rng, 'm3pro', staerke=0.3), rng)
        with tempfile.TemporaryDirectory() as tmp:
            g = ArmGehirn(Augen(welt), welt, welt.planer_kin, greifen.Politik('eigene', lokal=None), GW.FAHR,
                          AS.kamera_nenn(), auf=GW.AUF, zu=GW.ZU, rng=rng, protokoll=prot.Protokoll(tmp))
            g.einrichten()
            erg = []
            for art in ('wuerfel', 'wuerfel', 'figur', 'wuerfel'):
                welt.lege(art, 0.17, 0.0)
                erg.append(g.versuch('nicht_greifen' if art == 'figur' else 'greifen')['ergebnis'])
                welt.raeumen()
            self.assertEqual(erg[2], 'nicht_gegriffen')
            self.assertGreaterEqual(erg.count('abgelegt'), 2, erg)


if __name__ == '__main__':
    unittest.main(verbosity=2)
