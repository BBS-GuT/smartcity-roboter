"""Read-only transport regressions, no ROS, MQTT package or project broker required."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

spec = importlib.util.spec_from_file_location('mqtt_panel', Path(__file__).resolve().parents[1] / 'mqtt/panel_bridge.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class TestPanelTransport(unittest.TestCase):
    def test_missing_connack_stops_client_without_reading_panel(self):
        b = object.__new__(m.Bridge)
        b.write_status = lambda: None
        b.args = MagicMock(host='127.0.0.1', port=1883)
        b.args.camera_hz = 0
        b.client = MagicMock()
        b.stop = m.threading.Event()
        b.detail_stop = m.threading.Event()
        b.connection_lost = m.threading.Event()
        b.connected = MagicMock()
        b.connected.wait.return_value = False
        b.connected.is_set.return_value = False
        b.errors = 0
        with patch.object(m.time, 'monotonic', side_effect=[0, 11]), \
                patch.object(m, 'read_panel') as read, patch('builtins.print') as log:
            b.run()
        self.assertEqual(b.errors, 1)
        read.assert_not_called()
        b.client.disconnect.assert_called_once()
        b.client.loop_stop.assert_called_once()
        log.assert_called_once()

    def test_connection_failures_are_visible_and_restart_client(self):
        for rejected in (False, True):
            b = object.__new__(m.Bridge)
            b.write_status = lambda: None
            b.errors = 0
            b.connected = m.threading.Event()
            b.connection_lost = m.threading.Event()
            with patch('builtins.print') as log:
                if rejected:
                    b._connected(None, None, None, 5, None)
                else:
                    b._connect_failed(None, None)
            self.assertEqual(b.errors, 1)
            self.assertTrue(b.connection_lost.is_set())
            self.assertFalse(b.connected.is_set())
            log.assert_called_once()

    def test_invalid_sensor_values_are_unavailable(self):
        result = m.finite_json({'scan': [float('inf'), float('nan'), -float('inf'), 0, 1.2]})
        self.assertEqual(result, {'scan': [None, None, None, 0, 1.2]})
        json.dumps(result, allow_nan=False)

    def test_http_is_read_only(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"fahren":false,"ki":null}'
        with patch.object(m.urllib.request, 'urlopen', return_value=response) as get:
            self.assertEqual(m.read_panel('http://localhost:8080/')['ki'], None)
            get.assert_called_once_with('http://localhost:8080/api/status', timeout=2)

    def test_oversize_and_invalid_status_rejected(self):
        for raw in (b'[]', b'bad', b'123456'):
            response = MagicMock()
            response.__enter__.return_value.read.return_value = raw
            with patch.object(m.urllib.request, 'urlopen', return_value=response):
                with self.assertRaises((ValueError, json.JSONDecodeError)):
                    m.read_panel('http://localhost', limit=5)

    def test_ack_is_required(self):
        b = object.__new__(m.Bridge)
        b.base = 'synthetic/RMTEST'
        b.client = MagicMock()
        b.client.publish.return_value.is_published.return_value = False
        with self.assertRaises(TimeoutError):
            b.send('panel/state', '{}')
        b.client.publish.return_value.is_published.return_value = True
        b.send('panel/state', '{}')
        b.client.publish.assert_called_with('synthetic/RMTEST/panel/state', '{}', qos=1, retain=True)

    def test_common_state_requires_fresh_valid_document(self):
        fixture = json.loads((Path(__file__).resolve().parent / 'fixtures/grundbetrieb/stillstand.json').read_text())
        fixture['generated_mono_s'] = m.time.monotonic()
        response = MagicMock()
        response.__enter__.return_value.status = 200
        response.__enter__.return_value.read.return_value = json.dumps(fixture).encode()
        with patch.object(m.urllib.request, 'urlopen', return_value=response):
            self.assertEqual(m.read_common_state('http://localhost:8080'), fixture)
        fixture['generated_mono_s'] -= 10
        response.__enter__.return_value.read.return_value = json.dumps(fixture).encode()
        with patch.object(m.urllib.request, 'urlopen', return_value=response):
            with self.assertRaisesRegex(ValueError, 'not fresh'):
                m.read_common_state('http://localhost:8080')
        fixture['schema_version'] = 'invalid'
        response.__enter__.return_value.read.return_value = json.dumps(fixture).encode()
        with patch.object(m.urllib.request, 'urlopen', return_value=response):
            with self.assertRaises(ValueError):
                m.read_common_state('http://localhost:8080')

    def test_camera_rate_defaults_to_20_and_remains_bounded(self):
        with patch.object(m.sys, 'argv', ['panel_bridge.py', '--robot', 'RMTEST']):
            self.assertEqual(m.arguments().camera_hz, 20.0)
        with patch.object(m.sys, 'argv', ['panel_bridge.py', '--robot', 'RMTEST', '--camera-hz', '21']):
            with self.assertRaises(SystemExit):
                m.arguments()


if __name__ == '__main__':
    unittest.main()
