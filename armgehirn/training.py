#!/usr/bin/env python3
# Arm-Gehirn trainieren: Versuch -> Ergebnis -> lernen -> speichern -> warten, bis ein Mensch den Gegenstand neu
# hingelegt hat (Taste) -> naechster Versuch. Der Roboter faehrt dabei NICHT.
#
#   scripts/armgehirn_training.sh                 auf dem Roboter (ROS, Kamera muss laufen)
#   python3 armgehirn/training.py --sim           in der Uebungswelt (ohne ROS, legt selbst hin)
# Optionen: --versuche N (Ende nach N Versuchen), --einrichten (Boden neu lernen), --kalibrieren (Lage-Kalibrierung
#           mit Markierungen), --zuruecksetzen (Gelerntes BEWUSST loeschen, fragt nach)
# Bei jedem Versuch fragt das Skript, was da liegt: raeumbarer Gegenstand (Enter) oder Person/Figur (p) - dann ist
# "nicht greifen" das richtige Ergebnis. Fortschritt: config/lokal/armgehirn/versuche.csv und fortschritt.csv.
import argparse
import os
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HIER, '..'))
for _d in (HIER, os.path.join(REPO, 'lib'), os.path.join(REPO, 'sim')):
    sys.path.insert(0, _d)
import lage as lagelib     # noqa: E402
import protokoll as prot   # noqa: E402

HILFE = ('Gegenstand hinlegen, Haende weg, dann:\n'
         '  Enter = raeumbarer Gegenstand (soll gegriffen werden)\n'
         '  p     = Person/Spielfigur (darf NIE gegriffen werden)\n'
         '  m<N>  = raeumbarer Gegenstand genau auf Markierung N (z. B. m2): Lagefehler der Kamera wird gemessen\n'
         '  v     = nur vermessen, NICHT greifen (Kamera mit dem Lineal pruefen)\n'
         '  g     = Arm in Grundstellung      f = Arm in Fahrstellung      q = Ende')


def zeige(e, protokoll):
    print(f"  -> {e['ergebnis']}: {e.get('text', '')}" + (f"  (Korrektur {e['korrektur_cm']} cm)" if e.get('korrektur_cm') else ''))
    if e.get('gemessen_cm'):
        m = e['gemessen_cm']
        print(f"     gemessen: Mitte {m['mitte_vorne']} cm vorne, {m['links']:+} cm links, {m['breite']} cm breit, "
              f"{m['hoehe']} cm hoch (Blick {e.get('blick')})")
    if e.get('ziel_cm'):
        z = e['ziel_cm']
        print(f"     Greifer gezielt auf: {z[0]} cm vorne, {z[1]:+} cm links, {z[2]} cm hoch")
    if e.get('richtig') is not None:
        print('     richtig' if e['richtig'] else '     NICHT richtig')
    print('  ' + protokoll.text().replace('\n', '\n  '))


def markierungen(g):
    import arm as armlib
    return (armlib.lade_einstellungen().get('armgehirn') or {}).get('markierungen') or lagelib.MARKIERUNGEN


def kalibrieren(g, frage):
    pkt, paare = markierungen(g), []
    for i, wahr in enumerate(pkt):
        if frage(f'Gegenstand (Mitte) auf Markierung {i} legen ({wahr[0] * 100:.0f} cm vorne, {wahr[1] * 100:+.0f} cm '
                 'links), Enter (q = fertig): ').strip() == 'q':
            break
        o = g.nur_messen()
        if o is None:
            print('  nichts gesehen, Markierung uebersprungen')
            continue
        gem = (o['vor'] + o['breite'] / 2, o['seite'])
        paare.append((gem, tuple(wahr)))
        print(f'  gemessen {gem[0] * 100:.1f} / {gem[1] * 100:+.1f} cm, wahr {wahr[0] * 100:.1f} / {wahr[1] * 100:+.1f} cm')
    k = lagelib.rechnen(paare)
    if k is None:
        print('Zu wenige Markierungen (mind. 4) -> nichts gespeichert')
        return
    print(f"Lagefehler der Kamera: vorher {k['vorher_cm']} cm, nach Kalibrierung {k['rest_cm']} cm ({k['n']} Punkte)")
    if frage('Speichern? (ja/nein): ').strip() == 'ja':
        g.lage_kalibrierung = k
        g._speichern_zustand()
        print('Gespeichert (config/lokal/armgehirn.json). Das Greif-Lernen hat vorher mit unkalibrierter Lage gelernt;\n'
              'es gleicht die Aenderung von selbst aus. Wer ganz neu anfangen will: --zuruecksetzen.')


