#!/usr/bin/env python3
# Uebungswelt fuer das Arm-Gehirn (ohne ROS): ein zufaellig "anders gebauter" Roboter (sim/greifen_welt.py,
# Domain Randomization) steht still, vor ihm liegt ein Wuerfel - oder eine Spielfigur, die er NIE anfassen darf.
# Echt gerechnet wie auf dem Roboter: Tiefenbilder (sim/welt.py), Auswertung (lib/tiefe.py), Umschauen, Planung,
# Sicherheitsregel, Pruefung und Lernen (armgehirn/). Nur die Welt ist ausgedacht:
#   - Kamera sitzt an der Hand: wohin sie schaut, folgt aus den ECHTEN (dem Planer unbekannten) Armmassen
#   - Greifer zu: gefasst nach lib/greifen.trifft (echte Kinematik + Servo-Spiel); knapp daneben schiebt eine
#     Backe den Wuerfel weg, weiter daneben bleibt er liegen; gefasst faellt er selten unterwegs heraus
#   - Kamera-KI: erkennt die Figur als "Person", aber nicht in jedem Bild (wie das echte Modell)
import math
import os
import sys

import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__))
for _d in (HIER, os.path.join(HIER, '..', 'lib'), os.path.join(HIER, '..', 'armgehirn')):
    sys.path.insert(0, _d)
import welt as W            # noqa: E402
import arm as armlib        # noqa: E402
import greifen              # noqa: E402
import greifen_welt as GW   # noqa: E402

BEREICH_X, BEREICH_Y = (0.15, 0.20), (-0.05, 0.05)   # hier legt der "Mensch" die Mitte des Gegenstands hin (m)
KI_TREFFER = 0.8      # so oft erkennt die Kamera-KI die Figur in einem Bild als Person
FALLEN = 0.03         # so oft faellt ein gefasster Wuerfel unterwegs heraus
KNAPP = 0.012         # so weit ausserhalb des Spielraums trifft noch eine Backe den Wuerfel (m)


