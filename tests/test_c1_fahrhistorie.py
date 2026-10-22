import sys
import os

# Pfad für die Module anpassen
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lib')))
from grundbetrieb_vertrag import prfe_fahrhistorie

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