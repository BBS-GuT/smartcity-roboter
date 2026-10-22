#!/usr/bin/env python3
"""Temporarily serve exactly one robot test script to the known robot IP."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


FILES = {
    '/update_panel_mqtt.py': Path(__file__).with_name('update_panel_mqtt.py'),
    '/panel.py': Path(__file__).resolve().parents[1] / 'panel/panel.py',
    '/panel_index.html': Path(__file__).resolve().parents[1] / 'panel/index.html',
    '/mqtt_data.py': Path(__file__).resolve().parents[1] / 'panel/mqtt_data.py',
    '/telemetry_detail.py': Path(__file__).resolve().parents[1] / 'panel/telemetry_detail.py',
    '/microros_agent_stable.sh': Path(__file__).resolve().parents[1] / 'scripts/microros_agent_stable.sh',
    '/robot_live_test.py': Path(__file__).with_name('robot_live_test.py'),
    '/update_robot_live_test.py': Path(__file__).with_name('update_robot_live_test.py'),
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.client_address[0] not in ('10.0.12.104', '10.0.12.107', '10.0.12.100'):
            self.send_error(403)
            return
        script = FILES.get(self.path)
        if script is None:
            self.send_error(404)
            return
        body = script.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'text/x-python; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    HTTPServer(('10.0.12.100', 8765), Handler).serve_forever()
