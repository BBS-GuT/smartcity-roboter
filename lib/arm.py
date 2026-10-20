#!/usr/bin/env python3
# Greifarm des M3 Pro (DOFBOT-Pro, 6 Servos).
#
# Schnittstelle (Quelle: oeffentlicher Treiber fuer den M3 Pro, siehe docs/greifarm.md,
# auf RM02 geprueft, siehe docs/greifarm.md; Panel -> Arm -> "Arm-Topics anzeigen"):
#   Topic /arm6_joints, Typ arm_msgs/msg/ArmJoints
#   Felder joint1..joint6 = Winkel in GANZEN GRAD, time = Dauer der Bewegung in ms
#   Servo 1-4: 0-180, Servo 5 (Handgelenk): 0-270, Servo 6 (Greifer, siehe unten)
# Das Board meldet die aktuelle Armstellung NICHT zurueck. Man weiss also nur,
# was man zuletzt geschickt hat.
#
# Greifer (Servo 6): In Yahbooms Greif-Programmen (Kurs "Robotic Arm and 3D Space Gripping") ist
# 30 = offen und 120-130 = zugegriffen (groesser = fester). Frueher stand hier das Umgekehrte (aus einem
# fremden, ungeprueften Treiber). Einstellbar in config/arm.yaml (greifer_auf, greifer_zu) -> im Panel pruefen.
#
# Kinematik (wohin muessen die Servos, damit der Greifer an Punkt x, y, z ist?):
#   Echter Roboter: Yahbooms Dienst /get_kinemarics (Programm arm_kin/kin_srv, rechnet mit dem echten
#                   Robotermodell/URDF), siehe YahboomKinematik.
#   Ohne Dienst:    eigene einfache Rechnung (Kinematik). Masse in dieser Reihenfolge: selbst nachgemessen
#                   (config/lokal/arm.yaml, geometrie) > Yahbooms Robotermodell (URDF, lib/urdf.py, falls auf dem
#                   Roboter vorhanden) > Standard aus config/arm.yaml. Kleine Fehler gleicht das Greif-Lernen aus
#                   (lib/greifen.py). Winkel wie bei Yahboom: Servo 90 = Glied zeigt gerade nach oben, jedes Glied
#                   kippt um (90 - Servo) Grad weiter nach vorne (Servo 2, 3, 4 hintereinander).
import math
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # fuer lib/urdf.py

GRENZEN = {1: (0, 180), 2: (0, 180), 3: (0, 180), 4: (0, 180), 5: (0, 270), 6: (0, 180)}
GREIFER_AUF, GREIFER_ZU = 30, 130     # Standard (Yahboom-Kurse), wird aus config/arm.yaml ueberschrieben
NAMEN = ['Servo 1 (Drehen unten)', 'Servo 2 (Schulter)', 'Servo 3 (Ellbogen)',
         'Servo 4 (Handgelenk kippen)', 'Servo 5 (Handgelenk drehen)', 'Servo 6 (Greifer)']
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# Standard-Posen (im Repository) und eigene, im Panel gespeicherte Posen (NICHT im Repository,
# damit "git pull" nie an gespeicherten Werten scheitert). Eigene Werte gelten vor Standardwerten.
STANDARD_DATEI = os.path.join(REPO, 'config', 'arm.yaml')
POSEN_DATEI = os.environ.get('SMARTCITY_ARM_YAML', os.path.join(REPO, 'config', 'lokal', 'arm.yaml'))
BLICK_DREHUNG = 45   # Grad, um die Servo 1 zum Umschauen gedreht wird (blick_links/blick_rechts)
PRUEF_NEIGUNG = 20   # Grad, um die Servo 4 fuer den Pruefblick verstellt wird (Kamera steiler nach unten)


