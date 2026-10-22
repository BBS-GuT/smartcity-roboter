"""C1 V3a: reine Datenpruefung, keine Freigabe- oder Aktuatorlogik.

Explizite Register sind lokale Belege, niemals aus dem Kandidaten erzeugt.
Die Funktion ist zustandslos; Auswertungs-/Command-Register werden nicht geaendert.
"""
from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal
import math


STATUS = ('valid', 'unknown', 'invalid', 'stale', 'missing')
BASE = ('robot_id', 'producer_id', 'producer_boot_id')
REFS = {name: BASE + fields for name, fields in {
    'owner': (), 'operation': ('operation_id',), 'object': ('object_id',),
    'frame': ('source', 'frame_id'), 'detail': ('source', 'frame_id', 'channel', 'data_id'),
    'observation': ('observation_seq',), 'estimate': ('estimate_seq',),
    'request': ('request_seq',), 'command': ('command_seq',), 'output': ('output_seq',),
    'evaluation': ('domain', 'evaluation_seq'), 'block': ('block_id',),
    'evidence': ('evidence_seq',),
}.items()}


@dataclass(frozen=True)
class RaeumKontext:
    """Bestaetigte Datenbelege; current_*_ref stammt aus expliziter Annahme.

    Register sind Sequenzen vollstaendiger Datensaetze. component_units ordnet
    (coord_frame, calibration_version) auf {Komponente: Einheit} ab. bindings
    ordnet motion/arm/clearing auf bestaetigte Herkunft samt time_basis_id ab.
    Ein gleicher Text im Kandidaten ist keine implizite Bindung.
    """
    frames: tuple = ()
    details: tuple = ()
    evidences: tuple = ()
    policy_evidences: tuple = ()
    requests: tuple = ()
    commands: tuple = ()
    evaluations: tuple = ()
    component_units: dict = field(default_factory=dict)
    bindings: dict = field(default_factory=dict)
    current_request_ref: object = None
    current_command_ref: object = None
    previous_state: object = None

    def __post_init__(self):
        for name in self.__dataclass_fields__:
            object.__setattr__(self, name, deepcopy(getattr(self, name)))


def _ns(value):
    # Lazy import also works when this module is wired into the facade.
    try:
        from .grundbetrieb_vertrag import zeit_ns
    except ImportError:
        from grundbetrieb_vertrag import zeit_ns
    return zeit_ns(value)


def _finite(value):
    return (not isinstance(value, bool) and
            (isinstance(value, int) or
             (isinstance(value, Decimal) and value.is_finite()) or
             (isinstance(value, float) and math.isfinite(value))))


