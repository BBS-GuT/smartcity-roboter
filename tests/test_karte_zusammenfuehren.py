import numpy as np

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.karte_zusammenfuehren import BELEGT, Einzelkarte, zusammenfuehren

RES = 0.05


def _welt():
    w = np.zeros((80, 120), dtype=np.int8)
    w[0, :] = w[-1, :] = w[:, 0] = w[:, -1] = BELEGT
    w[:, 60] = BELEGT
    w[30:50, 60] = 0  # Tuer
    return w


def _karte(name, gitter, trafo, guete=0.9, bestaetigt=True, marker=None):
    return Einzelkarte(name, 1, gitter, RES, (0.0, 0.0), trafo, bestaetigt, guete, marker or {})


def _paar(**kw):
    welt = _welt()
    a = _karte("rm01", welt[:, :80], (0.0, 0.0, 0.0), marker={"M1": (1.0, 1.0)})
    b = _karte("rm02", welt[:, 40:], kw.pop("trafo", (2.0, 0.0, 0.0)), marker={"M1": (-1.0, 1.0)}, **kw)
    return a, b


def test_gute_karten_werden_vereint():
    r = zusammenfuehren(list(_paar()))
    assert r.guete.bestanden and len(r.quellen) == 2 and not r.abgelehnt
    assert r.guete.deckungsfehler_cm < 1.0
    assert r.marker["M1"] == (1.0, 1.0)
    assert (r.gitter != -1).sum() > (_welt()[:, :80] != -1).sum()  # groesser als Einzelkarte


def test_falsche_transformation_wird_abgelehnt():
    r = zusammenfuehren(list(_paar(trafo=(2.5, 0.3, 0.0))))
    assert len(r.quellen) == 1 and "Widerspruch" in r.abgelehnt[0][2]
    assert not r.guete.bestanden


def test_unbestaetigte_transformation_wird_abgelehnt():
    r = zusammenfuehren(list(_paar(bestaetigt=False)))
    assert "nicht bestaetigt" in r.abgelehnt[0][2]


def test_schlechte_eigene_guete_wird_abgelehnt():
    r = zusammenfuehren(list(_paar(guete=0.2)))
    assert "Guete" in r.abgelehnt[0][2]


def test_kartenkennung_ist_reproduzierbar():
    assert zusammenfuehren(list(_paar())).kartenkennung == zusammenfuehren(list(reversed(_paar()))).kartenkennung
