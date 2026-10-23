#!/usr/bin/env python3
"""Read-only panel -> MQTT adapter. No ROS imports and no movement commands."""
import argparse
from collections import deque
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import threading
import time
import urllib.request
import uuid
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
import grundbetrieb_vertrag  # noqa: E402


def finite_json(value):
    """Panel occasionally contains non-finite sensor values; mark these unavailable."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: finite_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [finite_json(item) for item in value]
    return value


def read_panel(url, limit=1048576):
    with urllib.request.urlopen(url.rstrip('/') + '/api/status', timeout=2) as response:
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Panel status exceeds size limit')
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError('Panel status must be a JSON object')
    return finite_json(data)


def read_detail(url, kind, limit=3145728):
    with urllib.request.urlopen(url.rstrip('/') + '/api/mqtt/' + kind, timeout=1) as response:
        if response.status == 204:
            return None
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Panel detail exceeds size limit')
    data = json.loads(raw)
    if not isinstance(data, (dict, list)):
        raise ValueError('Panel detail must be an object or list')
    return data


def read_common_state(url, limit=1048576):
    with urllib.request.urlopen(url.rstrip('/') + '/api/grundbetrieb', timeout=1) as response:
        if response.status == 204:
            return None
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Common state exceeds size limit')
    state = grundbetrieb_vertrag.lade_json(raw)
    age = time.monotonic() - state['generated_mono_s']
    if age < -1 or age > 2:
        raise ValueError('Common state is not fresh')
    return state


class Bridge:
    def __init__(self, args):
        import paho.mqtt.client as mqtt
        self.args = args
        self.boot = uuid.uuid4().hex
        self.seq = 0
        self.connected = threading.Event()
        self.connection_lost = threading.Event()
        self.stop = threading.Event()
        self.base = args.base_topic.rstrip('/') + '/' + args.robot
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id='panel-' + args.robot + '-' + self.boot[:12])
        self.client.max_inflight_messages_set(1)
        self.client.max_queued_messages_set(1)
        self.client.reconnect_delay_set(1, 10)
        if os.getenv('MQTT_USERNAME'):
            self.client.username_pw_set(os.environ['MQTT_USERNAME'], os.getenv('MQTT_PASSWORD'))
        if args.tls:
            self.client.tls_set(ca_certs=args.ca)
        self.client.will_set(self.base + '/availability', 'offline', qos=1, retain=True)
        self.client.on_connect = self._connected
        self.client.on_connect_fail = self._connect_failed
        self.client.on_disconnect = self._disconnected
        self.last_ack = None
        self.errors = 0
        self.detail_seq = 0
        self.detail_lock = threading.Lock()
        self.detail_stop = threading.Event()
        self.last_camera_key = None
        self.last_detail_errors = {}
        self.canonical_ack = None
        self.canonical_seen = None
        self.info_canonical = None
        self.events_seen = set()
        self.events_order = deque(maxlen=256)
        self.events_initialized = False
        self.dropped_messages = 0
        self.reconnects = getattr(args, 'reconnects', 0)
        self.last_error = None
        self.status_lock = threading.Lock()
        self.status_file = Path(os.getenv('SMARTCITY_MQTT_STATUS_FILE',
                                        str(Path(__file__).resolve().parents[1] / 'logs/mqtt-status.json')))

    def _connected(self, client, userdata, flags, reason, properties):
        if reason == 0:
            self.connected.set()
            self.last_error = None
            self.write_status()
        else:
            self.errors += 1
            self.last_error = 'connection rejected'
            print('MQTT connection rejected:', reason, flush=True)
            self.connection_lost.set()
            self.write_status()

    def _connect_failed(self, client, userdata):
        self.errors += 1
        self.last_error = 'TCP connection failed'
        print('MQTT TCP connection failed; check broker/network access', flush=True)
        self.connection_lost.set()
        self.write_status()

    def _disconnected(self, client, userdata, flags, reason, properties):
        self.connected.clear()
        self.connection_lost.set()
        self.last_error = 'disconnected'
        self.write_status()

    def send(self, suffix, payload, retain=True):
        result = self.client.publish(self.base + '/' + suffix, payload, qos=1, retain=retain)
        result.wait_for_publish(timeout=3)
        if not result.is_published():
            raise TimeoutError('MQTT PUBACK missing')

    def write_status(self):
        with self.status_lock:
            state = {'broker': 'connected' if self.connected.is_set() else 'disconnected',
                     'target': os.getenv('SMARTCITY_MQTT_TARGET', 'configured'),
                     'last_panel_ack_seq': self.last_ack,
                     'last_common_ack_seq': self.canonical_ack,
                     'reconnects': self.reconnects, 'dropped_messages': self.dropped_messages,
                     'last_error': self.last_error}
            try:
                self.status_file.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.status_file.with_name(self.status_file.name + '.' + self.boot + '.tmp')
                temporary.write_text(json.dumps(state), encoding='utf-8')
                os.replace(temporary, self.status_file)
            except OSError:
                pass

    def send_info(self, common_available):
        if self.info_canonical == common_available:
            return
        info = {'robot_id': self.args.robot, 'boot_id': self.boot,
                'transport_schema': 'panel-info/1',
                'software_version': os.getenv('SMARTCITY_SOFTWARE_VERSION') or None,
                'map_version': None, 'config_version': None,
                'common_state_available': common_available,
                'common_state_schema': 'grundbetrieb-v1' if common_available else None,
                'channels': ['panel/state', 'availability', 'info', 'events', 'communication',
                             'details/camera', 'details/depth', 'details/scan0', 'details/scan1']
                            + (['state'] if common_available else [])}
        self.send('info', json.dumps(info, allow_nan=False))
        self.info_canonical = common_available

    def send_events(self, events):
        if not isinstance(events, list):
            return
        prepared = []
        for event in reversed(events):
            if not isinstance(event, dict):
                continue
            text_value = event.get('text')
            if not isinstance(text_value, str) or not text_value:
                continue
            source = {'zeit': event.get('zeit'), 'text': text_value, 'art': event.get('art')}
            event_id = hashlib.sha256(json.dumps(source, sort_keys=True, default=str).encode()).hexdigest()[:24]
            prepared.append((event_id, source))
        if not self.events_initialized:
            self.events_initialized = True
            for event_id, _ in prepared:
                self.remember_event(event_id)
            return
        for event_id, source in prepared:
            if event_id in self.events_seen:
                continue
            message = {'transport_schema': 'panel-event/1', 'robot_id': self.args.robot,
                       'boot_id': self.boot, 'event_id': event_id, 'state_ack_seq': self.last_ack,
                       'received_at': datetime.now(timezone.utc).isoformat(),
                       'source': 'panel/api/status.ereignisse', 'payload': source}
            self.send('events', json.dumps(message, allow_nan=False), retain=False)
            self.remember_event(event_id)

    def remember_event(self, event_id):
        if len(self.events_order) == self.events_order.maxlen:
            self.events_seen.discard(self.events_order.popleft())
        self.events_order.append(event_id)
        self.events_seen.add(event_id)

    def send_common_state(self, state):
        if state is None:
            return False
        if state['robot_id'] != self.args.robot:
            raise ValueError('Common state robot identity does not match --robot')
        marker = (state['boot_id'], state['seq'])
        if marker == self.canonical_seen:
            return True
        if self.canonical_seen and marker[0] == self.canonical_seen[0] and marker[1] < self.canonical_seen[1]:
            raise ValueError('Common state sequence went backwards')
        self.send('state', grundbetrieb_vertrag.als_json(state))
        self.canonical_seen = marker
        self.canonical_ack = marker[1]
        self.write_status()
        return True

    def send_communication(self):
        message = {'transport_schema': 'panel-communication/1', 'robot_id': self.args.robot,
                   'boot_id': self.boot, 'broker': 'connected',
                   'panel_ack_seq': self.last_ack, 'common_ack_seq': self.canonical_ack,
                   'reconnects': self.reconnects, 'dropped_messages': self.dropped_messages,
                   'last_error': self.last_error,
                   'received_at': datetime.now(timezone.utc).isoformat()}
        self.send('communication', json.dumps(message, allow_nan=False), retain=False)

    def send_detail(self, suffix, data):
        if not self.connected.is_set() or self.connection_lost.is_set():
            return
        with self.detail_lock:
            message = {'transport_schema': 'panel-detail/1', 'robot_id': self.args.robot,
                       'boot_id': self.boot, 'detail_seq': self.detail_seq,
                       'state_ack_seq': self.last_ack,
                       'received_at': datetime.now(timezone.utc).isoformat(),
                       'source': 'panel/api/mqtt/' + data['kind'], 'payload': data}
            encoded = json.dumps(message, allow_nan=False, separators=(',', ':'))
            result = self.client.publish(self.base + '/details/' + suffix, encoded,
                                         qos=0, retain=False)
            result.wait_for_publish(timeout=0.25)
            if not result.is_published():
                raise TimeoutError('MQTT detail send timed out')
            self.detail_seq += 1

    def detail_error(self, kind, error):
        name = type(error).__name__
        if isinstance(error, TimeoutError):
            self.dropped_messages += 1
            self.write_status()
        if self.last_detail_errors.get(kind) != name:
            print('MQTT ' + kind + ' detail failed: ' + name, flush=True)
            self.last_detail_errors[kind] = name

    def camera_loop(self):
        rate = getattr(self.args, 'camera_hz', 20.0)
        if rate <= 0:
            return
        while not self.detail_stop.is_set() and not self.stop.is_set():
            started = time.monotonic()
            if self.last_ack is not None and self.connected.is_set():
                try:
                    data = read_detail(self.args.panel, 'camera')
                    if data and data['kind'] == 'camera' and data['frame_key'] != self.last_camera_key:
                        self.send_detail('camera', data)
                        self.last_camera_key = data['frame_key']
                        self.last_detail_errors.pop('camera', None)
                except Exception as error:
                    self.detail_error('camera', error)
            self.detail_stop.wait(max(0, 1 / rate - (time.monotonic() - started)))

    def send_slow_details(self):
        for kind in ('depth', 'scans'):
            try:
                data = read_detail(self.args.panel, kind)
                if kind == 'depth' and data and data['kind'] == 'depth':
                    self.send_detail('depth', data)
                elif kind == 'scans' and isinstance(data, list):
                    for scan in data:
                        if scan['kind'] == 'scan':
                            self.send_detail('scan' + str(scan['index']), scan)
                self.last_detail_errors.pop(kind, None)
            except Exception as error:
                self.detail_error(kind, error)

    def run(self):
        self.write_status()
        self.client.connect_async(self.args.host, self.args.port, keepalive=15)
        self.client.loop_start()
        connect_deadline = time.monotonic() + 10
        camera_worker = threading.Thread(target=self.camera_loop, daemon=True)
        camera_worker.start()
        try:
            while not self.stop.is_set():
                if self.connection_lost.is_set():
                    break
                if not self.connected.wait(0.2):
                    if time.monotonic() >= connect_deadline:
                        self.errors += 1
                        print('MQTT CONNACK timeout; check broker/authentication', flush=True)
                        break
                    continue
                try:
                    # Fetch after connecting: never build up historical panel samples offline.
                    data = read_panel(self.args.panel)
                    identity = str(data.get('roboter', '')).strip()
                    if identity and identity != self.args.robot:
                        raise ValueError('Panel robot identity does not match --robot')
                    message = {'transport_schema': 'panel-telemetry/1', 'robot_id': self.args.robot,
                               'boot_id': self.boot, 'seq': self.seq,
                               'received_at': datetime.now(timezone.utc).isoformat(),
                               'source': 'panel/api/status', 'payload': data,
                               'last_broker_ack_seq': self.last_ack}
                    encoded = json.dumps(message, allow_nan=False, separators=(',', ':'))
                    self.send('panel/state', encoded)
                    self.last_ack = self.seq
                    self.seq += 1
                    self.write_status()
                    # Online means both panel acquisition AND broker delivery succeeded.
                    self.send('availability', 'online')
                    try:
                        common = read_common_state(self.args.panel)
                        common_available = self.send_common_state(common)
                        self.last_detail_errors.pop('common_state', None)
                    except TimeoutError:
                        raise
                    except Exception as error:
                        common_available = False
                        self.detail_error('common_state', error)
                    if not common_available and self.info_canonical is not False:
                        # Delete a retained authoritative state if its producer is absent.
                        self.send('state', '')
                        self.canonical_seen = None
                        self.canonical_ack = None
                        self.write_status()
                    self.send_info(common_available)
                    self.send_events(data.get('ereignisse'))
                    self.send_communication()
                    print('MQTT PUBACK seq=' + str(self.last_ack), flush=True)
                    self.send_slow_details()
                except Exception as error:
                    self.errors += 1
                    self.last_error = type(error).__name__
                    self.write_status()
                    # Never log payload, credentials or exception URL contents.
                    print('MQTT/panel sample failed: ' + type(error).__name__, flush=True)
                    if self.connected.is_set():
                        try:
                            self.send('availability', 'offline')
                        except Exception:
                            pass
                    # Discard paho's pending retry sample before reconnecting. Fresh data only.
                    self.client.disconnect()
                    self.client.loop_stop()
                    break
                self.stop.wait(self.args.interval)
        finally:
            self.detail_stop.set()
            camera_worker.join(timeout=2)
            if self.connected.is_set():
                try:
                    self.send('availability', 'offline')
                except Exception:
                    pass
            self.client.disconnect()
            self.client.loop_stop()


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default=os.getenv('MQTT_HOST', '10.0.40.100'))
    parser.add_argument('--port', type=int, default=int(os.getenv('MQTT_PORT', '1883')))
    parser.add_argument('--robot', default=os.getenv('SMARTCITY_ROBOT_ID'))
    parser.add_argument('--panel', default=os.getenv('SMARTCITY_PANEL_URL', 'http://127.0.0.1:8080'))
    parser.add_argument('--base-topic', default='smartcity/robots')
    parser.add_argument('--interval', type=float, default=1.0)
    parser.add_argument('--camera-hz', type=float, default=20.0,
                        help='Best-effort JPEG frames per second (0 disables camera)')
    parser.add_argument('--tls', action='store_true')
    parser.add_argument('--ca')
    args = parser.parse_args()
    if not args.robot:
        try:
            args.robot = Path.home().joinpath('roboter_name').read_text().strip()
        except OSError:
            pass
    if args.robot not in ('RM01', 'RM02', 'RM03', 'RM04', 'RMTEST'):
        parser.error('--robot RM01..RM04 (or synthetic RMTEST) required')
    if not math.isfinite(args.interval) or args.interval < 0.2:
        parser.error('--interval must be finite and >= 0.2')
    if not math.isfinite(args.camera_hz) or not 0 <= args.camera_hz <= 20:
        parser.error('--camera-hz must be finite and between 0 and 20')
    if not 1 <= args.port <= 65535:
        parser.error('invalid port')
    return args


def main():
    args = arguments()
    stopped = threading.Event()
    current = [None]
    def stop(*_):
        stopped.set()
        if current[0]:
            current[0].stop.set()
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    while not stopped.is_set():
        # New client discards old in-flight packets after any source/transport failure.
        args.reconnects = getattr(args, 'reconnects', -1) + 1
        current[0] = Bridge(args)
        current[0].run()
        stopped.wait(1)


if __name__ == '__main__':
    main()

