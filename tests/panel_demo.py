#!/usr/bin/env python3
# Zeigt das Control-Panel mit ausgedachten Daten, OHNE Roboter und OHNE ROS.
# Aufruf: python3 tests/panel_demo.py   dann im Browser: http://localhost:8099
# Knoepfe wie START tun hier nichts Sinnvolles (es gibt keinen Roboter).
# Echte Simulation mit ROS 2: scripts/simulation.sh
import math
import os
import sys
import threading
import time
import types

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, 'attrappen'))
sys.path.insert(0, os.path.join(HIER, '..', 'panel'))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
import panel  # noqa: E402
from http.server import ThreadingHTTPServer  # noqa: E402


class Args:
    port = 8099
    kein_netz = False
    tiefe_topic = '/camera/depth/image_raw'
    karte = 'demo'      # Karte aus karten/demo (falls vorhanden, z. B. von scripts/simulation.sh)


node = panel.PanelNode(Args())
prozesse = panel.Prozesse()
ABLAUF = [  # (Sekunden, aktion, grund, ampel, lidar)
    (5, 'fahren', 'Weg frei', None, 1.2),
    (4, 'stopp', 'Rote Ampel -> warte auf Gruen', 'rot', 1.0),
    (3, 'fahren', 'Weg frei', 'gruen', 1.0),
    (4, 'langsam', 'LiDAR-Meldung nicht bestaetigt (z. B. Haus am Rand) -> langsam', None, 0.35),
    (4, 'stopp', 'Hindernis 30 cm, bestaetigt durch Kamera-KI: Person', None, 0.30),
]


def jpeg(text, farbe):
    img = np.full((480, 640, 3), 200, np.uint8)
    cv2.line(img, (330, 480), (300, 250), (25, 25, 25), 30)
    cv2.rectangle(img, (0, 0), (640, 34), farbe, -1)
    cv2.putText(img, text[:60], (8, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return cv2.imencode('.jpg', img)[1].tobytes()


def fake():
    start = time.time()
    letzte = None
    while True:
        t = (time.time() - start) % sum(a[0] for a in ABLAUF)
        for dauer, aktion, grund, ampel, d in ABLAUF:
            if t < dauer:
                break
            t -= dauer
        if (aktion, grund) != letzte:
            letzte = (aktion, grund)
            node._ereignis(types.SimpleNamespace(data=panel.json.dumps(
                {'zeit': time.time(), 'text': f'{aktion.upper()}: {grund}', 'art': aktion})))
        objekte = [{'name': 'Person', 'sicher': 0.81, 'im_weg': True, 'farbe': None}] if 'Person' in grund else []
        node._set('ki', {'aktion': aktion, 'faktor': 1.0, 'grund': grund, 'szenario': 'normal',
                         'ki': 'onnxruntime CPU (Demo)', 'ki_ms': 70, 'lidar': d, 'ampel': ampel,
                         'ampel_quelle': 'LED-Erkennung', 'stoppschild': False, 'tiefe_hindernis': False,
                         'objekte': objekte})
        node._set('lf', {'status': 'Linie: Lenkung +0.05', 'fps': 15, 'linear': 0.15 if aktion != 'stopp' else 0,
                         'angular': 0.05, 'linie': True, 'speed': 0.15})
        farbe = {'fahren': (60, 170, 60), 'langsam': (0, 170, 230), 'stopp': (40, 40, 220)}[aktion]
        node._set('bild_ki', jpeg(f'{aktion.upper()}: {grund}', farbe))
        node._set('bild_lf', jpeg('Linie erkannt', (120, 80, 40)))
        node._set('akku', 12.1)
        node._set('agent', True)
        for i, topic in enumerate(node.scan_topics):
            r = [1.4 + 0.3 * math.cos(2 * (k * math.pi / 180)) for k in range(360)]
            if i == 0:
                for k in range(175, 186):
                    r[k] = d
            node._scan(topic, types.SimpleNamespace(ranges=r, angle_min=-math.pi, angle_increment=math.pi / 180,
                                                    range_min=0.05, range_max=12.0))
        for topic in ('/battery', '/imu/data_raw', '/odom_raw', '/camera/color/camera_info', '/camera/depth/camera_info'):
            node.zaehle(topic)
            node.zaehle(topic)
        time.sleep(0.2)


threading.Thread(target=fake, daemon=True).start()
handler, _ = panel.mache_handler(node, prozesse)
srv = ThreadingHTTPServer(('127.0.0.1', Args.port), handler)
srv.daemon_threads = True
print(f'Panel-Vorschau: http://localhost:{Args.port}  (Strg+C = Ende)')
srv.serve_forever()
