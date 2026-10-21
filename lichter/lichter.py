#!/usr/bin/env python3
# F1: Lichtsteuerung als ROS-Programm. Die Logik steht in lib/lichtlogik.py, die Werte in config/lichter.yaml.
#
# Start:  python3 lichter/lichter.py        (nach source scripts/env.sh)
#
# Empfaengt (nur lesend, greift nicht in Fahrbefehle ein):
#   /ki/befehl          std_msgs/String  JSON der KI-Zentrale -> Blinker bei Manoevern mit Drehung/Querfahrt
#   /lichter/kommando   std_msgs/String  'blaulicht an|aus', 'abblendlicht an|aus', 'blinker links|rechts|aus',
#                                        'warnblinker an|aus'
# Sendet:
#   /lichter/zustand    std_msgs/String  JSON {abblendlicht, blinker, blinker_an, blaulicht, leiste: [[r,g,b], ...]}
#
# Die echte LED-Leiste wird NOCH NICHT angesteuert (ausgang: keiner), weil Topic und Nachrichtentyp der
# Yahboom-Platine am M3 Pro nicht festgestellt sind. Siehe docs/lichter.md.
import json
import os
import sys
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(REPO, 'lib'))
import lichtlogik  # noqa: E402

AUSGAENGE = ('keiner',)


def lade_einstellungen(repo=REPO):
    import yaml
    werte = {}
    for datei in (os.path.join(repo, 'config', 'lichter.yaml'),
                  os.path.join(repo, 'config', 'lokal', 'lichter.yaml')):
        try:
            with open(datei) as f:
                werte.update((yaml.safe_load(f) or {}).get('lichter') or {})
        except FileNotFoundError:
            pass
    return werte


class Lichtsteuerung(Node):
    def __init__(self, einstellungen):
        super().__init__('lichter')
        ausgang = einstellungen.pop('ausgang', 'keiner')
        if ausgang not in AUSGAENGE:
            raise ValueError(f'unbekannter Lichtausgang {ausgang!r}, erlaubt: {AUSGAENGE}')
        self.logik = lichtlogik.Lichter(einstellungen)
        self.create_subscription(String, '/ki/befehl', self._ki, 10)
        self.create_subscription(String, '/lichter/kommando', self._kommando, 10)
        self.pub = self.create_publisher(String, '/lichter/zustand', 10)
        self.create_timer(0.05, self._takt)     # 20 Hz: Blinktakt 1,5 Hz sauber darstellbar

    def _ki(self, msg):
        try:
            befehl = json.loads(msg.data)
        except (ValueError, TypeError):
            befehl = None                         # kaputter Befehl: wie kein Manoever
        self.logik.ki_befehl(befehl, time.monotonic())

    def _kommando(self, msg):
        if not self.logik.kommando(msg.data, time.monotonic()):
            self.get_logger().warn(f'unbekanntes Lichtkommando: {msg.data!r}')

    def _takt(self):
        z = self.logik.zustand(time.monotonic())
        z['leiste'] = [list(f) for f in z['leiste']]
        self.pub.publish(String(data=json.dumps(z)))


def main():
    rclpy.init()
    node = Lichtsteuerung(lade_einstellungen())
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
