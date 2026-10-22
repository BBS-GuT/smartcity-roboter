#!/usr/bin/env python3
# Arm-Gehirn: Augen = Tiefenkamera + Kamera-KI, je Blickstellung ausgewertet (ohne ROS).
#
# Die Tiefenkamera sieht nur, was aus dem Boden ragt. Dazu muss sie den Boden in JEDER Blickstellung einmal leer
# gesehen haben (lib/tiefe.py lernt je Bildzeile, wie hoch der Boden scheinbar liegt). Darum: einrichten() bei
# leerem Bereich. Der gelernte Boden wird gespeichert (config/lokal/armgehirn.json) und nach einem Neustart geladen.
# quelle.bild() liefert ein frisches Bild NACH dem Aufruf: (Tiefenbild in m, Kamera-KI-Funde).
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'))
from tiefe import Bodenmodell  # noqa: E402

TIEFE_CFG = {'weg_breite': 0.15, 'weg_laenge': 0.45, 'min_punkte': 15}


class Augen:
    def __init__(self, quelle, boden=None, cfg=None):
        self.quelle = quelle
        self.cfg = dict(TIEFE_CFG)
        self.cfg.update(cfg or {})
        self.modelle = {}
        self.gespeichert = dict(boden or {})       # Schluessel -> Bodenkorrektur je Bildzeile

    def _modell(self, schluessel, kamera):
        m = self.modelle.get(schluessel)
        if m is None or m.k != kamera:
            m = Bodenmodell(kamera, self.cfg)
            self.modelle[schluessel] = m
        return m

    def boden_lernen(self, schluessel, kamera, bilder=8):
        m = self._modell(schluessel, kamera)
        m.strahlen, m.gelernt = None, 0           # Boden neu lernen
        for _ in range(max(bilder, m.c['lern_bilder'])):
            tiefe, _ = self.quelle.bild()
            m.pruefe(tiefe, lernen=True)
        self.gespeichert[schluessel] = [round(float(v), 5) for v in m.korrektur]

    def kann(self, schluessel):
        return schluessel in self.gespeichert or (schluessel in self.modelle and self.modelle[schluessel].gelernt > 0)

    def messen(self, schluessel, kamera, bilder=6):
        """Bilder [{'objekt': Gegenstand (Kamera-System dieser Blickstellung) oder None, 'objekte': Kamera-KI}].
        Boden hier noch nie gelernt: keine Tiefe (objekt immer None) - nie 'frei' daraus schliessen."""
        m = self._modell(schluessel, kamera)
        aus = []
        for _ in range(bilder):
            tiefe, objekte = self.quelle.bild()
            obj = None
            if self.kann(schluessel) and tiefe is not None:
                if m.gelernt == 0:                       # nach Neustart: gespeicherten Boden einsetzen
                    m.punkte(tiefe)
                    alt = np.array(self.gespeichert[schluessel], dtype=float)
                    if len(alt) != len(m.korrektur):
                        aus.append({'objekt': None, 'objekte': list(objekte or [])})
                        continue                         # andere Bildgroesse: Boden passt nicht (neu einrichten)
                    m.korrektur, m.gelernt = alt, m.c['lern_bilder']
                _, obj = m.pruefe(tiefe, lernen=False)
            aus.append({'objekt': obj, 'objekte': list(objekte or [])})
        return aus

    def als_dict(self):
        return dict(self.gespeichert)
