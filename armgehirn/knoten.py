#!/usr/bin/env python3
# Arm-Gehirn auf dem Roboter (ROS 2): Kamera, Tiefe, Kamera-KI und Arm an armgehirn/gehirn.py anschliessen.
#
# ANTRIEB GESPERRT: Dieses Programm hat keinen Sender fuer Fahrbefehle (/cmd_vel) und startet nicht, solange das
# Fahr-Gehirn (Linienfolger oder KI-Zentrale) laeuft - beide wuerden sonst ebenfalls den Arm bewegen bzw. fahren.
#
# Schnittstelle nach aussen (fuer spaeter: Panel, KI-Zentrale, Wechsel mit dem Fahr-Gehirn):
#   /armgehirn/kommando  std_msgs/String  'start' (Objekt vor dir) | 'abbrechen' | 'grundstellung' | 'fahrstellung'
#                                         | 'status'
#   /armgehirn/zustand   std_msgs/String  JSON: zustand (bereit|laeuft|fertig|abgebrochen|fehler), phase, ergebnis,
#                                         antrieb, lernstand, fortschritt (1x pro Sekunde und bei jeder Aenderung)
#   /armgehirn/ergebnis  std_msgs/String  JSON am Ende jedes Versuchs ("fertig + Ergebnis")
# Start allein (nur Schnittstelle): python3 armgehirn/knoten.py   Training: scripts/armgehirn_training.sh
import json
import os
import sys
import threading
import time

for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_v, '1')

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HIER, '..'))
for _d in (HIER, os.path.join(REPO, 'lib'), os.path.join(REPO, 'erkennung'), os.path.join(REPO, 'line_follower')):
    sys.path.insert(0, _d)
import numpy as np  # noqa: E402

FAHR_GEHIRN = ('line_follower', 'ki_zentrale')   # laufen diese, startet das Arm-Gehirn nicht


def kamera_fahr():
    """Kameramasse in der Fahrstellung wie fuer Linienfolger/KI eingestellt (config/roboter.yaml + lokal)."""
    import einstellungen
    import linie
    werte = einstellungen.lade('line_follower')
    return {k: float(werte.get(k, linie.STANDARD[k])) for k in ('kamera_hoehe', 'kamera_neigung', 'kamera_fov', 'kamera_x')}


class RosQuelle:
    """Frische Bilder: bild() wartet auf ein Tiefenbild, das NACH dem Aufruf ankam (Arm steht dann still)."""

    def __init__(self, node, yolo, image_topic='/camera/color/image_raw', depth_topic='/camera/depth/image_raw'):
        from cv_bridge import CvBridge
        from rclpy.qos import qos_profile_sensor_data
        from sensor_msgs.msg import Image
        self.node, self.yolo, self.bridge = node, yolo, CvBridge()
        self.lock = threading.Lock()
        self.farbe = self.tiefe = None
        self.tiefe_zeit = 0.0
        node.create_subscription(Image, image_topic, self._farbe, qos_profile_sensor_data)
        node.create_subscription(Image, depth_topic, self._tiefe, qos_profile_sensor_data)

    def _farbe(self, msg):
        with self.lock:
            self.farbe = msg

    def _tiefe(self, msg):
        with self.lock:
            self.tiefe, self.tiefe_zeit = msg, time.monotonic()

    def bild(self, timeout=3.0):
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            with self.lock:
                msg, t, farbe = self.tiefe, self.tiefe_zeit, self.farbe
            if msg is not None and t > start:
                d = self.bridge.imgmsg_to_cv2(msg, 'passthrough').astype(np.float32)
                if msg.encoding != '32FC1':
                    d /= 1000.0
                objekte, ki = [], self.yolo is not None and farbe is not None
                if ki:
                    objekte = self.yolo.erkenne(self.bridge.imgmsg_to_cv2(farbe, 'bgr8'), 0.25)
                return d, objekte if ki else [{'name': 'KI fehlt', 'ki_fehlt': True}]
            time.sleep(0.02)
        return None, []


class RosArm:
    def __init__(self, node):
        import arm as armlib
        self.arm = armlib.Arm(node)

    def fahre(self, winkel, zeit_ms=1500):
        return self.arm.fahre(winkel, zeit_ms)

    def warte(self, s):
        time.sleep(s)

    def greifer(self):
        return None      # M3 Pro meldet die Servo-Stellung nicht zurueck (docs/greifarm.md)


