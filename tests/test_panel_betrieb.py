"""Panel lifecycle uses confirmed operating permission, not child process lifetime."""
import json
import sys
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest import mock
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests' / 'attrappen'))
sys.path.insert(0, str(ROOT / 'panel'))
sys.path.insert(0, str(ROOT / 'lib'))
import panel


class Args:
    port = 0
    kein_netz = False
    tiefe_topic = '/camera/depth/image_raw'
    karte = 'test'


class PanelLifecycle(unittest.TestCase):
    def setUp(self):
        self.node = panel.PanelNode(Args())
        self.prozesse = mock.Mock()
        self.prozesse.info = {'fahren': 'WAHRNEHMUNG'}
        self.prozesse.laeuft.side_effect = lambda name: name == 'fahren'
        handler, _ = panel.mache_handler(self.node, self.prozesse)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.url = 'http://127.0.0.1:' + str(self.server.server_address[1])
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def post(self, name, data=None):
        req = urllib.request.Request(self.url + '/api/' + name,
              data=json.dumps(data or {}).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as response:
            return json.load(response)['antwort']

    def ack_stop(self):
        self.node._set('lf', dict(self.node.betrieb, drive=False))

    def test_stop_keeps_process_and_manual_arm_needs_current_stop_ack(self):
        self.node.betrieb_setzen(True)
        with mock.patch.object(self.node, 'stillstand'):
            self.post('stopp')
        self.prozesse.stopp.assert_not_called()
        self.assertFalse(self.node.betrieb['angefordert'])
        arm = mock.Mock()
        self.node.arm = arm
        arm.echt = False
        arm.fahre.return_value = None
        with mock.patch.object(self.node, 'arm_holen', return_value=arm):
            self.assertIn('Quittung', self.post('arm_pose', {'winkel': [90]*6}))
            arm.fahre.assert_not_called()
            self.ack_stop()
            self.assertIn('Arm faehrt', self.post('arm_pose', {'winkel': [90]*6}))
            arm.fahre.assert_called_once()
            self.node.daten['lf'] = (0., dict(self.node.betrieb, drive=False))
            self.assertFalse(self.node.stopp_bestaetigt())

    def test_double_start_same_id_and_stop_invalidates_outstanding_request(self):
        self.node._set('ki', {'aktion': 'stopp'})
        self.post('start')
        first = dict(self.node.betrieb)
        self.post('start')
        self.assertEqual(first, self.node.betrieb)
        with mock.patch.object(self.node, 'stillstand'):
            self.post('stopp')
        self.assertGreater(self.node.betrieb['generation'], first['generation'])
        self.node._set('lf', dict(first, drive=True))
        self.assertFalse(self.node.stopp_bestaetigt())
        self.ack_stop()
        self.assertTrue(self.node.stopp_bestaetigt())

    def test_status_exposes_stop_separately_from_live_perception(self):
        self.ack_stop()
        with mock.patch.object(self.node, 'sensor_status', return_value=[{'ok':True},{'ok':True}]), \
             mock.patch.object(panel, 'board_diagnose', return_value='test'), \
             mock.patch.object(panel, 'agent_info', return_value={'laeuft':True}):
            with urllib.request.urlopen(self.url + '/api/status') as response:
                result = json.load(response)
        self.assertFalse(result['fahren'])
        self.assertTrue(result['wahrnehmung'])


if __name__ == '__main__':
    unittest.main()

