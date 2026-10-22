#!/usr/bin/env python3
# Fahr-Gehirn im Simulator: viele Runden mit Kreuzungen, OHNE ROS, mit simulierter Uhr.
#
# Es laeuft der ECHTE Code (fahrgehirn/fahrgehirn.py -> line_follower.py, linie.py, lernen.py ...) mit den
# ROS-Attrappen aus tests/attrappen. Kamera, LiDAR, Radzaehler, Lagesensor und Antrieb werden nachgerechnet wie in
# sim/linie_messen.py (Antrieb 'echt' = geschaetzte Werte, NICHT am Roboter gemessen).
#
# Welt: Rechteck 2,2 x 1,4 m (Ecken r = 25 cm) mit einem Steg in der Mitte -> zwei T-Kreuzungen (unten K1, oben K2).
# Fahrplan einer Runde (6 Kreuzungen, jede Richtung zweimal):
#   K1 links, K2 rechts, K1 geradeaus, K2 geradeaus, K1 rechts, K2 links      (ca. 16 m je Runde)
#
# Wahrheit: Der Simulator weiss, wo der Roboter wirklich ist. Er misst selbst (unabhaengig vom Fahr-Gehirn), ob jede
# Kreuzung geklappt hat und wie weit der Roboter neben der Linie war - und vergleicht das mit dem, was das Fahr-Gehirn
# selbst gemessen hat. Kommt der Roboter vom Weg ab, setzt ihn der "Helfer" hinter die Kreuzung zurueck auf den Weg
# (wie ein Mensch in der Halle) und meldet dem Fahr-Gehirn 'fahrplan <nr>'.
#
# Aufruf:  python3 sim/fahrgehirn_sim.py --runden 40                 (Lernstand + Logs in /tmp/fahrgehirn_sim)
#          python3 sim/fahrgehirn_sim.py --runden 20 --nicht_lernen  (Vergleich: feste Startwerte)
#          python3 sim/fahrgehirn_sim.py --runden 3 --hindernis       (Figur steht kurz im Weg: Stopp + Weiterfahrt)
#          --ordner DIR (eigener Speicherort), --weiter (vorhandenen Lernstand weiterverwenden), --antrieb schwer
import argparse
import json
import math
import os
import shutil
import sys
import time as echte_zeit
import types

import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HIER, '..'))
SCHRITT = 0.005
X0, X1, Y0, Y1, R, XM = 0.4, 2.6, 0.4, 1.8, 0.25, 1.5
PLAN = ['links', 'rechts', 'geradeaus', 'geradeaus', 'rechts', 'links']


def _gerade(a, b, s=0.005):
    n = max(2, int(math.dist(a, b) / s))
    return np.linspace(a, b, n, endpoint=False)


def _bogen(cx, cy, w0, w1, s=0.005):
    n = max(2, int(R * abs(w1 - w0) / s))
    w = np.linspace(w0, w1, n, endpoint=False)
    return np.stack([cx + R * np.cos(w), cy + R * np.sin(w)], axis=1)


def kanten():
    """Wege zwischen den Kreuzungen K1 (unten Mitte) und K2 (oben Mitte), je in Fahrtrichtung (Punkte alle 5 mm)."""
    h = math.pi / 2
    links = np.concatenate([   # K1 nach Westen, links herum hoch, oben nach Osten bis K2
        _gerade((XM, Y0), (X0 + R, Y0)), _bogen(X0 + R, Y0 + R, -h, -2 * h),
        _gerade((X0, Y0 + R), (X0, Y1 - R)), _bogen(X0 + R, Y1 - R, math.pi, h),
        _gerade((X0 + R, Y1), (XM, Y1))])
    rechts = np.concatenate([  # K2 nach Osten, rechts herum runter, unten nach Westen bis K1
        _gerade((XM, Y1), (X1 - R, Y1)), _bogen(X1 - R, Y1 - R, h, 0.0),
        _gerade((X1, Y1 - R), (X1, Y0 + R)), _bogen(X1 - R, Y0 + R, 0.0, -h),
        _gerade((X1 - R, Y0), (XM, Y0))])
    mitte = _gerade((XM, Y0), (XM, Y1))
    return {'L': links, 'L_rueck': links[::-1].copy(), 'R': rechts, 'M': mitte}


