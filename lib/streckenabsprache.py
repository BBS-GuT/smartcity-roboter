#!/usr/bin/env python3
# Streckenabsprache der Roboter (Issue #120, M1f; Elternissue #114). Ohne ROS, damit testbar.
#
# Jeder Roboter meldet seinen aktuellen und seinen naechsten geplanten Abschnitt. Bei der Wegwahl wird unter den
# ERLAUBTEN Ausfahrten die bevorzugt, die gerade kein anderer Roboter befaehrt oder kuerzlich befahren hat.
#
# Regeln aus dem Issue (Vorschlag, mit M1a zu bestaetigen):
#   - Die Absprache ist nur eine Bevorzugung innerhalb der erlaubten Ausfahrten, nie eine Freigabe.
#     choose_exit() gibt deshalb immer ein Element aus 'allowed' zurueck. Verkehrsregeln, Ampel, Hindernisse und
#     STOPP bleiben unberuehrt.
#   - Keine oder alte Nachrichten (Alter > MAX_AGE_S): Wahl wie bisher allein. Fehlender Empfang loest weder Halt
#     noch Warten aus.
#   - Konflikt (zwei Roboter wollen denselben Abschnitt): kleinere Geraetenummer behaelt ihn.
#   - Abschnitte laufen ueber gemeinsame Knotenkennungen der Strassenkarte (Zieldefinition Abschnitt 9, noch offen).
#
# NOCH NICHT EINGEBUNDEN: line_follower/linie.py waehlt Aeste noch per Kamera (Winkel) und zufaellig; Abschnitts-/
# Knotenkennungen (route.section, route.node, route.allowed_exits) und der Datenaustausch zwischen den Robotern
# (MQTT, M1a) gibt es im laufenden Code noch nicht. Dieses Modul ist die getestete Auswahllogik dafuer.
# UNGETESTET auf Geraeten: MAX_AGE_S und RECENT_WINDOW_S sind Startwerte, keine gemessenen Fachschwellen.
import random
import time
from collections import namedtuple

# Nachricht, die jeder Roboter periodisch sendet.
# current / next_ sind Abschnitte (siehe section()), next_ darf None sein.
# boot_id/seq stammen aus dem Zustandsdatensatz (schemas/grundbetrieb-v1) und
# dienen nur dazu, doppelte/verspaetete Nachrichten zu verwerfen.
Claim = namedtuple("Claim", "robot_id current next_ boot_id seq",
                   defaults=(None, None))

MAX_AGE_S = 3.0        # aeltere Meldungen gelten als "keine Meldung"
RECENT_WINDOW_S = 20.0  # "kuerzlich befahren"

# Strafpunkte: je niedriger, desto bevorzugter die Ausfahrt.
PEN_OCCUPIED = 3   # ein anderer Roboter befaehrt den Abschnitt gerade
PEN_CONFLICT = 2   # ein Roboter mit kleinerer Nummer will ihn auch als naechstes
PEN_RECENT = 1     # ein anderer Roboter war kuerzlich dort


def section(node_a, node_b):
    """Abschnitt als ungerichtetes Knotenpaar (A->B und B->A sind gleich)."""
    return (node_a, node_b) if node_a <= node_b else (node_b, node_a)


class ClaimTable:
    """Merkt sich die zuletzt empfangenen Meldungen der anderen Roboter.

    Zeitstempel sind die EMPFANGSZEITEN der eigenen Uhr (monotonic), damit
    keine Uhrensynchronisation zwischen den Robotern noetig ist.
    """

    def __init__(self, own_id, clock=time.monotonic):
        self.own_id = own_id
        self._clock = clock
        self._latest = {}   # robot_id -> (Claim, empfangen_um)
        self._visited = {}  # abschnitt -> (robot_id, empfangen_um)

    def on_message(self, claim):
        """Beim Empfang einer Meldung aufrufen. Eigene Meldungen ignorieren."""
        if claim.robot_id == self.own_id:
            return
        old = self._latest.get(claim.robot_id)
        if (old is not None and claim.seq is not None
                and old[0].boot_id == claim.boot_id
                and old[0].seq is not None and claim.seq <= old[0].seq):
            return  # doppelt oder ueberholt (gleicher Start, kleinere seq)
        now = self._clock()
        self._latest[claim.robot_id] = (claim, now)
        if claim.current is not None:
            self._visited[claim.current] = (claim.robot_id, now)

    def fresh_claims(self):
        now = self._clock()
        return [c for c, t in self._latest.values() if now - t <= MAX_AGE_S]

    def recently_visited(self, sec):
        entry = self._visited.get(sec)
        return entry is not None and self._clock() - entry[1] <= RECENT_WINDOW_S


def claim_from_state(state, exit_to_section=None):
    """Baut aus einem Zustandsdatensatz (grundbetrieb-v1) eine Claim.

    Gibt None zurueck, wenn der Roboter nicht verlaesslich lokalisiert ist
    oder keinen Abschnitt meldet -> dann wird die Meldung ignoriert.
    exit_to_section(node, exit) uebersetzt die Ausfahrt in einen Abschnitt,
    falls Ausfahrten und Abschnitte unterschiedliche Kennungen haben.
    """
    route = state["route"]
    if route["localization_status"] != "valid" or route["section"] is None:
        return None
    nxt = route["selected_exit"]
    if nxt is not None and exit_to_section is not None:
        nxt = exit_to_section(route["node"], nxt)
    return Claim(state["robot_id"], route["section"], nxt,
                 state["boot_id"], state["seq"])


def _penalty(sec, own_id, fresh, table):
    pen = 0
    for c in fresh:
        if c.current == sec:
            pen = max(pen, PEN_OCCUPIED)
        elif c.next_ == sec and c.robot_id < own_id:
            pen = max(pen, PEN_CONFLICT)
    if pen == 0 and table.recently_visited(sec):
        pen = PEN_RECENT
    return pen


def choose_exit(allowed, table, fallback=random.choice,
                node=None, exit_to_section=None):
    """Waehlt eine Ausfahrt aus `allowed` (Liste von Abschnitten).

    `fallback` waehlt unter gleich guten Kandidaten (bisheriges Verhalten,
    in Tests durch eine deterministische Funktion ersetzbar).
    Sind `allowed` Ausfahrten (nicht Abschnitte), uebersetzt
    exit_to_section(node, ausfahrt) sie fuer den Vergleich; zurueckgegeben
    wird immer das urspruengliche Element aus `allowed`.
    Gibt None zurueck, wenn `allowed` leer ist (dann entscheidet die
    uebrige Fahrlogik, z. B. STOPP/Wenden).
    """
    if not allowed:
        return None
    fresh = table.fresh_claims()
    if not fresh:                      # fehlend oder alt -> wie bisher allein
        return fallback(allowed)
    def sec_of(e):
        return exit_to_section(node, e) if exit_to_section else e

    pens = [(_penalty(sec_of(s), table.own_id, fresh, table), s)
            for s in allowed]
    best = min(p for p, _ in pens)
    return fallback([s for p, s in pens if p == best])


def make_claim(own_id, current, next_):
    """Eigene Meldung zum Senden (aktueller + naechster geplanter Abschnitt)."""
    return Claim(own_id, current, next_)
