#!/usr/bin/env python3
# Startet Simulator + KI-Zentrale + Linienfolger (faehrt nur im Simulator) und prueft,
# ob sich der simulierte Roboter richtig verhaelt.
# Aufruf: scripts/simulation.sh pruefen     (setzt eine eigene ROS_DOMAIN_ID, NICHT 30)
#   SIM_DAUER=150        so viele Sekunden fahren
#   SIM_SCHWER=1         wie in echt: grosser Raum, zweiter LiDAR versetzt eingebaut, Lagesensor 3 % daneben,
#                        Scans kommen spaeter an (prueft, ob die Karte trotzdem nicht wegdreht)
#   SIM_KARTE_ORDNER=... Kartenordner (Standard: neu in den Logs). Zweimal mit demselben Ordner
#                        starten -> prueft, ob der Roboter sich in der vorhandenen Karte wiederfindet.
#   SIM_WUERFEL_ZUFALL=1 Wuerfel zufaellig legen (Lage, Groesse); SIM_WUERFEL_SAAT=7 fuer immer denselben Zufall
#   SIM_ARM_WIE_PLANER=1 simulierter Arm genau so, wie die KI ihn sich vorstellt (sonst etwas anders, siehe
#                        sim/arm_sim.yaml geometrie_simulator -> die KI muss mit dem Gelernten ausgleichen)
#   SIM_GREIFEN_BEHALTEN=1  auf dem Roboter Gelerntes (Logs/greifen_lokal.json) vom letzten Lauf weiterverwenden
import json
import math
import os
import signal
import subprocess
import sys
import time

import numpy as np
import rclpy
from std_msgs.msg import String

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(REPO, 'sim'))
from welt import Welt  # noqa: E402
sys.path.insert(0, os.path.join(REPO, 'lib'))
import karte as K      # noqa: E402

DAUER = float(os.environ.get('SIM_DAUER', 150))
LOGS = os.environ.get('SIM_LOGS', '/tmp')
VERZ = float(os.environ.get('SIM_VERZOEGERUNG', 0.0))   # Kamerabild kommt so viele s zu spaet (Ueberlast)
GEGNER = bool(os.environ.get('SIM_GEGNER'))   # anderer Roboter blockiert die Linie -> muss ausweichen
KARTEN = os.environ.get('SIM_KARTE_ORDNER', os.path.join(LOGS, 'sim_karten'))
WUERFEL = ['-p', 'wuerfel_zufall:=true', '-p', f"wuerfel_saat:={int(os.environ.get('SIM_WUERFEL_SAAT', 0))}"] \
    if os.environ.get('SIM_WUERFEL_ZUFALL') else []
WUERFEL += ['-p', 'arm_wie_planer:=true'] if os.environ.get('SIM_ARM_WIE_PLANER') else []
SCHWER = ['-p', 'halle:=true', '-p', 'imu_skala:=1.03', '-p', 'lidar_umlauf:=0.12', '-p', 'lidar_verzoegerung:=0.1',
          '-p', 'lidar1_einbau:=[-0.12,0.0,4.0]'] if os.environ.get('SIM_SCHWER') else []


def starte(befehl, name, env):
    log = open(os.path.join(LOGS, f'sim_{name}.log'), 'w')
    return subprocess.Popen(befehl, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=env)