def pruefe(winkel, zeit_ms):
    """Fehlertext oder None. Werte ausserhalb werden abgelehnt, nicht gekuerzt."""
    if len(winkel) != 6:
        return 'Es muessen genau 6 Winkel sein'
    for i, w in enumerate(winkel, start=1):
        lo, hi = GRENZEN[i]
        if not isinstance(w, (int, float)) or not lo <= w <= hi:
            return f'{NAMEN[i - 1]}: {w} liegt ausserhalb {lo}..{hi} Grad'
    if not 300 <= zeit_ms <= 10000:
        return 'Zeit muss zwischen 300 und 10000 ms liegen (langsam = sicherer)'
    return None


def _lies(datei):
    try:
        import yaml
        with open(datei) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def lade_einstellungen():
    """Standard (config/arm.yaml) + eigene Werte (config/lokal/arm.yaml)."""
    daten = _lies(STANDARD_DATEI)
    eigene = _lies(POSEN_DATEI)
    posen = dict(daten.get('posen') or {})
    posen.update(eigene.get('posen') or {})
    daten.update(eigene)
    daten['posen'] = posen
    return daten


def greifer_werte():
    """(auf, zu) fuer Servo 6 aus config/arm.yaml (greifer_auf / greifer_zu)."""
    e = lade_einstellungen()
    return int(e.get('greifer_auf', GREIFER_AUF)), int(e.get('greifer_zu', GREIFER_ZU))


GREIFER_OFFEN_M = 0.085     # so weit ist der Greifer bei greifer_auf offen (m, geschaetzt)
GREIFER_GRAD_PRO_CM = 17.6  # Servo 6: so viele Grad je cm weniger Oeffnung (geschaetzt: 150 Grad auf 8,5 cm)
GREIFER_DRUECKEN = 8        # so viele Grad ueber das Beruehren hinaus zudruecken


def greifer_fuer_breite(breite):
    """(anlegen, zu) fuer Servo 6 bei einem Gegenstand dieser Breite (m).
    anlegen: kurz bevor die Backen beruehren (schnell), zu: beruehren + greifer_druecken Grad (langsam).
    Nie weiter als greifer_zu - ein fester Wert fuer alle Breiten drueckt schmale Dinge zu wenig und breite zu
    fest (Greifer knackt). Masse in config/arm.yaml (greifer_offen_m, greifer_grad_pro_cm, greifer_druecken)."""
    e = lade_einstellungen()
    auf, zu_max = greifer_werte()
    offen = float(e.get('greifer_offen_m', GREIFER_OFFEN_M))
    pro_cm = float(e.get('greifer_grad_pro_cm', GREIFER_GRAD_PRO_CM))
    beruehrt = auf + max(0.0, offen - float(breite)) * 100 * pro_cm
    zu = min(zu_max, beruehrt + float(e.get('greifer_druecken', GREIFER_DRUECKEN)))
    anlegen = min(zu, max(auf, beruehrt - 10))
    return int(round(anlegen)), int(round(zu))


def lade_posen():
    """Alle Posen: {name: [6 Winkel]}. Fehlen blick_links/blick_rechts, werden sie aus der
    Fahrstellung berechnet (Servo 1 um BLICK_DREHUNG Grad gedreht)."""
    e = lade_einstellungen()
    posen = {k: v for k, v in (e.get('posen') or {}).items()}
    fahr = posen.get('fahrstellung')
    if fahr:
        links = -1 if (e.get('geometrie') or {}).get('servo1_links', 1) < 0 else 1   # Drehrichtung Servo 1
        for name, d in (('blick_links', BLICK_DREHUNG * links), ('blick_rechts', -BLICK_DREHUNG * links)):
            if not posen.get(name):
                posen[name] = [max(0, min(180, fahr[0] + d))] + list(fahr[1:])
        if not posen.get('pruefblick'):
            # Kamera steiler nach unten: sieht Hindernisse, die zu nah fuer die Fahrstellung sind
            posen['pruefblick'] = list(fahr[:3]) + [max(0, fahr[3] - PRUEF_NEIGUNG)] + list(fahr[4:])
    return posen


