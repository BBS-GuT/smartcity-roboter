#!/usr/bin/env python3
# Arm-Gehirn: Protokoll je Versuch (CSV) und Fortschritt (ohne ROS).
#
# config/lokal/armgehirn/versuche.csv   eine Zeile je Versuch (Excel/LibreOffice: Trennzeichen ;)
# config/lokal/armgehirn/fortschritt.csv eine Zeile je 10 Versuche: Erfolgsquote und mittlerer Zielfehler
# config/lokal/armgehirn.json           weiterer Lernstand des Arm-Gehirns (Umschauen, Lage-Kalibrierung)
# Jede Zeile wird sofort auf die Karte geschrieben (flush + fsync): Strom weg = hoechstens die letzte Zeile fehlt.
#
# Ziel "gut und zuverlaessig" (ZIEL): mindestens 90 % der letzten 30 Versuche mit raeumbarem Gegenstand
# abgelegt UND jeder Versuch mit verbotenem Gegenstand (Person/Figur) richtig NICHT gegriffen (mindestens 5).
import csv
import json
import os
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ORDNER = os.environ.get('SMARTCITY_ARMGEHIRN', os.path.join(REPO, 'config', 'lokal', 'armgehirn'))
ZIEL = {'quote': 0.9, 'letzte': 30, 'verboten_min': 5}

SPALTEN = ['nr', 'zeit', 'erwartet', 'entscheidung', 'grund', 'ergebnis', 'belohnung', 'richtig',
           'gemessen_vor', 'gemessen_seite', 'breite', 'hoehe', 'tiefe', 'kalibriert_vor', 'kalibriert_seite',
           'wahr_vor', 'wahr_seite', 'lagefehler_cm',
           'ziel_x', 'ziel_y', 'ziel_z', 'korrektur_x', 'korrektur_y', 'korrektur_z', 'modell',
           'alter_ort_frei', 'verschiebung_cm', 'ablage_abweichung_cm', 'greifer', 'zielfehler_cm', 'zielfehler_quelle',
           'blick', 'blick_versuche', 'dauer_s', 'text']


def _f(v, nk=4):
    if v is None:
        return ''
    if isinstance(v, bool):
        return '1' if v else '0'
    if isinstance(v, float):
        return f'{v:.{nk}f}'
    return str(v)


def _anhaengen(datei, spalten, zeile):
    neu = not os.path.exists(datei)
    os.makedirs(os.path.dirname(datei), exist_ok=True)
    with open(datei, 'a', newline='') as f:
        w = csv.writer(f, delimiter=';')
        if neu:
            w.writerow(spalten)
        w.writerow([_f(zeile.get(k)) for k in spalten])
        f.flush()
        os.fsync(f.fileno())


