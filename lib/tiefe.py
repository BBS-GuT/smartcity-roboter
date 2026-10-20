#!/usr/bin/env python3
# Tiefenkamera: Ragt etwas aus dem Boden vor dem Roboter? Wo genau, wie breit, wie hoch?
#
# Fuer jeden Bildpunkt wird mit dem Kameramodell (Hoehe, Neigung, Blickwinkel) ausgerechnet,
# wo er im Raum liegt: x vorne, y links, z = Hoehe ueber dem Boden. Boden = 0 cm.
# Was mehr als 'min_hoehe' herausragt und im Fahrweg liegt, ist ein Hindernis -
# auch Dinge UNTER der LiDAR-Ebene (z. B. ein kleiner Holzwuerfel).
# Fahrweg = Streifen entlang der Linie vor dem Roboter (wie beim LiDAR-Fahrschlauch), in Kurven also
# gebogen. Ohne bekannte Linie: gerade nach vorne.
#
# Kameradaten sind nie ganz genau. Darum lernt das Modell, solange der Weg frei ist, fuer jede
# Bildzeile, wie hoch der Boden "scheinbar" liegt, und zieht das spaeter ab.
# UNGETESTET mit der echten Kamera. Annahme: Tiefenbild ist auf das Farbbild ausgerichtet
# (gleicher Blickwinkel), Werte in Millimetern (16UC1) oder Metern (32FC1).
import math

import numpy as np

from lidar import abstand_zum_weg

STANDARD = {
    'min_hoehe': 0.02,       # hoeher als das ueber dem Boden = Hindernis (m)
    'weg_breite': 0.14,      # Fahrweg: +- so viel seitlich (m)
    'weg_laenge': 0.60,      # Fahrweg: bis so weit voraus (m)
    'min_punkte': 25,        # so viele Bildpunkte muessen herausragen (gegen Rauschen)
    'lern_bilder': 5,        # so viele freie Bilder, bis die Bodenkorrektur gilt
}


