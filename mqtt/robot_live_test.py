#!/usr/bin/env python3
"""Temporary, read-only robot -> local MQTT broker -> browser test.

Run on the robot with system Python. Starts no driving, KI or arm process.
"""
import asyncio
import base64
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit
import urllib.request


REPO = Path.home() / 'smartcity-roboter'
VIEWER_PORT = 8766
BATTERY_PROBE = '''import json
import math
from pathlib import Path
import re
import tempfile
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rosidl_runtime_py.utilities import get_message

output = Path.home() / 'smartcity-roboter/logs/mqtt-live-battery-probe.json'

def save(data):
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output.parent,
                                     prefix=output.name + '.', suffix='.tmp', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(json.dumps(data, allow_nan=False))
        except BaseException:
            stream.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        for attempt in range(8):
            try:
                temporary.replace(output)
                break
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(0.02)
    finally:
        temporary.unlink(missing_ok=True)

class Probe(Node):
    def __init__(self):
        super().__init__('smartcity_mqtt_battery_probe')
        self.battery_subscriptions = {}
        self.candidates = []
        self.voltage = None
        self.source_topic = None
        self.source_type = None
        self.observed_at = None
        self.create_timer(2.0, self.discover)
        self.discover()

    def discover(self):
        try:
            topics = self.get_topic_names_and_types()
            self.candidates = sorted(name for name, _ in topics
                                     if re.search(r'battery|voltage|volt|vbat', name, re.I))
            for name, types in topics:
                if name not in self.candidates or name in self.battery_subscriptions or not types:
                    continue
                try:
                    message_type = get_message(types[0])
                    self.battery_subscriptions[name] = self.create_subscription(
                        message_type, name, lambda msg, n=name, t=types[0]: self.receive(msg, n, t),
                        qos_profile_sensor_data)
                except Exception:
                    continue
            self.publish_status()
        except Exception:
            pass

    def receive(self, message, name, message_type):
        for field in ('voltage', 'battery_voltage', 'battery_v', 'vbat', 'data'):
            value = getattr(message, field, None)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                voltage = float(value)
                # The robot uses a three-cell pack. Reject percent, zero and unknown values.
                if math.isfinite(voltage) and 7.0 <= voltage <= 16.8:
                    self.voltage = voltage
                    self.source_topic = name
                    self.source_type = message_type
                    self.observed_at = time.time()
                    self.publish_status()
                    return

    def publish_status(self):
        save({'voltage_v': self.voltage, 'source_topic': self.source_topic,
              'source_type': self.source_type, 'observed_at_unix': self.observed_at,
              'candidate_topics': self.candidates})

rclpy.init()
node = Probe()
try:
    rclpy.spin(node)
finally:
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
'''
VIEW_HTML = '''<!doctype html><html lang="de"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SmartCity MQTT Empfang</title><style>
:root{color-scheme:dark}*{box-sizing:border-box}
body{font:16px system-ui;margin:0;background:#0e1721;color:#eaf2f7}
main{max-width:1180px;margin:auto;padding:24px}
h1{font-size:1.65rem;margin:0 0 5px}h2{font-size:1.1rem;margin:0 0 12px}
p{color:#afc3d1;margin:0 0 18px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.card,.panel{background:#1b2b39;border:1px solid #335063;border-radius:12px;padding:16px}
.label{color:#acc3d0;font-size:.87rem}.value{font-size:1.75rem;font-weight:700;margin-top:8px;overflow-wrap:anywhere}
.hint{color:#9cb3c1;font-size:.82rem;margin-top:5px}.sections{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(310px,.75fr);gap:16px;margin-top:16px}
img{width:100%;min-height:180px;background:#101d29;border-radius:8px;object-fit:contain}
table{width:100%;border-collapse:collapse}td,th{text-align:left;border-bottom:1px solid #335063;padding:9px 5px;vertical-align:top}
th{color:#acc3d0;font-size:.85rem}td{font-size:.9rem;overflow-wrap:anywhere}
.panel{margin-top:16px;overflow:auto}.sections .panel{margin-top:0}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.78rem;color:#c4d8e4}
summary{cursor:pointer;font-weight:600}small{color:#a9bfcc}
@media(max-width:760px){.sections{grid-template-columns:1fr}main{padding:14px}.value{font-size:1.4rem}}
</style><main>
<h1>SmartCity MQTT Empfang · RM04</h1>
<p>Lesender Stillstandstest ohne Fahrbefehle. Angaben stammen aus empfangenen MQTT-Nachrichten.</p>
<section class="panel" aria-live="polite"><h2>Fehlende Voraussetzungen</h2><p id="board-diagnosis"></p><table><thead><tr><th>Punkt</th><th>Befund / Voraussetzung</th></tr></thead><tbody id="gaps"></tbody></table></section>
<div class="grid">
<div class="card"><div class="label">Broker</div><div class="value" id="broker">Warte …</div><div class="hint" id="updated">Noch keine Daten</div></div>
<div class="card"><div class="label">Akku-Spannung</div><div class="value" id="battery">—</div><div class="hint" id="battery-source">Warte auf Messwert</div></div>
<div class="card"><div class="label">Akku-Anzeige</div><div class="value" id="battery-percent">—</div><div class="hint">Schätzung aus der Spannung, keine Ladezustandsmessung</div></div>
<div class="card"><div class="label">Geschwindigkeit</div><div class="value" id="speed">—</div><div class="hint" id="speed-source">Testreferenz, nicht gemessen</div></div>
<div class="card"><div class="label">Kamera-Empfang</div><div class="value" id="fps">—</div><div class="hint" id="frames">Warte auf Bilder</div></div>
<div class="card"><div class="label">Antwortzeit zum Browser</div><div class="value" id="latency">—</div><div class="hint">Netz + Übertragung der Statusdaten</div></div>
</div>
<section class="panel"><h2>WebApp: Must</h2><table><thead><tr><th>Angabe</th><th>Empfangener Wert</th></tr></thead><tbody id="must"></tbody></table></section>
<section class="panel"><h2>WebApp: Nice</h2><table><thead><tr><th>Angabe</th><th>Empfangener Wert</th></tr></thead><tbody id="nice"></tbody></table></section>
<div class="sections"><section class="panel"><h2>Live-Kamera über MQTT</h2>
<img src="/stream.mjpg?key=__TOKEN__" alt="Noch kein Kamerabild"><small>Maximal 10 Bilder pro Sekunde im Stillstandstest.</small></section>
<section class="panel"><h2>Sensoren</h2><table><thead><tr><th>Sensor</th><th>Rate</th><th>Status</th></tr></thead><tbody id="sensors"></tbody></table></section></div>
<section class="panel"><h2>Weitere Sensordaten</h2><table><thead><tr><th>MQTT-Kanal</th><th>Letzter Inhalt</th></tr></thead><tbody id="details"></tbody></table></section>
<section class="panel"><h2>Empfangene MQTT-Nachrichten</h2><table><thead><tr><th>Topic</th><th>Anzahl</th></tr></thead><tbody id="topics"></tbody></table></section>
<section class="panel"><details><summary>Vollständige empfangene Daten anzeigen</summary><pre id="raw">Warte auf MQTT …</pre></details></section>
</main><script>
const $=id=>document.getElementById(id);
const value=x=>x===null||x===undefined?'—':String(x);
const measured=x=>x&&x.status==='valid'&&Number.isFinite(x.value)?x.value:null;
function rows(id,items){const body=$(id);body.replaceChildren();for(const cells of items){const tr=document.createElement('tr');
for(const cell of cells){const td=document.createElement('td');td.textContent=value(cell);tr.appendChild(td)}body.appendChild(tr)}}
async function update(){try{const started=performance.now();
const response=await fetch('/snapshot?key=__TOKEN__',{cache:'no-store'});
if(!response.ok)throw Error('HTTP '+response.status);const d=await response.json();
$('latency').textContent=Math.round(performance.now()-started)+' ms';
const fresh=d.health?.reachable===true;
const p=fresh?(d.panel_state?.payload||{}):{};const s=fresh?(d.stationary_test||{}):{};const c=d.camera||{};
const probe=fresh?(d.battery_probe||{}):{};const common=fresh?(d.common_state||{}):{};
const dashboard=d.health?.reachable===true?(d.dashboard||{}):{};const must=dashboard.must||{};const nice=dashboard.nice||{};
$('board-diagnosis').textContent=p.board_diagnose||'Keine Boarddiagnose empfangen';
const gaps=[];
if(!d.common_state)gaps.push(['Betriebszustand','Gemeinsamer grundbetrieb-v1-Zustand fehlt. Prozessflags belegen keinen Hardwarezustand.']);
if(must.position_on_site_plan==null)gaps.push(['Spielfeldposition','Verifizierte Zuordnung zur Spielfeldkarte fehlt.']);
if(must.battery_voltage_v==null)gaps.push(['Akku','Keine frische Spannungsmessung; Boardverbindung und Akku-Topic prüfen.']);
for(const sensor of p.sensoren||[])if(sensor.ok===false)gaps.push([sensor.name,'Keine frischen Daten: '+value(sensor.topic)]);
if(nice.current_task==null||nice.target==null)gaps.push(['Auftrag / Ziel','Keine bestätigte Auftragsquelle empfangen.']);
if(nice.measured_speed_m_s==null)gaps.push(['Geschwindigkeit','Gemessene Bewegung fehlt; 0 m/s Testreferenz ist kein Messwert.']);
if(nice.direction==null)gaps.push(['Richtung','Keine bestätigte Richtungsangabe empfangen.']);
if(!nice.route_history_local_map?.length)gaps.push(['Routenverlauf','Keine lokale Kartenpose empfangen.']);
if(c.last_frame_age_s==null||c.last_frame_age_s>3)gaps.push(['Kamera','Kein frisches Kamerabild seit mindestens drei Sekunden.']);
rows('gaps',gaps.length?gaps:[['Datenprüfung','Keine Lücke in den hier geprüften Feldern. Fachliche Abnahme bleibt gesondert.']]);
$('broker').textContent=d.health?.reachable===true?'Online':d.health?.reachable===false?'Offline / Daten veraltet':'Unbekannt';$('updated').textContent='Letzter Status vor '+value(d.health?.panel_age_s)+' s';
const commonVoltage=measured(common.diagnostics?.battery_v);
const voltage=p.akku??commonVoltage??probe.voltage_v;
const batterySource=p.akku!=null?'Panel /battery':commonVoltage!=null?'Grundbetrieb':
probe.voltage_v!=null?value(probe.source_topic):probe.probe_running===false?
'Akkusuche beendet · siehe logs/mqtt-live-battery-probe.log':'Keine frische Spannungsmessung';
$('battery').textContent=voltage==null?'Keine Messung':String(voltage)+' V';
$('battery-source').textContent=batterySource+(voltage==null&&probe.candidate_topics?.length?
' · gefundene Topics: '+probe.candidate_topics.join(', '):'');
const percent=p.akku_prozent??(voltage==null?null:Math.max(0,Math.min(100,Math.round((voltage-10.5)/2.1*100))));
$('battery-percent').textContent=percent==null?'Keine Schätzung':'ca. '+percent+' %';
$('speed').textContent=s.test_reference_speed_m_s==null?'—':s.test_reference_speed_m_s+' m/s';
$('speed-source').textContent=s.test_reference_speed_m_s==null?'Warte auf Testdatensatz':'Testreferenz · gemessen: '+value(s.measured_speed_m_s);
$('fps').textContent=c.fps_2s==null?'—':c.fps_2s+' FPS';
$('frames').textContent=value(c.received)+' Bilder empfangen · letztes vor '+value(c.last_frame_age_s)+' s';
rows('must',[
['Roboter erreichbar',d.health?.reachable===true?'Ja':d.health?.reachable===false?'Nein / keine frischen Daten':'Unbekannt'],
['Betriebszustand',value(must.state)+(must.state_source==='panel_process_flags'?' (aus Prozessflags; Hardwarezustand unbekannt)':'')],
['Position auf dem Spielfeldplan',must.position_on_site_plan==null?'Nicht verfügbar':JSON.stringify(must.position_on_site_plan)],
['Akku',must.battery_voltage_v==null?'Keine Messung':must.battery_voltage_v+' V · ca. '+value(must.battery_percent_estimate)+' %']]);
rows('nice',[
['Aktueller Auftrag / Ziel',value(nice.current_task)+' / '+value(nice.target)],
['Richtung',value(nice.direction)],
['Gemessene Geschwindigkeit',nice.measured_speed_m_s==null?'Nicht verfügbar':nice.measured_speed_m_s+' m/s'],
['Testreferenz Geschwindigkeit',nice.test_reference_speed_m_s==null?'—':nice.test_reference_speed_m_s+' m/s'],
['Lokale Kartenpose',nice.local_map_pose?JSON.stringify(nice.local_map_pose):'Nicht verfügbar'],
['Routenverlauf',value(nice.route_history_local_map?.length||0)+' lokale Kartenpunkte'],
['Ereignisse',(nice.events||[]).length?
nice.events.slice(0,5).map(e=>value(e.text)).join(' · '):'Keine aktuellen Meldungen']]);
rows('sensors',(p.sensoren||[]).map(x=>[x.name,x.hz==null?'—':x.hz+' Hz',x.ok===true?'OK':x.ok===false?'Fehlt':'Unbekannt']));
rows('topics',Object.entries(d.topic_counts||{}).sort((a,b)=>a[0].localeCompare(b[0])).map(([k,v])=>[k,v]));
rows('details',Object.entries(d.sensor_details||{}).sort((a,b)=>a[0].localeCompare(b[0])).map(([k,v])=>
[k,v.kind==='scan'?value(v.range_count)+' Messpunkte · '+value(v.topic):
value(v.width)+' × '+value(v.height)+' · '+value(v.encoding)+' · '+value(v.observed_at)]));
$('raw').textContent=JSON.stringify(d,null,2);
}catch(error){$('broker').textContent='Verbindung fehlt';$('updated').textContent=String(error)}
finally{setTimeout(update,1000)}}update();
</script></html>'''.encode('utf-8')


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def robot_addresses():
    try:
        result = subprocess.run(['ip', '-4', '-o', 'addr', 'show', 'scope', 'global'],
                                capture_output=True, text=True, timeout=3, check=True)
        addresses = []
        for line in result.stdout.splitlines():
            parts = line.split()
            match = re.search(r'\binet\s+(\d+\.\d+\.\d+\.\d+)/', line)
            if len(parts) > 1 and match and not parts[1].startswith(('docker', 'br-', 'veth', 'virbr')):
                addresses.append(match.group(1))
        return list(dict.fromkeys(addresses))
    except (OSError, subprocess.SubprocessError):
        return []


