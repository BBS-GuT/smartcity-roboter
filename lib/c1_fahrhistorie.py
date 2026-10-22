"""C1l: begrenzte bestaetigte Historie, ohne Navigation oder verstecktes Journal.

pruefe_historie prueft einen behaupteten Zustand, erzeugt keine Fahrtereignisse.
Ein valid-Anspruch braucht einen extern bestaetigten Karten-/Bindungskontext.
vorher ist ein vom Aufrufer bestaetigter Snapshot, nicht aus dem Kandidaten
erzeugt. Ohne vorher ist keine Aussage ueber fruehere Erfassungsluecken moeglich;
der Aufrufer muss diese im Bindungskontext als capture_gap erhalten.
Alle lokalen Zeiten benutzen ausschliesslich das gemeinsame 2.0-zeit_ns.
"""

MAX_ENTRIES = 16
_IDENTITY = ('producer_id', 'producer_boot_id', 'time_basis_id')
_HISTORY = set(_IDENTITY + ('status', 'reason', 'entries', 'dropped_entries'))
_ENTRY = {'section', 'node', 'approach_from', 'exit_to', 'entry_seq', 'confirmed_mono_s'}
_STATUSES = ('valid', 'missing', 'unknown', 'invalid')

# JSON-faehige $defs fuer den Integrator. Exaktes ns-Raster, Folge und externe
# Bindung bleiben semantische Pythonregeln, nicht behauptete Schemaabnahme.
_TEXT_SCHEMA = {'type': 'string', 'minLength': 1, 'pattern': r'\S'}
SCHEMA_DEFS = {
    'c1HistoryEntry': {
        'type': 'object', 'additionalProperties': False,
        'required': sorted(_ENTRY),
        'properties': {
            **{key: dict(_TEXT_SCHEMA) for key in ('section', 'node', 'approach_from', 'exit_to')},
            'entry_seq': {'type': 'integer', 'minimum': 0},
            'confirmed_mono_s': {
                'type': 'number', 'minimum': 0,
                'description': 'Exaktes ns-Raster und 0..2^63-1 ns prueft zeit_ns; keine Floatzeit im Pythonweg.'},
        },
    },
    'c1History': {
        'type': 'object', 'additionalProperties': False,
        'required': sorted(_HISTORY),
        'properties': {
            **{key: {'anyOf': [dict(_TEXT_SCHEMA), {'type': 'null'}]} for key in _IDENTITY},
            'status': {'enum': list(_STATUSES)},
            'reason': {'anyOf': [dict(_TEXT_SCHEMA), {'type': 'null'}]},
            'entries': {'anyOf': [
                {'type': 'null'},
                {'type': 'array', 'maxItems': MAX_ENTRIES,
                 'items': {'$ref': '#/$defs/c1HistoryEntry'}},
            ]},
            'dropped_entries': {'anyOf': [{'type': 'null'}, {'type': 'integer', 'minimum': 0}]},
        },
        'allOf': [
            {
                'if': {'properties': {'status': {'const': 'valid'}}},
                'then': {'properties': {
                    **{key: dict(_TEXT_SCHEMA) for key in _IDENTITY},
                    'reason': {'type': 'null'},
                    'entries': {'type': 'array'},
                    'dropped_entries': {'type': 'integer'},
                }},
                'else': {'properties': {
                    'reason': dict(_TEXT_SCHEMA), 'entries': {'type': 'null'},
                    'dropped_entries': {'type': 'null'},
                }},
            },
            {
                'if': {'properties': {'dropped_entries': {'type': 'integer', 'minimum': 1}}},
                'then': {'properties': {'entries': {'type': 'array', 'minItems': MAX_ENTRIES}}},
            },
            {
                'if': {'properties': {'reason': {'enum': ['capture_gap', 'map_changed']}}},
                'then': {'properties': {'status': {'const': 'invalid'}}},
            },
        ],
    },
}


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _integer(value):
    return type(value) is int and value >= 0


def _time(value, path, errors):
    # Spaeterer Fassadenimport ist damit ebenfalls ohne Importzyklus moeglich.
    from grundbetrieb_vertrag import zeit_ns
    try:
        return zeit_ns(value)
    except ValueError as exc:
        errors.append(f'{path}: {exc}')
        return None