class _Check:
    def __init__(self, state, context):
        self.s, self.c, self.errors = state, context, []
        self.robot = state.get('robot_id')
        self.clock = state.get('time_basis_id')
        self.now = self.time(state.get('generated_mono_s'), '$.generated_mono_s')

    def fail(self, p, text):
        self.errors.append(f'{p}: {text}')

    def obj(self, x, p, fields):
        if not isinstance(x, dict):
            self.fail(p, 'muss Objekt sein')
            return False
        for k in fields:
            if k not in x:
                self.fail(p + '.' + k, 'Pflichtfeld fehlt')
        extra = set(x) - set(fields)
        if extra:
            self.fail(p, 'unbekannte Felder: ' + ', '.join(sorted(extra)))
        return True

    def text(self, v, p, null=False, choices=None):
        if v is None and null:
            return True
        if not isinstance(v, str) or not v or (choices is not None and v not in choices):
            self.fail(p, 'ungueltiger Textwert')
            return False
        return True

    def seq(self, v, p, null=False):
        if v is None and null:
            return True
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            self.fail(p, 'muss ganze Zahl >= 0 sein')
            return False
        return True

    def time(self, v, p, null=False):
        if v is None and null:
            return None
        try:
            return _ns(v)
        except (ValueError, TypeError):
            self.fail(p, 'ungueltige exakte Sekundenzeit')
            return None

    def q(self, x, p):
        st = x.get('status')
        self.text(st, p + '.status', choices=STATUS)
        if st == 'valid':
            if x.get('reason') is not None:
                self.fail(p + '.reason', 'valid verlangt null')
        else:
            self.text(x.get('reason'), p + '.reason')
        return st == 'valid'

    def ref(self, x, kind, p, null=False):
        if x is None and null:
            return None
        fields = REFS[kind]
        if not self.obj(x, p, fields):
            return None
        for k in fields:
            if k.endswith('_seq'):
                self.seq(x.get(k), p + '.' + k)
            else:
                self.text(x.get(k), p + '.' + k)
        if x.get('robot_id') != self.robot:
            self.fail(p, 'fremdes Geraet')
        if kind == 'evaluation' and x.get('domain') not in ('motion', 'arm'):
            self.fail(p + '.domain', 'motion/arm erwartet')
        return x

    def identity(self, x, kind):
        return {k: x.get(k) for k in REFS[kind]}

    def find(self, entries, ref, kind):
        if not isinstance(ref, dict):
            return None
        matches = [e for e in entries if isinstance(e, dict) and
                   (e.get(kind + '_ref') == ref or self.identity(e, kind) == ref)]
        if not matches:
            return None
        if any(e != matches[0] for e in matches[1:]):
            self.fail('$.' + kind + '_register', 'gleicher Schluessel mit widerspruechlichem Inhalt')
            return None
        return matches[0]

    def clock_time(self, x, key, p, valid=False):
        t = self.time(x.get(key), p + '.' + key, null=not valid)
        self.text(x.get('time_basis_id'), p + '.time_basis_id', null=not valid)
        if t is not None and x.get('time_basis_id') == self.clock and self.now is not None and t > self.now:
            self.fail(p + '.' + key, 'nach Zustandserzeugung')
        if valid and x.get('time_basis_id') != self.clock:
            self.fail(p + '.time_basis_id', 'valid braucht belegte gemeinsame Uhr')
        return t

    def bound(self, domain, owner, clock, p):
        b = (self.c.bindings or {}).get(domain)
        if not isinstance(b, dict) or not isinstance(owner, dict) or any(b.get(k) != owner.get(k) for k in BASE) or b.get('time_basis_id') != clock:
            self.fail(p, 'explizite Herkunfts-/Uhrenbindung fehlt oder widerspricht')
            return False
        return True

    def components(self, x, p, uncertainty=False):
        if not self.obj(x, p, ('coord_frame', 'calibration_version', 'values', 'status', 'reason')):
            return
        valid = self.q(x, p)
        for k in ('coord_frame', 'calibration_version'):
            self.text(x.get(k), p + '.' + k, null=not valid)
        values = x.get('values')
        if not valid:
            if values is not None:
                self.fail(p + '.values', 'nicht verfuegbare Werte muessen null sein')
            return
        if not isinstance(values, dict) or not values:
            self.fail(p + '.values', 'valid braucht nichtleere Komponenten')
            return
        units = (self.c.component_units or {}).get((x.get('coord_frame'), x.get('calibration_version')))
        if not isinstance(units, dict):
            self.fail(p, 'Komponenten-/Kalibrierbeleg fehlt')
            units = {}
        for k, value in values.items():
            q = p + '.values.' + str(k)
            if self.obj(value, q, ('value', 'unit')):
                if not _finite(value.get('value')):
                    self.fail(q + '.value', 'endliche Zahl erforderlich')
                elif uncertainty and value['value'] < 0:
                    self.fail(q + '.value', 'Unsicherheit muss nichtnegativ sein')
                if value.get('unit') not in ('m', 'rad', 'N', '1') or units.get(k) != value.get('unit'):
                    self.fail(q + '.unit', 'Komponente/Einheit passt nicht zum gegebenen Kontext')

    def frame(self, ref, p, require=False):
        if self.ref(ref, 'frame', p, null=not require) is None:
            return None
        record = self.find(self.c.frames, ref, 'frame')
        if require and record is None:
            self.fail(p, 'historischer Framebeleg fehlt')
        return record

    def measurement_block(self, x, p):
        if not self.obj(x, p, ('measurements', 'status', 'reason')):
            return
        valid = self.q(x, p)
        entries = x.get('measurements')
        if not valid:
            if entries is not None:
                self.fail(p + '.measurements', 'unverfuegbare Messungen muessen null sein')
            return
        if not isinstance(entries, list) or not entries:
            self.fail(p, 'valid braucht echte Messdatensaetze')
            return
        for i, entry in enumerate(entries):
            q = f'{p}.measurements[{i}]'
            if self.obj(entry, q, ('frame_ref', 'time_basis_id', 'captured_mono_s', 'received_mono_s', 'components', 'status', 'reason')):
                ev = self.q(entry, q)
                record = self.frame(entry.get('frame_ref'), q + '.frame_ref', require=ev)
                captured = self.clock_time(entry, 'captured_mono_s', q, ev)
                received = self.clock_time(entry, 'received_mono_s', q, ev)
                if captured is not None and received is not None and entry.get('time_basis_id') == self.clock and captured > received:
                    self.fail(q, 'Aufnahme nach Empfang')
                if record is not None:
                    for k in ('time_basis_id', 'captured_mono_s'):
                        if record.get(k) != entry.get(k):
                            self.fail(q + '.' + k, 'widerspricht unveraenderlicher Frameaufnahme')
                self.components(entry.get('components'), q + '.components')
                if ev and not (isinstance(entry.get('components'), dict) and entry['components'].get('status') == 'valid'):
                    self.fail(q, 'valid braucht gueltige Messkomponenten')

    def observation(self, x, p, obj_ref):
        fields = ('observation_ref', 'object_ref', 'frame_ref', 'detail_ref', 'time_basis_id', 'captured_mono_s', 'received_mono_s', 'class_value', 'class_status', 'class_reason', 'spatial', 'status', 'reason')
        if not self.obj(x, p, fields):
            return
        valid = self.q(x, p)
        self.ref(x.get('observation_ref'), 'observation', p + '.observation_ref')
        self.ref(x.get('object_ref'), 'object', p + '.object_ref')
        if x.get('object_ref') != obj_ref:
            self.fail(p + '.object_ref', 'anderes Objekt')
        record = self.frame(x.get('frame_ref'), p + '.frame_ref', require=valid)
        detail = self.ref(x.get('detail_ref'), 'detail', p + '.detail_ref', null=True)
        if detail is not None:
            if {k: detail.get(k) for k in REFS['frame']} != x.get('frame_ref'):
                self.fail(p + '.detail_ref', 'anderer Frame')
            if valid and self.find(self.c.details, detail, 'detail') is None:
                self.fail(p + '.detail_ref', 'Detailbeleg fehlt')
        captured = self.clock_time(x, 'captured_mono_s', p, valid)
        received = self.clock_time(x, 'received_mono_s', p, valid)
        if captured is not None and received is not None and x.get('time_basis_id') == self.clock and captured > received:
            self.fail(p, 'Aufnahme nach Empfang')
        if record is not None and any(record.get(k) != x.get(k) for k in ('time_basis_id', 'captured_mono_s')):
            self.fail(p, 'Beobachtung darf Frameaufnahme nicht erneuern')
        class_q = {'status': x.get('class_status'), 'reason': x.get('class_reason')}
        if self.q(class_q, p + '.class'):
            self.text(x.get('class_value'), p + '.class_value')
        elif x.get('class_value') is not None:
            self.fail(p + '.class_value', 'unbekannte Klasse ist null')
        self.components(x.get('spatial'), p + '.spatial')

    def estimate(self, x, p, obj_ref, observation):
        fields = ('estimate_ref', 'object_ref', 'observation_ref', 'odometry_ref', 'time_basis_id', 'estimated_mono_s', 'spatial', 'uncertainty', 'status', 'reason')
        if not self.obj(x, p, fields):
            return
        valid = self.q(x, p)
        for kind in ('estimate', 'object', 'observation'):
            self.ref(x.get(kind + '_ref'), kind, p + '.' + kind + '_ref')
        if x.get('object_ref') != obj_ref or (isinstance(observation, dict) and x.get('observation_ref') != observation.get('observation_ref')):
            self.fail(p, 'Schaetzung hat anderen Objekt-/Beobachtungsbezug')
        self.frame(x.get('odometry_ref'), p + '.odometry_ref', require=valid)
        self.clock_time(x, 'estimated_mono_s', p, valid)
        self.components(x.get('spatial'), p + '.spatial')
        self.components(x.get('uncertainty'), p + '.uncertainty', uncertainty=True)
        if valid and any(not isinstance(x.get(k), dict) or x[k].get('status') != 'valid' for k in ('spatial', 'uncertainty')):
            self.fail(p, 'gueltige Schaetzung braucht belegte Lage und Unsicherheit')
        if isinstance(x.get('spatial'), dict) and isinstance(x.get('uncertainty'), dict):
            a, b = x['spatial'].get('values'), x['uncertainty'].get('values')
            if isinstance(a, dict) and isinstance(b, dict) and (set(a) != set(b) or any(not isinstance(a[k], dict) or not isinstance(b[k], dict) or a[k].get('unit') != b[k].get('unit') for k in set(a) & set(b))):
                self.fail(p + '.uncertainty', 'Komponenten/Einheiten passen nicht zur Lage')

    def clearing(self):
        x, p = self.s.get('clearing'), '$.clearing'
        if not self.obj(x, p, CLEARING_FIELDS):
            return
        valid = self.q(x, p)
        for k in ('producer_id', 'producer_boot_id', 'time_basis_id', 'operation_id'):
            self.text(x.get(k), p + '.' + k, null=(not valid or k == 'operation_id'))
        self.text(x.get('phase'), p + '.phase', null=not valid, choices=PHASES)
        self.text(x.get('execution_status'), p + '.execution_status', null=not valid, choices=('laufend', 'pausiert', 'beendet'))
        self.text(x.get('result'), p + '.result', null=not valid, choices=('offen', 'erfolgreich', 'nicht_raeumbar', 'abgebrochen'))
        if valid:
            owner = {'robot_id': self.robot, 'producer_id': x.get('producer_id'), 'producer_boot_id': x.get('producer_boot_id')}
            self.bound('clearing', owner, x.get('time_basis_id'), p)
        if x.get('phase') == 'inaktiv' and valid:
            for k in INACTIVE_NULL:
                if x.get(k) is not None:
                    self.fail(p + '.' + k, 'inaktiv verlangt null')
            if x.get('execution_status') != 'beendet' or x.get('result') != 'offen':
                self.fail(p, 'inaktiv verlangt beendet/offen')
            if isinstance(self.s.get('arm'), dict) and self.s['arm'].get('request') is not None:
                self.fail('$.arm.request', 'inaktiv entwertet aktuellen Armwunsch')
        active = x.get('phase') not in ('inaktiv', None)
        start = self.clock_time(x, 'started_mono_s', p, valid and active)
        update = self.clock_time(x, 'updated_mono_s', p, valid and active)
        if start is not None and update is not None and x.get('time_basis_id') == self.clock and start > update:
            self.fail(p, 'Beginn liegt nach letztem Uebergang')
        self.ref(x.get('object_ref'), 'object', p + '.object_ref', null=not (valid and active))
        if valid and active:
            self.text(x.get('operation_id'), p + '.operation_id')
        for reason, when in (('abort_reason', x.get('result') == 'abgebrochen'), ('result_reason', x.get('result') == 'nicht_raeumbar'), ('interruption_reason', x.get('execution_status') == 'pausiert')):
            if when:
                self.text(x.get(reason), p + '.' + reason)
            elif x.get(reason) is not None:
                self.fail(p + '.' + reason, 'hier null erforderlich')
        if x.get('execution_status') == 'pausiert':
            t = self.clock_time(x, 'interrupted_mono_s', p, True)
            if x.get('result') != 'offen':
                self.fail(p + '.result', 'Pause ist kein Abschluss')
            if t is not None and start is not None and update is not None and not start <= t <= update:
                self.fail(p + '.interrupted_mono_s', 'nicht innerhalb des Vorgangs')
        elif x.get('interrupted_mono_s') is not None:
            self.fail(p + '.interrupted_mono_s', 'ohne Pause null')
        if x.get('result') in ('erfolgreich', 'nicht_raeumbar', 'abgebrochen') and x.get('execution_status') != 'beendet':
            self.fail(p + '.execution_status', 'abschliessendes Ergebnis verlangt beendet')
        if x.get('phase') == 'beendet' and x.get('execution_status') != 'beendet':
            self.fail(p + '.execution_status', 'beendete Phase verlangt beendet')
        for name in ('observation', 'estimate'):
            if x.get(name) is not None:
                if x.get('object_ref') is None:
                    self.fail(p + '.' + name, 'ohne Objektbezug null')
                if name == 'observation':
                    self.observation(x[name], p + '.' + name, x.get('object_ref'))
                else:
                    self.estimate(x[name], p + '.' + name, x.get('object_ref'), x.get('observation'))
        op = {'robot_id': self.robot, 'producer_id': x.get('producer_id'), 'producer_boot_id': x.get('producer_boot_id'), 'operation_id': x.get('operation_id')}
        for kind in ('verification', 'travel_pose'):
            link = x.get(kind + '_ref')
            if link is None:
                if x.get('result') == 'erfolgreich':
                    self.fail(p + '.' + kind + '_ref', 'Erfolg braucht Nachweis')
                continue
            if not self.obj(link, p + '.' + kind + '_ref', ('ref', 'status', 'reason')):
                continue
            lv = self.q(link, p + '.' + kind + '_ref')
            ref = self.ref(link.get('ref'), 'evidence', p + '.' + kind + '_ref.ref', null=not lv)
            e = self.find(self.c.evidences, ref, 'evidence')
            if lv and (e is None or e.get('status') != 'valid' or e.get('kind') != kind or e.get('operation_ref') != op):
                self.fail(p + '.' + kind + '_ref', 'gueltiger Link braucht passenden belegten Nachweis')
            if x.get('result') == 'erfolgreich' and (not lv or e is None or e.get('status') != 'valid' or e.get('kind') != kind or e.get('operation_ref') != op):
                self.fail(p + '.' + kind + '_ref', 'Erfolgsnachweis fehlt/falscher Vorgang oder Art')
            if e is not None and lv:
                t = self.clock_time(e, 'confirmed_mono_s', p + '.' + kind + '_evidence', True)
                refs = e.get('source_refs')
                if not isinstance(refs, list) or not refs:
                    self.fail(p, 'Erfolgsbeleg braucht echte Quellen')
                else:
                    for j, r in enumerate(refs):
                        self.frame(r, f'{p}.{kind}.source_refs[{j}]', True)
                if t is not None and start is not None and update is not None and not start <= t <= update:
                    self.fail(p, 'Erfolgsbeleg ausserhalb des Vorgangs')

    def policy(self, name, id_name, version_name):
        x, p = self.s.get(name), '$.' + name
        if not self.obj(x, p, (id_name, version_name, 'evidence_ref', 'status', 'reason')):
            return
        valid = self.q(x, p)
        for k in (id_name, version_name):
            self.text(x.get(k), p + '.' + k, null=not valid)
        ref = self.ref(x.get('evidence_ref'), 'evidence', p + '.evidence_ref', null=not valid)
        if valid:
            e = self.find(self.c.policy_evidences, ref, 'evidence')
            if e is None or e.get('status') != 'valid' or e.get('kind') != ('policy' if name == 'protection' else 'sensor_requirements') or any(e.get(k) != x.get(k) for k in (id_name, version_name)):
                self.fail(p, 'Politik-/Matrixnachweis fehlt oder passt nicht')

    def command(self, x):
        p = '$.arm.request'
        if x is None:
            return
        fields = ('contract_version',) + BASE + ('command_seq', 'time_basis_id', 'generated_mono_s', 'valid_until_mono_s', 'operation_ref', 'object_ref', 'action', 'target')
        if not self.obj(x, p, fields):
            return
        self.ref(self.identity(x, 'command'), 'command', p + '.command_ref')
        if x.get('contract_version') != '2.0':
            self.fail(p + '.contract_version', 'muss2.0 sein')
        self.text(x.get('time_basis_id'), p + '.time_basis_id')
        generated = self.time(x.get('generated_mono_s'), p + '.generated_mono_s')
        until = self.time(x.get('valid_until_mono_s'), p + '.valid_until_mono_s')
        if generated is not None and until is not None and generated >= until:
            self.fail(p, 'positive Commanddauer erforderlich')
        for kind in ('operation', 'object'):
            self.ref(x.get(kind + '_ref'), kind, p + '.' + kind + '_ref')
        self.text(x.get('action'), p + '.action')
        if x.get('target') is not None:
            self.components(x['target'], p + '.target')
        else:
            # Zielwertfreie Aktion muss im expliziten Kontext deklariert sein.
            b = (self.c.bindings or {}).get('arm_command', {})
            if x.get('action') not in b.get('targetless_actions', ()):
                self.fail(p + '.target', 'zielwertfreie Aktionsbedeutung nicht bestaetigt')

    def package(self, domain):
        block, p = self.s.get(domain), '$.' + domain
        if not isinstance(block, dict):
            self.fail(p, 'muss Objekt sein')
            return
        key = 'request' if domain == 'motion' else 'command'
        release, locks, out, use = (block.get(k) for k in ('release', 'blocks', 'output', 'package_use'))
        rfields = ('owner_ref', 'decision_seq', 'evaluation_ref', 'time_basis_id', 'evaluated_mono_s', 'decision', key + '_ref', key + '_reason', 'output_ref', 'output_reason', 'status', 'reason')
        if not self.obj(release, p + '.release', rfields):
            return
        rv = self.q(release, p + '.release')
        self.text(release.get('decision'), p + '.release.decision', choices=('allowed', 'blocked', 'unknown'))
        owner = self.ref(release.get('owner_ref'), 'owner', p + '.release.owner_ref', null=True)
        eref = self.ref(release.get('evaluation_ref'), 'evaluation', p + '.release.evaluation_ref', null=True)
        self.seq(release.get('decision_seq'), p + '.release.decision_seq', null=True)
        evaluated = self.clock_time(release, 'evaluated_mono_s', p + '.release', rv)
        ref = self.ref(release.get(key + '_ref'), key, p + '.release.' + key + '_ref', null=True)
        for k, reason in ((key + '_ref', key + '_reason'), ('output_ref', 'output_reason')):
            self.text(release.get(reason), p + '.release.' + reason, null=release.get(k) is not None)
            if release.get(k) is not None and release.get(reason) is not None:
                self.fail(p + '.release.' + reason, 'bei vorhandener Referenz null')
        if owner is None:
            if release.get('decision') != 'unknown' or release.get('status') not in ('unknown', 'missing'):
                self.fail(p + '.release', 'ohne Besitzer nur unbekanntes Ergebnis')
        if eref is not None:
            if eref.get('domain') != domain or self.identity(eref, 'owner') != owner:
                self.fail(p + '.release.evaluation_ref', 'Auswertungsbesitzer/Domaene widerspricht')
        elif release.get('decision') != 'unknown' or rv:
            self.fail(p + '.release', 'bekanntes Ergebnis braucht Auswertung')
        if rv:
            self.bound(domain, owner, release.get('time_basis_id'), p + '.release')
        if not self.obj(use, p + '.package_use', ('mode', 'reason', 'evaluation_ref')):
            use = {}
        self.text(use.get('mode'), p + '.package_use.mode', choices=('current', 'historical', 'unknown'))
        if use.get('mode') == 'current':
            if use.get('reason') is not None:
                self.fail(p + '.package_use.reason', 'current verlangt null')
        else:
            self.text(use.get('reason'), p + '.package_use.reason')
        if use.get('evaluation_ref') != eref or (eref is None and use.get('mode') != 'unknown'):
            self.fail(p + '.package_use', 'Auswertungsbezug passt nicht')
        lfields = ('producer_id', 'producer_boot_id', 'seq', 'evaluation_ref', 'time_basis_id', 'evaluated_mono_s', 'entries', 'stop_latched', 'fault_latched', 'status', 'reason')
        effective = []
        if self.obj(locks, p + '.blocks', lfields):
            lv = self.q(locks, p + '.blocks')
            self.seq(locks.get('seq'), p + '.blocks.seq', null=not lv)
            for k in ('producer_id', 'producer_boot_id'):
                self.text(locks.get(k), p + '.blocks.' + k, null=not lv)
                if isinstance(owner, dict) and locks.get(k) != owner.get(k):
                    self.fail(p + '.blocks.' + k, 'Sperrbild nicht vom Freigabebesitzer')
            if locks.get('evaluation_ref') != eref or locks.get('time_basis_id') != release.get('time_basis_id') or locks.get('evaluated_mono_s') != release.get('evaluated_mono_s'):
                self.fail(p + '.blocks', 'kein atomares Auswertungspaket')
            for k in ('stop_latched', 'fault_latched'):
                latch = locks.get(k)
                if self.obj(latch, p + '.blocks.' + k, ('value', 'status', 'reason')):
                    qv = self.q(latch, p + '.blocks.' + k)
                    if (qv and not isinstance(latch.get('value'), bool)) or (not qv and latch.get('value') is not None):
                        self.fail(p + '.blocks.' + k, 'Latchwert passt nicht zur Qualitaet')
                    if latch.get('value') is True:
                        effective.append('STOP_LATCHED' if k == 'stop_latched' else 'FAULT')
            entries = locks.get('entries')
            if lv and not isinstance(entries, list):
                self.fail(p + '.blocks.entries', 'valid braucht vollstaendige Liste')
            if not lv and entries is not None:
                self.fail(p + '.blocks.entries', 'unbekanntes Sperrbild ist null')
            for i, entry in enumerate(entries if isinstance(entries, list) else []):
                q = f'{p}.blocks.entries[{i}]'
                if self.obj(entry, q, ('block_ref', 'code', 'effect', 'frame_ref', 'time_basis_id', 'reported_mono_s', 'status', 'reason')):
                    ev = self.q(entry, q)
                    self.ref(entry.get('block_ref'), 'block', q + '.block_ref')
                    self.text(entry.get('code'), q + '.code')
                    self.text(entry.get('effect'), q + '.effect', choices=('motion', 'arm', 'both'))
                    self.frame(entry.get('frame_ref'), q + '.frame_ref')
                    self.clock_time(entry, 'reported_mono_s', q)
                    if ev and entry.get('effect') in (domain, 'both'):
                        effective.append(entry.get('code'))
            if release.get('decision') == 'allowed' and (not lv or effective or any(not isinstance(locks.get(k), dict) or locks[k].get('status') != 'valid' for k in ('stop_latched', 'fault_latched'))):
                self.fail(p + '.release', 'allowed mit wirksamer/unbekannter Sperre')
        if out is None:
            if release.get('output_ref') is not None:
                self.fail(p + '.release.output_ref', 'ohne Ausgabe null')
        elif self.obj(out, p + '.output', OUTPUT_FIELDS[domain]):
            ov = self.q(out, p + '.output')
            self.ref(self.identity(out, 'output'), 'output', p + '.output.output_ref')
            self.ref(out.get('evaluation_ref'), 'evaluation', p + '.output.evaluation_ref', null=not ov)
            issued = self.clock_time(out, 'issued_mono_s', p + '.output', ov)
            if out.get('evaluation_ref') != eref or release.get('output_ref') != self.identity(out, 'output'):
                self.fail(p + '.output', 'Ausgabe-/Auswertungsbezug widerspricht')
            if out.get(key + '_ref') != ref or out.get(key + '_reason') != release.get(key + '_reason'):
                self.fail(p + '.output', 'Wunschbezug/Grund widerspricht Ergebnis')
            if evaluated is not None and issued is not None and out.get('time_basis_id') == release.get('time_basis_id') and issued < evaluated:
                self.fail(p + '.output', 'Ausgabe vor Auswertung')
            if out.get('time_basis_id') != release.get('time_basis_id'):
                self.fail(p + '.output', 'fremde Ausgabeuhr')
            if domain == 'motion':
                for k in ('v_m_s', 'w_rad_s'):
                    if ov and not _finite(out.get(k)):
                        self.fail(p + '.output.' + k, 'gueltige SI-Ausgabe erforderlich')
                    elif not ov and out.get(k) is not None:
                        self.fail(p + '.output.' + k, 'unbekannte Ausgabe ist null')
                moving = ov and all(_finite(out.get(k)) for k in ('v_m_s', 'w_rad_s')) and (out.get('v_m_s') != 0 or out.get('w_rad_s') != 0)
                if release.get('decision') == 'blocked' and moving:
                    self.fail(p + '.output', 'blocked verlangt exakt 0/0')
            else:
                self.text(out.get('action'), p + '.output.action', null=not ov)
                if out.get('target') is not None:
                    self.components(out['target'], p + '.output.target')
                for kind in ('operation', 'object'):
                    self.ref(out.get(kind + '_ref'), kind, p + '.output.' + kind + '_ref', null=ref is None)
                if release.get('decision') == 'blocked' and ref is not None:
                    self.fail(p + '.output', 'blocked verbietet commandgebundene Armausgabe')
                if ref is None and ov and release.get(key + '_reason') != 'PROTECTIVE_ACTION_WITHOUT_REQUEST':
                    self.fail(p + '.output', 'wunschloser Armauftrag braucht expliziten Schutzgrund')
        moving = (domain == 'motion' and isinstance(out, dict) and out.get('status') == 'valid' and all(_finite(out.get(k)) for k in ('v_m_s', 'w_rad_s')) and (out.get('v_m_s') != 0 or out.get('w_rad_s') != 0))
        needs_request = release.get('decision') == 'allowed' or moving or (domain == 'arm' and out is not None and ref is not None)
        if needs_request:
            register = self.c.requests if domain == 'motion' else self.c.commands
            request = self.find(register, ref, key)
            current_ref = self.c.current_request_ref if domain == 'motion' else self.c.current_command_ref
            if request is None or ref is None:
                self.fail(p, 'Erlaubnis/Ausgabe braucht aufloesbaren bestaetigten Wunsch')
            else:
                generated = self.time(request.get('generated_mono_s'), p + '.bound_request.generated_mono_s')
                until = self.time(request.get('valid_until_mono_s'), p + '.bound_request.valid_until_mono_s')
                if request.get('time_basis_id') != self.clock or release.get('time_basis_id') != self.clock:
                    self.fail(p, 'Wunsch-/Paketzeitbasis nicht belegt')
                if generated is not None and until is not None and evaluated is not None:
                    if not generated <= evaluated < until:
                        self.fail(p, 'Wunsch bereits bei Auswertung ungueltig')
                    if use.get('mode') == 'current' and self.now is not None and not generated <= self.now < until:
                        self.fail(p, 'aktuelle Verwendung nach/bei Ablauf oder vor Erzeugung')
                    if isinstance(out, dict):
                        issued = self.time(out.get('issued_mono_s'), p + '.output.issued_mono_s', True)
                        if issued is not None and not generated <= issued < until:
                            self.fail(p + '.output', 'Ausgabe ausserhalb Wunschfrist')
                if use.get('mode') == 'current' and current_ref != ref:
                    self.fail(p, 'kein bestaetigter aktueller Annahmebezug/ueberholt')
                inline = block.get('request')
                if inline is not None and inline != request:
                    self.fail(p + '.request', 'eingebetteter Wunsch weicht vom bestaetigten Inhalt ab')
            if use.get('mode') == 'unknown':
                self.fail(p + '.package_use', 'Erlaubnis/Ausgabe ohne belegten Verwendungsbezug')
        if moving and release.get('decision') != 'allowed':
            self.fail(p + '.output', 'fahrende Ausgabe braucht allowed')
        if use.get('mode') == 'current' and not rv:
            self.fail(p + '.package_use', 'aktuelles Paket braucht gueltige Ergebnisdaten')
        for known in self.c.evaluations:
            if isinstance(known, dict) and known.get('evaluation_ref') == eref and any(known.get(k) != block.get(k) for k in ('release', 'blocks', 'output')):
                self.fail(p, 'gleiche Auswertungskennung mit geaendertem Paket')
        previous = self.c.previous_state
        if isinstance(previous, dict) and isinstance(previous.get(domain), dict):
            old = previous[domain]
            old_release = old.get('release')
            if eref is not None and isinstance(old_release, dict) and old_release.get('evaluation_ref') == eref and any(old.get(k) != block.get(k) for k in ('release', 'blocks', 'output')):
                self.fail(p, 'gleiche Auswertungskennung gegenueber vorherigem Zustand veraendert')
        if domain == 'motion':
            rt = self.s.get('runtime')
            if isinstance(rt, dict):
                if use.get('mode') == 'current':
                    if rt.get('evaluation_ref') != eref:
                        self.fail('$.runtime.evaluation_ref', 'aktuelle Motion-Auswertung erforderlich')
                    if isinstance(locks, dict):
                        for k in ('stop_latched', 'fault_latched'):
                            latch = locks.get(k)
                            if isinstance(latch, dict) and rt.get(k) != latch.get('value'):
                                self.fail('$.runtime.' + k, 'Projektion widerspricht aktuellem Sperrbild')
                        if set(rt.get('hold_reasons') or ()) != set(effective):
                            self.fail('$.runtime.hold_reasons', 'Projektion muss aktuelles Sperrbild genau wiedergeben')
                elif rt.get('evaluation_ref') is not None:
                    self.fail('$.runtime.evaluation_ref', 'historische/unbekannte Pakete nicht aktuell projizieren')

    def run(self):
        self.clearing()
        previous = self.c.previous_state
        old = previous.get('clearing') if isinstance(previous, dict) else None
        current = self.s.get('clearing')
        if isinstance(old, dict) and isinstance(current, dict):
            keys = ('producer_id', 'producer_boot_id', 'operation_id')
            if current.get('operation_id') is not None and all(old.get(k) == current.get(k) for k in keys) and old.get('object_ref') != current.get('object_ref'):
                self.fail('$.clearing.object_ref', 'Objektwechsel verlangt neuen Vorgang')
        self.package('motion')
        self.package('arm')
        arm = self.s.get('arm')
        if isinstance(arm, dict):
            for k in ARM_FIELDS:
                if k not in arm:
                    self.fail('$.arm.' + k, 'Pflichtfeld fehlt')
            for k in set(arm) - set(ARM_FIELDS):
                self.fail('$.arm.' + k, 'unbekanntes Feld')
            self.command(arm.get('request'))
            for k in ('measured', 'load'):
                self.measurement_block(arm.get(k), '$.arm.' + k)
            ack = arm.get('ack')
            if ack is not None and self.obj(ack, '$.arm.ack', ('output_ref', 'time_basis_id', 'received_mono_s', 'status', 'reason')):
                valid = self.q(ack, '$.arm.ack')
                ref = self.ref(ack.get('output_ref'), 'output', '$.arm.ack.output_ref', null=not valid)
                received = self.clock_time(ack, 'received_mono_s', '$.arm.ack', valid)
                out = arm.get('output')
                if valid and (not isinstance(out, dict) or self.identity(out, 'output') != ref):
                    self.fail('$.arm.ack.output_ref', 'Empfang bestaetigt andere/unbekannte Ausgabe')
                if isinstance(out, dict) and received is not None:
                    issued = self.time(out.get('issued_mono_s'), '$.arm.output.issued_mono_s', True)
                    if issued is not None and ack.get('time_basis_id') == out.get('time_basis_id') and issued > received:
                        self.fail('$.arm.ack', 'Empfang vor Ausgabe')
        self.measurement_block(self.s.get('camera_pose'), '$.camera_pose')
        self.policy('protection', 'policy_id', 'policy_version')
        self.policy('sensor_requirements', 'matrix_id', 'matrix_version')
        return self.errors


