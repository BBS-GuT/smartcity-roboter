#!/usr/bin/env python3
# Simulator: ersetzt Roboter, Kamera, Tiefenkamera, LiDAR und Arm, damit man ALLES ohne
# Roboter testen kann. Braucht ROS 2. FAEHRT KEINEN ECHTEN ROBOTER, aber er benutzt die
# ROS_DOMAIN_ID der Umgebung -> NIE mit Domain 30 im Roboter-Netz starten! (scripts/simulation.sh)
#
# Welt: sim/welt.py (Rundkurs mit engen Kurven, Ampel, Zebrastreifen mit Fussgaenger,
# Holzwuerfel auf der Fahrbahn, Stoppschild, Einbahnstrasse, Haeuser).
#   Ampel: wird rot, wenn der Roboter kommt; gruen nach 3 s Stand
#   Fussgaenger: geht weg, wenn der Roboter 4 s vor dem Zebrastreifen gewartet hat
#   Wuerfel: kann mit dem Arm gegriffen und abgelegt werden. Ob der Greifer ihn trifft, wird aus den
#            Servowinkeln ausgerechnet, nicht aus eingelernten Posen. Der Simulator rechnet dabei mit dem
#            "wirklichen" Arm (sim/arm_sim.yaml, geometrie_simulator: etwas andere Masse, Servo-Nullpunkte,
#            Durchhaengen), die KI plant mit den Nennmassen (geometrie). Wie beim echten Roboter muss sie den
#            Unterschied also lernen (lib/greifen.py). Parameter arm_wie_planer:=true schaltet das aus.
#            wuerfel_zufall:=true legt den Wuerfel zufaellig (Lage entlang/quer zur Strasse, Groesse).
import json
import math
import os
import re
import sys
import time
from collections import deque

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image, LaserScan, CameraInfo, Imu, CompressedImage
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
from std_msgs.msg import Float32, String
from cv_bridge import CvBridge

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, '..', 'lib'))
from welt import Welt  # noqa: E402
import arm as armlib   # noqa: E402
import greifen         # noqa: E402


