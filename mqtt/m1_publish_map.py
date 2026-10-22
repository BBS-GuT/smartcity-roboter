#!/usr/bin/env python3
"""Publish two independently measured, explicitly aligned local maps."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
from m1_local_map import from_npz  # noqa: E402
from m1_map import align_markers, fuse  # noqa: E402
from m1_map_transport import publish  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map-id', required=True)
    parser.add_argument('--reference-markers', type=Path, required=True,
                        help='JSON: globally named fixed marker IDs to [x_m,y_m]')
    parser.add_argument('--source', nargs=3, action='append', metavar=('ROBOT', 'MAP_NPZ', 'MARKERS_JSON'),
                        required=True, help='repeat for at least two robots')
    parser.add_argument('--host', default=os.getenv('MQTT_HOST', '127.0.0.1'))
    parser.add_argument('--port', type=int, default=int(os.getenv('MQTT_PORT', '1883')))
    args = parser.parse_args()
    if len(args.source) < 2:
        parser.error('at least two robot sources required')
    reference = json.loads(args.reference_markers.read_text(encoding='utf-8'))
    maps = []
    for robot, path, markers_path in args.source:
        markers = json.loads(Path(markers_path).read_text(encoding='utf-8'))
        alignment = align_markers(markers, reference)
        maps.append(from_npz(path, robot=robot, alignment=alignment))
    result = fuse(maps, map_id=args.map_id, reference_markers=reference)
    import paho.mqtt.client as mqtt
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if os.getenv('MQTT_USERNAME'):
        client.username_pw_set(os.environ['MQTT_USERNAME'], os.getenv('MQTT_PASSWORD'))
    client.connect(args.host, args.port, keepalive=30)
    client.loop_start()
    try:
        pointer = publish(client, result)
    finally:
        client.disconnect()
        client.loop_stop()
    print(json.dumps({'pointer': pointer, 'quality': result['quality']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