def schleife(g, protokoll, frage, n_max, sim=None):
    nr = 0
    while not n_max or nr < n_max:
        if sim is not None:
            art = 'figur' if (len(protokoll.zeilen) + 1) % 7 == 0 else 'wuerfel'
            sim.lege(art)
            eingabe = 'p' if art == 'figur' else ''
            if frage is not None:
                frage(f"[Uebungswelt] {'Figur' if art == 'figur' else 'Wuerfel'} liegt, Enter: ")
        else:
            eingabe = frage(HILFE + '\n> ').strip().lower()
        if eingabe == 'q':
            break
        if eingabe == 'v':
            o = g.nur_messen()
            if o is None:
                print('  nichts gesehen')
            else:
                print(f"  gemessen: Mitte {(o['vor'] + o['breite'] / 2) * 100:.1f} cm vor der Robotermitte, "
                      f"{o['seite'] * 100:+.1f} cm links, {o['breite'] * 100:.1f} cm breit, {o['hoehe'] * 100:.1f} cm hoch, "
                      f"{o.get('laenge', float('nan')) * 100:.1f} cm tief; Vorderkante {o['vor'] * 100:.1f} cm")
            continue
        if eingabe in ('g', 'f'):
            print('  ' + str((g.grundstellung if eingabe == 'g' else g.fahrstellung)() or 'ok'))
            continue
        wahr = None
        if eingabe.startswith('m'):
            try:
                wahr = markierungen(g)[int(eingabe[1:])]
            except (ValueError, IndexError):
                print('  unbekannte Markierung')
                continue
        erwartet = 'nicht_greifen' if eingabe == 'p' else 'greifen'
        nr += 1
        print(f'Versuch {len(protokoll.zeilen) + 1} ({erwartet}) ...')
        e = g.versuch(erwartet, wahr)
        zeige(e, protokoll)
        if sim is not None:
            sim.raeumen()
        if e['fortschritt']['ziel_erreicht'] and not getattr(g, '_ziel_gemeldet', False):
            g._ziel_gemeldet = True
            print('\n*** Das Greifen ist gut und zuverlaessig (Ziel erreicht). Weiter trainieren geht trotzdem. ***\n')