def kamera_fuer_pose(kamera, fahr, pose, geo=None):
    """Kameramasse (kamera_hoehe, kamera_neigung, kamera_x wie fuer die Fahrstellung gemessen) fuer eine andere
    Armstellung umrechnen. Die Kamera sitzt fest an der Hand: sie dreht sich mit der Hand und wandert mit dem
    Handgelenk. Gerechnet mit der eigenen Kinematik (Masse aus config/arm.yaml), nur fuer Servo 1 wie in der
    Fahrstellung (nach vorne). None: geht nicht."""
    if pose is None or abs(pose[0] - fahr[0]) > 1:
        return None
    kin = Kinematik(geo)
    handgelenk = Kinematik(dict(kin.g, hand=0.0))
    (w0x, _, w0z), _ = handgelenk.vorwaerts(fahr)
    (w1x, _, w1z), _ = handgelenk.vorwaerts(pose)
    dneig = kin.vorwaerts(pose)[1] - kin.vorwaerts(fahr)[1]       # Grad, + = Hand weiter nach unten
    cx, cz = kamera['kamera_x'] - w0x, kamera['kamera_hoehe'] - w0z
    d = math.radians(dneig)
    aus = dict(kamera)
    aus['kamera_x'] = w1x + cx * math.cos(d) + cz * math.sin(d)
    aus['kamera_hoehe'] = w1z - cx * math.sin(d) + cz * math.cos(d)
    aus['kamera_neigung'] = kamera['kamera_neigung'] + dneig
    return aus


def _speichere(aenderung):
    import yaml
    eigene = _lies(POSEN_DATEI)
    aenderung(eigene)
    os.makedirs(os.path.dirname(POSEN_DATEI), exist_ok=True)
    with open(POSEN_DATEI, 'w') as f:
        f.write('# Eigene Arm-Posen dieses Roboters (gespeichert ueber das Panel, Seite Arm).\n'
                '# Nicht im Repository. Standardwerte: config/arm.yaml\n')
        yaml.safe_dump(eigene, f, allow_unicode=True, sort_keys=False)


def speichere_pose(name, winkel):
    _speichere(lambda d: d.setdefault('posen', {}).__setitem__(name, [int(w) for w in winkel]))


def speichere_einstellung(name, wert):
    _speichere(lambda d: d.__setitem__(name, wert))


# ---------------------------------------------------------------- Kinematik (eigene Rechnung)
GEOMETRIE_STANDARD = {
    # Werte aus einem oeffentlichen Modell des M3 Pro (github.com/robotics-career-coach/mujoco_rosmaster_m3pro,
    # Masse laut Autor aus Yahbooms CAD). Am echten Arm NICHT nachgemessen.
    'schulter': [0.0336, 0.0, 0.218],   # Schulter (Servo 2) gegenueber Robotermitte am Boden (m): vorne, links, Hoehe
    'oberarm': 0.0829,         # Servo 2 -> Servo 3 (m)
    'unterarm': 0.0828,        # Servo 3 -> Servo 4 (m)
    'hand': 0.150,             # Servo 4 -> Mitte zwischen den Greiferbacken (m), Greiferteil geschaetzt
    'servo1_links': 1,         # +1: Servo 1 groesser = Arm dreht nach links, -1: nach rechts
    # Nur fuer Simulation/Training ("so ist der Arm wirklich"): der Planer kennt diese Fehler nicht.
    'nullpunkte': [0.0, 0.0, 0.0, 0.0],   # Servo 1-4 stehen um so viele Grad anders als befohlen
    'durchhang': 0.0,          # Arm sackt durch sein Gewicht so viele Grad ab (bei 25 cm Reichweite)
}
NEIGUNGEN = (180, 170, 160, 150, 140, 130, 120, 110, 100, 90)


