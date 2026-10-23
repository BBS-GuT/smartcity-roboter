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
cv2.setNumThreads(1)   # OpenCV-Threads (pthreads, OMP_NUM_THREADS wirkt nicht): gleiche Wandzeit, halbe CPU
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
import lidar_fusion   # noqa: E402
import fahrtest       # noqa: E402
import arm as armlib  # noqa: E402
import greifen        # noqa: E402
from tiefe import Bodenmodell, abstand_im_kasten, spielfigur, tiefe_passt   # noqa: E402
from tiefenstatus import Zielbestaetigung, tiefe_messung_gueltig, raeum_pruefung, fahrraum_frei  # noqa: E402
import sensorstatus  # noqa: E402
from entscheider import Entscheider, STANDARD as KI_STANDARD  # noqa: E402
from ablaeufe import LEBEWESEN, FAHRZEUGE, akteur_einordnen  # noqa: E402

# Diese Dinge fuehren zum Anhalten, wenn die Kamera-KI sie im Weg sieht. Nur Verkehrsteilnehmer:
# Moebel/Gegenstaende (Stuhl, Flasche ...) erkennt YOLO oft falsch, z. B. die schwarze Kurve als "Stuhl".
# Echte Hindernisse auf der Strasse finden LiDAR und Tiefenkamera trotzdem.
# Radzaehler (/odom_raw, Yahboom ca. 20-50 Hz) gelten als frisch, wenn die letzte Meldung so jung ist (s). Laenger ohne
# Meldung: gefahrene Strecke ist nicht mehr gemessen (blindes Greifen nicht erlaubt), danach beginnt ein neuer Abschnitt
ODOM_FRISCH = 0.3
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
        dp('depth_info_topic', '/camera/depth/camera_info')
        dp('bodenreferenz', os.path.join(REPO, 'lib', 'bodenreferenz_rm01.npz'))
        dp('tiefe_nutzen', True)
        dp('begleiteter_fahrbetrieb', False)
        self.add_on_set_parameters_callback(fahrtest.parameter_aenderung)
        dp('led_ersatz', True)          # LED-Erkennung, wenn die KI keine Ampel findet
        dp('form_ersatz', True)         # Achteck-Erkennung, wenn die KI kein Stoppschild findet
        dp('ampel_min_hoehe', 0.03)     # KI-Ampel muss mind. so hoch sein (Anteil Bildhoehe) = nah genug
        dp('schild_min_hoehe', 0.12)    # KI-Stoppschild muss mind. so hoch sein = nah genug
        dp('weg_links', 0.2)            # "im Weg" = Kasten mittig ...
        dp('weg_rechts', 0.8)
        dp('weg_unten_min', 0.5)        # ... Unterkante in der unteren Bildhaelfte ...
        dp('weg_min_hoehe', 0.15)       # ... und gross genug (= nah)
        # Wegraeumen: nur Personen/Tiere/Fahrzeuge zaehlen, die so nah sind (m ab Kamera, Tiefenkamera). Weiter weg
        # (Hintergrund) halten sie das Wegraeumen nicht auf. Ohne sichere Tiefe im Kasten zaehlen sie (vorsichtig).
        dp('akteur_nah', 1.0)
        # Projektinhaber 22.10.: Personen/Tiere/Fahrzeuge halten ihn nicht auf (es gibt noch keine auf dem Brett, der
        # Roboter ist ungefaehrlich). False: sie zaehlen weder als 'nah' (Wegraeumen wartet nicht, faesst an) noch als
        # 'im Weg'. Hindernisse sehen LiDAR und Tiefenkamera weiter. Zebrastreifen wartet weiter auf Spielfiguren.
        dp('akteure_beachten', False)
        # Nur diese KI-Klassen gibt es in der SmartCity (Projektinhaber 21.10.: Spielfiguren, Ampeln, Stoppschilder;
        # Einbahnschilder erkennt schilder.py). Alles andere (Vogel, Auto, Stuhl ...) waren Fehlerkennungen oder
        # Dinge neben dem Spielfeld -> verworfen. Teddy: so erkennt das Modell Spielfiguren manchmal. Leer = alle.
        dp('ki_klassen', ['Person', 'Teddy', 'Ampel', 'Stoppschild'])
        # Spielfigur oder echter Mensch? Geschaetzte Groesse (Kastenhoehe x Abstand) bis hierhin = Figur (m)
        dp('figur_max_hoehe', 0.30)
        dp('scan_topics', ['/scan0', '/scan1'])
        dp('scan_front_deg', [0.0, 0.0])
        self.scan_geometrie = lidar_fusion.Geometrie(self)
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
        self.lidar_luecken = np.zeros(0)  # Winkel der Strahlen ohne Messung (alle Pflicht-LiDARs, fuer hinten)
        self.scan_reichweite = {}         # Kanal -> frei gemessene Reichweite je Richtung (lidar.freie_reichweite)
        self.lidar_reichweite = None      # davon das Minimum ueber alle Pflicht-LiDARs (Zebrastreifen #156)
        self.lidar_sicht = None

        self.bridge = CvBridge()
        self.lock = threading.Lock()
        self.bild = None                # neuestes Kamerabild (ROS-Nachricht)
        self.tiefe = None
        self.tiefe_ausgewertet, self.tiefe_nr = None, 0   # zuletzt ausgewertetes Tiefenbild, Zaehler
        self.tiefeninfo = None
        self.zielbestaetigung = Zielbestaetigung()
        self.aktionsstatus = None
        self.arm_aktionen = set()
        self.betriebsepoche = None
        self.planbindung = None
        self.auftragbindung = None
        self.odom_bewegung = None
        self.bild_empfang = self.tiefe_empfang = None   # monotone Empfangszeit (Paarpruefung Farbe/Tiefe)
        self.scan_lock = threading.Lock()  # Geometrie und Kanalstatus bilden genau einen Scanstand
        self.scans = {}
        self.scan_stempel = {}          # Kanal -> neueste akzeptierte Aufnahmezeit (muss vorwaerts laufen)
        self.wahrnehmung = {'bild_nr': 0, 'bild_zeit': 0.0, 'objekte': [], 'ampel': None,
                            'stoppschild': False, 'tiefe_hindernis': None}
        self.befehl = {'aktion': 'stopp', 'faktor': 0.0, 'grund': 'KI startet ...', 'arm': None}
        self.ki_ms = 0.0
        # Tiefenkamera prueft denselben Fahrweg wie der LiDAR (halbe Fahrschlauch-Breite)
        self.boden = Bodenmodell(self.kamera_cfg, {'weg_breite': self.p('fahrschlauch_breite') / 2})
        self.kalibriertes_bodenmodell = Bodenmodell(self.kamera_cfg, {'weg_breite': self.p('fahrschlauch_breite') / 2})
        try:
            self.kalibriertes_bodenmodell.lade_referenz(self.p('bodenreferenz'), self.posen.get('fahrstellung'))
        except (OSError, ValueError, KeyError) as e:
            self.get_logger().warn(f'Bodenreferenz nicht verwendbar: {e}')
        self.lidar_luecke = None
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
                # A named look pose is not evidence of a different calibrated view.
                try:
                    self.boden_pruef.lade_referenz(self.p('bodenreferenz'), self.posen['pruefblick'])
                except (OSError, ValueError, KeyError):
                    self.boden_pruef = None
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
            # CameraInfo is required to match the measured reference intrinsics.
            try:
                from sensor_msgs.msg import CameraInfo
            except ImportError:
                CameraInfo = None  # Test stubs; without metadata reference remains unusable.
            if CameraInfo is not None:
                self.create_subscription(CameraInfo, self.p('depth_info_topic'), self._tiefeninfo, nur_neuestes)
        for i, t in enumerate(self.p('scan_topics')):
            self.create_subscription(LaserScan, t, lambda m, t=t, i=i: self._scan(m, t, i),
                                     qos_profile_sensor_data)
        self.create_subscription(String, '/ki/kommando', self._kommando, 10, callback_group=self.gruppe)
        self.pub_antwort = self.create_publisher(String, '/ki/antwort', 10)
        self.create_subscription(Imu, '/imu/data_raw', self._imu, qos_profile_sensor_data)
        self.create_subscription(Twist, '/cmd_vel', self._cmd, 10)
        # gefahrene Strecke (Radzaehler) fuer das blinde Heranfahren beim Wegraeumen
        self.strecke, self.odom_zeit = 0.0, 0.0
        self.odom_abschnitt = 0         # zaehlt hoch, wenn die Radzaehler nach einer Luecke (> 1 s) wiederkommen
        self.strecke_geschaetzt = 0.0   # seit der letzten Radmeldung aus /cmd_vel geschaetzter Anteil von strecke
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
                             f"{st['versuche']} eigene Versuche; Greifer: {armlib.greifer_stand()}", 'info')

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

    def ros_jetzt(self):
        """ROS-Zeit dieses Knotens (s) - dieselbe Uhr wie header.stamp, auch mit use_sim_time."""
        return self.get_clock().now().nanoseconds * 1e-9

    # ---------------- Eingaenge ----------------
    def _bild(self, msg):
        with self.lock:
            self.bild, self.bild_empfang = msg, time.monotonic()

    def _tiefe(self, msg):
        with self.lock:
            self.tiefe, self.tiefe_empfang = msg, time.monotonic()

    def _tiefeninfo(self, msg):
        self.tiefeninfo = (list(msg.k), (msg.height, msg.width), msg.header.frame_id, time.monotonic())

    def _scan(self, msg, topic, i):
        empfang = time.monotonic()
        fronts = self.p('scan_front_deg')
        front = fronts[i] if i < len(fronts) else 0.0
        # Aufnahmezeit (header.stamp) getrennt vom Empfang: frisch empfangen heisst nicht frisch gemessen
        aufnahme, grund = lidar.aufnahme_pruefen(msg, self.ros_jetzt(), self.scan_stempel.get(topic),
                                                   max_zukunft=fahrtest.scan_uhrspielraum(self))
        if grund == 'doppelt':
            return                          # derselbe Scan nochmal: nichts Neues, Empfangszeit nicht erneuern
        if grund is None:
            self.scan_stempel[topic] = aufnahme     # Fortschritt nur mit akzeptiertem, neuerem Stempel
        grund = grund or lidar.scan_pruefen(msg)     # unbrauchbarer Scan = unbekannt, nie "frei"
        feld, geometrie_grund = self.scan_geometrie.vorbereiten(msg, topic, aufnahme)
        grund = grund or geometrie_grund
        xy = breit = luecken = reichweite = None
        if grund is None:
            xy = lidar.punkte_xy(msg, front, self.p('obstacle_min_range'))
            breit = lidar.naechster_vorne(msg, front, 60.0, self.p('obstacle_min_range'))   # fuer Zebrastreifen
            luecken = lidar.ungueltige_winkel(msg, front)   # Strahlen ohne Messung: dort ist nichts bekannt
            reichweite = lidar.freie_reichweite(msg, front)  # je Richtung frei gemessen bis (dahinter verdeckt)
        with self.scan_lock:
            self.scan_geometrie.uebernehmen(topic, feld)
            self.scans[topic] = (empfang, xy, breit, grund, aufnahme, luecken)
            self.scan_reichweite[topic] = reichweite

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
            self.strecke_geschaetzt += msg.linear.x * dt

    def _odom(self, msg):
        jetzt = time.time()
        luecke = jetzt - self.odom_zeit > ODOM_FRISCH  # Meldungen fehlten: Strecke dazwischen nicht durchgehend gemessen
        if luecke:
            self.odom_abschnitt += 1
        dt = min(0.2, jetzt - self.odom_zeit) if self.odom_zeit else 0.0
        self.odom_zeit = jetzt
        self.odom_bewegung = (msg.twist.twist.linear.x, msg.twist.twist.linear.y, msg.twist.twist.angular.z)
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        w = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        alt, self.odom_pose = self.odom_pose, (p.x, p.y, w)
        # Radzaehler wieder da: die Schaetzung aus der Luecke durch die gemessene Bewegung ersetzen (nicht doppelt)
        geschaetzt, self.strecke_geschaetzt = self.strecke_geschaetzt, 0.0
        if alt is not None and math.hypot(p.x - alt[0], p.y - alt[1]) < 0.5:
            self.strecke -= geschaetzt
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
        if self.lidar_sicht is not None:
            sicht = self.lidar_sicht
            return sicht.hinten(self.p('fahrschlauch_breite') / 2,
                                abdeckung_pflicht=not self.p('begleiteter_fahrbetrieb'))
        xy = self.lidar_xy
        hinten = xy[(xy[:, 0] < -0.05) & (np.abs(xy[:, 1]) < self.p('fahrschlauch_breite') / 2)]
        frei = float(-hinten[:, 0].max()) if len(hinten) else 5.0
        # nur so weit frei, wie gemessen: ein Strahl ohne Messung im Streifen begrenzt den freien Rueckraum
        luecke = lidar.hinten_luecke(self.lidar_luecken, self.p('fahrschlauch_breite') / 2)
        return frei if luecke is None else min(frei, luecke)

    def weg_voraus(self):
        """Linie vor dem Roboter vom Linienfolger (fuer den Fahrschlauch) oder None = geradeaus."""
        st = self.linie_status
        if time.time() - st.get('_zeit', 0.0) < 0.5 and st.get('weg'):
            return st['weg']
        return None

    def lidar_pruefen(self):
        """(Abstand im Fahrschlauch: m, inf = frei, None = keine LiDAR-Daten; Objekt oder None;
        Abstand im breiten Bereich vorne fuer den Zebrastreifen)."""
        topics = self.p('scan_topics')
        self.lidar_sicht = None
        self.lidar_luecke = None
        with self.scan_lock:
            scanstand = self.scans.copy()
            felder = self.scan_geometrie.received.copy()
            reichweiten_stand = self.scan_reichweite.copy()
        # Jeder Kanal in scan_topics ist Pflicht: ein frischer zweiter LiDAR ersetzt keinen fehlenden/alten
        frisch, grund = lidar.pflichtkanaele(scanstand, topics, time.monotonic())
        jetzt = self.ros_jetzt()     # Aufnahmealter jetzt nochmal: der Scan kann seit dem Empfang gealtert sein
        ungueltig = [f'{t}: {g or lidar.aufnahme_alter(a, jetzt, max_zukunft=fahrtest.scan_uhrspielraum(self))}' for t, (_, _, _, g, a, _) in zip(topics, frisch)
                     if g or lidar.aufnahme_alter(a, jetzt, max_zukunft=fahrtest.scan_uhrspielraum(self))]
        if grund or ungueltig:
            # Fehlender/alter Pflichtkanal oder unbrauchbarer Scan: wie keine LiDAR-Daten (Entscheider haelt)
            self.lidar_xy = None
            self.get_logger().warn('LiDAR unbekannt: ' + (grund or '; '.join(ungueltig)), throttle_duration_sec=2.0)
            return None, None, None
        stamps = {t: e[4] for t, e in zip(topics, frisch)}
        sicht, geometrie_grund = self.scan_geometrie.sicht(stamps, felder)
        if geometrie_grund:
            self.lidar_xy = None
            self.get_logger().warn('LiDAR unbekannt: ' + geometrie_grund, throttle_duration_sec=2.0)
            return None, None, None
        if sicht is not None:
            obj, gap = sicht.pfad(self.weg_voraus(), self.p('fahrschlauch_breite') / 2,
                                 self.p('fahrschlauch_laenge'))
            # A slow query must not certify expired measurements with a newer
            # callback's reception time. Recheck precisely this snapshot.
            _, zeitgrund = lidar.pflichtkanaele(dict(zip(topics, frisch)), topics, time.monotonic())
            jetzt = self.ros_jetzt()
            zeitgrund = zeitgrund or next((g for a in stamps.values()
                                          if (g := lidar.aufnahme_alter(a, jetzt, max_zukunft=fahrtest.scan_uhrspielraum(self)))), None)
            if zeitgrund:
                self.lidar_xy = None
                self.get_logger().warn('LiDAR unbekannt: ' + zeitgrund, throttle_duration_sec=2.0)
                return None, None, None
            self.lidar_luecke = gap
            if (not self.p('begleiteter_fahrbetrieb') and gap is not None
                    and (obj is None or gap <= obj['abstand'])):
                self.lidar_xy = None
                self.get_logger().warn(f'LiDAR unbekannt: gemeinsamer Fahrbereich ab {gap * 100:.0f} cm '
                                       'nicht gemessen (Roboterbezug)', throttle_duration_sec=2.0)
                return None, None, None
            self.lidar_sicht, self.lidar_xy = sicht, sicht.points
            self.lidar_reichweite = None  # separate measured-origin area query for the crossing
            self.lidar_luecken = np.zeros(0)
            points = sicht.points
            sector = (points[:, 0] > 0) & (np.abs(np.arctan2(points[:, 1], points[:, 0])) <= np.pi / 3)
            broad = float(np.linalg.norm(points[sector], axis=1).min()) if sector.any() else float('inf')
            if obj is None:
                return float('inf'), None, broad
            return obj['abstand'], dict(obj, quelle='lidar'), broad
        topics_frisch = list(zip(topics, frisch))
        frisch = [(xy, b) for _, xy, b, _, _, _ in frisch]
        self.lidar_xy = np.vstack([xy for xy, _ in frisch])   # alle Punkte (fuer den Zebrastreifen)
        self.lidar_luecken = np.concatenate([e[5] for _, e in topics_frisch])
        reichweiten = [reichweiten_stand.get(t) for t, _ in topics_frisch]
        self.lidar_reichweite = (np.minimum.reduce(reichweiten) if all(r is not None for r in reichweiten)
                                 else None)
        weg = self.weg_voraus()
        schlauch = dict(halbe_breite=self.p('fahrschlauch_breite') / 2, laenge=self.p('fahrschlauch_laenge'),
                        nah_halb_deg=self.p('obstacle_half_deg'))
        objekte = [lidar.fahrschlauch(xy, weg, **schlauch) for xy, _ in frisch]
        objekte = [o for o in objekte if o]
        breit = min(b for _, b in frisch)
        # Abdeckung: Strahlen ohne Messung, die durch den Fahrschlauch gehen -> dort ist der Weg unbekannt, nicht
        # frei (gueltige Punkte daneben aendern daran nichts). Ein naeheres echtes Hindernis bleibt Haltgrund.
        luecken = [(lidar.fahrschlauch_luecke(e[5], weg, **schlauch), t) for t, e in topics_frisch]
        luecken = [(d, t) for d, t in luecken if d is not None]
        naechstes = min((o['abstand'] for o in objekte), default=float('inf'))
        if luecken and min(luecken)[0] <= naechstes:
            d, t = min(luecken)
            self.lidar_xy = None
            self.get_logger().warn(f'LiDAR unbekannt: {t} misst den Fahrweg ab {d * 100:.0f} cm nicht '
                                   '(Strahlen ohne Messung)', throttle_duration_sec=2.0)
            return None, None, None
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
                empfang = (self.bild_empfang, self.tiefe_empfang)
            if msg is None or msg is letzte:
                time.sleep(0.02)
                continue
            letzte = msg
            try:
                self._auswerten(msg, tmsg, empfang)
            except Exception as e:
                self.get_logger().error(f'KI-Fehler: {e}', throttle_duration_sec=5.0)
            dauer = time.time() - start
            if dauer > 0.5:
                self.get_logger().warn(f'KI-Bild dauerte {dauer:.2f} s (Modell {self.ki_ms:.0f} ms) - Rechner ueberlastet?',
                                       throttle_duration_sec=10.0)
            rest = 1.0 / self.p('rate') - (time.time() - start)
            if rest > 0:
                time.sleep(rest)

    def _auswerten(self, msg, tmsg, empfang=(None, None)):
        img = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
        h, w = img.shape[:2]
        t0 = time.time()
        objekte = self.yolo.erkenne(img, self.p('min_conf')) if self.yolo else []
        klassen = self.p('ki_klassen')
        if klassen:
            objekte = [o for o in objekte if o['name'] in klassen]

        ampel_farbe, ampel_quelle, schild, schild_quelle = None, None, False, None
        for o in objekte:
            x, y, bw, bh = o['box']
            mitte = (x + bw / 2) / w
            o['im_weg'] = bool(o['name'] in STOPP_NAMEN and o['sicher'] >= self.p('weg_min_conf')
                               and self.p('weg_links') <= mitte <= self.p('weg_rechts')
                               and (y + bh) / h >= self.p('weg_unten_min') and bh / h >= self.p('weg_min_hoehe'))
            if o['name'] == 'Ampel' and bh / h >= self.p('ampel_min_hoehe'):
                o['farbe'] = ampel.farbe_in_box(img, o['box'], cfg=self.ampel_werte)
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

        d = None
        if tmsg is not None:
            d = self.bridge.imgmsg_to_cv2(tmsg, 'passthrough').astype(np.float32)
            if tmsg.encoding != '32FC1':
                d /= 1000.0  # Millimeter -> Meter
        # Abstand von Personen/Tieren/Fahrzeugen nur aus einem Tiefenbild, das zeitlich zu DIESEM Farbbild gehoert
        def stempel(m):
            s = getattr(getattr(m, 'header', None), 'stamp', None)
            return None if s is None else s.sec + s.nanosec * 1e-9
        d_akteur = d if d is not None and tiefe_passt(stempel(msg), stempel(tmsg), *empfang) else None
        for o in objekte:
            if o['name'] in LEBEWESEN | FAHRZEUGE:
                # Abstand ab Kamera (egal, wohin der Arm sie gerade richtet): nur Nahe zaehlen beim Wegraeumen.
                # Ohne passende Tiefe: unsicher -> nah
                akteur_einordnen(o, abstand_im_kasten(d_akteur, o['box'], (h, w)), self.p('akteure_beachten'),
                                 self.p('akteur_nah'))
                o['spielfigur'] = spielfigur(o['box'], o['abstand'], (h, w), self.p('kamera_fov'),
                                             self.p('figur_max_hoehe'))
        tiefe_hindernis, tiefe_obj, blick, pruef_tiefe = None, None, None, None
        modell, tiefe_objekte = None, []
        info = self.tiefeninfo
        pose_ab = self.arm_beobachter.zeit + self.arm_beobachter.dauer + .3 if self.arm_beobachter.winkel else 0
        neue_pose_bilder = all(isinstance(s, (int, float)) and s > pose_ab
                              for s in (stempel(msg), stempel(tmsg)))
        paar_ok = bool(d is not None and tmsg.encoding in ('16UC1', '32FC1')
                       and tmsg.header.frame_id == msg.header.frame_id
                       and tiefe_passt(stempel(msg), stempel(tmsg), *empfang)
                       and neue_pose_bilder)
        if paar_ok and fahrstellung:
            blick = 'fahr'
            lid = self.lidar_d
            frei = (lid is None or lid >= self.entscheider.c['pruef_dist']) and self.entscheider.ablauf is None
            if self.p('begleiteter_fahrbetrieb'):
                modell = self.kalibriertes_bodenmodell
                ref_ok = bool(info and time.monotonic() - info[3] < 1.0
                              and info[1] == d.shape and info[2] == tmsg.header.frame_id
                              and modell.referenz_passt(d.shape, tmsg.header.frame_id,
                                                       self.posen.get('fahrstellung'), info[0]))
                if ref_ok:
                    tiefe_hindernis, tiefe_obj = modell.pruefe(d, lernen=False, linie_voraus=self.weg_voraus())
            else:
                modell = self.boden
                tiefe_hindernis, tiefe_obj = modell.pruefe(d, lernen=frei, linie_voraus=self.weg_voraus())
            if tiefe_obj:
                tiefe_obj['quelle'] = 'tiefe'
        elif (paar_ok and self.boden_pruef is not None
              and self.arm_beobachter.in_pose(self.posen['pruefblick'], time.time())):
            # Arm steht im Pruefblick: mit dessen Kameramodell messen (Boden dort nicht gelernt -> nicht lernen)
            blick = 'pruef'
            modell = self.boden_pruef
            if (info and time.monotonic() - info[3] < 1.0 and info[1] == d.shape
                    and info[2] == tmsg.header.frame_id
                    and modell.referenz_passt(d.shape, tmsg.header.frame_id, self.posen['pruefblick'], info[0])):
                tiefe_hindernis, tiefe_obj = modell.pruefe(d, lernen=False, linie_voraus=self.weg_voraus())
            # Diagnose (Pruefblick sah am 21.10. nie etwas): misst die Tiefenkamera so nah ueberhaupt?
            t = getattr(self.boden_pruef, '_t', None)
            if t is not None:
                gut = np.isfinite(t)
                pruef_tiefe = (float(gut.mean()), float(t[gut].min()) if gut.any() else None)
            if tiefe_obj:
                tiefe_obj.update(quelle='tiefe', blick='pruef', blick_winkel=list(self.posen['pruefblick']))
        if blick and tmsg is not self.tiefe_ausgewertet:   # neues Tiefenbild (sonst wird das alte nur nochmal gerechnet)
            self.tiefe_ausgewertet, self.tiefe_nr = tmsg, self.tiefe_nr + 1
        if modell is not None and tiefe_hindernis is not None:
            tiefe_objekte = [dict(o, quelle='tiefe', blick=blick) for o in modell.objekte]
        tiefe_obj = self.zielbestaetigung.update(tiefe_objekte, stempel(tmsg),
                                                empfang[1] or time.monotonic(), blick)

        self.ki_ms = (time.time() - t0) * 1000
        with self.lock:
            nr = self.wahrnehmung['bild_nr'] + 1
            jetzt = time.time()
            a = stempel(msg)                    # Aufnahmezeit des Farbbilds (gleiche Uhr), nur wenn plausibel
            aufnahme = a if a is not None and a > 0 and 0.0 <= jetzt - a < 5.0 else None
            self.wahrnehmung = {'bild_nr': nr, 'bild_zeit': jetzt, 'aufnahme': aufnahme, 'objekte': objekte,
                                'ampel': ampel_farbe, 'ampel_quelle': ampel_quelle,
                                'stoppschild': schild, 'schild_quelle': schild_quelle,
                                'tiefe_hindernis': tiefe_hindernis, 'tiefe_objekt': tiefe_obj,
                                'tiefe_aufnahme': stempel(tmsg), 'tiefe_empfang': empfang[1],
                                'tiefe_gueltig': bool(paar_ok and modell is not None and tiefe_hindernis is not None
                                                      and tiefe_messung_gueltig(d, modell, self.weg_voraus())),
                                'tiefe_objekte': tiefe_objekte,
                                'blick': blick,   # Tiefe ausgewertet in: 'fahr' | 'pruef' | None (Arm unterwegs)
                                'tiefe_nr': self.tiefe_nr,   # zaehlt nur neue, ausgewertete Tiefenbilder
                                'pruef_tiefe': pruef_tiefe,  # Pruefblick: (Anteil gueltige Tiefe, naechster Wert m)
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
        # Je Richtung, wie weit frei GEMESSEN wurde (Minimum aller Pflicht-LiDARs; ohne Messung 0, hinter einem
        # Treffer verdeckt): Ablaeufe pruefen damit selbst, ob IHRE Zone ganz gemessen ist (Zebrastreifen #156) -
        # fehlende Punkte heissen sonst faelschlich "frei"
        w['lidar_reichweite'] = self.lidar_reichweite if w['lidar'] is not None else None
        w['lidar_fusionssicht'] = self.lidar_sicht if w['lidar'] is not None else None
        w['lidar_hinten'] = self.lidar_hinten()
        w['weg'] = self.weg_voraus()
        w['gier'] = self.gier
        w['strecke'] = self.strecke
        # Strecke wirklich von den Radzaehlern (frisch)? Ohne sie ist sie nur aus /cmd_vel geschaetzt (siehe _cmd)
        w['strecke_gemessen'] = jetzt - self.odom_zeit < ODOM_FRISCH
        w['odom_abschnitt'] = self.odom_abschnitt   # gleich = seitdem ohne Luecke gemessen
        st = self.linie_status
        frisch = 0 <= jetzt - st.get('_zeit', 0.0) < .6
        ids = {k: st.get(k) if frisch else None for k in ('session_id', 'generation', 'start_id')}
        epoche = tuple(ids.values())
        aktiv = bool(frisch and st.get('betrieb_freigegeben') is True and st.get('drive'))
        if epoche != self.betriebsepoche or not aktiv:
            self.aktionsstatus = None
            self.arm_aktionen.clear()
            self.planbindung = None
            self.auftragbindung = None
        self.betriebsepoche = epoche
        self.entscheider.fahrt_aktiv = aktiv
        w['betrieb'] = dict(ids, betrieb_freigegeben=aktiv)
        w['aktionsquittung_pflicht'] = True
        lf_antwort = st.get('aktionsstatus') if frisch else None
        w['aktionsstatus'] = (lf_antwort if self.befehl.get('manoever') else self.aktionsstatus)
        w['lidar_luecken_ignorieren'] = self.p('begleiteter_fahrbetrieb')
        w['linie'] = {'kamera': bool(st.get('linie_kamera')), 'quer': st.get('linie_quer'), 'kurs': st.get('linie_kurs'),
                      'kamera_quer': st.get('kamera_quer'), 'kamera_kurs': st.get('kamera_kurs')}
        # Hindernis fuer Aufheben/Anhalten: Tiefenkamera (sieht auch Flaches), sonst LiDAR
        if lid_obj and lid_obj['abstand'] >= self.entscheider.c['pruef_dist']:
            lid_obj = None
        w['objekt'] = w.get('tiefe_objekt') or lid_obj
        w.update(raeum_pruefung(w, self.p('fahrzeug_grenzen'), time.monotonic(), self.boden.c, jetzt))
        befehl = self.entscheider.update(jetzt, w)
        r = befehl.get('raeumfreigabe') or {}
        ablauf = self.entscheider.ablauf
        # A complete precomputed arm chain uses its initial target binding while
        # the arm camera moves. This is explicitly not a new depth observation.
        if r.get('phase', '').startswith('ausfuehren:'):
            plan = json.dumps(getattr(ablauf, 'plan', None), sort_keys=True)
            key = (r.get('auftrag_id'), r.get('ziel_id'), epoche, plan)
            if (self.planbindung is None and aktiv and r.get('ziel_id') == w['raeumziel_id']
                    and w['raeumziel_freigegeben'] and w['raeum_umgebung_frei'] and w['chassis_frei']):
                if w['strecke_gemessen'] and self.odom_pose is not None and self.odom_bewegung == (0., 0., 0.):
                    self.planbindung = (key, dict(w['objekt']), list(w.get('tiefe_objekte') or []),
                                        self.odom_pose, self.odom_abschnitt)
            binding = self.planbindung
            if (binding and binding[0] == key and w['strecke_gemessen']
                    and self.odom_abschnitt == binding[4] and self.odom_pose == binding[3]
                    and self.odom_bewegung == (0., 0., 0.)):
                gebunden = dict(w, objekt=dict(binding[1], messzeit=time.monotonic()),
                                tiefe_objekte=binding[2], tiefe_gueltig=True)
                # A new calibrated measurement of another object still vetoes.
                if w.get('tiefe_gueltig') and w.get('tiefe_objekte'):
                    gebunden['tiefe_objekte'] = w['tiefe_objekte']
                w.update(raeum_pruefung(gebunden, self.p('fahrzeug_grenzen'), time.monotonic(), self.boden.c))
                w['zielbindung'] = 'vorher bestaetigter Plan; keine neue Tiefenmessung'
                w['raeum_planbindung'] = {'auftrag_id': r['auftrag_id'], 'ziel_id': r['ziel_id']}
            else:
                w['raeumziel_freigegeben'] = False
        elif (getattr(ablauf, 'phase', None) in ('rueckweg', 'kontrolle') and self.auftragbindung
              and self.auftragbindung[0] == getattr(ablauf, 'auftrag_id', None)
              and self.auftragbindung[1] == getattr(ablauf, 'ziel_id', None)
              and self.auftragbindung[2] == epoche and self.auftragbindung[3] == self.odom_abschnitt
              and w['strecke_gemessen'] and w.get('blick') == 'fahr' and w.get('tiefe_gueltig') is True
              and getattr(ablauf, 'nr', -1) >= len(getattr(ablauf, 'schritte', []))):
            chassis, umgebung = fahrraum_frei(w, self.p('fahrzeug_grenzen'), self.boden.c)
            w.update(raeumziel_id=ablauf.ziel_id, raeumziel_freigegeben=True,
                     chassis_frei=chassis, raeum_umgebung_frei=umgebung,
                     zielbindung='Auftragsbindung nach Aufnahme, Ziel nicht neu gesehen')
        elif getattr(ablauf, 'phase', None) != 'ausfuehren':
            self.planbindung = None
            if ablauf is None or getattr(ablauf, 'name', None) != 'wegraeumen':
                self.auftragbindung = None
        if self.p('begleiteter_fahrbetrieb'):
            befehl = fahrtest.befehl_sichern(befehl, w, jetzt, time.monotonic(), self.kamera_lage()[0])
        self.aktionsstatus = befehl.get('aktionsstatus') or self.aktionsstatus
        # One software acknowledgement for each unique authorised arm segment.
        arm = befehl['arm']
        r = befehl.get('raeumfreigabe') or {}
        key = (r.get('auftrag_id'), r.get('phase'), epoche)
        if arm:
            erlaubt = aktiv and self.entscheider.arm_freigabe and (
                not self.p('begleiteter_fahrbetrieb') or r.get('zugelassen') is True)
            if erlaubt and self.arm is not None and (not r or key not in self.arm_aktionen):
                fehler = self._arm_befehl(arm)
                self.aktionsstatus = dict(r, status='verworfen' if fehler else 'ausgefuehrt',
                                         grund=fehler or 'Armsegment gesendet; keine Istpositionsrueckmeldung')
                if not fehler and r:
                    self.arm_aktionen.add(key)
                    if r.get('phase', '').startswith('ausfuehren:') and self.planbindung:
                        self.auftragbindung = (r['auftrag_id'], r['ziel_id'], epoche, self.odom_abschnitt)
            elif not erlaubt or self.arm is None:
                self.aktionsstatus = dict(r, status='verworfen', grund='Arm oder Betrieb nicht freigegeben')
        befehl.update(ids)
        befehl['aktionsstatus'] = self.aktionsstatus
        with self.lock:
            self.befehl = befehl
        for zeit, text, art in self.entscheider.ereignisse:
            self._sende_ereignis(zeit, text, art)
        self.entscheider.ereignisse.clear()
        kamera_ok, kamera_gier = self.kamera_lage()
        info = dict(befehl)
        with self.scan_lock:
            scan_snapshot = dict(self.scans)
        info['lidar_status'] = sensorstatus.lidar_status(scan_snapshot, self.p('scan_topics'), time.monotonic(),
                                                        self.ros_jetzt(), layout='ki',
                                                        max_zukunft=fahrtest.scan_uhrspielraum(self))
        info.update({
            'zeit': jetzt,
            'ki': self.yolo.backend if self.yolo else self.yolo_fehler, 'ki_ms': round(self.ki_ms),
            'takt_max_ms': round(self.takt_max * 1000),
            'bild_alter': round(jetzt - w['bild_zeit'], 2) if w['bild_zeit'] else None,
            # Aufnahmezeit des zuletzt ausgewerteten Farbbilds (None: Stempel fehlt/ungueltig). Der Linienfolger laesst
            # KI-Manoever ohne eigene Bilder nur zu, wenn diese Aufnahme frisch ist.
            'aufnahme': w.get('aufnahme'),
            'begleiteter_fahrbetrieb': self.p('begleiteter_fahrbetrieb'),
            'lidar_abdeckung': 'unbekannt' if w['lidar'] is None or self.lidar_luecke is not None else 'gemessen',
            'lidar_erste_luecke_m': self.lidar_luecke,
            'lidar': None if (w['lidar'] is None or (self.p('begleiteter_fahrbetrieb') and self.lidar_luecke is not None))
                     else (99.0 if w['lidar'] == float('inf') else round(w['lidar'], 3)),
            'ampel': w['ampel'], 'ampel_quelle': w.get('ampel_quelle'),
            'stoppschild': w['stoppschild'], 'schild_quelle': w.get('schild_quelle'),
            'tiefe_hindernis': w['tiefe_hindernis'],
            'objekte': [{'name': o['name'], 'sicher': o['sicher'], 'im_weg': o.get('im_weg', False),
                         'farbe': o.get('farbe'), 'abstand': o.get('abstand'), 'nah': o.get('nah')}
                        for o in w['objekte']],
            'arm_erlaubt': self.entscheider.arm_freigabe,
            'arm_status': self.entscheider.warum_kein_arm() or 'bereit (KI darf wegraeumen)',
            'kinematik': self.kinematik_text(),
            'greifen': self._politik(self.eigenes_modell).lernstand(),
            'zebra': w.get('zebra'), 'einfahrt_verboten': w.get('einfahrt_verboten', False),
            'kamera_ok': kamera_ok, 'kamera_gier': kamera_gier,   # Linienfolger/Kartograf: wohin schaut die Kamera?
            'objekt': w.get('objekt'), 'weg': self.weg_voraus(), 'fahrschlauch': self.p('fahrschlauch_breite'),
            'tiefe_objekte': w.get('tiefe_objekte'), 'zielbindung': w.get('zielbindung'),
            'raeum_planbindung': w.get('raeum_planbindung'),
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
        g = armlib.greifer_plan(obj['breite'])
        anlegen, zu = g['anlegen'], g['zu']
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
            plan['info'] = plan.get('info', '') + f" (Yahboom-Kinematik, {g['text']})"
            return plan
        plan = greifen.plane(obj, seite, self.eigene_kin.inverse, fahr, auf, zu, self._politik(self.eigenes_modell),
                             anlegen=anlegen)
        plan['info'] = plan.get('info', '') + f" (eigene Kinematik, {self.kin_quelle}, {g['text']})"
        return plan

    def _arm_befehl(self, arm):
        """arm: Posenname, {'pose': Name, 'greifer': 'auf' | 'zu' | None} oder {'winkel': [6], 'zeit_ms'}."""
        if isinstance(arm, str):
            arm = {'pose': arm}
        if arm.get('winkel'):
            fehler = self.arm.fahre(list(arm['winkel']), int(arm.get('zeit_ms', 1200)))
            if fehler:
                self.get_logger().error(f'Arm: {fehler}')
            return fehler
        winkel = self.posen.get(arm['pose'])
        if not winkel:
            fehler = f"Pose '{arm['pose']}' fehlt (im Panel einlernen)"
            self.get_logger().error(f'Arm: {fehler}')
            return fehler
        winkel = list(winkel)
        auf, zu = armlib.greifer_werte()
        if arm.get('greifer') == 'auf':
            winkel[5] = auf
        elif arm.get('greifer') == 'zu':
            winkel[5] = zu
        fehler = self.arm.fahre(winkel, 1200)
        if fehler:
            self.get_logger().error(f'Arm: {fehler}')
        return fehler

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