def lade_yolo(node):
    """Kamera-KI (Grafikkarte, sonst Prozessor). None: keine KI -> die Sicherheitsregel greift nie (Zweifel)."""
    import yolo as yololib
    try:
        pfad = yololib.gpu_modell_suchen(REPO)
        if pfad:
            return yololib.YoloGpu(pfad)
    except Exception as e:
        node.get_logger().info(f'Kamera-KI nicht auf der Grafikkarte ({e})')
    try:
        return yololib.Yolo(os.path.join(REPO, 'models', 'yolov8n.onnx'))
    except Exception as e:
        node.get_logger().error(f'Kamera-KI fehlt ({e}) -> es wird nichts gegriffen')
        return None


def baue_gehirn(node, protokoll=None, neu_lernen=False):
    """ArmGehirn mit Roboter-Adaptern. Gleiche Dateien wie der Grundbetrieb: config/lokal/greifen.json (Modell
    'eigene') - was das Arm-Gehirn lernt, nutzt spaeter auch das Wegraeumen im Fahrbetrieb."""
    import arm as armlib
    import greifen
    import protokoll as prot
    from augen import Augen
    from gehirn import ArmGehirn
    einst = armlib.lade_einstellungen()
    cfg = dict(einst.get('armgehirn') or {})
    posen = armlib.lade_posen()
    if cfg.get('greifblick') is None and posen.get('greifblick'):
        cfg['greifblick'] = posen['greifblick']
    kin, quelle = armlib.lade_kinematik_mit_quelle(urdf_suchen=True)
    politik = greifen.Politik(str(einst.get('greif_modell', 'eigene')))
    zustand_datei = os.path.join(os.path.dirname(prot.ORDNER), 'armgehirn.json')
    augen = Augen(RosQuelle(node, lade_yolo(node)), prot.lade_zustand(zustand_datei).get('boden'))
    g = ArmGehirn(augen, RosArm(node), kin, politik, posen['fahrstellung'], kamera_fahr(), cfg=cfg,
                  protokoll=protokoll, zustand_datei=zustand_datei, sicherheit_cfg=cfg.get('sicherheit'))
    node.get_logger().info(f'Arm-Gehirn: Kinematik {quelle}; Greif-Lernen {politik.herkunft}, '
                           f'{politik.versuche} Versuche; Grundstellung {g.grund}')
    return g


def fahr_gehirn_laeuft(node, warten=1.5):
    time.sleep(warten)          # ROS braucht kurz, bis es die anderen kennt
    return [n for n in FAHR_GEHIRN if n in node.get_node_names()]


class ArmGehirnKnoten:
    """Kommandos und Zustand als ROS-Topics (Schnittstelle nach aussen)."""

    def __init__(self, node, gehirn):
        from std_msgs.msg import String
        self.node, self.g, self.String = node, gehirn, String
        self.pub_zustand = node.create_publisher(String, '/armgehirn/zustand', 10)
        self.pub_ergebnis = node.create_publisher(String, '/armgehirn/ergebnis', 10)
        node.create_subscription(String, '/armgehirn/kommando', self._kommando, 10)
        node.create_timer(1.0, self._melden)
        self.gemeldet = None

    def _kommando(self, msg):
        k = msg.data.strip().split()
        if not k:
            return
        if k[0] == 'start':
            erwartet = k[1] if len(k) > 1 else None
            if not self.g.start(erwartet):
                self.node.get_logger().warn('Arm-Gehirn laeuft schon')
        elif k[0] == 'abbrechen':
            self.g.abbrechen()
        elif k[0] == 'grundstellung' and self.g.zustand != 'laeuft':
            self.g.grundstellung()
        elif k[0] == 'fahrstellung' and self.g.zustand != 'laeuft':
            self.g.fahrstellung()
        self._melden()

    def _melden(self):
        st = self.g.status()
        self.pub_zustand.publish(self.String(data=json.dumps(st, default=str)))
        if st['ergebnis'] is not None and st['ergebnis'] is not self.gemeldet and st['zustand'] != 'laeuft':
            self.gemeldet = st['ergebnis']
            self.pub_ergebnis.publish(self.String(data=json.dumps(st['ergebnis'], default=str)))


def main():
    import rclpy
    from rclpy.executors import MultiThreadedExecutor
    import protokoll as prot
    rclpy.init()
    node = rclpy.create_node('armgehirn')
    laeuft = fahr_gehirn_laeuft(node)
    if laeuft:
        print(f"Fahr-Gehirn laeuft ({', '.join(laeuft)}) -> Arm-Gehirn startet nicht (Panel: STOPP, Programm beenden).")
        rclpy.shutdown()
        sys.exit(1)
    g = baue_gehirn(node, prot.Protokoll())
    ArmGehirnKnoten(node, g)
    ex = MultiThreadedExecutor(num_threads=2)
    ex.add_node(node)
    try:
        ex.spin()
    except KeyboardInterrupt:
        g.abbrechen()
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    main()