def main():
    if os.environ.get('ROS_DOMAIN_ID', '0') == '30':
        sys.exit('ROS_DOMAIN_ID=30 ist die der Roboter! Simulation nur mit anderer Domain-ID.')
    env = dict(os.environ)
    env.setdefault('SMARTCITY_ARM_YAML', os.path.join(REPO, 'sim', 'arm_sim.yaml'))
    # Gelerntes Greifen der Simulation nicht in config/lokal/ (das gehoert dem echten Roboter)
    env.setdefault('SMARTCITY_GREIFEN', os.path.join(LOGS, 'greifen_lokal.json'))
    if not os.environ.get('SIM_GREIFEN_BEHALTEN') and os.path.exists(env['SMARTCITY_GREIFEN']):
        os.remove(env['SMARTCITY_GREIFEN'])
    cfg = ['--params-file', os.path.join(REPO, 'config', 'roboter.yaml')]
    prozesse = [
        starte([sys.executable, os.path.join(REPO, 'sim', 'simulator.py')]
               + ['--ros-args', '-p', f'gegner:={str(GEGNER).lower()}', '-p', f'kamera_verzoegerung:={VERZ}'] + SCHWER
               + WUERFEL,
               'simulator', env),
        starte([sys.executable, os.path.join(REPO, 'ki', 'zentrale.py'), '--ros-args'] + cfg, 'ki', env),
        starte([sys.executable, os.path.join(REPO, 'line_follower', 'line_follower.py'), '--ros-args'] + cfg +
               ['-p', 'drive:=true', '-p', 'show:=false'], 'linienfolger', env),
        starte([sys.executable, os.path.join(REPO, 'kartograf', 'kartograf.py'), '--ros-args'] + cfg +
               ['-p', f'ordner:={KARTEN}'], 'kartograf', env),
    ]
    rclpy.init()
    node = rclpy.create_node('sim_pruefer')
    zustaende, ereignisse, befehle, karte = [], [], [], []
    node.create_subscription(String, '/sim/zustand', lambda m: zustaende.append(json.loads(m.data)), 50)
    node.create_subscription(String, '/ki/ereignis', lambda m: ereignisse.append(json.loads(m.data)), 50)
    node.create_subscription(String, '/ki/befehl', lambda m: befehle.append(json.loads(m.data)), 50)
    node.create_subscription(String, '/karte/pose', lambda m: karte.append(json.loads(m.data)), 50)
    print(f'Simulation laeuft {DAUER:.0f} s ... (Logs: {LOGS}/sim_*.log)')
    ende = time.time() + DAUER
    try:
        while time.time() < ende:
            rclpy.spin_once(node, timeout_sec=0.1)
    finally:
        for p in prozesse:
            try:
                os.killpg(p.pid, signal.SIGINT)
            except ProcessLookupError:
                pass
        for p in prozesse:
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
        node.destroy_node()
        rclpy.shutdown()
    with open(os.path.join(LOGS, 'sim_verlauf.json'), 'w') as f:   # zum Nachschauen
        json.dump({'zustaende': zustaende, 'ereignisse': ereignisse, 'befehle': befehle[::5], 'karte': karte}, f)
    return auswerten(zustaende, ereignisse, karte)


