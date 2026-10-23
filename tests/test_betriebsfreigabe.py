"""STOPP/START at the real final publisher, with synthetic ROS/sensor messages."""
import json
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_lidar_fusion_verbraucher as c
from betriebsfreigabe import Betriebsfreigabe
q = c.q


def request(g=1, active=True, session='panel', sid=None):
    return dict(target_process_id='test-process', session_id=session, generation=g, start_id=sid or str(g), angefordert=active)


class Lifecycle(unittest.TestCase):
    def test_initial_stop_and_delayed_readiness(self):
        b = Betriebsfreigabe()
        b.process_id = 'test-process'
        b.empfang(request(0, False), -.1)
        self.assertFalse(b.pruefen(True, 0))
        b.empfang(request(), 0)
        self.assertFalse(b.pruefen(False, .1))
        self.assertTrue(b.pruefen(True, .2))

    def test_stop_invalidates_old_start_and_duplicate_cannot_reenable(self):
        b = Betriebsfreigabe()
        b.process_id = 'test-process'
        b.empfang(request(0, False), -.1)
        b.empfang(request(), 0)
        b.empfang(request(2, False), .1)
        self.assertFalse(b.empfang(request(), .2))
        self.assertFalse(b.pruefen(True, .2))
        b.empfang(request(2, True), .3)
        self.assertFalse(b.pruefen(True, .3))
        b.empfang(request(3), .4)
        self.assertTrue(b.pruefen(True, .4))

    def test_heartbeat_loss_latches_until_new_start(self):
        b = Betriebsfreigabe()
        b.process_id = 'test-process'
        b.empfang(request(0, False), -.1)
        b.empfang(request(), 0)
        self.assertTrue(b.pruefen(True, 0))
        self.assertFalse(b.pruefen(True, .7))
        b.empfang(request(), .8)
        self.assertFalse(b.pruefen(True, .8))
        b.empfang(request(2), .9)
        self.assertTrue(b.pruefen(True, .9))

    def test_new_panel_session_stops_and_rejects_retired_heartbeat(self):
        b = Betriebsfreigabe()
        b.process_id = 'test-process'
        b.empfang(request(0, False), -.1)
        b.empfang(request(), 0)
        self.assertTrue(b.pruefen(True, 0))
        self.assertFalse(b.empfang(request(session='new'), .1))
        b.empfang(request(0, False, 'new'), .2)
        self.assertFalse(b.pruefen(True, .2))
        self.assertFalse(b.empfang(request(), .3))
        b.empfang(request(1, True, 'new'), .4)
        self.assertTrue(b.pruefen(True, .4))

    def test_new_process_rejects_inherited_active_and_replayed_old_process_handshake(self):
        old = Betriebsfreigabe()
        new = Betriebsfreigabe()
        inherited = dict(request(), target_process_id=old.process_id)
        self.assertFalse(new.empfang(inherited, 0))
        self.assertFalse(new.empfang(dict(inherited, angefordert=False), .1))
        self.assertFalse(new.empfang(dict(inherited, target_process_id=new.process_id), .2))
        self.assertFalse(new.pruefen(True, .2))
        handshake = dict(request(2, False), target_process_id=new.process_id)
        self.assertTrue(new.empfang(handshake, .3))
        self.assertFalse(new.pruefen(True, .3))
        self.assertTrue(new.empfang(dict(request(3), target_process_id=new.process_id), .4))
        self.assertTrue(new.pruefen(True, .4))