def valid_measurement(value):
    if not isinstance(value, dict) or value.get('status') != 'valid':
        return None
    number = value.get('value')
    return number if isinstance(number, (int, float)) and not isinstance(number, bool) and math.isfinite(number) else None


def dashboard_summary(panel_status, common_state, battery_probe, availability, route_history):
    panel = panel_status.get('payload', {}) if isinstance(panel_status, dict) else {}
    common = common_state if isinstance(common_state, dict) else {}
    diagnostics = common.get('diagnostics') or {}
    motion = common.get('motion') or {}
    route = common.get('route') or {}
    runtime = common.get('runtime') or {}
    voltage = panel.get('akku')
    battery_source = 'panel /battery' if voltage is not None else None
    if voltage is None:
        voltage = valid_measurement(diagnostics.get('battery_v'))
        battery_source = 'grundbetrieb' if voltage is not None else None
    if voltage is None:
        voltage = battery_probe.get('voltage_v')
        battery_source = battery_probe.get('source_topic') if voltage is not None else None
    percent = panel.get('akku_prozent') if battery_source == 'panel /battery' else None
    if percent is None and isinstance(voltage, (int, float)):
        percent = max(0, min(100, round((voltage - 10.5) / 2.1 * 100)))
    local_pose = panel.get('karte') if isinstance(panel.get('karte'), dict) else {}
    if not all(isinstance(local_pose.get(key), (int, float)) for key in ('x', 'y', 'w')):
        local_pose = None
    else:
        local_pose = {'x_m': local_pose['x'], 'y_m': local_pose['y'],
                      'heading_rad': local_pose['w'], 'status': local_pose.get('status'),
                      'frame': 'local_map'}
    state = runtime.get('state')
    events = panel.get('ereignisse') if isinstance(panel.get('ereignisse'), list) else []
    return {
        'transport_schema': 'dashboard-test/1',
        'robot_id': 'RM04',
        'received_at': datetime.now(timezone.utc).isoformat(),
        'must': {
            'reachable': availability == 'online',
            'availability': availability,
            'state': state,
            'state_source': 'grundbetrieb' if runtime.get('state') else None,
            'state_reason': None if state else 'no_authoritative_runtime_state',
            'position_on_site_plan': None,
            'position_reason': 'no_verified_site_plan_coordinates',
            'battery_voltage_v': voltage,
            'battery_source': battery_source,
            'battery_percent_estimate': percent,
        },
        'nice': {
            'current_task': None,
            'target': None,
            'direction': route.get('direction'),
            'measured_speed_m_s': valid_measurement(motion.get('measured_v_m_s')),
            'test_reference_speed_m_s': 0.0,
            'local_map_pose': local_pose,
            'route_history_local_map': list(route_history),
            'events': events[:10],
        },
    }


