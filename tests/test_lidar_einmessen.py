#!/usr/bin/env python3
"""#66/#67: Einmesswerkzeug mit synthetischen Scans aus BEKANNTER Pose (keine Geraetewerte, kein ROS).

Die Scans entstehen per Strahlverfolgung gegen einen runden Raum und duenne Staebe. Geprueft wird, dass die
geschaetzte Pose im Produktvertrag (lib/lidar.py) dieselben Roboterkoordinaten ergibt, und dass mehrdeutige,
zu wenige, vertauschte oder gleich benannte Quellen keinen Vorschlag erzeugen.
Aufruf: python3 tests/test_lidar_einmessen.py
"""
import contextlib
import io
import json
import math
import os
import sys
import tempfile
import unittest

import numpy as np
import yaml

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, '..', 'scripts'))
sys.path.insert(0, os.path.join(HIER, '..', 'lib'))
import lidar  # noqa: E402
import lidar_einmessen as E  # noqa: E402

# Synthetische Posen (x, y, scan_front_deg) - bewusst KEINE RM01-Werte
POSEN = {'/scan0': ('laser_a', -0.12, 0.09, 0.0), '/scan1': ('laser_b', 0.11, -0.09, 90.0)}
ZIELE = [(0.60, 0.05), (0.35, 0.45), (-0.50, -0.30), (0.10, -0.55), (-0.30, 0.50)]
STAB = 0.02


def strahl(o, u, mitte, radius):
    """Kleinster positiver Abstand von o in Richtung u bis zum Kreis, sonst inf."""
    d = np.asarray(o) - np.asarray(mitte)
    b = float(d @ u)
    c = float(d @ d) - radius ** 2
    disk = b * b - c
    if disk < 0:
        return math.inf
    for r in (-b - math.sqrt(disk), -b + math.sqrt(disk)):
        if r > 1e-9:
            return r
    return math.inf


def scans(topic, staebe=(), anzahl=5, stamp=1000.0, alter=0.05, n=1440, rauschen=0.0, nachbearbeiten=None):
    frame, x, y, front = POSEN[topic]
    rng = np.random.default_rng(len(staebe) * 7 + n)
    ergebnis = []
    for k in range(anzahl):
        ranges = []
        for j in range(n):
            th = -math.pi + j * 2 * math.pi / n
            u = np.array([math.cos(th - math.radians(front)), math.sin(th - math.radians(front))])
            r = strahl((x, y), u, (0.0, 0.0), 2.5)            # Raumwand von innen
            for c in staebe:
                r = min(r, strahl((x, y), u, c, STAB / 2))
            ranges.append(float(r + rauschen * rng.standard_normal()))
        s = {'frame_id': frame, 'stamp': stamp + 0.1 * k, 'empfang_ros': stamp + 0.1 * k + alter,
             'angle_min': -math.pi, 'angle_increment': 2 * math.pi / n,
             'angle_max': -math.pi + (n - 1) * 2 * math.pi / n, 'range_min': 0.05, 'range_max': 12.0,
             'ranges': ranges}
        if nachbearbeiten:
            nachbearbeiten(s)
        ergebnis.append(s)
    return ergebnis


class Messordner:
    def __init__(self, test):
        self.tmp = tempfile.TemporaryDirectory()
        test.addCleanup(self.tmp.cleanup)
        self.ordner = self.tmp.name

    def aufnahme(self, name, staebe=(), topics=tuple(POSEN), **kw):
        with open(os.path.join(self.ordner, name + '.json'), 'w') as f:
            json.dump({'name': name, 'topics': {t: {'scans': scans(t, staebe, **kw)} for t in topics}}, f)
        return name + '.json'

    def messung(self, ziele=ZIELE, **extra):
        m = {'geraet': 'TEST', 'datum': '2000-01-01', 'pruefer': 'synthetisch', 'bezug': 'Testmitte',
             'hintergrund': self.aufnahme('hintergrund'), 'ziel_durchmesser': STAB, 'ziel_unsicherheit': 0.003,
             'ziele': [{'aufnahme': self.aufnahme(f'ziel{k}', [z]), 'x': z[0], 'y': z[1]}
                       for k, z in enumerate(ziele)]}
        m.update(extra)
        return m