PHASES = ('inaktiv', 'anschauen', 'ausrichten', 'greifen', 'ablegen', 'nachpruefen', 'fahrstellung_bestaetigen', 'beendet')
INACTIVE_NULL = ('operation_id', 'started_mono_s', 'updated_mono_s', 'object_ref', 'abort_reason', 'result_reason', 'interruption_reason', 'interrupted_mono_s', 'verification_ref', 'travel_pose_ref', 'observation', 'estimate')
CLEARING_FIELDS = ('producer_id', 'producer_boot_id', 'time_basis_id', 'status', 'reason', 'phase', 'execution_status', 'result') + INACTIVE_NULL
ARM_FIELDS = ('request', 'output', 'release', 'blocks', 'package_use', 'ack', 'measured', 'load')
OUTPUT_FIELDS = {
    'motion': BASE + ('output_seq', 'time_basis_id', 'issued_mono_s', 'v_m_s', 'w_rad_s', 'request_ref', 'request_reason', 'evaluation_ref', 'status', 'reason'),
    'arm': BASE + ('output_seq', 'time_basis_id', 'issued_mono_s', 'action', 'target', 'command_ref', 'command_reason', 'operation_ref', 'object_ref', 'evaluation_ref', 'status', 'reason'),
}
STATE_FIELDS = {'clearing': CLEARING_FIELDS, 'arm': ARM_FIELDS, 'motion_additional': ('release', 'blocks', 'package_use'), 'root_additional': ('clearing', 'arm', 'camera_pose', 'protection', 'sensor_requirements')}


