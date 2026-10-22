#!/usr/bin/env python3
"""Fahr-Gehirn ohne Roboter: Speichern/Laden, Neustart behaelt Lernstand, Hindernis-Stopp hat Vorrang,
Fahrplan statt Zufall, Blinker vor dem Abbiegen, Pause gibt /cmd_vel frei, Messung/Diagnose.

Kein ROS (Attrappen aus tests/attrappen), kein Geraet. Was das NICHT belegt: siehe docs/fahrgehirn.md (Abnahme).
"""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TMP = tempfile.mkdtemp(prefix='fahrgehirn_test_')
os.environ['SMARTCITY_FAHRGEHIRN'] = os.path.join(TMP, 'fahrgehirn.json')
os.environ['SMARTCITY_FAHRGEHIRN_LOGS'] = os.path.join(TMP, 'logs')
sys.path.insert(0, str(ROOT / 'tests' / 'attrappen'))
sys.path.insert(0, str(ROOT / 'line_follower'))
sys.path.insert(0, str(ROOT / 'fahrgehirn'))
import linie  # noqa: E402
import lernen  # noqa: E402
import messung  # noqa: E402
from blinker import BlinkerAttrappe  # noqa: E402
from fahrplan import Fahrplan, plan_aus_text  # noqa: E402
from gehirn import FahrGehirn  # noqa: E402
from sicherheit import HindernisRegel, im_pfad_schlauch, kreuzungs_pfad  # noqa: E402
import fahrgehirn as fg  # noqa: E402

B, H = 640, 480


def bild(linien):
    """Kamerabild mit schwarzen Linien [((x, y), (x, y)), ...] in Metern (x vorne, y links), wie test_kreuzung.py."""
    s = linie.LinienSucher()
    s._vogel(B, H)
    bw, bh = s.vogel_groesse
    boden = np.full((bh, bw), 255, np.uint8)
    for a, b in linien:
        cv2.line(boden, tuple(int(v) for v in s._zu_raster(*a)), tuple(int(v) for v in s._zu_raster(*b)), 0,
                 int(0.025 / s.RASTER))
    return cv2.cvtColor(cv2.warpPerspective(boden, np.linalg.inv(s.H), (B, H), borderValue=255), cv2.COLOR_GRAY2BGR)


T = bild([((0.0, 0.0), (0.36, 0.0)), ((0.36, -0.5), (0.36, 0.5))])            # T-Stoss: links / rechts
ABZWEIG = bild([((0.0, 0.0), (0.9, 0.0)), ((0.33, 0.0), (0.33, 0.6))])          # Gerade mit Abzweig nach links
NUR_GERADE = bild([((0.0, 0.0), (0.9, 0.0))])


def neues_gehirn(ordner, plan=('links', 'rechts')):
    blinker = BlinkerAttrappe(log=lambda *_: None)
    lern = lernen.Lernen(os.path.join(ordner, 'l.json'), log=lambda *_: None)
    return FahrGehirn(list(plan), lern, messung.Protokoll(os.path.join(ordner, 'logs')), blinker,
                      log=lambda *_: None)


def kreuzung_fahren(g, t, drehung_grad, richtungen=(math.radians(90), math.radians(-90)), schritte=40):
    """Eine Kreuzung: waehlen, dann 'schritte' Takte fahren und dabei gleichmaessig drehen. Rueckgabe: neue Zeit."""
    gier0 = g._gier
    g.kreuzung_waehlen(list(richtungen), gier0, jetzt=t)
    for i in range(schritte):
        t += 0.05
        gier = gier0 + math.radians(drehung_grad) * min(1.0, (i + 1) / (schritte * 0.6))
        g.takt(t, 0.05, 0.4, 0.0, {'quer': 0.005, 'kurs': 0.0, 'kruemmung': 0.0}, 'Linie: +0.5 cm', gier)
    return t


