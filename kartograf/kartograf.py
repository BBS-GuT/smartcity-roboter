#!/usr/bin/env python3
# Kartograf: baut waehrend jeder Fahrt eine 2D- und 3D-Karte und verbessert sie mit jeder Fahrt.
# FAEHRT NICHT und bewegt den Arm nicht selbst (er kann die KI hoechstens bitten, sich umzuschauen).
#
# Start: das Panel startet ihn automatisch mit der KI (scripts/panel.sh)
#
# Sensoren -> Karte (Erklaerung der Schichten in lib/karte.py, Rechnung in lib/kartierer.py):
#   LiDAR (/scan0, /scan1)        -> Belegung (Waende, Haeuser, Hindernisse) + Scan-Abgleich (Position)
#   Odometrie (/odom_raw) + IMU   -> Mitrechnen der Position zwischen zwei Scans
#   Kamera                        -> Bodenfoto (Linien, Zebrastreifen) von oben
#   Tiefenkamera                  -> 3D-Punkte von allem, was aus dem Boden ragt
#   KI (/ki/befehl)               -> Marker: Ampel, Stoppschild, Zebrastreifen, Einbahnstrasse, Hindernis
#                                    + wohin die Kamera gerade schaut (Arm)
# Hier steht nur das ROS-Drumherum: jede Nachricht wird zu einem dict und geht an den Kartierer. So kann man eine
# aufgezeichnete Messfahrt am Laptop genau gleich durchrechnen (kartograf/abspielen.py).
#
# Dateien (Ordner karten/<name>/, nicht im Repository):
#   karte.npz   alles zum Weiterbauen bei der naechsten Fahrt
#   karte.png   2D-Karte (1 Pixel = 1 cm)     karte.json  Infos fuer das Panel (Bereich, Marker, Pfad)
#   wolke.bin   3D-Punkte fuer das Panel       karte.ply   3D-Karte zum Oeffnen mit MeshLab/CloudCompare
#   karten/aufnahmen/<name>_<datum>.jsonl.gz   Messfahrten (Panel -> Karte -> "Messfahrt aufzeichnen")
#
# Sendet:  /karte/pose  std_msgs/String JSON {x, y, w, status, guete, fahrten, warnungen, aufnahme ...} (5x pro s)
#          /ki/kommando 'umschauen' (nur wenn umschauen_auto:=true)
# Empfaengt: /karte/kommando  'neu' oder 'neu:<auftrag>' (alte Karte sichern, neu anfangen) | 'speichern' |
#                             'aufnahme_start' | 'aufnahme_stopp'
#            Ergebnis eines Neuanfangs steht in /karte/pose unter 'karte_neu': {auftrag, ok, text, sicherung}
import json
import math
import os
import shutil
import signal
import sys
import threading
import time

import cv2
import numpy as np
import rclpy
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data, QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image, LaserScan, Imu
from nav_msgs.msg import Odometry
from std_msgs.msg import String
from cv_bridge import CvBridge

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(REPO, 'lib'))
sys.path.insert(0, os.path.join(REPO, 'line_follower'))
import aufnahme as A    # noqa: E402
import karte as K       # noqa: E402
import kartierer as KR  # noqa: E402
import linie            # noqa: E402

KAMERA_NAMEN = ('kamera_hoehe', 'kamera_neigung', 'kamera_fov', 'kamera_x')
# diese Einstellungen gehen an den Kartierer (und in den Kopf jeder Aufnahme)
KARTIERER_NAMEN = ('scan_topics', 'scan_front_deg', 'scan_spiegeln', 'obstacle_min_range', 'lidar_x',
                   'karte_min_abstand', 'scan_dauer', 'selbst_kalibrieren')


def schreibe_atomar(datei, daten):
    """Erst in eine Hilfsdatei schreiben, dann umbenennen: das Panel liest nie eine halbe Datei."""
    tmp = datei + '.neu'
    with open(tmp, 'wb') as f:
        f.write(daten)
    os.replace(tmp, datei)


