"""Local credential checks against a real broker; no project network or hardware."""
import asyncio
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

from amqtt.broker import Broker
from passlib.apps import custom_app_context
import paho.mqtt.client as mqtt
from panel_bridge import Bridge


async def shutdown_fixture(broker):
    for server in broker._servers.values():
        await server.close_instance()
    if not broker._broadcast_shutdown_waiter.done():
        broker._broadcast_shutdown_waiter.set_result(True)
    await asyncio.gather(broker._broadcast_task, return_exceptions=True)
    tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


def main():
    root = Path(__file__).resolve().parent
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    username, password = 'synthetic-check', secrets.token_hex(16)
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    with tempfile.TemporaryDirectory(prefix='mqtt-auth-') as tmp:
        password_file = Path(tmp) / 'users'
        # Fixture-only credentials: keep pure-Python verification fast on Windows.
        password_file.write_text(username + ':' + custom_app_context.hash(password, rounds=2000) + '\n')

        async def start():
            broker = Broker({
                'listeners': {'default': {'type': 'tcp', 'bind': f'127.0.0.1:{port}'}},
                'plugins': {
                    'amqtt.plugins.authentication.AnonymousAuthPlugin': {'allow_anonymous': False},
                    'amqtt.plugins.authentication.FileAuthPlugin': {'password_file': str(password_file)},
                },
            })
            await broker.start()
            return broker

        broker = None
        try:
            broker = asyncio.run_coroutine_threadsafe(start(), loop).result(10)
            for label, supplied, expected in (
                ('valid credentials and independent transfer', password, 0),
                ('wrong password rejected', 'invalid-' + password, 2),
                ('anonymous connection rejected', None, 2),
            ):
                env = os.environ.copy()
                env.pop('MQTT_USERNAME', None)
                env.pop('MQTT_PASSWORD', None)
                if supplied is not None:
                    env.update(MQTT_USERNAME=username, MQTT_PASSWORD=supplied)
                result = subprocess.run(
                    [sys.executable, str(root / 'check_broker.py'), '--host', '127.0.0.1',
                     '--port', str(port), '--timeout', '2'],
                    env=env, capture_output=True, text=True, timeout=15,
                )
                assert result.returncode == expected, (label, result.returncode, result.stdout, result.stderr)
                assert password not in result.stdout + result.stderr
                print('PASS', label, flush=True)

            args = SimpleNamespace(host='127.0.0.1', port=port, robot='RMTEST',
                                   base_topic='auth-review/' + secrets.token_hex(8),
                                   panel='http://synthetic.invalid', interval=.2, tls=False, ca=None)
            sample = {'roboter': 'RMTEST', 'fahren': False, 'akku': 12.1,
                      'ki': None, 'sensoren': {'scan': [None, 0.4, 2.3]},
                      'position': {'x': 1.25, 'y': -0.5}, 'ereignisse': ['synthetischer Test']}
            received = []
            subscribed = threading.Event()
            base = args.base_topic + '/RMTEST'
            reader = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                 client_id='bridge-observer-' + secrets.token_hex(6))
            reader.username_pw_set(username, password)
            reader.on_connect = lambda c, u, f, r, p: c.subscribe(base + '/#', qos=1)
            reader.on_subscribe = lambda c, u, mid, reasons, p: subscribed.set()
            reader.on_message = lambda c, u, msg: received.append((msg.topic, msg.payload, msg.retain))
            reader.connect('127.0.0.1', port)
            reader.loop_start()

            def wait_for(predicate):
                deadline = time.monotonic() + 5
                while not predicate():
                    if time.monotonic() >= deadline:
                        raise AssertionError('Independent telemetry observer timed out')
                    time.sleep(.02)

            with patch.dict(os.environ, MQTT_USERNAME=username, MQTT_PASSWORD=password), \
                    patch('panel_bridge.read_panel', return_value=sample):
                bridge = Bridge(args)
                worker = threading.Thread(target=bridge.run, daemon=True)
                try:
                    assert subscribed.wait(5), 'Observer subscription not acknowledged'
                    worker.start()
                    wait_for(lambda: len([1 for t, p, r in received if t == base + '/panel/state']) >= 3)
                    wait_for(lambda: any(t == base + '/availability' and p == b'online' for t, p, r in received))
                    states = [json.loads(p) for t, p, r in received if t == base + '/panel/state']
                    for state in states:
                        assert state['payload'] == sample, 'Telemetry payload differs from source'
                        assert state['robot_id'] == 'RMTEST'
                        assert state['boot_id'] == bridge.boot
                        assert state['transport_schema'] == 'panel-telemetry/1'
                        assert state['source'] == 'panel/api/status'
                        assert state['received_at']
                    assert [s['seq'] for s in states] == list(range(len(states)))
                    assert states[0]['last_broker_ack_seq'] is None
                    assert all(s['last_broker_ack_seq'] == s['seq'] - 1 for s in states[1:])
                    print('PASS independent telemetry observer: 3 complete samples match source, identity, sequence and ACK', flush=True)
                finally:
                    bridge.stop.set()
                    if worker.ident is not None:
                        worker.join(8)
                    try:
                        if worker.ident is not None and not worker.is_alive():
                            wait_for(lambda: any(t == base + '/availability' and p == b'offline' for t, p, r in received))
                    finally:
                        reader.disconnect()
                        reader.loop_stop()
                assert not worker.is_alive(), 'Bridge did not stop'
                assert bridge.errors == 0, bridge.errors
                print('PASS authenticated telemetry bridge: online, offline and cooperative shutdown', flush=True)

            # The common state comes from a separate, validated producer. Its
            # sample fixture is synthetic; no motor or ROS process is started.
            import json as json_module
            fixture = json_module.loads((root.parent / 'tests/fixtures/grundbetrieb/stillstand.json').read_text())
            current = [fixture]
            panel_status = {'roboter': 'RM02', 'fahren': False,
                            'ereignisse': [{'zeit': 1.0, 'text': 'existing', 'art': 'info'}]}
            args.robot = 'RM02'
            args.base_topic = 'auth-contract/' + secrets.token_hex(8)
            args.camera_hz = 0
            base = args.base_topic + '/RM02'
            messages = []
            subscribed.clear()
            reader = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                 client_id='contract-observer-' + secrets.token_hex(6))
            reader.username_pw_set(username, password)
            reader.on_connect = lambda c, u, f, r, p: c.subscribe(base + '/#', qos=1)
            reader.on_subscribe = lambda c, u, mid, reasons, p: subscribed.set()
            reader.on_message = lambda c, u, msg: messages.append((msg.topic, msg.payload, msg.retain))
            reader.connect('127.0.0.1', port)
            reader.loop_start()
            with patch.dict(os.environ, MQTT_USERNAME=username, MQTT_PASSWORD=password), \
                    patch('panel_bridge.read_panel', side_effect=lambda url: dict(panel_status)), \
                    patch('panel_bridge.read_common_state', side_effect=lambda url: current[0]), \
                    patch('panel_bridge.read_detail', return_value=None):
                bridge = Bridge(args)
                worker = threading.Thread(target=bridge.run, daemon=True)
                try:
                    assert subscribed.wait(5), 'Contract observer subscription not acknowledged'
                    worker.start()
                    wait_for(lambda: all(any(t == base + '/' + suffix for t, p, r in messages)
                                         for suffix in ('state', 'info', 'communication')))
                    published = [p for t, p, r in messages if t == base + '/state' and p]
                    assert published and json_module.loads(published[0]) == fixture
                    assert not [p for t, p, r in messages if t == base + '/events']
                    panel_status['ereignisse'].insert(0, {'zeit': 2.0, 'text': 'new synthetic stop', 'art': 'stopp'})
                    wait_for(lambda: any(t == base + '/events' for t, p, r in messages))
                    events = [json_module.loads(p) for t, p, r in messages if t == base + '/events']
                    assert len(events) == 1 and events[0]['payload']['text'] == 'new synthetic stop'
                    assert not any(r for t, p, r in messages if t == base + '/events')
                    current[0] = None
                    wait_for(lambda: any(t == base + '/state' and p == b'' for t, p, r in messages))
                    wait_for(lambda: any(t == base + '/info' and not json_module.loads(p)['common_state_available']
                                         for t, p, r in messages))
                    assert bridge.errors == 0, bridge.errors
                    print('PASS common state, info, one new event, communication and stale retained-state removal', flush=True)
                finally:
                    bridge.stop.set()
                    if worker.ident is not None:
                        worker.join(8)
                    reader.disconnect()
                    reader.loop_stop()
                assert not worker.is_alive()
        finally:
            try:
                if broker is not None:
                    asyncio.run_coroutine_threadsafe(shutdown_fixture(broker), loop).result(5)
            finally:
                loop.call_soon_threadsafe(loop.stop)
                thread.join(5)
                if thread.is_alive():
                    raise RuntimeError('Test broker thread did not stop')
                loop.close()


if __name__ == '__main__':
    main()
