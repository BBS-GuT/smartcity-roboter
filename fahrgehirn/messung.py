#!/usr/bin/env python3
# Messen, bevor gelernt wird (ohne ROS, damit testbar).
#
# Pro Kreuzung (kreuzungen.csv): gewuenschte Richtung (Fahrplan), erkannt ja/nein, gewaehlter Ast, gefahrene Richtung
#   (gemessen ueber die eigene Drehung, Lagesensor/Radzaehler), Linienverlust, groesste Abweichung, Blink-Vorlauf, Zeit.
# Pro Runde (runden.csv): Kreuzungen ok/gesamt, Linienverluste, mittlere/groesste Abweichung von der Linienmitte,
#   Pendeln, Lenkunruhe, Tempo, Zeit, Wertung, benutzte Parameter.
# Je 10 Runden (fortschritt.csv): Erfolgsquote Abbiegen, Linienhaltung, Wertung -> wird es besser?
#
# Die Abweichung kommt vom Roboter selbst (Linien-Gedaechtnis: wo liegt die Linie unter mir?). Das ist seine eigene
# Schaetzung, kein Massband. Im Simulator (sim/fahrgehirn_sim.py) wird sie mit der Wahrheit verglichen.
import csv
import math
import os

import numpy as np

from fahrplan import richtung_aus_drehung

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PROTOKOLL = os.environ.get('SMARTCITY_FAHRGEHIRN_LOGS', os.path.join(REPO, 'logs', 'fahrgehirn'))
BLOCK = 10                 # Fortschritt je so viele Runden
UNSAUBER_CM = 4.0          # Kreuzung geklappt, aber dabei weiter als das neben der Linie -> "unsauber"

# Ergebnis einer Kreuzung
OK, NICHT_ERKANNT, RICHTUNG_FEHLT, FALSCH, VERLOREN, ABGEBROCHEN = (
    'ok', 'nicht_erkannt', 'richtung_fehlt', 'falsch_abgebogen', 'linie_verloren', 'abgebrochen')

KREUZUNG_SPALTEN = ['zeit', 'runde', 'plan_pos', 'gewuenscht', 'erkannt', 'aeste_grad', 'gewaehlt', 'gefahren',
                    'drehung_grad', 'ergebnis', 'unsauber', 'linie_weg', 'max_abw_cm', 'blink_vorlauf_s', 'dauer_s',
                    'tempo', 'kandidat', 'hinweis']
RUNDEN_SPALTEN = ['zeit', 'runde', 'gewertet', 'dauer_s', 'strecke_m', 'kreuzungen', 'kreuzungen_ok', 'nicht_erkannt',
                  'richtung_fehlt', 'falsch_abgebogen', 'linie_verloren_kreuzung', 'unsauber', 'linie_weg',
                  'abw_mittel_cm', 'abw_max_cm', 'pendeln_cm', 'lenkunruhe', 'tempo_mittel', 'halte_sicherheit',
                  'wertung', 'phase', 'versuch', 'parameter']
FORTSCHRITT_SPALTEN = ['bis_runde', 'runden', 'abbiege_quote', 'abw_mittel_cm', 'pendeln_cm', 'linie_weg_je_runde',
                       'tempo_mittel', 'wertung_mittel', 'hauptproblem']


def wertung(r):
    """Eine Zahl je Runde, hoeher = besser (max. 100). Was zaehlt:
       50 Punkte  Anteil der Kreuzungen, die geklappt haben
       25 Punkte  Linienhaltung: 0 cm mittlere Abweichung = 25, ab 3 cm = 0
       10 Punkte  Ruhe: kein Pendeln = 10, ab 2 cm Pendeln = 0
       15 Punkte  Tempo: 0,25 m/s im Mittel = 15 (schneller zaehlt nicht mehr)
      -15 Punkte  je Linienverlust (hoechstens -45)"""
    quote = r['kreuzungen_ok'] / r['kreuzungen'] if r['kreuzungen'] else 1.0
    w = (50.0 * quote
         + 25.0 * max(0.0, 1.0 - r['abw_mittel_cm'] / 3.0)
         + 10.0 * max(0.0, 1.0 - r['pendeln_cm'] / 2.0)
         + 15.0 * min(1.0, r['tempo_mittel'] / 0.25)
         - min(45.0, 15.0 * r['linie_weg']))
    return round(w, 2)


