#!/usr/bin/env python3
"""Loopback-only MQTT demo with synthetic panel data and an independent browser receiver."""
import asyncio
import base64
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import threading
import time
from types import SimpleNamespace

from amqtt.broker import Broker
import paho.mqtt.client as mqtt
from panel_bridge import Bridge


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.start = time.monotonic()
        self.source_frames = 0
        self.received_frames = 0
        self.frame_times = deque(maxlen=100)
        self.image = None
        self.values = {}


def make_panel(state, jpeg):
    encoded = base64.b64encode(jpeg).decode('ascii')

    class Panel(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if self.path == '/api/grundbetrieb' or self.path in ('/api/mqtt/depth', '/api/mqtt/scans'):
                self.send_response(204)
                self.end_headers()
                return
            if self.path == '/api/status':
                age = time.monotonic() - state.start
                events = ([{'zeit': 3.0, 'text': 'Synthetischer Test gestartet', 'art': 'info'}]
                          if age >= 3 else [])
                payload = {'roboter': 'RMTEST', 'fahren': False, 'akku': 12.1,
                           'ki': None, 'ereignisse': events, 'simulation': True}
            elif self.path == '/api/mqtt/camera':
                with state.lock:
                    state.source_frames += 1
                    number = state.source_frames
                payload = {'kind': 'camera', 'frame_key': str(number), 'frame_id': 'synthetic',
                           'captured_at': None, 'observed_at': datetime.now(timezone.utc).isoformat(),
                           'encoding': 'jpeg', 'width': 640, 'height': 360, 'data_b64': encoded}
            else:
                self.send_error(404)
                return
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Panel


PAGE = b'''<!doctype html><html lang="de"><meta charset="utf-8"><title>MQTT Testempfaenger</title>
<style>body{font:18px system-ui;max-width:900px;margin:2em auto;padding:0 1em;background:#101820;color:#f5f7fa}
img{max-width:100%;border:2px solid #6ab;min-height:150px}pre{white-space:pre-wrap;background:#263644;padding:1em}</style>
<h1>Lokaler MQTT-Testempfaenger</h1><p>Alle Daten sind synthetisch. Kein Roboter verbunden.</p>
<img id="camera" alt="Synthetisches Testbild"><pre id="status">Warte auf MQTT...</pre>
<script>let frames=0;async function tick(){try{const r=await fetch('/snapshot',{cache:'no-store'});const s=await r.json();
frames=s.received_frames;document.getElementById('status').textContent=JSON.stringify(s,null,2);
}catch(e){document.getElementById('status').textContent=String(e)}}
setInterval(tick,250);setInterval(()=>{if(frames)document.getElementById('camera').src='/camera.jpg?n='+Date.now()},50);tick()</script></html>'''


def make_view(state):
    class View(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            with state.lock:
                if self.path == '/snapshot':
                    body = json.dumps({'source_frames': state.source_frames,
                                       'received_frames': state.received_frames,
                                       'received_fps_2s': sum(t >= time.monotonic() - 2
                                                              for t in state.frame_times) / 2,
                                       'topics': state.values}).encode()
                    content_type = 'application/json'
                elif self.path.split('?')[0] == '/camera.jpg' and state.image is not None:
                    body, content_type = state.image, 'image/jpeg'
                elif self.path == '/':
                    body, content_type = PAGE, 'text/html; charset=utf-8'
                else:
                    self.send_error(404)
                    return
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return View


async def stop_broker(broker):
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
    state = State()
    jpeg = (Path(__file__).resolve().parents[1] / 'docs/bilder/panel_dashboard.jpg').read_bytes()
    broker_port = free_port()
    loop = asyncio.new_event_loop()

    def loop_forever():
        asyncio.set_event_loop(loop)
        loop.run_forever()

    broker_thread = threading.Thread(target=loop_forever, daemon=True)
    broker_thread.start()

    async def start_broker():
        broker = Broker({'listeners': {'default': {'type': 'tcp',
                          'bind': f'127.0.0.1:{broker_port}'}},
                         'plugins': {'amqtt.plugins.authentication.AnonymousAuthPlugin':
                                     {'allow_anonymous': True}}})
        await broker.start()
        return broker

    broker = asyncio.run_coroutine_threadsafe(start_broker(), loop).result(10)
    panel = ThreadingHTTPServer(('127.0.0.1', 0), make_panel(state, jpeg))
    view = ThreadingHTTPServer(('127.0.0.1', 0), make_view(state))
    panel_thread = threading.Thread(target=panel.serve_forever, daemon=True)
    view_thread = threading.Thread(target=view.serve_forever, daemon=True)
    panel_thread.start()
    view_thread.start()

    reader = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='synthetic-demo-reader')
    subscribed = threading.Event()
    reader.on_connect = lambda client, *_: client.subscribe('demo/robots/RMTEST/#', qos=1)
    reader.on_subscribe = lambda *_: subscribed.set()

    def on_message(client, userdata, message):
        suffix = message.topic.removeprefix('demo/robots/RMTEST/')
        if suffix == 'details/camera':
            try:
                image = base64.b64decode(json.loads(message.payload)['payload']['data_b64'], validate=True)
            except (ValueError, KeyError):
                return
            with state.lock:
                state.image = image
                state.received_frames += 1
                state.frame_times.append(time.monotonic())
            return
        if suffix == 'state' and not message.payload:
            with state.lock:
                state.values.pop('state', None)
            return
        try:
            value = json.loads(message.payload)
        except ValueError:
            value = message.payload.decode('utf-8', errors='replace')
        with state.lock:
            state.values[suffix] = value

    reader.on_message = on_message
    bridge = None
    worker = None
    try:
        reader.connect('127.0.0.1', broker_port)
        reader.loop_start()
        if not subscribed.wait(5):
            raise TimeoutError('MQTT demo receiver did not subscribe')
        args = SimpleNamespace(host='127.0.0.1', port=broker_port, robot='RMTEST',
                               base_topic='demo/robots', panel=f'http://127.0.0.1:{panel.server_port}',
                               interval=1.0, camera_hz=20.0, tls=False, ca=None)
        bridge = Bridge(args)
        worker = threading.Thread(target=bridge.run, daemon=True)
        worker.start()
        print(f'Lokaler Testbroker: 127.0.0.1:{broker_port}', flush=True)
        print(f'Testempfaenger: http://127.0.0.1:{view.server_port}/', flush=True)
        print('Nur synthetische Daten. Beenden mit Strg+C.', flush=True)
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        if bridge:
            bridge.stop.set()
        if worker:
            worker.join(5)
        reader.disconnect()
        reader.loop_stop()
        panel.shutdown()
        view.shutdown()
        panel.server_close()
        view.server_close()
        try:
            asyncio.run_coroutine_threadsafe(stop_broker(broker), loop).result(5)
        finally:
            loop.call_soon_threadsafe(loop.stop)
            broker_thread.join(5)
            loop.close()


if __name__ == '__main__':
    main()