def auswerten(zustaende, ereignisse, karte=()):
    if not zustaende:
        print(f'FEHLER: keine Daten vom Simulator. Logs: {LOGS}/sim_*.log')
        return 1
    welt = Welt()
    L = welt.laenge
    t0 = zustaende[0]['zeit']
    print('\nEreignisse der KI:')
    for e in ereignisse:
        print(f"  {e['zeit'] - t0:6.1f} s  {e['text']}")

    fehler = 0

    def check(name, ok, info=''):
        nonlocal fehler
        fehler += not ok
        print(f"{'OK  ' if ok else 'FEHLER'} {name} {info}")

    def vor(z, s_ziel):
        """Wie weit (m, entlang der Strecke) liegt s_ziel vor dem Roboter? (in Fahrtrichtung vorwaerts)"""
        return (s_ziel - z['s']) % L

    # Abschnitt bis zur Einbahnstrasse (erste Runde, in Fahrtrichtung)
    hin = []
    for z in zustaende:
        if z['gefahren'] > 0.3 and not z['vorwaerts']:
            break
        hin.append(z)

    print('\nPruefungen:')
    gesamt = zustaende[-1]['gefahren']
    check('Roboter faehrt', gesamt > 2.0, f'({gesamt:.1f} m gefahren)')
    # Spurtreue: ohne die Aufheben-Stelle (dort faehrt er absichtlich seitlich zum Wuerfel und zurueck)
    fahrt = [z for z in zustaende if z['v'] > 0.05 and abs(z['quer']) < 1e-3
             and not (welt.wuerfel_s - 0.4 < z['s'] < welt.wuerfel_s + 0.3)]
    schnell = max((z['v'] for z in zustaende), default=0)
    check('Geschwindigkeit (0,15 m/s)', 0.12 <= schnell <= 0.17,
          f'(max {schnell:.2f} m/s)')
    abw = max((z['seite'] for z in fahrt), default=1.0)
    mittel = sum(z['seite'] for z in fahrt) / max(1, len(fahrt))
    check('genau auf der Linie (auch in Kurven)', abw < 0.04,
          f'(groesste Abweichung {abw * 100:.1f} cm, Mittel {mittel * 100:.1f} cm)')
    check('Linie nie verloren', abw < 0.08)

    if GEGNER:   # nur Ausweichen pruefen
        gegner = welt.pose_bei(1.75)
        naechster = min(math.hypot(z['x'] - gegner[0], z['y'] - gegner[1]) for z in zustaende)
        check('anderen Roboter nicht angefahren', naechster > 0.25, f'(naechster Abstand Mitte-Mitte {naechster * 100:.0f} cm)')
        zurueck = [z for z in zustaende if not z['vorwaerts'] and z['v'] > 0.05]
        check('nach Wartezeit ausgewichen (gewendet, faehrt in Gegenrichtung)', len(zurueck) > 20)
        print('\nAlles in Ordnung.' if not fehler else f'\n{fehler} Pruefung(en) fehlgeschlagen.')
        return 1 if fehler else 0

    # Ampel
    rot_vor = [vor(z, welt.ampel_s) for z in hin if z['ampel'] == 'rot']
    if rot_vor:
        ueber = [z for z in hin if z['ampel'] == 'rot' and vor(z, welt.ampel_s) > L - 0.5]
        check('bei Rot nicht ueber die Ampel gefahren', not ueber)
        halt = [vor(z, welt.ampel_s) for z in hin if z['ampel'] == 'rot' and z['v'] == 0]
        check('vor der roten Ampel angehalten', bool(halt), f'({min(halt) * 100:.0f} cm davor)' if halt else '')
        check('bei Gruen weitergefahren', any(z['s'] > welt.ampel_s + 0.1 for z in hin))
    else:
        check('Ampel erreicht', False, '(Simulation zu kurz?)')

    # Zebrastreifen mit Fussgaenger
    am_zebra = [z for z in hin if 0 < vor(z, welt.zebra_s) < 0.6]
    if am_zebra and any(z['s'] > welt.zebra_s + 0.1 for z in hin):
        ueber_mit = [z for z in hin if z['fussgaenger'] and welt.zebra_s - 0.15 < z['s'] < welt.zebra_s + 0.3]
        check('nicht ueber den Zebrastreifen, solange der Fussgaenger da ist', not ueber_mit)
        geschaut = any(z['arm'][0] > 110 for z in am_zebra) and any(z['arm'][0] < 70 for z in am_zebra)
        check('am Zebrastreifen nach links und rechts geschaut (Arm)', geschaut)
        check('Fussgaenger durfte gehen, dann weitergefahren',
              not zustaende[-1]['fussgaenger'] and any(z['s'] > welt.zebra_s + 0.2 for z in hin))
    else:
        check('Zebrastreifen erreicht und ueberquert', False, '(Simulation zu kurz?)')

    # Wuerfel aufheben
    w0 = welt.pose_bei(welt.wuerfel_s)
    nah = []
    for z in hin:
        if z['haelt'] or z['abgelegt']:
            break                      # nur bis zum Greifen pruefen
        if z['wuerfel']:
            dx, dy = z['wuerfel'][0] - z['x'], z['wuerfel'][1] - z['y']
            nah.append(math.cos(z['w']) * dx + math.sin(z['w']) * dy if math.hypot(dx, dy) < 0.4 else 9)
    gegriffen = any(z['haelt'] for z in zustaende)
    check('Wuerfel nicht angefahren', min(nah, default=9) > 0.12,
          f'(naechster Abstand vorne {min(nah, default=9) * 100:.0f} cm)')
    texte = [e['text'] for e in ereignisse]
    check('Hindernis erst genau angeschaut (Kamera)', any(t.startswith('Hindernis gesehen') for t in texte))
    check('Armbewegung selbst berechnet (keine eingelernten Greif-Posen)',
          any(t.startswith('Armbewegung berechnet') for t in texte))
    check('Wuerfel gegriffen', gegriffen)
    versuche = [t for t in texte if t.startswith('Greifversuch')]
    check('Greifversuch gelernt und gemeldet (Erfolg/daneben, Erfolgsquote)', bool(versuche),
          f"({'; '.join(v.split(', Korrektur')[0] for v in versuche)})")
    abgelegt = zustaende[-1]['abgelegt']
    if abgelegt:
        _, seite = welt.s_von(*abgelegt)
        check('Wuerfel neben die Strasse gelegt', seite > 0.1, f'({seite * 100:.0f} cm neben der Linie)')
        check('nach dem Wegraeumen geprueft, ob der Weg frei ist', any(t.startswith('Weg ist frei (geprueft)') for t in texte))
        check('erst dann weitergefahren', any(z['s'] > welt.wuerfel_s + 0.2 for z in hin))
    else:
        check('Wuerfel abgelegt', False)
    print(f'      (Wuerfel lag bei x={w0[0]:.2f}, y={w0[1]:.2f})')

    # Stoppschild
    am_schild = [z for z in hin if 0 < vor(z, welt.schild_s) < 0.8 and z['v'] == 0]
    stand = (am_schild[-1]['zeit'] - am_schild[0]['zeit']) if am_schild else 0
    if any(z['s'] > welt.schild_s + 0.1 for z in hin):
        check('am Stoppschild gehalten (ca. 3 s)', 2.0 <= stand <= 6.0, f'({stand:.1f} s)')
    else:
        check('Stoppschild erreicht', False, '(Simulation zu kurz?)')

    # Einbahnstrasse
    erreicht = [z for z in zustaende if 0 < vor(z, welt.einbahn_s) < 0.8 and z['vorwaerts']]
    if erreicht:
        hinein = [z for z in zustaende if z['vorwaerts'] and 0 < z['s'] - welt.einbahn_s < 0.4]
        check('nicht in die Einbahnstrasse gefahren', not hinein,
              f"(bis {max((z['s'] - welt.einbahn_s for z in hinein), default=0) * 100:.0f} cm hinein)")
        zurueck = [z for z in zustaende if not z['vorwaerts'] and z['v'] > 0.05]
        check('gewendet und in Gegenrichtung weitergefahren', len(zurueck) > 20)
    else:
        check('Einbahnstrasse erreicht', False, '(Simulation zu kurz?)')

    # Kartograf: stimmt seine Position? (Karten-System = Startpunkt der ersten Fahrt = Start im Simulator)
    start = welt.pose_bei(0.0)
    zeiten = np.array([z['zeit'] for z in zustaende])
    fehler_k = []
    for k in karte:
        if 'x' not in k:
            continue
        z = zustaende[int(np.argmin(np.abs(zeiten - k['zeit'])))]
        wahr = K.relativ(start, (z['x'], z['y'], z['w']))
        fehler_k.append((math.hypot(k['x'] - wahr[0], k['y'] - wahr[1]), abs(K.winkel(k['w'] - wahr[2]))))
    if fehler_k:
        f = np.array(fehler_k)
        check('Karte: Position des Roboters stimmt', f[:, 0].max() < 0.10,
              f'(max {f[:, 0].max() * 100:.1f} cm / {math.degrees(f[:, 1].max()):.1f} Grad, '
              f'Mittel {f[:, 0].mean() * 100:.1f} cm, Fahrt {karte[-1].get("fahrten")}, {karte[-1].get("status")})')
    else:
        check('Karte: Kartograf meldet eine Position', False, f"({karte[-1]['status'] if karte else 'keine Meldung'})")
    datei = os.path.join(KARTEN, 'smartcity', 'karte.json')
    try:
        with open(datei) as f:
            info = json.load(f)
        marker = ', '.join(f"{m['name']} ({m['anzahl']}x)" for m in info['marker'])
        check('Karte: Dateien geschrieben (karte.png, wolke.bin, karte.json)',
              all(os.path.exists(os.path.join(KARTEN, 'smartcity', d)) for d in ('karte.png', 'wolke.bin')),
              f"({info['punkte_3d']} 3D-Punkte, Marker: {marker or 'keine'})")
        arten = {m['art'] for m in info['marker']}
        check('Karte: KI-Marker fuer Ampel, Zebrastreifen, Stoppschild', {'ampel', 'zebra', 'stoppschild'} <= arten,
              f'({sorted(arten)})')
    except (OSError, ValueError, KeyError) as e:
        check('Karte: Dateien', False, f'({e})')

    print('\nAlles in Ordnung.' if not fehler else f'\n{fehler} Pruefung(en) fehlgeschlagen. Logs: {LOGS}/sim_*.log')
    return 1 if fehler else 0


if __name__ == '__main__':
    sys.exit(main())
