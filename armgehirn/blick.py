#!/usr/bin/env python3
# Arm-Gehirn: Wohin muss die Kamera schauen? Umschauen ausrechnen und ueben - ohne fest eingespeicherte Blick-Posen.
#
# Die Kamera sitzt an der Hand. In der Fahrstellung sieht sie den Boden erst ab ca. 22-25 cm vor dem Roboter,
# der Arm des M3 Pro reicht (Nennmasse) aber nur bis ca. 20 cm. Ohne zu fahren muss der Arm die Kamera also
# so stellen, dass sie den Bereich sieht, in dem er greifen kann - und beim Pruefen zur Ablage drehen.
#
# 1. Blickstellungen AUSRECHNEN (blickstellungen): Servo 2-4 durchprobieren, mit der eigenen Kinematik
#    ausrechnen, wo die Kamera dann sitzt und wohin sie schaut (arm.kamera_fuer_pose), und behalten, was den
#    Greifbereich gut abdeckt. Dazu Servo 1 nach links/rechts gedreht (Umschauen zur Seite).
# 2. UEBEN (BlickLernen): Fuer jede Stellung zaehlt er mit, wie oft er dort einen Gegenstand gefunden hat
#    (Bayes mit Beta-Verteilung, Thompson-Sampling wie beim Greifen). Bei der naechsten Suche schaut er zuerst
#    dorthin, wo es sich bewaehrt hat. Gespeichert in config/lokal/armgehirn.json (nach jedem Versuch).
# 3. Ablageblick: aus der besten Stellung Servo 1 so drehen, dass die Kamera auf die Ablagestelle zeigt.
# Eine eingelernte Pose 'greifblick' (config/lokal/arm.yaml) wird zuerst probiert, ist aber nicht noetig.
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'))
import arm as armlib  # noqa: E402

DREHUNGEN = (0, 25, -25, 50, -50)   # Servo 1 gegenueber geradeaus (Grad): Umschauen zur Seite
BEREICH = (0.10, 0.25)              # hier soll die Kamera den Boden ganz sehen (m vor der Robotermitte)


def sichtbereich(kamera):
    """(nah, fern) in m vor der Robotermitte: diesen Bodenstreifen sieht die Kamera (Bild 4:3)."""
    halb = math.degrees(math.atan(math.tan(math.radians(kamera['kamera_fov'] / 2)) * 0.75))
    aus = []
    for winkel in (kamera['kamera_neigung'] + halb, kamera['kamera_neigung'] - halb):
        aus.append(float('inf') if winkel <= 1 else kamera['kamera_x'] + kamera['kamera_hoehe'] / math.tan(math.radians(winkel)))
    return tuple(aus)


def blickstellungen(kamera_fahr, fahr, geo=None, bereich=BEREICH, anzahl=3):
    """Ausgerechnete Blickstellungen (geradeaus, Servo 1 wie in der Fahrstellung): Liste von
    {'pose': [6 Winkel], 'kamera': Kameramasse, 'sicht': (nah, fern)}, beste zuerst. Gut = deckt den Bereich ab,
    Kamera nicht zu flach (genauer) und Servos nah an der Fahrstellung (kurzer, sicherer Weg)."""
    kandidaten = []
    for s2 in range(60, 181, 10):
        for s3 in range(0, 91, 10):
            for s4 in range(0, 91, 10):
                pose = [fahr[0], s2, s3, s4] + list(fahr[4:6])
                k = armlib.kamera_fuer_pose(kamera_fahr, fahr, pose, geo)
                if not k or k['kamera_hoehe'] < 0.12 or not 35 <= k['kamera_neigung'] <= 80:
                    continue
                nah, fern = sichtbereich(k)
                if nah > bereich[0] or fern < bereich[1]:
                    continue
                weg = abs(s2 - fahr[1]) + abs(s3 - fahr[2]) + abs(s4 - fahr[3])
                kandidaten.append((weg + abs(k['kamera_neigung'] - 55), pose, k, (nah, fern)))
    kandidaten.sort(key=lambda x: x[0])
    aus = []
    for _, pose, k, sicht in kandidaten:
        if all(max(abs(a - b) for a, b in zip(pose, x['pose'])) >= 20 for x in aus):   # verschiedene Stellungen
            aus.append({'pose': pose, 'kamera': k, 'sicht': sicht})
        if len(aus) >= anzahl:
            break
    return aus


def gedreht(pose, grad, links=1):
    """Pose mit Servo 1 um grad gedreht (+ = nach links), None wenn ausserhalb 0..180."""
    s1 = pose[0] + grad * links
    return None if not 0 <= s1 <= 180 else [int(round(s1))] + list(pose[1:])


def ins_roboter_system(objekt, grad, schulter_x):
    """Gegenstand, gemessen mit um grad gedrehter Kamera (Drehachse Servo 1 bei schulter_x), ins Roboter-System."""
    if objekt is None or not grad:
        return objekt
    a = math.radians(grad)
    d = objekt.get('laenge') or objekt['breite']        # Ausdehnung in Blickrichtung (wie pruefung.tiefe)
    x, y = objekt['vor'] + d / 2 - schulter_x, objekt['seite']
    xm, ym = schulter_x + x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
    return dict(objekt, vor=xm - d / 2, seite=ym)


def drehung_zu(punkt, schulter_x):
    """So weit (Grad, + = links) muss Servo 1 drehen, damit die Kamera auf punkt (x, y) zeigt."""
    return math.degrees(math.atan2(punkt[1], punkt[0] - schulter_x))


class BlickLernen:
    """Welche Blickstellung findet den Gegenstand? Je Stellung (Schluessel 'Servo2/3/4@Drehung') gefunden/gesucht.
    Vorwissen: geradeaus wahrscheinlicher als zur Seite (dort liegt er meist)."""

    def __init__(self, daten=None):
        self.zaehler = {k: list(v) for k, v in (daten or {}).items()}

    @staticmethod
    def schluessel(pose, grad):
        return f'{pose[1]}/{pose[2]}/{pose[3]}@{grad:+d}'

    def reihenfolge(self, stellungen, rng=None, erkunden=True):
        """stellungen: [(Schluessel, ...), ...] -> gleiche Liste, wahrscheinlich erfolgreiche zuerst."""
        rng = rng if rng is not None else np.random.default_rng()

        def wert(i, s):
            gef, ges = self.zaehler.get(s[0], [0, 0])
            a = 1.0 + gef + (2.0 if s[0].endswith('@+0') else 0.0) + 1.0 / (1 + i)   # Vorwissen
            b = 1.0 + ges - gef
            return rng.beta(a, b) if erkunden else a / (a + b)
        werte = [wert(i, s) for i, s in enumerate(stellungen)]
        return [stellungen[i] for i in np.argsort(werte)[::-1]]

    def ergebnis(self, schluessel, gefunden):
        z = self.zaehler.setdefault(schluessel, [0, 0])
        z[0] += bool(gefunden)
        z[1] += 1

    def als_dict(self):
        return {k: list(v) for k, v in self.zaehler.items()}