class Kinematik:
    """Eigene Rechnung (ohne Yahboom-Programm). Punkte im Roboter-System: x vorne, y links, z Hoehe ueber Boden."""

    def __init__(self, geo=None):
        self.g = dict(GEOMETRIE_STANDARD)
        self.g.update(geo or {})

    def vorwaerts(self, winkel):
        """Servowinkel (mind. 4) -> (x, y, z) der Greifermitte und Neigung der Hand (Grad, 90 = waagrecht,
        180 = senkrecht nach unten)."""
        g = self.g
        n = list(g.get('nullpunkte') or [0, 0, 0, 0]) + [0] * 4
        w = [winkel[i] + n[i] for i in range(4)]
        dreh = math.radians(w[0] - 90) * g['servo1_links']
        p1 = math.radians(90 - w[1])
        p2 = p1 + math.radians(90 - w[2])
        p3 = p2 + math.radians(90 - w[3])
        if g.get('durchhang'):
            # Durchhaengen: je weiter der Arm nach vorne reicht, desto mehr kippt er nach unten
            r0 = g['oberarm'] * math.sin(p1) + g['unterarm'] * math.sin(p2) + g['hand'] * math.sin(p3)
            sack = math.radians(g['durchhang']) * max(0.0, r0) / 0.25
            p1, p2, p3 = p1 + 0.6 * sack, p2 + sack, p3 + sack
        r = g['oberarm'] * math.sin(p1) + g['unterarm'] * math.sin(p2) + g['hand'] * math.sin(p3)
        z = g['oberarm'] * math.cos(p1) + g['unterarm'] * math.cos(p2) + g['hand'] * math.cos(p3)
        sx, sy, sz = g['schulter']
        return (sx + r * math.cos(dreh), sy + r * math.sin(dreh), sz + z), math.degrees(p3)

    def inverse(self, x, y, z, neigungen=NEIGUNGEN):
        """Servowinkel [s1..s5] fuer die Greifermitte an (x, y, z) oder None (nicht erreichbar).
        Probiert die Handneigungen der Reihe nach (zuerst senkrecht von oben = am sichersten)."""
        g = self.g
        sx, sy, sz = g['schulter']
        dx, dy = x - sx, y - sy
        dreh = math.degrees(math.atan2(dy, dx))
        s1 = 90 + dreh * g['servo1_links']
        if not 0 <= s1 <= 180:
            return None
        r, h = math.hypot(dx, dy), z - sz
        a, b = g['oberarm'], g['unterarm']
        for neig in neigungen:
            p3 = math.radians(neig)
            wr, wz = r - g['hand'] * math.sin(p3), h - g['hand'] * math.cos(p3)    # Handgelenk
            d = math.hypot(wr, wz)
            if d > a + b - 1e-6 or d < abs(a - b) + 1e-6:
                continue
            ell = math.acos(max(-1.0, min(1.0, (a * a + b * b - d * d) / (2 * a * b))))   # Winkel im Ellbogen
            for knick in (math.pi - ell, -(math.pi - ell)):          # Ellbogen oben zuerst
                p1 = math.atan2(wr, wz) - math.atan2(b * math.sin(knick), a + b * math.cos(knick))
                p2 = p1 + knick
                s2 = 90 - math.degrees(p1)
                s3 = 90 - math.degrees(p2 - p1)
                s4 = 90 - math.degrees(p3 - p2)
                if all(0 <= s <= 180 for s in (s2, s3, s4)):
                    return [round(s1), round(s2), round(s3), round(s4), 90]
        return None


def lade_kinematik(urdf_suchen=False):
    """Eigene Kinematik. Ohne urdf_suchen: Masse aus den Arm-Dateien (Simulation, Tests)."""
    return lade_kinematik_mit_quelle(urdf_suchen)[0]