# Kanten einer Runde: an deren Anfang liegt jeweils die Kreuzung mit der Plan-Nr. (K1, K2, K1, K2, K1, K2)
RUNDE = ['M', 'R', 'L', 'R', 'M', 'L_rueck']


class Route:
    """Der geplante Weg (mehrere Runden hintereinander) mit Fortschritt des Roboters."""

    def __init__(self, runden):
        k = kanten()
        teile = [k['L_rueck']] + [k[n] for _ in range(runden + 2) for n in RUNDE]
        self.knoten_s = []        # Strecke (m) der Kreuzungen entlang der Route
        s0 = 0.0
        for i, t in enumerate(teile):
            if i:
                self.knoten_s.append(s0)
            s0 += len(t) * 0.005
        self.punkte = np.concatenate(teile)
        d = np.diff(np.vstack([self.punkte, self.punkte[-1:] + (self.punkte[-1] - self.punkte[-2])]), axis=0)
        self.richtung = np.arctan2(d[:, 1], d[:, 0])
        self.s = np.arange(len(self.punkte)) * 0.005
        self.i = 0

    def start_pose(self, vor_kreuzung=0.6):
        i = int((self.knoten_s[0] - vor_kreuzung) / 0.005)
        self.i = i
        return [float(self.punkte[i, 0]), float(self.punkte[i, 1]), float(self.richtung[i])]

    def verfolgen(self, x, y):
        """Fortschritt (Index) nachfuehren und seitliche Abweichung (m, + = links) zurueckgeben."""
        a, b = max(0, self.i - 60), min(len(self.punkte), self.i + 400)
        d = np.hypot(self.punkte[a:b, 0] - x, self.punkte[a:b, 1] - y)
        self.i = a + int(np.argmin(d))
        px, py = self.punkte[self.i]
        r = self.richtung[self.i]
        return -(x - px) * math.sin(r) + (y - py) * math.cos(r)

    def pose_bei_s(self, s):
        i = min(len(self.punkte) - 1, int(s / 0.005))
        self.i = i
        return [float(self.punkte[i, 0]), float(self.punkte[i, 1]), float(self.richtung[i])]


def welt_bauen(Welt, welt_modul):
    """Welt aus sim/welt.py, aber mit dem Kreuzungs-Netz statt des Rundkurses (keine Ampel, kein Zebrastreifen)."""
    w = Welt(False, False, False)
    w.schilder, w.zylinder = [], []
    k = kanten()
    w.netz = [np.vstack([k['L'], k['R']]), k['M']]
    h, b = int(welt_modul.HOEHE / welt_modul.AUFLOESUNG), int(welt_modul.BREITE / welt_modul.AUFLOESUNG)
    rng = np.random.default_rng(1)
    img = np.full((h, b, 3), 205, np.uint8)
    img = np.clip(img.astype(np.int16) + rng.normal(0, 5, img.shape).astype(np.int16), 0, 255).astype(np.uint8)
    import cv2
    dicke = int(0.025 / welt_modul.AUFLOESUNG)
    cv2.polylines(img, [w.welt_zu_pixel(w.netz[0]).astype(np.int32)], True, (25, 25, 25), dicke)
    cv2.polylines(img, [w.welt_zu_pixel(w.netz[1]).astype(np.int32)], False, (25, 25, 25), dicke)
    for x0, y0, x1, y1 in w.haeuser:   # Haeuser aus sim/welt.py (alle mind. 20 cm neben dem Netz, LiDAR sieht sie)
        a, c = w.welt_zu_pixel(np.array([[x0, y0], [x1, y1]])).astype(np.int32)
        cv2.rectangle(img, tuple(a), tuple(c), (90, 110, 150), -1)
    w.boden = img
    w._cache = {}
    return w