def ensure_broker():
    try:
        from amqtt.broker import Broker
        return Broker
    except ImportError:
        print('Installiere lokalen Testbroker amqtt fuer diesen Benutzer ...', flush=True)
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', '--user', 'amqtt==0.11.3'],
                                timeout=180, check=False)
        if result.returncode:
            raise RuntimeError('amqtt konnte nicht installiert werden')
        from amqtt.broker import Broker
        return Broker


def no_drive_processes():
    rows = subprocess.check_output(['ps', '-eo', 'pid=,args='], text=True)
    forbidden = ('line_follower.py', '/ki/zentrale.py', '/panel/panel.py')
    matches = []
    for line in rows.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2 and int(parts[0]) != os.getpid() and any(item in parts[1] for item in forbidden):
            matches.append(line.strip())
    if matches:
        raise RuntimeError('Bestehende Fahr-/KI-/Panelprozesse gefunden; Test wird nicht gestartet: '
                           + '; '.join(matches[:4]))


class Observer:
    def __init__(self):
        self.lock = threading.Lock()
        self.new_frame = threading.Condition(self.lock)
        self.frames = 0
        self.frame_times = deque(maxlen=100)
        self.image = None
        self.topics = {}
        self.last_status = None
        self.last_status_monotonic = None
        self.last_common_state = None
        self.last_details = {}
        self.last_stationary_test = None
        self.last_battery_probe = None
        self.last_dashboard = None
        self.route_history = deque(maxlen=300)
        self.last_pose_key = None

    def received(self, client, userdata, message):
        suffix = message.topic.removeprefix('smartcity/robots/RM04/')
        if suffix == 'details/camera':
            try:
                packet = json.loads(message.payload)
                image = base64.b64decode(packet['payload']['data_b64'], validate=True)
                if not image.startswith(b'\xff\xd8') or not image.endswith(b'\xff\xd9'):
                    return
            except (ValueError, KeyError, TypeError):
                return
            with self.new_frame:
                self.frames += 1
                self.frame_times.append(time.monotonic())
                self.image = image
                self.topics[suffix] = self.topics.get(suffix, 0) + 1
                self.new_frame.notify_all()
            return
        with self.lock:
            self.topics[suffix] = self.topics.get(suffix, 0) + 1
            if suffix == 'state' and not message.payload:
                self.last_common_state = None
                return
        try:
            packet = json.loads(message.payload)
        except ValueError:
            packet = message.payload.decode('utf-8', errors='replace')
        with self.lock:
            if suffix == 'panel/state':
                self.last_status = packet
                self.last_status_monotonic = time.monotonic()
                state = packet.get('payload') if isinstance(packet, dict) else None
                pose = state.get('karte') if isinstance(state, dict) else None
                if isinstance(pose, dict):
                    key = (pose.get('x'), pose.get('y'), pose.get('w'))
                    if all(isinstance(item, (int, float)) for item in key) and key != self.last_pose_key:
                        self.route_history.append({'received_at': datetime.now(timezone.utc).isoformat(),
                                                   'observed_at_unix': time.time(),
                                                   'x_m': key[0], 'y_m': key[1],
                                                   'heading_rad': key[2], 'frame': 'local_map'})
                        self.last_pose_key = key
                while self.route_history and time.time() - self.route_history[0]['observed_at_unix'] > 300:
                    self.route_history.popleft()
            elif suffix == 'state':
                self.last_common_state = packet
            elif suffix == 'test/stationary':
                self.last_stationary_test = packet
            elif suffix == 'test/battery':
                self.last_battery_probe = packet
            elif suffix == 'test/dashboard':
                self.last_dashboard = packet
            elif suffix.startswith('details/') and isinstance(packet, dict):
                detail = packet.get('payload')
                if isinstance(detail, dict):
                    self.last_details[suffix] = {
                        key: value for key, value in detail.items()
                        if key not in ('data_b64', 'ranges', 'intensities')}
                    if 'ranges' in detail:
                        self.last_details[suffix]['range_count'] = len(detail['ranges'])
                        self.last_details[suffix]['ranges_first_12'] = detail['ranges'][:12]
                    if 'data_b64' in detail:
                        self.last_details[suffix]['encoded_bytes'] = len(detail['data_b64'])
            elif suffix in ('availability', 'info', 'communication', 'events'):
                setattr(self, 'last_' + suffix, packet)