def pruefe_raeumzustand(zustand, *, kontext=None):
    """Fehlerliste; fehlender Kontext bestaetigt niemals Belege oder Erlaubnisse."""
    if not isinstance(zustand, dict):
        return ['$: muss Objekt sein']
    if kontext is None:
        kontext = RaeumKontext()
    if not isinstance(kontext, RaeumKontext):
        return ['$: kontext muss RaeumKontext sein']
    return _Check(zustand, kontext).run()


def _schema_defs():
    text = {'type': 'string', 'minLength': 1}
    nullable_text = {'anyOf': [text, {'type': 'null'}]}
    integer = {'type': 'integer', 'minimum': 0}
    number = {'type': 'number'}
    time = {'type': 'number', 'minimum': 0, 'maximum': Decimal('9223372036.854775807')}
    null = {'type': 'null'}
    q = {'status': {'enum': list(STATUS)}, 'reason': nullable_text}

    def obj(props):
        return {'type': 'object', 'required': list(props), 'properties': props, 'additionalProperties': False}

    def ref(name, nullable=False):
        r = {'$ref': '#/$defs/c1_' + name}
        return {'anyOf': [r, null]} if nullable else r

    def maybe(s):
        return {'anyOf': [s, null]}

    defs = {}
    for name, fields in REFS.items():
        defs['c1_' + name + '_ref'] = obj({k: ({'enum': ['motion', 'arm']} if k == 'domain' else integer if k.endswith('_seq') else text) for k in fields})
    component = obj({'value': number, 'unit': {'enum': ['m', 'rad', 'N', '1']}})
    defs['c1_components'] = obj({'coord_frame': nullable_text, 'calibration_version': nullable_text, 'values': maybe({'type': 'object', 'minProperties': 1, 'additionalProperties': component}), **q})
    defs['c1_measurement'] = obj({'frame_ref': ref('frame_ref'), 'time_basis_id': nullable_text, 'captured_mono_s': maybe(time), 'received_mono_s': maybe(time), 'components': ref('components'), **q})
    defs['c1_measurements'] = obj({'measurements': maybe({'type': 'array', 'minItems': 1, 'items': ref('measurement')}), **q})
    defs['c1_latch'] = obj({'value': {'type': ['boolean', 'null']}, **q})
    defs['c1_package_use'] = obj({'mode': {'enum': ['current', 'historical', 'unknown']}, 'reason': nullable_text, 'evaluation_ref': ref('evaluation_ref', True)})
    defs['c1_block_entry'] = obj({'block_ref': ref('block_ref'), 'code': text, 'effect': {'enum': ['motion', 'arm', 'both']}, 'frame_ref': ref('frame_ref', True), 'time_basis_id': nullable_text, 'reported_mono_s': maybe(time), **q})
    defs['c1_blocks'] = obj({'producer_id': nullable_text, 'producer_boot_id': nullable_text, 'seq': maybe(integer), 'evaluation_ref': ref('evaluation_ref', True), 'time_basis_id': nullable_text, 'evaluated_mono_s': maybe(time), 'entries': maybe({'type': 'array', 'items': ref('block_entry')}), 'stop_latched': ref('latch'), 'fault_latched': ref('latch'), **q})
    for domain, key in (('motion', 'request'), ('arm', 'command')):
        defs['c1_' + domain + '_release'] = obj({'owner_ref': ref('owner_ref', True), 'decision_seq': maybe(integer), 'evaluation_ref': ref('evaluation_ref', True), 'time_basis_id': nullable_text, 'evaluated_mono_s': maybe(time), 'decision': {'enum': ['allowed', 'blocked', 'unknown']}, key + '_ref': ref(key + '_ref', True), key + '_reason': nullable_text, 'output_ref': ref('output_ref', True), 'output_reason': nullable_text, **q})
        props = {k: text for k in BASE}
        props.update({'output_seq': integer, 'time_basis_id': nullable_text, 'issued_mono_s': maybe(time), key + '_ref': ref(key + '_ref', True), key + '_reason': nullable_text, 'evaluation_ref': ref('evaluation_ref', True), **q})
        if domain == 'motion':
            props.update({'v_m_s': maybe(number), 'w_rad_s': maybe(number)})
        else:
            props.update({'action': nullable_text, 'target': ref('components', True), 'operation_ref': ref('operation_ref', True), 'object_ref': ref('object_ref', True)})
        defs['c1_' + domain + '_output'] = obj(props)
    defs['c1_arm_command'] = obj({'contract_version': {'const': '2.0'}, **{k: text for k in BASE}, 'command_seq': integer, 'time_basis_id': text, 'generated_mono_s': time, 'valid_until_mono_s': time, 'operation_ref': ref('operation_ref'), 'object_ref': ref('object_ref'), 'action': text, 'target': ref('components', True)})
    defs['c1_arm_ack'] = obj({'output_ref': ref('output_ref', True), 'time_basis_id': nullable_text, 'received_mono_s': maybe(time), **q})
    defs['c1_arm'] = obj({'request': ref('arm_command', True), 'output': ref('arm_output', True), 'release': ref('arm_release'), 'blocks': ref('blocks'), 'package_use': ref('package_use'), 'ack': ref('arm_ack', True), 'measured': ref('measurements'), 'load': ref('measurements')})
    defs['c1_observation'] = obj({'observation_ref': ref('observation_ref'), 'object_ref': ref('object_ref'), 'frame_ref': ref('frame_ref'), 'detail_ref': ref('detail_ref', True), 'time_basis_id': nullable_text, 'captured_mono_s': maybe(time), 'received_mono_s': maybe(time), 'class_value': nullable_text, 'class_status': q['status'], 'class_reason': nullable_text, 'spatial': ref('components'), **q})
    defs['c1_estimate'] = obj({'estimate_ref': ref('estimate_ref'), 'object_ref': ref('object_ref'), 'observation_ref': ref('observation_ref'), 'odometry_ref': ref('frame_ref', True), 'time_basis_id': nullable_text, 'estimated_mono_s': maybe(time), 'spatial': ref('components'), 'uncertainty': ref('components'), **q})
    defs['c1_evidence_link'] = obj({'ref': ref('evidence_ref', True), **q})
    props = {k: nullable_text for k in ('producer_id', 'producer_boot_id', 'time_basis_id', 'operation_id')}
    props.update({'phase': {'enum': list(PHASES) + [None]}, 'execution_status': {'enum': ['laufend', 'pausiert', 'beendet', None]}, 'result': {'enum': ['offen', 'erfolgreich', 'nicht_raeumbar', 'abgebrochen', None]}, **q})
    props.update({k: maybe(time) for k in ('started_mono_s', 'updated_mono_s', 'interrupted_mono_s')})
    props.update({k: nullable_text for k in ('abort_reason', 'result_reason', 'interruption_reason')})
    props.update({'object_ref': ref('object_ref', True), 'observation': ref('observation', True), 'estimate': ref('estimate', True), 'verification_ref': ref('evidence_link', True), 'travel_pose_ref': ref('evidence_link', True)})
    defs['c1_clearing'] = obj(props)
    defs['c1_protection'] = obj({'policy_id': nullable_text, 'policy_version': nullable_text, 'evidence_ref': ref('evidence_ref', True), **q})
    defs['c1_sensor_requirements'] = obj({'matrix_id': nullable_text, 'matrix_version': nullable_text, 'evidence_ref': ref('evidence_ref', True), **q})
    return defs