class Bodenmodell:
    def __init__(self, kamera, cfg=None, breite=160):
        """kamera: dict mit kamera_hoehe, kamera_neigung, kamera_fov, kamera_x (wie linie.STANDARD)."""
        self.k = kamera
        self.c = dict(STANDARD)
        self.c.update(cfg or {})
        self.breite = breite           # Tiefenbild wird auf diese Breite verkleinert (schneller)
        self.strahlen = None
        self.korrektur = None          # gelernte Bodenhoehe je Bildzeile
        self.gelernt = 0

    def _vorbereiten(self, h, w):
        if self.strahlen is not None and self.strahlen[0].shape == (h, w):
            return
        k = self.k
        f = (w / 2) / math.tan(math.radians(k['kamera_fov']) / 2)
        u, v = np.meshgrid(np.arange(w) - w / 2 + 0.5, np.arange(h) - h / 2 + 0.5)
        du, dv = u / f, v / f
        p = math.radians(k['kamera_neigung'])
        # Punkt = Kamera + Tiefe * (rx, ry, rz)
        self.strahlen = (math.cos(p) - dv * math.sin(p), -du, -math.sin(p) - dv * math.cos(p))
        self.korrektur = np.zeros(h)

    def punkte(self, tiefe_m):
        """Tiefenbild (m) -> x, y, z je Bildpunkt (verkleinert). 0 = keine Messung -> nan."""
        h0, w0 = tiefe_m.shape
        schritt = max(1, w0 // self.breite)
        t = tiefe_m[::schritt, ::schritt].astype(np.float32)
        t = np.where(t > 0.03, t, np.nan)
        self._t = t
        self._vorbereiten(*t.shape)
        rx, ry, rz = self.strahlen
        x = self.k['kamera_x'] + t * rx
        y = t * ry
        z = self.k['kamera_hoehe'] + t * rz
        return x, y, z

    def pruefe(self, tiefe_m, lernen, linie_voraus=None):
        """Rueckgabe: (hindernis True/False oder None = noch nicht bereit, objekt-dict oder None).
        objekt: vor (m, naechster Punkt), seite (m, Mitte), breite (m), hoehe (m), punkte (Anzahl),
                quer (m, Abstand zur Linie; nur mit linie_voraus).
        linie_voraus: Linie vor dem Roboter [(x, y), ...] (vom Linienfolger) -> Fahrweg folgt ihr."""
        x, y, z = self.punkte(tiefe_m)
        weg = (x > 0.05) & (x < self.c['weg_laenge']) & (np.abs(y) < self.c['weg_breite'])
        if lernen:
            # Bodenkorrektur je Zeile: Median der Hoehe der Bodenpunkte im Fahrweg (alle Zeilen auf einmal:
            # ungueltige Werte als inf ans Ende sortieren, dann die Mitte wie np.median)
            gut = weg & np.isfinite(z)
            n = gut.sum(axis=1)
            zeilen = np.nonzero(n > 5)[0]
            if len(zeilen):
                s = np.sort(np.where(gut[zeilen], z[zeilen], np.inf), axis=1)
                nn, i = n[zeilen], np.arange(len(zeilen))
                unten, oben = s[i, (nn - 1) // 2], s[i, nn // 2]
                med = np.where(nn % 2 == 1, oben, (unten + oben) / s.dtype.type(2))
                self.korrektur[zeilen] += 0.3 * (med - self.korrektur[zeilen])
            self.gelernt += 1
        if self.gelernt < self.c['lern_bilder']:
            return None, None
        hoch = (z - self.korrektur[:, None]) > self.c['min_hoehe']
        quer_karte = None
        if linie_voraus:
            # Fahrweg entlang der Linie: nur die herausragenden Punkte pruefen (wenige, schnell)
            kand = hoch & np.isfinite(z) & (x > 0.05) & (np.hypot(x, y) < self.c['weg_laenge'] + 0.1)
            weg = np.zeros_like(kand)
            quer_karte = np.full(kand.shape, np.nan)
            if kand.any():
                quer, entlang = abstand_zum_weg(np.column_stack([x[kand], y[kand]]), linie_voraus,
                                                self.c['weg_laenge'])
                weg[kand] = (quer < self.c['weg_breite']) & (entlang < self.c['weg_laenge'])
                quer_karte[kand] = quer
        treffer = weg & hoch & np.isfinite(z)
        n = int(treffer.sum())
        if n < self.c['min_punkte']:
            return False, None
        xs, ys, zs = x[treffer], y[treffer], z[treffer] - self.korrektur[np.nonzero(treffer)[0]]
        naechster = float(np.percentile(xs, 5))
        vorne = xs < naechster + 0.05          # nur die Vorderseite fuer Lage und Breite
        objekt = {'vor': naechster, 'seite': float(np.median(ys[vorne])),
                  'breite': float(np.percentile(ys[vorne], 95) - np.percentile(ys[vorne], 5)),
                  'hoehe': float(np.percentile(zs, 95)), 'punkte': n}
        # Mitte im Bild (Anteil 0..1 von Breite/Hoehe) und Tiefe dort: damit rechnet Yahbooms Kinematik
        # den Punkt mit dem echten Armmodell in Arm-Koordinaten um (lib/arm.py, YahboomKinematik)
        zeilen, spalten = np.nonzero(treffer)
        hz, wz = treffer.shape
        objekt['pixel'] = [float((np.median(spalten) + 0.5) / wz), float((np.median(zeilen) + 0.5) / hz)]
        objekt['tiefe_m'] = float(np.median(self._t[treffer]))
        if quer_karte is not None:   # wie weit neben der Linie (Mitte des Fahrwegs) liegt es?
            objekt['quer'] = float(np.median(quer_karte[treffer][vorne]))
        return True, objekt
