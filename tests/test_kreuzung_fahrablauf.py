#!/usr/bin/env python3
"""Vorhandener geometrischer Fahrpfad mit ROS-Attrappen; keine B2-/Geraeteabnahme."""
import io
import json
import math
from pathlib import Path
import signal
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
for pfad in ('tests/attrappen', 'line_follower', 'ki', 'panel'):
    sys.path.insert(0, str(ROOT / pfad))
import line_follower as lf  # noqa: E402
import panel  # noqa: E402
from entscheider import Entscheider  # noqa: E402
from lidar_testdaten import geometrie  # noqa: E402
from test_kreuzung import bild_bei_pose  # noqa: E402


class Fahrablauf(unittest.TestCase):
    def setUp(self):
        self.t = 1800000000.0
        self.uhr = patch('time.time', side_effect=lambda: self.t)
        self.uhr.start()
        self.addCleanup(self.uhr.stop)
        self.n = lf.LineFollower()
        geometrie(self.n)
        self.n._p.update(drive=True, show=False, publish_image=False)
        self.e = Entscheider()
        self.nr = 0
        self.pose = (0.0, 0.0, 0.0)
        self.welt = [((0.0, 0.0), (0.9, 0.0)), ((0.36, 0.0), (0.36, 0.6))]

    def header(self):
        t = self.t - 0.01
        return types.SimpleNamespace(frame_id='base_link', stamp=types.SimpleNamespace(
            sec=int(t), nanosec=int((t % 1) * 1e9)))

    def scans(self, nah=False):
        for topic, index in (('/scan0', 0), ('/scan1', 1)):
            ranges = [2.0] * 360
            if nah:
                ranges[177:184] = [0.10] * 7
            self.n.on_scan(types.SimpleNamespace(ranges=ranges, angle_min=-math.pi,
                angle_increment=math.pi / 180, angle_max=math.pi - math.pi / 180,
                range_min=0.05, range_max=12.0, header=self.header()), topic, index)

    def schritt(self, pose=None, nah=False, ampel=None, bild=True):
        self.t += 0.1
        self.nr += 1
        if pose is not None:
            self.pose = pose
        # Vorgegebene synthetische Pose, keine simulierte/gemessene Fahrphysik.
        self.n.gedaechtnis.pose = list(self.pose)
        self.n.gedaechtnis.verlauf.clear()
        self.n.letzte_steuerung = self.t  # kein erfundener Bewegungsfortschritt aus Testlaufzeit
        self.scans(nah)
        if bild:
            self.n.on_image(types.SimpleNamespace(header=self.header(),
                img=bild_bei_pose(self.welt, self.pose)))
        b = self.e.update(self.t, dict(bild_nr=self.nr, bild_zeit=self.t, aufnahme=self.t,
            objekte=[], ampel=ampel, stoppschild=False, lidar=0.10 if nah else float('inf'),
            tiefe_hindernis=False, lidar_hinten=2.0))
        self.n.on_ki(types.SimpleNamespace(data=json.dumps(b)))
        self.n.steuern()
        cmd = self.n.pub.letzte
        return (cmd.linear.x, cmd.linear.y, cmd.angular.z)

    def abbiegend(self):
        # Nur RNG deterministisch; Bilderkennung und Wahlbindung laufen produktiv.
        with patch.object(self.n.sucher.zufall, 'choice', side_effect=lambda a: max(a, key=lambda p: p[0])):
            self.assertGreater(self.schritt()[0], 0)
        self.assertIsNotNone(self.n.sucher.wahl)
        cmd = self.schritt((0.30, 0.02, math.pi / 6))
        self.assertGreater(cmd[0], 0)
        self.assertGreater(abs(cmd[2]), 0.01)
        return self.n.sucher.wahl

    def ausfahrt(self):
        self.schritt((0.36, 0.04, math.pi / 3))
        self.schritt((0.36, 0.12, math.pi / 2))
        for _ in range(20):
            cmd = self.schritt((0.36, 0.30, math.pi / 2))
        self.assertIsNone(self.n.sucher.wahl)
        self.assertTrue(self.n.linie_gesehen)
        self.assertGreater(cmd[0], 0)

    def test_lidar_halt_wahl_und_wiederaufnahme(self):
        wahl = self.abbiegend()
        for _ in range(3):
            self.assertEqual(self.schritt(nah=True), (0, 0, 0))
            self.assertEqual(self.n.sucher.wahl, wahl)
            self.assertIn('NOTBREMSE', self.n.status_text)
            self.assertTrue(self.n.gedaechtnis.linie(0.3)['gefunden'])
        # Freier Scan allein ersetzt kein frisches Kamerabild.
        self.t += 1.0
        self.assertEqual(self.schritt(bild=False), (0, 0, 0))
        self.assertGreater(self.schritt()[0], 0)
        self.assertEqual(self.n.sucher.wahl, wahl)
        self.ausfahrt()

    def test_lokale_lidar_sperre_trotz_noch_fahrender_ki(self):
        wahl = self.abbiegend()
        self.assertEqual(self.n.ki[1]['aktion'], 'fahren')
        self.t += 0.05
        self.scans(nah=True)
        self.n.letzte_steuerung = self.t
        self.n.steuern()  # KI hat den neuen Scan noch nicht verarbeitet
        cmd = self.n.pub.letzte
        self.assertEqual((cmd.linear.x, cmd.linear.y, cmd.angular.z), (0, 0, 0))
        self.assertIn('NOTBREMSE', self.n.status_text)
        self.assertEqual(self.n.sucher.wahl, wahl)
        self.assertTrue(self.n.gedaechtnis.linie(0.3)['gefunden'])
        self.assertGreater(self.schritt()[0], 0)
        self.ausfahrt()

    def test_rot_im_abbiegen_bindet_bis_gruen_auch_bei_freiem_lidar(self):
        wahl = self.abbiegend()
        self.schritt(ampel='rot')
        self.assertEqual(self.schritt(ampel='rot'), (0, 0, 0))
        self.assertTrue(self.e.ampel_halt)
        for _ in range(60):
            self.assertEqual(self.schritt(), (0, 0, 0))
            self.assertEqual(self.n.sucher.wahl, wahl)
        self.schritt(ampel='gruen', nah=True)
        self.assertEqual(self.schritt(ampel='gruen', nah=True), (0, 0, 0))
        self.assertFalse(self.e.ampel_halt)
        while self.t + 0.1 < self.e.hindernis_bis:
            self.assertEqual(self.schritt(ampel='gruen'), (0, 0, 0))
        self.schritt(ampel='gruen')
        cmd = self.schritt(ampel='gruen')
        self.assertGreater(cmd[0], 0, self.n.status_text)
        self.ausfahrt()

    def test_start_quittiert_rot_erst_mit_aktiver_fahrt(self):
        self.abbiegend()
        self.schritt(ampel='rot')
        self.assertEqual(self.schritt(ampel='rot'), (0, 0, 0))
        self.e.fahrt_aktiv = False
        self.schritt()
        self.e.fahrt_aktiv = True
        self.assertEqual(self.schritt(), (0, 0, 0))
        self.e.fahrt_aktiv = False
        self.e.kommando(self.t, 'start')
        self.schritt()
        self.assertTrue(self.e.ampel_halt)
        self.e.fahrt_aktiv = True
        self.assertGreater(self.schritt()[0], 0)
        self.assertFalse(self.e.ampel_halt)
        self.ausfahrt()

    def test_panel_stopp_beendet_fahrprozess_ohne_wahltransfer(self):
        self.abbiegend()
        # Echter Handler und Prozesse.stopp; nur HTTP-I/O, POSIX-Signaltransport
        # und ROS-Executor sind ersetzt. Kein echter Prozess/Geraet wird beendet.
        pn = panel.PanelNode(types.SimpleNamespace(kein_netz=True))
        prozesse = panel.Prozesse()
        pr = Mock(pid=12345)
        pr.poll.return_value = None
        prozesse.p['fahren'] = pr
        handler, _ = panel.mache_handler(pn, prozesse)
        request = handler.__new__(handler)
        request.path = '/api/stopp'
        request.client_address = ('127.0.0.1', 1234)
        request.headers = {'Content-Type': 'application/json', 'Content-Length': '2'}
        request.rfile = io.BytesIO(b'{}')
        request._senden = Mock()
        executor = Mock()

        def ende(sekunden):
            if sekunden == 0.03:
                raise KeyboardInterrupt  # Signalzustellung am laufenden Hauptloop

        def warten(timeout):
            with patch.object(lf, 'signale_abfangen'), patch.object(lf, 'laeuft_schon', return_value=False), \
                 patch.object(lf, 'LineFollower', return_value=self.n), \
                 patch.object(lf, 'MultiThreadedExecutor', return_value=executor), \
                 patch.object(lf.threading, 'Thread'), patch.object(lf.cv2, 'destroyAllWindows'), \
                 patch('time.sleep', side_effect=ende), \
                 patch.object(self.n, 'destroy_node') as destroy:
                vorher = self.n.pub.n
                with patch.object(self.n.pub, 'publish', wraps=self.n.pub.publish) as publish:
                    lf.main()
                    for call in publish.call_args_list:
                        cmd = call.args[0]
                        self.assertEqual((cmd.linear.x, cmd.linear.y, cmd.angular.z), (0, 0, 0))
                self.assertEqual(self.n.pub.n - vorher, 5)
                self.assertEqual(self.n.pub.letzte.linear.x, 0)
                self.assertEqual(self.n.pub.letzte.angular.z, 0)
                destroy.assert_called_once()
            pr.poll.return_value = 0

        pr.wait.side_effect = warten
        with patch.object(panel.os, 'killpg', create=True) as kill:
            handler.do_POST(request)
            kill.assert_called_once_with(12345, signal.SIGINT)
        self.assertIn('Gestoppt', request._senden.call_args.args[2].decode())
        self.assertEqual(pn.pubs['/cmd_vel'].letzte.linear.x, 0)
        self.assertEqual(pn.pubs['/cmd_vel'].n, 10)
        self.assertFalse(prozesse.laeuft('fahren'))
        executor.shutdown.assert_called_once()
        # Ohne neuen Prozess existiert keine fortsetzbare Fahrt. Eine neue Node
        # besitzt die alte Wahl nicht; START darf hier keinen Asttransfer erfinden.
        neu = lf.LineFollower()
        self.assertIsNone(neu.sucher.wahl)
        self.assertFalse(neu.gedaechtnis.linie(0.3)['gefunden'])


if __name__ == '__main__':
    unittest.main()
