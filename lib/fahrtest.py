"""Explicit supervised operation with partial coverage; never a free-space certificate."""
import math
import numpy as np


def tiefe_messung_gueltig(tiefe_m, modell):
    """Require real depth across the visible corridor, including its near band.

    Project the expected floor footprint independently of measured depth, so
    missing pixels cannot remove themselves from the denominator. This is data
    health within the camera view, never a claim about the physical blind area.
    """
    if tiefe_m is None or tiefe_m.ndim != 2:
        return False
    modell.punkte(tiefe_m)
    rx, ry, rz = modell.strahlen
    with np.errstate(divide='ignore', invalid='ignore'):
        floor_depth = -modell.k['kamera_hoehe'] / rz
        x = modell.k['kamera_x'] + floor_depth * rx
        y = floor_depth * ry
    corridor = (floor_depth > .03) & (x > .05) & (x < modell.c['weg_laenge']) & (np.abs(y) < modell.c['weg_breite'])
    valid = np.isfinite(modell._t) & (modell._t > .03)
    if corridor.sum() < 25 or valid[corridor].mean() < .7:
        return False
    # A large missing near/side region must not hide behind a valid far floor.
    for lo, hi in ((.05, .25), (.25, .4), (.4, modell.c['weg_laenge'])):
        for left in (False, True):
            part = corridor & (x >= lo) & (x < hi) & ((y >= 0) if left else (y < 0))
            if part.sum() >= 10 and valid[part].mean() < .7:
                return False
    return True


def scan_uhrspielraum(node):
    # RM01's continuously arriving MCU scans were measured about 30 ms ahead.
    # Keep the raw stamps and all age/progress guards; never accept a large clock jump.
    return .1 if node.p('begleiteter_fahrbetrieb') else 0.0


def parameter_aenderung(params):
    from rcl_interfaces.msg import SetParametersResult
    changed = any(p.name == 'begleiteter_fahrbetrieb' for p in params)
    return SetParametersResult(successful=not changed,
                               reason='Betriebsartwechsel erfordert gestoppte Prozesse und Neustart' if changed else '')


def tiefe_halt(w, jetzt, monoton, kamera_ok):
    """Partial coverage needs current, valid, aligned depth; no learned-away obstacles."""
    if not kamera_ok or w.get('blick') != 'fahr':
        return 'Kamera nicht in gepruefter Fahrstellung'
    if w.get('lidar') is None:
        return 'Pflicht-LiDAR fehlt/ungueltig'
    if w.get('tiefe_gueltig') is not True or w.get('tiefe_hindernis') is None:
        return 'Tiefenmessung fehlt/ungueltig'
    for value, now in ((w.get('tiefe_aufnahme'), jetzt), (w.get('tiefe_empfang'), monoton)):
        if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= now - value <= .5:
            return 'Tiefenmessung fehlt/alt/andere Uhr'
    rgb = w.get('aufnahme')
    if not isinstance(rgb, (int, float)) or not math.isfinite(rgb) or abs(rgb-w['tiefe_aufnahme']) > .15:
        return 'Farb-/Tiefenbild passen zeitlich nicht zusammen'
    if w['tiefe_hindernis']:
        return 'HINDERNIS von Tiefenkamera'
    return None


def befehl_sichern(befehl, w, jetzt, monoton, kamera_ok):
    reason = tiefe_halt(w, jetzt, monoton, kamera_ok)
    if befehl.get('arm') or befehl.get('manoever'):
        reason = reason or 'Arm-/KI-Manoever im begleiteten Fahrbetrieb gesperrt'
    if reason:
        return dict(befehl, aktion='stopp', faktor=0.0, grund='BEGLEITETER FAHRBETRIEB: ' + reason,
                    arm=None, manoever=None)
    return dict(befehl, grund='BEGLEITETER FAHRBETRIEB (Messabdeckung unbekannt): ' + befehl.get('grund', ''))
