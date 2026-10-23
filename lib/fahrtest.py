"""Explicit supervised operation with partial coverage; never a free-space certificate."""
import math


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
