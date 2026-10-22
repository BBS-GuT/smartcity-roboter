#!/usr/bin/env python3
# Messfahrt abspielen (OHNE ROS, z. B. am Laptop): rechnet eine Aufnahme (Panel -> Karte -> "Messfahrt
# aufzeichnen") noch einmal genau so durch wie der Kartograf und sagt, was nicht passt.
#
# Aufruf:  python3 kartograf/abspielen.py karten/aufnahmen/smartcity_20261019_101500.jsonl.gz
#          --ausgabe ordner      Bilder und Karte dorthin (Standard: neben der Aufnahme, Ordner <name>_auswertung)
#          --setze name=wert     Einstellung ausprobieren, z. B. --setze scan_front_deg=[90,90]
#                                oder --setze scan_spiegeln=[true,true] oder --setze selbst_kalibrieren=false
#          --ohne-kamera         Bodenfoto weglassen (schneller)
#          --kurz                nur die wichtigsten Zeilen (fuer Vergleiche)
# Ergebnis: Text (Diagnose) + karte.png (Karte mit gefahrenem Weg) + diagnose.png (Abgleich ueber die Zeit)
import argparse
import base64
import json
import math
import os
import sys
import time

import cv2
import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for d in ('lib', 'line_follower', 'sim'):
    sys.path.insert(0, os.path.join(REPO, d))
import aufnahme as A     # noqa: E402
import karte as K        # noqa: E402
import kartierer as KR   # noqa: E402

KAMERA_NAMEN = ('kamera_hoehe', 'kamera_neigung', 'kamera_fov', 'kamera_x')


def kamera_cfg(cfg):
    try:
        import linie
        k = {n: linie.STANDARD[n] for n in KAMERA_NAMEN}
    except Exception:
        k = {'kamera_hoehe': 0.22, 'kamera_neigung': 32.0, 'kamera_fov': 70.0, 'kamera_x': 0.12}
    k.update({n: cfg[n] for n in KAMERA_NAMEN if n in cfg})
    k['arm_basis_x'] = cfg.get('arm_basis_x', 0.05)
    return k


