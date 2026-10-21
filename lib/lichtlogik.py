#!/usr/bin/env python3
# F1: Lichter des Roboters (Abblendlicht, Blinker links/rechts, Blaulicht) - reine Logik ohne ROS und Hardware.
#
# Eingaben:
#   ki_befehl(befehl, jetzt)  JSON-Befehl der KI-Zentrale (/ki/befehl). Faehrt die KI ein Manoever mit Drehung
#                             oder Querfahrt (Wenden, Ausweichen, Zuruecksetzen), blinkt der Blinker in diese Richtung.
#   kommando(text, jetzt)     Handbefehl (/lichter/kommando), z. B. 'blaulicht an', 'blinker links', 'warnblinker an'.
# Ausgabe:
#   zustand(jetzt)            {'abblendlicht', 'blinker', 'blinker_an', 'blaulicht', 'blaulicht_links_an', 'leiste'}
#                             'leiste' = Farbe jeder LED der vorderen LED-Leiste [(r, g, b), ...]
#
# Richtungen wie in ROS (REP 103): dreh > 0 = gegen den Uhrzeigersinn = links, quer > 0 = nach links.
# Takt Blinker: 1,5 Hz (StVZO/ECE R6: 90 +- 30 Takte pro Minute), Hell-Dunkel 50 %.
#
# NICHT enthalten: Wie die LED-Leiste am M3 Pro angesteuert wird (Topic/Nachrichtentyp der Yahboom-Platine) ist
# noch nicht am Roboter festgestellt. Das macht lichter/lichter.py ueber einen austauschbaren Ausgang.
import math

STANDARD = {
    'anzahl_leds': 14,                 # LEDs der vorderen Leiste - AM ROBOTER NACHZAEHLEN
    'blinker_links': [0, 1],           # Index 0 = linke Seite? AM ROBOTER PRUEFEN (Panel/Testbefehl)
    'blinker_rechts': [12, 13],
    'abblendlicht_immer': True,        # Abblendlicht leuchtet, solange die Lichtsteuerung laeuft
    'blink_hz': 1.5,
    'blaulicht_hz': 2.5,               # Wechsel links/rechts pro Sekunde (ein Takt = beide Haelften einmal)
    'ki_max_alter_s': 0.6,             # aelter: Befehl gilt als ausgefallen (wie im Linienfolger)
    'dreh_schwelle': 0.15,             # rad/s, darunter kein Blinker (Lenkkorrekturen)
    'quer_schwelle': 0.03,             # m/s
    'nachlauf_s': 1.0,                 # Blinker so lange nach Manoeverende weiter (kein Flackern)
    'farbe_abblend': [255, 255, 255],
    'farbe_blinker': [255, 120, 0],
    'farbe_blaulicht': [0, 0, 255],
    'farbe_aus': [0, 0, 0],
}

BLINKER = (None, 'links', 'rechts', 'warn')


def richtung_aus_manoever(manoever, dreh_schwelle, quer_schwelle):
    """'links' | 'rechts' | None aus {'lin', 'quer', 'dreh'} der KI. Drehung hat Vorrang vor Querfahrt."""
    if not isinstance(manoever, dict):
        return None

    def zahl(name):
        try:
            w = float(manoever.get(name) or 0.0)
        except (TypeError, ValueError):
            return 0.0
        return w if math.isfinite(w) else 0.0

    dreh, quer = zahl('dreh'), zahl('quer')
    if abs(dreh) >= dreh_schwelle:
        return 'links' if dreh > 0 else 'rechts'
    if abs(quer) >= quer_schwelle:
        return 'links' if quer > 0 else 'rechts'
    return None


