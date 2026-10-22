#!/usr/bin/env python3
# Antrieb wie in echt (ohne ROS, damit testbar): Der echte Roboter faehrt NICHT sofort so,
# wie befohlen. Fuer Simulator (sim/simulator.py) und Messung (sim/linie_messen.py).
#
#   totzeit     Befehl kommt erst so viele s spaeter bei den Motoren an (USB, Board, Regler)
#   traegheit   Motoren brauchen Zeit, bis sie das neue Tempo haben (Tiefpass, Zeitkonstante in s:
#               nach dieser Zeit sind ca. 63 % der Aenderung erreicht)
#   max_beschl  schneller (m/s^2) kann er nicht beschleunigen/bremsen, max_dreh_beschl genauso fuers Drehen
#   schlupf     Mecanum-Raeder rutschen in Kurven nach aussen (Fliehkraft = Tempo x Drehrate).
#               Rutschtempo seitlich = schlupf x Fliehkraft. Die Radzaehler merken davon NICHTS.
#   dreh_skala  Mecanum-Raeder drehen den Roboter weniger als befohlen (Rollen rutschen), 0.95 = 5 % weniger
#
# Profile: 'ideal' = Befehl ist sofort die Geschwindigkeit (wie frueher), 'echt' = GESCHAETZTE Werte
# fuer den ROSMASTER M3 Pro (nicht am Roboter gemessen!), 'schwer' = deutlich traeger.
import math
from collections import deque

PROFILE = {
    'ideal': {'totzeit': 0.0, 'traegheit': 0.0, 'max_beschl': 0.0, 'max_dreh_beschl': 0.0,
              'schlupf': 0.0, 'dreh_skala': 1.0},
    'echt': {'totzeit': 0.05, 'traegheit': 0.15, 'max_beschl': 0.8, 'max_dreh_beschl': 5.0,
             'schlupf': 0.04, 'dreh_skala': 0.95},
    'schwer': {'totzeit': 0.08, 'traegheit': 0.25, 'max_beschl': 0.5, 'max_dreh_beschl': 3.0,
               'schlupf': 0.07, 'dreh_skala': 0.9},
}


class Antrieb:
    def __init__(self, profil='ideal', **aenderungen):
        self.werte = dict(PROFILE[profil])
        self.werte.update({k: v for k, v in aenderungen.items() if v is not None})
        self.befehle = deque()                 # (Zeit, (vor, quer, dreh)) noch unterwegs zu den Motoren
        self.soll = (0.0, 0.0, 0.0)            # was bei den Motoren angekommen ist
        self.rad = [0.0, 0.0, 0.0]             # wie schnell die Raeder drehen (vor, quer, dreh) = was die Radzaehler messen
        self.wahr = (0.0, 0.0, 0.0)            # wie sich der Roboter wirklich bewegt (mit Schlupf)

    def befehl(self, vor, quer, dreh, jetzt):
        self.befehle.append((jetzt, (vor, quer, dreh)))

    def schritt(self, dt, jetzt):
        """Einen Zeitschritt rechnen. Rueckgabe: wahre Bewegung (vor m/s, seitwaerts m/s, drehen rad/s)."""
        w = self.werte
        while self.befehle and self.befehle[0][0] <= jetzt - w['totzeit']:
            self.soll = self.befehle.popleft()[1]
        anteil = 1.0 if w['traegheit'] <= 0 else 1.0 - math.exp(-dt / w['traegheit'])
        grenzen = (w['max_beschl'], w['max_beschl'], w['max_dreh_beschl'])
        for i in range(3):
            aenderung = (self.soll[i] - self.rad[i]) * anteil
            if grenzen[i] > 0:
                aenderung = max(-grenzen[i] * dt, min(grenzen[i] * dt, aenderung))
            self.rad[i] += aenderung
        vor, quer, dreh = self.rad
        dreh *= w['dreh_skala']
        quer -= w['schlupf'] * vor * dreh      # Linkskurve (dreh > 0) -> rutscht nach rechts (aussen)
        self.wahr = (vor, quer, dreh)
        return self.wahr

    def stopp(self):
        """Watchdog des Boards: kein Befehl mehr -> Motoren aus (bremsen trotzdem nicht sofort)."""
        self.befehle.clear()
        self.soll = (0.0, 0.0, 0.0)
