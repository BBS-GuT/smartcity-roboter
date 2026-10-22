#!/usr/bin/env python3
# Arm-Masse aus Yahbooms Robotermodell (URDF) lesen - ohne Zusatzpakete.
#
# URDF = "Unified Robot Description Format": eine XML-Datei, in der steht, aus welchen Teilen (links) der
# Roboter besteht und wo die Gelenke (joints) sitzen. Yahboom liefert so eine Datei fuer den M3 Pro mit
# (Paket yahboom_M3Pro_description). Oft als .xacro (URDF mit Platzhaltern wie ${pi/2}).
#
# Wir brauchen nur die Masse fuer lib/arm.py (Kinematik): wo sitzt die Schulter (Servo 2), wie lang sind
# Oberarm, Unterarm und Hand. Die stehen in den <origin xyz="..."> der Arm-Gelenke.
# Annahme (wie bei Yahboom): Alle Servos auf 90 Grad = alle Gelenkwinkel 0 = Arm zeigt gerade nach oben.
#
# UNGEPRUEFT auf unserem Roboter: Wir kennen Yahbooms Datei nur aus einem oeffentlichen Nachbau
# (github.com/robotics-career-coach/mujoco_rosmaster_m3pro, Masse laut Autor aus Yahbooms CAD).
import glob
import math
import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET

import numpy as np

PAKETE = ['yahboom_M3Pro_description', 'yahboom_m3pro_description', 'yahboomcar_description', 'm3pro_description']
SUCH_ORDNER = ['~/yahboomcar_ws/src', '~/yahboomcar_ros2_ws/src', '~/yahboomcar_ros2_ws/yahboomcar_ws/src',
               '~/M3Pro_ws/src', '~/ros2_ws/src', '~/yahboomcar_ws/install']


def _ausdruck(text, werte):
    """'${a*2+pi}' -> Zahl. Nur Zahlen, Namen aus werte, + - * / ( ) und pi (sicher, kein eval von Code)."""
    def ersetze(m):
        inhalt = m.group(1)
        erlaubt = dict(werte, pi=math.pi)
        tokens = re.findall(r'[A-Za-z_][A-Za-z0-9_]*|\d+\.?\d*(?:[eE][-+]?\d+)?|\.\d+|[-+*/()]', inhalt)
        teile = []
        for t in tokens:
            if re.match(r'[A-Za-z_]', t):
                if t not in erlaubt:
                    raise ValueError(f'unbekannter Name {t}')
                teile.append(repr(float(erlaubt[t])))
            else:
                teile.append(t)
        return repr(eval(''.join(teile), {'__builtins__': {}}, {}))   # nur Zahlen und Rechenzeichen
    return re.sub(r'\$\{([^}]*)\}', ersetze, text)


def _zahlen(text, werte):
    return [float(v) for v in _ausdruck(text or '0 0 0', werte).split()]


