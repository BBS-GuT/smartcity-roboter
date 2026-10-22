"""Unveraenderte historische Fahrpfad-Synthetik, ausschliesslich mit ROS-Attrappen.

Bekannt fehlerhafte Rueckgaben sind historische Signaturen, keine Sollregression.
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
from pathlib import Path
import platform
import sys
import threading
import time
import types
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from basis import pruefe_modul, zentrale_methoden


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", required=True, type=Path)
    root = parser.parse_args().export.resolve()
    sys.path[:0] = [str(root / "tests/attrappen"), str(root / "line_follower"), str(root / "ki")]
    # Alle hier benoetigten ROS-Importe pruefen, bevor ein Node konstruiert wird.
    stub_namen = ("rclpy", "rclpy.node", "rclpy.callback_groups", "rclpy.executors",
                  "rclpy.parameter", "rclpy.qos", "sensor_msgs", "sensor_msgs.msg",
                  "nav_msgs", "nav_msgs.msg", "geometry_msgs", "geometry_msgs.msg",
                  "std_msgs", "std_msgs.msg", "cv_bridge")
    for name in stub_namen:
        modul = importlib.import_module(name)
        rel = name.replace(".", "/")
        paket = root / "tests/attrappen" / rel / "__init__.py"
        datei = "tests/attrappen/" + rel + ("/__init__.py" if paket.is_file() else ".py")
        pruefe_modul(modul, root, datei)
    import line_follower as lf
    import entscheider
    import numpy as np
    import cv2
    pruefe_modul(lf, root, "line_follower/line_follower.py")
    pruefe_modul(entscheider, root, "ki/entscheider.py")
    pruefe_modul(lf.lidar, root, "lib/lidar.py")
    methoden = zentrale_methoden(root, np, lf.lidar)

    class Sensor:
        def __init__(self):
            self.scans, self.lock = {}, threading.Lock()
            self.lidar_d = self.lidar_xy = None

        def p(self, key):
            return {"scan_front_deg": [0.0, 0.0], "obstacle_min_range": 0.08,
                    "fahrschlauch_breite": 0.30, "fahrschlauch_laenge": 0.80,
                    "obstacle_half_deg": 30.0}[key]

        def weg_voraus(self):
            return None

    for name, funktion in methoden.items():
        setattr(Sensor, name, funktion)

    def scan(ranges, stamp=1000.0):
        return types.SimpleNamespace(ranges=ranges, angle_min=-math.pi,
            angle_increment=2 * math.pi / 500, range_min=0.05, range_max=12.0,
            header=types.SimpleNamespace(stamp=types.SimpleNamespace(sec=int(stamp), nanosec=0),
                                         frame_id="test"))

    def follower():
        n = lf.LineFollower()
        if type(n.pub).__module__ != "rclpy.node":
            raise RuntimeError("Publisher ist keine lokale ROS-Attrappe.")
        n._p.update(show=False, publish_image=False)
        n.gedaechtnis.hinzufuegen([(0.05 + 0.02 * k, 0.0) for k in range(30)])
        n.bild_zeit, n.bild_alter, n.stempel_ok = 1000.0, 0.1, True
        return n

    def fake_command(n):
        n.steuern()
        cmd = n.pub.letzte
        return [cmd.linear.x, cmd.linear.y, cmd.angular.z]

    cases = [("valid_free", 3.0, "both", 1000.0), ("all_zero", 0.0, "both", 1000.0),
        ("all_nan", float("nan"), "both", 1000.0), ("all_inf", float("inf"), "both", 1000.0),
        ("empty", None, "both", 1000.0), ("one_missing", 3.0, "one", 1000.0),
        ("one_stale", 3.0, "stale", 1000.0), ("old_header", 3.0, "both", 970.0),
        ("both_stale", 3.0, "bothstale", 1000.0), ("near_control", 0.10, "both", 1000.0)]
    rows = []
    with patch.object(time, "time", return_value=1000.0):
        for name, value, channels, stamp in cases:
            z, n = Sensor(), follower()
            msg = scan([] if value is None else [value] * 500, stamp)
            for i, topic in enumerate(("/scan0", "/scan1")):
                if channels == "one" and i == 1:
                    continue
                z._scan(msg, topic, i)
                n.on_scan(msg, topic, i)
                if channels == "bothstale" or (channels == "stale" and i == 1):
                    _, xy, wide = z.scans[topic]
                    z.scans[topic] = (980.0, xy, wide)
                    _, distance = n.scans[topic]
                    n.scans[topic] = (980.0, distance)
            distance, obj, wide = z.lidar_pruefen()
            z.lidar_d = distance
            rear = z.lidar_hinten()
            world = {"bild_nr": 1, "bild_zeit": 999.9, "objekte": [], "ampel": None,
                "stoppschild": False, "lidar": distance, "lidar_breit": wide,
                "lidar_xy": z.lidar_xy, "lidar_hinten": rear, "tiefe_hindernis": False}
            decision = entscheider.Entscheider().update(1000.0, world)
            n.on_ki(types.SimpleNamespace(data=json.dumps(decision)))
            result = n.entscheide()
            n.steuern()
            test_publications = n.pub.n
            n._p["drive"] = True
            command = fake_command(n)
            halt = name in ("both_stale", "near_control")
            signatur = (test_publications == 0 and n.pub.n == 1
                and all(math.isclose(a, b, abs_tol=1e-12) for a, b in
                        zip(command, [0.0 if halt else 0.15, 0.0, 0.0]))
                and decision["aktion"] == ("stopp" if halt else "fahren"))
            grund = n.notbremse()
            if name == "both_stale":
                signatur = signatur and distance is None and grund.startswith("KEIN LIDAR")
            elif name == "near_control":
                signatur = signatur and distance is not None and distance < 0.12 and grund.startswith("NOTBREMSE")
            else:
                signatur = signatur and math.isinf(distance) and grund is None
            if name in ("all_zero", "all_nan", "all_inf", "empty"):
                signatur = signatur and rear == 5.0
            rows.append({"case": name, "lidar_distance": str(distance), "rear_distance": rear,
                "ki_action": decision["aktion"], "ki_reason": decision["grund"],
                "notbremse": grund, "decision": result,
                "default_drive_false_publications": test_publications,
                "fake_drive_true_cmd": command, "historical_signature_match": bool(signatur)})
        for direction in (1.0, -1.0):
            n = follower()
            n._p.update(drive=True, direction=direction)
            ranges = [3.0] * 500
            for i in list(range(4)) + list(range(496, 500)):
                ranges[i] = 0.10
            for i, topic in enumerate(("/scan0", "/scan1")):
                n.on_scan(scan(ranges), topic, i)
            n.on_ki(types.SimpleNamespace(data=json.dumps({"aktion": "manoever",
                "manoever": {"lin": -0.05, "quer": 0.0, "dreh": 0.0, "text": "synthetic reverse wish"}})))
            result, command = n.entscheide(), fake_command(n)
            erwartung = [-0.05 if direction > 0 else 0.0, 0.0, 0.0]
            grund = n.notbremse()
            signatur = (n.pub.n == 1 and command == erwartung
                and (grund is None if direction > 0 else grund.startswith("NOTBREMSE")))
            rows.append({"case": "reverse_rear_obstacle", "direction_parameter": direction,
                "rear_obstacle_m": 0.10, "front_m": 3.0, "notbremse": grund,
                "decision": result, "fake_drive_true_cmd": command,
                "historical_signature_match": bool(signatur)})
    print(json.dumps({"product_acceptance": False, "hardware_access": False,
        "mode": "original methods with local ROS test doubles; synthetic KI reverse wish",
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__},
        "historical_signature_match": all(r["historical_signature_match"] for r in rows),
        "case_count": len(rows), "results": rows}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
