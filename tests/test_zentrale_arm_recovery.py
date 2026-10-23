"""STOPP/manual panel pose/new real depth -> KI readiness -> conscious START."""
import json
import sys
import time
import types
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_lidar_fusion_verbraucher as c
import test_panel_betrieb as panel_test
from tiefe import Bodenmodell


class Recovery(unittest.TestCase):
    def setUp(self):
        self.panel = panel_test.PanelLifecycle()
        self.panel.setUp()
        self.addCleanup(self.panel.doCleanups)
        self.panel.node.arm = panel_test.panel.armlib.Arm(self.panel.node)
        self.z = c.q.zentrale.Zentrale()
        self.z.pub_bild.get_subscription_count = lambda: 0
        c.configure(self.z)
        self.z._p.update(begleiteter_fahrbetrieb=True, led_ersatz=False, form_ersatz=False)
        with np.load(Path(__file__).resolve().parents[1] / 'lib' / 'bodenreferenz_rm01.npz') as data:
            self.meta = json.loads(str(data['metadaten'].item()))
            self.depth = data['referenz_tiefe'][0].repeat(4, 0).repeat(4, 1)
        self.z.posen['fahrstellung'] = self.meta['pose']
        model = Bodenmodell(self.meta['kamera'])
        model.lade_referenz(Path(__file__).resolve().parents[1] / 'lib' / 'bodenreferenz_rm01.npz', self.meta['pose'])
        self.z.kalibriertes_bodenmodell = model
        e = self.z.entscheider
        e.arm_zurueck_noetig = True
        e.arm_recovery_seit = time.time() - 1
        # An old matching pose must never clear the aborted-arm latch.
        self.z.arm_beobachter.winkel = list(self.meta['pose'])
        self.z.arm_beobachter.zeit = time.time() - 10
        self.z.arm_beobachter.dauer = 2
        self.lf = c.q.linienfolger()
        c.configure(self.lf)
        c.feed(self.lf)
        self.lf._p['begleiteter_fahrbetrieb'] = True
        self.panel.node._set('lf', dict(self.lf.betrieb.status(), drive=False))

    def stop(self):
        with mock.patch.object(self.panel.node, 'stillstand'):
            self.panel.post('stopp')
        self.assertTrue(self.lf.betrieb.empfang(self.panel.node.betrieb))
        status = dict(self.lf.betrieb.status(), drive=False)
        self.panel.node._set('lf', status)
        self.z.linie_status = dict(status, _zeit=time.time())

    def start(self):
        self.panel.node._set('lf', dict(self.lf.betrieb.status(), drive=False))
        self.panel.post('start')
        self.assertFalse(self.panel.node.betrieb['angefordert'])
        self.assertTrue(self.lf.betrieb.empfang(self.panel.node.betrieb))
        self.panel.node._set('lf', dict(self.lf.betrieb.status(), drive=False))
        self.panel.node.betrieb_senden()
        self.assertTrue(self.panel.node.betrieb['angefordert'])
        self.assertTrue(self.lf.betrieb.empfang(self.panel.node.betrieb))
        self.z._kommando(self.panel.node.ki_kommando_pub.letzte)
        self.z.linie_status = dict(self.lf.betrieb.status(), _zeit=time.time(), drive=False)

    def images(self, old=False):
        now, mono = time.time(), time.monotonic()
        def image(data, encoding):
            stamp = now - (4 if old else .02)
            return types.SimpleNamespace(img=data, encoding=encoding,
                header=types.SimpleNamespace(frame_id=self.meta['frame'],
                    stamp=types.SimpleNamespace(sec=int(stamp), nanosec=int((stamp % 1)*1e9))))
        self.z.linie_status['_zeit'] = now
        self.z.tiefeninfo = (self.meta['k'], self.depth.shape, self.meta['frame'], mono)
        c.feed(self.z)
        with mock.patch.object(self.z, '_bild_senden'):
            self.z._auswerten(image(np.zeros((480,640,3), np.uint8), 'bgr8'),
                             image(self.depth, '32FC1'), (mono, mono))

    def test_manual_panel_return_and_new_images_allow_only_a_new_start(self):
        self.stop()
        self.panel.node._set('ki', {'aktion': 'stopp'})
        self.start()
        self.images()
        self.assertTrue(self.z.entscheider.arm_zurueck_noetig)
        self.assertFalse(c.q.befehl(self.z)['sensoren_bereit'])
        lf = self.lf
        lf.ki = (time.time(), c.q.befehl(self.z))
        self.assertFalse(lf.start_bereit())
        self.stop()  # Waiting START must be revoked before manual panel movement.
        c.q.befehl(self.z)
        # Manual pose is the existing stopped-panel API, with real Arm validation.
        answer = self.panel.post('arm_pose', {'winkel': self.meta['pose'], 'zeit': 2000})
        self.assertIn('Arm faehrt', answer)
        self.z.arm_beobachter._sim(self.panel.node.arm.pub.letzte)
        self.images()
        self.assertTrue(self.z.entscheider.arm_zurueck_noetig)
        with c.q.spaeter(3):
            self.images(old=True)
            self.assertTrue(self.z.entscheider.arm_zurueck_noetig)
            self.images()
            self.assertFalse(self.z.entscheider.arm_zurueck_noetig)
            self.assertTrue(c.q.befehl(self.z)['sensoren_bereit'])
            c.feed(lf)
            lf.bild_zeit, lf.stempel_ok = time.time(), True
            self.assertFalse(lf.betrieb.pruefen(True))
            self.start()
            lf.ki = (time.time(), c.q.befehl(self.z))
            self.assertTrue(lf.start_bereit())
            self.assertTrue(lf.betrieb.pruefen(lf.start_bereit()))

    def test_rejected_manual_pose_never_creates_recovery_evidence(self):
        self.stop()
        old = self.z.arm_beobachter.zeit
        answer = self.panel.post('arm_pose', {'winkel': [999]*6, 'zeit': 2000})
        self.assertIn('ausserhalb', answer)
        self.assertEqual(self.z.arm_beobachter.zeit, old)
        with c.q.spaeter(3):
            self.images()
            self.assertTrue(self.z.entscheider.arm_zurueck_noetig)
            self.assertFalse(c.q.befehl(self.z)['sensoren_bereit'])


if __name__ == '__main__':
    unittest.main()