def _rpy(r, p, y):
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return np.array([[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
                     [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
                     [-sp, cp * sr, cp * cr]])


def gelenke(datei):
    """Alle Gelenke aus einer URDF/xacro-Datei: {name: {typ, eltern, kind, xyz, rpy, achse}}."""
    baum = ET.parse(datei).getroot()
    werte = {}
    for e in baum.iter():
        if e.tag.endswith('property') and e.get('name') and e.get('value') is not None:
            try:
                werte[e.get('name')] = float(_ausdruck(e.get('value'), werte))
            except (ValueError, SyntaxError, ZeroDivisionError):
                pass
    aus = {}
    for j in baum.iter():
        if not (j.tag == 'joint' or j.tag.endswith('}joint')) or j.get('type') is None:
            continue
        el, ki, o, a = j.find('parent'), j.find('child'), j.find('origin'), j.find('axis')
        if el is None or ki is None:
            continue
        aus[j.get('name')] = {'typ': j.get('type'), 'eltern': el.get('link'), 'kind': ki.get('link'),
                              'xyz': _zahlen(o.get('xyz') if o is not None else None, werte),
                              'rpy': _zahlen(o.get('rpy') if o is not None else None, werte),
                              'achse': _zahlen(a.get('xyz') if a is not None else '1 0 0', werte)}
    return aus


def arm_geometrie(datei, greifpunkt=0.075):
    """Masse fuer lib/arm.py (Kinematik) aus der URDF-Datei oder None (kein passender Arm gefunden).
    greifpunkt: Abstand Servo 5 (Hand drehen) -> Mitte zwischen den Greiferbacken (m). Steht nicht sauber
    in der URDF (die Backen bewegen sich), darum einstellbar (config/arm.yaml: greifpunkt)."""
    gl = gelenke(datei)
    kinder = {}
    for name, j in gl.items():
        kinder.setdefault(j['eltern'], []).append(name)
    alle_kinder = {j['kind'] for j in gl.values()}
    wurzeln = [j['eltern'] for j in gl.values() if j['eltern'] not in alle_kinder]
    if not wurzeln:
        return None
    wurzel = wurzeln[0]

    # Lage jedes Gelenks bei Winkel 0 im System der Wurzel (meist base_link / base_footprint am Boden)
    lage = {}

    def gehe(link, T):
        for name in kinder.get(link, []):
            j = gl[name]
            Tj = np.eye(4)
            Tj[:3, :3], Tj[:3, 3] = _rpy(*j['rpy']), j['xyz']
            Tn = T @ Tj
            lage[name] = (Tn[:3, 3].copy(), Tn[:3, :3] @ np.array(j['achse'], dtype=float))
            gehe(j['kind'], Tn)
    gehe(wurzel, np.eye(4))

    # Arm = laengste Kette von Drehgelenken (revolute) ab der Wurzel
    def ketten(link):
        beste = []
        for name in kinder.get(link, []):
            j = gl[name]
            rest = ketten(j['kind'])
            k = ([name] if j['typ'] == 'revolute' else []) + rest
            if len(k) > len(beste):
                beste = k
        return beste
    kette = ketten(wurzel)
    # Erstes Gelenk mit senkrechter Achse = Servo 1, danach drei waagrechte (Servo 2-4), dann Servo 5
    for i, name in enumerate(kette):
        if abs(lage[name][1][2]) > 0.9:
            kette = kette[i:]
            break
    if len(kette) < 5:
        return None
    s1, s2, s3, s4, s5 = (lage[n] for n in kette[:5])
    waagrecht = all(abs(a[2]) < 0.2 for _, a in (s2, s3, s4))
    if abs(s1[1][2]) < 0.9 or not waagrecht:
        return None
    return {
        'schulter': [round(float(v), 4) for v in s2[0]],
        'oberarm': round(float(np.linalg.norm(s3[0] - s2[0])), 4),
        'unterarm': round(float(np.linalg.norm(s4[0] - s3[0])), 4),
        'hand': round(float(np.linalg.norm(s5[0] - s4[0])) + greifpunkt, 4),
        'gelenke': kette[:5], 'wurzel': wurzel,
    }


MERKER = os.path.expanduser('~/.cache/smartcity_urdf.txt')   # zuletzt gefundener Pfad (leer = keiner)


def finde_urdf():
    """Pfad zu Yahbooms Robotermodell auf diesem Rechner oder None.
    Sucht: Umgebungsvariable SMARTCITY_URDF, installierte ROS-Pakete (ros2 pkg prefix), typische Workspaces."""
    if os.environ.get('SMARTCITY_URDF'):
        return os.environ['SMARTCITY_URDF'] if os.path.exists(os.environ['SMARTCITY_URDF']) else None
    # Die Suche dauert auf dem Roboter einige Sekunden (ros2 pkg prefix, viele Dateien) -> Ergebnis merken.
    # Nichts gefunden: erst nach einem Tag wieder suchen.
    try:
        with open(MERKER) as f:
            zeile = f.read().strip()
        if zeile and os.path.exists(zeile):
            return zeile
        if not zeile and time.time() - os.path.getmtime(MERKER) < 86400:
            return None
    except OSError:
        pass
    gefunden = _suchen()
    try:
        os.makedirs(os.path.dirname(MERKER), exist_ok=True)
        with open(MERKER, 'w') as f:
            f.write(gefunden or '')
    except OSError:
        pass
    return gefunden


def _suchen():
    ordner = []
    for p in PAKETE:
        try:
            r = subprocess.run(['ros2', 'pkg', 'prefix', p], capture_output=True, text=True, timeout=8)
            if r.returncode == 0 and r.stdout.strip():
                ordner.append(os.path.join(r.stdout.strip(), 'share', p))
        except (OSError, subprocess.SubprocessError):
            break                                   # kein ros2 auf diesem Rechner
    for o in SUCH_ORDNER:
        o = os.path.expanduser(o)
        for p in PAKETE:
            ordner += glob.glob(os.path.join(o, '**', p), recursive=True)[:3]
    kandidaten = []
    for o in ordner:
        for muster in ('**/*.urdf', '**/*.urdf.xacro', '**/*.xacro'):
            kandidaten += sorted(glob.glob(os.path.join(o, muster), recursive=True))
    # M3Pro-Dateien zuerst
    kandidaten.sort(key=lambda d: (0 if 'm3pro' in os.path.basename(d).lower() else 1, d))
    for d in kandidaten:
        try:
            if arm_geometrie(d):
                return d
        except (ET.ParseError, ValueError, SyntaxError, OSError):
            continue
    return None


if __name__ == '__main__':
    import sys
    d = sys.argv[1] if len(sys.argv) > 1 else finde_urdf()
    print('URDF:', d)
    print(arm_geometrie(d) if d else 'kein Yahboom-Robotermodell gefunden')