SCHEMA_DEFS = _schema_defs()


def unbekannte_bloecke():
    """Explizite unbekannte Nullbelegung fuer synthetische Bauwerte, kein Beleg.

    Uebernimmt keinerlei Daten aus einem Kandidaten und erzeugt keine Identitaet.
    runtime-Projektion muss evaluation_ref=None und unbekannte Latches enthalten.
    """
    q = {'status': 'unknown', 'reason': 'NOT_INITIALIZED'}
    latch = {'value': None, **q}
    use = {'mode': 'unknown', 'reason': 'NOT_INITIALIZED', 'evaluation_ref': None}
    locks = {k: None for k in ('producer_id', 'producer_boot_id', 'seq', 'evaluation_ref', 'time_basis_id', 'evaluated_mono_s', 'entries')}
    locks.update({'stop_latched': deepcopy(latch), 'fault_latched': deepcopy(latch), **q})
    result = {}
    for domain, key in (('motion', 'request'), ('arm', 'command')):
        release = {k: None for k in ('owner_ref', 'decision_seq', 'evaluation_ref', 'time_basis_id', 'evaluated_mono_s', key + '_ref', 'output_ref')}
        release.update({'decision': 'unknown', key + '_reason': key.upper() + '_REFERENCE_UNKNOWN', 'output_reason': 'OUTPUT_UNKNOWN', **q})
        result[domain] = {'request': None, 'output': None, 'release': release, 'blocks': deepcopy(locks), 'package_use': deepcopy(use)}
    result['arm'].update({'ack': None, 'measured': {'measurements': None, **q}, 'load': {'measurements': None, **q}})
    result['clearing'] = {k: None for k in CLEARING_FIELDS}
    result['clearing'].update(q)
    result['camera_pose'] = {'measurements': None, **q}
    result['protection'] = {'policy_id': None, 'policy_version': None, 'evidence_ref': None, **q}
    result['sensor_requirements'] = {'matrix_id': None, 'matrix_version': None, 'evidence_ref': None, **q}
    return result
