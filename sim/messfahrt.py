#!/usr/bin/env python3
# Messfahrt ohne ROS erzeugen: der Roboter faehrt in der Simulationswelt (sim/welt.py) Runden, und es entsteht
# eine Aufnahme im selben Format wie auf dem echten Roboter (lib/aufnahme.py). Mit kartograf/abspielen.py kann
# man sie dann auswerten. Dazu: Fehler, die es am echten Roboter geben kann, einzeln einschaltbar (FEHLER unten).
# Die wahre Position steht mit in der Datei ("wahr") -> man kann messen, wie weit die Karte je Runde wegdreht.
#
# Aufruf: python3 sim/messfahrt.py ausgabe.jsonl.gz [runden=4] [lidar0_einbau=0.1,0.08,90] [imu_skala=1.03] ...
import base64
import gzip
import json
import math
import os
import sys

import cv2
import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from welt import Welt  # noqa: E402

FEHLER = {
    'runden': 4,                 # so viele Runden fahren
    'tempo': 0.15,               # m/s (wie der Linienfolger)
    'halle': True,               # grosser Raum statt Waende am Spielfeld
    'halle_rand': 3.0,           # Hallenwaende so weit (m) vom Spielfeld weg
    'halle_haeuser': 2,          # so viele Haeuser in LiDAR-Hoehe
    'stopps': True,              # an der Ampel 3 s halten (Stand -> Nullpunkt des Lagesensors lernen)
    'wenden': False,             # einmal je Runde auf der Stelle ganz herum drehen (wie beim Wenden)
    'wenden_w': 0.8,             # so schnell (rad/s)
    'lidar0_einbau': (0.0, 0.0, 0.0),   # erster LiDAR: x, y (m) neben der Robotermitte, Drehung (Grad)
    'lidar1_einbau': (-0.12, 0.0, 4.0),  # zweiter LiDAR
    'lidar_gespiegelt': False,   # LiDAR zaehlt die Winkel andersherum
    'lidar_hz': 6.0,             # T-mini Plus: 6 Umdrehungen je Sekunde
    'lidar_umlauf': True,        # Strahlen nacheinander (eine Umdrehung = 1/lidar_hz s), sonst alle gleichzeitig
    'lidar_strahlen': 400,       # Strahlen je Umdrehung (T-mini Plus: ca. 670, weniger = schneller gerechnet)
    'lidar_verdeckt': 0.0,       # so viel Grad vom Roboteraufbau verdeckt
    'lidar_max': 12.0,           # Reichweite (m)
    'lidar_latenz': 0.05,        # Scan kommt so viel spaeter an (s)
    'imu_hz': 25.0,
    'imu_skala': 1.0,            # 1.03 = misst 3 % zu viel Drehung
    'imu_vorzeichen': 1.0,       # -1 = falsch herum eingebaut
    'gyro_bias': 0.003,          # Nullpunktfehler (rad/s)
    'odom_hz': 20.0,
    'odom_skala': 0.97,          # Raeder messen 3 % zu kurz
    'odom_w_skala': 1.02,        # Drehung laut Raedern
    'odom_rauschen': 0.0,        # Mecanum-Schlupf, zufaellig (Anteil der Geschwindigkeit)
    'odom_twist': True,          # False: /odom_raw ohne Geschwindigkeiten (nur Position)
    'stempel': 'jetzt',          # Zeitstempel: jetzt | start (Scan: erster Strahl) | null | versatz (andere Uhr)
    'stau': 0.0,                 # Odometrie/IMU kommen gesammelt alle so viele s an (ueberlasteter Rechner)
    'kamera': True,              # Kamerabilder mit aufnehmen (2 Hz)
    'kamera_latenz': 0.3,        # Bild kommt so viel spaeter an (s)
    'seed': 3,
}


def zahl_oder_liste(text):
    if ',' in text:
        return tuple(float(v) for v in text.split(','))
    if text.lower() in ('true', 'false'):
        return text.lower() == 'true'
    try:
        return float(text) if '.' in text or 'e' in text else int(text)
    except ValueError:
        return text


