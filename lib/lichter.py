#!/usr/bin/env python3
# Abblendlicht und Blinker (ohne ROS, das Panel rechnet damit 10x pro Sekunde).
#
# Abblendlicht: an/aus von Hand im Panel (Dashboard). START schaltet es VOR dem Losfahren ein.
#
# Blinker (links/rechts), in dieser Reihenfolge:
#   1. die KI sagt ausdruecklich, wohin sie abbiegt: Befehl {'blinker': 'links' | 'rechts'}
#      (fuer die spaetere Wegwahl an Kreuzungen K1-K8, gibt es noch nicht)
#   2. KI-Manoever mit Drehung, z. B. Wenden (Drehrichtung = Blinkrichtung)
#   3. Linie vor dem Roboter knickt stark ab (Linien-Gedaechtnis, 'weg' vom Linienfolger):
#      ab 'kurve_grad' Richtungsaenderung auf den naechsten ca. 80 cm = Abbiegen an einer Ecke.
#      Normale (sanfte) Kurven blinken NICHT, wie im echten Verkehr.
#   Nach dem Abbiegen blinkt er noch 'nachlauf' s weiter, mindestens 'mindest' s (kein Flackern).
#
# Ergebnis: zustand() -> {'abblend', 'blinker': None | 'links' | 'rechts', 'blink_an', 'grund', 'leds'}
#   leds = Farben der vorderen LED-Leiste [(r, g, b), ...] von links nach rechts (fuer den Leisten-Treiber)
import math

STANDARD = {
    'kurve_grad': 60.0,      # Abknicken der Linie voraus (Grad), ab dem geblinkt wird (0 = nie wegen Linie)
    'manoever_dreh': 0.3,    # KI-Manoever dreht schneller als das (rad/s) -> blinken
    'nachlauf': 1.0,         # s weiterblinken, wenn der Grund weg ist
    'mindest': 2.0,          # s blinkt er mindestens
    'takt_hz': 1.5,          # Blinkfrequenz (StVO: 1,5 Hz +- 0,5)
    'leds': 14,              # LEDs der vorderen Leiste (NOCH NICHT AM ROBOTER GEPRUEFT)
    'blink_leds': 3,         # davon je Seite fuer den Blinker
}
WEISS, GELB, AUS = (90, 90, 90), (255, 140, 0), (0, 0, 0)


def knick(weg):
    """Richtungsaenderung (rad, + = links) der Linie vor dem Roboter aus [(x vorne, y links), ...] oder None."""
    if not weg or len(weg) < 4:
        return None
    (x0, y0), (x1, y1) = weg[0], weg[2]
    (x2, y2), (x3, y3) = weg[-3], weg[-1]
    if math.hypot(x1 - x0, y1 - y0) < 0.03 or math.hypot(x3 - x2, y3 - y2) < 0.03:
        return None
    d = math.atan2(y3 - y2, x3 - x2) - math.atan2(y1 - y0, x1 - x0)
    return (d + math.pi) % (2 * math.pi) - math.pi


class Lichter:
    def __init__(self, cfg=None):
        self.c = dict(STANDARD, **(cfg or {}))
        self.abblend = False
        self.blinker = None
        self.grund = ''
        self.seit = 0.0          # Blinker an seit
        self.zuletzt = 0.0       # Grund zuletzt gesehen
        self.jetzt = 0.0

    def ausloeser(self, lf, ki):
        """(Richtung, Grund) oder (None, '') aus Linienfolger-Status und KI-Befehl (je dict oder None)."""
        if ki:
            if ki.get('blinker') in ('links', 'rechts'):
                return ki['blinker'], 'KI biegt ab'
            m = ki.get('manoever') if ki.get('aktion') == 'manoever' else None
            if m and abs(float(m.get('dreh', 0.0))) > self.c['manoever_dreh']:
                return ('links' if float(m['dreh']) > 0 else 'rechts'), 'Manoever: ' + str(m.get('text', 'drehen'))
        if lf and self.c['kurve_grad'] > 0:
            k = knick(lf.get('weg'))
            if k is not None and abs(math.degrees(k)) >= self.c['kurve_grad']:
                return ('links' if k > 0 else 'rechts'), f'Linie knickt {abs(math.degrees(k)):.0f} Grad ab'
        return None, ''

    def schritt(self, jetzt, lf, ki):
        """lf/ki: neueste Meldung (dict) oder None, wenn das Programm nicht laeuft/zu alt."""
        self.jetzt = jetzt
        richtung, grund = self.ausloeser(lf, ki) if lf else (None, '')   # ohne Linienfolger faehrt nichts
        if richtung:
            if richtung != self.blinker:
                self.blinker, self.seit = richtung, jetzt
            self.grund, self.zuletzt = grund, jetzt
        elif self.blinker and (not lf or (jetzt - self.zuletzt > self.c['nachlauf']
                                          and jetzt - self.seit > self.c['mindest'])):
            self.blinker, self.grund = None, ''
        return self.zustand()

    def blink_an(self):
        """Leuchtet der Blinker gerade (Hell-Phase)?"""
        return bool(self.blinker) and ((self.jetzt - self.seit) * self.c['takt_hz']) % 1.0 < 0.5

    def leds(self):
        n, b = int(self.c['leds']), int(self.c['blink_leds'])
        grund = WEISS if self.abblend else AUS
        farben = [grund] * n
        if self.blink_an():
            seite = range(b) if self.blinker == 'links' else range(n - b, n)
            for i in seite:
                farben[i] = GELB
        return farben

    def zustand(self):
        return {'abblend': self.abblend, 'blinker': self.blinker, 'blink_an': self.blink_an(),
                'grund': self.grund, 'leds': self.leds()}