def runde_fahren(g, t, ok=True):
    """Eine Runde mit Plan (links, rechts). ok=False: an der ersten Kreuzung geradeaus statt links."""
    t = kreuzung_fahren(g, t, 90 if ok else 0)
    return kreuzung_fahren(g, t, -90)


class FahrplanTest(unittest.TestCase):
    def test_plan_pruefen(self):
        self.assertEqual(plan_aus_text('Links, geradeaus;rechts'), ('links', 'geradeaus', 'rechts'))
        for falsch in ('', 'links, hoch', []):
            with self.assertRaises(ValueError):
                plan_aus_text(falsch)

    def test_fahrplan_statt_zufall_am_bild(self):
        """Gleiches Bild, gleicher Plan -> immer derselbe Ast. Der Zufall wird gar nicht gefragt."""
        for wunsch, grad in (('links', 90), ('rechts', -90)):
            for _ in range(10):
                s = linie.LinienSucher()
                plan = Fahrplan([wunsch])
                s.waehler = lambda r, g, p=plan: p.ast_waehlen(r)
                with patch.object(s.zufall, 'choice', side_effect=AssertionError('Zufall benutzt')):
                    erg = s.suche(T, 0.0)
                self.assertTrue(erg.get('kreuzung_neu'))
                self.assertAlmostEqual(math.degrees(s.wahl), grad, delta=20)

    def test_ohne_waehler_wie_bisher_zufaellig(self):
        """Grundbetrieb unveraendert: ohne waehler entscheidet der Zufall (beide Seiten kommen vor)."""
        seiten = set()
        for i in range(30):
            s = linie.LinienSucher()
            s.zufall.seed(i)
            s.suche(T, 0.0)
            seiten.add(math.degrees(s.wahl) > 0)
        self.assertEqual(seiten, {True, False})

    def test_wunsch_ast_fehlt(self):
        """Gewuenschte Richtung nicht im Bild: erst warten (None), nach wahl_warten Bildern der naechstbeste Ast."""
        with tempfile.TemporaryDirectory() as d:
            g = neues_gehirn(d, ('geradeaus',))
            richt = [math.radians(90), math.radians(-90)]
            for _ in range(g.wahl_warten - 1):
                self.assertIsNone(g.kreuzung_waehlen(richt, 0.0, jetzt=1.0))
            self.assertIsNotNone(g.kreuzung_waehlen(richt, 0.0, jetzt=1.0))
            self.assertNotEqual(g.kreuzung.d['gewaehlt'], 'geradeaus')


class AbbiegenHalten(unittest.TestCase):
    def test_gerade_ueberschreibt_wahl_nicht(self):
        """Links abbiegen von einer durchgehenden Linie: kurz vor der Kreuzung sieht die Kamera nur noch die Gerade.
        Mit abbiegen_halten wird die Gerade dann nicht genommen (Wahl links bleibt), ohne (Grundbetrieb) schon."""
        for halten, gefunden in ((True, False), (False, True)):
            s = linie.LinienSucher({'abbiegen_halten': halten})
            s.waehler = lambda r, g: max(r)                  # links
            erg = s.suche(ABZWEIG, 0.0, pos=(0.0, 0.0))
            self.assertTrue(erg.get('kreuzung_neu'))
            erg = s.suche(NUR_GERADE, 0.0, pos=(0.10, 0.0))
            self.assertEqual(erg['gefunden'], gefunden)
            if halten:
                self.assertIsNotNone(s.wahl)
                # eingelenkt (Roboter zeigt jetzt in Richtung des Astes): normale Liniensuche wieder
                erg = s.suche(NUR_GERADE, s.wahl, pos=(0.2, 0.1))
                self.assertTrue(erg['gefunden'])

    def test_standard_aus(self):
        self.assertFalse(linie.STANDARD['abbiegen_halten'])


