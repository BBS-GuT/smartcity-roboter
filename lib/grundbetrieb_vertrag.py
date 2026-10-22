# Gemeinsamer Zustandsvertrag des Grundbetriebs (C1, Issue #14), Version 1.0.
#
# EIN Zustandsdatensatz pro Roboter, aus dem spaeter Panel UND MQTT lesen (Zieldefinition GB-15, Abschnitt 7).
# Dieses Modul ist ROS-unabhaengig und braucht nur die Python-Standardbibliothek:
#   pruefe(d)          -> Liste von Fehlertexten (leer = gueltig): Struktur + fachliche Regeln
#   als_json(d)        -> strenges JSON (wirft bei Fehlern, nie NaN/Unendlich)
#   lade_json(text)    -> dict, wirft bei NaN/Unendlich oder ungueltigem Datensatz
#   Start              -> Startkennung + Sequenz eines Programmlaufs
#   vergleiche(a, b)   -> wie zwei Datensaetze zueinander stehen (Geraet/Start/Sequenz)
#   alter_s(d, jetzt)  -> Datenalter nach monotoner Uhr desselben Starts
# Feldbeschreibung: docs/schnittstellen-grundbetrieb.md. JSON-Schema (nur Struktur, fuer externe Leser):
# schemas/grundbetrieb-v1.schema.json. Die fachlichen Regeln (R1-R11) prueft nur pruefe().
# Alle Beispiele sind synthetisch (tests/fixtures/grundbetrieb/), keine Messwerte eines Geraets.
import json
import math
import re
import uuid

SCHEMA_VERSION = '1.0'
GERAETE = ('RM01', 'RM02', 'RM03', 'RM04')
# Gueltigkeit einer Quelle/eines Messwerts. Frei/belegt ist KEIN Status, sondern ein eigener Wert (corridor).
STATUS = ('valid', 'unknown', 'invalid', 'stale', 'missing')
ZUSTAENDE = ('GESTOPPT', 'TEST', 'BEREIT', 'SPURFOLGEN', 'KREUZUNG_ANNAEHERN', 'VERKEHRSHALT', 'MANOEVER',
             'AUSFAHRT_BESTAETIGEN', 'FEHLER')
FAHR_ZUSTAENDE = ('SPURFOLGEN', 'KREUZUNG_ANNAEHERN', 'MANOEVER', 'AUSFAHRT_BESTAETIGEN')
HALTEGRUENDE = ('STOP_LATCHED', 'FAULT', 'TEST_MODE', 'NO_REQUEST', 'RED_LIGHT', 'YELLOW_LIGHT', 'SIGNAL_UNKNOWN',
                'STOP_SIGN', 'CROSSING_OCCUPIED', 'FRONT_BLOCKED', 'DISTANCE_LOCK', 'SENSOR_MISSING',
                'SENSOR_STALE', 'SENSOR_INVALID', 'LINE_LOST', 'LOCALIZATION_UNKNOWN', 'MANEUVER_FAILED')
SIGNALE = ('red', 'yellow', 'green', 'off', 'unknown')
BELEGUNG = ('free', 'occupied', 'unknown')
BROKER = ('connected', 'disconnected', 'unknown', 'disabled')
ZEITSYNC = ('synced', 'unsynced', 'unknown')
_ZEIT_UTC = re.compile(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d{1,9})?Z$')


# ------------------------------------------------------------------ Start und Sequenz
class Start:
    """Ein Programmlauf: eigene Startkennung, Sequenz beginnt bei 0. Nach einem Neustart neue Kennung -
    so wird ein Neustart nie als Fortsetzung alter Daten gelesen."""

    def __init__(self, robot_id, boot_id=None):
        if robot_id not in GERAETE:
            raise ValueError(f'unbekanntes Geraet {robot_id!r}')
        self.robot_id = robot_id
        self.boot_id = boot_id or uuid.uuid4().hex
        self.seq = -1

    def naechste(self):
        self.seq += 1
        return self.seq


