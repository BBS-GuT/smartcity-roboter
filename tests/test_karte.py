#!/usr/bin/env python3
# Prueft Kartierung und Tiefenkamera mit der Simulationswelt (kein Roboter, kein ROS noetig, ca. 20 s).
# Aufruf: python3 tests/test_karte.py
import math
import os
import sys
import tempfile
import time

import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__))
for d in ('sim', 'lib', 'line_follower'):
    sys.path.insert(0, os.path.join(HIER, '..', d))
import karte as K   # noqa: E402
import linie        # noqa: E402
import tiefe        # noqa: E402
from welt import Welt  # noqa: E402

fehler = 0


def check(name, ok, info=''):
    global fehler
    fehler += not ok
    print(f"{'OK  ' if ok else 'FEHLER'} {name} {info}")


W = Welt()
START = W.pose_bei(0.0)          # Kartensystem = Start der ersten Fahrt
KAM = {n: linie.STANDARD[n] for n in ('kamera_hoehe', 'kamera_neigung', 'kamera_fov', 'kamera_x')}


def fahrt(karte, start_s, strecke, rng, bias, schlupf, kamera=False):
    """Faehrt die Strecke ab. Odometrie mit Fehlern (Schlupf, Drehraten-Nullpunkt), LiDAR aus der Welt."""
    lok = K.Lokalisierung(karte)
    s, wahr, abw, t, dt = start_s, W.pose_bei(start_s), [], 0.0, 0.1
    while s < start_s + strecke:
        neu = W.pose_bei(s + 0.015)
        rel = K.relativ(wahr, neu)
        lok.bewegen(rel[0] * schlupf, rel[1], rel[2] + (bias + rng.normal(0, 0.01)) * dt)
        wahr, s = neu, s + 0.015
        r, a = W.lidar(wahr, rng=rng)
        ok = np.isfinite(r) & (r > 0.08)
        lok.scan(np.column_stack([r[ok] * np.cos(a[ok]), r[ok] * np.sin(a[ok])]), t)
        if lok.pose is None and len(lok.puffer) == 3:
            lok.global_suchen()
        if kamera and lok.pose is not None and int(t / dt) % 6 == 0:
            bild, tief = W.kamera(wahr, 0.0, schritt=2)
            xy, f = K.boden_aus_bild(bild, KAM, tiefe_m=tief)
            karte.boden.eintragen(lok.pose, xy, f)
            p, f = K.raum_aus_tiefe(tief, bild, KAM, schritt=2)
            karte.wolke.eintragen(lok.pose, p, f)
        if lok.pose is not None:
            wk = K.relativ(START, wahr)
            abw.append(math.hypot(lok.pose[0] - wk[0], lok.pose[1] - wk[1]))
        t += dt
    return lok, abw


rng = np.random.default_rng(5)
with tempfile.TemporaryDirectory() as ordner:
    t0 = time.time()
    karte = K.Karte(ordner)
    lok, abw = fahrt(karte, 0.0, W.laenge * 1.2, rng, bias=0.003, schlupf=0.97, kamera=True)
    check('Fahrt 1: Position bleibt genau (Odometrie 3 % daneben, Drehrate driftet)', max(abw) < 0.08,
          f'(max {max(abw) * 100:.1f} cm, Mittel {np.mean(abw) * 100:.1f} cm, {time.time() - t0:.0f} s)')
    check('Fahrt 1: Bodenfoto und 3D-Punkte entstanden',
          (karte.boden.anzahl > 0).sum() > 10000 and len(karte.wolke.punkte()[0]) > 20,
          f'({(karte.boden.anzahl > 0).sum()} Bodenpixel, {len(karte.wolke.punkte()[0])} 3D-Wuerfelchen)')
    karte.speichern()
    k2 = K.Karte(ordner)
    check('Karte speichern und laden', k2.laden() and k2.fahrten == 1)
    lok2, abw2 = fahrt(k2, 3.0, 3.0, rng, bias=-0.004, schlupf=1.03)
    check('Fahrt 2: Position in der vorhandenen Karte gefunden (Start woanders)', lok2.pose is not None and k2.fahrten == 2,
          f'({lok2.status})')
    check('Fahrt 2: genau', abw2 and max(abw2) < 0.08, f'(max {max(abw2) * 100:.1f} cm)' if abw2 else '')
    bild, bereich = k2.bild()
    check('2D-Bild der Karte', bild is not None and bild.shape[0] > 100, f'({bild.shape[1]} x {bild.shape[0]} Pixel)')
    ply = k2.ply()
    check('3D-Export (PLY)', ply.startswith(b'ply') and len(ply) > 10000, f'({len(ply) // 1024} KB)')