class LernenTest(unittest.TestCase):
    def test_speichern_laden_identisch_und_atomar(self):
        with tempfile.TemporaryDirectory() as d:
            pfad = os.path.join(d, 'sub', 'fahrgehirn.json')
            l1 = lernen.Lernen(pfad, log=lambda *_: None)
            for w in (60, 61, 58, 70, 71):
                l1.runde_fertig(w, 'pendeln')
                l1.speichern()
            self.assertFalse(os.path.exists(pfad + '.neu'))           # Hilfsdatei ist umbenannt
            with open(pfad + '.neu', 'w') as f:                         # halb geschrieben (Strom weg) ...
                f.write('{"kaputt')
            l2 = lernen.Lernen(pfad, log=lambda *_: None)               # ... aendert am Lernstand nichts
            self.assertEqual(l1.stand, l2.stand)
            self.assertEqual(l1.parameter(), l2.parameter())

    def test_kaputte_datei_wird_nicht_ueberschrieben(self):
        with tempfile.TemporaryDirectory() as d:
            pfad = os.path.join(d, 'fahrgehirn.json')
            with open(pfad, 'w') as f:
                f.write('kein json')
            l = lernen.Lernen(pfad, log=lambda *_: None)
            self.assertEqual(l.stand['champion'], lernen.startwerte())
            self.assertTrue(os.path.exists(pfad + '.kaputt'))

    def test_grenzen_auch_bei_handgeaenderter_datei(self):
        with tempfile.TemporaryDirectory() as d:
            pfad = os.path.join(d, 'fahrgehirn.json')
            stand = lernen.leerer_lernstand()
            stand['champion'].update({'speed': 5.0, 'threshold': -3, 'halt_abstand': 0.01})
            with open(pfad, 'w') as f:
                json.dump(stand, f)
            p = lernen.Lernen(pfad, log=lambda *_: None).parameter()
            self.assertEqual(p['speed'], lernen.PARAMETER['speed']['max'])
            self.assertEqual(p['threshold'], lernen.PARAMETER['threshold']['min'])
            self.assertNotIn('halt_abstand', p)                          # Sicherheit ist kein Lernparameter

    def test_ausprobieren_bleibt_in_den_grenzen(self):
        rng = np.random.default_rng(1)
        with tempfile.TemporaryDirectory() as d:
            l = lernen.Lernen(os.path.join(d, 'l.json'), log=lambda *_: None)
            arten = list(lernen.GRUPPEN)
            for _ in range(600):
                l.runde_fertig(float(rng.uniform(0, 100)), arten[int(rng.integers(len(arten)))])
                for n, v in l.parameter().items():
                    p = lernen.PARAMETER[n]
                    self.assertTrue(p['min'] <= v <= p['max'], (n, v))
            self.assertGreater(len(l.stand['versuche']), 50)

    def test_besserer_herausforderer_wird_champion(self):
        with tempfile.TemporaryDirectory() as d:
            l = lernen.Lernen(os.path.join(d, 'l.json'), log=lambda *_: None)
            l.runde_fertig(50, 'langsam')
            text = l.runde_fertig(50, 'langsam')
            self.assertIn('Neuer Versuch', text)
            name = l.stand['kandidat']['name']
            neu = l.stand['kandidat']['parameter'][name]
            l.runde_fertig(60, 'langsam')
            text = l.runde_fertig(60, 'langsam')
            self.assertIn('ANGENOMMEN', text)
            self.assertEqual(l.stand['champion'][name], neu)
            # schlechterer Versuch: alter Wert bleibt
            l.runde_fertig(60, 'langsam')
            name2 = l.stand['kandidat']['name']
            alt2 = l.stand['champion'][name2]
            l.runde_fertig(40, 'langsam')
            self.assertIn('verworfen', l.runde_fertig(40, 'langsam'))
            self.assertEqual(l.stand['champion'][name2], alt2)