def lade_kinematik_mit_quelle(urdf_suchen=True):
    """(Kinematik, Text woher die Masse kommen). Reihenfolge: selbst eingetragen (config/lokal/arm.yaml bzw.
    Simulations-Datei) > Yahbooms URDF auf dem Roboter > Standard (config/arm.yaml)."""
    e = lade_einstellungen()
    eigene = (_lies(POSEN_DATEI).get('geometrie') or {})
    greifpunkt = float(e.get('greifpunkt', 0.075))
    if eigene:
        return Kinematik(dict(e.get('geometrie') or {}, **eigene)), f'Masse aus {os.path.basename(POSEN_DATEI)}'
    if urdf_suchen:
        try:
            import urdf
            datei = urdf.finde_urdf()
            geo = urdf.arm_geometrie(datei, greifpunkt) if datei else None
            if geo:
                basis = dict(e.get('geometrie') or {})
                basis.update({k: geo[k] for k in ('schulter', 'oberarm', 'unterarm', 'hand')})
                return Kinematik(basis), f'Masse aus Yahbooms Robotermodell ({datei})'
        except Exception as ex:      # URDF kaputt/unbekannt -> Standard
            return Kinematik(e.get('geometrie') or {}), f'Standardmasse (URDF nicht lesbar: {ex})'
    return Kinematik(e.get('geometrie') or {}), 'Standardmasse (config/arm.yaml, geschaetzt)'


def greifer_position(winkel, geo=None):
    """(x, y, z) der Greifermitte fuer diese Servowinkel (eigene Rechnung, z. B. fuer den Simulator).
    geo: andere Masse als die des Planers (Simulator: "so ist der Arm wirklich")."""
    return (Kinematik(geo) if geo else lade_kinematik()).vorwaerts(winkel)[0]


def begrenze_tempo(schritte, start, grad_pro_s=60.0):
    """Bewegungen langsam halten: Dauer jedes Schritts so verlaengern, dass kein Servo schneller als
    grad_pro_s dreht (Greifer egal). schritte: [(Text, [6 Winkel], Dauer s), ...]."""
    aus, vorher = [], list(start)
    for text, winkel, dauer in schritte:
        weg = max(abs(a - b) for a, b in zip(winkel[:5], vorher[:5]))
        aus.append((text, winkel, round(max(dauer, weg / grad_pro_s), 2)))
        vorher = winkel
    return aus