def vergleiche(a, b):
    """Wie steht Datensatz b zu a? 'anderes_geraet' | 'anderer_start' (nicht vergleichbar, keine Fortsetzung) |
    'neuer' | 'gleich' | 'aelter' (z. B. Duplikat/verspaetete Nachricht bei MQTT QoS 1)."""
    if a['robot_id'] != b['robot_id']:
        return 'anderes_geraet'
    if a['boot_id'] != b['boot_id']:
        return 'anderer_start'
    if b['seq'] > a['seq']:
        return 'neuer'
    return 'gleich' if b['seq'] == a['seq'] else 'aelter'


def alter_s(d, jetzt_mono_s):
    """Alter des Datensatzes in s nach der monotonen Uhr DESSELBEN Starts (lokal, z. B. im Panel)."""
    return max(0.0, jetzt_mono_s - d['generated_mono_s'])


def prfe_fahrhistorie(history_daten):
    """Prueft den begrenzten Fahrhistorien-Puffer auf hoechstens 16 lueckenlose Sequenzeintraege (C1I, #153)."""
    if not isinstance(history_daten, dict) or 'entries' not in history_daten:
        return False
    entries = history_daten['entries']
    if not isinstance(entries, list) or len(entries) > 16:
        return False
    letzte_seq = None
    for eintrag in entries:
        if not isinstance(eintrag, dict):
            return False
        seq = eintrag.get('seq')
        if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
            return False
        if letzte_seq is not None and seq != letzte_seq + 1:
            return False
        letzte_seq = seq
    return True


# ------------------------------------------------------------------ JSON
def _kein_nan(wert):
    raise ValueError(f'nicht erlaubter JSON-Wert {wert}')