class GehirnTest(unittest.TestCase):
    def test_blinker_vor_dem_abbiegen(self):
        with tempfile.TemporaryDirectory() as d:
            g = neues_gehirn(d)
            g.kommando('start', jetzt=0.0)
            self.assertEqual(g.blinker.verlauf, [])
            kreuzung_fahren(g, 0.0, 90)
            self.assertEqual([r for _, r in g.blinker.verlauf], ['links', 'aus'])
            k = messung.Protokoll(os.path.join(d, 'logs')).lies('kreuzungen.csv')[0]
            self.assertEqual(k['ergebnis'], 'ok')
            self.assertGreater(float(k['blink_vorlauf_s']), 0.0)        # Blinker war an, BEVOR er sich drehte
            # geradeaus: kein Blinker
            g2 = neues_gehirn(os.path.join(d, 'b'), ('geradeaus',))
            g2.kommando('start', jetzt=0.0)
            kreuzung_fahren(g2, 0.0, 0, richtungen=(0.0, math.radians(90)))
            self.assertEqual(g2.blinker.verlauf, [])

    def test_runden_messen_und_fortschritt(self):
        with tempfile.TemporaryDirectory() as d:
            g = neues_gehirn(d)
            g.kommando('start', jetzt=0.0)
            t = 0.0
            for i in range(12):
                t = runde_fahren(g, t, ok=(i % 3 != 0))
            p = messung.Protokoll(os.path.join(d, 'logs'))
            runden = p.gewertete_runden()
            self.assertEqual(len(runden), 12)
            self.assertEqual([int(r['kreuzungen']) for r in runden], [2] * 12)
            self.assertEqual(int(runden[0]['falsch_abgebogen']), 1)
            fortschritt = p.lies('fortschritt.csv')
            self.assertEqual(len(fortschritt), 1)
            self.assertAlmostEqual(float(fortschritt[0]['abbiege_quote']), 16 / 20)
            self.assertEqual(fortschritt[0]['hauptproblem'], 'falsch_abgebogen')

    def test_umsetzen_zaehlt_uebersprungene_als_nicht_erkannt(self):
        with tempfile.TemporaryDirectory() as d:
            g = neues_gehirn(d, ('links', 'rechts', 'geradeaus'))
            g.kommando('start', jetzt=0.0)
            g.kommando('fahrplan 2', jetzt=1.0)
            k = messung.Protokoll(os.path.join(d, 'logs')).lies('kreuzungen.csv')
            self.assertEqual([x['ergebnis'] for x in k], ['nicht_erkannt', 'nicht_erkannt'])
            self.assertEqual(g.plan.index, 2)

    def test_neustart_mitten_im_plan_wird_nicht_gewertet(self):
        with tempfile.TemporaryDirectory() as d:
            g = neues_gehirn(d)
            g.kommando('start', jetzt=0.0)
            t = kreuzung_fahren(g, 0.0, 90)                      # halbe Runde, dann "Neustart"
            g2 = neues_gehirn(d)
            self.assertEqual(g2.plan.index, 1)                   # Fahrplan-Position ist gespeichert
            g2.kommando('start', jetzt=t)
            t = kreuzung_fahren(g2, t, -90)                      # Rest der Runde: nicht gewertet
            t = runde_fahren(g2, t)                              # naechste ganze Runde: gewertet
            r = messung.Protokoll(os.path.join(d, 'logs')).lies('runden.csv')
            self.assertEqual([x['gewertet'] for x in r], ['False', 'True'])

    def test_hilfe_noetig_ohne_linie(self):
        with tempfile.TemporaryDirectory() as d:
            g = neues_gehirn(d)
            g.kommando('start', jetzt=0.0)
            for i in range(250):                                 # 12,5 s ohne Linie
                g.takt(i * 0.05, 0.05, 0.0, 0.0, None, 'KEINE LINIE -> STOPP', 0.0)
            self.assertTrue(g.zustand_info()['hilfe_noetig'])
            g.takt(13.0, 0.05, 0.1, 0.0, None, 'Linie: +0.5 cm', 0.0)   # wieder auf die Linie gesetzt
            self.assertFalse(g.zustand_info()['hilfe_noetig'])

    def test_diagnose(self):
        basis = {'kreuzungen': 6, 'kreuzungen_ok': 6, 'nicht_erkannt': 0, 'richtung_fehlt': 0, 'falsch_abgebogen': 0,
                 'linie_verloren_kreuzung': 0, 'linie_weg': 0, 'pendeln_cm': 0.05, 'abw_mittel_cm': 0.05,
                 'tempo_mittel': 0.24}
        self.assertEqual(messung.diagnose([basis])[0], 'langsam')
        self.assertEqual(messung.diagnose([dict(basis, nicht_erkannt=2, kreuzungen_ok=4)])[0], 'kreuzung_nicht_erkannt')
        self.assertEqual(messung.diagnose([dict(basis, linie_weg=2)])[0], 'linie_verloren')
        self.assertEqual(messung.diagnose([dict(basis, pendeln_cm=3.0)])[0], 'pendeln')
        self.assertEqual(messung.diagnose([dict(basis, abw_mittel_cm=1.0)])[0], 'abweichung')


