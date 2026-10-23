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


def pflichtdaten_bereit(w, jetzt, monoton, kamera_ok):
    """Current startup data readiness; an observed obstacle is not a data fault."""
    if (not kamera_ok or w.get('blick') != 'fahr' or w.get('lidar') is None
            or w.get('tiefe_gueltig') is not True or w.get('tiefe_hindernis') is None):
        return False
    rgb, depth, receive = w.get('aufnahme'), w.get('tiefe_aufnahme'), w.get('tiefe_empfang')
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in (rgb, depth, receive)):
        return False
    return (0 <= jetzt-rgb <= .5 and 0 <= jetzt-depth <= .5
            and 0 <= monoton-receive <= .5 and abs(rgb-depth) <= .15)


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


def raeum_pruefung(w, hull, monoton, cfg=None, jetzt=None):
    """Exclude only the confirmed object's exact measured rectangle from other hits."""
    obj = w.get('objekt') or {}
    result = dict(raeumziel_id=obj.get('ziel_id'), raeumziel_freigegeben=False,
                  raeum_umgebung_frei=False, chassis_frei=False)
    region = obj.get('region') or {}
    if not (obj.get('bestaetigt') is True and w.get('tiefe_gueltig') is True
            and 0 <= monoton - obj.get('messzeit', -math.inf) <= .5
            and len(hull) == 4 and all(math.isfinite(v) and v > 0 for v in hull)
            and 'min' in region and 'max' in region):
        return result
    if jetzt is not None:
        rgb, depth, receive = w.get('aufnahme'), w.get('tiefe_aufnahme'), w.get('tiefe_empfang')
        if (any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in (rgb, depth, receive))
                or not 0 <= jetzt-rgb <= .5 or not 0 <= jetzt-depth <= .5
                or not 0 <= monoton-receive <= .5 or abs(rgb-depth) > .15):
            return result
    result['raeumziel_freigegeben'] = True
    low, high = np.asarray(region['min']), np.asarray(region['max'])
    xy = w.get('lidar_xy')
    if xy is None or w.get('lidar') is None:
        return result
    xy = np.asarray(xy).reshape(-1, 2)
    front, back, left, right = hull
    inside = ((xy[:, 0] <= front) & (xy[:, 0] >= -back)
              & (xy[:, 1] <= left) & (xy[:, 1] >= -right))
    target_inside = low[0] <= front and high[0] >= -back and low[1] <= left and high[1] >= -right
    result['chassis_frei'] = not target_inside and not inside.any()
    in_target = ((xy >= low[:2]) & (xy <= high[:2])).all(axis=1)
    # Check the entire visible depth corridor, retaining every other component;
    # no broad target cone and no general obstacle suppression.
    corridor, _, _ = wegmaske(xy[:, 0], xy[:, 1], cfg or
                              {'weg_breite': max(left, right), 'weg_laenge': .6}, w.get('weg'))
    other_front = (~in_target) & (xy[:, 0] > front) & corridor
    result['raeum_umgebung_frei'] = len(w.get('tiefe_objekte') or []) == 1 and not other_front.any()
    return result


def fahrraum_frei(w, hull, cfg):
    """Post-grasp check: no selected-object exclusion remains."""
    if (len(hull) != 4 or not all(math.isfinite(v) and v > 0 for v in hull)
            or w.get('lidar') is None or w.get('lidar_xy') is None):
        return False, False
    xy = np.asarray(w['lidar_xy']).reshape(-1, 2)
    front, back, left, right = hull
    inside = ((xy[:, 0] <= front) & (xy[:, 0] >= -back)
              & (xy[:, 1] <= left) & (xy[:, 1] >= -right))
    corridor, _, _ = wegmaske(xy[:, 0], xy[:, 1], cfg, w.get('weg'))
    return not inside.any(), not bool(w.get('tiefe_objekte')) and not (corridor & (xy[:, 0] > front)).any()


def ablage_frei(xy, ablage, radius, abgelegte_region=None):
    """Only an expected deposited target's measured footprint may be excluded."""
    if xy is None or ablage is None or len(ablage) != 3:
        return False
    points = np.asarray(xy).reshape(-1, 2)
    occupied = np.hypot(points[:, 0]-ablage[0], points[:, 1]-ablage[1]) < radius
    if abgelegte_region:
        low, high = np.asarray(abgelegte_region['min'][:2]), np.asarray(abgelegte_region['max'][:2])
        half = (high-low) / 2
        if np.isfinite(half).all() and (half > 0).all():
            expected = (np.abs(points-np.asarray(ablage[:2])) <= half).all(axis=1)
            occupied &= ~expected
    return not occupied.any()