# ---------------- Zwei LiDARs: zweiter sitzt anders als eingestellt (wie am M3 Pro: vorne/hinten versetzt) ----------
EINBAU = (-0.12, 0.03, math.radians(4.0))      # wahrer Versatz des zweiten LiDARs (unbekannt fuer die Karte)
rng = np.random.default_rng(9)
with tempfile.TemporaryDirectory() as ordner:
    karte = K.Karte(ordner)
    lok = K.Lokalisierung(karte)
    s, wahr, t, abw = 0.0, W.pose_bei(0.0), 0.0, []
    while s < W.laenge * 1.5:
        neu = W.pose_bei(s + 0.015)
        rel = K.relativ(wahr, neu)
        lok.bewegen(rel[0], rel[1], rel[2] + (0.003 + rng.normal(0, 0.01)) * 0.1, t)
        wahr, s = neu, s + 0.015
        scans = []
        for einbau in ((0.0, 0.0, 0.0), EINBAU):
            r, a = W.lidar(K.verknuepfen(wahr, einbau), rng=rng)
            ok = np.isfinite(r) & (r > 0.08) & (r < 7.9)
            # beide LiDARs "glauben", sie saessen in der Robotermitte
            scans.append(np.column_stack([r[ok] * np.cos(a[ok]), r[ok] * np.sin(a[ok])]))
        lok.scan(scans[0], t, weitere={'/scan1': (t, scans[1])})
        wk = K.relativ(START, wahr)
        abw.append(math.hypot(lok.pose[0] - wk[0], lok.pose[1] - wk[1]))
        t += 0.1
    k = lok.einbau['/scan1'].korrektur
    check('Zweiter LiDAR: Einbau selbst gelernt', k is not None and abs(k[0] - EINBAU[0]) < 0.015
          and abs(k[1] - EINBAU[1]) < 0.015 and abs(k[2] - EINBAU[2]) < math.radians(1.0),
          f'(wahr {EINBAU[0] * 100:+.0f} / {EINBAU[1] * 100:+.0f} cm, 4.0 Grad; {lok.einbau["/scan1"].text()})')
    check('Zweiter LiDAR: Karte bleibt genau', max(abw) < 0.08, f'(max {max(abw) * 100:.1f} cm)')
    karte.speichern()
    k2 = K.Karte(ordner)
    k2.laden()
    check('Gelernter Einbau wird mit der Karte gespeichert', k2.einbau.get('/scan1') is not None)

# ---------------- Tiefenkamera: Hindernis im Fahrweg, auch in Kurven ----------------
bm = tiefe.Bodenmodell(KAM)
for s in np.linspace(0.3, 0.8, 8):          # Boden lernen (freie Strecke)
    bm.pruefe(W.kamera(W.pose_bei(s), 0, 2)[1], True)
mit_wuerfel = Welt(mit_fussgaenger=False)
_, d = mit_wuerfel.kamera(mit_wuerfel.pose_bei(mit_wuerfel.wuerfel_s - 0.3), 0, 2)
gerade = [(0.1 * i, 0.0) for i in range(1, 8)]
treffer, obj = bm.pruefe(d, False, gerade)
check('Tiefe: Wuerfel (4,5 cm, unter der LiDAR-Ebene) 30 cm voraus erkannt', bool(treffer) and abs(obj['vor'] - 0.28) < 0.06,
      f"(vor {obj['vor'] * 100:.0f} cm, seitlich {obj['seite'] * 100:+.1f} cm, {obj['hoehe'] * 100:.1f} cm hoch, "
      f"neben der Linie {obj['quer'] * 100:.1f} cm)" if obj else '')
# in der Kurve vor dem Zebrastreifen: Fussgaenger steht rechts NEBEN der Strasse
_, d = W.kamera((2.556, 0.515, 0.947), 0, 2)
kurve = [(0.05, 0.004), (0.085, 0.013), (0.23, 0.096), (0.264, 0.129), (0.312, 0.156), (0.349, 0.191), (0.393, 0.207),
         (0.438, 0.242), (0.462, 0.265)]
check('Tiefe: in der Kurve stoert der Fussgaenger am Rand nicht (Fahrweg folgt der Linie)', bm.pruefe(d, False, kurve)[1] is None)

print('\nAlle Tests bestanden.' if not fehler else f'\n{fehler} Test(s) fehlgeschlagen.')
sys.exit(1 if fehler else 0)