def als_json(d):
    """Strenges JSON. Wirft ValueError, wenn der Datensatz ungueltig ist oder NaN/Unendlich enthaelt."""
    fehler = pruefe(d)
    if fehler:
        raise ValueError('ungueltiger Zustandsdatensatz: ' + '; '.join(fehler))
    return json.dumps(d, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def lade_json(text):
    """JSON lesen und pruefen. Wirft ValueError bei NaN/Infinity oder ungueltigem Datensatz."""
    d = json.loads(text, parse_constant=_kein_nan)
    fehler = pruefe(d)
    if fehler:
        raise ValueError('ungueltiger Zustandsdatensatz: ' + '; '.join(fehler))
    return d


# ------------------------------------------------------------------ Pruefen
class _Pruefer:
    def __init__(self):
        self.fehler = []

    def f(self, pfad, text):
        self.fehler.append(f'{pfad}: {text}')

    def obj(self, d, pfad, felder):
        """d muss ein dict mit genau diesen Feldern sein. Rueckgabe: True, wenn es ein dict ist."""
        if not isinstance(d, dict):
            self.f(pfad, 'muss ein Objekt sein')
            return False
        for k in felder:
            if k not in d:
                self.f(f'{pfad}.{k}', 'fehlt')
        for k in d:
            if k not in felder:
                self.f(f'{pfad}.{k}', 'unbekanntes Feld')
        return True

    def zahl(self, d, pfad, k, null=False, mini=None, maxi=None, ganz=False):
        if k not in d:
            return
        v = d[k]
        if v is None:
            if not null:
                self.f(f'{pfad}.{k}', 'darf nicht null sein')
            return
        if isinstance(v, bool) or not isinstance(v, (int, float)) or (ganz and not isinstance(v, int)):
            self.f(f'{pfad}.{k}', 'muss eine ' + ('ganze Zahl' if ganz else 'Zahl') + ' sein')
            return
        if isinstance(v, float) and not math.isfinite(v):
            self.f(f'{pfad}.{k}', 'NaN/Unendlich nicht erlaubt (null + Status verwenden)')
            return
        if mini is not None and v < mini:
            self.f(f'{pfad}.{k}', f'kleiner als {mini}')
        if maxi is not None and v > maxi:
            self.f(f'{pfad}.{k}', f'groesser als {maxi}')

    def text(self, d, pfad, k, null=False, auswahl=None, muster=None):
        if k not in d:
            return
        v = d[k]
        if v is None:
            if not null:
                self.f(f'{pfad}.{k}', 'darf nicht null sein')
            return
        if not isinstance(v, str) or not v:
            self.f(f'{pfad}.{k}', 'muss ein nicht leerer Text sein')
        elif auswahl is not None and v not in auswahl:
            self.f(f'{pfad}.{k}', f'{v!r} nicht erlaubt (erlaubt: {", ".join(auswahl)})')
        elif muster is not None and not muster.match(v):
            self.f(f'{pfad}.{k}', f'{v!r} hat das falsche Format')

    def janein(self, d, pfad, k, null=False):
        if k in d and not (isinstance(d[k], bool) or (null and d[k] is None)):
            self.f(f'{pfad}.{k}', 'muss true/false sein' + (' oder null' if null else ''))

    def liste(self, d, pfad, k, auswahl=None):
        """Liste eindeutiger Texte."""
        if k not in d:
            return []
        v = d[k]
        if not isinstance(v, list) or not all(isinstance(x, str) and x for x in v):
            self.f(f'{pfad}.{k}', 'muss eine Liste von Texten sein')
            return []
        if len(set(v)) != len(v):
            self.f(f'{pfad}.{k}', 'doppelte Eintraege')
        for x in v:
            if auswahl is not None and x not in auswahl:
                self.f(f'{pfad}.{k}', f'{x!r} nicht erlaubt')
        return v

    def messwert(self, d, pfad, k, mini=None, maxi=None):
        """{value, status, source}: valid <=> value vorhanden. Unbekannt wird nie zur gueltigen Null (R2)."""
        if k not in d:
            return
        m, p = d[k], f'{pfad}.{k}'
        if not self.obj(m, p, ('value', 'status', 'source')):
            return
        self.zahl(m, p, 'value', null=True, mini=mini, maxi=maxi)
        self.text(m, p, 'status', auswahl=STATUS)
        self.text(m, p, 'source', null=True)
        if m.get('status') == 'valid' and m.get('value') is None:
            self.f(p, 'status valid braucht einen Wert (R2)')
        if m.get('status') in STATUS and m.get('status') != 'valid' and m.get('value') is not None:
            self.f(p, f"status {m['status']} darf keinen Wert tragen - nicht verfuegbar ist null, nicht 0 (R2)")


FELDER = ('schema_version', 'robot_id', 'boot_id', 'seq', 'generated_at', 'generated_mono_s', 'time_sync',
          'software_version', 'map_version', 'config_version', 'runtime', 'motion', 'lane', 'route', 'traffic',
          'obstacles', 'sensors', 'diagnostics', 'communication', 'details')


def pruefe(d):
    """Alle Fehler des Datensatzes (leer = gueltig). Struktur wie im JSON-Schema plus fachliche Regeln R1-R11
    (siehe docs/schnittstellen-grundbetrieb.md)."""
    p = _Pruefer()
    if not p.obj(d, '$', FELDER):
        return p.fehler
    if d.get('schema_version') != SCHEMA_VERSION:
        p.f('$.schema_version', f'muss {SCHEMA_VERSION!r} sein')
    p.text(d, '$', 'robot_id', auswahl=GERAETE)
    p.text(d, '$', 'boot_id')
    if isinstance(d.get('boot_id'), str) and len(d['boot_id']) < 8:
        p.f('$.boot_id', 'zu kurz (mind. 8 Zeichen, eindeutig pro Start)')
    p.zahl(d, '$', 'seq', mini=0, ganz=True)
    p.text(d, '$', 'generated_at', muster=_ZEIT_UTC)
    p.zahl(d, '$', 'generated_mono_s', mini=0)
    for k in ('software_version', 'map_version', 'config_version'):
        p.text(d, '$', k, null=True)
    if p.obj(d.get('time_sync'), '$.time_sync', ('status', 'source')):
        p.text(d['time_sync'], '$.time_sync', 'status', auswahl=ZEITSYNC)
        p.text(d['time_sync'], '$.time_sync', 'source', null=True)

    rt = d.get('runtime')
    if p.obj(rt, '$.runtime', ('mode', 'state', 'motor_enabled', 'stop_latched', 'fault_latched', 'hold_reasons',
                               'faults')):
        if rt.get('mode') != 'GRUNDBETRIEB':
            p.f('$.runtime.mode', "muss 'GRUNDBETRIEB' sein (andere Modi sind nicht Teil von v1)")
        p.text(rt, '$.runtime', 'state', auswahl=ZUSTAENDE)
        for k in ('motor_enabled', 'stop_latched', 'fault_latched'):
            p.janein(rt, '$.runtime', k)
        p.liste(rt, '$.runtime', 'hold_reasons', auswahl=HALTEGRUENDE)
        p.liste(rt, '$.runtime', 'faults')
    else:
        rt = {}

    mo = d.get('motion')
    out = {}
    if p.obj(mo, '$.motion', ('request', 'output', 'measured_v_m_s', 'measured_w_rad_s', 'odometry_distance_m',
                              'heading_rad')):
        rq = mo.get('request')
        if rq is not None and p.obj(rq, '$.motion.request', ('request_id', 'valid_until_mono_s', 'v_m_s', 'w_rad_s',
                                                             'maneuver', 'hold_reasons')):
            p.text(rq, '$.motion.request', 'request_id')
            p.zahl(rq, '$.motion.request', 'valid_until_mono_s', mini=0)
            p.zahl(rq, '$.motion.request', 'v_m_s', mini=-1, maxi=1)
            p.zahl(rq, '$.motion.request', 'w_rad_s', mini=-10, maxi=10)
            p.text(rq, '$.motion.request', 'maneuver', null=True)
            p.liste(rq, '$.motion.request', 'hold_reasons', auswahl=HALTEGRUENDE)
        if p.obj(mo.get('output'), '$.motion.output', ('v_m_s', 'w_rad_s')):
            out = mo['output']
            p.zahl(out, '$.motion.output', 'v_m_s', mini=-1, maxi=1)
            p.zahl(out, '$.motion.output', 'w_rad_s', mini=-10, maxi=10)
        p.messwert(mo, '$.motion', 'measured_v_m_s', -1, 1)
        p.messwert(mo, '$.motion', 'measured_w_rad_s', -10, 10)
        p.messwert(mo, '$.motion', 'odometry_distance_m', 0)
        p.messwert(mo, '$.motion', 'heading_rad', -math.pi, math.pi)

    la = d.get('lane')
    if p.obj(la, '$.lane', ('status', 'offset_m', 'heading_error_rad')):
        p.text(la, '$.lane', 'status', auswahl=STATUS)
        p.zahl(la, '$.lane', 'offset_m', null=True, mini=-1, maxi=1)
        p.zahl(la, '$.lane', 'heading_error_rad', null=True, mini=-math.pi, maxi=math.pi)
        _wert_passt_zu_status(p, la, '$.lane', ('offset_m', 'heading_error_rad'))

    ro = d.get('route')
    if p.obj(ro, '$.route', ('section', 'node', 'approach_from', 'direction', 'allowed_exits', 'selected_exit',
                             'maneuver', 'maneuver_progress', 'localization_status', 'localization_quality')):
        for k in ('section', 'node', 'approach_from', 'direction', 'selected_exit', 'maneuver'):
            p.text(ro, '$.route', k, null=True)
        ausgaenge = p.liste(ro, '$.route', 'allowed_exits')
        if ro.get('selected_exit') is not None and ro.get('selected_exit') not in ausgaenge:
            p.f('$.route.selected_exit', 'ist nicht unter allowed_exits (R9)')
        p.zahl(ro, '$.route', 'maneuver_progress', null=True, mini=0, maxi=1)
        p.text(ro, '$.route', 'localization_status', auswahl=STATUS)
        p.zahl(ro, '$.route', 'localization_quality', null=True, mini=0, maxi=1)

    tr = d.get('traffic')
    if p.obj(tr, '$.traffic', ('signal_id', 'signal', 'signal_status', 'signal_confidence', 'signs', 'crossings')):
        p.text(tr, '$.traffic', 'signal_id', null=True)
        p.text(tr, '$.traffic', 'signal', auswahl=SIGNALE)
        p.text(tr, '$.traffic', 'signal_status', auswahl=STATUS)
        p.zahl(tr, '$.traffic', 'signal_confidence', null=True, mini=0, maxi=1)
        if tr.get('signal_status') == 'valid' and tr.get('signal') == 'unknown':
            p.f('$.traffic', "signal_status valid mit signal 'unknown' widerspricht sich (R11)")
        for i, s in enumerate(tr.get('signs') if isinstance(tr.get('signs'), list) else []):
            if p.obj(s, f'$.traffic.signs[{i}]', ('type', 'status', 'confidence')):
                p.text(s, f'$.traffic.signs[{i}]', 'type')
                p.text(s, f'$.traffic.signs[{i}]', 'status', auswahl=STATUS)
                p.zahl(s, f'$.traffic.signs[{i}]', 'confidence', null=True, mini=0, maxi=1)
        for i, c in enumerate(tr.get('crossings') if isinstance(tr.get('crossings'), list) else []):
            if p.obj(c, f'$.traffic.crossings[{i}]', ('id', 'occupancy', 'status')):
                p.text(c, f'$.traffic.crossings[{i}]', 'id', null=True)
                p.text(c, f'$.traffic.crossings[{i}]', 'occupancy', auswahl=BELEGUNG)
                p.text(c, f'$.traffic.crossings[{i}]', 'status', auswahl=STATUS)
        for k in ('signs', 'crossings'):
            if k in tr and not isinstance(tr[k], list):
                p.f(f'$.traffic.{k}', 'muss eine Liste sein')

    ob = d.get('obstacles')
    if p.obj(ob, '$.obstacles', ('corridor', 'front_clearance_m', 'unknown_areas', 'distance_locks', 'objects')):
        p.text(ob, '$.obstacles', 'corridor', auswahl=BELEGUNG)
        p.messwert(ob, '$.obstacles', 'front_clearance_m', 0)
        p.janein(ob, '$.obstacles', 'unknown_areas', null=True)
        p.liste(ob, '$.obstacles', 'distance_locks')
        objekte = ob.get('objects')
        if not isinstance(objekte, list):
            p.f('$.obstacles.objects', 'muss eine Liste sein')
            objekte = []
        for i, o in enumerate(objekte):
            q = f'$.obstacles.objects[{i}]'
            if p.obj(o, q, ('class', 'distance_m', 'lateral_m', 'in_corridor', 'source', 'frame_id')):
                p.text(o, q, 'class', null=True)       # null = gemessen, aber nicht erkannt (bleibt wirksam)
                p.zahl(o, q, 'distance_m', null=True, mini=0)
                p.zahl(o, q, 'lateral_m', null=True)
                p.janein(o, q, 'in_corridor')
                p.text(o, q, 'source')
                p.text(o, q, 'frame_id', null=True)
        if ob.get('corridor') == 'free' and any(isinstance(o, dict) and o.get('in_corridor') for o in objekte):
            p.f('$.obstacles', "corridor 'free', aber ein Objekt liegt im Fahrbereich (R10)")

    se = d.get('sensors')
    if not isinstance(se, dict) or not se:
        p.f('$.sensors', 'muss ein nicht leeres Objekt sein (Name -> Quelle)')
    else:
        for name, q in se.items():
            _quelle(p, q, f'$.sensors.{name}')

    di = d.get('diagnostics')
    if p.obj(di, '$.diagnostics', ('battery_v', 'board_status', 'warnings', 'events')):
        p.messwert(di, '$.diagnostics', 'battery_v', 0, 30)
        p.text(di, '$.diagnostics', 'board_status', auswahl=STATUS)
        p.liste(di, '$.diagnostics', 'warnings')
        ev = di.get('events')
        if not isinstance(ev, list):
            p.f('$.diagnostics.events', 'muss eine Liste sein')
            ev = []
        for i, e in enumerate(ev):
            q = f'$.diagnostics.events[{i}]'
            if p.obj(e, q, ('event_id', 'mono_s', 'kind', 'text')):
                p.text(e, q, 'event_id')
                p.zahl(e, q, 'mono_s', mini=0)
                p.text(e, q, 'kind', auswahl=('info', 'stop', 'drive', 'warning', 'fault'))
                p.text(e, q, 'text')

    co = d.get('communication')
    if p.obj(co, '$.communication', ('broker', 'last_publish_requested_seq', 'last_broker_ack_seq',
                                     'last_broker_ack_mono_s', 'reconnects', 'dropped_messages', 'last_error')):
        p.text(co, '$.communication', 'broker', auswahl=BROKER)
        p.zahl(co, '$.communication', 'last_publish_requested_seq', null=True, mini=0, ganz=True)
        p.zahl(co, '$.communication', 'last_broker_ack_seq', null=True, mini=0, ganz=True)
        p.zahl(co, '$.communication', 'last_broker_ack_mono_s', null=True, mini=0)
        p.zahl(co, '$.communication', 'reconnects', mini=0, ganz=True)
        p.zahl(co, '$.communication', 'dropped_messages', mini=0, ganz=True)
        p.text(co, '$.communication', 'last_error', null=True)
        _kommunikation(p, d, co)

    de = d.get('details')
    if not isinstance(de, list):
        p.f('$.details', 'muss eine Liste sein')
    else:
        for i, x in enumerate(de):
            q = f'$.details[{i}]'
            if p.obj(x, q, ('channel', 'data_id', 'format', 'captured_at_s', 'frame_id', 'status')):
                for k in ('channel', 'data_id', 'format'):
                    p.text(x, q, k)
                p.zahl(x, q, 'captured_at_s', null=True, mini=0)
                p.text(x, q, 'frame_id', null=True)
                p.text(x, q, 'status', auswahl=STATUS)
                if x.get('status') == 'valid' and (x.get('captured_at_s') is None or x.get('frame_id') is None):
                    p.f(q, 'gueltige Detaildaten brauchen captured_at_s und frame_id')

    if not p.fehler:
        _betrieb(p, rt, out)
    return p.fehler


def _wert_passt_zu_status(p, d, pfad, felder):
    """R2 fuer Objekte mit eigenem status-Feld: valid <=> Werte vorhanden."""
    st = d.get('status')
    for k in felder:
        if st == 'valid' and d.get(k) is None:
            p.f(f'{pfad}.{k}', 'status valid braucht einen Wert (R2)')
        if st in STATUS and st != 'valid' and d.get(k) is not None:
            p.f(f'{pfad}.{k}', f'status {st} darf keinen Wert tragen (R2)')


def _quelle(p, q, pfad):
    """Sensorquelle (R7): valid braucht Aufnahmezeit und Alter, missing hat beides nicht."""
    if not p.obj(q, pfad, ('source_id', 'status', 'reason', 'captured_at_s', 'age_s', 'rate_hz', 'frame_id',
                           'coord_frame')):
        return
    p.text(q, pfad, 'source_id')
    p.text(q, pfad, 'status', auswahl=STATUS)
    p.text(q, pfad, 'reason', null=True)
    p.zahl(q, pfad, 'captured_at_s', null=True, mini=0)
    p.zahl(q, pfad, 'age_s', null=True, mini=0)
    p.zahl(q, pfad, 'rate_hz', null=True, mini=0)
    p.text(q, pfad, 'frame_id', null=True)
    p.text(q, pfad, 'coord_frame', null=True)
    st = q.get('status')
    if st == 'valid' and (q.get('captured_at_s') is None or q.get('age_s') is None):
        p.f(pfad, 'status valid braucht captured_at_s und age_s (R7)')
    if st == 'missing' and (q.get('captured_at_s') is not None or q.get('age_s') is not None):
        p.f(pfad, 'status missing: keine Messung, also auch keine Zeit (R7)')
    if st in ('invalid', 'stale', 'missing', 'unknown') and not q.get('reason'):
        p.f(pfad, f'status {st} braucht einen Grund (reason)')


def _kommunikation(p, d, co):
    """R6: bestaetigt <= angefordert <= dieser Datensatz. Angefordert ist noch keine Brokerbestaetigung."""
    seq, ang, best = d.get('seq'), co.get('last_publish_requested_seq'), co.get('last_broker_ack_seq')
    if isinstance(ang, int) and isinstance(seq, int) and ang > seq:
        p.f('$.communication', 'last_publish_requested_seq groesser als seq (R6)')
    if isinstance(best, int) and (ang is None or (isinstance(ang, int) and best > ang)):
        p.f('$.communication', 'last_broker_ack_seq ohne/groesser als angeforderte Veroeffentlichung (R6)')
    if (best is None) != (co.get('last_broker_ack_mono_s') is None):
        p.f('$.communication', 'last_broker_ack_seq und last_broker_ack_mono_s nur zusammen (R6)')
    if co.get('broker') == 'disconnected' and not co.get('last_error'):
        p.f('$.communication', 'broker disconnected braucht last_error')


def _betrieb(p, rt, out):
    """Fachliche Regeln zum Betrieb (R3-R5, R8). Nur, wenn die Struktur stimmt."""
    v, w = out.get('v_m_s', 0), out.get('w_rad_s', 0)
    bewegt = v != 0 or w != 0
    zustand, gruende = rt['state'], rt['hold_reasons']
    gesperrt = rt['stop_latched'] or rt['fault_latched'] or zustand in ('GESTOPPT', 'TEST', 'FEHLER')
    if gesperrt and rt['motor_enabled']:
        p.f('$.runtime.motor_enabled', f'muss false sein bei {zustand}/STOPP-/Fehlersperre (R3)')
    if gesperrt and bewegt:
        p.f('$.motion.output', f'muss 0 sein bei {zustand}/STOPP-/Fehlersperre (R3)')
    if bewegt and zustand not in FAHR_ZUSTAENDE:
        p.f('$.motion.output', f'Bewegung nur in {", ".join(FAHR_ZUSTAENDE)} (R4)')
    if bewegt and not rt['motor_enabled']:
        p.f('$.motion.output', 'Bewegung ohne motor_enabled (R4)')
    if zustand == 'VERKEHRSHALT':
        if not gruende:
            p.f('$.runtime.hold_reasons', 'VERKEHRSHALT braucht mindestens einen Haltegrund (R5)')
        if bewegt:
            p.f('$.motion.output', 'VERKEHRSHALT: Ausgabe muss 0 sein (R5)')
    if rt['stop_latched'] and 'STOP_LATCHED' not in gruende:
        p.f('$.runtime.hold_reasons', 'STOPP-Sperre aktiv, STOP_LATCHED fehlt (R8)')
    if zustand == 'FEHLER' and not rt['fault_latched']:
        p.f('$.runtime.fault_latched', 'FEHLER braucht fault_latched (R8)')
    if rt['fault_latched'] and not rt['faults']:
        p.f('$.runtime.faults', 'Fehlersperre ohne Fehlerbeschreibung (R8)')