def main():
    ap = argparse.ArgumentParser(description='Arm-Gehirn trainieren (Roboter faehrt nicht)')
    ap.add_argument('--sim', action='store_true', help='Uebungswelt statt Roboter (ohne ROS)')
    ap.add_argument('--saat', type=int, default=2026, help='Uebungswelt: welcher Zufallsroboter')
    ap.add_argument('--ordner', default='', help='Uebungswelt: hier speichern (Standard: Temp-Ordner)')
    ap.add_argument('--warten', action='store_true', help='Uebungswelt: vor jedem Versuch auf Enter warten')
    ap.add_argument('--versuche', type=int, default=0, help='nach so vielen Versuchen aufhoeren (0 = bis q)')
    ap.add_argument('--einrichten', action='store_true', help='Boden in allen Blickstellungen neu lernen')
    ap.add_argument('--kalibrieren', action='store_true', help='Lage der Kamera mit Markierungen kalibrieren')
    ap.add_argument('--zuruecksetzen', action='store_true', help='Gelerntes des Arm-Gehirns BEWUSST loeschen')
    a = ap.parse_args()
    frage = input
    if a.sim:
        g, sim, protokoll = baue_sim(a)
        if a.versuche == 0:
            a.versuche = 60
        if not a.warten:
            frage = None
    else:
        g, protokoll, node, ende = baue_roboter()
        sim = None
    try:
        if a.zuruecksetzen:
            if (frage or input)('Wirklich das Gelernte loeschen (Greifen + Umschauen)? "ja" eintippen: ').strip() == 'ja':
                g.politik.zuruecksetzen()
                g.blick_lernen.zaehler.clear()
                g._speichern_zustand()
                print('Geloescht. Es gilt wieder das Vortraining.')
            return
        if a.einrichten or not g.augen.gespeichert:
            if frage is not None:
                frage('Boden lernen: Bereich vor UND rechts neben dem Roboter leer raeumen, Haende weg, Enter: ')
            print(f'  {g.einrichten()} Blickstellungen eingerichtet')
        if a.kalibrieren:
            kalibrieren(g, frage or input)
            return
        st = g.politik.lernstand()
        print(f"Greif-Lernen: {st['herkunft']}, {st['versuche']} Versuche bisher; Speicher: {g.politik.lokal}")
        print('  ' + protokoll.text())
        schleife(g, protokoll, frage, a.versuche, sim)
    finally:
        if not a.sim:
            ende()


def baue_sim(a):
    import numpy as np
    import armgehirn_sim as AS
    import greifen
    import greifen_welt as GW
    from augen import Augen
    from gehirn import ArmGehirn
    ordner = a.ordner or os.path.join(tempfile.gettempdir(), f'armgehirn_sim_{a.saat}')
    rng = np.random.default_rng(a.saat)
    welt = AS.SimWelt(GW.zufalls_roboter(rng, 'm3pro'), rng)
    protokoll = prot.Protokoll(os.path.join(ordner, 'armgehirn'))
    zustand = os.path.join(ordner, 'armgehirn.json')
    g = ArmGehirn(Augen(welt, prot.lade_zustand(zustand).get('boden')), welt, welt.planer_kin,
                  greifen.Politik('eigene', lokal=os.path.join(ordner, 'greifen.json')), GW.FAHR, AS.kamera_nenn(),
                  protokoll=protokoll, zustand_datei=zustand, rng=rng, auf=GW.AUF, zu=GW.ZU)
    print(f'Uebungswelt (Zufallsroboter {a.saat}), gespeichert in {ordner}')
    return g, welt, protokoll


def baue_roboter():
    import rclpy
    from rclpy.executors import MultiThreadedExecutor
    import threading
    import knoten
    rclpy.init()
    node = rclpy.create_node('armgehirn')
    laeuft = knoten.fahr_gehirn_laeuft(node)
    if laeuft:
        print(f"Fahr-Gehirn laeuft ({', '.join(laeuft)}) -> erst beenden (Panel: STOPP, Programm beenden). Abbruch.")
        rclpy.shutdown()
        sys.exit(1)
    protokoll = prot.Protokoll()
    g = knoten.baue_gehirn(node, protokoll)
    knoten.ArmGehirnKnoten(node, g)           # Zustand/Kommandos auch waehrend des Trainings sichtbar
    ex = MultiThreadedExecutor(num_threads=2)
    ex.add_node(node)
    threading.Thread(target=ex.spin, daemon=True).start()

    def ende():
        g.abbrechen()
        try:                              # beim Beenden nie haengen bleiben
            ex.shutdown(timeout_sec=2.0)
            node.destroy_node()
            rclpy.shutdown()
        except Exception:
            pass
    return g, protokoll, node, ende


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print('\nEnde. Gelerntes ist nach jedem Versuch gespeichert.')