class SimZeit:
    """Simulierte Uhr fuer alle Module (time.time / monotonic / sleep / strftime)."""

    def __init__(self):
        self.t = 1_000_000.0

    def time(self):
        return self.t

    monotonic = time

    def sleep(self, s):
        pass

    @staticmethod
    def strftime(*a):
        return echte_zeit.strftime(*a)


def scan_nachricht(welt, pose, t, rng):
    r, _ = welt.lidar(pose, n=360, rauschen=0.004, rng=rng, max_r=8.0)
    r = np.where(np.isfinite(r), r, 0.0)
    stempel = types.SimpleNamespace(sec=int(t), nanosec=int((t % 1) * 1e9))
    return types.SimpleNamespace(ranges=r.tolist(), angle_min=-math.pi, angle_increment=2 * math.pi / 360,
                                 angle_max=math.pi - 2 * math.pi / 360, range_min=0.05, range_max=12.0,
                                 header=types.SimpleNamespace(stamp=stempel))


def lauf(a):
    os.environ['SMARTCITY_FAHRGEHIRN'] = os.path.join(a.ordner, 'fahrgehirn.json')
    os.environ['SMARTCITY_FAHRGEHIRN_LOGS'] = os.path.join(a.ordner, 'logs')
    sys.path.insert(0, os.path.join(REPO, 'tests', 'attrappen'))
    sys.path.insert(0, os.path.join(REPO, 'fahrgehirn'))
    sys.path.insert(0, HIER)
    import fahrgehirn as fg
    import gehirn
    import line_follower as lf
    import linie
    import welt as welt_modul
    from antrieb import Antrieb

    uhr = SimZeit()
    for modul in (lf, fg, gehirn):
        modul.time = uhr
    welt = welt_bauen(welt_modul.Welt, welt_modul)
    route = Route(a.runden)
    node = fg.FahrGehirnKnoten.__new__(fg.FahrGehirnKnoten)
    node.ros_jetzt = uhr.time
    fg.FahrGehirnKnoten.__init__(node)
    einst = [lf.Parameter('fahrplan', value=', '.join(PLAN)), lf.Parameter('tiefe_pruefen', value=False),
             lf.Parameter('publish_image', value=False)]
    node.set_parameters(einst)
    node.gehirn.plan = gehirn.Fahrplan(PLAN, node.lern.stand.get('fahrplan_index', 0) if a.weiter else 0)
    node.gehirn.lernen_an = not a.nicht_lernen
    node.tiefe = (0.0, 'aus')
    node.parameter_uebernehmen()
    if node.gehirn.plan.index:
        node.gehirn.umsetzen(0)
    # Was das Fahr-Gehirn selbst misst, mitschreiben (zum Vergleich mit der Wahrheit)
    selbst = []
    protokoll_kreuzung = node.gehirn.protokoll.kreuzung

    def mitschreiben(d):
        selbst.append(dict(d))
        protokoll_kreuzung(d)
    node.gehirn.protokoll.kreuzung = mitschreiben

    motor = Antrieb(a.antrieb)
    rng = np.random.default_rng(a.saat)
    pose = route.start_pose()
    node.gehirn.kommando('start')
    unterwegs, messungen = [], []
    t_bild = t_befehl = t_mess = t_scan = t_auf = uhr.t
    wahr = []                 # Wahrheit je Kreuzung
    offen = None              # Kreuzung, an der er gerade ist (Wahrheit)
    k_naechste = 0            # Index in route.knoten_s
    abw = []                  # (Zeit, Abweichung m) waehrend der Fahrt
    hindernis, hindernis_log = None, []
    kollision = 0
    fortschritt = (uhr.t, 0.0)    # (Zeit, Strecke) des letzten Fortschritts: 30 s ohne -> steckt fest
    haenger = []                  # festgesteckt zwischen Kreuzungen
    runden_ziel = node.lern.stand['runden_alle'] + a.runden
    ende = uhr.t + a.runden * 400
    letzte_ausgabe = echte_zeit.time()
    while uhr.t < ende and node.lern.stand['runden_alle'] < runden_ziel:
        uhr.t += SCHRITT
        t = uhr.t
        vor, quer, dreh = motor.schritt(SCHRITT, t)
        x, y, w = pose
        pose = [x + (vor * math.cos(w) - quer * math.sin(w)) * SCHRITT,
                y + (vor * math.sin(w) + quer * math.cos(w)) * SCHRITT, w + dreh * SCHRITT]
        if t >= t_bild:
            t_bild += 1.0 / 15
            unterwegs.append((t + 0.1, t, tuple(pose)))
        while unterwegs and unterwegs[0][0] <= t:
            _, aufnahme, p = unterwegs.pop(0)
            bild, _ = welt.kamera(p)
            node.on_image(types.SimpleNamespace(img=bild, header=types.SimpleNamespace(
                stamp=types.SimpleNamespace(sec=int(aufnahme), nanosec=int((aufnahme % 1) * 1e9)))))
        if t >= t_mess:
            t_mess += 0.1
            rv, rq, rw = motor.rad
            odom = types.SimpleNamespace(twist=types.SimpleNamespace(twist=types.SimpleNamespace(
                linear=types.SimpleNamespace(x=rv * 0.97, y=rq * 0.97),
                angular=types.SimpleNamespace(z=rw * 1.02 + 0.004))))
            imu = types.SimpleNamespace(angular_velocity=types.SimpleNamespace(
                z=dreh + 0.003 + float(rng.normal(0, 0.01))))
            messungen.append((t + 0.05, odom, imu))
        while messungen and messungen[0][0] <= t:
            _, odom, imu = messungen.pop(0)
            node.on_odom(odom)
            node.on_imu(imu)
        if t >= t_scan:
            t_scan += 0.1
            for i, topic in enumerate(node.p('scan_topics')):
                node.on_scan(scan_nachricht(welt, pose, t - 0.02, rng), topic, i)
        # ---- Hindernis: eine Figur (14 cm hoch, LiDAR sieht sie) steht kurz auf dem Weg vor dem Roboter ----
        if a.hindernis and hindernis is None and offen is None and route.s[route.i] > 1.0 \
                and node.lern.stand['runden_alle'] >= len(hindernis_log) and len(hindernis_log) < a.runden:
            naechster_knoten = route.knoten_s[k_naechste]
            s_fig = route.s[route.i] + 0.6
            if naechster_knoten - s_fig > 0.5 or s_fig - naechster_knoten > 0.5:
                i_vorher = route.i
                fx, fy, _ = route.pose_bei_s(s_fig)
                route.i = i_vorher
                hindernis = {'x': fx, 'y': fy, 'r': 0.025, 'h': 0.14, 'farbe': (40, 40, 160), 'name': 'figur',
                             'seit': t, 'min_abstand': 9.0, 'weg_bei_halt': None}
                welt.zylinder.append(hindernis)
        if hindernis is not None:
            d = math.hypot(pose[0] - hindernis['x'], pose[1] - hindernis['y'])
            hindernis['min_abstand'] = min(hindernis['min_abstand'], d)
            if d < 0.15 + hindernis['r']:
                kollision += 1
            if t - hindernis['seit'] > a.hindernis_dauer:
                welt.zylinder.remove(hindernis)
                hindernis['weg_zeit'] = t
                hindernis['weiter'] = None
                hindernis_log.append(hindernis)
                hindernis = None
        for h in hindernis_log:
            if h.get('weiter') is None and vor > 0.05:
                h['weiter'] = round(t - h['weg_zeit'], 2)
        # ---- Wahrheit: Abweichung, Kreuzungen ----
        if t >= t_auf:
            t_auf += 0.05
            seite = route.verfolgen(pose[0], pose[1])
            s_jetzt = route.s[route.i]
            if vor > 0.05:
                abw.append(abs(seite))
            ks = route.knoten_s[k_naechste]
            if offen is None and s_jetzt > ks - 0.45:
                offen = {'nr': k_naechste, 'plan_pos': k_naechste % len(PLAN), 'gewuenscht': PLAN[k_naechste % len(PLAN)],
                         'gier0': pose[2], 'selbst_vorher': len(selbst), 'max_abw': 0.0,
                         'blinker_vorher': node.blinker.zustand}
            if offen is not None:
                offen['max_abw'] = max(offen['max_abw'], abs(seite))
                if s_jetzt > ks + 0.5:
                    dreh_grad = math.degrees(math.remainder(pose[2] - offen['gier0'], 2 * math.pi))
                    offen.update(gefahren=_richtung(dreh_grad),
                                 drehung=round(dreh_grad), abgekommen=False)
                    offen['ok'] = offen['gefahren'] == offen['gewuenscht']
                    wahr.append(offen)
                    offen = None
                    k_naechste += 1
            if s_jetzt > fortschritt[1] + 0.05 or hindernis is not None:
                fortschritt = (t, s_jetzt)
            fest = t - fortschritt[0] > 30.0
            if fest and offen is None:
                # steht zwischen zwei Kreuzungen (z. B. Linie verloren -> Stopp): Helfer setzt ihn 30 cm weiter
                haenger.append({'s': round(s_jetzt, 2), 'status': node.status_text, 'zeit': round(t - 1_000_000)})
                print(f"  Helfer: steckt fest bei s = {s_jetzt:.2f} m ({node.status_text}) -> 30 cm weiter", flush=True)
                pose = route.pose_bei_s(s_jetzt + 0.3)
                motor, fortschritt = Antrieb(a.antrieb), (t, s_jetzt + 0.3)
                _helfer_setzt(node, linie, unterwegs, messungen)
            elif abs(seite) > 0.12 or fest:
                # vom Weg abgekommen oder an der Kreuzung haengen geblieben: Helfer setzt ihn hinter die Kreuzung
                nr = k_naechste
                if fest:
                    print(f"  Helfer: steckt an Kreuzung {nr % len(PLAN)} fest ({node.status_text})", flush=True)
                if offen is None:
                    offen = {'nr': nr, 'plan_pos': nr % len(PLAN), 'gewuenscht': PLAN[nr % len(PLAN)],
                             'gier0': pose[2], 'selbst_vorher': len(selbst), 'max_abw': abs(seite)}
                offen.update(gefahren='steckt fest' if fest else 'vom Weg', drehung=None, abgekommen=True, ok=False,
                             ort=round(route.s[route.i] - route.knoten_s[nr], 2), status=node.status_text)
                wahr.append(offen)
                offen = None
                k_naechste = nr + 1
                pose = route.pose_bei_s(route.knoten_s[nr] + 0.35)
                motor, fortschritt = Antrieb(a.antrieb), (t, route.knoten_s[nr] + 0.35)
                _helfer_setzt(node, linie, unterwegs, messungen)
                node.gehirn.umsetzen((nr + 1) % len(PLAN))
        if t >= t_befehl:
            t_befehl += 1.0 / node.p('rate')
            node.steuern()
            lin, q, d = node.letzter_cmd
            motor.befehl(lin, q, d, t)
        if echte_zeit.time() - letzte_ausgabe > 30:
            letzte_ausgabe = echte_zeit.time()
            print(f"  ... Runde {node.lern.stand['runden_alle']}/{runden_ziel}, Sim-Zeit {t - 1_000_000:.0f} s",
                  flush=True)
    return node, wahr, selbst, abw, hindernis_log, kollision, haenger