def stempel(msg):
    return KR.zeit_aus_stamp(msg.header.stamp)


class Kartograf(Node):
    def __init__(self):
        super().__init__('kartograf')
        dp = self.declare_parameter
        dp('karte', 'smartcity')                 # Name der Karte (Ordner karten/<name>)
        dp('ordner', os.path.join(REPO, 'karten'))
        dp('scan_topics', ['/scan0', '/scan1'])
        dp('scan_front_deg', [0.0, 0.0])
        dp('scan_spiegeln', [False, False])      # LiDAR zaehlt die Winkel andersherum (erkennt er auch selbst)
        dp('obstacle_min_range', 0.08)
        dp('lidar_x', 0.0)                       # LiDAR so weit vor der Robotermitte (m) - nachmessen
        dp('karte_min_abstand', 0.15)            # naeher (m) nicht in die Karte (eigene Teile, Beruehrung)
        dp('scan_dauer', 0.0)                    # Dauer einer LiDAR-Umdrehung (s), falls nicht im Scan. 0 = aus
        dp('selbst_kalibrieren', True)           # gelernte Korrekturen (Lagesensor, LiDAR-Einbau) anwenden
        dp('max_reichweite', 8.0)                # LiDAR-Punkte weiter weg nicht verwenden (m)
        dp('odom_topic', '/odom_raw')
        dp('imu_topic', '/imu/data_raw')
        dp('image_topic', '/camera/color/image_raw')
        dp('depth_topic', '/camera/depth/image_raw')
        dp('kamera_hz', 2.0)                     # so oft Kamera/Tiefe in die Karte eintragen
        dp('aufnahme_bild_hz', 2.0)              # so oft ein Kamerabild in die Messfahrt-Aufnahme
        dp('arm_basis_x', 0.05)                  # Drehachse von Servo 1 vor der Robotermitte (m) - geschaetzt
        dp('umschauen_auto', False)              # KI bitten, sich umzuschauen, wo die Karte Luecken hat
        dp('umschauen_abstand', 1.5)             # hoechstens alle so viele Meter
        for n in KAMERA_NAMEN:
            dp(n, linie.STANDARD[n])
        self.ordner = os.path.join(self.p('ordner'), self.p('karte'))
        self.k_cfg = {n: self.p(n) for n in KAMERA_NAMEN}
        self.k_cfg['arm_basis_x'] = self.p('arm_basis_x')

        self.lock = threading.Lock()
        # Dateien im Kartenordner schreiben/verschieben: immer ZUERST datei_lock, dann lock (nie andersherum)
        self.datei_lock = threading.Lock()
        self.karte_neu = None               # Ergebnis des letzten Neuanfangs (fuers Panel, s. o.)
        self.bridge = CvBridge()
        self.karte = K.Karte(self.ordner, cfg={'max_reichweite': self.p('max_reichweite')})
        geladen = self.karte.laden()
        self.kr = KR.Kartierer(self.karte, self.kartierer_cfg())
        self.bild = self.tiefe = None
        self.ki = (0.0, {})
        self.gefahren, self.umschauen_bei = 0.0, 0.0
        self.suche_laeuft = False
        self.fehlversuche = 0
        self.scan_karte = None
        self.geaendert = True
        self.angefangen = time.time()       # wann diese Karte (im Speicher) angefangen wurde - Panel prueft "Neue Karte"
        self.aufnahme = None
        self.arm = None
        try:
            import arm as armlib       # hoert mit, wohin der Arm geschickt wird (nur fuer die Aufnahme)
            self.arm = armlib.ArmBeobachter(self)
        except Exception as e:
            self.get_logger().warn(f'Arm wird nicht mit aufgezeichnet: {e}')
        self.arm_zeit = 0.0

        sensor = MutuallyExclusiveCallbackGroup()
        kamera = MutuallyExclusiveCallbackGroup()
        arbeit = MutuallyExclusiveCallbackGroup()
        nur_neuestes = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT,
                                  history=HistoryPolicy.KEEP_LAST)
        for t in self.p('scan_topics'):
            self.create_subscription(LaserScan, t, lambda m, t=t: self._scan(m, t), qos_profile_sensor_data,
                                     callback_group=sensor)
        self.create_subscription(Odometry, self.p('odom_topic'), self._odom, qos_profile_sensor_data,
                                 callback_group=sensor)
        self.create_subscription(Imu, self.p('imu_topic'), self._imu, qos_profile_sensor_data, callback_group=sensor)
        self.create_subscription(Image, self.p('image_topic'), self._bild, nur_neuestes, callback_group=kamera)
        self.create_subscription(Image, self.p('depth_topic'), lambda m: setattr(self, 'tiefe', m), nur_neuestes,
                                 callback_group=kamera)
        self.create_subscription(String, '/ki/befehl', self._ki, 10, callback_group=sensor)
        self.create_subscription(String, '/karte/kommando', self._kommando, 10, callback_group=sensor)
        self.pub_pose = self.create_publisher(String, '/karte/pose', 10)
        self.pub_ki = self.create_publisher(String, '/ki/kommando', 10)
        self.create_timer(0.2, self._scans_verarbeiten, callback_group=arbeit)
        self.create_timer(0.2, self._pose_senden, callback_group=sensor)
        self.create_timer(1.0 / self.p('kamera_hz'), self._kamera_verarbeiten, callback_group=kamera)
        self.create_timer(3.0, self._dateien_schreiben, callback_group=arbeit)
        self.create_timer(30.0, self._speichern, callback_group=arbeit)
        self.get_logger().info(f"Kartograf: Karte '{self.p('karte')}' "
                               + (f'geladen ({self.karte.fahrten} Fahrten)' if geladen else 'neu'))

    def p(self, name):
        return self.get_parameter(name).value

    def kartierer_cfg(self):
        return {n: self.p(n) for n in KARTIERER_NAMEN}

    # ---------------- Sensoren -> Kartierer (+ Aufnahme) ----------------
    def _imu(self, msg):
        jetzt = time.time()
        g, a = msg.angular_velocity, msg.linear_acceleration
        d = {'stamp': stempel(msg), 'g': [g.x, g.y, g.z], 'a': [a.x, a.y, a.z]}
        with self.lock:
            self.kr.imu(jetzt, d)
        self._aufnehmen({'typ': 'imu', 't': jetzt, **d})

    def _odom(self, msg):
        jetzt = time.time()
        t, p, q = msg.twist.twist, msg.pose.pose.position, msg.pose.pose.orientation
        w = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        d = {'stamp': stempel(msg), 'vx': t.linear.x, 'vy': t.linear.y, 'wz': t.angular.z, 'x': p.x, 'y': p.y, 'w': w}
        with self.lock:
            alt = self.kr.roboter
            self.kr.odom(jetzt, d)
            self.gefahren += math.hypot(self.kr.roboter[0] - alt[0], self.kr.roboter[1] - alt[1])
        self._aufnehmen({'typ': 'odom', 't': jetzt, **d})

    def _scan(self, msg, topic):
        jetzt = time.time()
        d = {'stamp': stempel(msg), 'amin': msg.angle_min, 'ainc': msg.angle_increment, 'rmin': msg.range_min,
             'rmax': msg.range_max, 'ti': msg.time_increment, 'st': msg.scan_time,
             'r': np.asarray(msg.ranges, dtype=np.float32)}
        with self.lock:
            self.kr.scan(jetzt, topic, d)
        if self.aufnahme:
            self.aufnahme.scan(jetzt, topic, d)

    def _bild(self, msg):
        self.bild = (time.time(), msg)
        a = self.aufnahme
        if a and a.bild_hz > 0 and time.time() - a.letztes_bild >= 1.0 / a.bild_hz:
            try:
                a.bild(time.time(), stempel(msg), self.bridge.imgmsg_to_cv2(msg, 'bgr8'))
            except Exception:
                pass

    def _aufnehmen(self, eintrag):
        if self.aufnahme:
            self.aufnahme.schreiben(eintrag)

    # ---------------- LiDAR ----------------
    def _scans_verarbeiten(self):
        jetzt = time.time()
        with self.lock:
            vorher = self.kr.lok.pose
            suchen = self.kr.verarbeiten(jetzt) and not self.suche_laeuft
            pose = self.kr.lok.pose
            punkte = self.kr.lok.letzte_punkte
            if pose is not None and punkte is not None and len(punkte):
                # Scan in Kartenkoordinaten fuer die Anzeige (passt so immer zur Karte)
                auswahl = punkte[np.linspace(0, len(punkte) - 1, min(len(punkte), 180)).astype(int)]
                self.scan_karte = np.round(K.in_karte(pose, auswahl), 3).tolist()
            if vorher is None and pose is not None:
                self.get_logger().info(f'Karte: {self.kr.lok.status}')
            meldung, self.kr.meldung = self.kr.meldung, None
        if meldung:
            self.get_logger().info(f'Karte: {meldung}')
        self.geaendert = True
        if suchen:
            self.suche_laeuft = True
            threading.Thread(target=self._global_suchen, daemon=True).start()
        self._umschauen_pruefen()

    def _global_suchen(self):
        """Neue Fahrt mit vorhandener Karte: wo bin ich? (dauert einige Sekunden, eigener Thread)"""
        try:
            with self.lock:
                lok = self.kr.lok
                if lok.pose is not None or not lok.puffer:
                    return
                odom_scan, punkte = lok.puffer[-1]
                alle = [punkte] + [K.in_karte(K.relativ(odom_scan, o), p) for o, p in lok.puffer[-8:-1]]
            pose, guete, eindeutig = self.karte.belegung.global_suchen(np.concatenate(alle))
            with self.lock:
                if lok is not self.kr.lok:
                    return          # inzwischen neue Karte angefangen
                lok.guete = guete
                if pose is None or not eindeutig:
                    self.fehlversuche += 1
                    lok.status = (f'suche Position in der Karte ... (beste Uebereinstimmung {guete:.0%}, '
                                  f'{self.fehlversuche}. Versuch)')
                    if self.fehlversuche >= 3:
                        lok.status += ' - andere Umgebung? Panel -> Karte -> Neue Karte'
                    return
                self.fehlversuche = 0
                lok.pose = K.verknuepfen(pose, K.relativ(odom_scan, lok.odom))
                lok.status = f'Position in der Karte gefunden ({guete:.0%})'
                self.karte.fahrten += 1
                for o, p in lok.puffer:
                    self.karte.belegung.eintragen(K.verknuepfen(pose, K.relativ(odom_scan, o)), p)
                lok.puffer = []
            self.get_logger().info(lok.status)
        finally:
            # nicht dauernd suchen (kostet viel Rechenzeit, die Linienfolger und KI brauchen):
            # erst alle 5 s, nach mehreren Fehlversuchen nur noch alle 30 s
            time.sleep(5.0 if self.fehlversuche < 3 else 30.0)
            self.suche_laeuft = False

    # ---------------- Kamera + Tiefe ----------------
    def _kamera_verarbeiten(self):
        bild, tiefe_msg = self.bild, self.tiefe
        jetzt = time.time()
        if bild is None:
            return
        empfang, bild_msg = bild
        ki_zeit, ki = self.ki
        if ki_zeit and jetzt - ki_zeit < 1.0:
            if ki.get('kamera_ok'):
                gier = 0.0
            else:
                gier = ki.get('kamera_gier')     # Arm schaut zur Seite (bekannt) oder None (unbekannt)
        else:
            gier = 0.0                           # ohne KI: Arm steht in Fahrstellung (wie nach dem Start)
        with self.lock:
            # Position ZUR AUFNAHMEZEIT des Bildes (Bilder kommen oft spaet an), nur wenn der Abgleich sicher ist
            pose, _ = self.kr.bild_pose(empfang, stempel(bild_msg))
        if pose is None or gier is None:
            return
        bild = self.bridge.imgmsg_to_cv2(bild_msg, 'bgr8')
        tiefe = None
        if tiefe_msg is not None:
            tiefe = self.bridge.imgmsg_to_cv2(tiefe_msg, 'passthrough').astype(np.float32)
            if tiefe_msg.encoding != '32FC1':
                tiefe /= 1000.0
        xy, farben = K.boden_aus_bild(bild, self.k_cfg, gier, tiefe_m=tiefe)
        xyz = None
        if tiefe is not None:
            xyz, farben3 = K.raum_aus_tiefe(tiefe, bild, self.k_cfg, gier)
        with self.lock:
            self.karte.boden.eintragen(pose, xy, farben)
            if xyz is not None:
                self.karte.wolke.eintragen(pose, xyz, farben3)
        self.geaendert = True
        self.bild = None          # jedes Bild nur einmal

    # ---------------- KI ----------------
    def _ki(self, msg):
        try:
            ki = json.loads(msg.data)
        except ValueError:
            return
        jetzt = time.time()
        self.ki = (jetzt, ki)
        self._aufnehmen({'typ': 'ki', 't': jetzt, 'daten': {'kamera_ok': ki.get('kamera_ok'),
                                                             'kamera_gier': ki.get('kamera_gier')}})
        with self.lock:
            pose = self.kr.roboter_pose_bei()
            fahrt = self.karte.fahrten
        if pose is None or not ki.get('kamera_ok'):
            return
        m = self.karte.marker
        if ki.get('zebra'):
            x, y = K.in_karte(pose, [[ki['zebra']['abstand'] + 0.04, 0.0]])[0]
            m.melden('zebra', x, y, fahrt=fahrt)
        # Schilder/Ampel: Entfernung ist nur grob bekannt (stehen vorne rechts, wenn sie gross genug sind)
        for art, an in (('einfahrt_verboten', ki.get('einfahrt_verboten')), ('stoppschild', ki.get('stoppschild')),
                        ('ampel', ki.get('ampel'))):
            if an:
                x, y = K.in_karte(pose, [[0.45, -0.12]])[0]
                m.melden(art, x, y, fahrt=fahrt)
        o = ki.get('objekt')
        if o and o.get('quelle') == 'tiefe' and o.get('vor') is not None:   # Dinge AUF der Strasse (Tiefenkamera)
            x, y = K.in_karte(pose, [[o['vor'] + o.get('breite', 0.04) / 2, o.get('seite', 0.0)]])[0]
            m.melden('hindernis', x, y, fahrt=fahrt)

    def _umschauen_pruefen(self):
        """KI bitten, sich umzuschauen, wenn um den Roboter herum noch wenig Bodenfoto da ist."""
        if not self.p('umschauen_auto') or self.gefahren - self.umschauen_bei < self.p('umschauen_abstand'):
            return
        with self.lock:
            pose = self.kr.roboter_pose_bei()
            if pose is None:
                return
            b = self.karte.boden
            i = int((pose[0] - b.ursprung) / b.aufl)
            j = int((pose[1] - b.ursprung) / b.aufl)
            r = int(0.5 / b.aufl)
            if not (r <= i < b.n - r and r <= j < b.n - r):
                return
            gesehen = float((b.anzahl[j - r:j + r, i - r:i + r] > 0).mean())
        if gesehen < 0.5:
            self.umschauen_bei = self.gefahren
            self.pub_ki.publish(String(data='umschauen'))
            self.get_logger().info(f'Karte: hier erst {gesehen:.0%} gesehen -> bitte KI, sich umzuschauen')

    # ---------------- Ausgabe ----------------
    def _pose_senden(self):
        jetzt = time.time()
        with self.lock:
            aus = self.kr.meldung_pose(jetzt)
        aus['karte'] = self.p('karte')
        aus['angefangen'] = self.angefangen
        aus['karte_neu'] = self.karte_neu
        if 'x' in aus:
            aus['scan'] = self.scan_karte
        a = self.aufnahme
        if a is not None:
            aus['aufnahme'] = a.info()
            if not a.laeuft:            # von selbst aufgehoert (zu gross / zu lang)
                self._aufnahme_stopp()
            else:
                self._aufnehmen({'typ': 'pose', 't': jetzt, 'daten': {k: v for k, v in aus.items() if k != 'scan'}})
                if self.arm is not None and self.arm.zeit > self.arm_zeit:
                    self.arm_zeit = self.arm.zeit
                    self._aufnehmen({'typ': 'arm', 't': self.arm.zeit, 'winkel': self.arm.winkel,
                                     'dauer': self.arm.dauer})
        elif getattr(self, 'letzte_aufnahme', None):
            aus['aufnahme'] = self.letzte_aufnahme
        self.pub_pose.publish(String(data=json.dumps(aus)))

    def _dateien_schreiben(self):
        if not self.geaendert:
            return
        self.geaendert = False
        with self.datei_lock:    # nicht gleichzeitig mit "Neue Karte" (Ordner wird verschoben)
            with self.lock:
                bild, bereich = self.karte.bild()
                p, f = self.karte.wolke_export()
                info = {'zeit': time.time(), 'karte': self.p('karte'), 'fahrten': self.karte.fahrten,
                        'bereich': bereich, 'aufloesung': self.karte.boden.aufl, 'status': self.kr.lok.status,
                        'pose': self.kr.roboter_pose_bei(), 'pfad': self.kr.lok.pfad[-3000:],
                        'marker': self.karte.marker.sichere(), 'punkte_3d': int(len(p))}
            os.makedirs(self.ordner, exist_ok=True)
            if bild is not None:
                schreibe_atomar(os.path.join(self.ordner, 'karte.png'), cv2.imencode('.png', bild)[1].tobytes())
            kopf = np.array([len(p)], np.uint32).tobytes()
            schreibe_atomar(os.path.join(self.ordner, 'wolke.bin'), kopf + p.astype('<f4').tobytes() + f.tobytes())
            schreibe_atomar(os.path.join(self.ordner, 'karte.json'), json.dumps(info).encode())

    def _speichern(self):
        with self.datei_lock:
            with self.lock:
                ply = self._speichern_ohne_lock()
            schreibe_atomar(os.path.join(self.ordner, 'karte.ply'), ply)

    def _speichern_ohne_lock(self):
        """Aktuellen Stand (Karte, Pose, Kalibrierung) in den Kartenordner. Aufrufer haelt lock. Rueckgabe: PLY."""
        self.karte.letzte_pose = self.kr.lok.pose
        self.karte.kalibrierung = self.kr.kal.speichern()
        self.karte.speichern()
        return self.karte.ply()

    def _sicherungs_ordner(self):
        """Eindeutiger Name fuer die Sicherung der alten Karte (auch bei zwei Anfragen in derselben Sekunde)."""
        basis = self.ordner + time.strftime('_alt_%Y%m%d_%H%M%S')
        ziel, n = basis, 2
        while os.path.exists(ziel):
            ziel, n = f'{basis}_{n}', n + 1
        return ziel

    def neue_karte(self, auftrag=None):
        """Alte Karte mit ihrem AKTUELLEN Stand sichern (umbenennen, nichts loeschen) und neu anfangen.
        Erst alles vorbereiten, dann umschalten: geht etwas schief, bleibt die alte Karte aktiv und vollstaendig.
        Ergebnis in self.karte_neu (fuers Panel, mit Auftragskennung)."""
        sicherung = None
        try:
            with self.datei_lock:
                with self.lock:
                    kal = self.kr.kal.speichern()      # Gelerntes ueber die Sensoren gilt weiter
                    karte = K.Karte(self.ordner, cfg={'max_reichweite': self.p('max_reichweite')})
                    karte.kalibrierung = kal
                    kr = KR.Kartierer(karte, self.kartierer_cfg())
                    ply = self._speichern_ohne_lock()    # neuester Stand, nicht nur der letzte Autosave
                    schreibe_atomar(os.path.join(self.ordner, 'karte.ply'), ply)
                    sicherung = self._sicherungs_ordner()
                    shutil.move(self.ordner, sicherung)
                    self.karte, self.kr = karte, kr
                    self.angefangen = time.time()
        except Exception as e:     # z. B. keine Schreibrechte: melden, Kartograf laeuft mit der alten Karte weiter
            self.get_logger().error(f'Neue Karte geht nicht: {e!r}')
            self.karte_neu = {'auftrag': auftrag, 'ok': False, 'text': f'Neue Karte geht nicht: {e}',
                              'sicherung': sicherung if sicherung and os.path.isdir(sicherung) else None}
            return self.karte_neu
        self.geaendert = True
        self.get_logger().info(f'Neue Karte angefangen, alte gesichert in {sicherung}')
        self.karte_neu = {'auftrag': auftrag, 'ok': True, 'text': 'Neue Karte angefangen',
                          'sicherung': os.path.basename(sicherung)}
        return self.karte_neu

    # ---------------- Messfahrt aufzeichnen ----------------
    def _aufnahme_start(self):
        if self.aufnahme is not None:
            return 'Aufnahme laeuft schon'
        ordner = os.path.join(self.p('ordner'), 'aufnahmen')
        datei = os.path.join(ordner, f"{self.p('karte')}_{time.strftime('%Y%m%d_%H%M%S')}.jsonl.gz")
        cfg = self.kartierer_cfg()
        cfg.update(self.k_cfg)
        cfg['max_reichweite'] = self.p('max_reichweite')
        name = os.path.expanduser('~/roboter_name')
        kopf = {'quelle': 'roboter', 'karte': self.p('karte'), 'cfg': cfg,
                'roboter': open(name).read().strip() if os.path.exists(name) else '',
                'topics': {'odom': self.p('odom_topic'), 'imu': self.p('imu_topic'), 'bild': self.p('image_topic')},
                'kalibrierung': self.kr.kal.speichern()}
        try:
            self.aufnahme = A.Aufnahme(datei, kopf, bild_hz=self.p('aufnahme_bild_hz'))
        except OSError as e:     # Platte voll, keine Schreibrechte: Kartograf laeuft weiter
            self.aufnahme = None
            return f'Aufnahme geht nicht: {e}'
        self.get_logger().info(f'Messfahrt-Aufnahme: {datei}')
        return f'Aufnahme laeuft: {datei}'

    def _aufnahme_stopp(self):
        a, self.aufnahme = self.aufnahme, None
        if a is None:
            return 'keine Aufnahme'
        a.stopp()
        self.letzte_aufnahme = a.info()
        self.get_logger().info(f'Messfahrt-Aufnahme beendet: {a.datei} ({a.info()["mb"]} MB)')
        return f'Aufnahme gespeichert: {a.datei}'

    def _kommando(self, msg):
        befehl = msg.data.strip()
        if befehl == 'speichern':
            self._speichern()
            self.get_logger().info('Karte gespeichert')
        elif befehl == 'aufnahme_start':
            self._aufnahme_start()
        elif befehl == 'aufnahme_stopp':
            self._aufnahme_stopp()
        elif befehl == 'neu' or befehl.startswith('neu:'):
            self.neue_karte(befehl[4:] or None)

def signale_abfangen():
    def ende(*_):
        raise KeyboardInterrupt
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, ende)


def main():
    signale_abfangen()
    try:
        os.nice(10)   # niedrigere Prioritaet: Linienfolger und KI gehen vor (die Karte darf warten)
    except OSError:
        pass
    rclpy.init()
    node = Kartograf()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node._aufnahme_stopp()
            node._dateien_schreiben()
            node._speichern()
            print('Karte gespeichert.')
        except Exception as e:
            print(f'Karte speichern hat nicht geklappt: {e}')
        executor.shutdown()
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    main()
