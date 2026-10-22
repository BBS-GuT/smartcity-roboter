#!/usr/bin/env python3
# Control-Panel fuer den Roboter: Webseite mit grossen Knoepfen.
# Start: scripts/panel.sh  (startet Kamera + KI und oeffnet die Seite im Vollbild)
#
# Erreichbar:
#   am Roboter selbst:  http://localhost:8080
#   vom Laptop:         http://<IP-des-Roboters>:8080   -> Laptop-Zugriff ist STANDARDMAESSIG AN
#                       (ausschalten: im Panel unter "System" oder Start mit --kein-netz).
#                       Die aktuelle IP zeigt das Panel selbst an.
#   ACHTUNG: Solange Laptop-Zugriff an ist, kann jeder im Netz, der die Adresse kennt, den Roboter starten.
#
# Was das Panel tut:
#   Dashboard        -> alles auf einer Seite: Karte (2D/3D), Kamera, LiDAR, Knoepfe, Ereignisse
#                       (einzelne Seiten fuer Karte, Kamera, LiDAR, Arm, Sensoren, System)
#   START/TEST/STOPP -> startet/beendet den Linienfolger (KI-Zentrale muss laufen)
#   STOPP            -> sendet sofort Stillstand an /cmd_vel UND beendet den Linienfolger
#   Ansichten        -> KI-Sicht, Linie, LiDAR, Tiefe (Bild fuer Bild, ohne Stau)
#   Karte            -> startet den Kartografen mit der KI (kartograf/kartograf.py), zeigt seine Dateien,
#                       Messfahrt aufzeichnen + herunterladen (zum Auswerten mit kartograf/abspielen.py)
#   Arm              -> nur auf Knopfdruck, nie waehrend der Fahrt
#   Lichter          -> Abblendlicht an/aus (START schaltet es vor dem Losfahren ein), Blinker beim Abbiegen
#                       (lib/lichter.py), Zustand 10x pro Sekunde auf /lichter/zustand
import argparse
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Mathe-Bibliotheken nur einen Thread (gilt auch fuer alle vom Panel gestarteten Programme, sie erben die Umgebung):
# sonst warten auf dem Jetson Threads auf allen Kernen aktiv (RM02 20.10.: Linienfolger bis 500 % CPU)
for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_v, '1')

import cv2  # noqa: E402
cv2.setNumThreads(1)   # OpenCV-Threads (pthreads, OMP_NUM_THREADS wirkt nicht): gleiche Wandzeit, halbe CPU
import numpy as np
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image, CompressedImage, LaserScan
from geometry_msgs.msg import Twist
from std_msgs.msg import String, Float32, ColorRGBA
from cv_bridge import CvBridge

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# Protokolle der vom Panel gestarteten Programme. Im Projekt statt in /tmp: /tmp wird beim Neustart des
# Roboters geleert. Pro Programm <name>.log (dieser Lauf) und <name>.alt.log (der Lauf davor).
LOGS = os.path.join(REPO, 'logs')
HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, 'lib'))
sys.path.insert(0, os.path.join(REPO, 'ki'))
import lidar           # noqa: E402
import arm as armlib   # noqa: E402
import greifen         # noqa: E402
import lichter as lichterlib  # noqa: E402
import einstellungen   # noqa: E402
import protokolle      # noqa: E402
import systemlast      # noqa: E402
from entscheider import STANDARD as KI_STANDARD  # noqa: E402

# Sensoren fuer die Statusseite: (Anzeigename, Topic, Mindestrate in Hz oder None = nur Info)
SENSOREN = [
    ('Akku', '/battery', 0.5),
    ('IMU (Lagesensor)', '/imu/data_raw', 5),
    ('Odometrie (Radzaehler)', '/odom_raw', 5),
    ('LiDAR scan0', '/scan0', 3),
    ('LiDAR scan1', '/scan1', 3),
    ('Kamera Farbe', '/camera/color/camera_info', 5),
    ('Kamera Tiefe', '/camera/depth/camera_info', 5),
    ('Gamepad', '/joy', None),
]
# Dateien des Kartografen, die das Panel ausliefert: Adresse -> (Datei, Typ, als Download)
KARTEN_DATEIEN = {
    '/karte/bild.png': ('karte.png', 'image/png', False),
    '/karte/info.json': ('karte.json', 'application/json', False),
    '/karte/wolke.bin': ('wolke.bin', 'application/octet-stream', False),
    '/karte/export.png': ('karte.png', 'image/png', True),
    '/karte/export.ply': ('karte.ply', 'application/octet-stream', True),
}
# Akku: 3 Li-Ion-Zellen (voll ca. 12,6 V). Prozent ist nur eine grobe SCHAETZUNG.
AKKU_VOLL, AKKU_LEER, AKKU_WARNUNG = 12.6, 10.5, 11.0


def lade_lidar_einstellungen():
    try:
        return einstellungen.lade('line_follower')
    except Exception:
        return {}


_IPS = [0.0, []]   # (Zeit, Adressen): das Panel fragt alle 0,4 s, ein Unterprozess je Abfrage waere unnoetig


def ip_adressen():
    """Aktuelle IPv4-Adressen des Roboters (ohne 127.x). Aendert sich z. B. mit den VLANs (hoechstens 10 s alt)."""
    if time.monotonic() - _IPS[0] < 10.0:
        return list(_IPS[1])
    ips = []
    try:
        aus = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=3).stdout
        ips = [a for a in aus.split() if re.fullmatch(r'\d+\.\d+\.\d+\.\d+', a) and not a.startswith('127.')]
    except Exception:
        pass
    if not ips:
        try:  # Ersatz: welche Adresse wuerde fuer Verbindungen nach aussen benutzt?
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('10.255.255.255', 1))
            ips = [s.getsockname()[0]]
            s.close()
        except Exception:
            pass
    _IPS[:] = [time.monotonic(), ips]
    return list(ips)