def _helfer_setzt(node, linie, unterwegs, messungen):
    """Wie ein Mensch, der den Roboter hochhebt und woanders hinsetzt: Gedaechtnis und Kreuzungswahl sind weg."""
    unterwegs.clear()
    messungen.clear()
    node.gedaechtnis = linie.Gedaechtnis()
    node.sucher.wahl, node.sucher.ohne_kreuzung = None, 0
    node.lenkung.zuletzt_gesehen = 0.0
    node.letzter_cmd = (0.0, 0.0, 0.0)


def _richtung(grad):
    return 'links' if grad > 45 else 'rechts' if grad < -45 else 'geradeaus'


def bericht(node, wahr, selbst, abw, hindernis_log, kollision, haenger, a):
    print()
    print('=== Wahrheit (Simulator) je 10 Kreuzungs-Durchfahrten ===')
    for i in range(0, len(wahr), 12):
        teil = wahr[i:i + 12]
        ok = sum(w['ok'] for w in teil)
        print(f"  Kreuzungen {i + 1:3d}-{i + len(teil):3d}: {ok}/{len(teil)} richtig, "
              f"vom Weg {sum(w['abgekommen'] for w in teil)}, "
              f"max. Abweichung an Kreuzungen {max(w['max_abw'] for w in teil) * 100:.1f} cm")
    # Selbstmessung vs. Wahrheit
    paare = [(w, selbst[w['selbst_vorher']]) for w in wahr if w['selbst_vorher'] < len(selbst)]
    gleich = sum((w['ok']) == (s['ergebnis'] == 'ok') for w, s in paare)
    print(f"Selbstmessung des Fahr-Gehirns stimmt bei {gleich}/{len(paare)} Kreuzungen mit der Wahrheit "
          f"(ok / nicht ok) ueberein.")
    print(f"Abweichung von der Linie (Wahrheit, waehrend der Fahrt): Mittel {np.mean(abw) * 100:.2f} cm, "
          f"95 % unter {np.percentile(abw, 95) * 100:.1f} cm")
    print(f'Festgesteckt zwischen Kreuzungen (Helfer musste umsetzen): {len(haenger)}x'
          + ''.join(f"\n  s = {h['s']} m: {h['status']}" for h in haenger))
    fest = [w for w in wahr if w.get('gefahren') == 'steckt fest']
    for w in fest:
        print(f"  an Kreuzung {w['plan_pos']} ({w['gewuenscht']}) festgesteckt: {w.get('status')}")
    if a.hindernis:
        for h in hindernis_log:
            print(f"Hindernis: naechster Abstand Robotermitte-Figur {h['min_abstand'] * 100:.0f} cm, "
                  f"weitergefahren {h.get('weiter')} s nach dem Wegnehmen")
        print(f'Kollisionen: {kollision}')
    print()
    print('=== Fortschritt (logs/fahrgehirn/fortschritt.csv, Selbstmessung) ===')
    import auswerten
    auswerten.drucken(node.gehirn.protokoll)