class SimWelt:
    """Welt + Arm + Kamera eines Uebungsroboters. Adapter fuer armgehirn/gehirn.py: quelle (bild) und arm."""

    def __init__(self, roboter, rng):
        self.r, self.rng = roboter, rng
        self.welt = W.Welt(False, False, False)
        self.welt.zylinder = []
        self.planer_kin = armlib.Kinematik(roboter['nenn'])
        self.echt_kin = armlib.Kinematik(roboter['echt'])
        k = roboter['kamera']
        self.kamera_echt = {'kamera_x': k['x'], 'kamera_hoehe': k['hoehe'], 'kamera_neigung': k['neigung_deg'],
                            'kamera_fov': k['fov_deg']}
        self.winkel = list(GW.FAHR)
        self.gegenstand = None          # {'art': 'wuerfel'|'figur', 'x', 'y', 'b', 'h'}
        self.gehalten = False
        self.letzter_zielfehler = None
        self.zeit = 0.0

    # ---------------------------------------------------------------- Welt
    def lege(self, art='wuerfel', x=None, y=None):
        """Mensch legt einen Gegenstand hin (Mitte x, y; zufaellig im Bereich)."""
        x = float(self.rng.uniform(*BEREICH_X)) if x is None else x
        y = float(self.rng.uniform(*BEREICH_Y)) if y is None else y
        if art == 'figur':
            self.gegenstand = {'art': art, 'x': x, 'y': y, 'b': 0.03, 'h': 0.08}
        else:
            b = float(self.rng.uniform(0.03, 0.05))
            self.gegenstand = {'art': art, 'x': x, 'y': y, 'b': b, 'h': b}
        self.gehalten = False
        self.letzter_zielfehler = None
        return self.gegenstand

    def raeumen(self):
        self.gegenstand, self.gehalten = None, False

    def _zylinder(self):
        g = self.gegenstand
        if g is None or self.gehalten:
            return []
        farbe = (60, 120, 180) if g['art'] == 'wuerfel' else (200, 60, 200)
        return [{'x': GW.POSE[0] + g['x'], 'y': GW.POSE[1] + g['y'], 'r': g['b'] / 2, 'h': g['h'], 'farbe': farbe,
                 'name': g['art']}]

    # ---------------------------------------------------------------- Kamera (quelle fuer armgehirn/augen.py)
    def bild(self):
        """(Tiefenbild m, Kamera-KI-Funde) fuer die aktuelle Armstellung (Kamera an der Hand, echte Masse)."""
        w = self.winkel
        basis = [GW.FAHR[0]] + list(w[1:4]) + list(GW.FAHR[4:])
        k = armlib.kamera_fuer_pose(self.kamera_echt, GW.FAHR, basis, self.r['echt'])
        if k is None:
            return None, []
        n1 = (self.r['echt'].get('nullpunkte') or [0])[0]
        dreh = (w[0] + n1 - 90) * self.r['echt'].get('servo1_links', 1) + self.r['kamera']['gier_deg']
        W.KAMERA.update({'x': k['kamera_x'], 'hoehe': k['kamera_hoehe'], 'neigung_deg': k['kamera_neigung'],
                         'fov_deg': k['kamera_fov'], 'arm_basis_x': self.r['echt']['schulter'][0]})
        self.welt._cache = {}
        self.welt.zylinder = self._zylinder()
        _, d = self.welt.kamera(GW.POSE, dreh, schritt=2)
        rs = self.r['rauschen']
        tiefe = (d * rs['skala'] + self.rng.normal(0, rs['tiefe'], d.shape)) * (d > 0)
        ki = []
        g = self.gegenstand
        if g and g['art'] == 'figur' and not self.gehalten and self.rng.random() < KI_TREFFER:
            ki.append({'name': 'Person', 'sicher': round(float(self.rng.uniform(0.3, 0.8)), 2), 'box': (0, 0, 10, 10)})
        return tiefe, ki

    # ---------------------------------------------------------------- Arm (arm fuer armgehirn/gehirn.py)
    def fahre(self, winkel, zeit_ms=1500):
        fehler = armlib.pruefe([int(round(v)) for v in winkel], zeit_ms)
        if fehler:
            return fehler
        alt, self.winkel = self.winkel, [int(round(v)) for v in winkel]
        auf = GW.AUF
        zu_vorher, zu_jetzt = alt[5] > auf + 5, self.winkel[5] > auf + 5
        spiel = self.r['rauschen']['spiel']
        echt = [v + float(self.rng.uniform(-spiel, spiel)) for v in self.winkel[:4]]
        greifer = np.array(self.echt_kin.vorwaerts(echt)[0])
        g = self.gegenstand
        if g is not None and not zu_vorher and zu_jetzt and not self.gehalten:
            self._zugreifen(greifer)
        elif self.gehalten and zu_vorher and not zu_jetzt:
            g.update(x=float(greifer[0]), y=float(greifer[1]))       # losgelassen: liegt, wo der Greifer ist
            self.gehalten = False
        elif self.gehalten and self.rng.random() < FALLEN / 4:     # unterwegs heraus gefallen
            g.update(x=float(greifer[0]), y=float(greifer[1]))
            self.gehalten = False
        return None

    def _zugreifen(self, greifer):
        g = self.gegenstand
        ok, _ = greifen.trifft(greifer, (g['x'], g['y']), g['b'], g['h'])
        daneben = math.hypot(greifer[0] - g['x'], greifer[1] - g['y'])
        self.letzter_zielfehler = daneben
        if ok and g['art'] == 'wuerfel':
            self.gehalten = True
            return
        erlaubt = max(0.005, (greifen.OEFFNUNG - g['b']) / 2)
        if erlaubt <= daneben < erlaubt + KNAPP and greifer[2] < g['h']:
            # eine Backe trifft ihn: er wird zur Greifermitte hin geschoben (1-2,5 cm)
            s = float(self.rng.uniform(0.01, 0.025))
            g['x'] += s * (greifer[0] - g['x']) / max(daneben, 1e-6)
            g['y'] += s * (greifer[1] - g['y']) / max(daneben, 1e-6)

    def warte(self, s):
        self.zeit += s

    def greifer(self):
        return None        # wie der M3 Pro: meldet die Servo-Stellung nicht


def kamera_nenn():
    """Kameramasse in der Fahrstellung, wie sie der Planer kennt (config/roboter.yaml)."""
    return dict(GW.KAMERA_NENN)
