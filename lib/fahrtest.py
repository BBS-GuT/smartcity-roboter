"""Explicit supervised operation with partial coverage; never a free-space certificate."""
import math
import numpy as np


def tiefe_messung_gueltig(tiefe_m, modell, linie_voraus=None):
    """Require real depth across the visible corridor, including its near band.

    Project the expected floor footprint independently of measured depth, so
    missing pixels cannot remove themselves from the denominator. This is data
    health within the camera view, never a claim about the physical blind area.
    """
    from tiefenstatus import tiefe_messung_gueltig as pruefen
    return pruefen(tiefe_m, modell, linie_voraus)


def raeumfreigabe_gueltig(befehl, betrieb):
    """Auftragsfreigabe an genau die aktuelle bestaetigte Betriebsepoche binden.

    Empfangsalter des Befehls und echte Kollisionspruefung bleiben Aufgabe des
    finalen Publishers; dieses Praedikat ersetzt keine Sensorpruefung.
    """
    if not isinstance(befehl, dict) or not isinstance(betrieb, dict):
        return False
    r = befehl.get('raeumfreigabe') or {}
    if not isinstance(r, dict):
        return False
    return (r.get('zugelassen') is True and bool(r.get('auftrag_id')) and bool(r.get('phase'))
            and betrieb.get('betrieb_freigegeben') is True
            and all(r.get(k) is not None and r[k] == betrieb.get(k)
                    for k in ('session_id', 'generation', 'start_id')))


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
    r = befehl.get('raeumfreigabe') or {}
    if not isinstance(r, dict):
        r = {}
    special = bool(befehl.get('arm') or befehl.get('manoever'))
    if special:
        betrieb = w.get('betrieb') or {}
        kandidat = dict(befehl, raeumfreigabe=dict(r, zugelassen=True))
        ziel_id = w.get('raeumziel_id') or (w.get('objekt') or {}).get('ziel_id')
        bindung = w.get('raeum_planbindung') or {}
        plan_gebunden = (isinstance(bindung, dict) and w.get('blick') != 'fahr'
                        and str(r.get('phase', '')).startswith('ausfuehren:')
                        and all(r.get(k) is not None and r[k] == bindung.get(k)
                                for k in ('auftrag_id', 'ziel_id')))
        datenfehler = None if plan_gebunden else tiefe_halt(
            dict(w, tiefe_hindernis=False), jetzt, monoton, kamera_ok)
        if not raeumfreigabe_gueltig(kandidat, betrieb):
            reason = 'Raeumauftrag passt nicht zur aktuellen Betriebsfreigabe'
        elif datenfehler:
            reason = datenfehler
        elif not r.get('ziel_id') or r['ziel_id'] != ziel_id or w.get('raeumziel_freigegeben') is not True:
            reason = 'Raeumziel fehlt/alt/anderer Auftrag'
        elif w.get('lidar') is None:
            reason = 'Pflicht-LiDAR fehlt/ungueltig'
        elif w.get('raeum_umgebung_frei') is not True:
            reason = 'Anderes Objekt oder ungepruefte Raeumumgebung'
        elif w.get('chassis_frei') is not True:
            reason = 'Fahrgestellkollision oder ungepruefte Fahrzeughuelle'
        else:
            # Phasengerechte Ziel-/Posepruefung durch die Wahrnehmung. Nur das
            # gebundene Ziel darf der Arm beruehren; die Huellpruefung bleibt.
            reason = None
            befehl = kandidat
    if reason:
        result = dict(befehl, aktion='stopp', faktor=0.0, grund='BEGLEITETER FAHRBETRIEB: ' + reason,
                      arm=None, manoever=None)
    else:
        result = dict(befehl, grund='BEGLEITETER FAHRBETRIEB (Messabdeckung unbekannt): ' + befehl.get('grund', ''))
    if special:
        result['aktionsstatus'] = dict(r, status='verworfen' if reason else 'zugelassen', grund=reason or '')
        result['raeumfreigabe'] = dict(r, zugelassen=not bool(reason))
    return result