class Einmessen(unittest.TestCase):
    def test_bekannte_pose_wird_gefunden_und_passt_zum_produktvertrag(self):
        o = Messordner(self)
        ergebnis, probleme = E.auswerten(o.messung(), o.ordner)
        self.assertEqual(probleme, [])
        self.assertEqual(list(ergebnis), ['/scan0', '/scan1'])
        for topic, (frame, x, y, front) in POSEN.items():
            e = ergebnis[topic]
            with self.subTest(topic):
                self.assertEqual(e['frame_id'], frame)
                self.assertAlmostEqual(e['x'], x, delta=0.003)
                self.assertAlmostEqual(e['y'], y, delta=0.003)
                self.assertAlmostEqual(e['front_deg'], front, delta=0.3)
                self.assertLess(e['rms_m'], 0.003)
                self.assertIsNotNone(e['jackknife'])
                # Mit der geschaetzten Pose rechnet lib/lidar.py jeden Stab an seine echte Stelle
                einbau = lidar.Einbau(frame, e['x'], e['y'], 'gemessen')
                for z in ZIELE:
                    u = np.array([z[0] - x, z[1] - y])
                    r = np.linalg.norm(u)
                    w = math.atan2(u[1], u[0]) + math.radians(front)
                    p = lidar.sensor_zu_basis([[r * math.cos(w), r * math.sin(w)]], e['front_deg'], einbau)
                    self.assertLess(np.linalg.norm(p[0] - z), 0.006)
        text = E.vorschlag(ergebnis, o.messung())
        cfg = yaml.safe_load(text)['/**']['ros__parameters']
        self.assertEqual(cfg['scan_frames'], ['laser_a', 'laser_b'])
        self.assertEqual(cfg['scan_einbau_quelle'], ['gemessen', 'gemessen'])
        self.assertNotIn('fahrzeug_grenzen', cfg)        # Huelle wird separat gemessen
        einbau, grund = lidar.einbau_aus_parametern(cfg['scan_topics'], cfg['scan_frames'],
                                                    cfg['scan_einbau_xy'], cfg['scan_einbau_quelle'])
        self.assertIsNone(grund)

    def test_rauschen_erhoeht_unsicherheit_statt_sie_zu_verstecken(self):
        o = Messordner(self)
        m = o.messung()
        ruhig = E.auswerten(m, o.ordner)[0]['/scan0']
        with open(os.path.join(o.ordner, m['ziele'][0]['aufnahme']), 'w') as f:  # ein Ziel 3 cm falsch notiert
            json.dump({'topics': {t: {'scans': scans(t, [(ZIELE[0][0] + .03, ZIELE[0][1])])} for t in POSEN}}, f)
        unruhig, probleme = E.auswerten(m, o.ordner)
        self.assertEqual(probleme, [])
        self.assertGreater(unruhig['/scan0']['rms_m'], 0.005)
        self.assertGreater(unruhig['/scan0']['U_x_m'], ruhig['U_x_m'])
        self.assertGreater(unruhig['/scan0']['jackknife']['front_deg'], ruhig['jackknife']['front_deg'])

    def test_massband_abgleich_erkennt_vertauschte_topics(self):
        o = Messordner(self)
        richtig = {t: {'x': p[1], 'y': p[2], 'unsicherheit': 0.01} for t, p in POSEN.items()}
        ergebnis, probleme = E.auswerten(o.messung(sensoren=richtig), o.ordner)
        self.assertEqual(probleme, [])
        self.assertTrue(all(e['massband_passt'] for e in ergebnis.values()))
        vertauscht = {'/scan0': richtig['/scan1'], '/scan1': richtig['/scan0']}
        ergebnis, probleme = E.auswerten(o.messung(sensoren=vertauscht), o.ordner)
        self.assertEqual(len(probleme), 2)
        self.assertIn('vertauscht', probleme[0])

    def test_mehrdeutiges_ziel_ergibt_keine_zahl(self):
        o = Messordner(self)
        m = o.messung(ziele=ZIELE[:2])
        m['ziele'][1]['aufnahme'] = o.aufnahme('person_im_bild', [ZIELE[1], (0.9, -0.9)])
        ergebnis, probleme = E.auswerten(m, o.ordner)
        self.assertTrue(any('mehrdeutig' in n for n in ergebnis['/scan0']['notizen']))
        self.assertTrue(any('mindestens 2 Ziele' in p for p in probleme))
        self.assertIsNone(E.vorschlag(ergebnis, m))

    def test_zu_dichte_ziele_bestimmen_keine_drehung(self):
        with self.assertRaises(ValueError):
            E.pose_schaetzen([(0.5, 0.0), (0.5, 0.05)], [(0.6, 0.0), (0.6, 0.05)])

    def test_gemeinsamer_frame_wird_gemeldet(self):
        o = Messordner(self)
        alt = dict(POSEN)
        POSEN['/scan1'] = ('laser_a',) + POSEN['/scan1'][1:]
        self.addCleanup(POSEN.update, alt)
        _, probleme = E.auswerten(o.messung(), o.ordner)
        self.assertTrue(any('denselben Frame' in p for p in probleme))

    def test_kommandozeile_ohne_ros(self):
        o = Messordner(self)
        datei = os.path.join(o.ordner, 'messung.yaml')
        with open(datei, 'w') as f:
            yaml.safe_dump(o.messung(), f)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(E.main(['auswerten', datei]), 0)
        self.assertIn('scan_einbau_xy', out.getvalue())
        with open(datei, 'w') as f:
            yaml.safe_dump(o.messung(ziele=ZIELE[:1]), f)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(E.main(['auswerten', datei]), 1)
        self.assertIn('PROBLEME', out.getvalue())
        self.assertNotIn('scan_einbau_xy', out.getvalue())

    def test_werkzeug_sendet_nichts(self):
        with open(E.__file__) as f:
            quelle = f.read()
        for verboten in ('create_publisher', 'cmd_vel', 'Twist', 'set_parameters'):
            self.assertNotIn(verboten, quelle)