class YahboomKinematik:
    """Yahbooms Kinematik-Dienst auf dem Roboter (/get_kinemarics, Typ arm_interface/srv/ArmKinemarics).
    Start: ros2 run arm_kin kin_srv  (das Panel startet ihn mit, wenn es ihn gibt).
    Ziel in base_link (Yahbooms Robotermodell), Winkel in Grad wie am Servo.
    UNGETESTET auf unserem Roboter: Umrechnung so wie in Yahbooms grasp_desktop.py (Servo 1 = 180 - joint1)."""

    def __init__(self):
        from rosidl_runtime_py.utilities import get_service
        import rclpy
        from rclpy.executors import SingleThreadedExecutor
        self.typ = get_service('arm_interface/srv/ArmKinemarics')   # Fehler, wenn das Yahboom-Paket fehlt
        self.node = rclpy.create_node(f'ki_kinematik_{os.getpid()}')
        self.client = self.node.create_client(self.typ, '/get_kinemarics')
        self.exe = SingleThreadedExecutor()
        self.exe.add_node(self.node)
        threading.Thread(target=self.exe.spin, daemon=True).start()

    def bereit(self):
        return self.client.service_is_ready()

    def _frage(self, **felder):
        req = self.typ.Request()
        for k, v in felder.items():
            setattr(req, k, v)
        fertig = threading.Event()
        zukunft = self.client.call_async(req)
        zukunft.add_done_callback(lambda _: fertig.set())
        if not fertig.wait(3.0):
            return None
        return zukunft.result()

    def inverse(self, x, y, z, neigung=80.0, aktuell=(90, 90, 90, 90, 90, 90)):
        """Servo [s1..s5] oder None. neigung: Hand nach unten gekippt (Grad, Yahboom nimmt 80)."""
        a = list(aktuell) + [90] * (6 - len(aktuell))
        r = self._frage(tar_x=float(x), tar_y=float(y), tar_z=float(z), roll=0.0, pitch=math.radians(neigung),
                        yaw=0.0, kin_name='ik', cur_joint1=float(180 - a[0]), cur_joint2=float(a[1]),
                        cur_joint3=float(a[2]), cur_joint4=float(a[3]), cur_joint5=float(a[4]),
                        cur_joint6=float(a[5]))
        if r is None:
            return None
        w = [180 - r.joint1, r.joint2, r.joint3, min(90.0, r.joint4), 90]
        if not all(0 <= v <= 180 for v in w) or any(math.isnan(v) for v in w):
            return None
        return [int(round(v)) for v in w]

    def vorwaerts(self, winkel):
        """Pose des Arm-Endes in base_link: (x, y, z, roll, pitch, yaw) oder None."""
        a = list(winkel) + [90] * (6 - len(winkel))
        r = self._frage(kin_name='fk', cur_joint1=float(180 - a[0]), cur_joint2=float(a[1]), cur_joint3=float(a[2]),
                        cur_joint4=float(a[3]), cur_joint5=float(a[4]), cur_joint6=float(a[5]))
        return None if r is None else (r.x, r.y, r.z, r.roll, r.pitch, r.yaw)

    # Kamera am Arm-Ende (Werte aus Yahbooms grasp_desktop.py / Kursunterlagen)
    ENDE_ZU_KAMERA = [[0, 0, 1, -0.100], [-1, 0, 0, 0], [0, -1, 0, 0.0482], [0, 0, 0, 1]]
    K_640 = (477.574, 477.557, 319.382, 238.641)       # fx, fy, cx, cy bei 640 x 480
    VERSATZ_DATEI = os.path.expanduser('~/yahboomcar_ws/src/arm_kin/param/offset_value.yaml')

    def kamera_zu_basis(self, pixel, tiefe_m, winkel):
        """Bildpunkt (Anteil 0..1) + Tiefe (m), Arm in 'winkel' -> Punkt in base_link (x, y, z) oder None.
        Wie Yahboom: Kamera-Punkt -> Arm-Ende (ENDE_ZU_KAMERA) -> base_link (Vorwaertsrechnung) + Versatz
        aus Yahbooms Kalibrierung (offset_value.yaml, falls vorhanden)."""
        import numpy as np
        ende = self.vorwaerts(winkel)
        if ende is None:
            return None
        fx, fy, cx, cy = self.K_640
        u, v = pixel[0] * 640, pixel[1] * 480
        kam = np.array([(u - cx) * tiefe_m / fx, (v - cy) * tiefe_m / fy, tiefe_m, 1.0])
        x, y, z, r, p, w = ende
        cr, sr, cp, sp, cw, sw = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(w), math.sin(w)
        rot = np.array([[cw * cp, cw * sp * sr - sw * cr, cw * sp * cr + sw * sr],
                        [sw * cp, sw * sp * sr + cw * cr, sw * sp * cr - cw * sr],
                        [-sp, cp * sr, cp * cr]])
        t_ende = np.eye(4)
        t_ende[:3, :3], t_ende[:3, 3] = rot, (x, y, z)
        punkt = t_ende @ np.array(self.ENDE_ZU_KAMERA, dtype=float) @ kam
        versatz = _lies(self.VERSATZ_DATEI)
        return (float(punkt[0]) + float(versatz.get('x_offset', 0.0)), float(punkt[1]) + float(versatz.get('y_offset', 0.0)),
                float(punkt[2]) + float(versatz.get('z_offset', 0.0)))


