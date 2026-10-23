"""Echter Automat -> Zentrale -> finaler Publisher mit synthetischen Sensoren.

Nur Boardausgabe, Kamera-Pose und Startbereitschaft sind Geraeteattrappen;
Auftragsentscheidung, Schutzpruefung und Quittierung bleiben Produktcode.
"""
import math
import json
import time
import types
import unittest
from unittest import mock
import test_lidar_fusion_verbraucher as c


class Vollpfad(unittest.TestCase):
    def scene(self, vor):
        z, lf = c.q.zentrale.Zentrale(), c.q.lf.LineFollower()
        ids = dict(session_id='integration', generation=1, start_id='start')
        for n in (z, lf):
            c.configure(n)
            n._p.update(begleiteter_fahrbetrieb=True, drive=True, show=False, publish_image=False)
        lf.start_bereit = lambda: True
        z.arm = types.SimpleNamespace(fahre=mock.Mock(return_value=None))
        z.entscheider.arm_freigabe = True
        z.entscheider.planer = lambda obj, seite: dict(
            schritte=[('heben', [90, 153, 0, 0, 90, 130], .4),
                      ('zurueck in Fahrstellung', [90, 153, 0, 0, 90, 30], .4)],
            ablage=[.05, .4, .03])
        obj = dict(ziel_id='target', bestaetigt=True, vor=vor, seite=0., breite=.04,
                   hoehe=.05, quelle='tiefe', blick='fahr',
                   region={'min':[vor, -.02, .02], 'max':[vor+.04, .02, .05]})
        return z, lf, ids, obj

    def tick(self, scene, k, rear_hit=False):
        z, lf, ids, obj = scene
        with c.q.spaeter(k*.1):
            now, mono = time.time(), time.monotonic()
            for n in (z, lf):
                c.feed(n)
                if rear_hit:
                    msg = c.message(0)
                    i = round((math.pi-msg.angle_min)/msg.angle_increment)
                    msg.ranges[i] = .18  # Sensor x=-.1 -> Treffer hinter Huelle bei x=-.28.
                    (n._scan if hasattr(n, '_scan') else n.on_scan)(msg, '/scan0', 0)
            lf.betrieb.empfang(dict(ids, angefordert=True))
            lf.betrieb.pruefen(True)
            lf.steuern()
            z.linie_status = dict(json.loads(lf.pub_status.letzte.data), _zeit=now)
            z.odom_zeit, z.odom_pose, z.odom_bewegung = now, (0.,0.,0.), (0.,0.,0.)
            z.wahrnehmung.update(bild_nr=k, tiefe_nr=k, bild_zeit=now, aufnahme=now,
                blick='fahr', tiefe_aufnahme=now, tiefe_empfang=mono, tiefe_gueltig=True,
                tiefe_hindernis=True, tiefe_objekt=dict(obj, messzeit=mono),
                tiefe_objekte=[dict(obj, messzeit=mono)])
            with mock.patch.object(z, 'kamera_lage', return_value=(True, 0)):
                command = c.q.befehl(z)
            lf.ki = (now, command)
            lf.steuern()
            return command

    def test_stationary_grasp_uses_real_automaton_and_send_ack(self):
        scene = self.scene(.33)
        z, lf, _, _ = scene
        phases = []
        for k in range(80):
            self.tick(scene, k)
            a = z.entscheider.ablauf
            phases.append(getattr(a, 'phase', None))
            if z.arm.fahre.call_count >= 2:
                break
            time.sleep(.001)  # Reinen bestehenden Planerthread rechnen lassen.
        self.assertIn('anschauen', phases)
        self.assertIn('planen', phases)
        self.assertEqual(z.arm.fahre.call_count, 2)
        self.assertEqual(z.befehl['aktionsstatus']['status'], 'ausgefuehrt')
        self.assertEqual(lf.pub.letzte.linear.x, 0.)

    def test_real_rear_hit_vetoes_positioning_without_progress(self):
        scene = self.scene(.30)
        z, lf, _, _ = scene
        requests = []
        for k in range(65):
            b = self.tick(scene, k, rear_hit=True)
            if b.get('manoever'):
                requests.append(b)
                self.assertLess(b['manoever']['lin'], 0.)
                self.assertEqual(lf.pub.letzte.linear.x, 0.)
                feedback = json.loads(lf.pub_status.letzte.data)['aktionsstatus']
                self.assertEqual(feedback['status'], 'verworfen')
                self.assertEqual(feedback['auftrag_id'], b['raeumfreigabe']['auftrag_id'])
            time.sleep(.001)
        self.assertTrue(requests, z.befehl)
        self.assertEqual(z.arm.fahre.call_count, 0)
        self.assertEqual(z.strecke, 0.)
        self.assertEqual(z.entscheider.ablauf.phase, 'abstand')
        self.assertIsNone(z.entscheider.ablauf.ergebnis)

    def test_real_arm_send_error_cannot_commit_phase(self):
        scene = self.scene(.33)
        z = scene[0]
        z.arm.fahre.return_value = 'Servo abgewiesen'
        before = None
        for k in range(60):
            self.tick(scene, k)
            a = z.entscheider.ablauf
            if z.arm.fahre.call_count:
                state = (a.phase, getattr(a, 'nr', None), a.seit, a.arm_bewegt)
                if before is None:
                    before = state
                self.assertEqual(state, before)
                self.assertEqual(z.befehl['aktionsstatus']['status'], 'verworfen')
                self.assertIsNone(a.ergebnis)
            time.sleep(.001)
        self.assertIsNotNone(before)


if __name__ == '__main__':
    unittest.main()
