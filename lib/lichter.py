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
#      Entprellt: die Richtung muss 'bestaetigen' s lang gleich bleiben (vor Kreuzungen sieht die Kamera mehrere
#      Aeste, der Knick springt dann links/rechts, RM02 21.10.), ein Wechsel der Seite sogar 'wechsel' s.
#   Nach dem Abbiegen blinkt er noch 'nachlauf' s weiter, mindestens 'mindest' s (kein Flackern).
#
# Ergebnis: zustand() -> {'abblend', 'blinker': None | 'links' | 'rechts', 'blink_an', 'grund', 'leds'}
#   leds = Farben der vorderen LED-Leiste [(r, g, b), ...] von links nach rechts
#
# LED-Leiste am Board (RM02, ~/rgb_zuordnung.txt): Topic /rgb, std_msgs/ColorRGBA. Feld a waehlt die LED
# (0 = alle, 1..8 = eine LED), r/g/b = Farbe. a ab 100 = fertige Effekte des Gamepads (nutzen wir nicht).
# rgb_befehle() rechnet aus, welche Nachrichten noetig sind (nur geaenderte LEDs, das Board haengt am micro-ROS).
import math

STANDARD = {
    'kurve_grad': 60.0,      # Abknicken der Linie voraus (Grad), ab dem geblinkt wird (0 = nie wegen Linie)
    'manoever_dreh': 0.3,    # KI-Manoever dreht schneller als das (rad/s) -> blinken
    'nachlauf': 1.0,         # s weiterblinken, wenn der Grund weg ist
    'mindest': 2.0,          # s blinkt er mindestens
    'bestaetigen': 0.5,      # s muss die Linie gleich abknicken, bevor er blinkt
    'wechsel': 1.5,          # s muss sie zur anderen Seite abknicken, bevor der Blinker die Seite wechselt
    'takt_hz': 1.5,          # Blinkfrequenz (StVO: 1,5 Hz +- 0,5)
    'leds': 8,               # LEDs der Leiste (a = 1..8, ~/rgb_zuordnung.txt)
    'blink_leds': 2,         # davon je Seite fuer den Blinker
    'links_zuerst': False,   # LED 1 sitzt links (in Fahrtrichtung)? RM02 21.10.: LED 1 sitzt RECHTS
}
WEISS, GELB, AUS = (90, 90, 90), (255, 140, 0), (0, 0, 0)


def knick(weg):
    """Richtung (rad, + = links) der Linie ca. 70-80 cm voraus, gemessen gegen die eigene Fahrtrichtung, oder None.
    weg: [(x vorne, y links), ...] vom Linienfolger. Bewusst NICHT gegen das erste Linienstueck am Roboter: direkt
    nach dem Abbiegen liegen dort noch Reste der Ecke, dann sah die gerade Strecke wie ein Rechtsknick aus und
    er blinkte nach dem Linksabbiegen rechts (RM02 22.10.)."""
    vorne = [p for p in (weg or []) if p[0] > 0.03]
    if len(vorne) < 3:
        return None
    (x2, y2), (x3, y3) = vorne[-3], vorne[-1]
    if math.hypot(x3 - x2, y3 - y2) < 0.03:
        return None
    return math.atan2(y3 - y2, x3 - x2)


def rgb_befehle(alt, neu, links_zuerst=True):
    """Noetige Nachrichten fuer die Leiste: [(a, (r, g, b)), ...]. alt = zuletzt gesendet oder None (alles senden).
    neu von links nach rechts; a = Nummer der LED am Board (1..n), 0 = alle gleich."""
    n = len(neu)
    if alt is None or len(alt) != n:
        if len(set(neu)) == 1:
            return [(0, neu[0])]
        alt = [None] * n
    aus = []
    for i, (vorher, farbe) in enumerate(zip(alt, neu)):
        if vorher != farbe:
            aus.append((i + 1 if links_zuerst else n - i, farbe))
    return aus


class Lichter:
    def __init__(self, cfg=None):
        self.c = dict(STANDARD, **(cfg or {}))
        self.abblend = False
        self.blinker = None
        self.grund = ''
        self.seit = 0.0          # Blinker an seit
        self.zuletzt = 0.0       # Grund zuletzt gesehen
        self.jetzt = 0.0
        self.kandidat, self.kandidat_seit = None, 0.0   # Richtung der Linie, noch nicht bestaetigt
        self.kandidat_wechsel = False   # Kandidat kam, waehrend die andere Seite blinkte -> 'wechsel' abwarten

    def ausloeser(self, lf, ki):
        """(Richtung, Grund) oder (None, '') aus Linienfolger-Status und KI-Befehl (je dict oder None).
        KI-Vorgabe und Manoever gelten sofort, die Linie erst, wenn sie lange genug gleich abknickt."""
        if ki:
            if ki.get('blinker') in ('links', 'rechts'):
                return ki['blinker'], 'KI biegt ab'
            m = ki.get('manoever') if ki.get('aktion') == 'manoever' else None
            if m and abs(float(m.get('dreh', 0.0))) > self.c['manoever_dreh']:
                return ('links' if float(m['dreh']) > 0 else 'rechts'), 'Manoever: ' + str(m.get('text', 'drehen'))
        richtung, grund = None, ''
        if lf and self.c['kurve_grad'] > 0:
            k = knick(lf.get('weg'))
            if k is not None and abs(math.degrees(k)) >= self.c['kurve_grad']:
                richtung, grund = ('links' if k > 0 else 'rechts'), f'Linie knickt {abs(math.degrees(k)):.0f} Grad ab'
        if richtung != self.kandidat:
            self.kandidat, self.kandidat_seit = richtung, self.jetzt
            self.kandidat_wechsel = self.blinker is not None and richtung != self.blinker
        if richtung is None or richtung == self.blinker:
            return richtung, grund
        # Auch wenn die alte Seite inzwischen (Nachlauf) ausgegangen ist: ein Seitenwechsel bleibt ein Wechsel
        noetig = self.c['wechsel'] if self.blinker or self.kandidat_wechsel else self.c['bestaetigen']
        return (richtung, grund) if self.jetzt - self.kandidat_seit >= noetig else (None, '')

    def schritt(self, jetzt, lf, ki):
        """lf/ki: neueste Meldung (dict) oder None, wenn das Programm nicht laeuft/zu alt."""
        self.jetzt = jetzt
        richtung, grund = self.ausloeser(lf, ki) if lf else (None, '')   # ohne Linienfolger faehrt nichts
        if not lf:
            self.kandidat = None    # nach einem Ausfall wieder volle 'bestaetigen' s mit frischen Meldungen abwarten
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
