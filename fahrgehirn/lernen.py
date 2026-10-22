#!/usr/bin/env python3
# Lernen der Fahrparameter (ohne ROS, damit testbar).
#
# Verfahren: schrittweise Parameteroptimierung mit Fehlerdiagnose ("Champion gegen Herausforderer").
#   1. Der Champion ist der beste bisher bekannte Parametersatz. Er faehrt Kontrollrunden.
#   2. Die Diagnose (fahrgehirn/messung.py) sagt, WOMIT es zuletzt am meisten scheiterte, z. B. "Kreuzung nicht
#      erkannt". Zu jedem Fehler gehoeren die Parameter, die ihn beeinflussen (GRUPPEN). Davon wird EINER um einen
#      Schritt veraendert (Herausforderer). Nur einer: dann weiss man, was gewirkt hat.
#   3. Der Herausforderer faehrt RUNDEN_JE_VERSUCH Runden. Ist seine mittlere Wertung um mindestens VORSPRUNG
#      besser als die der letzten Champion-Runden, wird er neuer Champion. Sonst bleibt der alte.
#   4. Schrittweite je Parameter passt sich an: Erfolg -> groesser (x1,5), Misserfolg -> kleiner (x0,6) und naechstes
#      Mal in die andere Richtung. So tastet er sich an das Optimum heran.
# Warum nicht ein Bandit wie beim Greifen (lib/greifen.py)? Dort gibt es 3 Werte und einen klaren Treffer/Daneben.
# Hier sind es 7 Parameter, und eine Runde liefert viele Messwerte (Abweichung, Kreuzungen, Zeit). Ein Gitter ueber
# 7 Parameter waere riesig (Millionen Kombinationen) - einen Parameter nach dem anderen zu verbessern braucht wenige
# Runden, ist nachvollziehbar (jede Aenderung steht im Protokoll) und bleibt immer innerhalb der GRENZEN.
#
# Sicherheit: Jeder Wert bleibt in [min, max] (auch wenn jemand die Datei von Hand aendert: beim Laden begrenzt).
# Die Hindernis-Regel (fahrgehirn/sicherheit.py) und die LiDAR-Notbremse sind KEINE Lernparameter.
#
# Speichern: nach jeder Runde und jeder Kreuzung atomar (erst <datei>.neu schreiben, dann umbenennen: bei
# Stromausfall bleibt die alte Datei ganz). Ort: config/lokal/fahrgehirn.json (nicht im Repository).
# Zuruecksetzen nur bewusst: scripts/fahrgehirn_zuruecksetzen.sh (legt vorher eine Sicherung an).
import copy
import json
import os
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LERNSTAND = os.environ.get('SMARTCITY_FAHRGEHIRN', os.path.join(REPO, 'config', 'lokal', 'fahrgehirn.json'))
VERSION = 1

# Gelernte Parameter: Startwert, Grenzen (nie darueber hinaus), Startschrittweite, Erklaerung.
# Die Namen der Linien-Parameter sind die aus line_follower/linie.py (STANDARD).
PARAMETER = {
    'speed':          {'start': 0.15, 'min': 0.10, 'max': 0.25, 'schritt': 0.03,
                       'text': 'Grundtempo auf der Geraden (m/s)'},
    'kreuzung_tempo': {'start': 0.70, 'min': 0.30, 'max': 1.00, 'schritt': 0.10,
                       'text': 'Tempo-Faktor von "Kreuzung erkannt" bis "Kreuzung durchfahren"'},
    'regel_abstand':  {'start': 44.0, 'min': 20.0, 'max': 80.0, 'schritt': 6.0,
                       'text': 'Lenkverstaerkung seitlicher Abstand zur Linie (1/m^2)'},
    'regel_richtung': {'start': 13.0, 'min': 6.0, 'max': 22.0, 'schritt': 2.0,
                       'text': 'Lenkverstaerkung Richtung zur Linie (1/m), daempft das Pendeln'},
    'quer_beschl':    {'start': 0.15, 'min': 0.08, 'max': 0.25, 'schritt': 0.02,
                       'text': 'Vorausschau-Bremse: hoechste Fliehkraft vor und in Kurven (m/s^2)'},
    'ast_min':        {'start': 0.05, 'min': 0.03, 'max': 0.10, 'schritt': 0.01,
                       'text': 'Kreuzungserkennung: so lang (m) muss ein Abzweig zu sehen sein'},
    'threshold':      {'start': 70, 'min': 45, 'max': 100, 'schritt': 6,
                       'text': 'Kreuzungs-/Linienerkennung: dunkler als das = Linie (0-255)'},
}
GANZZAHL = {'threshold'}