class Statistik:
    """Was kam wie oft, wie spaet, wie gleichmaessig an?"""

    def __init__(self):
        self.t = {}           # topic -> Liste Empfangszeiten
        self.stamp = {}       # topic -> Liste Zeitstempel
        self.scan_info = {}   # topic -> dict
        self.verdeckt = {}    # topic -> Zaehler je 5-Grad-Sektor (Messung < 0.2 m oder keine)
        self.odom = {'twist': 0, 'pose': 0, 'n': 0}
        self.imu_g = []
        self.imu_a = []

    def neu(self, topic, t, stamp):
        self.t.setdefault(topic, []).append(t)
        self.stamp.setdefault(topic, []).append(stamp or 0.0)

    def scan(self, name, d):
        r = d['r']
        s = self.scan_info.setdefault(name, {'n': 0, 'strahlen': [], 'gueltig': [], 'ti': d.get('ti', 0.0),
                                             'st': d.get('st', 0.0), 'amin': d['amin'], 'ainc': d['ainc'],
                                             'rmax': d.get('rmax'), 'weit': []})
        s['n'] += 1
        if s['n'] % 5:
            return
        ok = np.isfinite(r) & (r > 0)
        s['strahlen'].append(len(r))
        s['gueltig'].append(float(ok.mean()))
        if ok.any():
            s['weit'].append(float(np.percentile(r[ok], 90)))
        a = np.degrees(d['amin'] + np.arange(len(r)) * d['ainc'])
        sektor = (np.round(a / 5).astype(int)) % 72
        nah = ~ok | (r < 0.2)
        z = self.verdeckt.setdefault(name, np.zeros((2, 72)))
        np.add.at(z[0], sektor, nah)
        np.add.at(z[1], sektor, 1)

    def text(self):
        zeilen = ['Nachrichten:']
        for n in sorted(self.t):
            t = np.array(self.t[n])
            if len(t) < 3:
                continue
            dt = np.diff(t)
            st = np.array(self.stamp[n])
            hz = (len(t) - 1) / max(1e-6, t[-1] - t[0])
            stau = float((dt < 0.003).mean())
            z = f'  {n:12s} {len(t):6d} x  {hz:5.1f} Hz  Luecken bis {dt.max():.2f} s'
            if stau > 0.2:
                z += f'  ACHTUNG {stau:.0%} kommen gesammelt an (Rechner ausgelastet?)'
            if (st > 0).mean() < 0.5:
                z += '  keine Zeitstempel'
            else:
                v = t[st > 0] - st[st > 0]
                z += f'  Stempel->Ankunft {np.median(v) * 1000:+.0f} ms (Streuung {np.std(v) * 1000:.0f} ms)'
            zeilen.append(z)
        o = self.odom
        if o['n']:
            zeilen.append(f"  Odometrie: Geschwindigkeiten in {o['twist'] / o['n']:.0%}, Position aendert sich in "
                          f"{o['pose'] / o['n']:.0%} der Nachrichten")
            if o['twist'] == 0:
                zeilen.append('  ACHTUNG /odom_raw ohne Geschwindigkeiten (twist) - der Kartograf nimmt die Positionen')
        if self.imu_a:
            a = np.median(np.array(self.imu_a), axis=0)
            zeilen.append(f'  Lagesensor: Beschleunigung im Mittel x {a[0]:+.1f}, y {a[1]:+.1f}, z {a[2]:+.1f} m/s^2'
                          + ('  (z negativ: steht auf dem Kopf?)' if a[2] < -5 else ''))
        zeilen.append('LiDAR:')
        for n, s in sorted(self.scan_info.items()):
            if not s['strahlen']:
                continue
            z = (f"  {n}: {int(np.median(s['strahlen']))} Strahlen, {math.degrees(s['ainc']):.2f} Grad Schritt, ab "
                 f"{math.degrees(s['amin']):.0f} Grad, gueltig {np.mean(s['gueltig']):.0%}, weit (90 %) "
                 f"{np.median(s['weit']) if s['weit'] else 0:.1f} m, time_increment {s['ti'] * 1e3:.3f} ms, "
                 f"scan_time {s['st']:.3f} s")
            zeilen.append(z)
            v = self.verdeckt.get(n)
            if v is not None and v[1].sum():
                anteil = v[0] / np.maximum(v[1], 1)
                zu = np.nonzero(anteil > 0.8)[0]
                if len(zu):
                    zeilen.append(f'    verdeckt/nah (<20 cm) meistens: {bereiche(zu * 5)} (Grad im LiDAR-System)')
        return '\n'.join(zeilen)


def ausrichten(a, b):
    """Punktfolge a (N,2) so drehen und verschieben, dass sie am besten auf b liegt. Rueckgabe: Abstaende (N,)."""
    am, bm = a.mean(0), b.mean(0)
    h = (a - am).T @ (b - bm)
    w = math.atan2(h[0, 1] - h[1, 0], h[0, 0] + h[1, 1])
    c, s = math.cos(w), math.sin(w)
    q = (a - am) @ np.array([[c, s], [-s, c]]) + bm
    return np.hypot(*(q - b).T)


def bereiche(grad):
    """[0, 5, 10, 200, 205] -> '0..10, 200..205'"""
    teile, start, letzt = [], None, None
    for g in sorted(int(x) for x in grad):
        if start is None:
            start = letzt = g
        elif g - letzt <= 5:
            letzt = g
        else:
            teile.append((start, letzt))
            start = letzt = g
    if start is not None:
        teile.append((start, letzt))
    return ', '.join(f'{(a + 180) % 360 - 180}..{(b + 180) % 360 - 180}' for a, b in teile)