_scan_nr = [0]


def scan(abstand_vorne):
    _scan_nr[0] += 1
    t = time.time() - 0.05 + _scan_nr[0] * 1e-6
    r = [2.0] * 360
    for k in range(177, 184):
        r[k] = abstand_vorne
    return types.SimpleNamespace(ranges=r, angle_min=-math.pi, angle_increment=2 * math.pi / 360,
                                 angle_max=math.pi - 2 * math.pi / 360, range_min=0.05, range_max=12.0,
                                 header=types.SimpleNamespace(stamp=types.SimpleNamespace(sec=int(t),
                                                                                          nanosec=int((t % 1) * 1e9))))


class KnotenTest(unittest.TestCase):
    def setUp(self):
        for n in ('fahrgehirn.json',):
            p = os.path.join(TMP, n)
            if os.path.exists(p):
                os.remove(p)
        self.n = fg.FahrGehirnKnoten()
        self.n.set_parameters([fg.Parameter('tiefe_pruefen', value=False)])
        self.n.gedaechtnis.hinzufuegen([(0.05 + 0.02 * k, 0.0) for k in range(30)])
        self.n.bild_zeit = time.time()
        self.n.stempel_ok = True
        self.n.gehirn.kommando('start')

    def lidar(self, abstand):
        self.n.on_scan(scan(abstand), '/scan0', 0)
        self.n.on_scan(scan(abstand), '/scan1', 1)

    def test_faehrt_ohne_hindernis(self):
        self.lidar(1.5)
        lin, _, _, status = self.n.entscheide()
        self.assertGreater(lin, 0.0, status)

    def test_hindernis_stopp_hat_vorrang_und_wartet(self):
        self.lidar(0.25)                                    # 25 cm vor dem Roboter auf der Linie
        # Vorrang auch vor einer offenen Kreuzung, einem KI-Manoever und dem Panel-Tempo
        self.n.gehirn.kreuzung_waehlen([math.radians(90)], 0.0)
        self.n.ki = (time.time(), {'aktion': 'manoever', 'manoever': {'lin': 0.1}, 'aufnahme': time.time()})
        self.n.on_tempo(types.SimpleNamespace(data=0.5))
        lin, quer, dreh, status = self.n.entscheide()
        self.assertEqual((lin, quer, dreh), (0.0, 0.0, 0.0))
        self.assertIn('HINDERNIS', status)
        # Hindernis weg: erst nach frei_warten weiter (nicht beim ersten freien Scan)
        self.lidar(1.5)
        lin, _, _, status = self.n.entscheide()
        self.assertEqual(lin, 0.0)
        self.assertIn('warte', status)
        self.n.regel.blockiert_bis -= self.n.regel.frei_warten
        lin, _, _, status = self.n.entscheide()
        self.assertGreater(lin, 0.0, status)

    def test_ohne_lidar_kein_fahren(self):
        lin, _, _, status = self.n.entscheide()
        self.assertEqual(lin, 0.0)
        self.assertIn('LIDAR', status)

    def test_tiefe_unbekannt_haelt(self):
        self.lidar(1.5)
        self.n.set_parameters([fg.Parameter('tiefe_pruefen', value=True)])
        lin, _, _, status = self.n.entscheide()
        self.assertEqual(lin, 0.0)
        self.assertIn('TIEFENKAMERA', status)

    def test_lernen_aendert_keine_sicherheitswerte(self):
        werte = (self.n.regel.halt_abstand, self.n.regel.frei_warten, self.n.p('notbremse_dist'))
        for _ in range(30):
            self.n.lern.runde_fertig(50.0, 'langsam')
            self.n.parameter_uebernehmen()
        self.assertEqual(werte, (self.n.regel.halt_abstand, self.n.regel.frei_warten, self.n.p('notbremse_dist')))

    def test_pause_gibt_cmd_vel_frei(self):
        self.lidar(1.5)
        pub = self.n.pub.pub
        self.n.steuern()
        n0 = pub.n
        self.n.gehirn.kommando('pause')
        self.n.steuern()                                   # direkt nach der Pause: noch Stopp-Befehle
        self.assertEqual(pub.n, n0 + 1)
        self.assertEqual(pub.letzte.linear.x, 0.0)
        self.n.gehirn.zustand_seit -= 1.0
        self.n.steuern()                                   # danach: nichts mehr (anderes Gehirn darf fahren)
        self.assertEqual(pub.n, n0 + 1)
        self.assertEqual(self.n.gehirn.kommando('weiter'), 'faehrt')
        self.n.steuern()
        self.assertEqual(pub.n, n0 + 2)

    def test_blinker_ueber_bild_und_topic(self):
        self.lidar(1.5)
        self.n.bild_zeit = time.time() - 1.0               # sonst wird das Bild als "zu schnell" ausgelassen
        stempel = types.SimpleNamespace(sec=int(time.time()), nanosec=0)
        self.n.on_image(types.SimpleNamespace(img=T, header=types.SimpleNamespace(stamp=stempel)))
        self.assertTrue(self.n.gehirn.kreuzung_aktiv())
        self.assertEqual(self.n.blinker.zustand, 'links')   # Standardplan beginnt mit 'links'
        self.assertEqual(self.n.pubs['/fahrgehirn/blinker'].letzte.data, 'links')
        self.assertAlmostEqual(math.degrees(self.n.sucher.wahl), 90, delta=20)


    def test_haus_hinter_t_kreuzung_haelt_nicht_beim_abbiegen(self):
        """Sim-Fund: Haus 25 cm geradeaus hinter einem T. Biegt er ab, liegt es nicht auf seinem Weg -> faehrt.
        Faehrt er laut Plan geradeaus, haelt er davor."""
        self.lidar(0.25)
        for wunsch, faehrt in (('rechts', True), ('geradeaus', False)):
            self.n.gehirn.plan = Fahrplan([wunsch])
            self.n.gehirn.kreuzung = None
            self.n.regel.blockiert_bis = None
            self.n.gehirn.kreuzung_waehlen([math.radians(-90), 0.0], 0.0)
            self.n.sucher.wahl = math.radians(-90) if wunsch == 'rechts' else 0.0
            self.n.abzweig = (0.08, 0.0)                     # Abzweig 8 cm vor der Robotermitte
            lin, _, _, status = self.n.entscheide()
            self.assertEqual(lin > 0, faehrt, (wunsch, status))