# Fehlerart (aus der Diagnose) -> Parameter, die daran etwas aendern koennen
GRUPPEN = {
    'kreuzung_nicht_erkannt': ['ast_min', 'threshold', 'kreuzung_tempo', 'speed'],
    'falsch_abgebogen':       ['kreuzung_tempo', 'regel_richtung', 'regel_abstand', 'speed'],
    'linie_verloren':         ['speed', 'quer_beschl', 'regel_abstand', 'kreuzung_tempo', 'threshold'],
    'pendeln':                ['regel_richtung', 'regel_abstand', 'speed'],
    'abweichung':             ['regel_abstand', 'regel_richtung', 'quer_beschl', 'speed'],
    'langsam':                ['speed', 'kreuzung_tempo', 'quer_beschl'],   # alles klappt -> schneller werden
}
RUNDEN_JE_VERSUCH = 2      # so viele Runden faehrt ein Herausforderer
KONTROLLRUNDEN = 1         # danach so viele Runden der Champion (misst ihn unter gleichen Bedingungen nach)
VORSPRUNG = 0.5            # so viele Wertungspunkte muss der Herausforderer besser sein (gegen Zufallstreffer)
CHAMPION_FENSTER = 4       # Wertung des Champions = Mittel seiner letzten so vielen Runden
SCHRITT_MIN, SCHRITT_MAX = 0.25, 2.0   # Schrittweite: Vielfaches des Startschritts


def begrenzen(name, wert):
    p = PARAMETER[name]
    wert = min(p['max'], max(p['min'], float(wert)))
    return int(round(wert)) if name in GANZZAHL else round(wert, 4)


def startwerte():
    return {n: begrenzen(n, p['start']) for n, p in PARAMETER.items()}


def leerer_lernstand():
    return {
        'version': VERSION,
        'champion': startwerte(),
        'champion_wertungen': [],          # Wertungen der letzten Champion-Runden
        'kandidat': None,                  # {'parameter', 'name', 'richtung', 'wertungen'} oder None
        'phase': 'champion',               # 'champion' (Kontrollrunde) oder 'kandidat'
        'kontrolle_offen': KONTROLLRUNDEN,
        'schritt': {n: 1.0 for n in PARAMETER},      # Faktor auf den Startschritt
        'richtung': {n: 1 for n in PARAMETER},       # naechster Versuch: +1 groesser, -1 kleiner
        'reihum': {g: 0 for g in GRUPPEN},           # welcher Parameter der Gruppe als naechstes
        'versuche': [],                    # Protokoll der letzten 200 Versuche
        'runden_gesamt': 0,                # gewertete Runden
        'runden_alle': 0,                  # alle Runden (auch nicht gewertete, z. B. nach Neustart)
        'fahrplan_index': 0,
        'strecken': {},                    # Plan-Position -> gemessene Strecken (m) von der vorigen Kreuzung
        'aktualisiert': None,
    }


