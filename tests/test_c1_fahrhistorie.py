import json
import os
import sys

# Pfad für die Module anpassen
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lib')))
from grundbetrieb_vertrag import prfe_fahrhistorie, pruefe
import jsonschema

ROOT = os.path.dirname(os.path.abspath(__file__))
SCHEMA = os.path.join(ROOT, '..', 'schemas', 'grundbetrieb-v1.schema.json')
with open(SCHEMA, encoding='utf-8') as f:
    SCHEMA_VALIDATOR = jsonschema.Draft202012Validator(json.load(f))

def test_c1_fahrhistorie_struktur():
    """Grundlegender Test für die begrenzte bestätigte Fahrhistorie (C1I, Issue #153)."""
    assert prfe_fahrhistorie({'entries': []})
    assert prfe_fahrhistorie({'entries': [{'seq': seq} for seq in range(12, 16)]})
    assert prfe_fahrhistorie({'entries': [{'seq': seq} for seq in range(16)]})
    assert not prfe_fahrhistorie(None)
    assert not prfe_fahrhistorie({})
    assert not prfe_fahrhistorie({'entries': [{'seq': seq} for seq in range(17)]})
    assert not prfe_fahrhistorie({'entries': [{'seq': 4}, {'seq': 6}]})
    assert not prfe_fahrhistorie({'entries': [{'seq': 4}, {'seq': 4}]})
    assert not prfe_fahrhistorie({'entries': [{'seq': True}]})

    with open(os.path.join(ROOT, 'fixtures', 'grundbetrieb', 'fahrt.json'), encoding='utf-8') as f:
        datensatz = json.load(f)
    datensatz['route']['history'] = {'entries': [{'seq': seq} for seq in range(12, 16)]}
    assert pruefe(datensatz) == []
    assert SCHEMA_VALIDATOR.is_valid(datensatz)

    datensatz['route']['history']['entries'][2]['seq'] = 16
    assert any('$.route.history' in fehler for fehler in pruefe(datensatz))
    assert not SCHEMA_VALIDATOR.is_valid(datensatz)

    datensatz['route']['history'] = {'entries': [{'seq': seq} for seq in range(17)]}
    assert any('$.route.history' in fehler for fehler in pruefe(datensatz))
    assert not SCHEMA_VALIDATOR.is_valid(datensatz)