def viewer_handler(observer, token):
    class View(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            parsed = urlsplit(self.path)
            supplied = parse_qs(parsed.query).get('key', [''])[0]
            if not secrets.compare_digest(supplied, token):
                self.send_error(403)
                return
            if parsed.path == '/stream.mjpg':
                self.send_response(200)
                self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                last_frame = 0
                try:
                    while True:
                        with observer.new_frame:
                            observer.new_frame.wait_for(
                                lambda: observer.frames != last_frame, timeout=5)
                            if observer.frames == last_frame:
                                continue
                            last_frame, image = observer.frames, observer.image
                        self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\n'
                                         + f'Content-Length: {len(image)}\r\n\r\n'.encode()
                                         + image + b'\r\n')
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
                    return
            with observer.lock:
                if parsed.path == '/':
                    body, mime = VIEW_HTML.replace(b'__TOKEN__', token.encode()), 'text/html; charset=utf-8'
                elif parsed.path == '/snapshot':
                    now = time.monotonic()
                    panel_age = (max(0, now - observer.last_status_monotonic)
                                 if observer.last_status_monotonic is not None else None)
                    availability = getattr(observer, 'last_availability', None)
                    body = json.dumps({
                        'robot': 'RM04', 'test_time': datetime.now(timezone.utc).isoformat(),
                        'health': {'reachable': (availability == 'online' and panel_age <= 5)
                                   if panel_age is not None else None,
                                   'panel_age_s': round(panel_age, 2) if panel_age is not None else None,
                                   'timeout_s': 5},
                        'camera': {'received': observer.frames,
                                   'fps_2s': sum(t >= now - 2 for t in observer.frame_times) / 2,
                                   'last_frame_age_s': round(now - observer.frame_times[-1], 2)
                                   if observer.frame_times else None},
                        'topic_counts': observer.topics,
                        'availability': getattr(observer, 'last_availability', None),
                        'stationary_test': observer.last_stationary_test,
                        'battery_probe': observer.last_battery_probe,
                        'dashboard': observer.last_dashboard,
                        'panel_state': observer.last_status,
                        'common_state': observer.last_common_state,
                        'sensor_details': observer.last_details,
                        'info': getattr(observer, 'last_info', None),
                        'communication': getattr(observer, 'last_communication', None),
                        'last_event': getattr(observer, 'last_events', None),
                    }, allow_nan=False).encode()
                    mime = 'application/json'
                elif parsed.path == '/camera.jpg' and observer.image:
                    body, mime = observer.image, 'image/jpeg'
                else:
                    self.send_error(404)
                    return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return View