def plane_wegraeumen(ik, greif, ablagen, hoehe, fahrstellung, auf, zu, anlegen=None):
    """Armbewegung zum Wegraeumen ausrechnen.
    ik(x, y, z) -> [s1..s5] oder None; greif: Mitte des Hindernisses (x, y, z); ablagen: moegliche Ablagestellen
    (x, y, z), die erste erreichbare gilt; hoehe: Hoehe des Hindernisses (m).
    anlegen: Greiferwert kurz vor dem Beruehren - dann erst schnell bis dahin, danach langsam zudruecken
    (schont Greifer und Gegenstand). None: in einem Schritt zu.
    Rueckgabe: {'schritte': [(Text, [6 Winkel], Dauer s), ...], 'info': Text} oder {'fehler': Text}."""
    gx, gy, gz = greif

    def zug(punkte):
        aus = []
        for text, p, greifer, dauer in punkte:
            w = ik(*p)
            if w is None:
                return None, f'{text} ({p[0] * 100:.0f} / {p[1] * 100:.0f} / {p[2] * 100:.0f} cm)'
            aus.append((text, [int(v) for v in w[:5]] + [greifer], dauer))
        return aus, None
    greifen, fehler = zug([('Greifer auf, ueber das Hindernis', (gx, gy, gz + hoehe / 2 + 0.06), auf, 1.5),
                           ('runter zum Hindernis', (gx, gy, gz), auf, 1.0),
                           *([('Greifer anlegen', (gx, gy, gz), anlegen, 0.5)] if anlegen is not None else []),
                           ('zugreifen', (gx, gy, gz), zu, 0.8 if anlegen is None else 1.2),
                           ('anheben', (gx, gy, gz + hoehe / 2 + 0.08), zu, 1.0)])
    if greifen is None:
        return {'fehler': f'Arm erreicht es nicht: {fehler}'}
    for ax, ay, az in ablagen:
        ablegen, fehler = zug([('zur Seite', (ax, ay, az + 0.08), zu, 1.6), ('absetzen', (ax, ay, az), zu, 0.8),
                               ('loslassen', (ax, ay, az), auf, 0.6), ('Arm hoch', (ax, ay, az + 0.08), auf, 0.8)])
        if ablegen is not None:
            fahr = list(fahrstellung[:6]) + [auf] * (6 - len(fahrstellung))
            return {'schritte': greifen + ablegen + [('zurueck in Fahrstellung', fahr, 1.5)],
                    'info': f'greife bei {gx * 100:.0f} / {gy * 100:+.0f} / {gz * 100:.0f} cm, lege ab bei '
                            f'{ax * 100:.0f} / {ay * 100:+.0f} cm'}
    if not ablagen:
        return {'fehler': 'keine freie Ablagestelle neben der Strasse (LiDAR sieht dort ueberall etwas)',
                'ablage_fehlt': True}
    return {'fehler': f'keine erreichbare Ablagestelle neben der Strasse ({fehler})', 'ablage_fehlt': True}


ABLAGE_X = (0.10, 0.06, 0.14, 0.18, 0.04, 0.22, 0.02, 0.26)   # vorne (m), beliebteste zuerst
ABLAGE_Y = (0.18, 0.20, 0.17, 0.22, 0.25)                     # seitlich (m): ausserhalb des Fahrschlauchs
ABLAGE_FREI = 0.06            # so nah (m) darf kein LiDAR-Punkt an einer Ablagestelle liegen


def ablagestellen(seite, z, belegt=None):
    """Ablagestellen neben dem Roboter (Roboter-System), bevorzugte Seite zuerst (+1 links, -1 rechts).
    So weit seitlich, dass es ausserhalb des Fahrschlauchs liegt. Ein Gitter statt weniger fester Punkte:
    welche der Arm wirklich erreicht, haengt von seinen (nicht nachgemessenen) Massen ab.
    belegt: LiDAR-Punkte (x, y) - Stellen, an denen schon etwas steht, fallen weg."""
    import numpy as np
    pkt = None if belegt is None else np.asarray(belegt, dtype=float).reshape(-1, 2)
    aus = []
    for s in (seite, -seite):
        for y in ABLAGE_Y:
            for x in ABLAGE_X:
                if pkt is not None and len(pkt) and np.hypot(pkt[:, 0] - x, pkt[:, 1] - s * y).min() < ABLAGE_FREI:
                    continue
                aus.append((x, s * y, z))
    return aus