class Publisher(unittest.TestCase):
    def node(self):
        n = q.linienfolger()
        c.configure(n)
        n._p.update(drive=True, begleiteter_fahrbetrieb=True)
        c.feed(n)
        n.ki[1].update(begleiteter_fahrbetrieb=True, sensoren_bereit=True, session_id='panel', generation=1, start_id='1')
        return n

    def send(self, n, req):
        if not n.betrieb.handshake_bestaetigt:
            n.on_betrieb(SimpleNamespace(data=json.dumps(dict(request(0, False),
                target_process_id=n.betrieb.process_id))))
        n.on_betrieb(SimpleNamespace(data=json.dumps(dict(req, target_process_id=n.betrieb.process_id))))

    def test_initial_stop_current_start_and_old_ack_after_stop(self):
        n = self.node()
        with mock.patch.object(n, '_wunsch', return_value=(.15, 0., .5, 'Linie')):
            n.steuern()
            self.assertEqual(n.pub.letzte.linear.x, 0)
            self.send(n, request())
            n.steuern()
            self.assertEqual(n.pub.letzte.linear.x, .15)
            self.send(n, request(2, False))
            self.assertEqual(n.pub.letzte.linear.x, 0)
            self.send(n, request())
            n.steuern()
            self.assertEqual(n.pub.letzte.linear.x, 0)
            self.assertIn('/scan0', n.scans)

    def test_missing_data_and_wrong_ki_epoch_wait_then_actual_data_acknowledges(self):
        n = self.node()
        self.send(n, request())
        n.ki[1]['start_id'] = 'old'
        self.assertFalse(n.start_bereit())
        n.ki[1]['start_id'] = '1'
        saved = n.scans.pop('/scan1')
        self.assertFalse(n.start_bereit())
        n.scans['/scan1'] = saved
        self.assertTrue(n.start_bereit())

    def test_supervised_start_waits_for_sensor_readiness_then_acknowledges_obstacle_hold(self):
        for readiness in (None, False):
            with self.subTest(readiness=readiness):
                n = self.node()
                self.send(n, request())
                if readiness is None:
                    n.ki[1].pop('sensoren_bereit')
                else:
                    n.ki[1]['sensoren_bereit'] = readiness
                n.ki[1].update(aktion='stopp', grund='Klotz')
                n.steuern()
                waiting = json.loads(n.pub_status.letzte.data)
                self.assertFalse(waiting['bereit'])
                self.assertFalse(waiting['drive'])
                self.assertEqual(n.pub.letzte.linear.x, 0.)
                # Neue echte Sensorbestaetigung ist vom Fahrwunsch getrennt.
                n.ki[1]['sensoren_bereit'] = True
                self.send(n, request())
                n.steuern()
                acknowledged = json.loads(n.pub_status.letzte.data)
                self.assertTrue(acknowledged['bereit'])
                self.assertTrue(acknowledged['drive'])
                self.assertEqual(n.pub.letzte.linear.x, 0.)
                self.assertIn('Klotz', acknowledged['status'])

    def test_active_operation_remains_active_during_obstacle_hold(self):
        n = self.node()
        self.send(n, request())
        with mock.patch.object(n, 'entscheide', return_value=(0., 0., 0., 'Klotz')):
            n.steuern()
        st = json.loads(n.pub_status.letzte.data)
        self.assertTrue(st['drive'])
        self.assertEqual(n.pub.letzte.linear.x, 0)
        self.assertIn('bewegung', st)

    def test_heartbeat_timeout_zeroes_actual_publisher_and_requires_new_start(self):
        n = self.node()
        self.send(n, request())
        with mock.patch.object(n, '_wunsch', return_value=(.15, 0., 0., 'Linie')):
            n.steuern()
            self.assertEqual(n.pub.letzte.linear.x, .15)
            with q.spaeter(.7):
                n.steuern()
                self.assertEqual(n.pub.letzte.linear.x, 0)
            self.send(n, request())
            n.steuern()
            self.assertEqual(n.pub.letzte.linear.x, 0)

    def test_permission_hold_preserves_concrete_sensor_reason(self):
        for requested in (False, True):
            n = self.node()
            if requested:
                self.send(n, request())
            n.scans.pop('/scan1')
            n.steuern()
            status = json.loads(n.pub_status.letzte.data)['status']
            self.assertIn('KEIN LIDAR', status)
            self.assertIn('/scan1', status)
            self.assertIn('START WARTET' if requested else 'BEDIEN-STOPP', status)
            self.assertEqual(n.pub.letzte.linear.x, 0.)

    def test_active_publisher_stops_for_sensor_fault_with_current_permission_path(self):
        for fault in ('missing', 'quality', 'geometry'):
            with self.subTest(fault=fault):
                n = self.node()
                self.send(n, request())
                with mock.patch.object(n, '_wunsch', return_value=(.15, 0., 0., 'Linie')):
                    n.steuern()
                    self.assertEqual(n.pub.letzte.linear.x, .15)
                    self.assertTrue(json.loads(n.pub_status.letzte.data)['drive'])
                    self.send(n, request())
                    n.ki = (time.time(), n.ki[1])
                    if fault == 'missing':
                        n.scans.pop('/scan1')
                    elif fault == 'quality':
                        invalid = c.message(1)
                        invalid.ranges = [0.] * len(invalid.ranges)
                        n.on_scan(invalid, '/scan1', 1)
                    else:
                        n._p['scan_einbau_quelle'] = ['gemessen', 'unbekannt']
                    n.steuern()
                status = json.loads(n.pub_status.letzte.data)
                self.assertEqual(n.pub.letzte.linear.x, 0.)
                self.assertTrue(status['drive'])  # Betrieb aktiv, konkretes Sensorveto.
                self.assertFalse(status['freigabeweg_ausgefallen'])
                self.assertIn('Geometrie' if fault == 'geometry' else 'LIDAR', status['status'])
                self.assertNotIn('FREIGABEWEG AUSGEFALLEN', status['status'])
                self.assertNotIn('KI-BETRIEBSKENNUNG', status['status'])

    def maneuver(self, n):
        self.send(n, request())
        n.steuern()
        n.ki[1].update(aktion='manoever', aufnahme=time.time(),
                      manoever={'lin': -.05, 'quer': 0., 'dreh': 0.},
                      raeumfreigabe=dict(request(), auftrag_id='block-1', ziel_id='block-target-1', phase='rueckfahrt', zugelassen=True))

    def test_bound_clearing_reverse_reaches_real_hull_guard(self):
        n = self.node()
        self.maneuver(n)
        with mock.patch.object(n, 'notbremse', wraps=n.notbremse) as guard:
            n.steuern()
        self.assertEqual(n.pub.letzte.linear.x, -.05)
        self.assertEqual(json.loads(n.pub_status.letzte.data)['aktionsstatus']['status'], 'zugelassen')
        guard.assert_any_call(-.05, 0., 0.)
        n.ki[1]['raeumfreigabe']['generation'] = 0
        n.steuern()
        self.assertEqual(n.pub.letzte.linear.x, 0.)

    def test_bound_clearing_maneuver_still_stops_for_measured_second_object(self):
        n = self.node()
        self.maneuver(n)
        c.feed(n, distance=.21)
        n.steuern()
        self.assertEqual(n.pub.letzte.linear.x, 0.)
        feedback = json.loads(n.pub_status.letzte.data)['aktionsstatus']
        self.assertEqual(feedback['status'], 'verworfen')
        self.assertEqual(feedback['auftrag_id'], 'block-1')
        self.assertEqual(feedback['phase'], 'rueckfahrt')

    def test_standard_nonclearing_maneuver_keeps_existing_path(self):
        n = self.node()
        n._p['begleiteter_fahrbetrieb'] = False
        n._p['obstacle_check'] = False
        n.ki[1].update(aktion='manoever', aufnahme=time.time(), manoever={'lin': -.05})
        self.assertEqual(n._wunsch()[0], -.05)

    def test_late_command_from_old_start_cannot_move_even_with_overridden_wish(self):
        n = self.node()
        self.send(n, request())
        n.steuern()
        n.ki[1]['start_id'] = 'old'
        with mock.patch.object(n, 'entscheide', return_value=(.15, 0., 0., 'Linie')):
            n.steuern()
        self.assertEqual(n.pub.letzte.linear.x, 0.)


if __name__ == '__main__':
    unittest.main()
