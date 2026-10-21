"""Drei historische Geometriegegenspiele; keine Vermessung oder Kalibrierung.

Herstellerpositionen aus der auf RM-01 gelesenen M3Pro.urdf sind eine explizite
synthetische Referenz. Es werden keine privaten Zustands- oder Rohdaten gelesen.
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from basis import pruefe_modul, zentrale_methoden

MODELL_SHA = "6001d4747d0ed68826a2bacad0891aec531fb9217351c2ffff72114909825acf"
# Feste Joints laser0/laser1 -> base_link; rpy jeweils [0, 0, 0].
MODELL_XYZ = {"laser0_frame": [-0.11617, 0.09156, 0.1253],
              "laser1_frame": [0.10766, -0.09078, 0.1253]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", required=True, type=Path)
    root = parser.parse_args().export.resolve()
    sys.path.insert(0, str(root / "lib"))
    lib = importlib.import_module("lidar")
    pruefe_modul(lib, root, "lib/lidar.py")
    import numpy as np
    methoden = zentrale_methoden(root, np, lib)

    def msg_for_xy(x, y, frame):
        angle = math.atan2(y, x)
        if frame == "laser0_frame":
            angle %= 2 * math.pi
        return SimpleNamespace(ranges=[math.hypot(x, y)], angle_min=angle, angle_increment=0.01,
            range_min=0.05, range_max=12.0, header=SimpleNamespace(frame_id=frame))

    def rear_distance(xy):
        obj = SimpleNamespace(lidar_xy=xy, lidar_d=1.0, p=lambda key: 0.30 if key == "fahrschlauch_breite" else None)
        return methoden["lidar_hinten"](obj)

    cases = []
    for name, frame, point, mode in [
        ("front_corridor_missed", "laser1_frame", (0.30, 0.20), "front"),
        ("front_side_point_counted_as_corridor", "laser1_frame", (0.40, -0.10), "front"),
        ("rear_corridor_missed", "laser0_frame", (-0.30, -0.20), "rear"),
    ]:
        message = msg_for_xy(*point, frame)
        raw = lib.punkte_xy(message, 0.0, 0.08)
        base = raw + np.array(MODELL_XYZ[frame][:2])
        if mode == "front":
            actual = lib.fahrschlauch(raw, None, 0.15, 0.80)
            reference = lib.fahrschlauch(base, None, 0.15, 0.80)
        else:
            actual, reference = rear_distance(raw), rear_distance(base)
        if name == "front_corridor_missed":
            signatur = actual is None and reference is not None
        elif name == "front_side_point_counted_as_corridor":
            signatur = actual is not None and reference is None
        else:
            signatur = actual == 5.0 and reference < 0.5
        cases.append({"case": name, "frame": frame, "synthetic_sensor_xy_m": list(point),
            "historical_xy_m": raw.tolist(), "manufacturer_model_base_xy_m": base.tolist(),
            "historical_result": actual, "result_with_model_translation": reference,
            "historical_signature_match": bool(signatur)})
    print(json.dumps({"product_acceptance": False, "hardware_access": False,
        "mode": "synthetic points; original pure library and AST-extracted Zentrale method",
        "manufacturer_model": {"file": "M3Pro.urdf", "sha256": MODELL_SHA,
            "positions_m": MODELL_XYZ, "independently_surveyed": False},
        "reference_parameters": {"half_width_m": 0.15, "length_m": 0.80, "min_range_m": 0.08},
        "historical_signature_match": all(r["historical_signature_match"] for r in cases),
        "case_count": len(cases), "results": cases}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