class Arm:
    """Schickt Posen an den Arm. Braucht einen laufenden ROS-Node."""

    def __init__(self, node):
        self.node = node
        self.letzte = None
        try:
            from rosidl_runtime_py.utilities import get_message
            self.typ = get_message('arm_msgs/msg/ArmJoints')
            self.pub = node.create_publisher(self.typ, '/arm6_joints', 10)
            self.echt = True
        except Exception:
            # Paket arm_msgs nicht gefunden (z. B. Simulation ohne Yahboom-Workspace):
            # dann als Text auf ein Test-Topic senden, damit man sieht, was passiert waere.
            from std_msgs.msg import String
            self.typ = String
            self.pub = node.create_publisher(String, '/arm6_joints_sim', 10)
            self.echt = False

    def fahre(self, winkel, zeit_ms=1500):
        """Rueckgabe: Fehlertext oder None."""
        winkel = [int(round(w)) for w in winkel]
        fehler = pruefe(winkel, zeit_ms)
        if fehler:
            return fehler
        if self.echt:
            msg = self.typ()
            for i, w in enumerate(winkel, start=1):
                setattr(msg, f'joint{i}', w)
            msg.time = int(zeit_ms)
        else:
            msg = self.typ(data=f'{winkel} {zeit_ms} ms')
        self.pub.publish(msg)
        self.letzte = winkel
        return None


class ArmBeobachter:
    """Hoert mit, wohin der Arm zuletzt geschickt wurde - egal von wem (KI, Panel, Gamepad).
    Damit wissen KI und Kartograf, wohin die Kamera (am Arm) gerade schaut."""

    def __init__(self, node):
        self.winkel, self.zeit, self.dauer = None, 0.0, 0.0
        # Drehrichtung von Servo 1 (config/arm.yaml geometrie.servo1_links): gier soll immer "links = +" sein
        self.links = -1 if (lade_einstellungen().get('geometrie') or {}).get('servo1_links', 1) < 0 else 1
        from std_msgs.msg import String
        try:
            from rosidl_runtime_py.utilities import get_message
            typ = get_message('arm_msgs/msg/ArmJoints')
            node.create_subscription(typ, '/arm6_joints', self._echt, 10)
        except Exception:
            pass   # kein arm_msgs (Simulation)
        node.create_subscription(String, '/arm6_joints_sim', self._sim, 10)

    def _neu(self, winkel, dauer_ms):
        import time
        self.winkel, self.zeit, self.dauer = [float(w) for w in winkel], time.time(), float(dauer_ms) / 1000.0

    def _echt(self, m):
        self._neu([m.joint1, m.joint2, m.joint3, m.joint4, m.joint5, m.joint6], m.time)

    def _sim(self, m):
        import re
        t = re.match(r'\[([^\]]*)\]\s*(\d+)?', m.data)
        if t:
            self._neu([float(w) for w in t.group(1).split(',')], int(t.group(2) or 1000))

    def in_pose(self, pose, jetzt):
        """Steht der Arm still in dieser Pose (Servos 1-5 auf 3 Grad genau)?"""
        if self.winkel is None or not pose or jetzt - self.zeit < self.dauer + 0.3:
            return False
        return all(abs(self.winkel[i] - pose[i]) <= 3 for i in range(5))

    def kamera(self, posen, jetzt):
        """(in_fahrstellung, gier_grad). gier_grad = Drehung von Servo 1 gegenueber der Fahrstellung,
        None = Kamera schaut irgendwohin (Arm bewegt sich oder andere Servos verstellt).
        Ohne Meldung seit dem Start: Fahrstellung angenommen (so startet der Roboter)."""
        fahr = posen.get('fahrstellung')
        if self.winkel is None or not fahr:
            return True, 0.0
        if jetzt - self.zeit < self.dauer + 0.3:
            return False, None                       # Arm faehrt noch
        gleich = [abs(self.winkel[i] - fahr[i]) <= 3 for i in range(5)]   # Greifer (6) egal
        if all(gleich):
            return True, 0.0
        if all(gleich[1:]):
            return False, (self.winkel[0] - fahr[0]) * self.links
        return False, None
