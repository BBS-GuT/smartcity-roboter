#!/usr/bin/env python3
"""RM02 22.10.: In Greifweite (33 cm) ruckelte er 15 s lang zwischen "schaue hin" (STOPP) und "fahre", ohne voran zu
kommen, dann "in Greifweite fahren dauert zu lange".

- Einzelne Bilder ohne Treffer (verrauschte Tiefe) hielten ihn jedes Mal an und setzten Seitwaerts/Drehen auf 0.
- Kleine Korrekturen (unter ca. 2 cm/s) bewegen die Motoren kaum (Totzone, hier angenommen: nicht gemessen).
- Ein einzelner Ausreisser in der Messung setzte "ruhig" zurueck.

Echter Entscheider, kuenstliche Uhr, Planerstub. Kein ROS, kein Geraet.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
from raeum_lauf import Lauf  # noqa: E402
from entscheider import STANDARD  # noqa: E402

GREIF = STANDARD['greif_vor']
TOTZONE_LIN, TOTZONE_QUER = 0.014, 0.018      # darunter bewegt sich der Welt-Roboter nicht (Annahme)


class Welt:
    """Wuerfel liegt fest bei (x, y); jedes 'luecke'-te Bild liefert keinen Treffer, Ausreisser verfaelschen eins."""

    def __init__(self, x, y, luecke=2, ausreisser=None):
        self.lauf = Lauf()
        self.x, self.y = x, y
        self.luecke, self.ausreisser = luecke, ausreisser or {}
        self.n = 0
        self.quer_strecke = 0.0
        self.aktionen = []

    def schritt(self):
        m = (self.lauf.letzter or {}).get('manoever') or {}
        q = m.get('quer', 0.0)
        if abs(q) >= TOTZONE_QUER:
            self.quer_strecke += q * 0.1
        if 0 < abs(m.get('lin', 0.0)) < TOTZONE_LIN:      # Lauf zaehlt lin immer; Totzone wieder abziehen
            self.lauf.strecke -= m['lin'] * 0.1
        self.n += 1
        obj = None
        if not (self.luecke and self.n % self.luecke == 0):
            obj = {'vor': self.x - self.lauf.strecke, 'seite': self.y - self.quer_strecke, 'breite': 0.03,
                   'hoehe': 0.05, 'quelle': 'tiefe'}
            obj.update(self.ausreisser.get(self.n, {}))
        b = self.lauf.schritt(objekt=obj, tiefe_hindernis=obj is not None)
        self.aktionen.append((self.lauf.phase(), b['aktion'], b['grund']))
        return b

    def texte(self):
        return [t for _, t, _ in self.lauf.e.ereignisse]

    def bis_planen(self, schritte=300):
        for _ in range(schritte):
            self.schritt()
            if self.lauf.phase() not in (None, 'anschauen', 'vorpruefen', 'abstand'):
                return self.lauf.phase()
        return self.lauf.phase()


class Positionieren(unittest.TestCase):
    def test_luecken_und_kleiner_seitenversatz(self):
        """In Greifweite, 3 cm seitlich, jedes zweite Bild ohne Treffer: richtet sich aus und plant."""
        w = Welt(GREIF + 0.005, 0.03, luecke=2)
        phase = w.bis_planen()
        self.assertIn(phase, ('planen', 'ausfuehren'), w.aktionen[-6:])
        self.assertFalse(any('dauert zu lange' in t for t in w.texte()), w.texte())
        abstand = [a for p, a, g in w.aktionen if p == 'abstand']
        # kein Ruckeln: waehrend er seitlich korrigiert, schickt er nicht jedes zweite Mal STOPP
        self.assertLess(abstand.count('stopp'), 3, w.aktionen)

    def test_kleiner_abstandsfehler_ueberwindet_totzone(self):
        w = Welt(GREIF + 0.022, 0.0, luecke=0)         # 2,2 cm zu weit: vorher 1,3 cm/s befohlen
        w.lauf.e.c['tiefe_halt'] = GREIF + 0.10       # haelt schon weiter weg an (Start ausserhalb Greifweite)
        self.assertIn(w.bis_planen(), ('planen', 'ausfuehren'), w.aktionen[-6:])

    def test_einzelner_ausreisser_setzt_nicht_zurueck(self):
        """Jedes dritte Bild ein Ausreisser (5 cm seitlich): Median der letzten 3 bleibt ruhig."""
        w = Welt(GREIF, 0.0, luecke=0, ausreisser={n: {'seite': 0.05} for n in range(0, 300, 3)})
        self.assertIn(w.bis_planen(), ('planen', 'ausfuehren'), w.aktionen[-6:])

    def test_lange_luecke_haelt_an(self):
        """Laenger als greif_luecke kein Treffer: nicht blind weiterdrehen/-schieben."""
        w = Welt(GREIF + 0.005, 0.03, luecke=0)
        for _ in range(200):
            w.schritt()
            if w.lauf.phase() == 'abstand' and any((w.lauf.letzter.get('manoever') or {}).get(k) for k in ('quer',)):
                break
        self.assertEqual(w.lauf.phase(), 'abstand')
        w.luecke = 1                                     # ab jetzt nie mehr gesehen
        quer = []
        for _ in range(int(STANDARD['greif_luecke'] / 0.1) + 3):
            b = w.schritt()
            quer.append(((b.get('manoever') or {}).get('quer', 0.0)))
        self.assertEqual(quer[-1], 0.0, quer)


if __name__ == '__main__':
    unittest.main(verbosity=2)
