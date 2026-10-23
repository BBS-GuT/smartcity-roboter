"""M1d (Issue #118): Einzelkarten zu einer gemeinsamen Karte zusammenfuehren.

Zentral ausfuehrbar (Laptop/Server am Broker), belastet die Jetsons nicht.
Eine Einzelkarte geht nur ein, wenn
  1. ihre Transformation bestaetigt ist (M1c),
  2. ihre eigene Guete ausreicht,
  3. sie mit der bisherigen gemeinsamen Karte ueberlappt UND dort messbar
     deckungsgleich ist (Deckungsfehler, Doppelwaende, Widersprueche).
Sonst wird sie abgelehnt - die gemeinsame Karte wird dadurch nie schlechter.

Die gemeinsame Karte ersetzt NICHT die lokale Hindernispruefung eines Roboters.

ANNAHMEN (an lib/karte.py anpassen, siehe adapter-Hinweis in der PR):
  * Gitter: int8, -1 unbekannt, 0 frei, 100 belegt; gitter[zeile=y, spalte=x]
  * ursprung = Koordinate der unteren linken Gitterecke im eigenen Rahmen (m)
  * transformation = (x, y, theta) vom eigenen in den gemeinsamen Rahmen
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

UNBEKANNT, FREI, BELEGT = -1, 0, 100


@dataclass
class Einzelkarte:
    geraet: str
    version: int
    gitter: np.ndarray
    aufloesung_m: float
    ursprung: tuple[float, float]
    transformation: tuple[float, float, float] | None
    transformation_bestaetigt: bool
    eigene_guete: float  # 0..1
    marker: dict[str, tuple[float, float]] = field(default_factory=dict)


@dataclass
class Grenzwerte:
    """Platzhalter - Werte mit dem Team festlegen und in docs/karte.md eintragen."""
    min_eigene_guete: float = 0.5
    suchradius_cm: float = 20.0         # Wand gilt als "gemeinsam gesehen"
    max_deckungsfehler_cm: float = 5.0
    doppelwand_ab_cm: float = 8.0       # Abstand, ab dem ein Paar als Doppelwand zaehlt
    max_doppelwand_anteil: float = 0.10
    max_widerspruch_anteil: float = 0.25  # Wandzellen ohne Gegenstueck im Ueberlappungsbereich
    min_wandzellen: int = 20            # darunter ist die Transformation nicht pruefbar
    min_bekannte_flaeche_prozent: float = 0.0


@dataclass
class Guete:
    deckungsfehler_cm: float
    doppelwand_anteil: float
    widerspruch_anteil: float
    bekannte_flaeche_prozent: float
    bestanden: bool


@dataclass
class Ergebnis:
    gitter: np.ndarray | None
    ursprung: tuple[float, float] | None
    aufloesung_m: float | None
    guete: Guete | None
    marker: dict[str, tuple[float, float]]
    kartenkennung: str
    version: int
    quellen: list[tuple[str, int]]
    abgelehnt: list[tuple[str, int, str]]


# ---------- Geometrie ----------

def _vor(t, x, y):
    tx, ty, th = t
    c, s = np.cos(th), np.sin(th)
    return c * x - s * y + tx, s * x + c * y + ty


def _rueck(t, x, y):
    tx, ty, th = t
    c, s = np.cos(th), np.sin(th)
    dx, dy = x - tx, y - ty
    return c * dx + s * dy, -s * dx + c * dy


def _rahmen(karten, res):
    punkte = []
    for k in karten:
        h, w = k.gitter.shape
        x0, y0 = k.ursprung
        for cx, cy in ((x0, y0), (x0 + w * res, y0), (x0, y0 + h * res), (x0 + w * res, y0 + h * res)):
            punkte.append(_vor(k.transformation, cx, cy))
    xs, ys = zip(*punkte)
    return min(xs), min(ys), max(xs), max(ys)


def _rasterisieren(k, x0, y0, shape, res):
    """Inverse Abbildung (keine Luecken bei Drehung)."""
    h, w = shape
    X, Y = np.meshgrid(x0 + (np.arange(w) + 0.5) * res, y0 + (np.arange(h) + 0.5) * res)
    sx, sy = _rueck(k.transformation, X, Y)
    j = np.floor((sx - k.ursprung[0]) / res).astype(int)
    i = np.floor((sy - k.ursprung[1]) / res).astype(int)
    ok = (i >= 0) & (i < k.gitter.shape[0]) & (j >= 0) & (j < k.gitter.shape[1])
    out = np.full(shape, UNBEKANNT, dtype=np.int8)
    out[ok] = k.gitter[i[ok], j[ok]]
    return out


def _fusion(gitter, gewichte):
    """Oefter/zuverlaessiger Gesehenes gewinnt; bei Gleichstand konservativ belegt."""
    occ = sum(w * (g == BELEGT) for g, w in zip(gitter, gewichte))
    fr = sum(w * (g == FREI) for g, w in zip(gitter, gewichte))
    out = np.full(gitter[0].shape, UNBEKANNT, dtype=np.int8)
    out[fr > 0] = FREI
    out[(occ > 0) & (occ >= fr)] = BELEGT
    return out


# ---------- Guetemasse ----------

def _einseitig(a, b, res, g):
    """Belegte Zellen von a (dort wo b etwas weiss) gegen belegte Zellen von b."""
    occ_a = (a == BELEGT) & (b != UNBEKANNT)
    n = int(occ_a.sum())
    if n == 0:
        return 0, 0.0, 0.0, 0.0
    if not (b == BELEGT).any():
        return n, 0.0, 0.0, 1.0
    dist_cm = ndimage.distance_transform_edt(b != BELEGT) * res * 100.0
    d = dist_cm[occ_a]
    nah = d <= g.suchradius_cm
    if not nah.any():
        return n, 0.0, 0.0, 1.0
    return n, float(d[nah].mean()), float((d[nah] > g.doppelwand_ab_cm).mean()), 1.0 - float(nah.mean())


def _paar(a, b, res, g):
    r1, r2 = _einseitig(a, b, res, g), _einseitig(b, a, res, g)
    return {
        "wandzellen": r1[0] + r2[0],
        "fehler": max(r1[1], r2[1]),
        "doppel": max(r1[2], r2[2]),
        "widerspruch": max(r1[3], r2[3]),
    }


def _grund_ablehnung(m, g):
    if m["wandzellen"] < g.min_wandzellen:
        return "zu wenig gemeinsame Waende - Transformation nicht pruefbar"
    if m["widerspruch"] > g.max_widerspruch_anteil:
        return f"Widerspruch {m['widerspruch']:.0%} > {g.max_widerspruch_anteil:.0%} (Transformation vermutlich falsch)"
    if m["fehler"] > g.max_deckungsfehler_cm:
        return f"Deckungsfehler {m['fehler']:.1f} cm > {g.max_deckungsfehler_cm} cm"
    if m["doppel"] > g.max_doppelwand_anteil:
        return f"Doppelwaende {m['doppel']:.0%} > {g.max_doppelwand_anteil:.0%}"
    return None


# ---------- Hauptfunktion ----------

def zusammenfuehren(karten, grenz: Grenzwerte | None = None, spielfeld_m2: float | None = None) -> Ergebnis:
    g = grenz or Grenzwerte()
    abgelehnt, gueltig = [], []
    for k in karten:
        if not k.transformation_bestaetigt or k.transformation is None:
            abgelehnt.append((k.geraet, k.version, "Transformation nicht bestaetigt (M1c)"))
        elif k.eigene_guete < g.min_eigene_guete:
            abgelehnt.append((k.geraet, k.version, f"eigene Guete {k.eigene_guete:.2f} < {g.min_eigene_guete}"))
        else:
            gueltig.append(k)

    if not gueltig:
        return Ergebnis(None, None, None, None, {}, "", 0, [], abgelehnt)

    res = gueltig[0].aufloesung_m
    if any(abs(k.aufloesung_m - res) > 1e-9 for k in gueltig):
        raise ValueError("Einzelkarten haben unterschiedliche Aufloesung - vorher angleichen")

    gueltig.sort(key=lambda k: k.eigene_guete, reverse=True)
    x0, y0, x1, y1 = _rahmen(gueltig, res)
    shape = (int(np.ceil((y1 - y0) / res)), int(np.ceil((x1 - x0) / res)))
    raster = {id(k): _rasterisieren(k, x0, y0, shape, res) for k in gueltig}

    angenommen = [gueltig[0]]
    merged = _fusion([raster[id(gueltig[0])]], [gueltig[0].eigene_guete])
    schlechtester = {"fehler": 0.0, "doppel": 0.0, "widerspruch": 0.0}

    for k in gueltig[1:]:
        m = _paar(merged, raster[id(k)], res, g)
        grund = _grund_ablehnung(m, g)
        if grund:
            abgelehnt.append((k.geraet, k.version, grund))
            continue
        angenommen.append(k)
        for key in schlechtester:
            schlechtester[key] = max(schlechtester[key], m[key])
        merged = _fusion([raster[id(a)] for a in angenommen], [a.eigene_guete for a in angenommen])

    bekannt = float((merged != UNBEKANNT).sum()) * res * res
    if spielfeld_m2:
        prozent = 100.0 * bekannt / spielfeld_m2
    else:
        prozent = 100.0 * float((merged != UNBEKANNT).mean())
    bestanden = (
        len(angenommen) >= 2
        and prozent >= g.min_bekannte_flaeche_prozent
        and _grund_ablehnung({**schlechtester, "wandzellen": g.min_wandzellen}, g) is None
    )
    guete = Guete(schlechtester["fehler"], schlechtester["doppel"], schlechtester["widerspruch"], prozent, bestanden)

    marker_roh: dict[str, list[tuple[float, float]]] = {}
    for k in angenommen:
        for name, (mx, my) in k.marker.items():
            marker_roh.setdefault(name, []).append(_vor(k.transformation, mx, my))
    marker = {n: (float(np.mean([p[0] for p in ps])), float(np.mean([p[1] for p in ps]))) for n, ps in marker_roh.items()}

    quellen = sorted((a.geraet, a.version) for a in angenommen)
    kennung = hashlib.sha1(repr(quellen).encode()).hexdigest()[:8]
    return Ergebnis(merged, (x0, y0), res, guete, marker, kennung, len(quellen), quellen, abgelehnt)
