"""Explicit, supervised short forward test; never a free-space certificate."""
import math

MAX_TEMPO = .05  # configured vehicle envelope, m/s including rotational corner speed
MAX_DAUER = 6.0


def parameter_aenderung(params):
    from rcl_interfaces.msg import SetParametersResult
    changed = any(p.name == 'begleiteter_fahrtest' for p in params)
    return SetParametersResult(successful=not changed,
                               reason='Testmoduswechsel erfordert gestoppte Prozesse und Neustart' if changed else '')


def tiefe_halt(w, jetzt, monoton, kamera_ok):
    """The test needs current, valid, aligned depth; no learned-away obstacles."""
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
        reason = reason or 'Arm-/KI-Manoever im begleiteten Fahrtest gesperrt'
    if reason:
        return dict(befehl, aktion='stopp', faktor=0.0, grund='BEGLEITETER FAHRTEST: ' + reason,
                    arm=None, manoever=None)
    return dict(befehl, grund='BEGLEITETER FAHRTEST (Messabdeckung unbekannt): ' + befehl.get('grund', ''))


class Kurzfahrt:
    """One bounded attempt. A hold after motion latches until a NEW process/START."""
    def __init__(self):
        self.beginn = None
        self.beendet = False

    def begrenze(self, lin, quer, dreh, status, hull, jetzt, drive):
        prefix = 'BEGLEITETER FAHRTEST: '
        if self.beendet:
            return 0.0, 0.0, 0.0, prefix + 'beendet -> STOPP; neuer Versuch erst nach STOPP/START'
        values = (lin, quer, dreh, jetzt, *hull)
        if (len(hull) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values)
                or min(hull) <= 0):
            self.beendet = True
            return 0.0, 0.0, 0.0, prefix + 'Befehl/Fahrzeuggrenzen ungueltig -> STOPP'
        moving = bool(lin or quer or dreh)
        if self.beginn is not None and (not 0 <= jetzt-self.beginn < MAX_DAUER or not moving):
            self.beendet = True
            return 0.0, 0.0, 0.0, prefix + status + ' / Versuch beendet -> STOPP'
        if lin < 0 or abs(quer) > 1e-9 or (lin == 0 and dreh != 0):
            self.beendet = True
            return 0.0, 0.0, 0.0, prefix + 'nur Linienfahrt vorwaerts -> STOPP'
        if moving and drive and self.beginn is None:
            self.beginn = jetzt
        radius = math.hypot(max(hull[:2]), max(hull[2:]))
        envelope_speed = math.hypot(lin, quer) + abs(dreh)*radius
        scale = min(1.0, MAX_TEMPO/envelope_speed) if envelope_speed else 1.0
        return lin*scale, quer*scale, dreh*scale, prefix + status
