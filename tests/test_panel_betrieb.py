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
        self.node.betrieb['target_process_id'] = 'test-process'
        self.node._set('lf', dict(self.node.betrieb, process_id='test-process',
            handshake_bestaetigt=True, betrieb_angefordert=False, drive=False))

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

    def test_stop_is_not_blocked_by_slow_start_and_late_completion_cannot_activate(self):
        entered, release = threading.Event(), threading.Event()
        answer = []
        def slow_package_check(_):
            entered.set()
            release.wait(3.)
            return False
        def start_request():
            answer.append(self.post('start'))
        with mock.patch.object(panel, 'paket_da', side_effect=slow_package_check), \
             mock.patch.object(self.node, 'stillstand'):
            worker = threading.Thread(target=start_request)
            worker.start()
            try:
                self.assertTrue(entered.wait(1.))
                stop_answer = self.post('stopp')
                self.assertIn('Gestoppt', stop_answer)
                self.assertFalse(self.node.betrieb['angefordert'])
                self.assertFalse(release.is_set())
            finally:
                release.set()
                worker.join(3.)
        self.assertFalse(worker.is_alive())
        self.assertIn('verworfen', answer[0])
        self.assertFalse(self.node.betrieb['angefordert'])

    def test_pending_start_requires_matching_process_handshake_and_stop_invalidates_ack(self):
        self.node.betrieb_setzen(True)
        self.assertTrue(self.node.start_wartet)
        self.assertFalse(self.node.betrieb['angefordert'])
        self.node._set('lf', {'process_id': 'new-process', 'drive': False})
        self.node.betrieb_senden()
        pending = dict(self.node.betrieb)
        self.assertEqual(pending['target_process_id'], 'new-process')
        ack = dict(pending, process_id='new-process', drive=False,
                   betrieb_angefordert=False, handshake_bestaetigt=True)
        self.node._set('lf', ack)
        self.node.betrieb_senden()
        self.assertTrue(self.node.betrieb['angefordert'])
        self.assertGreater(self.node.betrieb['generation'], pending['generation'])
        self.node.betrieb_setzen(False)
        self.node.betrieb_setzen(True)
        pending = dict(self.node.betrieb)
        self.node.betrieb_setzen(False)  # STOPP gewinnt vor verspaeteter Quittung.
        self.node._set('lf', dict(pending, process_id='new-process', drive=False,
            betrieb_angefordert=False, handshake_bestaetigt=True))
        self.node.betrieb_senden()
        self.assertFalse(self.node.start_wartet)
        self.assertFalse(self.node.betrieb['angefordert'])

    def test_explicit_new_start_after_process_restart_rebinds_only_inactive(self):
        self.ack_stop()
        self.node.betrieb_setzen(True)
        self.node._set('lf', dict(self.node.betrieb, process_id='test-process', drive=False,
            betrieb_angefordert=False, handshake_bestaetigt=True))
        self.node.betrieb_senden()
        self.assertTrue(self.node.betrieb['angefordert'])
        old = dict(self.node.betrieb)
        self.node._set('lf', {'process_id': 'restarted-process', 'drive': False})
        self.node.betrieb_senden()
        self.assertEqual(self.node.betrieb, old)  # Normaler HB bindet nicht neu.
        self.node.betrieb_setzen(True)  # Neue bewusste Bedienung darf handshaken.
        self.assertTrue(self.node.start_wartet)
        self.assertFalse(self.node.betrieb['angefordert'])
        self.assertEqual(self.node.betrieb['target_process_id'], 'restarted-process')
        self.assertGreater(self.node.betrieb['generation'], old['generation'])


if __name__ == '__main__':
    unittest.main()
