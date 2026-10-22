#!/usr/bin/env python3
"""Prefer the project broker; keep local MQTT available during outages."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / 'logs/mqtt-status.json'
CONFIG = Path.home() / '.config/smartcity/mqtt.json'


def settings():
    values = {}
    if CONFIG.is_file():
        values = json.loads(CONFIG.read_text(encoding='utf-8'))
        if not isinstance(values, dict):
            raise ValueError('MQTT config must be an object')
    def get(name, default):
        return os.environ.get(name, values.get(name, default))
    return {'host': str(get('MQTT_HOST', '10.0.10.11')),
            'port': int(get('MQTT_PORT', 1883)),
            'username': get('MQTT_USERNAME', None),
            'password': get('MQTT_PASSWORD', None)}


def project_available(config, timeout=3):
    """Require a successful MQTT CONNACK, not just an open TCP port."""
    import paho.mqtt.client as mqtt
    ready = threading.Event()
    accepted = [False]
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id='panel-probe-' + uuid.uuid4().hex[:12],
                         reconnect_on_failure=False)
    client.connect_timeout = timeout
    if config['username']:
        client.username_pw_set(str(config['username']), config['password'])
    def connected(_client, _userdata, _flags, reason, _properties):
        accepted[0] = not reason.is_failure
        ready.set()
    client.on_connect = connected
    try:
        client.connect(config['host'], config['port'], keepalive=10)
        client.loop_start()
        ready.wait(timeout)
        return accepted[0]
    except (OSError, ValueError):
        return False
    finally:
        try:
            client.disconnect()
            client.loop_stop()
        except (OSError, RuntimeError):
            pass


def tcp_open(host='127.0.0.1', port=1883):
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def stop_child(child):
    if child is None or child.poll() is not None:
        return
    child.send_signal(signal.SIGINT)
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=2)


def broker_status():
    try:
        if time.time() - STATUS.stat().st_mtime > 5:
            return 'stale'
        return json.loads(STATUS.read_text(encoding='utf-8')).get('broker')
    except (OSError, ValueError):
        return 'unknown'


def run():
    config = settings()
    if not 1 <= config['port'] <= 65535:
        raise ValueError('MQTT_PORT out of range')
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    local = None
    bridge = None
    mode = None
    started = 0.0
    next_probe = 0.0
    try:
        while not stop.is_set():
            now = time.monotonic()
            if mode is None or now >= next_probe:
                primary = project_available(config)
                next_probe = time.monotonic() + 30
            else:
                primary = mode == 'project'
            desired = 'project' if primary else 'local'
            if mode == 'project' and now - started > 10 and broker_status() != 'connected':
                desired = 'local'
            if bridge is not None and bridge.poll() is not None:
                desired = None
            if desired != mode or bridge is None or bridge.poll() is not None:
                stop_child(bridge)
                bridge = None
                if desired is None:
                    mode = None
                    stop.wait(2)
                    continue
                if desired == 'local' and not tcp_open():
                    local = subprocess.Popen([sys.executable, str(ROOT / 'mqtt/local_broker.py')],
                                             cwd=ROOT)
                    for _ in range(20):
                        if tcp_open() or local.poll() is not None:
                            break
                        if stop.wait(0.1):
                            break
                if desired == 'local' and not tcp_open():
                    print('Local MQTT broker unavailable', flush=True)
                    mode = None
                    stop.wait(5)
                    continue
                env = os.environ.copy()
                if desired == 'project':
                    env.update(MQTT_USERNAME=str(config['username'] or ''),
                               MQTT_PASSWORD=str(config['password'] or ''))
                    host, port = config['host'], config['port']
                else:
                    env.pop('MQTT_USERNAME', None)
                    env.pop('MQTT_PASSWORD', None)
                    host, port = '127.0.0.1', 1883
                env['SMARTCITY_MQTT_TARGET'] = desired
                print('MQTT target: ' + desired + ' (' + host + ':' + str(port) + ')', flush=True)
                bridge = subprocess.Popen([sys.executable, str(ROOT / 'mqtt/panel_bridge.py'),
                                           '--host', host, '--port', str(port), '--camera-hz', '0'],
                                          cwd=ROOT, env=env)
                mode, started = desired, time.monotonic()
            stop.wait(2)
    finally:
        stop_child(bridge)
        stop_child(local)


if __name__ == '__main__':
    run()