def main():
    ap = argparse.ArgumentParser(description='Fahr-Gehirn im Simulator (viele Runden, ohne ROS)')
    ap.add_argument('--runden', type=int, default=30)
    ap.add_argument('--ordner', default='/tmp/fahrgehirn_sim')
    ap.add_argument('--weiter', action='store_true', help='vorhandenen Lernstand im Ordner weiterverwenden')
    ap.add_argument('--nicht_lernen', action='store_true', help='nur messen, Parameter fest')
    ap.add_argument('--hindernis', action='store_true', help='je Runde einmal eine Figur in den Weg stellen')
    ap.add_argument('--hindernis_dauer', type=float, default=6.0)
    ap.add_argument('--antrieb', default='echt')
    ap.add_argument('--saat', type=int, default=0)
    a = ap.parse_args()
    if not a.weiter and os.path.isdir(a.ordner):
        shutil.rmtree(a.ordner)
    os.makedirs(a.ordner, exist_ok=True)
    start = echte_zeit.time()
    erg = lauf(a)
    bericht(*erg, a)
    with open(os.path.join(a.ordner, 'wahrheit.json'), 'w') as f:
        json.dump({'kreuzungen': [{k: v for k, v in w.items() if k != 'gier0'} for w in erg[1]],
                   'festgesteckt': erg[6]}, f, indent=1, default=str)
    print(f'\nRechenzeit {echte_zeit.time() - start:.0f} s. Lernstand: {a.ordner}/fahrgehirn.json, '
          f'Protokolle: {a.ordner}/logs/')


if __name__ == '__main__':
    main()
