#!/usr/bin/env python3
# Verkehrszeichen-Erkennung ohne KI (Farbe + Form). Ohne ROS, wie ampel.py.
#
# Stoppschild = rotes ACHTECK. Rote Flaeche suchen, Umriss vereinfachen,
# 7-9 Ecken + ungefaehr quadratisch + gross genug -> Stoppschild.
# Weitere Schilder (z. B. Vorfahrt = Dreieck, Gebotsschilder = blaue Kreise)
# koennen nach demselben Muster ergaenzt werden, sobald klar ist, welche
# Schilder in der SmartCity stehen.
import math

import cv2
import numpy as np

STANDARD = {
    'sign_top': 0.0,         # Suchbereich oben (Anteil Bildhoehe)
    'sign_bottom': 0.8,      # Suchbereich unten
    'sign_sat_min': 90,      # Rot-Saettigung (Schild ist nicht leuchtend, nur kraeftig)
    'sign_val_min': 60,      # Rot-Mindesthelligkeit
    'sign_min_area': 600,    # kleinere Flaechen ignorieren (Pixel) = Schild noch zu weit weg
    'sign_min_corners': 7,   # Achteck: 7..9 Ecken erlauben (Kamera sieht es nie perfekt)
    'sign_max_corners': 9,
    'sign_max_aspect': 1.4,  # Breite/Hoehe
    'sign_min_solidity': 0.85,  # Flaeche / konvexe Huelle (Achteck ist "voll")
    'sign_max_round': 0.94,  # Flaeche / umschliessender Kreis: Achteck ~0.90, Kreis ~0.97
}


def finde_stoppschild(img, cfg):
    """Rueckgabe: dict mit bereich, maske, treffer (x, y, b, h) oder None, kandidaten."""
    c = dict(STANDARD)
    c.update(cfg)
    h, w = img.shape[:2]
    y0, y1 = int(h * c['sign_top']), int(h * c['sign_bottom'])
    erg = {'bereich': (0, y0, w, y1), 'maske': None, 'treffer': None, 'kandidaten': []}
    part = img[y0:y1]
    if part.size == 0:
        return erg
    hsv = cv2.cvtColor(part, cv2.COLOR_BGR2HSV)
    s, v = int(c['sign_sat_min']), int(c['sign_val_min'])
    maske = cv2.inRange(hsv, (0, s, v), (10, 255, 255)) | cv2.inRange(hsv, (170, s, v), (180, 255, 255))
    # Weisse Schrift "STOP" schliessen, damit das Schild eine Flaeche bleibt
    maske = cv2.morphologyEx(maske, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    erg['maske'] = maske
    contours, _ = cv2.findContours(maske, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bester = 0
    for cnt in contours:
        flaeche = cv2.contourArea(cnt)
        if flaeche < c['sign_min_area']:
            continue
        x, y, bw, bh = cv2.boundingRect(cnt)
        ecken = len(cv2.approxPolyDP(cnt, 0.03 * cv2.arcLength(cnt, True), True))
        huelle = cv2.contourArea(cv2.convexHull(cnt))
        grund = ''
        if not c['sign_min_corners'] <= ecken <= c['sign_max_corners']:
            grund = f'{ecken} Ecken'
        elif max(bw, bh) / max(1, min(bw, bh)) > c['sign_max_aspect']:
            grund = 'nicht quadratisch'
        elif huelle and flaeche / huelle < c['sign_min_solidity']:
            grund = 'nicht voll'
        elif flaeche / (math.pi * cv2.minEnclosingCircle(cnt)[1] ** 2) > c['sign_max_round']:
            grund = 'Kreis'
        erg['kandidaten'].append((x, y0 + y, bw, bh, grund))
        if not grund and flaeche > bester:
            bester = flaeche
            erg['treffer'] = (x, y0 + y, bw, bh)
    return erg


def finde_einfahrt_verboten(img, cfg=None):
    """Schild "Verbot der Einfahrt" (Einbahnstrasse von der falschen Seite):
    roter KREIS mit weissem waagrechtem Balken in der Mitte.
    Rueckgabe: (x, y, b, h) oder None."""
    c = dict(STANDARD)
    c.update(cfg or {})
    h, w = img.shape[:2]
    y0, y1 = int(h * c['sign_top']), int(h * c['sign_bottom'])
    part = img[y0:y1]
    if part.size == 0:
        return None
    hsv = cv2.cvtColor(part, cv2.COLOR_BGR2HSV)
    s, v = int(c['sign_sat_min']), int(c['sign_val_min'])
    rot = cv2.inRange(hsv, (0, s, v), (10, 255, 255)) | cv2.inRange(hsv, (170, s, v), (180, 255, 255))
    rot = cv2.morphologyEx(rot, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    weiss = cv2.inRange(hsv, (0, 0, 170), (180, 70, 255))
    contours, _ = cv2.findContours(rot, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bester = None
    for cnt in contours:
        flaeche = cv2.contourArea(cnt)
        if flaeche < c['sign_min_area'] * 0.6:
            continue
        (cx, cy), r = cv2.minEnclosingCircle(cnt)
        if flaeche / (math.pi * r * r) < c['sign_max_round']:
            continue                                   # nicht rund genug (z. B. Achteck = Stoppschild)
        kreis = np.zeros(rot.shape, np.uint8)
        cv2.circle(kreis, (int(cx), int(cy)), int(r * 0.85), 255, -1)
        innen = cv2.bitwise_and(weiss, kreis)
        pts = cv2.findNonZero(innen)
        if pts is None:
            continue
        bx, by, bw, bh = cv2.boundingRect(pts)
        gefuellt = cv2.countNonZero(innen) / max(1, bw * bh)
        mittig = abs(by + bh / 2 - cy) < 0.2 * r
        if bw >= 1.0 * r and bw / max(1, bh) >= 2.5 and gefuellt >= 0.6 and mittig:
            x, y, ww, hh = cv2.boundingRect(cnt)
            if bester is None or ww * hh > bester[2] * bester[3]:
                bester = (x, y0 + y, ww, hh)
    return bester


def zeichne(view, erg):
    for x, y, bw, bh, grund in erg['kandidaten']:
        if grund:
            cv2.rectangle(view, (x, y), (x + bw, y + bh), (0, 165, 255), 1)
            cv2.putText(view, grund, (x, y + bh + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 165, 255), 1)
    if erg['treffer'] is not None:
        x, y, bw, bh = erg['treffer']
        cv2.rectangle(view, (x, y), (x + bw, y + bh), (255, 255, 255), 3)
        cv2.putText(view, 'STOPPSCHILD', (x, max(12, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