def abspielen(datei, setze=None, kamera=True, ordner=None):
    """Aufnahme durch den Kartierer schicken. Rueckgabe: dict mit allem fuer die Auswertung."""
    kopf, cfg = {}, {}
    karte = K.Karte(ordner or '/nicht/speichern')
    kr = None
    stat = Statistik()
    wahr, posen, live = [], [], []
    naechster = naechstes_bild = None
    bild, ki, suche_bei = None, (0.0, {}), 0.0
    bilder = [0, 0, {}]     # eingetragen, verworfen, Gruende
    k_cfg = None
    for e in A.lesen(datei):
        typ = e.get('typ')
        if typ == 'kopf':
            kopf = e
            cfg = dict(e.get('cfg') or {})
            cfg.update(setze or {})
            k_cfg = kamera_cfg(cfg)
            kr = KR.Kartierer(karte, cfg)
            continue
        if kr is None:
            kr = KR.Kartierer(karte, setze)
            k_cfg = kamera_cfg({})
        t = e['t']
        if naechster is None:
            naechster = naechstes_bild = t
        while t >= naechster:            # wie die Zeitgeber im Kartografen
            if kr.verarbeiten(naechster) and naechster > suche_bei:
                kr.global_suchen()
                suche_bei = naechster + 5.0
            p = kr.roboter_pose_bei()
            if p is not None:
                posen.append((naechster, *p))
            naechster += 0.2
        while kamera and t >= naechstes_bild:
            naechstes_bild += 0.5
            if bild is None:
                continue
            gier = 0.0
            if ki[0] and t - ki[0] < 1.0 and not ki[1].get('kamera_ok', True):
                gier = ki[1].get('kamera_gier')
            pose, grund = kr.bild_pose(bild[0], bild[1])
            if pose is None or gier is None:
                bilder[1] += 1
                g = grund or 'Arm schaut irgendwohin'
                bilder[2][g] = bilder[2].get(g, 0) + 1
            else:
                bgr = cv2.imdecode(np.frombuffer(base64.b64decode(bild[2]), np.uint8), cv2.IMREAD_COLOR)
                xy, farben = K.boden_aus_bild(bgr, k_cfg, gier)
                karte.boden.eintragen(pose, xy, farben)
                bilder[0] += 1
            bild = None
        if typ == 'scan':
            d = A.scan_aus_json(e)
            stat.neu(e['name'], t, e.get('stamp'))
            stat.scan(e['name'], d)
            kr.scan(t, e['name'], d)
        elif typ == 'odom':
            stat.neu('odom', t, e.get('stamp'))
            stat.odom['n'] += 1
            stat.odom['twist'] += abs(e.get('vx', 0)) + abs(e.get('vy', 0)) + abs(e.get('wz', 0)) > 1e-5
            kr.odom(t, e)
            pose = (e.get('x'), e.get('y'), e.get('w'))
            if stat.odom.get('alt') is not None and pose[0] is not None and pose != stat.odom['alt']:
                stat.odom['pose'] += 1
            stat.odom['alt'] = pose
        elif typ == 'imu':
            stat.neu('imu', t, e.get('stamp'))
            stat.imu_g.append(e['g'])
            if e.get('a'):
                stat.imu_a.append(e['a'])
            kr.imu(t, e)
        elif typ == 'bild':
            stat.neu('kamera', t, e.get('stamp'))
            bild = (t, e.get('stamp'), e['jpg'])
        elif typ == 'ki':
            ki = (t, e.get('daten') or {})
        elif typ == 'wahr':
            wahr.append((t, e['x'], e['y'], e['w'], e.get('weg', 0.0)))
        elif typ == 'pose':
            p = e.get('daten') or {}
            if 'x' in p:
                live.append((t, p['x'], p['y'], p['w']))
    return {'kopf': kopf, 'kartierer': kr, 'karte': karte, 'stat': stat, 'wahr': wahr, 'posen': posen,
            'live': live, 'bilder': bilder}


