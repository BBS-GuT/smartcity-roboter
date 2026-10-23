"""Depth health and a small, spatially bounded clearing target."""
import math

import numpy as np

from lidar import abstand_zum_weg


def strahlen(kamera, shape):
    h, w = shape
    f = (w / 2) / math.tan(math.radians(kamera['kamera_fov']) / 2)
    u, v = np.meshgrid(np.arange(w) - w / 2 + .5, np.arange(h) - h / 2 + .5)
    p = math.radians(kamera['kamera_neigung'])
    return math.cos(p) - v / f * math.sin(p), -u / f, -math.sin(p) - v / f * math.cos(p)


def wegmaske(x, y, cfg, linie_voraus=None):
    """Same curved footprint for measured obstacles and expected floor pixels."""
    finite = np.isfinite(x) & np.isfinite(y) & (x > .05)
    mask = np.zeros(x.shape, dtype=bool)
    quer = np.full(x.shape, np.nan)
    entlang = np.full(x.shape, np.nan)
    if finite.any():
        q, e = abstand_zum_weg(np.column_stack((x[finite], y[finite])), linie_voraus, cfg['weg_laenge'])
        quer[finite], entlang[finite] = q, e
        mask[finite] = (q < cfg['weg_breite']) & (e < cfg['weg_laenge'])
    return mask, quer, entlang


def tiefe_messung_gueltig(tiefe_m, modell, linie_voraus=None):
    """Pure check; missing measurements cannot remove their own denominator."""
    if tiefe_m is None or tiefe_m.ndim != 2 or not tiefe_m.size:
        return False
    step = max(1, tiefe_m.shape[1] // modell.breite)
    t = tiefe_m[::step, ::step]
    rx, ry, rz = strahlen(modell.k, t.shape)
    with np.errstate(divide='ignore', invalid='ignore'):
        depth = -modell.k['kamera_hoehe'] / rz
        x, y = modell.k['kamera_x'] + depth * rx, depth * ry
    corridor, _, along = wegmaske(x, y, modell.c, linie_voraus)
    corridor &= np.isfinite(depth) & (depth > .03)
    valid = np.isfinite(t) & (t > .03)
    if corridor.sum() < 25 or valid[corridor].mean() < .7:
        return False
    for lo, hi in ((.05, .25), (.25, .4), (.4, modell.c['weg_laenge'])):
        for left in (False, True):
            part = corridor & (along >= lo) & (along < hi) & ((y >= 0) if left else (y < 0))
            if part.sum() >= 10 and valid[part].mean() < .7:
                return False
    return True


class Zielbestaetigung:
    """Three distinct fresh measurements of one local region; no object tracking system."""
    def __init__(self):
        self.reset()
        self.zaehler = 0

    def reset(self):
        self.objekt = None
        self.anzahl = 0
        self.messung = None
        self.zeit = None

    def update(self, objekte, messung, zeit, pose):
        if messung == self.messung:
            return None if self.objekt is None else dict(self.objekt)
        old = self.objekt
        if not objekte or (self.zeit is not None and not 0 < zeit - self.zeit <= .5):
            self.reset()
            old = None
        self.messung, self.zeit = messung, zeit
        if not objekte:
            return None
        candidate = min(objekte, key=lambda o: o['vor'])
        same = old is not None and old.get('blick') == pose and all(
            abs(candidate[k] - old[k]) <= .025 for k in ('vor', 'seite', 'breite', 'hoehe'))
        if same:
            self.anzahl += 1
        else:
            self.zaehler += 1
            self.anzahl = 1
        self.objekt = dict(candidate, ziel_id=(old['ziel_id'] if same else f'tiefe-{self.zaehler}'),
                           blick=pose, messzeit=zeit, bestaetigt=self.anzahl >= 3,
                           messungen=self.anzahl)
        return dict(self.objekt)