class NeustartTest(unittest.TestCase):
    def test_prozess_neu_starten_behaelt_lernstand(self):
        """Echter Neustart: anderer Python-Prozess laedt dieselbe Datei -> Werte und Lernstand identisch."""
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, SMARTCITY_FAHRGEHIRN=os.path.join(d, 'fahrgehirn.json'),
                       SMARTCITY_FAHRGEHIRN_LOGS=os.path.join(d, 'logs'))
            prog = (
                'import sys, json\n'
                f'sys.path[:0] = [{str(ROOT / "tests" / "attrappen")!r}, {str(ROOT / "fahrgehirn")!r}]\n'
                'import fahrgehirn as fg\n'
                'n = fg.FahrGehirnKnoten()\n'
                'if sys.argv[1] == "lernen":\n'
                '    for w in (50, 50, 55, 56, 40, 61, 62):\n'
                '        n.lern.runde_fertig(w, "pendeln"); n.lern.speichern()\n'
                '    n.parameter_uebernehmen()\n'
                'werte = {k: n.p(k) for k in n.gehirn.parameter() if k != "kreuzung_tempo"}\n'
                'print(json.dumps({"stand": n.lern.stand, "aktiv": n.gehirn.parameter(), "knoten": werte}))\n')

            def lauf(art):
                out = subprocess.run([sys.executable, '-c', prog, art], env=env, capture_output=True, text=True,
                                     timeout=60, cwd=ROOT)
                self.assertEqual(out.returncode, 0, out.stderr)
                return json.loads(out.stdout.strip().splitlines()[-1])
            vorher = lauf('lernen')
            nachher = lauf('nur_laden')
            self.assertNotEqual(vorher['aktiv'], lernen.startwerte())    # es wurde wirklich etwas gelernt
            self.assertEqual(vorher['stand'], nachher['stand'])
            self.assertEqual(vorher['aktiv'], nachher['aktiv'])
            self.assertEqual(vorher['knoten'], nachher['knoten'])          # Knoten faehrt mit den geladenen Werten
            # auswerten.py (eigener Prozess) liest denselben Stand
            out = subprocess.run([sys.executable, 'fahrgehirn/auswerten.py', '--lernstand'], env=env, cwd=ROOT,
                                 capture_output=True, text=True, timeout=60)
            self.assertEqual(json.loads(out.stdout), nachher['stand'])


