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
    return dict(session_id=session, generation=g, start_id=sid or str(g), angefordert=active)


class Lifecycle(unittest.TestCase):
    def test_initial_stop_and_delayed_readiness(self):
        b = Betriebsfreigabe()
        self.assertFalse(b.pruefen(True, 0))
        b.empfang(request(), 0)
        self.assertFalse(b.pruefen(False, .1))
        self.assertTrue(b.pruefen(True, .2))

    def test_stop_invalidates_old_start_and_duplicate_cannot_reenable(self):
        b = Betriebsfreigabe()
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
        b.empfang(request(), 0)
        self.assertTrue(b.pruefen(True, 0))
        self.assertFalse(b.pruefen(True, .7))
        b.empfang(request(), .8)
        self.assertFalse(b.pruefen(True, .8))
        b.empfang(request(2), .9)
        self.assertTrue(b.pruefen(True, .9))

    def test_new_panel_session_stops_and_rejects_retired_heartbeat(self):
        b = Betriebsfreigabe()
        b.empfang(request(), 0)
        self.assertTrue(b.pruefen(True, 0))
        self.assertFalse(b.empfang(request(session='new'), .1))
        b.empfang(request(0, False, 'new'), .2)
        self.assertFalse(b.pruefen(True, .2))
        self.assertFalse(b.empfang(request(), .3))
        b.empfang(request(1, True, 'new'), .4)
        self.assertTrue(b.pruefen(True, .4))


class Publisher(unittest.TestCase):
    def node(self):
        n = q.linienfolger()
        c.configure(n)
        n._p.update(drive=True, begleiteter_fahrbetrieb=True)
        c.feed(n)
        n.ki[1].update(begleiteter_fahrbetrieb=True, session_id='panel', generation=1, start_id='1')
        return n

    def send(self, n, req):
        n.on_betrieb(SimpleNamespace(data=json.dumps(req)))

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


if __name__ == '__main__':
    unittest.main()