def diagnose(runden):
    """Womit scheitert er? runden: die letzten Runden (dicts wie in runden.csv). Rueckgabe: (Fehlerart, Text).
    Fehlerarten wie fahrgehirn/lernen.py GRUPPEN. Reihenfolge = Gewicht: was am meisten Wertung kostet zuerst."""
    if not runden:
        return 'langsam', 'noch keine Runde'
    n = len(runden)
    summe = lambda k: sum(float(r[k]) for r in runden)   # noqa: E731
    kreuzungen = max(1.0, summe('kreuzungen'))
    kosten = {
        # Punkte, die diese Fehlerart je Runde ungefaehr kostet (wie in wertung())
        'kreuzung_nicht_erkannt': 50.0 * (summe('nicht_erkannt') + summe('richtung_fehlt')) / kreuzungen,
        'falsch_abgebogen': 50.0 * summe('falsch_abgebogen') / kreuzungen,
        'linie_verloren': min(45.0, 15.0 * summe('linie_weg') / n) + 50.0 * summe('linie_verloren_kreuzung') / kreuzungen,
        'pendeln': 10.0 * min(1.0, summe('pendeln_cm') / n / 2.0),
        'abweichung': 25.0 * min(1.0, summe('abw_mittel_cm') / n / 3.0),
        'langsam': 15.0 * (1.0 - min(1.0, summe('tempo_mittel') / n / 0.25)),
    }
    art, wert = max(kosten.items(), key=lambda kv: kv[1])
    if wert < 1.0:
        return 'langsam', 'kaum noch Fehler -> schneller werden'
    teile = ', '.join(f'{k} {v:.1f}' for k, v in sorted(kosten.items(), key=lambda kv: -kv[1]) if v >= 0.5)
    return art, f'Hauptproblem: {art} (verlorene Punkte je Runde: {teile})'


class KreuzungsMessung:
    """Eine Kreuzung vom Erkennen bis zur Auswertung (Drehung nach 'messweg' m gemessen)."""

    def __init__(self, jetzt, runde, plan_pos, gewuenscht, gier, weg, kandidat):
        self.d = {'zeit': round(jetzt, 2), 'runde': runde, 'plan_pos': plan_pos, 'gewuenscht': gewuenscht,
                  'erkannt': True, 'aeste_grad': '', 'gewaehlt': '', 'gefahren': '', 'drehung_grad': '',
                  'ergebnis': '', 'unsauber': False, 'linie_weg': 0, 'max_abw_cm': 0.0, 'blink_vorlauf_s': '',
                  'dauer_s': 0.0, 'tempo': 0.0, 'kandidat': kandidat, 'hinweis': ''}
        self.start, self.gier0, self.weg0 = jetzt, gier, weg
        self.gewaehlt_zeit = None
        self.blink_zeit = None
        self.wartet = 0               # so viele Bilder war die Wunschrichtung nicht zu sehen
        self.tempo = []

    def gewaehlt(self, jetzt, aeste_grad, richtung, gier, weg):
        self.d['aeste_grad'] = ' '.join(f'{a:+.0f}' for a in sorted(aeste_grad))
        self.d['gewaehlt'] = richtung
        self.gewaehlt_zeit, self.gier0, self.weg0 = jetzt, gier, weg

    def takt(self, quer, lin, linie_weg_neu):
        if quer is not None:
            self.d['max_abw_cm'] = max(self.d['max_abw_cm'], round(abs(quer) * 100, 1))
        self.d['linie_weg'] += int(linie_weg_neu)
        self.tempo.append(lin)

    def drehung(self, gier):
        return math.degrees(math.remainder(gier - self.gier0, 2 * math.pi))

    def abschliessen(self, jetzt, gier, ergebnis=None, drehbeginn=None):
        d = self.d
        dreh = self.drehung(gier)
        d['drehung_grad'] = round(dreh, 1)
        d['gefahren'] = richtung_aus_drehung(dreh)
        d['dauer_s'] = round(jetzt - self.start, 2)
        d['tempo'] = round(float(np.mean(self.tempo)), 3) if self.tempo else 0.0
        if self.blink_zeit is not None and drehbeginn is not None:
            d['blink_vorlauf_s'] = round(drehbeginn - self.blink_zeit, 2)
        if ergebnis is None:
            if d['gewaehlt'] and d['gewaehlt'] != d['gewuenscht']:
                ergebnis = RICHTUNG_FEHLT
            elif d['gefahren'] == d['gewuenscht']:
                ergebnis = OK
            elif d['linie_weg']:
                ergebnis = VERLOREN
            else:
                ergebnis = FALSCH
        d['ergebnis'] = ergebnis
        d['unsauber'] = ergebnis == OK and d['max_abw_cm'] > UNSAUBER_CM
        return d