class Bahn:
    """Wahre Bewegung des Roboters: faehrt die Linie ab, haelt an der Ampel, dreht sich evtl. beim Wenden."""

    def __init__(self, welt, f):
        self.welt = welt
        dt = 0.005
        L = welt.laenge
        t, s, phase, warte, gedreht = 0.0, 0.0, 'fahren', 0.0, 0.0
        extra_w = 0.0                     # Drehung zusaetzlich zur Linie (vom Wenden)
        zeiten, posen = [], []
        runde_halt = runde_wende = -1
        while s < f['runden'] * L:
            runde = int(s // L)
            x, y, w = self._linie(s)
            zeiten.append(t)
            posen.append((x, y, w + extra_w))
            if phase == 'fahren':
                if f['stopps'] and runde_halt < runde and (s % L) >= welt.ampel_s:
                    phase, warte, runde_halt = 'halt', 3.0, runde
                elif f['wenden'] and runde_wende < runde and (s % L) >= welt.einbahn_s:
                    phase, warte, gedreht, runde_wende = 'vor_wende', 1.0, 0.0, runde
                else:
                    s += f['tempo'] * dt
            elif phase in ('halt', 'vor_wende', 'nach_wende'):
                warte -= dt
                if warte <= 0:
                    phase = 'wende' if phase == 'vor_wende' else 'fahren'
            elif phase == 'wende':
                schritt = min(f['wenden_w'] * dt, 2 * math.pi - gedreht)
                extra_w += schritt
                gedreht += schritt
                if gedreht >= 2 * math.pi - 1e-9:
                    phase, warte = 'nach_wende', 1.0
            t += dt
        self.t = np.array(zeiten)
        p = np.array(posen)
        self.x, self.y = p[:, 0], p[:, 1]
        self.w = np.unwrap(p[:, 2])
        self.dauer = float(self.t[-1])
        # Geschwindigkeiten (Roboter-System)
        vx = np.gradient(self.x, self.t)
        vy = np.gradient(self.y, self.t)
        self.v = np.cos(self.w) * vx + np.sin(self.w) * vy
        self.quer = -np.sin(self.w) * vx + np.cos(self.w) * vy
        self.dreh = np.gradient(self.w, self.t)
        self.weg = np.concatenate([[0], np.cumsum(np.hypot(np.diff(self.x), np.diff(self.y)))])

    def _punkt(self, s):
        """Punkt auf der Linie bei Strecke s (zwischen den Stuetzpunkten interpoliert)."""
        w = self.welt
        s = s % w.laenge
        i = int(np.searchsorted(w.s_werte, s, side='right') - 1)
        j = (i + 1) % len(w.punkte)
        teil = w.s_werte[j] - w.s_werte[i] if j else w.laenge - w.s_werte[i]
        a = (s - w.s_werte[i]) / max(teil, 1e-9)
        return w.punkte[i] + a * (w.punkte[j] - w.punkte[i])

    def _linie(self, s):
        x, y = self._punkt(s)
        a, b = self._punkt(s - 0.015), self._punkt(s + 0.015)
        return float(x), float(y), math.atan2(b[1] - a[1], b[0] - a[0])

    def pose(self, t):
        t = min(max(t, 0.0), self.dauer)
        return (float(np.interp(t, self.t, self.x)), float(np.interp(t, self.t, self.y)),
                float(np.interp(t, self.t, self.w)))

    def werte(self, t):
        t = min(max(t, 0.0), self.dauer)
        return float(np.interp(t, self.t, self.v)), float(np.interp(t, self.t, self.quer)), \
            float(np.interp(t, self.t, self.dreh))


def erzeugen(datei, **aenderungen):
    """Messfahrt erzeugen und als Aufnahme speichern. Rueckgabe: verwendete Einstellungen (dict)."""
    f = dict(FEHLER)
    f.update(aenderungen)
    rng = np.random.default_rng(f['seed'])
    welt = Welt(mit_einbahn=False, mit_wuerfel=False, mit_fussgaenger=False, halle=f['halle'],
                halle_rand=f['halle_rand'], halle_haeuser=f['halle_haeuser'])
    bahn = Bahn(welt, f)
    ereignisse = []           # (empfangszeit, eintrag)
    T0 = 1000.0               # Startzeit (wie eine Uhrzeit), damit "0" als fehlender Zeitstempel erkennbar bleibt

    def stempel(t, art=None):
        art = art or f['stempel']
        if art == 'null':
            return 0.0
        if art == 'versatz':
            return T0 + t - 1000.0 + 5000.0
        return T0 + t

    def stau(t):
        return math.ceil(t / f['stau']) * f['stau'] if f['stau'] > 0 else t

    # Odometrie
    ox = oy = ow = 0.0
    t = 0.0
    while t < bahn.dauer:
        v, q, w = bahn.werte(t)
        vx = v * f['odom_skala'] * (1 + rng.normal(0, f['odom_rauschen']))
        vy = q * f['odom_skala'] + abs(v) * rng.normal(0, f['odom_rauschen'])
        wz = w * f['odom_w_skala'] + 0.004
        dt = 1 / f['odom_hz']
        ox += (vx * math.cos(ow) - vy * math.sin(ow)) * dt
        oy += (vx * math.sin(ow) + vy * math.cos(ow)) * dt
        ow += wz * dt
        e = {'typ': 'odom', 'stamp': stempel(t), 'x': ox, 'y': oy, 'w': ow}
        e.update({'vx': vx, 'vy': vy, 'wz': wz} if f['odom_twist'] else {'vx': 0.0, 'vy': 0.0, 'wz': 0.0})
        ereignisse.append((stau(t + 0.01 + abs(rng.normal(0, 0.003))), e))
        t += dt
    # Lagesensor
    t = 0.0
    while t < bahn.dauer:
        _, _, w = bahn.werte(t)
        gz = f['imu_vorzeichen'] * f['imu_skala'] * w + f['gyro_bias'] + rng.normal(0, 0.01)
        ereignisse.append((stau(t + 0.005 + abs(rng.normal(0, 0.002))),
                           {'typ': 'imu', 'stamp': stempel(t), 'g': [0.0, 0.0, gz], 'a': [0.0, 0.0, 9.81]}))
        t += 1 / f['imu_hz']
    # LiDARs
    umlauf = 1.0 / f['lidar_hz'] if f['lidar_umlauf'] else 0.0
    for i, (name, einbau) in enumerate((('/scan0', f['lidar0_einbau']), ('/scan1', f['lidar1_einbau']))):
        t = 0.3 + i * 0.07
        while t < bahn.dauer:
            r, winkel = welt.lidar_umlauf(lambda tt: bahn.pose(tt), t, einbau, umlauf, n=int(f['lidar_strahlen']),
                                          gespiegelt=f['lidar_gespiegelt'], verdeckt_deg=f['lidar_verdeckt'],
                                          rng=rng, max_r=f['lidar_max'])
            st = T0 + t - umlauf if f['stempel'] == 'start' else stempel(t)   # 'start': Zeit des ersten Strahls
            mm = np.where(np.isfinite(r), np.round(r * 1000), 0).clip(0, 65000).astype(int)
            ereignisse.append((t + f['lidar_latenz'] + abs(rng.normal(0, 0.01)), {
                'typ': 'scan', 'name': name, 'stamp': st, 'amin': float(winkel[0]),
                'ainc': float(winkel[1] - winkel[0]), 'rmin': 0.05, 'rmax': f['lidar_max'],
                'ti': umlauf / len(r) if umlauf else 0.0, 'st': umlauf, 'r': mm.tolist()}))
            t += 1.0 / f['lidar_hz']
    # Kamera (2 Hz, 320 x 240) + KI-Meldung "Kamera schaut nach vorne"
    if f['kamera']:
        t = 0.5
        while t < bahn.dauer:
            bild, _ = welt.kamera(bahn.pose(t), 0.0, schritt=2)
            ok, jpg = cv2.imencode('.jpg', bild, [cv2.IMWRITE_JPEG_QUALITY, 70])
            ereignisse.append((t + f['kamera_latenz'], {'typ': 'bild', 'stamp': T0 + t,
                                                        'jpg': base64.b64encode(jpg.tobytes()).decode()}))
            t += 0.5
    t = 0.0
    while t < bahn.dauer:
        ereignisse.append((t, {'typ': 'ki', 'daten': {'kamera_ok': True}}))
        x, y, w = bahn.pose(t)
        ereignisse.append((t, {'typ': 'wahr', 'x': x, 'y': y, 'w': w, 'weg': float(np.interp(t, bahn.t, bahn.weg))}))
        t += 0.1
    ereignisse.sort(key=lambda e: e[0])
    kopf = {'typ': 'kopf', 'zeit': T0, 'version': 1, 'quelle': 'messfahrt.py', 'runde_m': welt.laenge,
            'start': list(welt.pose_bei(0.0)),
            'fehler': {k: (list(v) if isinstance(v, tuple) else v) for k, v in f.items()},
            'cfg': {'scan_topics': ['/scan0', '/scan1'], 'scan_front_deg': [0.0, 0.0], 'lidar_x': 0.0}}
    os.makedirs(os.path.dirname(os.path.abspath(datei)), exist_ok=True)
    with gzip.open(datei, 'wt', compresslevel=3) as aus:
        aus.write(json.dumps(kopf) + '\n')
        for t, e in ereignisse:
            e['t'] = T0 + t
            aus.write(json.dumps(e, separators=(',', ':')) + '\n')
    return f


def runden_fehler(schaetzung, wahr, runde_m, anpassen_m=2.0, ab_m=None):
    """Wie gut stimmt die geschaetzte Position (Karte) mit der wahren ueberein, Runde fuer Runde?
    schaetzung: [(t, x, y, w)] (Karte), wahr: [(t, x, y, w, weg)] (Welt). Die Karte hat ein eigenes System:
    es wird auf anpassen_m Metern ab Strecke ab_m (Standard: Anfang der 2. Runde, dann ist das Selbst-Lernen
    der ersten Runde vorbei) auf die Welt gelegt (Drehung + Verschiebung). Danach zaehlt jede Abweichung.
    Rueckgabe: Liste je Runde: dict runde, pos_mittel, pos_max (m), winkel_mittel, winkel_max (Grad)."""
    if len(schaetzung) < 10:
        return []
    s = np.array(schaetzung, dtype=np.float64)
    w = np.array(wahr, dtype=np.float64)
    wx = np.interp(s[:, 0], w[:, 0], w[:, 1])
    wy = np.interp(s[:, 0], w[:, 0], w[:, 2])
    ww = np.interp(s[:, 0], w[:, 0], np.unwrap(w[:, 3]))
    weg = np.interp(s[:, 0], w[:, 0], w[:, 4])
    if ab_m is None:
        ab_m = runde_m if weg.max() > 1.6 * runde_m else 0.0
    start = ab_m if ab_m else weg[0]
    auswahl = (weg >= start) & (weg < start + anpassen_m)
    # Drehung + Verschiebung (kleinste Quadrate), die die Karte auf die Welt legt
    a = np.column_stack([s[auswahl, 1], s[auswahl, 2]])
    b = np.column_stack([wx[auswahl], wy[auswahl]])
    am, bm = a.mean(0), b.mean(0)
    h = (a - am).T @ (b - bm)
    dreh = math.atan2(h[0, 1] - h[1, 0], h[0, 0] + h[1, 1])
    c, si = math.cos(dreh), math.sin(dreh)
    ex = c * (s[:, 1] - am[0]) - si * (s[:, 2] - am[1]) + bm[0]
    ey = si * (s[:, 1] - am[0]) + c * (s[:, 2] - am[1]) + bm[1]
    pos = np.hypot(ex - wx, ey - wy)
    # Winkelfehler: Abweichung zur ersten Runde (der feste Einbauwinkel faellt so heraus)
    dw = np.degrees((s[:, 3] + dreh - ww + math.pi) % (2 * math.pi) - math.pi)
    dw = dw - np.median(dw[auswahl])
    dw = (dw + 180) % 360 - 180
    aus = []
    for k in range(int(weg.max() // runde_m) + 1):
        m = (weg >= k * runde_m) & (weg < (k + 1) * runde_m)
        if m.sum() < 5:
            continue
        aus.append({'runde': k + 1, 'pos_mittel': float(pos[m].mean()), 'pos_max': float(pos[m].max()),
                    'winkel_mittel': float(dw[m].mean()), 'winkel_max': float(np.abs(dw[m]).max())})
    return aus


def runden_text(liste):
    return '\n'.join(f"  Runde {r['runde']}: Position im Mittel {r['pos_mittel'] * 100:5.1f} cm (max {r['pos_max'] * 100:5.1f}),"
                     f" Winkel {r['winkel_mittel']:+6.1f} Grad (max {r['winkel_max']:5.1f})" for r in liste)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__ or 'Aufruf: python3 sim/messfahrt.py ausgabe.jsonl.gz [name=wert ...]')
    werte = {}
    for a in sys.argv[2:]:
        k, v = a.split('=', 1)
        if k not in FEHLER:
            sys.exit(f'unbekannt: {k} (moeglich: {", ".join(FEHLER)})')
        werte[k] = zahl_oder_liste(v)
    f = erzeugen(sys.argv[1], **werte)
    print(f'Messfahrt geschrieben: {sys.argv[1]} ({os.path.getsize(sys.argv[1]) / 1e6:.1f} MB)')