def _object(value, fields, path, errors):
    if not isinstance(value, dict):
        errors.append(f'{path}: Objekt erforderlich')
        return False
    if set(value) != fields:
        errors.append(f'{path}: fehlende oder unbekannte Felder')
        return False
    return True


def _shape(history, path, errors):
    """Nur Form und intrinsische Konsistenz; keine Bestaetigung von Herkunft."""
    if not _object(history, _HISTORY, path, errors):
        return None
    status = history['status']
    if status not in _STATUSES:
        errors.append(f'{path}.status: valid/missing/unknown/invalid erforderlich')
    for field in _IDENTITY:
        value = history[field]
        if not _text(value) and not (value is None and status != 'valid'):
            errors.append(f'{path}.{field}: Herkunft fehlt oder ist kein Text')
    if status != 'valid':
        if not _text(history['reason']):
            errors.append(f'{path}.reason: begruendender Text erforderlich')
        if history['entries'] is not None or history['dropped_entries'] is not None:
            errors.append(f'{path}: nicht gueltige Nutzwerte muessen null bleiben')
        if history['reason'] in ('capture_gap', 'map_changed') and status != 'invalid':
            errors.append(f'{path}: Erfassungsluecke/Kartenwiderspruch muss invalid sein')
        return []
    if history['reason'] is not None:
        errors.append(f'{path}.reason: bei valid null erforderlich')
    entries, dropped = history['entries'], history['dropped_entries']
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        errors.append(f'{path}.entries: Liste mit maximal 16 Eintraegen erforderlich')
        return None
    if not _integer(dropped):
        errors.append(f'{path}.dropped_entries: nichtnegative ganze Zahl erforderlich')
        return None
    if dropped and len(entries) != MAX_ENTRIES:
        errors.append(f'{path}: positiver Verlustzaehler verlangt genau 16 Eintraege')
    times = []
    for index, entry in enumerate(entries):
        ep = f'{path}.entries[{index}]'
        if not _object(entry, _ENTRY, ep, errors):
            return None
        for field in ('section', 'node', 'approach_from', 'exit_to'):
            if not _text(entry[field]):
                errors.append(f'{ep}.{field}: Kartenkennung erforderlich')
        if not _integer(entry['entry_seq']) or entry['entry_seq'] != dropped + index:
            errors.append(f'{ep}.entry_seq: muss dropped_entries + Index sein')
        ns = _time(entry['confirmed_mono_s'], ep + '.confirmed_mono_s', errors)
        if ns is not None and times and times[-1] is not None and ns < times[-1]:
            errors.append(f'{ep}.confirmed_mono_s: Zeitregression')
        times.append(ns)
    return times


def _context(context, errors):
    """Kontext stammt aus einem bestaetigten externen Register, nie Kandidaten."""
    if not isinstance(context, dict):
        errors.append('history.context: bestaetigter Kontext fehlt')
        return None
    if set(context) != {'binding', 'map', 'confirmed_new_history_start'}:
        errors.append('history.context: unvollstaendiger oder unbekannter Kontext')
        return None
    if type(context['confirmed_new_history_start']) is not bool:
        errors.append('history.context.confirmed_new_history_start: bool erforderlich')
    binding = context['binding']
    fields = {'robot_id', 'producer_id', 'producer_boot_id', 'time_basis_id', 'initialized'}
    if (not isinstance(binding, dict)
            or set(binding) not in (fields, fields | {'capture_gap'})):
        errors.append('history.context.binding: unvollstaendige Bindung')
        return None
    if (any(not _text(binding[f]) for f in fields - {'initialized'})
            or type(binding['initialized']) is not bool
            or type(binding.get('capture_gap', False)) is not bool):
        errors.append('history.context.binding: ungueltige Identitaet/Initialisierung')
    road_map = context['map']
    if not _object(road_map, {'map_version', 'sections'}, 'history.context.map', errors):
        return None
    if not _text(road_map['map_version']) or not isinstance(road_map['sections'], list):
        errors.append('history.context.map: Version und gerichtete Abschnitte erforderlich')
        return None
    sections = {}
    for row in road_map['sections']:
        if not _object(row, {'section', 'node', 'approach_from', 'allowed_exits'},
                       'history.context.map.sections', errors):
            return None
        if any(not _text(row[f]) for f in ('section', 'node', 'approach_from')):
            errors.append('history.context.map: ungueltige Kartenkennung')
            return None
        exits = row['allowed_exits']
        if (not isinstance(exits, list) or not exits
                or any(not _text(x) for x in exits) or len(set(exits)) != len(exits)):
            errors.append('history.context.map: eindeutige erlaubte Ausfahrten erforderlich')
            return None
        if row['section'] in sections:
            errors.append('history.context.map: doppelte Abschnittskennung')
        sections[row['section']] = row
    return binding, road_map['map_version'], sections


