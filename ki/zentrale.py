#!/usr/bin/env python3
# KI-Zentrale: behaelt alles im Blick und sagt dem Linienfolger, ob er fahren darf.
#
# Start: das Panel startet sie automatisch (scripts/panel.sh)
#
# Sinne:
#   Kamera      -> YOLO-KI (Personen, Autos, Ampeln, Stoppschilder, ...)
#                  + Farbe der gefundenen Ampel (welche Lampe leuchtet)
#                  + Ersatz: LED-Erkennung und Achteck-Form, falls die KI die kleinen
#                    Modell-Ampeln/Schilder nicht als solche erkennt
#   LiDAR       -> naechster Gegenstand im FAHRSCHLAUCH (Streifen entlang der Linie vor dem Roboter,
#                  kommt vom Linienfolger; ohne Linie: geradeaus). Haeuser neben Kurven stoeren so nicht.
#   Tiefenkamera-> ragt etwas aus dem Boden?
# Die Entscheidung trifft ki/entscheider.py.
#
# Sendet:
#   /ki/befehl              std_msgs/String  JSON {aktion, faktor, grund, ...}  (10x pro Sekunde)
#   /ki/ereignis            std_msgs/String  JSON {zeit, text, art}
#   /ki/bild/compressed     Kamerabild mit allem, was die KI sieht (fuer das Panel)
#   /ki/antwort             std_msgs/String  Antwort auf /ki/kommando
# Empfaengt:
#   /ki/kommando            std_msgs/String  'start' (Panel: ausdruecklicher START, quittiert Fehler-/Hindernissperren),
#                                            'umschauen' (Kartograf/Panel: kurz anhalten, links/rechts schauen),
#                                            'greifen_zuruecksetzen' (Panel: Gelerntes vergessen)
#   /arm6_joints            wohin der Arm geschickt wurde (von wem auch immer) -> wohin schaut die Kamera?
import json
import math
import os
import signal
import sys
import threading
import time

# Mathe-Bibliotheken (OpenBLAS/OpenMP) nur einen Thread: sonst warten auf dem Jetson Threads auf allen Kernen aktiv
# (RM02 20.10.: Linienfolger 200-500 % CPU, Rechner haengt, KI-Befehle kommen nicht an). Vor numpy/cv2 setzen!
for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_v, '1')

import cv2  # noqa: E402
import numpy as np
import rclpy
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data, QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image, CompressedImage, LaserScan, Imu
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from std_msgs.msg import String
from cv_bridge import CvBridge

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for _d in ('lib', 'line_follower', 'erkennung', 'ki'):
    sys.path.insert(0, os.path.join(REPO, _d))
import ampel          # noqa: E402
import schilder       # noqa: E402
import linie          # noqa: E402
from zebra import finde_zebra  # noqa: E402
import lidar          # noqa: E402
import arm as armlib  # noqa: E402
import greifen        # noqa: E402
from tiefe import Bodenmodell        # noqa: E402
from entscheider import Entscheider, STANDARD as KI_STANDARD  # noqa: E402

# Diese Dinge fuehren zum Anhalten, wenn die Kamera-KI sie im Weg sieht. Nur Verkehrsteilnehmer:
# Moebel/Gegenstaende (Stuhl, Flasche ...) erkennt YOLO oft falsch, z. B. die schwarze Kurve als "Stuhl".
# Echte Hindernisse auf der Strasse finden LiDAR und Tiefenkamera trotzdem.
STOPP_NAMEN = ['Person', 'Fahrrad', 'Auto', 'Motorrad', 'Bus', 'LKW', 'Hund', 'Katze', 'Teddy']
FARBE_BGR = {'rot': (0, 0, 255), 'gelb': (0, 220, 255), 'gruen': (0, 200, 0)}
AKTION_BGR = {'fahren': (60, 170, 60), 'langsam': (0, 170, 230), 'stopp': (40, 40, 220)}


def lade_ampel_werte():
    """Eingestellte Ampelwerte aus config/ampel.yaml (Panel -> System -> Ampel einstellen)."""
    try:
        import yaml
        with open(os.path.join(REPO, 'config', 'ampel.yaml')) as f:
            daten = yaml.safe_load(f) or {}
        werte = {}
        for teil in daten.values():
            werte.update((teil or {}).get('ros__parameters', {}))
        return {k: v for k, v in werte.items() if k in ampel.STANDARD}
    except FileNotFoundError:
        return {}


