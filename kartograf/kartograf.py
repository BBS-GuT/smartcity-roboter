#!/usr/bin/env python3
# Kartograf: baut waehrend jeder Fahrt eine 2D- und 3D-Karte und verbessert sie mit jeder Fahrt.
# FAEHRT NICHT und bewegt den Arm nicht selbst (er kann die KI hoechstens bitten, sich umzuschauen).
#
# Start: das Panel startet ihn automatisch mit der KI (scripts/panel.sh)
#
# Sensoren -> Karte (Erklaerung der Schichten in lib/karte.py):
#   LiDAR (/scan0, /scan1)        -> Belegung (Waende, Haeuser, Hindernisse) + Scan-Abgleich (Position)
#   Odometrie (/odom_raw) + IMU   -> Mitrechnen der Position zwischen zwei Scans
#   Kamera                        -> Bodenfoto (Linien, Zebrastreifen) von oben
#   Tiefenkamera                  -> 3D-Punkte von allem, was aus dem Boden ragt
#   KI (/ki/befehl)               -> Marker: Ampel, Stoppschild, Zebrastreifen, Einbahnstrasse, Hindernis
#                                    + wohin die Kamera gerade schaut (Arm)
#
# Dateien (Ordner karten/<name>/, nicht im Repository):
#   karte.npz   alles zum Weiterbauen bei der naechsten Fahrt
#   karte.png   2D-Karte (1 Pixel = 1 cm)     karte.json  Infos fuer das Panel (Bereich, Marker, Pfad)
#   wolke.bin   3D-Punkte fuer das Panel       karte.ply   3D-Karte zum Oeffnen mit MeshLab/CloudCompare
#
# Sendet:  /karte/pose  std_msgs/String JSON {x, y, w, status, guete, fahrten}  (5x pro Sekunde)
#          /ki/kommando 'umschauen' (nur wenn umschauen_auto:=true)
# Empfaengt: /karte/kommando  'neu' (alte Karte sichern, neu anfangen) | 'speichern'
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
import karte as K   # noqa: E402
import lidar        # noqa: E402
import linie        # noqa: E402

KAMERA_NAMEN = ('kamera_hoehe', 'kamera_neigung', 'kamera_fov', 'kamera_x')


def schreibe_atomar(datei, daten):
    """Erst in eine Hilfsdatei schreiben, dann umbenennen: das Panel liest nie eine halbe Datei."""
    tmp = datei + '.neu'
    with open(tmp, 'wb') as f:
        f.write(daten)
    os.replace(tmp, datei)