class Standcheck(unittest.TestCase):
    def test_sauberer_kanal_ohne_hinweise(self):
        b = E.standcheck(scans('/scan0'))
        self.assertEqual(b['hinweise'], [])
        self.assertEqual(b['frame_id'], 'laser_a')
        self.assertEqual(b['anteil_ungueltig'], 0.0)

    def test_offene_fragen_aus_58_werden_sichtbar(self):
        def stoeren(s):
            r = s['ranges']
            for j in range(100, 160):
                r[j] = 0.0                       # verdeckter Sektor
            r[400], r[401] = 12.0, math.inf      # genau range_max, inf
            for j in range(700, 705):
                r[j] = 0.08                      # eigener Aufbau sehr nah
        b = E.standcheck(scans('/scan0', nachbearbeiten=stoeren))
        text = ' '.join(b['hinweise'])
        self.assertEqual(len(b['ungueltige_sektoren_grad']), 2)
        self.assertGreater(b['genau_range_max'], 0)
        self.assertGreater(b['inf'], 0)
        self.assertEqual(len(b['nahe_treffer_sektoren_grad']), 1)
        for teil in ('range_max', 'inf', 'ohne Messung', 'eigene Teile'):
            self.assertIn(teil, text)

    def test_zeitstempel_zukunft_alt_und_rueckwaerts(self):
        self.assertIn('Zukunft', ' '.join(E.standcheck(scans('/scan0', alter=-0.2))['hinweise']))
        self.assertIn('alt', ' '.join(E.standcheck(scans('/scan0', alter=1.5))['hinweise']))

        def rueckwaerts(s):
            s['stamp'] = 5.0
        self.assertIn('rueckwaerts', ' '.join(E.standcheck(scans('/scan0', nachbearbeiten=rueckwaerts))['hinweise']))

    def test_wechselnde_geometrie_wird_abgelehnt(self):
        a = scans('/scan0', anzahl=2)
        a[1]['frame_id'] = 'anders'
        with self.assertRaises(ValueError):
            E.standcheck(a)


if __name__ == '__main__':
    unittest.main()
