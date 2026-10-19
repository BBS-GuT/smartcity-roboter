#!/usr/bin/env python3
# Schnelle Uebungswelt fuers Greifen (ohne ROS): tausende Greifversuche in wenigen Minuten.
#
# Was ist echt (wie im ROS-Simulator und auf dem Roboter)?
#   - Messung: Tiefenbild aus sim/welt.py, ausgewertet mit lib/tiefe.py (gleiche Rechnung wie die KI)
#   - Planung: lib/greifen.py plane() + lib/arm.py Kinematik (gleiche Rechnung wie ki/zentrale.py)
#   - Greifen gilt nach derselben Regel wie im Simulator (lib/greifen.py trifft())
# Was ist zufaellig ("Domain Randomization" = jeder Uebungsroboter ist etwas anders gebaut)?
#   - Armmasse (Schulter, Glieder, Hand), Servo-Nullpunkte, Durchhaengen des Arms, Spiel der Servos
#   - Kamera: Hoehe, Neigung, Lage, seitliche Drehung, Blickwinkel; Tiefenrauschen und Massstabsfehler
#   - Wuerfel: Groesse und Lage vor dem Roboter
# Der PLANER kennt davon nichts: er rechnet mit den Nennmassen (so wie die KI auf dem echten Roboter).
import math
import os
import sys

import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__))
for _d in (HIER, os.path.join(HIER, '..', 'lib'), os.path.join(HIER, '..', 'line_follower')):
    sys.path.insert(0, _d)
import welt as W        # noqa: E402
import arm as armlib    # noqa: E402
import greifen          # noqa: E402
from tiefe import Bodenmodell   # noqa: E402

KAMERA_NENN = {'kamera_hoehe': 0.22, 'kamera_neigung': 32.0, 'kamera_fov': 70.0, 'kamera_x': 0.12}  # roboter.yaml
FAHR = [90, 120, 10, 20, 90, 30]
AUF, ZU = 30, 130
# Nennmasse, mit denen der Planer rechnet: Simulator-Arm (sim/arm_sim.yaml) und M3-Pro-Modell (config/arm.yaml)
NENN = {
    'sim': {'schulter': [0.037, 0.0, 0.13], 'oberarm': 0.083, 'unterarm': 0.083, 'hand': 0.155, 'servo1_links': 1},
    'm3pro': {'schulter': [0.0336, 0.0, 0.218], 'oberarm': 0.0829, 'unterarm': 0.0828, 'hand': 0.150, 'servo1_links': 1},
}
POSE = (1.5, 1.1, 0.0)    # Roboter steht hier in der Uebungswelt (schaut nach +x)


def zufalls_roboter(rng, familie=None, staerke=1.0):
    """Ein zufaellig 'anders gebauter' Roboter: (Nennmasse fuer den Planer, echte Masse, echte Kamera, Rauschen)."""
    familie = familie or ('sim' if rng.random() < 0.5 else 'm3pro')
    nenn = dict(NENN[familie])
    s = staerke
    u = lambda a: float(rng.uniform(-a, a) * s)
    echt = dict(nenn)
    echt['schulter'] = [nenn['schulter'][0] + u(0.008), nenn['schulter'][1] + u(0.003), nenn['schulter'][2] + u(0.008)]
    echt['oberarm'] = nenn['oberarm'] + u(0.004)
    echt['unterarm'] = nenn['unterarm'] + u(0.004)
    echt['hand'] = nenn['hand'] + u(0.010)
    echt['nullpunkte'] = [u(2.5), u(2.5), u(2.5), u(2.5)]          # nach Yahbooms Kalibrierung, Rest-Fehler
    echt['durchhang'] = float(rng.uniform(0.0, 3.0) * s)            # Arm sackt immer nach UNTEN durch
    kamera = {'x': KAMERA_NENN['kamera_x'] + u(0.01), 'hoehe': KAMERA_NENN['kamera_hoehe'] + u(0.012),
              'neigung_deg': KAMERA_NENN['kamera_neigung'] + u(2.5), 'fov_deg': KAMERA_NENN['kamera_fov'] + u(2.0),
              'gier_deg': u(1.5)}
    rauschen = {'tiefe': float(rng.uniform(0.002, 0.006)), 'skala': 1.0 + u(0.015), 'spiel': float(rng.uniform(0.2, 0.8))}
    return {'familie': familie, 'nenn': nenn, 'echt': echt, 'kamera': kamera, 'rauschen': rauschen}