class Simulator(Node):
    def __init__(self):
        super().__init__('simulator')
        self.declare_parameter('einbahn', True)
        self.declare_parameter('wuerfel', True)
        self.declare_parameter('fussgaenger', True)
        self.declare_parameter('gegner', False)   # anderer Roboter steht auf der Linie (blockiert)
        # Kamerabild kommt so viele Sekunden verspaetet an (wie auf einem ueberlasteten Roboter)
        self.declare_parameter('kamera_verzoegerung', 0.0)
        # wie in echt: grosser Raum statt Waende direkt am Spielfeld, Lagesensor misst Drehungen etwas falsch
        self.declare_parameter('halle', False)
        self.declare_parameter('imu_skala', 1.0)      # z. B. 1.03 = misst 3 % zu viel Drehung
        self.declare_parameter('lidar_verzoegerung', 0.0)   # Scan kommt so viele s spaeter an (ueberlasteter Roboter)
        # Ein echter LiDAR misst nicht alles gleichzeitig, sondern dreht sich (ca. 0,1 s je Umdrehung).
        # Faehrt der Roboter dabei eine Kurve, ist der Scan leicht verzerrt. 0 = alles gleichzeitig.
        self.declare_parameter('lidar_umlauf', 0.0)
        # Wo sitzt der zweite LiDAR (scan1) gegenueber dem ersten? [x m, y m, Drehung Grad] (Einbau nicht gleich)
        self.declare_parameter('lidar1_einbau', [0.0, 0.0, 0.0])
        self.declare_parameter('arm_wie_planer', False)   # true = Arm genau so, wie die KI ihn sich vorstellt
        self.declare_parameter('wuerfel_zufall', False)   # true = Wuerfel zufaellig legen
        self.declare_parameter('wuerfel_saat', 0)         # Zufallszahl dafuer (0 = jedes Mal anders)
        # Weitere Fehler, die es am echten Roboter geben kann (alle Standardwerte = wie bisher, kein Fehler):
        # lidar0_einbau: auch der erste LiDAR sitzt nicht in der Mitte / "vorne" ist gedreht (z. B. 90 oder 180 Grad)
        self.declare_parameter('lidar0_einbau', [0.0, 0.0, 0.0])
        self.declare_parameter('lidar_gespiegelt', False)   # LiDAR zaehlt die Winkel andersherum
        self.declare_parameter('lidar_hz', 7.0)             # Umdrehungen je Sekunde (T-mini Plus: 6)
        self.declare_parameter('lidar_strahlen', 360)       # Strahlen je Umdrehung (T-mini Plus: ca. 670)
        self.declare_parameter('lidar_verdeckt', 0.0)       # so viel Grad verdeckt der Roboteraufbau je LiDAR
        self.declare_parameter('odom_twist', True)          # False: /odom_raw ohne Geschwindigkeiten (nur Position)
        self.declare_parameter('imu_vorzeichen', 1.0)       # -1: Lagesensor falsch herum eingebaut
        self.declare_parameter('gyro_bias', 0.003)          # Nullpunktfehler des Lagesensors (rad/s)
        self.declare_parameter('odom_rauschen', 0.0)        # Mecanum-Raeder rutschen zufaellig (Anteil der Geschw.)
        self.declare_parameter('sensor_stau', 0.0)          # Odometrie/IMU kommen gesammelt alle so viele s an
        self.declare_parameter('stempel', 'jetzt')          # Zeitstempel: jetzt | null (fehlt) | versatz (andere Uhr)
        self.stau = []
        self.stau_zeit = 0.0
        self.verlauf = deque(maxlen=400)          # (Zeit, Pose, Arm) fuer verspaetete Bilder
        self.declare_parameter('halle_rand', 3.0)           # so weit (m) sind die Hallenwaende vom Spielfeld weg
        self.declare_parameter('halle_haeuser', 2)          # so viele Haeuser stehen in der Halle
        self.welt = Welt(self.get_parameter('einbahn').value, self.get_parameter('wuerfel').value,
                         self.get_parameter('fussgaenger').value, self.get_parameter('halle').value,
                         self.get_parameter('halle_rand').value, self.get_parameter('halle_haeuser').value)
        self.imu_skala = self.get_parameter('imu_skala').value
        if self.get_parameter('gegner').value:
            x, y, _ = self.welt.pose_bei(1.75)
            self.welt.zylinder.append({'x': x, 'y': y, 'r': 0.12, 'h': 0.2, 'farbe': (90, 90, 90), 'name': 'gegner'})
        self.bridge = CvBridge()
        self.rng = np.random.default_rng(7)
        x, y, w = self.welt.pose_bei(0.0)
        self.pose = [x, y, w]                 # wahre Position
        self.odom_pose = [x, y, w]            # was die Raeder meinen (mit Fehlern)
        self.v = self.quer = self.w = 0.0
        self.cmd_zeit = 0.0
        self.stand_seit = None
        self.arm = [90, 120, 10, 20, 90, 30]  # Fahrstellung
        self.haelt = None                     # gegriffener Zylinder
        self.abgelegt = None
        self.posen = armlib.lade_posen()
        # "So ist der Arm wirklich" (weicht von dem ab, womit die KI plant)
        einst = armlib.lade_einstellungen()
        self.arm_geo = None if self.get_parameter('arm_wie_planer').value else einst.get('geometrie_simulator')
        if self.arm_geo:
            self.arm_geo = dict(einst.get('geometrie') or {}, **self.arm_geo)
        if self.get_parameter('wuerfel_zufall').value:
            self._wuerfel_zufaellig(self.get_parameter('wuerfel_saat').value or None)
        self.gefahren = 0.0
        self.create_subscription(Twist, '/cmd_vel', self.cmd, 10)
        self.create_subscription(String, '/arm6_joints_sim', self.arm_befehl, 10)
        self.pub_bild = self.create_publisher(Image, '/camera/color/image_raw', qos_profile_sensor_data)
        self.pub_tiefe = self.create_publisher(Image, '/camera/depth/image_raw', qos_profile_sensor_data)
        self.pub_info_c = self.create_publisher(CameraInfo, '/camera/color/camera_info', 10)
        self.pub_info_d = self.create_publisher(CameraInfo, '/camera/depth/camera_info', 10)
        self.pub_scan = [self.create_publisher(LaserScan, t, qos_profile_sensor_data) for t in ('/scan0', '/scan1')]
        self.pub_akku = self.create_publisher(Float32, '/battery', 10)
        self.pub_imu = self.create_publisher(Imu, '/imu/data_raw', 10)
        self.pub_odom = self.create_publisher(Odometry, '/odom_raw', 10)
        self.pub_zustand = self.create_publisher(String, '/sim/zustand', 10)
        self.pub_draufsicht = self.create_publisher(CompressedImage, '/sim/bild/compressed', 1)   # fuers Panel
        self.spur = deque(maxlen=1500)
        self.letzte = time.time()
        self.create_timer(0.02, self.physik)
        self.create_timer(1 / 15, self.kamera)
        self.create_timer(0.1, self.tiefe)
        self.create_timer(1 / self.get_parameter('lidar_hz').value, self.lidar)
        self.create_timer(1.0, lambda: self.pub_akku.publish(Float32(data=12.3)))
        self.create_timer(0.2, self.draufsicht)
        self.get_logger().info(f'Simulator laeuft, Strecke {self.welt.laenge:.2f} m')

    # ---------------- Befehle ----------------
    def cmd(self, msg):
        self.v, self.quer, self.w = msg.linear.x, msg.linear.y, msg.angular.z
        self.cmd_zeit = time.time()

    def _wuerfel_zufaellig(self, saat):
        rng = np.random.default_rng(saat)
        for z in self.welt.zylinder:
            if z['name'] != 'wuerfel':
                continue
            s = self.welt.wuerfel_s + float(rng.uniform(-0.10, 0.10))
            quer = float(rng.uniform(-0.035, 0.035))
            x, y, w = self.welt.pose_bei(s)
            z['x'], z['y'] = x - quer * math.sin(w), y + quer * math.cos(w)
            z['r'] = float(rng.uniform(0.018, 0.025))
            z['h'] = 2 * z['r'] * float(rng.uniform(0.9, 1.0))
            self.get_logger().info(f"Wuerfel zufaellig: {s - self.welt.wuerfel_s:+.2f} m entlang, {quer * 100:+.1f} cm "
                                   f"quer, {z['r'] * 200:.1f} cm breit, {z['h'] * 100:.1f} cm hoch")

    def arm_befehl(self, msg):
        m = re.match(r'\[([^\]]*)\]', msg.data)
        if not m:
            return
        neu = [int(v) for v in m.group(1).split(',')]
        alt = self.arm
        self.arm = neu
        auf, zu = armlib.greifer_werte()
        mitte = (auf + zu) / 2
        schliesst = (alt[5] - mitte) * (zu - mitte) < 0 and (neu[5] - mitte) * (zu - mitte) > 0
        oeffnet = (alt[5] - mitte) * (zu - mitte) > 0 and (neu[5] - mitte) * (zu - mitte) < 0
        g = self.greifer_welt()           # Greifermitte laut Servowinkeln (Arm-Geometrie aus der Arm-Datei)
        if schliesst and self.haelt is None and g is not None:
            for z in self.welt.zylinder:
                if z['name'] != 'wuerfel':
                    continue
                ok, grund = greifen.trifft(g, (z['x'], z['y']), 2 * z['r'], z['h'])   # gleiche Regel wie im Training
                if ok:
                    self.haelt = z
                    self.welt.zylinder.remove(z)
                    self.get_logger().info(f'Wuerfel gegriffen ({grund})')
                else:
                    self.get_logger().info(f'Greifen daneben: {grund}')
        if oeffnet and self.haelt is not None:
            if g is not None:
                self.haelt['x'], self.haelt['y'] = g[0], g[1]   # faellt senkrecht nach unten
            self.welt.zylinder.append(self.haelt)
            self.abgelegt = self.haelt
            self.haelt = None
            self.get_logger().info('Wuerfel abgelegt')

    # ---------------- Welt ----------------
    def physik(self):
        jetzt = time.time()
        dt = min(0.1, jetzt - self.letzte)
        self.letzte = jetzt
        if jetzt - self.cmd_zeit > 0.3:           # Watchdog wie beim echten Board
            self.v = self.quer = self.w = 0.0
        x, y, w = self.pose
        x += (self.v * math.cos(w) - self.quer * math.sin(w)) * dt
        y += (self.v * math.sin(w) + self.quer * math.cos(w)) * dt
        w += self.w * dt
        self.pose = [x, y, (w + math.pi) % (2 * math.pi) - math.pi]
        self.verlauf.append((jetzt, list(self.pose), self.arm[0]))
        self.gefahren += math.hypot(self.v, self.quer) * dt
        # Odometrie mit Fehlern: 3 % zu kurz gemessen, Drehung leicht verfaelscht
        ov, oq, ow = self.v * 0.97, self.quer * 0.97, self.w * 1.02 + 0.004
        rausch = self.get_parameter('odom_rauschen').value
        if rausch > 0:   # Mecanum-Raeder rutschen: mal mehr, mal weniger, auch seitlich
            ov *= 1 + float(self.rng.normal(0, rausch))
            oq += abs(self.v) * float(self.rng.normal(0, rausch))
        ox, oy, oth = self.odom_pose
        self.odom_pose = [ox + (ov * math.cos(oth) - oq * math.sin(oth)) * dt,
                          oy + (ov * math.sin(oth) + oq * math.cos(oth)) * dt, oth + ow * dt]
        o = Odometry()
        o.header.stamp = self._stempel(jetzt)
        if self.get_parameter('odom_twist').value:
            o.twist.twist.linear.x, o.twist.twist.linear.y, o.twist.twist.angular.z = ov, oq, ow
        o.pose.pose.position.x, o.pose.pose.position.y = self.odom_pose[0], self.odom_pose[1]
        o.pose.pose.orientation.z, o.pose.pose.orientation.w = math.sin(self.odom_pose[2] / 2), math.cos(self.odom_pose[2] / 2)
        imu = Imu()
        imu.header.stamp = o.header.stamp
        imu.angular_velocity.z = (self.w * self.imu_skala * self.get_parameter('imu_vorzeichen').value
                                  + self.get_parameter('gyro_bias').value + float(self.rng.normal(0, 0.01)))
        imu.linear_acceleration.z = 9.81
        stau = self.get_parameter('sensor_stau').value
        if stau > 0:   # ueberlasteter Roboter: Nachrichten kommen gesammelt an
            self.stau += [(self.pub_odom, o), (self.pub_imu, imu)]
            if jetzt - self.stau_zeit >= stau:
                for pub, m in self.stau:
                    pub.publish(m)
                self.stau, self.stau_zeit = [], jetzt
        else:
            self.pub_odom.publish(o)
            self.pub_imu.publish(imu)

        steht = abs(self.v) < 0.005 and abs(self.w) < 0.01 and abs(self.quer) < 0.005
        self.stand_seit = (self.stand_seit or jetzt) if steht else None
        stand = jetzt - self.stand_seit if self.stand_seit else 0.0
        s, seite = self.welt.s_von(x, y)
        vorwaerts = math.cos(w - self.welt.pose_bei(s)[2]) > 0
        # Ampel: rot, wenn der Roboter (vorwaerts) kommt; gruen nach 3 s Stand
        bis_ampel = (self.welt.ampel_s - s) % self.welt.laenge
        if vorwaerts and bis_ampel < 0.8:
            if self.welt.ampel == 'aus':
                self.welt.ampel = 'rot'
            elif self.welt.ampel == 'rot' and stand > 3.0:
                self.welt.ampel = 'gruen'
        elif bis_ampel > self.welt.laenge - 0.2 or not vorwaerts:
            self.welt.ampel = 'aus'
        # Fussgaenger geht weg, wenn der Roboter 4 s vor dem Zebrastreifen gewartet hat
        bis_zebra = (self.welt.zebra_s - s) % self.welt.laenge
        if stand > 4.0 and bis_zebra < 0.6:
            vorher = len(self.welt.zylinder)
            self.welt.zylinder = [z for z in self.welt.zylinder if z['name'] != 'fussgaenger']
            if len(self.welt.zylinder) < vorher:
                self.get_logger().info('Fussgaenger ist ueber den Zebrastreifen gegangen')
        fussgaenger = any(z['name'] == 'fussgaenger' for z in self.welt.zylinder)
        wuerfel = next((z for z in self.welt.zylinder if z['name'] == 'wuerfel'), None)
        self.pub_zustand.publish(String(data=json.dumps({
            'zeit': jetzt, 'x': round(x, 3), 'y': round(y, 3), 'w': round(self.pose[2], 3),
            'odom': [round(v, 3) for v in self.odom_pose], 's': round(s, 3), 'seite': round(seite, 3),
            'vorwaerts': vorwaerts, 'v': round(self.v, 3), 'quer': round(self.quer, 3), 'dreh': round(self.w, 3),
            'gefahren': round(self.gefahren, 3), 'ampel': self.welt.ampel, 'fussgaenger': fussgaenger,
            'wuerfel': None if wuerfel is None else [round(wuerfel['x'], 3), round(wuerfel['y'], 3)],
            'haelt': self.haelt is not None,
            'abgelegt': None if self.abgelegt is None else [round(self.abgelegt['x'], 3), round(self.abgelegt['y'], 3)],
            'arm': self.arm})))

    def greifer_welt(self):
        """Wo ist die Greiferspitze (Welt, x/y/Hoehe)? None = Arm-Geometrie unbekannt."""
        try:
            vor, links, hoch = armlib.greifer_position(self.arm, self.arm_geo)
        except Exception:
            return None
        x, y, w = self.pose
        return (x + vor * math.cos(w) - links * math.sin(w), y + vor * math.sin(w) + links * math.cos(w), hoch)

    def draufsicht(self):
        """Bild der Simulation von oben (Panel: Kamera -> Simulation)."""
        x, y, _ = self.pose
        if not self.spur or math.hypot(self.spur[-1][0] - x, self.spur[-1][1] - y) > 0.02:
            self.spur.append((x, y))
        g = self.greifer_welt()
        bild = self.welt.draufsicht(self.pose, self.arm[0] - 90, g[:2] if g else None, self.haelt is not None,
                                    list(self.spur))
        ok, jpg = cv2.imencode('.jpg', bild, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if ok:
            self.pub_draufsicht.publish(CompressedImage(format='jpeg', data=jpg.tobytes()))

    # ---------------- Sensoren ----------------
    def _frueher(self, name='kamera_verzoegerung'):
        """(Zeit, Pose, Arm) vor 'kamera_verzoegerung' Sekunden: so alt ist das Bild, wenn es ankommt."""
        verz = self.get_parameter(name).value
        jetzt = time.time()
        if verz <= 0 or not self.verlauf:
            return jetzt, self.pose, self.arm[0]
        for t, pose, arm in reversed(self.verlauf):
            if t <= jetzt - verz:
                return t, pose, arm
        return self.verlauf[0]

    def kamera(self):
        zeit, pose, arm = self._frueher()
        bild, _ = self.welt.kamera(pose, arm - 90)
        msg = self.bridge.cv2_to_imgmsg(bild, 'bgr8')
        msg.header.stamp.sec, msg.header.stamp.nanosec = int(zeit), int((zeit % 1) * 1e9)  # Aufnahmezeit
        msg.header.frame_id = 'camera_color'
        self.pub_bild.publish(msg)
        self.pub_info_c.publish(CameraInfo(header=msg.header, width=bild.shape[1], height=bild.shape[0]))

    def tiefe(self):
        zeit, pose, arm = self._frueher()
        _, d = self.welt.kamera(pose, arm - 90, schritt=2)
        d = d + self.rng.normal(0, 0.003, d.shape) * (d > 0)
        msg = self.bridge.cv2_to_imgmsg((d * 1000).astype(np.uint16), '16UC1')
        msg.header.stamp.sec, msg.header.stamp.nanosec = int(zeit), int((zeit % 1) * 1e9)
        msg.header.frame_id = 'camera_depth'
        self.pub_tiefe.publish(msg)
        self.pub_info_d.publish(CameraInfo(header=msg.header, width=d.shape[1], height=d.shape[0]))

    def _pose_zu(self, t):
        """Wahre Pose zur Zeit t (aus dem Verlauf, sonst die aktuelle)."""
        for zeit, pose, _ in reversed(self.verlauf):
            if zeit <= t:
                return pose
        return self.verlauf[0][1] if self.verlauf else self.pose

    def _stempel(self, t):
        """Zeitstempel fuer Nachrichten (Parameter 'stempel': wie zuverlaessig sind die Zeitstempel am Roboter?)"""
        art = self.get_parameter('stempel').value
        if art == 'null':
            t = 0.0
        elif art == 'versatz':
            t -= 1000.0          # andere Uhr (z. B. Board ohne Zeitabgleich)
        from builtin_interfaces.msg import Time
        return Time(sec=int(t), nanosec=int((t % 1) * 1e9))

    def lidar(self):
        verz = self.get_parameter('lidar_verzoegerung').value
        umlauf = self.get_parameter('lidar_umlauf').value
        ende = time.time() - verz                  # letzter Strahl des Scans
        for i, pub in enumerate(self.pub_scan):
            einbau = self.get_parameter('lidar1_einbau' if i == 1 else 'lidar0_einbau').value
            # Strahlen nacheinander, jeder aus der Pose zu seiner Messzeit (Drehung gegen den Uhrzeigersinn)
            r, winkel = self.welt.lidar_umlauf(self._pose_zu, ende, einbau, umlauf,
                                               n=self.get_parameter('lidar_strahlen').value,
                                               gespiegelt=self.get_parameter('lidar_gespiegelt').value,
                                               verdeckt_deg=self.get_parameter('lidar_verdeckt').value,
                                               rng=self.rng, max_r=8.0)
            msg = LaserScan()
            msg.header.stamp = self._stempel(time.time())
            msg.header.frame_id = f'laser{i}'
            msg.angle_min, msg.angle_increment = float(winkel[0]), float(winkel[1] - winkel[0])
            msg.angle_max = float(winkel[-1])
            msg.range_min, msg.range_max = 0.05, 8.0
            msg.scan_time = float(umlauf)
            msg.time_increment = float(umlauf / len(r)) if umlauf > 0 else 0.0
            msg.ranges = r.tolist()
            pub.publish(msg)


def main():
    rclpy.init()
    node = Simulator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    main()