def start_child(command, log_name, environment=None):
    log_dir = REPO / 'logs'
    log_dir.mkdir(exist_ok=True)
    log = open(log_dir / log_name, 'ab', buffering=0)
    process = subprocess.Popen(command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT,
                               start_new_session=True, env=environment)
    log.close()
    return process


def _run_test():
    if not (REPO / 'mqtt/panel_bridge.py').is_file():
        raise RuntimeError('Repo unter ~/smartcity-roboter fehlt')
    robot = (Path.home() / 'roboter_name').read_text().strip()
    if robot != 'RM04':
        raise RuntimeError('Unerwartete Roboter-ID: ' + robot)
    no_drive_processes()
    Broker = ensure_broker()
    import paho.mqtt.client as mqtt

    loop = asyncio.new_event_loop()

    def run_loop():
        asyncio.set_event_loop(loop)
        loop.run_forever()

    loop_thread = threading.Thread(target=run_loop, daemon=True)
    loop_thread.start()
    broker_port = free_port()

    async def create_broker():
        broker = Broker({'listeners': {'default': {'type': 'tcp',
                          'bind': f'127.0.0.1:{broker_port}'}},
                         'plugins': {'amqtt.plugins.authentication.AnonymousAuthPlugin':
                                     {'allow_anonymous': True}}})
        await broker.start()
        return broker

    broker = asyncio.run_coroutine_threadsafe(create_broker(), loop).result(15)
    children = []
    observer = Observer()
    reader = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='RM04-local-test-reader')
    reader.on_connect = lambda client, *_: client.subscribe('smartcity/robots/RM04/#', qos=1)
    reader.on_message = observer.received
    viewer = None
    viewer_token = secrets.token_urlsafe(16)
    previous_signals = {}
    def request_shutdown(_signum, _frame):
        raise KeyboardInterrupt
    try:
        for name in ('SIGTERM', 'SIGHUP'):
            signum = getattr(signal, name, None)
            if signum is not None:
                previous_signals[signum] = signal.signal(signum, request_shutdown)
        reader.connect('127.0.0.1', broker_port)
        reader.loop_start()
        try:
            viewer = ThreadingHTTPServer(('0.0.0.0', VIEWER_PORT), viewer_handler(observer, viewer_token))
        except OSError as error:
            raise RuntimeError(f'Empfangsansicht kann Port {VIEWER_PORT} nicht belegen; '
                               'alten Test zuerst mit Strg+C beenden') from error
        threading.Thread(target=viewer.serve_forever, daemon=True).start()

        panel_port = free_port()
        panel_env = os.environ.copy()
        panel_env['SMARTCITY_MQTT'] = '0'
        panel_command = ['bash', '-lc',
                         f'source scripts/env.sh && exec python3 panel/panel.py --kein-netz --port {panel_port}']
        children.append(start_child(panel_command, 'mqtt-live-panel.log', panel_env))
        deadline = time.monotonic() + 30
        while True:
            if children[-1].poll() is not None:
                raise RuntimeError('Lesendes Panel beendet; siehe logs/mqtt-live-panel.log')
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{panel_port}/api/status', timeout=1).close()
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Panel antwortet nicht; siehe logs/mqtt-live-panel.log')
                time.sleep(.5)

        battery_probe_path = REPO / 'logs/mqtt-live-battery-probe.json'
        battery_probe_path.unlink(missing_ok=True)
        (REPO / 'logs/mqtt-live-battery-probe.py').write_text(BATTERY_PROBE, encoding='utf-8')
        battery_process = start_child(
            ['bash', '-lc', 'source scripts/env.sh && exec python3 -u logs/mqtt-live-battery-probe.py'],
            'mqtt-live-battery-probe.log')
        children.append(battery_process)

        try:
            camera_topic = subprocess.run(
                ['bash', '-lc', 'source scripts/env.sh && ros2 topic info /camera/color/image_raw'],
                cwd=REPO, capture_output=True, text=True, timeout=6)
            has_camera_publisher = any(
                line.startswith('Publisher count:') and int(line.split(':', 1)[1].strip()) > 0
                for line in camera_topic.stdout.splitlines()
                if line.startswith('Publisher count:') and line.split(':', 1)[1].strip().isdigit())
        except subprocess.TimeoutExpired:
            has_camera_publisher = False
        if not has_camera_publisher:
            print('Starte nur den Kameratreiber ...', flush=True)
            children.append(start_child(['bash', 'scripts/kamera.sh'], 'mqtt-live-camera.log'))
        else:
            print('Kameratreiber laeuft bereits; verwende vorhandene Bilder.', flush=True)

        bridge_env = os.environ.copy()
        bridge_env.pop('MQTT_USERNAME', None)
        bridge_env.pop('MQTT_PASSWORD', None)
        bridge_env['SMARTCITY_MQTT_STATUS_FILE'] = str(REPO / 'logs/mqtt-live-status.json')
        children.append(start_child(
            [sys.executable, 'mqtt/panel_bridge.py', '--host', '127.0.0.1',
             '--port', str(broker_port), '--robot', 'RM04',
             '--panel', f'http://127.0.0.1:{panel_port}', '--camera-hz', '10'],
            'mqtt-live-bridge.log', bridge_env))

        print(f'Lokaler Broker: 127.0.0.1:{broker_port}', flush=True)
        for address in robot_addresses():
            print(f'Empfangsansicht im Netz: http://{address}:{viewer.server_port}/?key={viewer_token}', flush=True)
        print(f'Empfangsansicht am Roboter: http://127.0.0.1:{viewer.server_port}/?key={viewer_token}', flush=True)
        print('Testreferenz 0 m/s auf test/stationary; kein gemessener Fahrwert.', flush=True)
        print('Keine Fahr-, KI- oder Armprogramme gestartet. Beenden mit Strg+C.', flush=True)
        last_stationary_sent = 0.0
        while True:
            if any(child.poll() is not None for child in children if child is not battery_process):
                raise RuntimeError('Ein Testprozess wurde beendet; Logs in ~/smartcity-roboter/logs/mqtt-live-*.log')
            with observer.lock:
                panel_status = observer.last_status
            if isinstance(panel_status, dict):
                state = panel_status.get('payload')
                if not isinstance(state, dict):
                    raise RuntimeError('Panelstatus ohne gueltige Nutzdaten')
                if state.get('fahren') is not False or state.get('ki_prozess') is not False or state.get('fremde'):
                    raise RuntimeError('Fahr-/KI-Prozess gemeldet; Stillstandstest wird beendet')
                now = time.monotonic()
                if now - last_stationary_sent >= 1:
                    stationary = {
                        'transport_schema': 'stationary-test/1',
                        'robot_id': 'RM04',
                        'received_at': datetime.now(timezone.utc).isoformat(),
                        'source': 'manual_stationary_test',
                        'panel_state_seq': panel_status.get('seq'),
                        'test_reference_speed_m_s': 0.0,
                        'measured_speed_m_s': None,
                        'panel_reports_drive_process_running': False,
                        'panel_reports_ki_process_running': False,
                        'motor_hardware_state': 'not_measured',
                    }
                    publication = reader.publish('smartcity/robots/RM04/test/stationary',
                                                 json.dumps(stationary), qos=1, retain=False)
                    publication.wait_for_publish(timeout=2)
                    if not publication.is_published():
                        raise RuntimeError('MQTT-Bestaetigung fuer Stillstandstest fehlt')
                    try:
                        battery_record = json.loads(battery_probe_path.read_text(encoding='utf-8'))
                    except (OSError, ValueError):
                        battery_record = {}
                    voltage = battery_record.get('voltage_v')
                    observed = battery_record.get('observed_at_unix')
                    fresh = (isinstance(voltage, (int, float)) and not isinstance(voltage, bool)
                             and isinstance(observed, (int, float))
                             and 7.0 <= voltage <= 16.8 and 0 <= time.time() - observed <= 5)
                    battery = {
                        'transport_schema': 'battery-probe-test/1',
                        'robot_id': 'RM04',
                        'received_at': datetime.now(timezone.utc).isoformat(),
                        'voltage_v': voltage if fresh else None,
                        'source_topic': battery_record.get('source_topic') if fresh else None,
                        'source_type': battery_record.get('source_type') if fresh else None,
                        'candidate_topics': battery_record.get('candidate_topics', []),
                        'probe_running': battery_process.poll() is None,
                    }
                    publication = reader.publish('smartcity/robots/RM04/test/battery',
                                                 json.dumps(battery), qos=1, retain=False)
                    publication.wait_for_publish(timeout=2)
                    if not publication.is_published():
                        raise RuntimeError('MQTT-Bestaetigung fuer Akkutest fehlt')
                    with observer.lock:
                        common_state = observer.last_common_state
                        availability = getattr(observer, 'last_availability', None)
                        route_history = list(observer.route_history)
                    dashboard = dashboard_summary(panel_status, common_state, battery,
                                                  availability, route_history)
                    publication = reader.publish('smartcity/robots/RM04/test/dashboard',
                                                 json.dumps(dashboard, allow_nan=False),
                                                 qos=1, retain=False)
                    publication.wait_for_publish(timeout=2)
                    if not publication.is_published():
                        raise RuntimeError('MQTT-Bestaetigung fuer Dashboardtest fehlt')
                    last_stationary_sent = now
            time.sleep(.2)
    except KeyboardInterrupt:
        pass
    finally:
        for child in reversed(children):
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGINT)
                try:
                    child.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
        reader.disconnect()
        reader.loop_stop()
        if viewer:
            viewer.shutdown()
            viewer.server_close()
        async def close_broker():
            for server in broker._servers.values():
                await server.close_instance()
            if not broker._broadcast_shutdown_waiter.done():
                broker._broadcast_shutdown_waiter.set_result(True)
            await asyncio.gather(broker._broadcast_task, return_exceptions=True)
        try:
            asyncio.run_coroutine_threadsafe(close_broker(), loop).result(5)
        finally:
            loop.call_soon_threadsafe(loop.stop)
            loop_thread.join(5)
            loop.close()
            for signum, handler in previous_signals.items():
                signal.signal(signum, handler)


def main():
    # Linux robot only: retain the advisory lock for the whole process lifetime.
    import fcntl
    if not (REPO / 'mqtt/panel_bridge.py').is_file():
        raise RuntimeError('Repo unter ~/smartcity-roboter fehlt')
    log_dir = REPO / 'logs'
    log_dir.mkdir(exist_ok=True)
    with (log_dir / 'mqtt-live-test.lock').open('a') as test_lock:
        try:
            fcntl.flock(test_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('Ein MQTT-Livetest läuft bereits; zuerst geordnet beenden.') from error
        _run_test()


if __name__ == '__main__':
    main()
