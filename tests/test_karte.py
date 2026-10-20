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
for d in ('sim', 'lib', 'line_follower', 'kartograf'):
    sys.path.insert(0, os.path.join(HIER, '..', d))
import abspielen    # noqa: E402
import aufnahme     # noqa: E402
import karte as K   # noqa: E402
import kartierer    # noqa: E402
import linie        # noqa: E402
import messfahrt    # noqa: E402
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

# ---------------- Messfahrt: aufzeichnen und wieder lesen (auch wenn die Datei mittendrin abbricht) ----------------
with tempfile.TemporaryDirectory() as ordner:
    datei = os.path.join(ordner, 'a.jsonl.gz')
    a = aufnahme.Aufnahme(datei, {'quelle': 'test', 'cfg': {'lidar_x': 0.0}}, bild_hz=2.0)
    for i in range(200):
        a.scan(1000.0 + i * 0.1, '/scan0', {'stamp': 1000.0 + i * 0.1, 'amin': -math.pi, 'ainc': 0.1, 'rmin': 0.05,
                                           'rmax': 12.0, 'ti': 0.0, 'st': 0.0, 'r': np.full(63, 2.5)})
        a.schreiben({'typ': 'odom', 't': 1000.0 + i * 0.1, 'stamp': 0.0, 'vx': 0.1, 'vy': 0.0, 'wz': 0.0})
    a.bild(1000.0, 1000.0, np.zeros((480, 640, 3), np.uint8))
    a.stopp()
    eintraege = list(aufnahme.lesen(datei))
    scans = [e for e in eintraege if e['typ'] == 'scan']
    check('Aufnahme: alles wieder lesbar', eintraege[0]['typ'] == 'kopf' and len(scans) == 200
          and abs(aufnahme.scan_aus_json(scans[0])['r'][0] - 2.5) < 1e-6 and any(e['typ'] == 'bild' for e in eintraege),
          f'({len(eintraege)} Eintraege, {os.path.getsize(datei) // 1024} KB)')
    with open(datei, 'rb') as f:
        halb = f.read()[:os.path.getsize(datei) // 2]
    with open(datei, 'wb') as f:
        f.write(halb)
    check('Aufnahme: abgebrochene Datei bis zur kaputten Stelle lesbar', 0 < len(list(aufnahme.lesen(datei))) < len(eintraege))

# ---------------- Zeitstempel: Nachrichten kommen gesammelt an (ausgelasteter Rechner) ----------------
u = kartierer.Uhr()
zeiten = [u.zeit(0.0, 100.0 + (i // 6) * 0.3) for i in range(120)]   # ohne Stempel, alle 0,3 s sechs auf einmal
abstaende = np.diff(zeiten[60:])
check('Ohne Zeitstempel: gesammelte Nachrichten werden gleichmaessig verteilt', np.abs(abstaende - 0.05).max() < 0.02,
      f'(Abstand {abstaende.min() * 1000:.0f}..{abstaende.max() * 1000:.0f} ms, gesendet alle 50 ms)')


# ---------------- Fehler, die es am echten Roboter geben kann: Messfahrt in der Simulationswelt + abspielen ----------
def messfahrt_pruefen(name, pruefung=None, grenze=(0.05, 2.0), **fehler):
    """2 Runden fahren (mit dem Fehler), abspielen wie auf dem Roboter. In Runde 2 muss die Karte stimmen
    (gegen die wahre Position, ausgerichtet am Anfang von Runde 2)."""
    t0 = time.time()
    with tempfile.TemporaryDirectory() as ordner:
        datei = os.path.join(ordner, 'f.jsonl.gz')
        messfahrt.erzeugen(datei, runden=2, kamera=False, lidar_strahlen=300, **fehler)
        erg = abspielen.abspielen(datei, kamera=False)
    r = messfahrt.runden_fehler(erg['posen'], erg['wahr'], erg['kopf']['runde_m'])
    kr = erg['kartierer']
    ok = (len(r) == 2 and r[1]['pos_mittel'] < grenze[0] and abs(r[1]['winkel_mittel']) < grenze[1]
          and r[1]['pos_max'] < 0.15)
    extra = ''
    if pruefung:
        ok2, extra = pruefung(kr)
        ok = ok and ok2
    info = (f"(Runde 2: im Mittel {r[1]['pos_mittel'] * 100:.1f} cm / {r[1]['winkel_mittel']:+.1f} Grad, "
            f"max {r[1]['pos_max'] * 100:.1f} cm; {extra}; "
            f"{time.time() - t0:.0f} s)" if len(r) == 2 else '(keine Position)')
    check(name, ok, info)


def vorne_90(kr):
    w = math.degrees(kr.kal.einbau[2])
    warnt = any('LiDAR-Richtung' in x for x in kr.warnungen())
    return kr.kal.einbau_gelernt and abs(w - 90) < 3 and warnt, f'gelernt: vorne {w:+.1f} Grad, Warnung {warnt}'


def ecke(kr):
    x, y, _ = kr.kal.einbau
    return abs(x - 0.12) < 0.03 and abs(y - 0.10) < 0.03, f'gelernt: {x * 100:+.0f} / {y * 100:+.0f} cm (wahr +12 / +10)'


messfahrt_pruefen('Messfahrt: LiDAR "vorne" 90 Grad falsch -> erkannt und herausgerechnet', vorne_90,
                  lidar0_einbau=(0.0, 0.0, 90.0), lidar1_einbau=(-0.12, 0.0, 94.0))
messfahrt_pruefen('Messfahrt: Lagesensor falsch herum -> erkannt und korrigiert',
                  lambda kr: (kr.kal.imu_vorzeichen < 0, f'Vorzeichen {kr.kal.imu_vorzeichen:+.0f}'), imu_vorzeichen=-1.0)
messfahrt_pruefen('Messfahrt: LiDAR gespiegelt -> erkannt und korrigiert',
                  lambda kr: (kr.kal.spiegeln, f'gespiegelt erkannt: {kr.kal.spiegeln}'), lidar_gespiegelt=True)
messfahrt_pruefen('Messfahrt: Odometrie/IMU kommen gesammelt an (0,3 s)', None, stau=0.3)
# ohne Zeitstempel geht es nur ungefaehr (die Position haengt bis zu 0,3 s hinterher)
messfahrt_pruefen('Messfahrt: ... und dazu ohne Zeitstempel (ungenauer)', None, grenze=(0.08, 5.0), stau=0.3, stempel='null')
messfahrt_pruefen('Messfahrt: /odom_raw ohne Geschwindigkeiten (nur Position)', None, odom_twist=False)
messfahrt_pruefen('Messfahrt: Haupt-LiDAR an der Ecke, Wenden auf der Stelle, Aufbau verdeckt 90 Grad', ecke,
                  lidar0_einbau=(0.12, 0.10, 0.0), lidar1_einbau=(-0.12, -0.10, 0.0), lidar_verdeckt=90.0, wenden=True)

# Karte gespeichert, bevor der LiDAR-Einbau gelernt war ('einbau': None) -> Kartograf muss sie wieder laden koennen
# (stuerzte sonst bei JEDEM Start ab, damit ging auch "Neue Karte" nicht mehr)
with tempfile.TemporaryDirectory() as d:
    k1 = K.Karte(d)
    k1.kalibrierung = kartierer.Kalibrierung().speichern()
    k1.speichern()
    k2 = K.Karte(d)
    try:
        ok = k2.laden() and kartierer.Kartierer(k2).kal.einbau == (0.0, 0.0, 0.0)
    except Exception as e:
        ok = False
        print(f'      {e!r}')
    fehler += not ok
    print(f"{'OK  ' if ok else 'FEHLER'} Karte ohne gelernten LiDAR-Einbau speichern und wieder laden")

print('\nAlle Tests bestanden.' if not fehler else f'\n{fehler} Test(s) fehlgeschlagen.')
sys.exit(1 if fehler else 0)