class Lernen:
    def __init__(self, pfad=LERNSTAND, log=print):
        self.pfad = pfad
        self.log = log
        self.stand = self.laden()

    # ---------------- Speichern / Laden ----------------
    def laden(self):
        """Gelerntes laden. Fehlt die Datei: Startwerte. Kaputte Datei: NICHT ueberschreiben, Startwerte nutzen und
        die Datei beiseitelegen (.kaputt), damit nichts unbemerkt verloren geht."""
        stand = leerer_lernstand()
        try:
            with open(self.pfad) as f:
                gelesen = json.load(f)
        except FileNotFoundError:
            self.log(f'Fahr-Gehirn: noch nichts gelernt ({self.pfad} fehlt) -> Startwerte')
            return stand
        except (OSError, ValueError) as e:
            ziel = self.pfad + '.kaputt'
            try:
                os.replace(self.pfad, ziel)
            except OSError:
                pass
            self.log(f'Fahr-Gehirn: Lernstand unlesbar ({e}) -> nach {ziel} verschoben, Startwerte')
            return stand
        for k in stand:
            if k in gelesen:
                stand[k] = gelesen[k]
        # Grenzen gelten immer, auch fuer von Hand geaenderte Dateien; unbekannte Parameter fallen weg
        stand['champion'] = {n: begrenzen(n, stand['champion'].get(n, PARAMETER[n]['start'])) for n in PARAMETER}
        if stand['kandidat']:
            k = stand['kandidat']
            k['parameter'] = {n: begrenzen(n, k['parameter'].get(n, stand['champion'][n])) for n in PARAMETER}
        for n in PARAMETER:
            stand['schritt'][n] = min(SCHRITT_MAX, max(SCHRITT_MIN, float(stand['schritt'].get(n, 1.0))))
            stand['richtung'][n] = 1 if stand['richtung'].get(n, 1) >= 0 else -1
        for g in GRUPPEN:
            stand['reihum'].setdefault(g, 0)
        self.log(f"Fahr-Gehirn: Lernstand geladen ({stand['runden_gesamt']} Runden, {len(stand['versuche'])} Versuche)")
        return stand

    def speichern(self):
        """Atomar: erst ganz in <pfad>.neu schreiben, dann umbenennen (nie eine halbe Datei)."""
        self.stand['aktualisiert'] = time.strftime('%Y-%m-%d %H:%M:%S')
        os.makedirs(os.path.dirname(self.pfad) or '.', exist_ok=True)
        tmp = self.pfad + '.neu'
        with open(tmp, 'w') as f:
            json.dump(self.stand, f, indent=1, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.pfad)

    # ---------------- Lernen ----------------
    def parameter(self):
        """Parameter, mit denen JETZT gefahren wird (Herausforderer oder Champion)."""
        if self.stand['phase'] == 'kandidat' and self.stand['kandidat']:
            return dict(self.stand['kandidat']['parameter'])
        return dict(self.stand['champion'])

    def runde_fertig(self, wertung, diagnose):
        """Nach jeder gewerteten Runde. wertung: Zahl (hoeher = besser), diagnose: Fehlerart (GRUPPEN) der letzten
        Runden. Rueckgabe: Text, was sich geaendert hat, oder None."""
        s = self.stand
        s['runden_gesamt'] += 1
        text = None
        if s['phase'] == 'kandidat' and s['kandidat']:
            k = s['kandidat']
            k['wertungen'].append(round(float(wertung), 2))
            if len(k['wertungen']) >= RUNDEN_JE_VERSUCH:
                text = self._entscheiden()
        else:
            s['champion_wertungen'] = (s['champion_wertungen'] + [round(float(wertung), 2)])[-CHAMPION_FENSTER:]
            s['kontrolle_offen'] = max(0, s['kontrolle_offen'] - 1)
            # erst wenn der Champion gemessen ist (mind. 2 Runden) und die Kontrollrunden vorbei sind: neuer Versuch
            if len(s['champion_wertungen']) >= 2 and s['kontrolle_offen'] == 0:
                text = self._herausforderer(diagnose)
        return text

    def _entscheiden(self):
        s, k = self.stand, self.stand['kandidat']
        name = k['name']
        neu = sum(k['wertungen']) / len(k['wertungen'])
        alt = sum(s['champion_wertungen']) / len(s['champion_wertungen'])
        angenommen = neu >= alt + VORSPRUNG
        eintrag = {'zeit': time.strftime('%Y-%m-%d %H:%M:%S'), 'runde': s['runden_gesamt'], 'name': name,
                   'alt': s['champion'][name], 'neu': k['parameter'][name], 'wertung_alt': round(alt, 2),
                   'wertung_neu': round(neu, 2), 'grund': k.get('grund'), 'angenommen': angenommen}
        s['versuche'] = (s['versuche'] + [eintrag])[-200:]
        if angenommen:
            s['champion'] = dict(k['parameter'])
            s['champion_wertungen'] = list(k['wertungen'])
            s['schritt'][name] = min(SCHRITT_MAX, s['schritt'][name] * 1.5)
        else:
            s['schritt'][name] = max(SCHRITT_MIN, s['schritt'][name] * 0.6)
            s['richtung'][name] = -k['richtung']          # naechstes Mal andersherum probieren
        s['kandidat'], s['phase'], s['kontrolle_offen'] = None, 'champion', KONTROLLRUNDEN
        return (f"Versuch {name} {eintrag['alt']} -> {eintrag['neu']}: Wertung {alt:.1f} -> {neu:.1f} "
                + ('ANGENOMMEN (neuer Champion)' if angenommen else 'verworfen (alter Wert bleibt)'))

    def _herausforderer(self, diagnose):
        s = self.stand
        gruppe = diagnose if diagnose in GRUPPEN else 'langsam'
        namen = GRUPPEN[gruppe]
        # reihum durch die Gruppe; ein Parameter, der schon an beiden Grenzen nichts mehr bringt, wird uebersprungen
        for versuch in range(len(namen)):
            name = namen[(s['reihum'][gruppe] + versuch) % len(namen)]
            p = PARAMETER[name]
            alt = s['champion'][name]
            for richtung in (s['richtung'][name], -s['richtung'][name]):
                neu = begrenzen(name, alt + richtung * p['schritt'] * s['schritt'][name])
                if neu != alt:
                    break
            if neu == alt:
                continue
            s['reihum'][gruppe] = (s['reihum'][gruppe] + versuch + 1) % len(namen)
            werte = dict(s['champion'])
            werte[name] = neu
            s['richtung'][name] = richtung
            s['kandidat'] = {'parameter': werte, 'name': name, 'richtung': richtung, 'wertungen': [], 'grund': gruppe}
            s['phase'] = 'kandidat'
            return f'Neuer Versuch wegen "{gruppe}": {name} {alt} -> {neu} ({p["text"]})'
        return None

    def zuruecksetzen(self):
        """Nur bewusst aufrufen (Skript). Legt vorher eine Sicherung mit Zeitstempel an."""
        sicherung = None
        if os.path.exists(self.pfad):
            sicherung = f"{self.pfad}.sicherung_{time.strftime('%Y%m%d_%H%M%S')}"
            os.replace(self.pfad, sicherung)
        self.stand = leerer_lernstand()
        self.speichern()
        return sicherung

    def kopie(self):
        return copy.deepcopy(self.stand)
