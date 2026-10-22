"""Eigenstaendiger C1-Fahrwunsch und explizite Datenannahme, ohne Aktorfreigabe.

Struktur-/JSON-Pruefung ist zustandslos. Nur ``annehmen`` schreibt die getrennt
gespeicherten Annahme- und Anti-Replay-Staende fort. Alle Zeitoperationen benutzen
den gemeinsamen exakten Nanosekundenpfad; Nachrichten koennen keine Bindung setzen.
"""
import copy
from decimal import Decimal
import json


FELDER = ('contract_version', 'robot_id', 'producer_id', 'producer_boot_id',
          'request_seq', 'request_id', 'time_basis_id', 'generated_mono_s',
          'valid_until_mono_s', 'v_m_s', 'w_rad_s', 'maneuver', 'hold_reasons')
BINDUNGSFELDER = ('robot_id', 'producer_id', 'producer_boot_id', 'time_basis_id',
                 'bind_mono_s', 'max_duration_s')
IDENTITAETSFELDER = BINDUNGSFELDER[:4]


def _vertrag():
    # Auch der Fassadenimport aus grundbetrieb_vertrag bleibt dadurch kreisfrei.
    import grundbetrieb_vertrag
    return grundbetrieb_vertrag


def zeit_ns(wert):
    return _vertrag().zeit_ns(wert)


def sekunden_aus_ns(wert):
    return _vertrag().sekunden_aus_ns(wert)


def pruefe_fahrwunsch(wunsch):
    """Struktur und intrinsische Regeln; keinerlei Annahme oder Fristneustart."""
    v = _vertrag()
    p = v._Pruefer()
    if not p.obj(wunsch, '$', FELDER):
        return p.fehler
    p.text(wunsch, '$', 'contract_version', auswahl=(v.SCHEMA_VERSION,))
    p.text(wunsch, '$', 'robot_id', auswahl=v.GERAETE)
    for feld in ('producer_id', 'producer_boot_id', 'request_id', 'time_basis_id'):
        p.text(wunsch, '$', feld)
    p.zahl(wunsch, '$', 'request_seq', ganz=True, mini=0)
    for feld in ('generated_mono_s', 'valid_until_mono_s'):
        p.zahl(wunsch, '$', feld, mini=0)
    p.zahl(wunsch, '$', 'v_m_s', mini=-1, maxi=1)
    p.zahl(wunsch, '$', 'w_rad_s', mini=-10, maxi=10)
    p.text(wunsch, '$', 'maneuver', null=True)
    p.liste(wunsch, '$', 'hold_reasons', auswahl=v.HALTEGRUENDE)
    if not p.fehler:
        if zeit_ns(wunsch['valid_until_mono_s']) <= zeit_ns(wunsch['generated_mono_s']):
            p.f('$.valid_until_mono_s', 'Frist muss nach der Erzeugung liegen')
    return p.fehler


def fahrwunsch_als_json(wunsch):
    """Exaktes JSON gemaess gemeinsamem Vertrag, ohne Zustandsaenderung."""
    fehler = pruefe_fahrwunsch(wunsch)
    if fehler:
        raise ValueError('; '.join(fehler))
    return _vertrag()._json_wert(wunsch)


def _eindeutige_felder(paare):
    ergebnis = {}
    for name, wert in paare:
        if name in ergebnis:
            raise ValueError('doppeltes JSON-Feld: ' + name)
        ergebnis[name] = wert
    return ergebnis


def lade_fahrwunsch_json(text):
    """JSON ohne Float-Zwischenstufe; strenge, zustandslose Requestpruefung."""
    try:
        wunsch = json.loads(text, parse_float=Decimal,
                            parse_constant=_vertrag()._kein_nan,
                            object_pairs_hook=_eindeutige_felder)
    except (TypeError, UnicodeError, json.JSONDecodeError) as e:
        raise ValueError('ungueltiges Fahrwunsch-JSON') from e
    fehler = pruefe_fahrwunsch(wunsch)
    if fehler:
        raise ValueError('; '.join(fehler))
    return wunsch