class RegelTest(unittest.TestCase):
    def test_regel(self):
        r = HindernisRegel()
        self.assertIsNone(r.pruefe(0.0, 1.0, False))
        self.assertIn('HINDERNIS', r.pruefe(1.0, 0.2, False))
        self.assertIn('TIEFENKAMERA', r.pruefe(1.1, 1.0, None))
        self.assertIn('Tiefenkamera', r.pruefe(1.2, 1.0, True))
        self.assertIn('LIDAR', r.pruefe(1.3, None, False))
        self.assertIsNotNone(r.pruefe(1.3 + r.frei_warten - 0.01, 1.0, False))
        self.assertIsNone(r.pruefe(1.3 + r.frei_warten + 0.01, 1.0, False))
        self.assertGreaterEqual(HindernisRegel(halt_abstand=0.0, frei_warten=0.0).halt_abstand, 0.2)

    def test_kreuzungs_pfad(self):
        pfad = kreuzungs_pfad((0.1, 0.0), math.radians(-90))     # rechts abbiegen, Abzweig 10 cm voraus
        drin, entlang = im_pfad_schlauch([(0.35, 0.0), (0.1, -0.15), (0.2, 0.0), (0.1, 0.25)], pfad, 0.15, 0.3)
        self.assertEqual(list(drin), [False, True, True, False])  # geradeaus hinter dem T: nicht im Weg
        self.assertAlmostEqual(entlang[1], 0.25, places=2)          # 10 cm bis zum Abzweig + 15 cm im Ast
        self.assertEqual(len(kreuzungs_pfad((-0.05, 0.0), 0.0)), 2)  # Abzweig schon hinter ihm


if __name__ == '__main__':
    unittest.main(verbosity=2)