def _transition(history, current, previous, context, errors):
    fields = {'robot_id', 'map_version', 'time_basis_id', 'generated_mono_s', 'history'}
    if not isinstance(previous, dict) or not fields.issubset(previous):
        errors.append('history.previous: bestaetigter Snapshot unvollstaendig')
        return
    previous_errors = []
    old_times = _shape(previous['history'], 'history.previous.history', previous_errors)
    old_time = _time(previous['generated_mono_s'], 'history.previous.generated_mono_s',
                     previous_errors)
    for field in ('robot_id', 'map_version', 'time_basis_id'):
        if not _text(previous[field]):
            previous_errors.append(f'history.previous.{field}: Kennung erforderlich')
    if previous_errors:
        errors.extend(previous_errors)
        return
    old = previous['history']
    if old['status'] == 'valid' and (
            old['time_basis_id'] != previous['time_basis_id']
            or any(ns > old_time for ns in old_times)):
        errors.append('history.previous: bestaetigter Snapshot hat unpassenden Zeitbezug')
        return
    if previous['robot_id'] != current['robot_id']:
        errors.append('history.previous: fremdes Geraet ist kein eigener Verlauf')
        return
    old_pair = old['producer_id'], old['producer_boot_id']
    new_pair = history['producer_id'], history['producer_boot_id']
    changed = old_pair != new_pair
    if changed:
        # Fehlendes Herkunftswissen darf keine bekannte alte Identitaet loeschen.
        if any(old[f] is not None and history[f] is None for f in _IDENTITY):
            errors.append('history: bekannte Herkunft darf nicht verloren gehen')
        if not (context and context['confirmed_new_history_start'] is True):
            errors.append('history: anderer B-Historienstart nicht bestaetigt')
        # Die explizite Initialisierung wird am ersten leeren Puffer beobachtet.
        # Ein spaeterer erster Abruf ohne diesen Vergleichsnachweis braucht einen
        # separat bestaetigten Snapshot, kein Erraten des Resetzeitpunktes.
        if history['status'] == 'valid' and (history['entries'] or history['dropped_entries']):
            errors.append('history: bestaetigter neuer B-Start muss leer initialisieren')
        return
    capture_gap = old['status'] == 'invalid' and old['reason'] == 'capture_gap'
    if capture_gap and not (history['status'] == 'invalid' and history['reason'] == 'capture_gap'):
        errors.append('history: capture_gap bleibt bis bestaetigtem neuen B-Start invalid')
    if previous['map_version'] != current['map_version']:
        if not (history['status'] == 'invalid' and history['reason'] in ('map_changed', 'capture_gap')):
            errors.append('history: map_changed braucht invalid oder neuen B-Historienstart')
    if previous['time_basis_id'] != current['time_basis_id']:
        if history['status'] == 'valid':
            errors.append('history: Uhrwechsel darf alte Zeiten nicht umetikettieren')
        return  # Keine Differenz oder Ordnung ueber verschiedene Geraeteuhren.
    if current['generated_ns'] < old_time:
        errors.append('history: Zustandserzeugung in derselben Uhr ruecklaeufig')
    for field in _IDENTITY:
        if old[field] is not None and history[field] is None:
            errors.append(f'history.{field}: bekannte Herkunft nicht loeschen')
    if old['status'] != 'valid' or history['status'] != 'valid':
        return
    if old['time_basis_id'] != history['time_basis_id']:
        errors.append('history: Historienuhr darf im selben B-Start nicht wechseln')
        return
    old_count = old['dropped_entries'] + len(old['entries'])
    new_count = history['dropped_entries'] + len(history['entries'])
    if new_count < old_count or history['dropped_entries'] < old['dropped_entries']:
        errors.append('history: Puffer/Zaehler im selben B-Start zurueckgesetzt')
    old_entries = {entry['entry_seq']: entry for entry in old['entries']}
    for entry in history['entries']:
        if entry['entry_seq'] in old_entries and entry != old_entries[entry['entry_seq']]:
            errors.append('history: bestaetigter Eintrag nachtraeglich veraendert')
        if old['entries'] and entry['entry_seq'] >= old_count:
            if _time(entry['confirmed_mono_s'], 'history.confirmed_mono_s', errors) < _time(
                    old['entries'][-1]['confirmed_mono_s'], 'history.previous.confirmed_mono_s', errors):
                errors.append('history: neuer Abschluss liegt vor letzter Bestaetigung')


