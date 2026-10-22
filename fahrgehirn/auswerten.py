#!/usr/bin/env python3
# Auswertung des Fahr-Gehirns: Wird es besser? Womit scheitert es?
#
# Aufruf (auf dem Roboter oder mit kopierten Logs):
#   python3 fahrgehirn/auswerten.py                    Fortschritt je 10 Runden, Fehler je Kreuzung, letzte Lernversuche
#   python3 fahrgehirn/auswerten.py --lernstand        nur den gespeicherten Lernstand (JSON) ausgeben
#   python3 fahrgehirn/auswerten.py --logs DIR --datei config/lokal/fahrgehirn.json   (andere Orte)
import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import messung  # noqa: E402
import lernen  # noqa: E402


def drucken(protokoll, lernstand=None):
    runden = protokoll.gewertete_runden()
    alle = protokoll.lies('runden.csv')
    print(f'Runden: {len(alle)} gefahren, {len(runden)} gewertet (nicht gewertet: Start mitten im Fahrplan, Stopp)')
    if not runden:
        print('Noch keine gewertete Runde.')
        return
    print()
    print('Fortschritt je 10 Runden (fortschritt.csv):')
    print(f"{'bis Runde':>9} | {'Abbiegen':>8} | {'Abw. cm':>7} | {'Pendeln':>7} | {'Linie weg':>9} | "
          f"{'Tempo':>5} | {'Wertung':>7} | Hauptproblem")
    zeilen = protokoll.fortschritt()
    rest = len(runden) % messung.BLOCK
    if rest:   # angefangener Block: zum Ansehen, steht nicht in fortschritt.csv
        zeilen = zeilen + [dict(messung.block_zeile(runden[-rest:]), bis_runde=f"{runden[-1]['runde']}*")]
    for z in zeilen:
        quote = '-' if z['abbiege_quote'] == '' else f"{float(z['abbiege_quote']) * 100:.0f} %"
        print(f"{z['bis_runde']:>9} | {quote:>8} | {float(z['abw_mittel_cm']):7.2f} | {float(z['pendeln_cm']):7.2f} | "
              f"{float(z['linie_weg_je_runde']):9.2f} | {float(z['tempo_mittel']):5.2f} | "
              f"{float(z['wertung_mittel']):7.1f} | {z['hauptproblem']}")
    if rest:
        print(f'  * = angefangener Block ({rest} Runden), noch nicht in fortschritt.csv')
    print()
    art, text = messung.diagnose(runden[-10:])
    print('Diagnose der letzten 10 Runden: ' + text)
    kreuzungen = protokoll.lies('kreuzungen.csv')[-200:]
    if kreuzungen:
        print()
        print('Kreuzungen (letzte 200) je Plan-Position: Ergebnis')
        for pos in sorted({k['plan_pos'] for k in kreuzungen}, key=int):
            teil = [k for k in kreuzungen if k['plan_pos'] == pos]
            c = Counter(k['ergebnis'] for k in teil)
            unsauber = sum(k['unsauber'] == 'True' for k in teil)
            vorlauf = [float(k['blink_vorlauf_s']) for k in teil if k['blink_vorlauf_s']]
            print(f"  Nr. {pos} ({teil[0]['gewuenscht']:>9}): " + ', '.join(f'{e} {n}' for e, n in c.most_common())
                  + (f', davon unsauber {unsauber}' if unsauber else '')
                  + (f', Blinker {min(vorlauf):.1f}-{max(vorlauf):.1f} s vor dem Abbiegen' if vorlauf else ''))
    if lernstand:
        print()
        print('Gelernte Parameter (Champion):')
        for n, v in lernstand['champion'].items():
            if n not in lernen.PARAMETER:
                continue
            p = lernen.PARAMETER[n]
            print(f"  {n:15} {v:>7}   (Start {p['start']}, Grenzen {p['min']}..{p['max']})  {p['text']}")
        versuche = lernstand['versuche'][-8:]
        if versuche:
            print('Letzte Lernversuche:')
            for v in versuche:
                print(f"  Runde {v['runde']:>4}: {v['name']} {v['alt']} -> {v['neu']} wegen {v['grund']}: Wertung "
                      f"{v['wertung_alt']} -> {v['wertung_neu']} {'ANGENOMMEN' if v['angenommen'] else 'verworfen'}")


def main():
    ap = argparse.ArgumentParser(description='Auswertung des Fahr-Gehirns')
    ap.add_argument('--logs', default=messung.PROTOKOLL)
    ap.add_argument('--datei', default=lernen.LERNSTAND)
    ap.add_argument('--lernstand', action='store_true', help='nur den gespeicherten Lernstand ausgeben (JSON)')
    a = ap.parse_args()
    try:                         # nur lesen: die Auswertung aendert und verschiebt nie etwas
        with open(a.datei) as f:
            stand = json.load(f)
    except FileNotFoundError:
        stand = lernen.leerer_lernstand()
    if a.lernstand:
        print(json.dumps(stand, indent=1, sort_keys=True))
        return
    drucken(messung.Protokoll(a.logs), stand)


if __name__ == '__main__':
    main()
