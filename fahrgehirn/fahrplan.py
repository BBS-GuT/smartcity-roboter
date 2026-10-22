#!/usr/bin/env python3
# Fahrplan: welche Richtung an welcher Kreuzung (statt Zufall wie im Grundbetrieb).
#
# Eine Runde = der Fahrplan einmal ganz durchfahren, z. B. ['links', 'rechts', 'geradeaus'].
# Weil die Wunschrichtung vorher feststeht, kann man messen, ob eine Kreuzung geklappt hat.
#
# Richtungen der Aeste kommen von line_follower/linie.py (LinienSucher.aeste) in rad: 0 = geradeaus, + = links.
import math

RICHTUNGEN = ('links', 'geradeaus', 'rechts')
ZIEL_GRAD = {'links': 90.0, 'geradeaus': 0.0, 'rechts': -90.0}
GERADEAUS_GRAD = 30.0     # Ast innerhalb +-30 Grad = geradeaus, sonst links/rechts (wie line_follower.py)
ABBIEGE_GRAD = 45.0       # gefahrene Richtung: Drehung ueber die Kreuzung mehr als 45 Grad = abgebogen


def richtung_aus_ast(grad):
    """Richtung eines Astes (Grad, + = links) -> 'links' / 'geradeaus' / 'rechts'."""
    if grad > GERADEAUS_GRAD:
        return 'links'
    if grad < -GERADEAUS_GRAD:
        return 'rechts'
    return 'geradeaus'


def richtung_aus_drehung(grad):
    """Wie weit hat sich der Roboter ueber die Kreuzung gedreht (Grad, + = links)? -> gefahrene Richtung."""
    if grad > ABBIEGE_GRAD:
        return 'links'
    if grad < -ABBIEGE_GRAD:
        return 'rechts'
    return 'geradeaus'


def plan_aus_text(text):
    """'links, geradeaus, rechts' oder Liste -> geprueftes Tupel. Leere oder falsche Eintraege -> ValueError."""
    teile = text.replace(';', ',').split(',') if isinstance(text, str) else list(text)
    plan = tuple(str(t).strip().lower() for t in teile if str(t).strip())
    falsch = [t for t in plan if t not in RICHTUNGEN]
    if not plan or falsch:
        raise ValueError(f'Fahrplan ungueltig: {falsch or "leer"} (erlaubt: {", ".join(RICHTUNGEN)})')
    return plan


class Fahrplan:
    def __init__(self, plan, index=0):
        self.plan = plan_aus_text(plan)
        self.index = int(index) % len(self.plan)

    @property
    def aktuell(self):
        """Gewuenschte Richtung an der naechsten Kreuzung."""
        return self.plan[self.index]

    def weiter(self):
        """Naechste Kreuzung. Rueckgabe True, wenn damit eine Runde (der ganze Plan) fertig ist."""
        self.index = (self.index + 1) % len(self.plan)
        return self.index == 0

    def ast_waehlen(self, richtungen):
        """richtungen: Aeste dieser Kreuzung (rad). Rueckgabe: der Ast, der am besten zur Wunschrichtung passt,
        oder None, wenn kein Ast in diese Richtung fuehrt (z. B. noch nicht im Bild)."""
        wunsch = self.aktuell
        passend = [r for r in richtungen if richtung_aus_ast(math.degrees(r)) == wunsch]
        if not passend:
            return None
        return min(passend, key=lambda r: abs(math.degrees(r) - ZIEL_GRAD[wunsch]))

    @staticmethod
    def naechster_ast(richtungen, wunsch):
        """Notloesung: Ast, der der Wunschrichtung am naechsten kommt (wenn sie nicht vorhanden ist)."""
        return min(richtungen, key=lambda r: abs(math.degrees(r) - ZIEL_GRAD[wunsch]))