def pruefe_historie(history, *, robot_id, map_version, time_basis_id,
                     generated_mono_s, kontext=None, vorher=None):
    """Fehlerliste, leer = ehrliche, konsistente Darstellung (auch missing/invalid).

    valid erfordert bestaetigte externe binding/map; null-Nutzwerte markieren
    fehlenden/unbekannten/ungueltigen Verlauf. Bekannte Herkunft bleibt erhalten.
    confirmed_new_history_start erlaubt einen leeren neuen B-Start im Vergleich.
    C-boot_id, Zustandseq, STOPP/TEST/Reconnect sind bewusst keine Reset-Eingaenge.
    Der Aufrufer liefert vorher oder dauerhaft bekannte capture_gap-Bindung;
    die Funktion fuehrt selbst keine Historie und prueft keine reale Bewegung.
    """
    errors = []
    times = _shape(history, 'history', errors)
    generated_ns = _time(generated_mono_s, 'generated_mono_s', errors)
    if not _text(robot_id):
        errors.append('robot_id: Geraetekennung erforderlich')
    if errors:
        return errors
    info = _context(kontext, errors) if kontext is not None else None
    if errors:
        return errors
    if history['status'] == 'valid':
        if info is None:
            errors.append('history: valid braucht bestaetigten Bindungs-/Kartenkontext')
        else:
            binding, version, sections = info
            if not binding['initialized']:
                errors.append('history: B-Erfassung nicht initialisiert')
            if binding.get('capture_gap', False):
                errors.append('history: capture_gap erlaubt keinen valid-Anspruch')
            if binding['robot_id'] != robot_id or any(history[f] != binding[f] for f in _IDENTITY):
                errors.append('history: fremde oder nicht bestaetigte Produzenten-/Uhrenbindung')
            if map_version != version:
                errors.append('history: fremde map_version')
            if time_basis_id != history['time_basis_id']:
                errors.append('history: Zustand und Historie haben keine gemeinsame Uhr')
            else:
                if any(ns > generated_ns for ns in times):
                    errors.append('history: Abschluss liegt nach Zustandserzeugung')
            for entry in history['entries']:
                row = sections.get(entry['section'])
                if (row is None or row['node'] != entry['node']
                        or row['approach_from'] != entry['approach_from']
                        or entry['exit_to'] not in row['allowed_exits']):
                    errors.append('history: Abschnitt/Zufahrt/Ausfahrt nicht in gegebener Karte')
    elif info:
        binding = info[0]
        for field in _IDENTITY:
            if history[field] is None and binding[field] is not None:
                errors.append(f'history.{field}: bekannte Herkunft nicht durch null ersetzen')
            elif history[field] is not None and history[field] != binding[field]:
                errors.append(f'history.{field}: Herkunft stimmt nicht mit bestaetigter Bindung ueberein')
        if binding.get('capture_gap', False) and not (
                history['status'] == 'invalid' and history['reason'] == 'capture_gap'):
            errors.append('history: bekannte capture_gap muss invalid bleiben')
    if vorher is not None and not errors:
        current = dict(robot_id=robot_id, map_version=map_version,
                       time_basis_id=time_basis_id, generated_ns=generated_ns)
        _transition(history, current, vorher, kontext, errors)
    return errors