class Lichter:
    def __init__(self, einstellungen=None):
        self.e = dict(STANDARD)
        self.e.update(einstellungen or {})
        n = int(self.e['anzahl_leds'])
        if n < 1:
            raise ValueError('anzahl_leds muss mindestens 1 sein')
        for name in ('blinker_links', 'blinker_rechts'):
            if any(not 0 <= int(i) < n for i in self.e[name]):
                raise ValueError(f'{name}: LED-Nummer ausserhalb 0..{n - 1}')
        if set(self.e['blinker_links']) & set(self.e['blinker_rechts']):
            raise ValueError('blinker_links und blinker_rechts duerfen keine LED gemeinsam haben')
        for name in ('blink_hz', 'blaulicht_hz'):
            if not float(self.e[name]) > 0:
                raise ValueError(f'{name} muss groesser als 0 sein')
        self.abblendlicht = bool(self.e['abblendlicht_immer'])
        self.blaulicht = False
        self.blaulicht_seit = 0.0
        self.hand_blinker = None          # per Kommando gesetzt, gilt bis 'blinker aus'
        self.ki_zeit = None
        self.ki_richtung = None
        self.ki_richtung_bis = None       # Nachlauf
        self.blinker_jetzt = None
        self.blinker_seit = 0.0

    # ---------- Eingaben ----------
    def ki_befehl(self, befehl, jetzt):
        self.ki_zeit = jetzt
        richtung = None
        if isinstance(befehl, dict) and befehl.get('aktion') == 'manoever':
            richtung = richtung_aus_manoever(befehl.get('manoever'), float(self.e['dreh_schwelle']),
                                             float(self.e['quer_schwelle']))
        if richtung is not None:
            self.ki_richtung = richtung
            self.ki_richtung_bis = None
        elif self.ki_richtung is not None and self.ki_richtung_bis is None:
            self.ki_richtung_bis = jetzt + float(self.e['nachlauf_s'])

    def kommando(self, text, jetzt):
        """Gibt True zurueck, wenn das Kommando bekannt war."""
        worte = str(text).strip().lower().split()
        if len(worte) != 2:
            return False
        was, wert = worte
        if was == 'blaulicht' and wert in ('an', 'aus'):
            if wert == 'an' and not self.blaulicht:
                self.blaulicht_seit = jetzt
            self.blaulicht = wert == 'an'
        elif was == 'abblendlicht' and wert in ('an', 'aus'):
            self.abblendlicht = wert == 'an'
        elif was == 'blinker' and wert in ('links', 'rechts', 'aus'):
            self.hand_blinker = None if wert == 'aus' else wert
        elif was == 'warnblinker' and wert in ('an', 'aus'):
            self.hand_blinker = 'warn' if wert == 'an' else None
        else:
            return False
        return True

    # ---------- Ausgabe ----------
    def _ki_richtung(self, jetzt):
        if self.ki_zeit is None or jetzt - self.ki_zeit > float(self.e['ki_max_alter_s']):
            self.ki_richtung = self.ki_richtung_bis = None   # KI weg: kein Blinker aus altem Befehl
            return None
        if self.ki_richtung_bis is not None and jetzt >= self.ki_richtung_bis:
            self.ki_richtung = self.ki_richtung_bis = None
        return self.ki_richtung

    def zustand(self, jetzt):
        blinker = self.hand_blinker or self._ki_richtung(jetzt)
        if blinker != self.blinker_jetzt:      # neuer Blinker beginnt sofort hell
            self.blinker_jetzt, self.blinker_seit = blinker, jetzt
        periode = 1.0 / float(self.e['blink_hz'])
        blinker_an = blinker is not None and ((jetzt - self.blinker_seit) % periode) < periode / 2
        b_periode = 1.0 / float(self.e['blaulicht_hz'])
        blau_links = self.blaulicht and ((jetzt - self.blaulicht_seit) % b_periode) < b_periode / 2
        z = {'abblendlicht': self.abblendlicht, 'blinker': blinker, 'blinker_an': blinker_an,
             'blaulicht': self.blaulicht, 'blaulicht_links_an': blau_links}
        z['leiste'] = self.leiste(z)
        return z

    def leiste(self, z):
        e = self.e
        n = int(e['anzahl_leds'])
        aus = tuple(e['farbe_aus'])
        links, rechts = set(e['blinker_links']), set(e['blinker_rechts'])
        mitte = [i for i in range(n) if i not in links and i not in rechts]
        farben = [aus] * n
        if z['abblendlicht']:
            for i in mitte:
                farben[i] = tuple(e['farbe_abblend'])
        if z['blaulicht'] and mitte:
            haelfte = len(mitte) // 2 or 1
            an = mitte[:haelfte] if z['blaulicht_links_an'] else mitte[haelfte:]
            for i in mitte:                  # Blaulicht ersetzt das Abblendlicht in der Mitte
                farben[i] = tuple(e['farbe_blaulicht']) if i in an else aus
        if z['blinker_an']:
            seiten = {'links': links, 'rechts': rechts, 'warn': links | rechts}[z['blinker']]
            for i in seiten:
                farben[i] = tuple(e['farbe_blinker'])
        return farben