class Uebungswelt:
    """Ein Uebungsroboter vor einem Wuerfel. messen() wie die KI, greifen() rechnet nach, ob es klappt."""

    def __init__(self, roboter, rng):
        self.r, self.rng = roboter, rng
        self.welt = W.Welt(False, False, False)
        self.welt.zylinder = []
        k = roboter['kamera']
        W.KAMERA.update({'x': k['x'], 'hoehe': k['hoehe'], 'neigung_deg': k['neigung_deg'], 'fov_deg': k['fov_deg']})
        self.welt._cache = {}
        self.boden = Bodenmodell(KAMERA_NENN, {'weg_breite': 0.15})
        for _ in range(6):                      # Boden kennenlernen (wie auf dem Roboter, solange frei)
            self.boden.pruefe(self._tiefe(), lernen=True)
        self.planer_kin = armlib.Kinematik(roboter['nenn'])
        self.echt_kin = armlib.Kinematik(roboter['echt'])

    def _tiefe(self):
        _, d = self.welt.kamera(POSE, self.r['kamera']['gier_deg'], schritt=2)
        rs = self.r['rauschen']
        return (d * rs['skala'] + self.rng.normal(0, rs['tiefe'], d.shape)) * (d > 0)

    def neuer_wuerfel(self):
        """Wuerfel so, wie er nach 'in Greifweite fahren' liegt: Vorderkante ca. 25 cm voraus, bis 4,5 cm seitlich."""
        b = float(self.rng.uniform(0.03, 0.05))
        vorne = 0.25 + float(self.rng.uniform(-0.02, 0.02))
        self.wuerfel = {'x': vorne + b / 2, 'y': float(self.rng.uniform(-0.045, 0.045)), 'b': b}
        self.welt.zylinder = [{'x': POSE[0] + self.wuerfel['x'], 'y': POSE[1] + self.wuerfel['y'], 'r': b / 2,
                               'h': b, 'farbe': (60, 120, 180), 'name': 'wuerfel'}]
        return self.wuerfel

    def messen(self, bilder=3):
        """Wie Wegraeumen: mehrere Bilder, Median. None = nichts gesehen."""
        m = [o for o in (self.boden.pruefe(self._tiefe(), lernen=False)[1] for _ in range(bilder)) if o]
        if len(m) < 2:
            return None
        return {k: float(np.median([x[k] for x in m])) for k in ('vor', 'seite', 'breite', 'hoehe')}

    def greifen(self, obj, politik=None, erkunden=True):
        """Ein Greifversuch mit der echten Planungsrechnung. (erfolg, plan, Grund). erfolg None = nicht erreichbar."""
        plan = greifen.plane(obj, -1, self.planer_kin.inverse, FAHR, AUF, ZU, politik, self.rng, erkunden=erkunden)
        if plan.get('naeher'):
            # wie Wegraeumen: blind naeher heranfahren (Fahrfehler +-5 mm), dann mit verschobener Messung neu planen
            d = plan['naeher']
            self.wuerfel['x'] -= d + float(self.rng.uniform(-0.005, 0.005))
            obj = dict(obj, vor=obj['vor'] - d)
            plan = greifen.plane(obj, -1, self.planer_kin.inverse, FAHR, AUF, ZU, politik, self.rng, erkunden=erkunden)
        if plan.get('fehler'):
            return None, plan, plan['fehler']
        winkel = next(w for t, w, _ in plan['schritte'] if t == 'zugreifen')
        spiel = self.r['rauschen']['spiel']
        winkel = [v + float(self.rng.uniform(-spiel, spiel)) for v in winkel[:4]]
        g = self.echt_kin.vorwaerts(winkel)[0]
        w = self.wuerfel
        ok, grund = greifen.trifft(g, (w['x'], w['y']), w['b'], w['b'])
        return ok, plan, grund

    def ideale_korrektur(self, obj):
        """NUR im Simulator moeglich ("Lehrer, der alles weiss"): Welche Korrektur haette den Greifer genau in
        die Mitte des Wuerfels gebracht? Gerechnet mit den echten Massen. None = nicht erreichbar.
        Faehrt wie greifen() vorher naeher heran, wenn der Arm nicht hinreicht (veraendert dann den Wuerfel)."""
        plan = greifen.plane(obj, -1, self.planer_kin.inverse, FAHR, AUF, ZU)
        if plan.get('naeher'):
            d = plan['naeher']
            self.wuerfel['x'] -= d + float(self.rng.uniform(-0.005, 0.005))
            obj = dict(obj, vor=obj['vor'] - d)
        basis = greifen.greifpunkt(obj)
        w = self.wuerfel
        ziel = np.array([w['x'], w['y'], w['b'] / 2])
        a = np.zeros(3)
        for _ in range(5):
            winkel = self.planer_kin.inverse(*(basis + a))
            if winkel is None:
                return None, obj
            g = np.array(self.echt_kin.vorwaerts(winkel)[0])
            a = a + (ziel - g)
        return (a if np.all(np.abs(a) < 0.06) else None), obj
