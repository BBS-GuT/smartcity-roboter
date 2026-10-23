"""Central adapter sends each authorised segment once and reports real send vetoes."""
import sys
import time
import types
import unittest
from pathlib import Path
from unittest import mock
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_lidar_fusion_verbraucher as c


class Segment(unittest.TestCase):
    def scene(self):
        n = c.q.zentrale.Zentrale()
        c.configure(n)
        n._p['begleiteter_fahrbetrieb'] = True
        c.feed(n)
        now, mono = time.time(), time.monotonic()
        ids = dict(session_id='panel', generation=1, start_id='start')
        n.linie_status = dict(ids, _zeit=now, drive=True, betrieb_freigegeben=True)
        obj = dict(ziel_id='target', bestaetigt=True, messzeit=mono, vor=.3, seite=0.,
                   breite=.04,hoehe=.05,region={'min':[.3,-.02,.02],'max':[.34,.02,.05]})
        n.wahrnehmung.update(bild_zeit=now,aufnahme=now,blick='fahr',tiefe_aufnahme=now,
                            tiefe_empfang=mono,tiefe_gueltig=True,tiefe_hindernis=True,
                            tiefe_objekt=obj,tiefe_objekte=[obj])
        n.odom_zeit=now
        n.odom_pose=(0.,0.,0.)
        n.odom_bewegung=(0.,0.,0.)
        n.arm=types.SimpleNamespace(fahre=mock.Mock(return_value=None))
        n.entscheider.arm_freigabe=True
        n.entscheider.ablauf=types.SimpleNamespace(name='wegraeumen', phase='ausfuehren',plan={'schritte':[],'ablage':[.1,.2,.03]},
                                                 nr=0,auftrag_id='order',ziel_id='target')
        r=dict(ids,auftrag_id='order',ziel_id='target',phase='ausfuehren:1')
        command=dict(aktion='stopp',faktor=0.,grund='Segment',arm={'winkel':[90]*6,'zeit_ms':1000},
                     manoever=None,raeumfreigabe=r)
        return n,command

    def run_segment(self,n,command):
        with mock.patch.object(n.entscheider,'update',return_value=command), mock.patch.object(n,'kamera_lage',return_value=(True,0)):
            n._entscheiden()
        return n.befehl

    def test_send_success_is_acknowledged_once_without_resending(self):
        n,command=self.scene()
        first=self.run_segment(n,command)
        self.assertEqual(first['aktionsstatus']['status'],'ausgefuehrt')
        self.run_segment(n,command)
        self.assertEqual(n.arm.fahre.call_count,1)
        self.assertEqual(first['session_id'],'panel')

    def test_arm_send_failure_is_not_execution(self):
        n,command=self.scene()
        n.arm.fahre.return_value='Servo abgewiesen'
        result=self.run_segment(n,command)
        self.assertEqual(result['aktionsstatus']['status'],'verworfen')
        self.assertIn('Servo abgewiesen',result['aktionsstatus']['grund'])

    def test_stop_and_epoch_change_prevent_old_segment(self):
        for change in ({'drive':False,'betrieb_freigegeben':False},{'generation':2}):
            n,command=self.scene()
            n.linie_status.update(change)
            result=self.run_segment(n,command)
            self.assertEqual(n.arm.fahre.call_count,0)
            self.assertIsNone(result['arm'])

    def test_old_rgb_cannot_create_bound_plan(self):
        n,command=self.scene()
        n.wahrnehmung['aufnahme']-=2
        result=self.run_segment(n,command)
        self.assertEqual(n.arm.fahre.call_count,0)
        self.assertIsNone(n.planbindung)
        self.assertEqual(result['aktionsstatus']['status'],'verworfen')

    def test_new_side_obstacle_blocks_next_bound_arm_segment(self):
        n,command=self.scene()
        self.run_segment(n,command)
        self.assertEqual(n.arm.fahre.call_count,1)
        # Camera has moved; bind to the old plan but retain current LiDAR.
        n.wahrnehmung.update(blick=None,tiefe_gueltig=False)
        command=dict(command,raeumfreigabe=dict(command['raeumfreigabe'],phase='ausfuehren:2'))
        xy=n.lidar_xy.copy()
        with mock.patch.object(n,'lidar_pruefen',side_effect=lambda: (setattr(n,'lidar_xy',
             np.vstack((xy,[[.1,.2]]))) or (float('inf'),None,float('inf')))):
            result=self.run_segment(n,command)
        self.assertEqual(n.arm.fahre.call_count,1)
        self.assertEqual(result['aktionsstatus']['status'],'verworfen')

    def test_after_release_only_measured_target_box_allows_withdrawal(self):
        for point, allowed in (([.1,.2],True),([.1,.24],False)):
            n,command=self.scene()
            command=dict(command,raeumfreigabe=dict(command['raeumfreigabe'],
                         segment_name='loslassen',segment_index=6))
            first=self.run_segment(n,command)
            self.assertEqual(first['aktionsstatus']['status'],'ausgefuehrt')
            n.wahrnehmung.update(blick=None,tiefe_gueltig=False)
            command=dict(command,raeumfreigabe=dict(command['raeumfreigabe'],phase='ausfuehren:2',
                         segment_name='Arm hoch',segment_index=7))
            xy=n.lidar_xy.copy()
            with mock.patch.object(n,'lidar_pruefen',side_effect=lambda: (setattr(n,'lidar_xy',
                 np.vstack((xy,[point]))) or (float('inf'),None,float('inf')))):
                result=self.run_segment(n,command)
            self.assertEqual(n.arm.fahre.call_count,2 if allowed else 1)
            self.assertEqual(result['aktionsstatus']['status'],'ausgefuehrt' if allowed else 'verworfen')


if __name__=='__main__':
    unittest.main()