class FahrwunschAnnahme:
    """Lokaler, ausdruecklich gebundener Annahmekontext eines A-Verbrauchers.

    ``None`` dokumentiert unbekannten Kontext. ``binde`` ist die einzige
    ausdrueckliche Neubindung; C-Start und eingehende Nachrichten sind keine
    Bindungsquelle. Zurueckgegebene Objekte sind stets abgetrennte Kopien.
    """

    def __init__(self, *, robot_id, producer_id, producer_boot_id,
                 time_basis_id, bind_mono_s, max_duration_s):
        self.binde(robot_id=robot_id, producer_id=producer_id,
                   producer_boot_id=producer_boot_id, time_basis_id=time_basis_id,
                   bind_mono_s=bind_mono_s, max_duration_s=max_duration_s)

    def binde(self, *, robot_id, producer_id, producer_boot_id,
              time_basis_id, bind_mono_s, max_duration_s):
        """Bestaetigte A-/B-Neubindung; loescht alte Datenverwendbarkeit."""
        self._bindung = copy.deepcopy(dict(robot_id=robot_id, producer_id=producer_id,
            producer_boot_id=producer_boot_id, time_basis_id=time_basis_id,
            bind_mono_s=bind_mono_s, max_duration_s=max_duration_s))
        self._angenommen = None
        self._hoechststand = None

    def _kontextzeiten(self, jetzt_mono_s):
        if any(self._bindung[k] is None for k in BINDUNGSFELDER):
            return 'unknown', 'binding_or_budget_unknown', None
        if any(not isinstance(self._bindung[k], str) or not self._bindung[k]
               for k in IDENTITAETSFELDER):
            return 'invalid', 'binding_identity_invalid', None
        if self._bindung['robot_id'] not in _vertrag().GERAETE:
            return 'invalid', 'binding_robot_invalid', None
        if jetzt_mono_s is None:
            return 'unknown', 'now_unknown', None
        try:
            jetzt = zeit_ns(jetzt_mono_s)
            bind = zeit_ns(self._bindung['bind_mono_s'])
            dauer = zeit_ns(self._bindung['max_duration_s'])
        except ValueError:
            return 'invalid', 'binding_or_now_time_invalid', None
        if dauer <= 0 or bind > jetzt:
            return 'invalid', 'binding_or_budget_invalid', None
        return None, None, (jetzt, bind, dauer)

    def _antwort(self, status, reason):
        return dict(status=status, reason=reason, verwendbar=status == 'accepted',
                    neu=status == 'accepted', kontext=copy.deepcopy(self._bindung),
                    angenommen=copy.deepcopy(self._angenommen),
                    hoechststand=copy.deepcopy(self._hoechststand))

    def annehmen(self, wunsch, *, jetzt_mono_s):
        """Explizite Datenannahme; abgelaufene hoehere Sequenz sperrt aeltere.

        Fremde, zukuenftige, ueberlange oder zeitregressive Eingaben veraendern
        keinen Vergleichsstand. Der Hoechststand bleibt auch nach Ablauf erhalten.
        """
        fehler = pruefe_fahrwunsch(wunsch)
        if fehler:
            return self._antwort('invalid', 'request_invalid: ' + '; '.join(fehler))
        status, grund, zeiten = self._kontextzeiten(jetzt_mono_s)
        if status:
            return self._antwort(status, grund)
        if any(wunsch[k] != self._bindung[k] for k in IDENTITAETSFELDER):
            return self._antwort('invalid', 'request_binding_mismatch')
        jetzt, bind, maximaldauer = zeiten
        erzeugt = zeit_ns(wunsch['generated_mono_s'])
        frist = zeit_ns(wunsch['valid_until_mono_s'])
        if erzeugt <= bind:
            return self._antwort('invalid', 'request_not_after_binding')
        if erzeugt > jetzt:
            return self._antwort('invalid', 'request_from_future')
        if frist - erzeugt > maximaldauer:
            return self._antwort('invalid', 'request_duration_exceeded')

        hwm = self._hoechststand
        if hwm is not None:
            if wunsch['request_seq'] < hwm['request_seq']:
                return self._antwort('replay', 'request_sequence_below_high_watermark')
            if wunsch['request_seq'] == hwm['request_seq']:
                if wunsch == hwm:
                    return self._antwort('duplicate', 'request_already_observed')
                return self._antwort('invalid', 'request_sequence_content_conflict')
            if erzeugt < zeit_ns(hwm['generated_mono_s']):
                return self._antwort('invalid', 'request_generation_regressed')

        self._hoechststand = copy.deepcopy(wunsch)
        if jetzt >= frist:
            return self._antwort('expired', 'request_deadline_reached')
        self._angenommen = copy.deepcopy(wunsch)
        return self._antwort('accepted', 'fresh_bound_request_accepted')

    def annehmen_json(self, text, *, jetzt_mono_s):
        try:
            wunsch = lade_fahrwunsch_json(text)
        except ValueError as e:
            return self._antwort('invalid', 'request_json_invalid: ' + str(e))
        return self.annehmen(wunsch, jetzt_mono_s=jetzt_mono_s)

    def aktueller_wunsch(self, *, jetzt_mono_s):
        """Erneut Frist/Bindung/Anti-Replay pruefen, ohne Annahmestand zu mutieren."""
        status, _, zeiten = self._kontextzeiten(jetzt_mono_s)
        if status or self._angenommen is None or self._hoechststand is None:
            return None
        if self._angenommen != self._hoechststand:
            return None
        jetzt, bind, _ = zeiten
        erzeugt = zeit_ns(self._angenommen['generated_mono_s'])
        frist = zeit_ns(self._angenommen['valid_until_mono_s'])
        if not bind < erzeugt <= jetzt < frist:
            return None
        return copy.deepcopy(self._angenommen)
