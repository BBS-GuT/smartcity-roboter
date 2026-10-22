"""Two independent MQTT clients with one local broker; no ROS hardware."""
import asyncio
import json
import socket
import threading
import time
import uuid

from amqtt.broker import Broker
import paho.mqtt.client as mqtt

from m1_map_transport import publish, verify_package
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
from m1_protocol import Inbox, envelope
from m1_map import fuse
from m1_routes import choose


def free_port():
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


async def main():
    port = free_port()
    broker = Broker({'listeners': {'default': {'type': 'tcp', 'bind': f'127.0.0.1:{port}'}},
                     'plugins': {'amqtt.plugins.authentication.AnonymousAuthPlugin': {'allow_anonymous': True}}})
    await broker.start()
    received = []
    clients = []
    try:
        for robot in ('RM01', 'RM02'):
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='m1-' + robot + uuid.uuid4().hex[:8])
            if robot == 'RM02':
                client.on_message = lambda _c, _u, msg: received.append((msg.topic, msg.payload))
            client.connect('127.0.0.1', port)
            client.loop_start()
            clients.append(client)
        clients[1].subscribe('smartcity/m1/robots/RM01/intention', qos=1)
        clients[1].subscribe('smartcity/map/shared/#', qos=1)
        await asyncio.sleep(.2)
        now = time.time()
        intention = envelope('RM01', uuid.uuid4().hex, 1, 'intention', 'city', 1,
                             {'current_section': 'A', 'next_section': 'B'}, now=now)
        ack = clients[0].publish('smartcity/m1/robots/RM01/intention', json.dumps(intention), qos=1)
        await asyncio.to_thread(ack.wait_for_publish, 5)
        for _ in range(30):
            if received: break
            await asyncio.sleep(.05)
        inbox = Inbox()
        item = inbox.accept(received[0][1], topic_robot='RM01',
                            authenticated_robot='RM01', now=time.time())
        peer = {'robot': 'RM01', 'current_section': item['data']['current_section'],
                'next_section': item['data']['next_section'], 'map_id': 'city',
                'map_version': 1, 'observed_at': time.time()}
        assert choose(['B', 'C'], 'RM02', 'A', [peer], 'B', map_id='city', map_version=1) == 'C'
        assert choose(['B', 'C'], 'RM02', 'A', [peer], 'B', map_id='city', map_version=1,
                      now=time.time()+4) == 'B'
        base = {'resolution_m': .02, 'quality': 'verified',
                'alignment': {'x_m': 0, 'y_m': 0, 'yaw_rad': 0, 'max_error_m': 0},
                'cells': [{'ix': 0, 'iy': 0, 'occupancy': 50}]}
        merged = fuse([dict(base, robot=r) for r in ('RM01', 'RM02')], map_id='city')
        pointer = await asyncio.to_thread(publish, clients[0], merged)
        for _ in range(30):
            if any(topic.endswith('/current') for topic, _ in received): break
            await asyncio.sleep(.05)
        actual = json.loads(next(payload for topic, payload in received if topic.endswith('/current')))
        assert actual == pointer
        prefix = f"smartcity/map/shared/{pointer['map_id']}/{pointer['version']}"
        def artifact(name):
            topic = f'{prefix}/{name}'
            count = int(next(payload for path, payload in received if path == topic + '/chunks'))
            return b''.join(next(payload for path, payload in received if path == f'{topic}/{i}')
                            for i in range(count))
        manifest = artifact('manifest.json')
        files = {name: artifact(name) for name in ('occupancy.png', 'map.json')}
        assert verify_package(actual, manifest, files)['version'] == merged['version']
        print('PASS two MQTT clients: intention, conflict, stale fallback, verified complete map')
    finally:
        for client in clients:
            client.disconnect()
            client.loop_stop()
        await asyncio.sleep(.2)
        await broker.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