class Zentrale(Node):
    def __init__(self):
        super().__init__('ki_zentrale')
        dp = self.declare_parameter
        dp('model', os.path.join(REPO, 'models', 'yolov8n.onnx'))
        dp('imgsz', 320)
        dp('kerne', 2)                  # Prozessorkerne fuer die KI (nur ohne Grafikkarte)
        dp('gpu', True)                 # KI auf der Grafikkarte rechnen, wenn moeglich (viel schneller, entlastet
                                        # den Prozessor fuer Linienfolger und Karte)
        dp('gpu_modell', '')            # leer = automatisch suchen (erkennung/yolo.py, GPU_MODELLE)
        dp('rate', 8.0)                 # KI-Bilder pro Sekunde (hoechstens)
        dp('min_conf', 0.35)            # Mindest-Sicherheit der KI (zum Anzeigen)
        dp('weg_min_conf', 0.5)         # so sicher muss sie sein, damit "im Weg" zum Anhalten fuehrt
        dp('image_topic', '/camera/color/image_raw')
        dp('depth_topic', '/camera/depth/image_raw')
        dp('tiefe_nutzen', True)
        dp('led_ersatz', True)          # LED-Erkennung, wenn die KI keine Ampel findet
        dp('form_ersatz', True)         # Achteck-Erkennung, wenn die KI kein Stoppschild findet
        dp('ampel_min_hoehe', 0.03)     # KI-Ampel muss mind. so hoch sein (Anteil Bildhoehe) = nah genug
        dp('schild_min_hoehe', 0.12)    # KI-Stoppschild muss mind. so hoch sein = nah genug
        dp('weg_links', 0.2)            # "im Weg" = Kasten mittig ...
        dp('weg_rechts', 0.8)
        dp('weg_unten_min', 0.5)        # ... Unterkante in der unteren Bildhaelfte ...
        dp('weg_min_hoehe', 0.15)       # ... und gross genug (= nah)
        dp('scan_topics', ['/scan0', '/scan1'])
        dp('scan_front_deg', [0.0, 0.0])
        dp('obstacle_half_deg', 30.0)
        dp('obstacle_min_range', 0.08)
        dp('fahrschlauch_breite', 0.30)  # Roboterbreite + etwas Rand (m) - am Roboter nachmessen
        dp('fahrschlauch_laenge', 0.80)  # so weit voraus pruefen (m)
        for name in ('kamera_hoehe', 'kamera_neigung', 'kamera_fov', 'kamera_x', 'threshold'):
            dp(name, linie.STANDARD[name])   # gleiche Kameradaten wie der Linienfolger (config/roboter.yaml)
        # Alle Werte des Entscheiders (ki/entscheider.py, STANDARD) sind auch einstellbar, z. B. in
        # config/lokal/roboter.yaml unter ki_zentrale: ros__parameters: greif_abstand: 0.22
        for name, wert in KI_STANDARD.items():
            dp(name, wert)

        einst = armlib.lade_einstellungen()
        self.posen = {k: v for k, v in armlib.lade_posen().items() if v}
        # Arm: Der Sender ist immer da, OB die KI ihn bewegen darf, entscheidet die Einstellung
        # ki_darf_arm_bewegen (Panel -> Arm, wird alle 2 s neu gelesen, gilt also sofort).
        self.arm = armlib.Arm(self) if self.posen.get('fahrstellung') else None
        # Kinematik zum Wegraeumen: Yahbooms Dienst, wenn er laeuft (echtes Armmodell), sonst eigene Rechnung
        # (Masse: selbst gemessen > Yahbooms URDF > Standard). Was dabei danebengeht, lernt lib/greifen.py.
        self.eigene_kin, self.kin_quelle = armlib.lade_kinematik_mit_quelle(urdf_suchen=bool(self.arm and self.arm.echt))
        self.eigenes_modell = str(einst.get('greif_modell', 'eigene'))     # Simulator: 'sim'
        self.politik = {}
        self.yahboom_kin = None
        if self.arm is not None and self.arm.echt:
            try:
                self.yahboom_kin = armlib.YahboomKinematik()
            except Exception as e:
                self.get_logger().info(f'Yahboom-Kinematik nicht verfuegbar ({e}) -> eigene Rechnung')
        planer_fehlt = '' if self.arm is not None else 'Pose "fahrstellung" fehlt (Panel -> Arm)'
        arm_erlaubt = bool(einst.get('ki_darf_arm_bewegen')) and self.arm is not None
        self.entscheider = Entscheider(cfg={n: self.p(n) for n in KI_STANDARD}, arm_erlaubt=arm_erlaubt,
                                       posen=self.posen, planer=self.planen if self.arm is not None else None,
                                       rueckmeldung=self.greif_ergebnis, planer_fehlt=planer_fehlt)
        # Entscheiden (10x/s, sendet /ki/befehl) in eigener Gruppe: Sensor-Callbacks (IMU ~100/s, zwei LiDARs) duerfen
        # es nicht verzoegern - sonst meldet der Linienfolger "KI-Zentrale antwortet nicht" (>0,6 s ohne Befehl)
        self.gruppe = MutuallyExclusiveCallbackGroup()
        self.create_timer(2.0, self._arm_einstellung, callback_group=self.gruppe)
        self.arm_beobachter = armlib.ArmBeobachter(self)
        self.kamera_cfg = {n: self.p(n) for n in ('kamera_hoehe', 'kamera_neigung', 'kamera_fov', 'kamera_x', 'threshold')}
        self.linien_sucher = linie.LinienSucher(self.kamera_cfg)   # Draufsicht fuer den Zebrastreifen
        self.gier, self.gier_zeit, self.imu_zeit = 0.0, time.time(), 0.0
        self.linie_status = {}
        self.lidar_d, self.lidar_xy = None, None

        self.bridge = CvBridge()
        self.lock = threading.Lock()
        self.bild = None                # neuestes Kamerabild (ROS-Nachricht)
        self.tiefe = None
        self.scans = {}
        self.wahrnehmung = {'bild_nr': 0, 'bild_zeit': 0.0, 'objekte': [], 'ampel': None,
                            'stoppschild': False, 'tiefe_hindernis': None}
        self.befehl = {'aktion': 'stopp', 'faktor': 0.0, 'grund': 'KI startet ...', 'arm': None}
        self.ki_ms = 0.0
        # Tiefenkamera prueft denselben Fahrweg wie der LiDAR (halbe Fahrschlauch-Breite)
        self.boden = Bodenmodell(self.kamera_cfg, {'weg_breite': self.p('fahrschlauch_breite') / 2})
        # Pruefblick (Kamera steiler nach unten, fuer Hindernisse zu nah fuer die Fahrstellung): eigenes Kameramodell
        self.boden_pruef = None
        if self.posen.get('fahrstellung') and self.posen.get('pruefblick'):
            try:
                cfg = armlib.kamera_fuer_pose(self.kamera_cfg, self.posen['fahrstellung'], self.posen['pruefblick'],
                                              self.eigene_kin.g)
            except Exception as e:      # Masse kaputt -> ohne Pruefblick
                self.get_logger().warn(f'Pruefblick: Kameramodell nicht berechenbar ({e})')
                cfg = None
            if cfg:
                self.boden_pruef = Bodenmodell(cfg, {'weg_breite': self.p('fahrschlauch_breite') / 2})
        self.ampel_werte = lade_ampel_werte()

        self.yolo, self.yolo_fehler = None, ''
        if self.p('gpu'):
            try:
                from yolo import YoloGpu, gpu_modell_suchen
                pfad = gpu_modell_suchen(REPO, self.p('gpu_modell'))
                if pfad:
                    self.get_logger().info(f'Lade KI-Modell fuer die Grafikkarte: {pfad} (dauert etwas) ...')
                    self.yolo = YoloGpu(pfad, self.p('imgsz'))
            except Exception as e:   # keine Grafikkarte, Ultralytics fehlt, .engine passt nicht zu TensorRT ...
                self.get_logger().warn(f'Grafikkarte geht nicht ({e}) -> KI rechnet auf dem Prozessor')
                self.yolo = None
        try:
            from yolo import Yolo
            if self.yolo is not None:
                pass
            elif os.path.exists(self.p('model')):
                self.yolo = Yolo(self.p('model'), self.p('imgsz'), kerne=self.p('kerne'))
            else:
                self.yolo_fehler = 'Modell fehlt: ' + self.p('model')
        except Exception as e:  # z. B. onnxruntime fehlt und OpenCV zu alt
            self.yolo_fehler = f'KI-Modell laesst sich nicht laden: {e}'
        if self.yolo_fehler:
            self.get_logger().error(self.yolo_fehler + '  -> nur Ersatz-Erkennung (LED, Form, Tiefe)')

        nur_neuestes = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT,
                                  history=HistoryPolicy.KEEP_LAST)
        self.create_subscription(Image, self.p('image_topic'), self._bild, nur_neuestes)
        if self.p('tiefe_nutzen'):
            self.create_subscription(Image, self.p('depth_topic'), self._tiefe, nur_neuestes)
        for i, t in enumerate(self.p('scan_topics')):
            self.create_subscription(LaserScan, t, lambda m, t=t, i=i: self._scan(m, t, i),
                                     qos_profile_sensor_data)
        self.create_subscription(String, '/ki/kommando', self._kommando, 10, callback_group=self.gruppe)
        self.pub_antwort = self.create_publisher(String, '/ki/antwort', 10)
        self.create_subscription(Imu, '/imu/data_raw', self._imu, qos_profile_sensor_data)
        self.create_subscription(Twist, '/cmd_vel', self._cmd, 10)
        # gefahrene Strecke (Radzaehler) fuer das blinde Heranfahren beim Wegraeumen
        self.strecke, self.odom_zeit = 0.0, 0.0
        self.odom_pose = None           # letzte Odometrie-Position (x, y, w)
        self.create_subscription(Odometry, '/odom_raw', self._odom, qos_profile_sensor_data)
        self.create_subscription(String, '/line_follower/status', self._linie, 10)
        self.pub_befehl = self.create_publisher(String, '/ki/befehl', 10)
        self.pub_ereignis = self.create_publisher(String, '/ki/ereignis', 50)
        self.pub_bild = self.create_publisher(CompressedImage, '/ki/bild/compressed', 1)
        self.create_timer(0.1, self._entscheiden, callback_group=self.gruppe)
        self.takt_letzt, self.takt_max = None, 0.0   # Abstand zwischen zwei Entscheidungen (Diagnose)
        self.bild_gesendet = 0.0
        self.laeuft = True
        threading.Thread(target=self._ki_schleife, daemon=True).start()
        backend = self.yolo.backend if self.yolo else 'ohne KI-Modell'
        self.get_logger().info(f'KI-Zentrale laeuft ({backend}), Arm erlaubt: {arm_erlaubt}')
        pol = self._politik(self.eigenes_modell)
        st = pol.lernstand()
        self._sende_ereignis(time.time(), f"Arm: {'KI darf ihn bewegen' if arm_erlaubt else 'fuer die KI AUS'}; "
                             f"Kinematik: {self.kinematik_text()}; Greif-Lernen: {st['herkunft']}, "
                             f"{st['versuche']} eigene Versuche", 'info')

    # ---------------- Arm, Greifen, Lernen ----------------
    def _arm_einstellung(self):
        """Schalter im Panel (ki_darf_arm_bewegen) gilt sofort, ohne Neustart."""
        try:
            darf = bool(armlib.lade_einstellungen().get('ki_darf_arm_bewegen')) and self.arm is not None
        except Exception:
            return
        if darf != self.entscheider.arm_freigabe:
            self.entscheider.arm_freigabe = darf
            self._sende_ereignis(time.time(), 'Arm: KI darf ihn jetzt bewegen' if darf else
                                 'Arm: fuer die KI ausgeschaltet (Panel)', 'info')

    def _politik(self, name):
        if name not in self.politik:
            self.politik[name] = greifen.Politik(name)
        return self.politik[name]

    def kinematik_text(self):
        if self.yahboom_kin is not None and self.yahboom_kin.bereit():
            return 'Yahbooms Dienst /get_kinemarics'
        return f'eigene Rechnung ({self.kin_quelle})'

    def greif_ergebnis(self, plan, erfolg):
        """Wegraeumen meldet: hat der Greifversuch geklappt? (Weg danach frei = Erfolg). Lernen + speichern."""
        l = plan['lernen']
        pol = self._politik(l['modell'])
        pol.ergebnis(l['obj'], l['a'], erfolg)
        pol.speichern()
        q = pol.quote()
        return (f"Greifversuch {pol.versuche}: {'Erfolg' if erfolg else 'daneben'}, Erfolgsquote "
                f"{q * 100:.0f} % (letzte {min(20, len(pol.verlauf))}), Korrektur jetzt "
                f"{pol.W[0, 0] * 100:+.1f} / {pol.W[1, 0] * 100:+.1f} / {pol.W[2, 0] * 100:+.1f} cm")

    def p(self, name):
        return self.get_parameter(name).value

    # ---------------- Eingaenge ----------------
    def _bild(self, msg):
        with self.lock:
            self.bild = msg

    def _tiefe(self, msg):
        with self.lock:
            self.tiefe = msg

    def _scan(self, msg, topic, i):
        fronts = self.p('scan_front_deg')
        front = fronts[i] if i < len(fronts) else 0.0
        xy = lidar.punkte_xy(msg, front, self.p('obstacle_min_range'))
        breit = lidar.naechster_vorne(msg, front, 60.0, self.p('obstacle_min_range'))   # fuer Zebrastreifen
        with self.lock:
            self.scans[topic] = (time.time(), xy, breit)

    def _imu(self, msg):
        # Drehung um die Hochachse aufsummieren (fuer das Wenden)
        jetzt = time.time()
        dt = min(0.1, jetzt - self.imu_zeit) if self.imu_zeit else 0.0
        self.imu_zeit = jetzt
        self.gier += msg.angular_velocity.z * dt

    def _cmd(self, msg):
        # Ersatz, falls kein Lagesensor (IMU) Daten liefert: befohlene Drehung aufsummieren
        jetzt = time.time()
        dt = min(0.1, jetzt - self.gier_zeit)
        self.gier_zeit = jetzt
        if jetzt - self.imu_zeit > 1.0:
            self.gier += msg.angular.z * dt
        if jetzt - self.odom_zeit > 1.0:
            self.strecke += msg.linear.x * dt     # keine Radzaehler: befohlene Strecke (ungenauer)

    def _odom(self, msg):
        jetzt = time.time()
        dt = min(0.2, jetzt - self.odom_zeit) if self.odom_zeit else 0.0
        self.odom_zeit = jetzt
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        w = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        alt, self.odom_pose = self.odom_pose, (p.x, p.y, w)
        if alt is not None and math.hypot(p.x - alt[0], p.y - alt[1]) < 0.5:
            # Positions-Unterschied in Fahrtrichtung: geht auch ueber verlorene Nachrichten nichts verloren
            # (Geschwindigkeit x Zeit verlor bei Rechner-Haengern von 1-3 s Strecke, 20.10.)
            self.strecke += (p.x - alt[0]) * math.cos(alt[2]) + (p.y - alt[1]) * math.sin(alt[2])
        else:
            self.strecke += msg.twist.twist.linear.x * dt

    def _linie(self, msg):
        try:
            st = json.loads(msg.data)
            st['_zeit'] = time.time()
            self.linie_status = st
        except ValueError:
            pass

    def _kommando(self, msg):
        if msg.data.strip() == 'greifen_zuruecksetzen':
            # alle Modelle, auch die, die seit dem Start noch nicht geladen wurden (z. B. 'yahboom')
            namen = set(self.politik) | set((greifen._lies(greifen.LOKAL) or {}).get('modelle') or {})
            for name in namen or {self.eigenes_modell}:
                self._politik(name).zuruecksetzen()
            antwort = 'Gelerntes Greifen zurueckgesetzt (zurueck zum Vortraining)'
            self._sende_ereignis(time.time(), antwort, 'info')
            self.pub_antwort.publish(String(data=antwort))
            return
        antwort = self.entscheider.kommando(time.time(), msg.data.strip())
        self.get_logger().info(f'Kommando {msg.data}: {antwort}')
        self.pub_antwort.publish(String(data=antwort))

    def kamera_lage(self):
        """(ok, gier): ok = Kamera schaut normal nach vorne (Draufsicht, Linie, Tiefe stimmen),
        gier = Drehung (Grad) des Arms gegenueber der Fahrstellung oder None (unbekannt / Arm faehrt)."""
        fahr, gier = self.arm_beobachter.kamera(self.posen, time.time())
        ok = fahr and self.entscheider.arm_in_fahrstellung
        return ok, (0.0 if ok else gier)

    def lidar_hinten(self):
        """Frei nach hinten (m) im Streifen der Roboterbreite, None = keine LiDAR-Daten (dann nie rueckwaerts)."""
        if self.lidar_xy is None or self.lidar_d is None:
            return None
        xy = self.lidar_xy
        hinten = xy[(xy[:, 0] < -0.05) & (np.abs(xy[:, 1]) < self.p('fahrschlauch_breite') / 2)]
        return float(-hinten[:, 0].max()) if len(hinten) else 5.0

    def weg_voraus(self):
        """Linie vor dem Roboter vom Linienfolger (fuer den Fahrschlauch) oder None = geradeaus."""
        st = self.linie_status
        if time.time() - st.get('_zeit', 0.0) < 0.5 and st.get('weg'):
            return st['weg']
        return None

    def lidar_pruefen(self):
        """(Abstand im Fahrschlauch: m, inf = frei, None = keine LiDAR-Daten; Objekt oder None;
        Abstand im breiten Bereich vorne fuer den Zebrastreifen)."""
        jetzt = time.time()
        with self.lock:
            frisch = [(xy, b) for z, xy, b in self.scans.values() if jetzt - z < 1.0]
        if not frisch:
            return None, None, None
        self.lidar_xy = np.vstack([xy for xy, _ in frisch])   # alle Punkte (fuer den Zebrastreifen)
        weg = self.weg_voraus()
        objekte = [lidar.fahrschlauch(xy, weg, self.p('fahrschlauch_breite') / 2, self.p('fahrschlauch_laenge'),
                                      nah_halb_deg=self.p('obstacle_half_deg')) for xy, _ in frisch]
        objekte = [o for o in objekte if o]
        breit = min(b for _, b in frisch)
        if not objekte:
            return float('inf'), None, breit
        o = dict(min(objekte, key=lambda o: o['abstand']))
        o['quelle'] = 'lidar'
        return o['abstand'], o, breit

    # ---------------- Kamera auswerten (eigener Thread) ----------------
    def _ki_schleife(self):
        letzte = None
        while self.laeuft and rclpy.ok():
            start = time.time()
            with self.lock:
                msg, tmsg = self.bild, self.tiefe
            if msg is None or msg is letzte:
                time.sleep(0.02)
                continue
            letzte = msg
            try:
                self._auswerten(msg, tmsg)
            except Exception as e:
                self.get_logger().error(f'KI-Fehler: {e}', throttle_duration_sec=5.0)
            dauer = time.time() - start
            if dauer > 0.5:
                self.get_logger().warn(f'KI-Bild dauerte {dauer:.2f} s (Modell {self.ki_ms:.0f} ms) - Rechner ueberlastet?',
                                       throttle_duration_sec=10.0)
            rest = 1.0 / self.p('rate') - (time.time() - start)
            if rest > 0:
                time.sleep(rest)

    def _auswerten(self, msg, tmsg):
        img = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
        h, w = img.shape[:2]
        t0 = time.time()
        objekte = self.yolo.erkenne(img, self.p('min_conf')) if self.yolo else []

        ampel_farbe, ampel_quelle, schild, schild_quelle = None, None, False, None
        for o in objekte:
            x, y, bw, bh = o['box']
            mitte = (x + bw / 2) / w
            o['im_weg'] = bool(o['name'] in STOPP_NAMEN and o['sicher'] >= self.p('weg_min_conf')
                               and self.p('weg_links') <= mitte <= self.p('weg_rechts')
                               and (y + bh) / h >= self.p('weg_unten_min') and bh / h >= self.p('weg_min_hoehe'))
            if o['name'] == 'Ampel' and bh / h >= self.p('ampel_min_hoehe'):
                o['farbe'] = ampel.farbe_in_box(img, o['box'])
                if o['farbe'] and ampel_farbe is None:
                    ampel_farbe, ampel_quelle = o['farbe'], f"KI {o['sicher']:.0%}"
            if o['name'] == 'Stoppschild' and bh / h >= self.p('schild_min_hoehe'):
                schild, schild_quelle = True, f"KI {o['sicher']:.0%}"

        led = None
        if ampel_farbe is None and self.p('led_ersatz'):
            led = ampel.finde_ampel(img, self.ampel_werte)
            if led['farbe']:
                ampel_farbe, ampel_quelle = led['farbe'], 'LED-Erkennung'
        form = None
        if not schild and self.p('form_ersatz'):
            form = schilder.finde_stoppschild(img, {})
            # erst halten, wenn das Schild nah ist (gleiche Regel wie bei der KI: Mindesthoehe im Bild)
            if form['treffer'] is not None and form['treffer'][3] / h >= self.p('schild_min_hoehe'):
                schild, schild_quelle = True, 'Form-Erkennung (Achteck)'

        # Kameramodell (Draufsicht, Tiefenkamera) stimmt nur, wenn der Arm in Fahrstellung steht
        fahrstellung = self.kamera_lage()[0]
        einfahrt = schilder.finde_einfahrt_verboten(img) if fahrstellung else None
        zebra, vogel = None, None
        if fahrstellung:
            vogel = self.linien_sucher.vogel(img)     # nur die Draufsicht, die Linie sucht der Linienfolger
            zebra = finde_zebra(vogel, self.linien_sucher.RASTER, self.linien_sucher.VORNE[1])

        tiefe_hindernis, tiefe_obj = None, None
        if tmsg is not None and fahrstellung:
            d = self.bridge.imgmsg_to_cv2(tmsg, 'passthrough').astype(np.float32)
            if tmsg.encoding != '32FC1':
                d /= 1000.0  # Millimeter -> Meter
            lid = self.lidar_d
            frei = (lid is None or lid >= self.entscheider.c['pruef_dist']) and self.entscheider.ablauf is None
            tiefe_hindernis, tiefe_obj = self.boden.pruefe(d, lernen=frei, linie_voraus=self.weg_voraus())
            if tiefe_obj:
                tiefe_obj['quelle'] = 'tiefe'
        elif (tmsg is not None and self.boden_pruef is not None
              and self.arm_beobachter.in_pose(self.posen['pruefblick'], time.time())):
            # Arm steht im Pruefblick: mit dessen Kameramodell messen (Boden dort nicht gelernt -> nicht lernen)
            d = self.bridge.imgmsg_to_cv2(tmsg, 'passthrough').astype(np.float32)
            if tmsg.encoding != '32FC1':
                d /= 1000.0
            tiefe_hindernis, tiefe_obj = self.boden_pruef.pruefe(d, lernen=False)
            if tiefe_obj:
                tiefe_obj.update(quelle='tiefe', blick='pruef', blick_winkel=list(self.posen['pruefblick']))

        self.ki_ms = (time.time() - t0) * 1000
        with self.lock:
            nr = self.wahrnehmung['bild_nr'] + 1
            self.wahrnehmung = {'bild_nr': nr, 'bild_zeit': time.time(), 'objekte': objekte,
                                'ampel': ampel_farbe, 'ampel_quelle': ampel_quelle,
                                'stoppschild': schild, 'schild_quelle': schild_quelle,
                                'tiefe_hindernis': tiefe_hindernis, 'tiefe_objekt': tiefe_obj,
                                'zebra': zebra, 'einfahrt_verboten': einfahrt is not None}
            befehl = dict(self.befehl)
        self.letzte_extras = {'einfahrt': einfahrt, 'zebra': zebra, 'tiefe': tiefe_obj}
        # Bild fuers Panel (Zeichnen + JPEG kostet Rechenzeit): nur wenn jemand zuschaut, hoechstens 3x pro Sekunde
        jetzt = time.time()
        if jetzt - self.bild_gesendet >= 1.0 / 3 and self.pub_bild.get_subscription_count() > 0:
            self.bild_gesendet = jetzt
            self._bild_senden(msg, img, objekte, led, form, ampel_farbe, ampel_quelle, schild, befehl)

    def _bild_senden(self, msg, img, objekte, led, form, ampel_farbe, ampel_quelle, schild, befehl):
        view = img
        h, w = view.shape[:2]
        x0, x1 = int(w * self.p('weg_links')), int(w * self.p('weg_rechts'))
        cv2.rectangle(view, (x0, int(h * self.p('weg_unten_min'))), (x1, h - 1), (255, 0, 255), 1)
        for o in objekte:
            x, y, bw, bh = o['box']
            farbe = (0, 0, 255) if o.get('im_weg') else FARBE_BGR.get(o.get('farbe'), (0, 255, 0))
            cv2.rectangle(view, (x, y), (x + bw, y + bh), farbe, 2)
            text = f"{o['name']} {o['sicher']:.0%}" + (f" {o['farbe']}" if o.get('farbe') else '')
            cv2.putText(view, text, (x, max(14, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, farbe, 2)
        if led and led['farbe']:
            x, y, bw, bh = led['lampen'][led['farbe']]['treffer']
            cv2.circle(view, (x + bw // 2, y + bh // 2), max(bw, bh) + 6, FARBE_BGR[led['farbe']], 3)
        if form and form['treffer'] is not None:
            schilder.zeichne(view, form)
        extras = getattr(self, 'letzte_extras', {})
        if extras.get('einfahrt'):
            x, y, bw, bh = extras['einfahrt']
            cv2.rectangle(view, (x, y), (x + bw, y + bh), (255, 255, 255), 3)
            cv2.putText(view, 'EINFAHRT VERBOTEN', (x, max(14, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
        if extras.get('zebra'):
            cv2.putText(view, f"ZEBRASTREIFEN {extras['zebra']['abstand'] * 100:.0f} cm", (10, h - 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        if extras.get('tiefe'):
            o = extras['tiefe']
            cv2.putText(view, f"HINDERNIS (Tiefe) {o['vor'] * 100:.0f} cm, {o['breite'] * 100:.0f} cm breit, "
                              f"{o['hoehe'] * 100:.0f} cm hoch", (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
        # Kopfzeile: Entscheidung
        farbe = AKTION_BGR.get(befehl['aktion'], (80, 80, 80))
        cv2.rectangle(view, (0, 0), (w, 34), farbe, -1)
        cv2.putText(view, f"{befehl['aktion'].upper()}: {befehl['grund']}"[:70], (8, 23),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        if w > 640:
            view = cv2.resize(view, (640, int(h * 640 / w)))
        ok, jpg = cv2.imencode('.jpg', view, [cv2.IMWRITE_JPEG_QUALITY, 65])
        if ok:
            self.pub_bild.publish(CompressedImage(header=msg.header, format='jpeg', data=jpg.tobytes()))

    # ---------------- Entscheiden (10x pro Sekunde) ----------------
    def _entscheiden(self):
        jetzt = time.time()
        if self.takt_letzt is not None:
            luecke = jetzt - self.takt_letzt
            self.takt_max = max(self.takt_max * 0.98, luecke)
            if luecke > 0.4:
                self.get_logger().warn(f'Entscheiden kam {luecke:.2f} s zu spaet (soll 0,1 s) - Rechner ueberlastet?',
                                       throttle_duration_sec=5.0)
        self.takt_letzt = jetzt
        with self.lock:
            w = dict(self.wahrnehmung)
        w['lidar'], lid_obj, w['lidar_breit'] = self.lidar_pruefen()
        self.lidar_d = w['lidar']
        w['lidar_xy'] = self.lidar_xy if w['lidar'] is not None else None
        w['lidar_hinten'] = self.lidar_hinten()
        w['weg'] = self.weg_voraus()
        w['gier'] = self.gier
        w['strecke'] = self.strecke
        st = self.linie_status
        # Faehrt das Fahrprogramm wirklich? Nur dann darf die KI den Arm bewegen (nicht im TEST, nicht nach STOPP)
        self.entscheider.fahrt_aktiv = bool(st.get('drive')) and jetzt - st.get('_zeit', 0.0) < 1.0
        w['linie'] = {'kamera': bool(st.get('linie_kamera')), 'quer': st.get('linie_quer'), 'kurs': st.get('linie_kurs'),
                      'kamera_quer': st.get('kamera_quer'), 'kamera_kurs': st.get('kamera_kurs')}
        # Hindernis fuer Aufheben/Anhalten: Tiefenkamera (sieht auch Flaches), sonst LiDAR
        if lid_obj and lid_obj['abstand'] >= self.entscheider.c['pruef_dist']:
            lid_obj = None
        w['objekt'] = w.get('tiefe_objekt') or lid_obj
        befehl = self.entscheider.update(jetzt, w)
        # Arm nur, wenn freigegeben (zurueck in die Fahrstellung darf er immer)
        arm = befehl['arm']
        zurueck = arm == 'fahrstellung' or (isinstance(arm, dict) and arm.get('pose') == 'fahrstellung')
        if arm and self.arm is not None and (self.entscheider.arm_freigabe or zurueck):
            self._arm_befehl(befehl['arm'])
        with self.lock:
            self.befehl = befehl
        for zeit, text, art in self.entscheider.ereignisse:
            self._sende_ereignis(zeit, text, art)
        self.entscheider.ereignisse.clear()
        kamera_ok, kamera_gier = self.kamera_lage()
        info = dict(befehl)
        info.update({
            'zeit': jetzt,
            'ki': self.yolo.backend if self.yolo else self.yolo_fehler, 'ki_ms': round(self.ki_ms),
            'takt_max_ms': round(self.takt_max * 1000),
            'bild_alter': round(jetzt - w['bild_zeit'], 2) if w['bild_zeit'] else None,
            'lidar': None if w['lidar'] is None else (99.0 if w['lidar'] == float('inf') else round(w['lidar'], 3)),
            'ampel': w['ampel'], 'ampel_quelle': w.get('ampel_quelle'),
            'stoppschild': w['stoppschild'], 'schild_quelle': w.get('schild_quelle'),
            'tiefe_hindernis': w['tiefe_hindernis'],
            'objekte': [{'name': o['name'], 'sicher': o['sicher'], 'im_weg': o.get('im_weg', False),
                         'farbe': o.get('farbe')} for o in w['objekte']],
            'arm_erlaubt': self.entscheider.arm_freigabe,
            'arm_status': self.entscheider.warum_kein_arm() or 'bereit (KI darf wegraeumen)',
            'kinematik': self.kinematik_text(),
            'greifen': self._politik(self.eigenes_modell).lernstand(),
            'zebra': w.get('zebra'), 'einfahrt_verboten': w.get('einfahrt_verboten', False),
            'kamera_ok': kamera_ok, 'kamera_gier': kamera_gier,   # Linienfolger/Kartograf: wohin schaut die Kamera?
            'objekt': w.get('objekt'), 'weg': self.weg_voraus(), 'fahrschlauch': self.p('fahrschlauch_breite'),
            'ablauf': self.entscheider.ablauf.name if self.entscheider.ablauf else None,
            'ablauf_phase': self.entscheider.ablauf.phase if self.entscheider.ablauf else None,
        })
        self.pub_befehl.publish(String(data=json.dumps(info)))

    def planen(self, obj, seite):
        """Armbewegung zum Wegraeumen ausrechnen (laeuft in einem eigenen Thread, siehe ki/ablaeufe.py).
        obj: gemessenes Hindernis (Tiefenkamera, Roboter-System), seite: Ablage +1 links / -1 rechts.
        Zielpunkt + gelernte Korrektur (lib/greifen.py), probiert dabei etwas aus (lernt daraus)."""
        fahr = self.posen['fahrstellung']
        auf = armlib.greifer_werte()[0]
        anlegen, zu = armlib.greifer_fuer_breite(obj['breite'])
        kin = self.yahboom_kin
        if kin is not None and kin.bereit() and obj.get('pixel') and obj.get('tiefe_m'):
            p = kin.kamera_zu_basis(obj['pixel'], obj['tiefe_m'], obj.get('blick_winkel') or fahr)
            if p is None:
                return {'fehler': 'Yahboom-Kinematik antwortet nicht'}
            # Kamerapunkt liegt auf der Vorderseite/Oberseite -> etwas weiter hinein greifen.
            # Ist er naeher herangefahren (obj['vor'] kleiner als gemessen), verschiebt sich der Punkt mit.
            versatz = obj.get('vor_gemessen', obj['vor']) - obj['vor']
            punkt = (p[0] + obj['breite'] / 4 - versatz, p[1], p[2])
            boden = p[2] - obj['hoehe'] / 2
            def ik(x, y, z):
                # Yahboom rechnet mit fester Handneigung; zur Seite (Ablage) reicht 80 Grad oft nicht -> flacher
                for neigung in (80.0, 65.0, 50.0):
                    w = kin.inverse(x, y, z, neigung=neigung, aktuell=fahr)
                    if w is not None:
                        return w
                return None
            plan = greifen.plane(obj, seite, ik, fahr, auf, zu,
                                 self._politik('yahboom'), punkt=punkt, boden=boden, anlegen=anlegen)
            plan['info'] = plan.get('info', '') + f' (Yahboom-Kinematik, Greifer {zu})'
            return plan
        plan = greifen.plane(obj, seite, self.eigene_kin.inverse, fahr, auf, zu, self._politik(self.eigenes_modell),
                             anlegen=anlegen)
        plan['info'] = plan.get('info', '') + f' (eigene Kinematik, {self.kin_quelle}, Greifer {zu})'
        return plan

    def _arm_befehl(self, arm):
        """arm: Posenname, {'pose': Name, 'greifer': 'auf' | 'zu' | None} oder {'winkel': [6], 'zeit_ms'}."""
        if isinstance(arm, str):
            arm = {'pose': arm}
        if arm.get('winkel'):
            fehler = self.arm.fahre(list(arm['winkel']), int(arm.get('zeit_ms', 1200)))
            if fehler:
                self.get_logger().error(f'Arm: {fehler}')
            return
        winkel = self.posen.get(arm['pose'])
        if not winkel:
            self.get_logger().error(f"Arm: Pose '{arm['pose']}' fehlt (im Panel einlernen)")
            return
        winkel = list(winkel)
        auf, zu = armlib.greifer_werte()
        if arm.get('greifer') == 'auf':
            winkel[5] = auf
        elif arm.get('greifer') == 'zu':
            winkel[5] = zu
        fehler = self.arm.fahre(winkel, 1200)
        if fehler:
            self.get_logger().error(f'Arm: {fehler}')

    def _sende_ereignis(self, zeit, text, art):
        self.get_logger().info(text)
        self.pub_ereignis.publish(String(data=json.dumps({'zeit': zeit, 'text': text, 'art': art})))


def laeuft_schon(name):
    """Gibt es schon ein Programm mit diesem ROS-Namen? (zwei KIs wuerden sich widersprechen)"""
    pruefer = rclpy.create_node('pruefe_' + name + f'_{os.getpid()}')
    time.sleep(1.5)  # ROS braucht kurz, bis es die anderen kennt
    gefunden = name in pruefer.get_node_names()
    pruefer.destroy_node()
    return gefunden


def signale_abfangen():
    """Strg+C, Beenden und Fenster-zu immer als KeyboardInterrupt behandeln (sauberes Ende).
    Noetig, weil mit '&' aus Skripten gestartete Programme Strg+C sonst ignorieren."""
    def ende(*_):
        raise KeyboardInterrupt
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, ende)


def main():
    signale_abfangen()
    rclpy.init()
    if laeuft_schon('ki_zentrale'):
        print('FEHLER: Es laeuft schon eine KI-Zentrale. Zwei wuerden sich widersprechen -> Abbruch.')
        rclpy.shutdown()
        sys.exit(1)
    node = Zentrale()
    executor = MultiThreadedExecutor(num_threads=2)   # Sensoren | Entscheiden (siehe self.gruppe)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.laeuft = False
        executor.shutdown()
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    main()