def diagnose_text(erg, kurz=False):
    kr, stat = erg['kartierer'], erg['stat']
    zeilen = []
    if erg['wahr'] and erg['kopf'].get('runde_m'):
        import messfahrt
        r = messfahrt.runden_fehler(erg['posen'], erg['wahr'], erg['kopf']['runde_m'])
        zeilen.append(messfahrt.runden_text(r))
    if kr is None:
        return 'Aufnahme leer oder kaputt.'
    d = np.array(kr.diagnose) if kr.diagnose else np.zeros((0, 5))
    sicher = float(d[:, 2].mean()) if len(d) else 0.0
    kal = kr.kal
    zeilen.append(f'  Abgleich sicher: {sicher:.0%} von {len(d)} Scans, Guete im Mittel '
                  f'{np.median(d[:, 1]) if len(d) else 0:.0%}; {kal.text()}; {kr.lok.einbau_text()}')
    if kurz:
        for w in kr.warnungen():
            zeilen.append('  ! ' + w)
        return '\n'.join(zeilen)
    zeilen.insert(0, f"Aufnahme: {erg['kopf'].get('quelle', '?')}, "
                     f"{time.strftime('%d.%m.%Y %H:%M', time.localtime(erg['kopf'].get('zeit', 0)))}")
    zeilen.append(stat.text())
    zeilen.append('Zeitstempel (so rechnet der Kartograf): ' +
                  ', '.join(f'{n}: {u.art}' for n, u in sorted(kr.uhren.items())))
    zeilen.append('Lokalisierung:')
    if len(d):
        t0 = d[0, 0]
        luecke, start = 0.0, None
        for z in d:
            if not z[2]:
                start = z[0] if start is None else start
                luecke = max(luecke, z[0] - start)
            else:
                start = None
        zeilen.append(f'  laengste unsichere Zeit {luecke:.1f} s, weite Suche benutzt in {(d[:, 3] > 0).mean():.0%}')
        for m in range(int((d[-1, 0] - t0) // 60) + 1):
            s = d[(d[:, 0] - t0 >= m * 60) & (d[:, 0] - t0 < (m + 1) * 60)]
            if len(s):
                zeilen.append(f'  Minute {m + 1}: sicher {s[:, 2].mean():.0%}, Guete {np.median(s[:, 1]):.0%}, '
                              f'Punkte je Scan {np.median(s[:, 4]):.0f}')
    zeilen.append(f'  Status am Ende: {kr.lok.status}, Fahrten in der Karte {kr.karte.fahrten}')
    zeilen.append('Selbstkalibrierung (aus den sicheren Abgleichen):')
    dg = kal.ergebnis.get('drehung')
    if dg:
        zeilen.append(f"  Drehung: LiDAR dreht sich {dg['skala']:.3f} mal so viel wie der Lagesensor misst "
                      f"(+-{dg['fehler']:.3f}), Nullpunkt {math.degrees(dg['bias']):+.2f} Grad/s, {dg['n']} Proben")
    else:
        zeilen.append('  Drehung: zu wenig sichere Abgleiche beim Drehen')
    eb = kal.ergebnis.get('einbau')
    if eb:
        zeilen.append(f"  Haupt-LiDAR: 'vorne' liegt bei {math.degrees(eb['w']):+.1f} Grad (+-{math.degrees(eb['fehler_w']):.1f}), "
                      f"sitzt {eb['x'] * 100:+.1f} / {eb['y'] * 100:+.1f} cm (+-{eb['fehler_ort'] * 100:.1f}) "
                      f"neben der Robotermitte, Raeder messen {eb['odom_skala']:.1%} der Strecke ({eb['n']} Proben)")
    else:
        zeilen.append('  Haupt-LiDAR: zu wenig sichere Abgleiche beim Fahren')
    u = kr.drehpruefung.urteil()
    if u:
        r_imu, r_odo = u
        zeilen.append('  Scan gegen Scan (ohne Karte): Scan dreht sich ' +
                      (f'{r_imu:+.2f} mal so viel wie der Lagesensor' if r_imu is not None else '? (Lagesensor)') + ', ' +
                      (f'{r_odo:+.2f} mal so viel wie die Raeder' if r_odo is not None else '? (Raeder)') +
                      '  (+1 = passt, -1 = andersherum)')
    for t, text in kal.meldungen:
        zeilen.append(f'  gelernt: {text}')
    b = erg['bilder']
    if b[0] or b[1]:
        zeilen.append(f'Bodenfoto: {b[0]} Bilder eingetragen, {b[1]} verworfen ' +
                      ', '.join(f'{k}: {v}' for k, v in b[2].items()))
    if len(erg['live']) > 10 and len(erg['posen']) > 10:
        # die Aufnahme beginnt mitten in der Fahrt: Abspielen faengt eine eigene Karte an -> erst aufeinanderlegen
        lv = np.array(erg['live'])
        po = np.array(erg['posen'])
        lv = lv[(lv[:, 0] >= po[0, 0]) & (lv[:, 0] <= po[-1, 0])]
        if len(lv) > 10:
            a = np.column_stack([np.interp(lv[:, 0], po[:, 0], po[:, 1]), np.interp(lv[:, 0], po[:, 0], po[:, 2])])
            rest = ausrichten(a, lv[:, 1:3])
            zeilen.append(f'Vergleich mit dem, was der Roboter live gerechnet hat (aufeinandergelegt): Abstand im Mittel '
                          f'{rest.mean() * 100:.0f} cm, max {rest.max() * 100:.0f} cm (gross = Abspielen rechnet anders)')
    w = kr.warnungen()
    zeilen.append('Hinweise:' if w else 'Hinweise: keine')
    for x in w:
        zeilen.append('  ! ' + x)
    return '\n'.join(zeilen)


def bilder_schreiben(erg, ordner):
    os.makedirs(ordner, exist_ok=True)
    karte = erg['karte']
    bild, bereich = karte.bild()
    if bild is not None:
        x0, y0, x1, y1 = bereich
        a = karte.boden.aufl

        def px(x, y):
            return int((x - x0) / a), int((y1 - y) / a)
        for i in range(1, len(erg['posen'])):
            p, q = erg['posen'][i - 1], erg['posen'][i]
            if math.hypot(p[1] - q[1], p[2] - q[2]) < 0.3:
                cv2.line(bild, px(p[1], p[2]), px(q[1], q[2]), (230, 120, 40), 1)
        cv2.imwrite(os.path.join(ordner, 'karte.png'), bild)
    d = np.array(erg['kartierer'].diagnose) if erg['kartierer'] and erg['kartierer'].diagnose else None
    if d is not None and len(d) > 2:
        b, h = 1200, 300
        img = np.full((h, b, 3), 255, np.uint8)
        t0, t1 = d[0, 0], d[-1, 0]
        xs = ((d[:, 0] - t0) / max(1e-6, t1 - t0) * (b - 60) + 50).astype(int)
        ys = (h - 30 - d[:, 1] * (h - 60)).astype(int)
        for g in (0.0, 0.35, 0.5, 1.0):
            y = int(h - 30 - g * (h - 60))
            cv2.line(img, (50, y), (b - 10, y), (220, 220, 220), 1)
            cv2.putText(img, f'{g:.0%}', (5, y + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (90, 90, 90), 1)
        for x, y, s in zip(xs, ys, d[:, 2]):
            cv2.circle(img, (x, y), 1, (60, 160, 60) if s else (40, 40, 220), -1)
        cv2.putText(img, 'Guete des Scan-Abgleichs ueber die Zeit (gruen = sicher, rot = unsicher)', (50, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (40, 40, 40), 1)
        cv2.putText(img, f'{t1 - t0:.0f} s', (b - 60, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (90, 90, 90), 1)
        cv2.imwrite(os.path.join(ordner, 'diagnose.png'), img)


def wert(text):
    try:
        return json.loads(text)
    except ValueError:
        return text


def main():
    ap = argparse.ArgumentParser(description='Messfahrt abspielen und auswerten (ohne ROS)')
    ap.add_argument('datei')
    ap.add_argument('--ausgabe', default=None)
    ap.add_argument('--setze', action='append', default=[], help='name=wert, z. B. scan_front_deg=[90,90]')
    ap.add_argument('--ohne-kamera', action='store_true')
    ap.add_argument('--kurz', action='store_true')
    args = ap.parse_args()
    setze = {}
    for s in args.setze:
        k, v = s.split('=', 1)
        setze[k] = wert(v)
    t0 = time.time()
    erg = abspielen(args.datei, setze, kamera=not args.ohne_kamera)
    print(diagnose_text(erg, args.kurz))
    ordner = args.ausgabe or (args.datei.split('.jsonl')[0] + '_auswertung')
    bilder_schreiben(erg, ordner)
    if not args.kurz:
        print(f'Bilder: {ordner}/karte.png, {ordner}/diagnose.png  ({time.time() - t0:.0f} s gerechnet)')


if __name__ == '__main__':
    main()