class Kartograf(Node):
    def __init__(self):
        super().__init__('kartograf')
        dp = self.declare_parameter
        dp('karte', 'smartcity')                 # Name der Karte (Ordner karten/<name>)
        dp('ordner', os.path.join(REPO, 'karten'))
        dp('scan_topics', ['/scan0', '/scan1'])
        dp('scan_front_deg', [0.0, 0.0])
        dp('obstacle_min_range', 0.08)
        dp('lidar_x', 0.0)                       # LiDAR so weit vor der Robotermitte (m) - nachmessen
        dp('karte_min_abstand', 0.15)            # naeher (m) nicht in die Karte (eigene Teile, Beruehrung)
        dp('odom_topic', '/odom_raw')
        dp('imu_topic', '/imu/data_raw')
        dp('image_topic', '/camera/color/image_raw')
        dp('depth_topic', '/camera/depth/image_raw')
        dp('kamera_hz', 2.0)                     # so oft Kamera/Tiefe in die Karte eintragen
        dp('arm_basis_x', 0.05)                  # Drehachse von Servo 1 vor der Robotermitte (m) - geschaetzt
        dp('umschauen_auto', False)              # KI bitten, sich umzuschauen, wo die Karte Luecken hat
        dp('umschauen_abstand', 1.5)             # hoechstens alle so viele Meter
        for n in KAMERA_NAMEN:
            dp(n, linie.STANDARD[n])
        self.ordner = os.path.join(self.p('ordner'), self.p('karte'))
        self.k_cfg = {n: self.p(n) for n in KAMERA_NAMEN}
        self.k_cfg['arm_basis_x'] = self.p('arm_basis_x')

        self.lock = threading.Lock()
        self.bridge = CvBridge()
        self.karte = K.Karte(self.ordner)
        geladen = self.karte.laden()
        self.lok = K.Lokalisierung(self.karte)
        self.scans = {}                 # topic -> (zeit, punkte)
        self.odom_zeit = None
        self.imu = (0.0, 0.0)           # (zeit, drehrate)
        self.gyro_bias, self.stand_drehraten = 0.0, []
        self.dreh = 0.0                 # aktuelle Drehrate (fuer "dreht sich schnell")
        self.v = 0.0
        self.bild = self.tiefe = None
        self.ki = (0.0, {})
        self.gefahren, self.umschauen_bei = 0.0, 0.0
        self.suche_laeuft = False
        self.fehlversuche = 0
        self.scan_karte = None
        self.geaendert = True
        self.laeuft = True

        sensor = MutuallyExclusiveCallbackGroup()
        kamera = MutuallyExclusiveCallbackGroup()
        arbeit = MutuallyExclusiveCallbackGroup()
        nur_neuestes = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT,
                                  history=HistoryPolicy.KEEP_LAST)
        for i, t in enumerate(self.p('scan_topics')):
            self.create_subscription(LaserScan, t, lambda m, t=t, i=i: self._scan(m, t, i),
                                     qos_profile_sensor_data, callback_group=sensor)
        self.create_subscription(Odometry, self.p('odom_topic'), self._odom, qos_profile_sensor_data,
                                 callback_group=sensor)
        self.create_subscription(Imu, self.p('imu_topic'), self._imu, qos_profile_sensor_data, callback_group=sensor)
        self.create_subscription(Image, self.p('image_topic'), lambda m: setattr(self, 'bild', m), nur_neuestes,
                                 callback_group=kamera)
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

    # ---------------- Bewegung ----------------
    def _imu(self, msg):
        jetzt = time.time()
        letzte = self.imu[0]
        self.imu = (jetzt, msg.angular_velocity.z)
        if self.odom_zeit is None or jetzt - self.odom_zeit > 0.5:
            # keine Odometrie: wenigstens die Drehung vom Lagesensor mitrechnen (Strecke macht der Scan-Abgleich)
            if letzte and jetzt - letzte < 0.2:
                with self.lock:
                    self.lok.bewegen(0.0, 0.0, (msg.angular_velocity.z - self.gyro_bias) * (jetzt - letzte), jetzt)

    def _odom(self, msg):
        jetzt = time.time()
        if self.odom_zeit is None:
            self.odom_zeit = jetzt
            return
        dt = min(0.2, jetzt - self.odom_zeit)
        self.odom_zeit = jetzt
        t = msg.twist.twist
        vx, vy, wz = t.linear.x, t.linear.y, t.angular.z
        imu_zeit, imu_w = self.imu
        if jetzt - imu_zeit < 0.3:
            # Drehung lieber vom Lagesensor (Mecanum-Raeder rutschen beim Drehen).
            # Im Stand misst er trotzdem etwas (Nullpunktfehler) -> lernen und abziehen.
            if abs(vx) < 0.002 and abs(vy) < 0.002 and abs(wz) < 0.005:
                self.stand_drehraten = (self.stand_drehraten + [imu_w])[-200:]
                if len(self.stand_drehraten) >= 50:
                    self.gyro_bias = float(np.median(self.stand_drehraten))
                wz = 0.0
            else:
                wz = imu_w - self.gyro_bias
        self.dreh, self.v = wz, math.hypot(vx, vy)
        with self.lock:
            self.lok.bewegen(vx * dt, vy * dt, wz * dt, jetzt)
        self.gefahren += math.hypot(vx, vy) * dt

    # ---------------- LiDAR ----------------
    def _scan(self, msg, topic, i):
        fronts = self.p('scan_front_deg')
        xy = lidar.punkte_xy(msg, fronts[i] if i < len(fronts) else 0.0, self.p('obstacle_min_range'))
        xy = xy[np.hypot(xy[:, 0], xy[:, 1]) >= self.p('karte_min_abstand')]
        xy[:, 0] += self.p('lidar_x')
        self.scans[topic] = (time.time(), xy)

    def _scans_verarbeiten(self):
        jetzt = time.time()
        # Der erste LiDAR (scan_topics[0]) baut die Karte. Die weiteren zaehlen erst mit, wenn ihr genauer
        # Einbau gelernt ist (siehe lib/karte.py, LidarEinbau). Jeder Scan mit seiner Messzeit.
        frisch = [(t, self.scans[t]) for t in self.p('scan_topics') if t in self.scans and jetzt - self.scans[t][0] < 0.5]
        if not frisch:
            return
        (_, (zeit, punkte)), weitere = frisch[0], {t: v for t, v in frisch[1:]}
        if abs(self.dreh) > 1.0:
            return                   # dreht schnell: Scan ist verzerrt -> nur mitrechnen
        with self.lock:
            vorher = self.lok.pose
            self.lok.scan(punkte, jetzt, eintragen=abs(self.dreh) < 0.5, scan_zeit=zeit, weitere=weitere)
            for t in weitere:
                self.scans.pop(t, None)          # jeden Scan nur einmal verwenden
            self.scans.pop(frisch[0][0], None)
            if self.lok.pose is not None:   # Scan in Kartenkoordinaten fuer die Anzeige (passt so immer zur Karte)
                auswahl = punkte[np.linspace(0, len(punkte) - 1, min(len(punkte), 180)).astype(int)]
                self.scan_karte = np.round(K.in_karte(self.lok.pose, auswahl), 3).tolist()
            if vorher is None and self.lok.pose is not None:
                self.get_logger().info(f'Karte: {self.lok.status}')
            suchen = self.lok.pose is None and len(self.lok.puffer) >= 3 and not self.suche_laeuft
        self.geaendert = True
        if suchen:
            self.suche_laeuft = True
            threading.Thread(target=self._global_suchen, daemon=True).start()
        self._umschauen_pruefen()

    def _global_suchen(self):
        """Neue Fahrt mit vorhandener Karte: wo bin ich? (dauert einige Sekunden, eigener Thread)"""
        try:
            with self.lock:
                if self.lok.pose is not None or not self.lok.puffer:
                    return
                odom_scan, punkte = self.lok.puffer[-1]
                alle = [punkte] + [K.in_karte(K.relativ(odom_scan, o), p) for o, p in self.lok.puffer[-8:-1]]
            pose, guete, eindeutig = self.karte.belegung.global_suchen(np.concatenate(alle))
            with self.lock:
                self.lok.guete = guete
                if pose is None or not eindeutig:
                    self.fehlversuche += 1
                    self.lok.status = (f'suche Position in der Karte ... (beste Uebereinstimmung {guete:.0%}, '
                                       f'{self.fehlversuche}. Versuch)')
                    if self.fehlversuche >= 3:
                        self.lok.status += ' - andere Umgebung? Panel -> Karte -> Neue Karte'
                    return
                self.fehlversuche = 0
                self.lok.pose = K.verknuepfen(pose, K.relativ(odom_scan, self.lok.odom))
                self.lok.status = f'Position in der Karte gefunden ({guete:.0%})'
                self.karte.fahrten += 1
                for o, p in self.lok.puffer:
                    self.karte.belegung.eintragen(K.verknuepfen(pose, K.relativ(odom_scan, o)), p)
                self.lok.puffer = []
            self.get_logger().info(self.lok.status)
        finally:
            # nicht dauernd suchen (kostet viel Rechenzeit, die Linienfolger und KI brauchen):
            # erst alle 5 s, nach mehreren Fehlversuchen nur noch alle 30 s
            time.sleep(5.0 if self.fehlversuche < 3 else 30.0)
            self.suche_laeuft = False

    # ---------------- Kamera + Tiefe ----------------
    def _kamera_verarbeiten(self):
        bild_msg, tiefe_msg = self.bild, self.tiefe
        jetzt = time.time()
        ki_zeit, ki = self.ki
        if ki_zeit and jetzt - ki_zeit < 1.0:
            if ki.get('kamera_ok'):
                gier = 0.0
            else:
                gier = ki.get('kamera_gier')     # Arm schaut zur Seite (bekannt) oder None (unbekannt)
        else:
            gier = 0.0                           # ohne KI: Arm steht in Fahrstellung (wie nach dem Start)
        with self.lock:
            pose = self.lok.pose
        if pose is None or gier is None or bild_msg is None or abs(self.dreh) > 0.4:
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

    # ---------------- KI ----------------
    def _ki(self, msg):
        try:
            ki = json.loads(msg.data)
        except ValueError:
            return
        self.ki = (time.time(), ki)
        with self.lock:
            pose = self.lok.pose
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
            pose = self.lok.pose
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
        with self.lock:
            pose, status, guete, fahrten = self.lok.pose, self.lok.status, self.lok.guete, self.karte.fahrten
            einbau = self.lok.einbau_text()
        aus = {'zeit': time.time(), 'status': status, 'guete': round(guete, 2), 'fahrten': fahrten,
               'karte': self.p('karte'), 'lidar_einbau': einbau}
        if pose is not None:
            aus.update({'x': round(pose[0], 3), 'y': round(pose[1], 3), 'w': round(pose[2], 3), 'scan': self.scan_karte})
        self.pub_pose.publish(String(data=json.dumps(aus)))

    def _dateien_schreiben(self):
        if not self.geaendert:
            return
        self.geaendert = False
        with self.lock:
            bild, bereich = self.karte.bild()
            p, f = self.karte.wolke_export()
            info = {'zeit': time.time(), 'karte': self.p('karte'), 'fahrten': self.karte.fahrten,
                    'bereich': bereich, 'aufloesung': self.karte.boden.aufl, 'status': self.lok.status,
                    'pose': self.lok.pose, 'pfad': self.lok.pfad[-3000:], 'marker': self.karte.marker.sichere(),
                    'punkte_3d': int(len(p))}
        os.makedirs(self.ordner, exist_ok=True)
        if bild is not None:
            schreibe_atomar(os.path.join(self.ordner, 'karte.png'), cv2.imencode('.png', bild)[1].tobytes())
        kopf = np.array([len(p)], np.uint32).tobytes()
        schreibe_atomar(os.path.join(self.ordner, 'wolke.bin'), kopf + p.astype('<f4').tobytes() + f.tobytes())
        schreibe_atomar(os.path.join(self.ordner, 'karte.json'), json.dumps(info).encode())

    def _speichern(self):
        with self.lock:
            self.karte.letzte_pose = self.lok.pose
            self.karte.speichern()
            ply = self.karte.ply()
        schreibe_atomar(os.path.join(self.ordner, 'karte.ply'), ply)

    def _kommando(self, msg):
        befehl = msg.data.strip()
        if befehl == 'speichern':
            self._speichern()
            self.get_logger().info('Karte gespeichert')
        elif befehl == 'neu':
            with self.lock:
                if os.path.isdir(self.ordner):
                    # nichts loeschen: alte Karte bleibt als Sicherung liegen
                    shutil.move(self.ordner, self.ordner + time.strftime('_alt_%Y%m%d_%H%M%S'))
                self.karte = K.Karte(self.ordner)
                self.lok = K.Lokalisierung(self.karte)
            self.geaendert = True
            self.get_logger().info('Neue Karte angefangen (alte als Sicherung umbenannt)')


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