class Protokoll:
    def __init__(self, ordner=ORDNER):
        self.ordner = ordner
        self.datei = os.path.join(ordner, 'versuche.csv')
        self.fortschritt_datei = os.path.join(ordner, 'fortschritt.csv')
        self._alte_spalten_wegraeumen()
        self.zeilen = self._lesen()

    def _alte_spalten_wegraeumen(self):
        """Datei aus einer frueheren Version mit anderen Spalten: umbenennen (.alt_...) statt falsch weiterschreiben."""
        try:
            with open(self.datei, newline='') as f:
                kopf = next(csv.reader(f, delimiter=';'), None)
        except OSError:
            return
        if kopf is not None and kopf != SPALTEN:
            stempel = time.strftime('%Y%m%d_%H%M%S')
            for d in (self.datei, self.fortschritt_datei):
                if os.path.exists(d):
                    os.replace(d, f'{d}.alt_{stempel}')

    def _lesen(self):
        try:
            with open(self.datei, newline='') as f:
                return list(csv.DictReader(f, delimiter=';'))
        except OSError:
            return []

    def schreiben(self, zeile):
        """Einen Versuch anhaengen (zeile: dict mit Schluesseln aus SPALTEN). Alle 10 Versuche: Fortschritt."""
        zeile = dict(zeile, nr=len(self.zeilen) + 1, zeit=time.strftime('%Y-%m-%d %H:%M:%S'))
        _anhaengen(self.datei, SPALTEN, zeile)
        self.zeilen.append({k: _f(zeile.get(k)) for k in SPALTEN})
        if len(self.zeilen) % 10 == 0:
            st = self.stand()
            _anhaengen(self.fortschritt_datei, ['bis_versuch', 'zeit', 'quote_letzte_10', 'quote_letzte_30',
                                                'zielfehler_cm_letzte_10', 'verboten_richtig', 'ziel_erreicht'],
                       {'bis_versuch': len(self.zeilen), 'zeit': zeile['zeit'], 'quote_letzte_10': st['quote_10'],
                        'quote_letzte_30': st['quote_30'], 'zielfehler_cm_letzte_10': st['zielfehler_10'],
                        'verboten_richtig': f"{st['verboten_richtig']}/{st['verboten']}",
                        'ziel_erreicht': st['ziel_erreicht']})
        return zeile

    def stand(self):
        """Fortschritt: Erfolgsquote (raeumbare Gegenstaende abgelegt) je 10 und ueber die letzten 30,
        mittlerer Zielfehler, verbotene Gegenstaende richtig nicht gegriffen, Ziel erreicht?"""
        raeumbar = [z for z in self.zeilen if z['erwartet'] == 'greifen']
        verboten = [z for z in self.zeilen if z['erwartet'] == 'nicht_greifen']

        def quote(zs):
            return round(sum(z['ergebnis'] == 'abgelegt' for z in zs) / len(zs), 3) if zs else None
        fehler = [float(z['zielfehler_cm']) for z in raeumbar[-10:] if z.get('zielfehler_cm')]
        bloecke = [quote(raeumbar[i:i + 10]) for i in range(0, len(raeumbar), 10)]
        v_richtig = sum(z['richtig'] == '1' for z in verboten)
        q30 = quote(raeumbar[-ZIEL['letzte']:])
        ziel = (len(raeumbar) >= ZIEL['letzte'] and q30 is not None and q30 >= ZIEL['quote']
                and len(verboten) >= ZIEL['verboten_min'] and v_richtig == len(verboten))
        return {'versuche': len(self.zeilen), 'raeumbar': len(raeumbar), 'quote_10': quote(raeumbar[-10:]),
                'quote_30': q30, 'quote_je_10': bloecke,
                'zielfehler_10': round(sum(fehler) / len(fehler), 2) if fehler else None,
                'verboten': len(verboten), 'verboten_richtig': v_richtig, 'ziel_erreicht': bool(ziel)}

    def text(self):
        st = self.stand()
        q = lambda v: '-' if v is None else f'{v * 100:.0f} %'
        t = (f"{st['versuche']} Versuche ({st['raeumbar']} raeumbar): letzte 10 {q(st['quote_10'])}, letzte 30 "
             f"{q(st['quote_30'])}, je 10: {' '.join(q(v) for v in st['quote_je_10']) or '-'}; Zielfehler "
             f"{'-' if st['zielfehler_10'] is None else str(st['zielfehler_10']) + ' cm'}; verbotene Gegenstaende "
             f"richtig nicht gegriffen {st['verboten_richtig']}/{st['verboten']}")
        if st['ziel_erreicht']:
            t += (f"\n*** ZIEL ERREICHT: >= {ZIEL['quote'] * 100:.0f} % der letzten {ZIEL['letzte']} Versuche abgelegt, "
                  f"alle verbotenen richtig nicht gegriffen ***")
        return t


def lade_zustand(datei=None):
    datei = datei or os.path.join(os.path.dirname(ORDNER), 'armgehirn.json')
    try:
        with open(datei) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def speichere_zustand(daten, datei=None):
    """Atomar wie lib/greifen.py: erst .neu schreiben, dann umbenennen."""
    datei = datei or os.path.join(os.path.dirname(ORDNER), 'armgehirn.json')
    os.makedirs(os.path.dirname(os.path.abspath(datei)), exist_ok=True)
    with open(datei + '.neu', 'w') as f:
        json.dump(daten, f, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(datei + '.neu', datei)
