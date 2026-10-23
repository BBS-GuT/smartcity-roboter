"""Synthetische Bauwerte fuer isolierte Quellen-/Zeitpruefungen.

Keine Freigabe aus Kandidatendaten: Fachpakete bleiben ausdruecklich unbekannt.
Die gemeinsamen Fahrt-/STOPP-Beispiele werden separat mit gegebenem Kontext geprueft.
"""
from decimal import Decimal
import json
import grundbetrieb_vertrag as V
from c1_raeumzustand import unbekannte_bloecke
from pathlib import Path


def neutralisiere(d):
    for key, value in unbekannte_bloecke().items():
        if key == 'motion':
            request = d['motion']['request']
            d['motion'].update(value)
            d['motion']['request'] = request
        else:
            d[key] = value
    d['runtime'].update(evaluation_ref=None, stop_latched=None, fault_latched=None)
    d['route']['history'] = dict(producer_id=None, producer_boot_id=None,
        time_basis_id=None, status='unknown', reason='NOT_INITIALIZED',
        entries=None, dropped_entries=None)
    request = d['motion']['request']
    if request is not None:
        request.update(contract_version='2.0', robot_id=d['robot_id'],
            producer_id='synthetic-b', producer_boot_id='synthetic-b-start',
            request_seq=42, time_basis_id=d['time_basis_id'], generated_mono_s=0)
    return d


def lade_isoliertes_beispiel(text):
    d = neutralisiere(json.loads(text, parse_float=Decimal))
    return V.lade_json(V._json_wert(d))


def synthetischer_raeumkontext():
    """Expliziter Testbeleg aus separater Datei, niemals aus dem Kandidaten."""
    path = Path(__file__).parent / 'fixtures/c1_context/grundbetrieb.json'
    return V.RaeumKontext(**json.loads(path.read_text(encoding='utf-8'), parse_float=Decimal))