class Prozesse:
    """Startet und beendet Programme (Linienfolger, Kamera, KI) als Kindprozesse."""

    def __init__(self):
        self.p, self.info = {}, {}

    def laeuft(self, name):
        pr = self.p.get(name)
        return pr is not None and pr.poll() is None

    def start(self, name, befehl, info='', env=None):
        if self.laeuft(name):
            return False
        log = protokolle.neu_oeffnen(LOGS, name)   # vorigen Lauf als <name>.alt.log aufheben
        env = dict(os.environ if env is None else env, PYTHONUNBUFFERED='1')   # sofort ins Protokoll, nicht gepuffert
        # eigene Prozessgruppe, damit beim Beenden auch alle Unterprozesse beendet werden
        self.p[name] = subprocess.Popen(befehl, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=env)
        self.info[name] = info
        return True

    def stopp(self, name, warte=3.0):
        pr = self.p.get(name)
        if pr is None or pr.poll() is not None:
            return
        try:
            os.killpg(pr.pid, signal.SIGINT)   # wie Strg+C
            pr.wait(warte)
        except subprocess.TimeoutExpired:
            os.killpg(pr.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def alle_stoppen(self):
        for name in list(self.p):
            self.stopp(name)


class PanelNode(Node):
    def __init__(self, args):
        super().__init__('control_panel')
        self.args = args
        self.bridge = CvBridge()
        self.lock = threading.Lock()
        self.daten = {}                 # name -> (zeit, wert)
        self.scans = {}                 # topic -> (zeit, msg)
        self.ereignisse = deque(maxlen=40)
        self.zaehler = {}               # topic -> Zeitpunkte (fuer Hz)
        self.netz_erlaubt = not args.kein_netz
        cfg = lade_lidar_einstellungen()
        self.scan_topics = list(cfg.get('scan_topics', ['/scan0', '/scan1']))
        self.scan_front = [float(x) for x in cfg.get('scan_front_deg', [0.0] * len(self.scan_topics))]
        self.halb_deg = float(cfg.get('obstacle_half_deg', 30.0))
        self.notbremse = float(cfg.get('notbremse_dist', KI_STANDARD['notbremse_dist']))
        self.arm = None
        self.tiefe_sub, self.tiefe_gewuenscht = None, 0.0
        werte = einstellungen.lade('lichter')
        self.lichter = lichterlib.Lichter({k: v for k, v in werte.items() if k in lichterlib.STANDARD})

        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.ki_kommando_pub = self.create_publisher(String, '/ki/kommando', 10)
        self.karte_kommando_pub = self.create_publisher(String, '/karte/kommando', 10)
        self.tempo_pub = self.create_publisher(Float32, '/line_follower/tempo', 10)
        self.licht_pub = self.create_publisher(String, '/lichter/zustand', 10)
        # LED-Leiste am Board (lib/lichter.py). Leer = Leiste nicht ansteuern, nur anzeigen.
        self.rgb_topic = str(werte.get('rgb_topic', '/rgb'))
        self.rgb_pub = self.create_publisher(ColorRGBA, self.rgb_topic, 10) if self.rgb_topic else None
        self.led_gesendet, self.led_voll = None, 0.0
        sub = self.create_subscription
        sub(String, '/line_follower/status', lambda m: self._json('lf', m), 10)
        sub(String, '/ki/befehl', lambda m: self._json('ki', m), 10)
        sub(String, '/ki/ereignis', self._ereignis, 50)
        sub(String, '/karte/pose', lambda m: self._json('karte', m), 10)
        sub(String, '/ki/antwort', lambda m: self._set('ki_antwort', m.data), 10)
        sub(CompressedImage, '/line_follower/bild/compressed', lambda m: self._set('bild_lf', bytes(m.data)), 1)
        sub(CompressedImage, '/ki/bild/compressed', lambda m: self._set('bild_ki', bytes(m.data)), 1)
        sub(CompressedImage, '/sim/bild/compressed', lambda m: self._set('bild_sim', bytes(m.data)), 1)  # nur Simulation
        for t in self.scan_topics:
            sub(LaserScan, t, lambda m, t=t: self._scan(t, m), qos_profile_sensor_data)
        self.dyn_subs = {}
        self.create_timer(2.0, self._dynamisch_abonnieren)
        self.create_timer(3.0, self._agent_pruefen)
        self.create_timer(0.5, self._tiefe_verwalten)
        self.create_timer(0.1, self.lichter_takt)

    # ---------------- Eingaenge ----------------
    def _set(self, name, wert):
        with self.lock:
            self.daten[name] = (time.time(), wert)

    def get(self, name, max_alter=None):
        with self.lock:
            zeit, wert = self.daten.get(name, (0.0, None))
        if max_alter is not None and time.time() - zeit > max_alter:
            return None
        return wert

    def get_frisch(self, name, max_alter=1.0):
        """Wie get(), aber ohne Sperre (Aufrufer haelt self.lock schon)."""
        zeit, wert = self.daten.get(name, (0.0, None))
        return wert if time.time() - zeit <= max_alter else None

    def _json(self, name, msg):
        try:
            self._set(name, json.loads(msg.data))
        except ValueError:
            pass

    def _ereignis(self, msg):
        try:
            e = json.loads(msg.data)
        except ValueError:
            return
        with self.lock:
            self.ereignisse.appendleft(e)

    def _scan(self, topic, msg):
        with self.lock:
            self.scans[topic] = (time.time(), msg)
        self.zaehle(topic)

    def zaehle(self, topic):
        with self.lock:
            self.zaehler.setdefault(topic, deque(maxlen=300)).append(time.time())

    def hz(self, topic):
        jetzt = time.time()
        with self.lock:
            n = sum(1 for z in self.zaehler.get(topic, ()) if jetzt - z < 2.0)
        return n / 2.0

    def _dynamisch_abonnieren(self):
        # Nachrichtentyp zur Laufzeit nachsehen (z. B. /battery), dann muss man ihn nicht kennen.
        try:
            from rosidl_runtime_py.utilities import get_message
            typen = dict(self.get_topic_names_and_types())
            for _, topic, _ in SENSOREN:
                if topic in self.scan_topics or topic in self.dyn_subs or not typen.get(topic):
                    continue
                typ = get_message(typen[topic][0])
                if topic == '/battery':
                    cb = lambda m: (self.zaehle('/battery'), self._akku(m))
                else:
                    cb = lambda m, t=topic: self.zaehle(t)
                self.dyn_subs[topic] = self.create_subscription(typ, topic, cb, qos_profile_sensor_data)
        except Exception as e:
            self.get_logger().warn(f'Sensor-Abo: {e}', throttle_duration_sec=30)

    def _akku(self, msg):
        wert = getattr(msg, 'data', None)
        if wert is None:
            wert = getattr(msg, 'voltage', None)
        if wert is not None:
            self._set('akku', float(wert))

    def _agent_pruefen(self):
        self._set('agent', agent_info()['laeuft'])

    def _tiefe_verwalten(self):
        # Tiefenbilder sind gross -> nur abonnieren, solange jemand die Tiefen-Ansicht offen hat
        gewollt = time.time() - self.tiefe_gewuenscht < 5.0
        if gewollt and self.tiefe_sub is None:
            self.tiefe_sub = self.create_subscription(Image, self.args.tiefe_topic,
                                                      lambda m: self._set('tiefe', m), qos_profile_sensor_data)
        elif not gewollt and self.tiefe_sub is not None:
            self.destroy_subscription(self.tiefe_sub)
            self.tiefe_sub = None

    # ---------------- Ausgaenge ----------------
    def lichter_takt(self):
        """Blinker aus Linienfolger und KI neu rechnen und den Lichtzustand senden (10x pro Sekunde)."""
        with self.lock:
            vorher = self.lichter.blinker
            z = self.lichter.schritt(time.time(), self.get_frisch('lf'), self.get_frisch('ki'))
            if z['blinker'] != vorher:
                text = f"Blinker {z['blinker']} ({z['grund']})" if z['blinker'] else 'Blinker aus'
                self.ereignisse.appendleft({'zeit': time.time(), 'text': text, 'art': 'licht'})
        self.licht_pub.publish(String(data=json.dumps(z)))
        self.leiste_senden(z['leds'])
        return z

    def leiste_senden(self, leds):
        """Nur geaenderte LEDs ans Board, alle 2 s die ganze Leiste (falls das Board neu gestartet ist)."""
        if self.rgb_pub is None:
            return
        jetzt = time.time()
        alt = self.led_gesendet if jetzt - self.led_voll < 2.0 else None
        if alt is None:
            self.led_voll = jetzt
        for a, (r, g, b) in lichterlib.rgb_befehle(alt, leds, self.lichter.c['links_zuerst']):
            self.rgb_pub.publish(ColorRGBA(r=float(r), g=float(g), b=float(b), a=float(a)))
        self.led_gesendet = list(leds)

    def leiste_aus(self):
        if self.rgb_pub is not None:
            self.rgb_pub.publish(ColorRGBA(r=0.0, g=0.0, b=0.0, a=0.0))

    def abblend_setzen(self, an):
        with self.lock:
            if self.lichter.abblend != an:
                self.ereignisse.appendleft({'zeit': time.time(), 'text': 'Abblendlicht ' + ('an' if an else 'aus'),
                                            'art': 'licht'})
            self.lichter.abblend = an
        self.lichter_takt()      # sofort senden, nicht erst im naechsten Takt

    def alter(self, name):
        """Wie alt (s) ist die letzte Meldung? None = noch nie."""
        with self.lock:
            zeit = self.daten.get(name, (None, None))[0]
        return None if zeit is None else round(time.time() - zeit, 1)

    def stillstand(self):
        for _ in range(5):
            self.cmd_pub.publish(Twist())
            time.sleep(0.02)

    def arm_holen(self):
        if self.arm is None:
            self.arm = armlib.Arm(self)
        return self.arm

    # ---------------- Auswertungen fuer die Webseite ----------------
    def sensor_status(self):
        liste = [{'name': 'micro-ROS-Agent (Verbindung zum Board)', 'topic': 'Prozess', 'hz': None,
                  'ok': bool(self.get('agent'))},
                 {'name': 'Motorboard (/YB_Node)', 'topic': 'Node', 'hz': None,
                  'ok': 'YB_Node' in self.get_node_names()}]
        for name, topic, min_hz in SENSOREN:
            hz = self.hz(topic)
            liste.append({'name': name, 'topic': topic, 'hz': round(hz, 1),
                          'ok': None if min_hz is None else hz >= min_hz})
        return liste

    def lidar_daten(self):
        jetzt = time.time()
        with self.lock:
            scans = dict(self.scans)
        aus = {'scans': [], 'notbremse': self.notbremse, 'pruef': KI_STANDARD['pruef_dist'],
               'halb_deg': self.halb_deg}
        naechster = None
        for i, t in enumerate(self.scan_topics):
            zeit, msg = scans.get(t, (0.0, None))
            front = self.scan_front[i] if i < len(self.scan_front) else 0.0
            eintrag = {'topic': t, 'front_deg': front, 'aktiv': msg is not None and jetzt - zeit < 1.0, 'punkte': []}
            if eintrag['aktiv']:
                eintrag['punkte'] = lidar.punkte(msg, front)
                d = lidar.naechster_vorne(msg, front, self.halb_deg)
                if d != float('inf') and (naechster is None or d < naechster):
                    naechster = d
            aus['scans'].append(eintrag)
        aus['naechster_vorne'] = naechster
        return aus

    def jpeg_tiefe(self):
        self.tiefe_gewuenscht = time.time()
        roh = self.get('tiefe', max_alter=2.0)
        if roh is None:
            return text_bild('Tiefenkamera: warte auf Bilder ...')
        d = self.bridge.imgmsg_to_cv2(roh, 'passthrough').astype(np.float32)
        if roh.encoding != '32FC1':
            d /= 1000.0  # mm -> m
        nah, fern = 0.15, 1.5
        norm = np.clip((d - nah) / (fern - nah), 0, 1)
        bild = cv2.applyColorMap((255 - norm * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
        bild[d <= 0] = 0
        h, w = d.shape
        mitte = d[h // 2, w // 2]
        cv2.drawMarker(bild, (w // 2, h // 2), (255, 255, 255), cv2.MARKER_CROSS, 24, 2)
        cv2.putText(bild, f'Mitte: {mitte * 100:.0f} cm', (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        if w > 640:
            bild = cv2.resize(bild, (640, int(h * 640 / w)))
        return cv2.imencode('.jpg', bild, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()


def text_bild(text):
    bild = np.full((360, 640, 3), (42, 30, 15), np.uint8)
    cv2.putText(bild, text, (24, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (240, 240, 240), 2)
    return cv2.imencode('.jpg', bild)[1].tobytes()


def log_ende(name, zeilen=8):
    """Letzte Zeilen des Protokolls eines vom Panel gestarteten Programms (logs/<name>.log)."""
    try:
        with open(os.path.join(LOGS, f'{name}.log'), errors='replace') as f:
            return ''.join(f.readlines()[-zeilen:]).strip() or '(Protokoll leer)'
    except OSError:
        return '(kein Protokoll)'


def topics_mit(woerter):
    """ros2 topic list, gefiltert (fuer die Arm-Diagnose). Nur lesen."""
    try:
        aus = subprocess.run(['ros2', 'topic', 'list', '-t'], capture_output=True, text=True, timeout=15).stdout
    except Exception as e:
        return str(e)
    zeilen = [z for z in aus.splitlines() if any(w in z.lower() for w in woerter)]
    return '\n'.join(zeilen) or 'keine passenden Topics gefunden'


def system_info():
    """Schnellcheck (frueher scripts/check.sh): Name, Netz, Version, Programme. Aendert nichts."""
    def lauf(befehl):
        try:
            return subprocess.run(befehl, capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception as e:
            return f'({e})'
    name_datei = os.path.expanduser('~/roboter_name')
    zeilen = [f"Rechner: {socket.gethostname()}",
              'Roboter: ' + (open(name_datei).read().strip() if os.path.exists(name_datei)
                             else 'unbekannt (echo RM02 > ~/roboter_name)'),
              f"Domain-ID: {os.environ.get('ROS_DOMAIN_ID', '?')}, "
              f"ROS-Uebertragung: {os.environ.get('RMW_IMPLEMENTATION', 'Standard (Fast DDS)')}",
              'IP: ' + ', '.join(ip_adressen())]
    for n in sorted(os.listdir('/sys/class/net')) if os.path.isdir('/sys/class/net') else []:
        if n != 'lo':
            try:
                zeilen.append(f'MAC {n}: ' + open(f'/sys/class/net/{n}/address').read().strip())
            except OSError:
                pass
    zeilen.append('Repo-Stand: ' + lauf(['git', '-C', REPO, 'log', '--oneline', '-1']))
    a = agent_info()
    zeilen.append('micro-ROS-Agent: ' + (f"laeuft, Domain-ID {a['domain'] or 'nicht lesbar'}, Anschluss "
                                         f"{a['geraet'] or '?'}" if a['laeuft'] else 'LAEUFT NICHT'))
    return '\n'.join(zeilen)


def agent_info():
    """Laeuft der micro-ROS-Agent (Verbindung Jetson <-> Board)? Mit welcher Domain-ID und welchem Anschluss?
    Liest nur /proc (aendert nichts). Werte None = nicht lesbar (z. B. Agent laeuft als root)."""
    info = {'laeuft': False, 'domain': None, 'geraet': None, 'befehl': ''}
    try:
        pids = subprocess.run(['pgrep', '-f', 'micro_ros_agent'], capture_output=True, text=True).stdout.split()
    except Exception:
        return info
    for pid in pids:
        try:
            teile = open(f'/proc/{pid}/cmdline', 'rb').read().split(b'\0')
        except OSError:
            continue
        befehl = [t.decode(errors='replace') for t in teile if t]
        if not befehl:
            continue
        programm = os.path.basename(befehl[0])
        # das Agent-Programm selbst oder "ros2 run micro_ros_agent ..." (nicht eine Shell, die das Wort enthaelt)
        ros2_run = (programm.startswith('python') and len(befehl) > 2 and os.path.basename(befehl[1]) == 'ros2'
                    and 'micro_ros_agent' in befehl[2:4])
        if programm != 'micro_ros_agent' and not ros2_run:
            continue
        info.update(laeuft=True, befehl=' '.join(befehl))
        for schalter in ('--dev', '-D'):
            if schalter in befehl and befehl.index(schalter) + 1 < len(befehl):
                info['geraet'] = befehl[befehl.index(schalter) + 1]
        try:
            umgebung = open(f'/proc/{pid}/environ', 'rb').read().split(b'\0')
            werte = dict(t.decode(errors='replace').split('=', 1) for t in umgebung if b'=' in t)
            info['domain'] = werte.get('ROS_DOMAIN_ID', '0')    # nicht gesetzt = 0
        except OSError:
            pass
        break
    return info


def board_diagnose(board_da, sensoren_da):
    """Text, warum das Board fehlt (oder None, wenn alles da ist)."""
    if board_da and sensoren_da:
        return None
    a = agent_info()
    unsere = os.environ.get('ROS_DOMAIN_ID', '0')
    if not a['laeuft']:
        return ('micro-ROS-Agent laeuft nicht -> keine Verbindung zum Board. Roboter einmal aus- und einschalten '
                '(der Agent startet automatisch).')
    if board_da:
        return 'Board ist verbunden, aber einzelne Sensoren liefern nichts -> Kabel/Stecker der fehlenden Sensoren pruefen.'
    if a['domain'] is not None and a['domain'] != unsere:
        return (f"Domain-ID passt nicht: der Agent (Board) laeuft mit {a['domain']}, unsere Programme mit {unsere}. "
                f"Dann sehen sie sich nicht. Loesung: echo {a['domain']} > ~/ros_domain_id, Panel neu starten "
                '(oder den Agent auf dieselbe Nummer stellen, Wiki: Roboter-und-Netz).')
    if a['geraet'] and not os.path.exists(a['geraet']):
        return (f"Der Agent wartet auf {a['geraet']}, das Geraet gibt es aber nicht -> USB-Kabel Jetson <-> Board "
                'und Strom des Boards pruefen.')
    teile = [f"Agent laeuft ({a['befehl'][:80]}), aber das Board meldet sich nicht."]
    if a['domain'] is None:
        teile.append(f'(Domain-ID des Agents nicht lesbar, unsere: {unsere}. Pruefen: '
                     "sudo cat /proc/$(pgrep -f micro_ros_agent | head -1)/environ | tr '\\0' '\\n' | grep DOMAIN)")
    teile.append('Meist hilft: Hauptschalter am Board aus und wieder an, oder Reset-Knopf am Board druecken, '
                 'kurz warten. Danach diese Seite neu laden.')
    return ' '.join(teile)


def paket_da(paket):
    try:
        return subprocess.run(['ros2', 'pkg', 'prefix', paket], capture_output=True, timeout=10).returncode == 0
    except Exception:
        return False


_KINEMATIK = None


def eigene_kinematik_text():
    """Was die KI ohne Yahbooms Dienst rechnet (eigene Kinematik): Masse und ein Testpunkt."""
    kin, quelle = armlib.lade_kinematik_mit_quelle(urdf_suchen=True)
    fahr = armlib.lade_posen().get('fahrstellung') or [90, 120, 10, 20, 90, 30]
    (x, y, z), _ = kin.vorwaerts(fahr)
    test = kin.inverse(0.20, 0.0, 0.02)
    return (f'Die KI rechnet dann selbst: {quelle}.\nFahrstellung {fahr}: Greifer bei x {x * 100:.1f} / y {y * 100:.1f} / '
            f'z {z * 100:.1f} cm. Testpunkt 20 cm voraus, 2 cm hoch -> Servos {test or "nicht erreichbar"}')


def kinematik_pruefen():
    """Fragt Yahbooms Kinematik-Dienst, wo der Greifer in der Fahrstellung ist (rechnet nur, bewegt nichts)."""
    global _KINEMATIK
    fahr = armlib.lade_posen().get('fahrstellung')
    try:
        kin = _KINEMATIK = _KINEMATIK or armlib.YahboomKinematik()
    except Exception as e:
        return f'Yahboom-Kinematik nicht installiert ({e}).\n' + eigene_kinematik_text()
    for _ in range(20):
        if kin.bereit():
            break
        time.sleep(0.25)
    else:
        return ('Dienst /get_kinemarics antwortet nicht (laeuft "ros2 run arm_kin kin_srv"? startet mit der KI).\n'
                + eigene_kinematik_text())
    ende = kin.vorwaerts(fahr)
    if ende is None:
        return 'Dienst antwortet nicht (Zeit abgelaufen).'
    x, y, z = ende[:3]
    ziel = kin.inverse(0.22, 0.0, 0.03, aktuell=fahr)
    return (f'Kinematik laeuft. Fahrstellung {fahr}: Arm-Ende bei x {x * 100:.1f} cm, y {y * 100:.1f} cm, '
            f'z {z * 100:.1f} cm (base_link).\nTest: Punkt 22 cm voraus, 3 cm hoch -> Servos {ziel or "nicht erreichbar"}')


_GREIFEN = {'zeit': 0.0, 'stand': None}


def greifen_stand():
    """Lernstand Greifen (aus den Dateien, hoechstens alle 3 s gelesen)."""
    if time.time() - _GREIFEN['zeit'] > 3.0:
        try:
            _GREIFEN['stand'] = greifen.lernstand_dateien()
        except Exception as e:
            _GREIFEN['stand'] = {'fehler': str(e)}
        _GREIFEN['zeit'] = time.time()
    return _GREIFEN['stand']


def param_setzen(knoten, name, wert):
    """Parameter eines laufenden Programms aendern (im Hintergrund, Fehler egal)."""
    def lauf():
        subprocess.run(['ros2', 'param', 'set', knoten, name, wert], capture_output=True, timeout=20)
    threading.Thread(target=lauf, daemon=True).start()


def mache_handler(node, prozesse, beenden=None):
    zustand = {'tempo': 0.15}

    def ki_starten():
        # Kartograf gehoert dazu: baut bei jeder Fahrt die Karte weiter (faehrt nicht, bewegt keinen Arm)
        karte_starten()
        # Yahbooms Kinematik-Dienst (rechnet Armbewegungen mit dem echten Armmodell), falls installiert
        if 'kinemarics_arm' not in node.get_node_names() and paket_da('arm_kin'):
            prozesse.start('kinematik', ['ros2', 'run', 'arm_kin', 'kin_srv'])
        return prozesse.start('ki', [sys.executable, os.path.join(REPO, 'ki', 'zentrale.py'), '--ros-args']
                              + einstellungen.ros_argumente())

    def karte_starten():
        befehl = [sys.executable, os.path.join(REPO, 'kartograf', 'kartograf.py'), '--ros-args']
        return prozesse.start('karte', befehl + einstellungen.ros_argumente() + ['-p', f'karte:={node.args.karte}'])

    def lf_befehl(drive):
        befehl = [sys.executable, os.path.join(REPO, 'line_follower', 'line_follower.py'), '--ros-args']
        return befehl + einstellungen.ros_argumente() + [
            '-p', f'drive:={"true" if drive else "false"}', '-p', 'show:=false', '-p', f"speed:={zustand['tempo']}"]

    def aktion(name, daten, lokal):
        if name == 'stopp':
            node.stillstand()                 # sofort Stillstand senden ...
            prozesse.stopp('fahren')          # ... dann Programm beenden
            node.stillstand()
            return 'Gestoppt'
        if name in ('start', 'test'):
            if prozesse.laeuft('fahren'):
                return 'Laeuft schon. Erst STOPP druecken.'
            if node.get('ki', max_alter=2.0) is None:
                ki_starten()
                hinweis = ' KI-Zentrale wird gestartet (ca. 5 s), bis dahin bleibt er stehen.'
            else:
                hinweis = ''
            if 'line_follower' in node.get_node_names():
                return ('Es laeuft schon ein Linienfolger, der NICHT vom Panel gestartet wurde (alte Version oder '
                        'aus einem Terminal). Erst beenden: Terminal -> scripts/stopp.sh, dann nochmal.')
            if name == 'start':
                node.abblend_setzen(True)       # Licht an, BEVOR er losfaehrt
            prozesse.start('fahren', lf_befehl(name == 'start'), 'FAEHRT' if name == 'start' else 'TESTMODUS')
            time.sleep(2.5)       # sofort wieder beendet? Dann den Grund aus dem Protokoll zeigen
            if not prozesse.laeuft('fahren'):
                return 'Linienfolger hat sich sofort beendet:\n' + log_ende('fahren')
            if name == 'start':
                # ausdruecklicher START: KI quittiert damit Manoever-Fehler und fehlgeschlagenes Wegraeumen
                node.ki_kommando_pub.publish(String(data='start'))
            return ('Faehrt los.' if name == 'start' else 'Testmodus: zeigt alles, faehrt nicht.') + hinweis
        if name == 'abblend':
            node.abblend_setzen(bool(daten.get('an')))
            fahrt = prozesse.laeuft('fahren') and prozesse.info.get('fahren') == 'FAEHRT'
            if node.lichter.abblend:
                return 'Abblendlicht AN'
            return 'Abblendlicht AUS' + (' - Achtung: er faehrt gerade ohne Licht!' if fahrt else '')
        if name == 'licht_diagnose':
            return topics_mit(['light', 'led', 'rgb', 'lamp', 'licht'])
        if name == 'tempo':
            zustand['tempo'] = max(0.05, min(0.4, float(daten.get('wert', 0.15))))
            node.tempo_pub.publish(Float32(data=zustand['tempo']))
            return f"Tempo {zustand['tempo']:.2f} m/s"
        if name == 'kamera_start':
            if node.count_publishers('/camera/color/image_raw') > 0:
                return 'Kamera laeuft schon'
            prozesse.start('kamera', ['bash', os.path.join(REPO, 'scripts', 'kamera.sh')])
            return 'Kamera wird gestartet (ca. 10 s)'
        if name == 'ki_start':
            return 'KI wird gestartet. Log: logs/ki.log' if ki_starten() else 'KI laeuft schon'
        if name == 'ki_stopp':
            prozesse.stopp('ki')
            return 'KI gestoppt (Fahrprogramm haelt dann an)'
        # ---- Karte ----
        if name == 'karte_start':
            return 'Kartograf wird gestartet' if karte_starten() else 'Kartograf laeuft schon'
        if name == 'karte_stopp':
            prozesse.stopp('karte', warte=8.0)   # speichert beim Beenden
            return 'Kartograf gestoppt, Karte gespeichert'
        if name == 'karte_speichern':
            node.karte_kommando_pub.publish(String(data='speichern'))
            return 'Karte wird gespeichert'
        if name == 'karte_neu':
            # Erfolg nur, wenn der Kartograf GENAU DIESEN Auftrag bestaetigt (nicht: er wurde nur neu gestartet)
            vorher = node.get('karte', max_alter=3.0)
            if vorher is None:
                return ('Kartograf laeuft nicht (oder meldet sich nicht) -> keine neue Karte. '
                        'Erst "Kartograf starten" (System), dann nochmal.\n' + log_ende('karte'))
            if 'karte_neu' not in vorher:      # alter Kartograf (vor dem Update gestartet) bestaetigt nicht
                node.karte_kommando_pub.publish(String(data='neu'))
                return 'Neue Karte angefordert (Kartograf neu starten, dann wird sie auch bestaetigt).'
            auftrag = uuid.uuid4().hex[:12]
            node.karte_kommando_pub.publish(String(data=f'neu:{auftrag}'))
            ende = time.time() + 8.0
            while time.time() < ende:
                time.sleep(0.3)
                erg = (node.get('karte', max_alter=3.0) or {}).get('karte_neu') or {}
                if erg.get('auftrag') == auftrag:
                    if erg.get('ok'):
                        return (f"Neue Karte angefangen. Die alte liegt als Sicherung in karten/{erg.get('sicherung')} "
                                '(nichts geloescht).')
                    return f"Neue Karte NICHT angefangen, alte Karte bleibt aktiv: {erg.get('text')}"
            return ('Kartograf hat die neue Karte NICHT bestaetigt. Letzte Zeilen aus logs/karte.log:\n'
                    + log_ende('karte'))
        if name == 'karte_aufnahme':
            # Messfahrt aufzeichnen: alle Rohdaten fuer kartograf/abspielen.py (siehe docs/karte.md)
            if not prozesse.laeuft('karte'):
                return 'Kartograf laeuft nicht (er nimmt auf). Erst Kartograf starten.'
            k = node.get('karte', max_alter=2.0) or {}
            laeuft = bool((k.get('aufnahme') or {}).get('laeuft'))
            node.karte_kommando_pub.publish(String(data='aufnahme_stopp' if laeuft else 'aufnahme_start'))
            if laeuft:
                return 'Aufnahme beendet. Herunterladen: Knopf "Aufnahme herunterladen" (Ordner karten/aufnahmen/)'
            return ('Aufnahme laeuft. Jetzt 2-3 Runden normal fahren (auch Kurven und Wenden), dann wieder hier stoppen.')
        if name == 'umschauen':
            node.ki_kommando_pub.publish(String(data='umschauen'))
            time.sleep(0.5)
            return 'KI: ' + (node.get('ki_antwort', max_alter=2.0) or 'keine Antwort (laeuft die KI?)')
        # ---- Arm ----
        if name.startswith('greifer_'):
            if prozesse.laeuft('fahren') and name in ('greifer_schritt', 'greifer_messen'):
                return 'Arm nur, wenn das Fahrprogramm aus ist (Kamera sitzt am Arm). Erst STOPP.'
            return greifer_einmessen(name, daten)
        if name.startswith('arm_'):
            if prozesse.laeuft('fahren') and name in ('arm_pose', 'arm_greifer'):
                return 'Arm nur, wenn das Fahrprogramm aus ist (Kamera sitzt am Arm). Erst STOPP.'
            if name == 'arm_pose':
                fehler = node.arm_holen().fahre(daten.get('winkel', []), int(daten.get('zeit', 2000)))
                return fehler or 'Arm faehrt (' + ('echt' if node.arm.echt else 'nur Test-Topic, arm_msgs fehlt') + ')'
            if name == 'arm_greifer':
                letzte = node.arm_holen().letzte or daten.get('winkel')
                if not letzte:
                    return 'Erst einmal eine ganze Pose schicken (der Roboter meldet die Armstellung nicht).'
                winkel = list(letzte)
                auf, zu = armlib.greifer_werte()
                winkel[5] = auf if daten.get('auf') else zu
                return node.arm.fahre(winkel, 800) or (f'Greifer auf ({auf})' if daten.get('auf') else
                                                       f'Greifer zu ({zu}). Falsch herum? greifer_auf/greifer_zu in '
                                                       'config/lokal/arm.yaml tauschen.')
            if name == 'arm_speichern':
                pose = daten.get('name', '')
                if not re.fullmatch(r'[a-z0-9_]{2,30}', pose):
                    return 'Name nur aus Kleinbuchstaben/Zahlen'
                fehler = armlib.pruefe([int(w) for w in daten.get('winkel', [])], 1000)
                if fehler:
                    return fehler
                armlib.speichere_pose(pose, daten['winkel'])
                return f'Pose "{pose}" gespeichert (config/lokal/arm.yaml). KI neu starten, damit sie sie kennt.'
            if name == 'arm_ki':
                if daten.get('erlaubt') and not armlib.lade_posen().get('fahrstellung'):
                    return 'Erst die Pose "fahrstellung" speichern.'
                armlib.speichere_einstellung('ki_darf_arm_bewegen', bool(daten.get('erlaubt')))
                return ('Gespeichert. Die KI uebernimmt es in ca. 2 s (kein Neustart noetig).' if daten.get('erlaubt')
                        else 'Gespeichert: KI bewegt den Arm nicht mehr (gilt in ca. 2 s).')
            if name == 'arm_kinematik':
                return kinematik_pruefen()
            if name == 'arm_lernen_zuruecksetzen':
                # KI vergisst es selbst (sie haelt das Modell im Speicher), sonst die Datei direkt loeschen
                if node.get('ki', max_alter=2.0) is not None:
                    node.ki_kommando_pub.publish(String(data='greifen_zuruecksetzen'))
                    time.sleep(0.5)
                    return 'KI: ' + (node.get('ki_antwort', max_alter=2.0) or 'keine Antwort (laeuft die KI?)')
                if os.path.exists(greifen.LOKAL):
                    os.remove(greifen.LOKAL)
                return 'Gelerntes Greifen geloescht (config/lokal/greifen.json). Gilt wieder das Vortraining.'
            if name == 'arm_diagnose':
                return topics_mit(['arm', 'servo', 'joint', 'grip', 'claw'])
        # ---- LiDAR ----
        if name == 'lidar_winkel':
            i, grad = int(daten.get('index', 0)), float(daten.get('grad', 0))
            if 0 <= i < len(node.scan_front):
                node.scan_front[i] = ((grad + 180) % 360) - 180
            return f"Vorne fuer {node.scan_topics[i]}: {node.scan_front[i]:.0f} Grad (noch nicht gespeichert)"
        if name == 'lidar_speichern':
            einstellungen.speichere('scan_front_deg', [round(float(w), 1) for w in node.scan_front])
            wert = '[' + ', '.join(f'{w:.1f}' for w in node.scan_front) + ']'
            for knoten in ('/ki_zentrale', '/line_follower', '/kartograf'):
                param_setzen(knoten, 'scan_front_deg', wert)
            return 'Gespeichert in config/lokal/roboter.yaml und an KI, Linienfolger und Kartograf geschickt.'
        # ---- System ----
        if name == 'netz':
            if not lokal:
                return 'Laptop-Zugriff kann nur am Roboter selbst umgeschaltet werden.'
            node.netz_erlaubt = bool(daten.get('erlaubt'))
            return 'Laptop-Zugriff ' + ('AN' if node.netz_erlaubt else 'AUS')
        if name == 'ampel_kalibrieren':
            if prozesse.laeuft('fahren'):
                return 'Erst STOPP druecken.'
            env = dict(os.environ, DISPLAY=os.environ.get('DISPLAY', ':0'))
            if not prozesse.start('ampel', [sys.executable, os.path.join(REPO, 'line_follower', 'ampel_kalibrieren.py')],
                                  env=env):
                return 'Ampel-Einstellung laeuft schon (Fenster am Roboter-Bildschirm).'
            return ('Fenster "Ampel einstellen" geht am Roboter-Bildschirm auf. Tasten: s = Foto, w = Werte speichern, '
                    'q = Ende. Danach KI neu starten, damit die Werte gelten.')
        if name == 'system_info':
            return system_info()
        if name == 'update':
            if prozesse.laeuft('fahren'):
                return 'Erst STOPP druecken.'
            r = subprocess.run(['bash', os.path.join(REPO, 'scripts', 'update.sh')], capture_output=True, text=True,
                               timeout=90)
            return (r.stdout + r.stderr).strip() + '\nPanel neu starten, damit Aenderungen gelten.'
        if name == 'beenden' and beenden:
            threading.Thread(target=beenden, daemon=True).start()
            return 'Panel wird beendet, Roboter haelt an.'
        return f'Unbekannte Aktion {name}'

    def greifer_einmessen(name, daten):
        """Greifer einmessen (Panel -> Arm): Servo 6 in kleinen Schritten zu, bis die Backen anliegen, merken."""
        if name == 'greifer_messpunkte_loeschen':
            armlib.loesche_greifer_messpunkte()
            return 'Messpunkte geloescht. Greifer gilt wieder als geschaetzt. KI neu starten (System).'
        if name == 'greifer_einmessen_stand':
            return greifer_text()
        letzte = node.arm_holen().letzte
        if not letzte:
            return 'Erst einmal eine ganze Pose schicken (z. B. Fahrstellung), der Roboter meldet die Armstellung nicht.'
        if name == 'greifer_schritt':
            winkel = list(letzte)
            lo, hi = armlib.GRENZEN[6]
            auf, zu = armlib.greifer_werte()
            richtung = 1 if zu >= auf else -1          # + = weiter zu, egal wie herum der Greifer eingebaut ist
            schritt = max(-10, min(10, int(daten.get('grad', 0)))) * richtung
            winkel[5] = max(lo, min(hi, int(winkel[5]) + schritt))
            fehler = node.arm.fahre(winkel, 400)
            return fehler or f'Servo 6 (Greifer) jetzt {winkel[5]}'
        breite = float(daten.get('breite_cm', -1)) / 100
        if not 0.0 <= breite <= 0.12:
            return 'Breite in cm eingeben (0 = ohne Gegenstand, Backen beruehren sich; hoechstens 12 cm)'
        armlib.speichere_greifer_messpunkt(breite, int(letzte[5]))
        return (f'Gemerkt: {breite * 100:.1f} cm -> Servo 6 = {int(letzte[5])}. Greifer jetzt wieder oeffnen! '
                'KI neu starten (System), damit sie es nimmt.\n\n' + greifer_text())

    def greifer_text():
        e = armlib.lade_einstellungen()
        zeilen = ['Greifer: ' + armlib.greifer_stand(e), 'Damit wuerde die KI so greifen (Kamera-Breite -> Servo 6):']
        for b in (0.025, 0.03, 0.035, 0.04, 0.05, 0.06):
            zeilen.append(f'  {b * 100:.1f} cm: ' + armlib.greifer_plan(b, e)['text'])
        return '\n'.join(zeilen)

    def fremde_programme():
        """Unsere Programme, die laufen, aber NICHT vom Panel gestartet wurden (z. B. alte Version nach Update)."""
        namen = node.get_node_names()
        aus = []
        for knoten, proz, titel in (('line_follower', 'fahren', 'Linienfolger'), ('ki_zentrale', 'ki', 'KI-Zentrale'),
                                    ('kartograf', 'karte', 'Kartograf')):
            if knoten in namen and not prozesse.laeuft(proz):
                aus.append(titel)
        return aus

    def status(lokal):
        akku = node.get('akku', max_alter=5.0)
        sensoren = node.sensor_status()
        posen = armlib.lade_posen()
        e = armlib.lade_einstellungen()
        return {
            'fahren': prozesse.laeuft('fahren'), 'modus': prozesse.info.get('fahren', ''),
            'ki_prozess': prozesse.laeuft('ki'),
            'lf': node.get('lf', max_alter=1.5), 'ki': node.get('ki', max_alter=1.5),
            'lf_alter': node.alter('lf'), 'fremde': fremde_programme(),
            'ereignisse': list(node.ereignisse)[:25],
            'akku': akku, 'akku_warnung': AKKU_WARNUNG,
            'akku_prozent': None if akku is None else
            max(0, min(100, round((akku - AKKU_LEER) / (AKKU_VOLL - AKKU_LEER) * 100))),
            'sensoren': sensoren, 'board_diagnose': board_diagnose(
                sensoren[1]['ok'], all(x['ok'] is not False for x in sensoren[2:] if x['topic'].startswith(('/battery', '/imu', '/odom', '/scan')))),
            'lichter': node.lichter.zustand(),
            'tempo': zustand['tempo'], 'simulation': node.get('bild_sim', max_alter=3.0) is not None,
            'ips': ip_adressen(), 'port': node.args.port, 'netz_erlaubt': node.netz_erlaubt, 'lokal': lokal,
            'roboter': open(os.path.expanduser('~/roboter_name')).read().strip()
            if os.path.exists(os.path.expanduser('~/roboter_name')) else '',
            'karte': node.get('karte', max_alter=2.0), 'kartograf': prozesse.laeuft('karte'),
            'arm': {'grenzen': armlib.GRENZEN, 'namen': armlib.NAMEN, 'posen': posen,
                    'letzte': node.arm.letzte if node.arm else None,
                    'ki_darf': bool(e.get('ki_darf_arm_bewegen')),
                    'lernen': greifen_stand(),
                    'gespeichert': sorted(k for k, v in (e.get('posen') or {}).items() if v)},
        }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass  # keine Zeile pro Anfrage ins Terminal

        def _lokal(self):
            return self.client_address[0] in ('127.0.0.1', '::1', '::ffff:127.0.0.1')

        def _senden(self, code, typ, daten):
            self.send_response(code)
            self.send_header('Content-Type', typ)
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(daten)

        def _erlaubt(self):
            if self._lokal() or node.netz_erlaubt:
                return True
            self._senden(403, 'text/html; charset=utf-8', (
                '<h1 style="font-family:sans-serif">Laptop-Zugriff ist aus</h1>'
                '<p style="font-family:sans-serif">Am Roboter im Panel unter <b>System</b> '
                '"Laptop-Zugriff erlauben" einschalten, dann diese Seite neu laden.</p>').encode())
            return False

        def do_GET(self):
            if not self._erlaubt():
                return
            pfad = self.path.split('?')[0]
            try:
                if pfad in ('/', '/index.html'):
                    with open(os.path.join(HIER, 'index.html'), 'rb') as f:
                        self._senden(200, 'text/html; charset=utf-8', f.read())
                elif pfad == '/api/status':
                    self._senden(200, 'application/json', json.dumps(status(self._lokal())).encode())
                elif pfad == '/api/lidar':
                    self._senden(200, 'application/json', json.dumps(node.lidar_daten()).encode())
                elif pfad == '/bild/sim.jpg':
                    b = node.get('bild_sim', max_alter=2.0)
                    self._senden(200, 'image/jpeg', b or text_bild('Keine Simulation (nur mit scripts/simulation.sh)'))
                elif pfad in ('/bild/ki.jpg', '/bild/linie.jpg'):
                    b = node.get('bild_ki' if 'ki' in pfad else 'bild_lf', max_alter=2.0)
                    if b is None:
                        b = text_bild('KI-Zentrale laeuft nicht' if 'ki' in pfad else 'Linienfolger laeuft nicht (START/TEST)')
                    self._senden(200, 'image/jpeg', b)
                elif pfad == '/bild/tiefe.jpg':
                    self._senden(200, 'image/jpeg', node.jpeg_tiefe())
                elif pfad == '/karte/aufnahme.jsonl.gz':
                    # neueste Messfahrt zum Herunterladen
                    ordner = os.path.join(REPO, 'karten', 'aufnahmen')
                    try:
                        dateien = sorted((f for f in os.listdir(ordner) if f.endswith('.jsonl.gz')),
                                         key=lambda f: os.path.getmtime(os.path.join(ordner, f)))
                    except FileNotFoundError:
                        dateien = []
                    if not dateien:
                        return self._senden(404, 'text/plain; charset=utf-8', 'Noch keine Aufnahme'.encode())
                    datei = os.path.join(ordner, dateien[-1])
                    laeuft = ((node.get('karte', max_alter=3.0) or {}).get('aufnahme') or {}).get('laeuft')
                    if laeuft:
                        return self._senden(409, 'text/plain; charset=utf-8',
                                            'Aufnahme laeuft noch - erst "Aufnahme stoppen", dann herunterladen'.encode())
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/gzip')
                    self.send_header('Content-Length', str(os.path.getsize(datei)))
                    self.send_header('Content-Disposition', f'attachment; filename="{dateien[-1]}"')
                    self.end_headers()
                    with open(datei, 'rb') as f:      # stueckweise (kann gross sein)
                        shutil.copyfileobj(f, self.wfile)
                elif pfad == '/logs.tar.gz':
                    # alle Protokolle auf einmal (zum Weiterschicken bei Problemen), begrenzt, siehe lib/protokolle.py
                    try:
                        daten = protokolle.archiv(LOGS)
                    except Exception as e:
                        return self._senden(500, 'text/plain; charset=utf-8',
                                            f'Logs konnten nicht gepackt werden: {e!r}'.encode())
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/gzip')
                    self.send_header('Content-Length', str(len(daten)))
                    self.send_header('Content-Disposition',
                                     f'attachment; filename="smartcity_logs_{time.strftime("%Y%m%d_%H%M")}.tar.gz"')
                    self.end_headers()
                    self.wfile.write(daten)
                elif pfad in KARTEN_DATEIEN:
                    datei, typ, herunterladen = KARTEN_DATEIEN[pfad]
                    try:
                        with open(os.path.join(REPO, 'karten', node.args.karte, datei), 'rb') as f:
                            inhalt = f.read()
                    except FileNotFoundError:
                        return self._senden(404, 'text/plain', b'Noch keine Karte')
                    self.send_response(200)
                    self.send_header('Content-Type', typ)
                    self.send_header('Cache-Control', 'no-store')
                    if herunterladen:
                        self.send_header('Content-Disposition', f'attachment; filename="{node.args.karte}_{datei}"')
                    self.end_headers()
                    self.wfile.write(inhalt)
                else:
                    self._senden(404, 'text/plain', b'Nicht gefunden')
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _fremde_seite(self):
            """Kommt der Auftrag von einer fremden Webseite im selben Browser (CSRF)? Das Panel schickt JSON;
            eine fremde Seite kann das nicht ohne Rueckfrage des Browsers. Origin muss zur eigenen Adresse passen."""
            herkunft = self.headers.get('Origin')
            if herkunft and herkunft != 'null':
                # Browser schicken bei POST immer Origin: passt er, ist es das Panel (auch eine alte, noch offene Seite)
                return urllib.parse.urlsplit(herkunft).netloc != (self.headers.get('Host') or '')
            return (self.headers.get('Content-Type') or '').split(';')[0].strip().lower() != 'application/json'

        def do_POST(self):
            if not self._erlaubt():
                return
            if not self.path.startswith('/api/'):
                return self._senden(404, 'text/plain', b'?')
            if self._fremde_seite():
                return self._senden(403, 'text/plain; charset=utf-8', 'Auftrag nicht vom Panel'.encode())
            laenge = int(self.headers.get('Content-Length', 0))
            try:
                daten = json.loads(self.rfile.read(laenge) or b'{}')
            except ValueError:
                daten = {}
            try:
                antwort = aktion(self.path[5:], daten, self._lokal())
            except Exception as e:  # Fehler anzeigen statt das Panel abstuerzen zu lassen
                antwort = f'Fehler: {e}'
            self._senden(200, 'application/json', json.dumps({'antwort': antwort}).encode())

    return Handler, ki_starten


def systemlast_protokollieren(alle=2.0):
    """Alle 2 s eine Zeile nach logs/system.log: CPU, Speicher, Temperatur, GPU und wer die Rechenzeit braucht.
    Kommt die Messung deutlich zu spaet, steht 'HING x s' in der Zeile: Der Messthread lief verspaetet. Ob das am
    Panelprozess (z. B. GIL), am Scheduler oder am ganzen Rechner lag, zeigt diese Zeile allein nicht."""
    messer = systemlast.Systemlast()
    log = protokolle.neu_oeffnen(LOGS, 'system')
    soll = time.monotonic()
    while True:
        soll += alle
        time.sleep(max(0.0, soll - time.monotonic()))
        zu_spaet = time.monotonic() - soll
        if zu_spaet > 2.0:                 # weit zurueck: neu anfangen statt aufzuholen
            soll = time.monotonic()
        try:
            log.write(systemlast.zeile(messer.messen(), zu_spaet if zu_spaet > 0.5 else None) + '\n')
            log.flush()
        except Exception as e:
            print(f'Systemlast: {e}')
            return


def main():
    ap = argparse.ArgumentParser(description='Control-Panel')
    ap.add_argument('--port', type=int, default=8080)
    ap.add_argument('--kein-netz', action='store_true', help='Laptop-Zugriff beim Start AUS (Standard: an)')
    ap.add_argument('--tiefe-topic', default='/camera/depth/image_raw')
    ap.add_argument('--autostart', action='store_true', help='Kamera und KI-Zentrale beim Start mitstarten')
    ap.add_argument('--karte', default='smartcity', help='Name der Karte (Ordner karten/<name>)')
    args, _ = ap.parse_known_args()

    rclpy.init()
    node = PanelNode(args)
    prozesse = Prozesse()
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    threading.Thread(target=executor.spin, daemon=True).start()
    threading.Thread(target=systemlast_protokollieren, daemon=True).start()
    server = None

    def beenden():
        time.sleep(0.3)
        server.shutdown()
    handler, ki_starten = mache_handler(node, prozesse, beenden)
    server = ThreadingHTTPServer(('0.0.0.0', args.port), handler)
    server.daemon_threads = True
    print(f'Control-Panel am Roboter:  http://localhost:{args.port}')
    for ip in ip_adressen():
        print(f"Vom Laptop (Laptop-Zugriff {'AN' if node.netz_erlaubt else 'AUS'}):  http://{ip}:{args.port}")
    # Auch bei "Beenden"-Signalen (Fenster zu, Herunterfahren) sauber aufraeumen,
    # sonst laufen KI und Linienfolger ohne Panel weiter.
    def signal_ende(*_):
        raise KeyboardInterrupt
    # SIGINT auch ausdruecklich: Mit '&' aus einem Skript gestartete Programme ignorieren es sonst.
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, signal_ende)
    if args.autostart:
        time.sleep(2.0)  # kurz warten, bis ROS die anderen Programme kennt
        if node.count_publishers('/camera/color/image_raw') == 0:
            print('Starte Kamera ...')
            prozesse.start('kamera', ['bash', os.path.join(REPO, 'scripts', 'kamera.sh')])
        print('Starte KI-Zentrale ...')
        ki_starten()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        # Beim Beenden des Panels: Roboter anhalten, Lichter aus und alle gestarteten Programme beenden
        node.stillstand()
        node.leiste_aus()
        prozesse.alle_stoppen()
        node.stillstand()
        server.server_close()
        executor.shutdown(timeout_sec=2.0)  # ROS-Teil zuerst anhalten, sonst Absturz beim Abbau
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass
        print('Panel beendet, Roboter angehalten.', flush=True)
        # Direkt beenden: ein ROS-Hintergrundthread stuerzt sonst beim Python-Ende ab ("Aborted").
        # Alles Wichtige (Stillstand, Programme beenden) ist an dieser Stelle schon erledigt.
        os._exit(0)


if __name__ == '__main__':
    main()