class RundenMessung:
    """Sammelt die Messwerte einer Runde (20x pro Sekunde takt())."""

    def __init__(self, jetzt, runde):
        self.runde, self.start = runde, jetzt
        self.kreuzungen = []
        self.quer, self.quer_gerade, self.dreh_gerade, self.tempo = [], [], [], []
        self.strecke = 0.0
        self.linie_weg = 0
        self.pause = 0.0              # Zeit im Stand wegen Hindernis/Pause zaehlt nicht zur Rundenzeit
        self.halte = 0
        self.gestoert = None          # Grund, warum diese Runde nicht gewertet wird (Neustart, Umsetzen ...)

    def takt(self, dt, lin, dreh, lokal, linie_weg_neu, steht_absichtlich):
        if steht_absichtlich:
            self.pause += dt
            return
        self.strecke += abs(lin) * dt
        self.linie_weg += int(linie_weg_neu)
        if lin > 0.05:
            self.tempo.append(lin)
            if lokal is not None:
                self.quer.append(lokal['quer'])
                if abs(lokal['kruemmung']) < 0.5:        # Gerade: hier zaehlt Pendeln
                    self.quer_gerade.append(lokal['quer'])
                    self.dreh_gerade.append(dreh)

    def abschliessen(self, jetzt, phase, versuch, parameter):
        """Kreuzungen, die im Fahrplan standen, aber nie erkannt wurden, stehen als 'nicht_erkannt' in self.kreuzungen
        (FahrGehirn traegt sie beim Ueberspringen ein)."""
        k = self.kreuzungen
        zaehle = lambda e: sum(1 for x in k if x['ergebnis'] == e)   # noqa: E731
        q = np.abs(self.quer) * 100 if self.quer else np.zeros(1)
        if len(self.quer_gerade) > 20:
            # Pendeln = Schwankung um die eigene Mitte (gleitender Mittelwert ueber ca. 2 s abgezogen)
            g = np.array(self.quer_gerade) * 100
            n = min(40, len(g) // 2)
            glatt = np.convolve(g, np.ones(n) / n, mode='same')
            pendeln = float(math.sqrt(2) * np.std(g - glatt))
            unruhe = float(np.std(self.dreh_gerade))
        else:
            pendeln = unruhe = 0.0
        r = {'zeit': round(jetzt, 1), 'runde': self.runde, 'gewertet': self.gestoert is None,
             'dauer_s': round(jetzt - self.start - self.pause, 1), 'strecke_m': round(self.strecke, 2),
             'kreuzungen': len(k), 'kreuzungen_ok': zaehle(OK), 'nicht_erkannt': zaehle(NICHT_ERKANNT),
             'richtung_fehlt': zaehle(RICHTUNG_FEHLT), 'falsch_abgebogen': zaehle(FALSCH),
             'linie_verloren_kreuzung': zaehle(VERLOREN), 'unsauber': sum(1 for x in k if x['unsauber']),
             'linie_weg': self.linie_weg, 'abw_mittel_cm': round(float(np.mean(q)), 2),
             'abw_max_cm': round(float(np.max(q)), 2), 'pendeln_cm': round(pendeln, 2), 'lenkunruhe': round(unruhe, 3),
             'tempo_mittel': round(float(np.mean(self.tempo)), 3) if self.tempo else 0.0, 'halte_sicherheit': self.halte,
             'phase': phase, 'versuch': versuch, 'parameter': parameter}
        r['wertung'] = wertung(r)
        return r


class Protokoll:
    """CSV-Dateien in logs/fahrgehirn/ (anhaengen, bleiben ueber Neustarts erhalten)."""

    def __init__(self, ordner=PROTOKOLL):
        self.ordner = ordner
        os.makedirs(ordner, exist_ok=True)

    def _anhaengen(self, name, spalten, zeile):
        pfad = os.path.join(self.ordner, name)
        neu = not os.path.exists(pfad) or os.path.getsize(pfad) == 0
        with open(pfad, 'a', newline='') as f:
            w = csv.DictWriter(f, fieldnames=spalten, extrasaction='ignore')
            if neu:
                w.writeheader()
            w.writerow(zeile)
            f.flush()
            os.fsync(f.fileno())

    def kreuzung(self, d):
        self._anhaengen('kreuzungen.csv', KREUZUNG_SPALTEN, d)

    def runde(self, r):
        self._anhaengen('runden.csv', RUNDEN_SPALTEN, r)

    def lies(self, name):
        try:
            with open(os.path.join(self.ordner, name), newline='') as f:
                return list(csv.DictReader(f))
        except FileNotFoundError:
            return []

    def gewertete_runden(self):
        return [r for r in self.lies('runden.csv') if r['gewertet'] == 'True']

    def fortschritt(self, runden=None):
        """Je BLOCK gewertete Runden eine Zeile. Schreibt fortschritt.csv neu (aus runden.csv, immer vollstaendig)."""
        runden = self.gewertete_runden() if runden is None else runden
        zeilen = []
        for i in range(0, len(runden) - BLOCK + 1, BLOCK):
            zeilen.append(block_zeile(runden[i:i + BLOCK]))
        pfad = os.path.join(self.ordner, 'fortschritt.csv')
        with open(pfad + '.neu', 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=FORTSCHRITT_SPALTEN)
            w.writeheader()
            w.writerows(zeilen)
        os.replace(pfad + '.neu', pfad)
        return zeilen


def block_zeile(teil):
    f = lambda k: [float(r[k]) for r in teil]   # noqa: E731
    kreuzungen = sum(f('kreuzungen'))
    return {'bis_runde': teil[-1]['runde'], 'runden': len(teil),
            'abbiege_quote': round(sum(f('kreuzungen_ok')) / kreuzungen, 3) if kreuzungen else '',
            'abw_mittel_cm': round(float(np.mean(f('abw_mittel_cm'))), 2),
            'pendeln_cm': round(float(np.mean(f('pendeln_cm'))), 2),
            'linie_weg_je_runde': round(float(np.mean(f('linie_weg'))), 2),
            'tempo_mittel': round(float(np.mean(f('tempo_mittel'))), 3),
            'wertung_mittel': round(float(np.mean(f('wertung'))), 1),
            'hauptproblem': diagnose(teil)[0]}
