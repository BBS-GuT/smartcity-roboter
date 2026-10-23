"""Auftragsfreigabe und echte Rueckmeldung, ohne ROS oder Geraet."""
import sys
import unittest
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'ki'), str(ROOT / 'lib')]
from ablaeufe import Wegraeumen, Zebrastreifen
from entscheider import Entscheider, STANDARD
from fahrtest import befehl_sichern, raeumfreigabe_gueltig
from lidar_fusion import Sicht


class Raeumfreigabe(unittest.TestCase):
    def setUp(self):
        self.betrieb = dict(session_id='boot', generation=1, start_id='start', betrieb_freigegeben=True)
        self.w = dict(betrieb=self.betrieb, aktionsquittung_pflicht=True,
                      objekt=dict(ziel_id='klotz', bestaetigt=True), raeumziel_id='klotz',
                      raeumziel_freigegeben=True, raeum_umgebung_frei=True, chassis_frei=True,
                      lidar=.18, blick='fahr', tiefe_gueltig=True, tiefe_hindernis=True,
                      tiefe_aufnahme=100., tiefe_empfang=20., aufnahme=100.)
        self.a = Wegraeumen(100., dict(STANDARD))
        self.a.phase, self.a.nr, self.a.warte = 'ausfuehren', -1, 0.
        self.a.schritte = [('heben', [90, 153, 0, 0, 90, 130], 1.),
                          ('fahren', [90, 153, 0, 0, 90, 30], 1.)]

    def command(self):
        return self.a.schritt(100., self.w)

    def checked(self, command, **changes):
        return befehl_sichern(command, dict(self.w, **changes), 100.1, 20.1, True)

    def test_stationary_target_contact_requires_exact_order_and_environment(self):
        b = self.command()
        allowed = self.checked(b)
        self.assertIsNotNone(allowed['arm'])
        self.assertTrue(raeumfreigabe_gueltig(allowed, self.betrieb))
        for change in (dict(raeumziel_id='zweiter'), dict(raeumziel_freigegeben=False),
                       dict(raeum_umgebung_frei=False), dict(chassis_frei=False), dict(lidar=None),
                       dict(betrieb=dict(self.betrieb, generation=2)),
                       dict(betrieb=dict(self.betrieb, betrieb_freigegeben=False))):
            with self.subTest(change=change):
                denied = self.checked(b, **change)
                self.assertIsNone(denied['arm'])
                self.assertEqual(denied['aktionsstatus']['status'], 'verworfen')

    def test_veto_and_permission_alone_never_advance_arm_sequence(self):
        b = self.command()
        denied = self.checked(b, chassis_frei=False)
        for status in ('verworfen', 'zugelassen'):
            w = dict(self.w, aktionsstatus=dict(denied['aktionsstatus'], status=status))
            same = self.a.schritt(104., w)
            self.assertEqual(same['raeumfreigabe'], b['raeumfreigabe'])
            self.assertEqual(self.a.nr, -1)
            self.assertIsNone(self.a.ergebnis)

    def test_arm_phase_transition_is_only_committed_after_execution_ack(self):
        self.a.phase = 'planen'
        self.a.plan = {'schritte': self.a.schritte}
        before = (self.a.phase, self.a.nr, self.a.seit, self.a.warte, self.a.arm_bewegt)
        b = self.command()
        self.assertEqual((self.a.phase, self.a.nr, self.a.seit, self.a.warte, self.a.arm_bewegt), before)
        denied = self.checked(b, chassis_frei=False)
        self.a.schritt(105., dict(self.w, aktionsstatus=denied['aktionsstatus']))
        self.assertEqual((self.a.phase, self.a.nr, self.a.seit, self.a.warte, self.a.arm_bewegt), before)
        ack = dict(b['raeumfreigabe'], status='ausgefuehrt')
        self.a.schritt(106., dict(self.w, aktionsstatus=ack))
        self.assertEqual((self.a.phase, self.a.nr, self.a.arm_bewegt), ('ausfuehren', 0, True))

    def test_final_permission_requires_target_id(self):
        b = self.checked(self.command())
        b['raeumfreigabe'].pop('ziel_id')
        self.assertFalse(raeumfreigabe_gueltig(b, self.betrieb))

    def test_target_flags_cannot_override_invalid_depth_or_rgb_pair(self):
        b = self.command()
        for change in (dict(tiefe_aufnahme=99.), dict(tiefe_empfang=19.),
                       dict(tiefe_gueltig=False), dict(aufnahme=99.)):
            denied = self.checked(b, **change)
            self.assertIsNone(denied['arm'])
            self.assertFalse(denied['raeumfreigabe']['zugelassen'])

    def test_bound_plan_is_specific_to_the_original_order(self):
        b = self.command()
        bound = dict(auftrag_id=b['raeumfreigabe']['auftrag_id'], ziel_id='klotz')
        self.assertIsNotNone(self.checked(b, blick='arm', raeum_planbindung=bound)['arm'])
        bound['auftrag_id'] = 'anderer-auftrag'
        self.assertIsNone(self.checked(b, blick='arm', raeum_planbindung=bound)['arm'])

    def test_only_matching_execution_ack_starts_segment_timer(self):
        b = self.command()
        wrong = dict(b['raeumfreigabe'], phase='other', status='ausgefuehrt')
        self.assertEqual(self.a.schritt(102., dict(self.w, aktionsstatus=wrong)), b)
        ack = dict(b['raeumfreigabe'], status='ausgefuehrt')
        wait = self.a.schritt(103., dict(self.w, aktionsstatus=ack))
        self.assertIsNone(wait['arm'])
        self.assertEqual(self.a.nr, 0)
        next_command = self.a.schritt(104.1, self.w)
        self.assertNotEqual(next_command['raeumfreigabe']['phase'], b['raeumfreigabe']['phase'])
        self.assertEqual(self.a.nr, 0)  # Zweites Segment erst angefordert.

    def test_missing_execution_ack_is_failure_not_success(self):
        self.command()
        self.assertIsNone(self.a.schritt(111., self.w))
        self.assertEqual(self.a.ergebnis, 'fehler')

    def test_estimated_odometry_cannot_move_the_return_distance(self):
        self.a.phase = 'rueckweg'
        self.a._gefahren(dict(strecke=0., strecke_gemessen=False), 100., -.1)
        ds = self.a._gefahren(dict(strecke=-.3, strecke_gemessen=False), 103., -.1)
        self.assertEqual(ds, 0.)

    def test_stop_or_epoch_change_discards_existing_order(self):
        for state in (dict(self.betrieb, generation=2), dict(self.betrieb, betrieb_freigegeben=False)):
            e = Entscheider()
            e.ablauf = self.a
            e.betriebsepoche = ('boot', 1, 'start')
            e.update(100., dict(betrieb=state, lidar=None))
            self.assertIsNot(e.ablauf, self.a)

    def test_rear_hole_alone_is_allowed_but_actual_hit_still_stops(self):
        view = Sicht((), (.2, .2, .15, .15), np.zeros((0, 2)))
        self.assertIsNone(view.hinten(.15))
        self.assertGreater(view.hinten(.15, abdeckung_pflicht=False), .2)
        self.assertIsNone(view.schutz(['hinten'], .12, abdeckung_pflicht=False))
        hit = Sicht((), view.hull, np.array([[-.23, 0.]]))
        self.assertAlmostEqual(hit.hinten(.15, abdeckung_pflicht=False), .23)
        self.assertIn('NOTBREMSE', hit.schutz(['hinten'], .12, abdeckung_pflicht=False))

    def test_crossing_hole_exception_never_replaces_missing_source(self):
        a = Zebrastreifen(100., dict(STANDARD), .3)
        self.assertIsNone(a._zone_ungemessen(dict(lidar_luecken_ignorieren=True,
                                                 lidar_xy=np.zeros((0, 2)))))
        self.assertIsNotNone(a._zone_ungemessen(dict(lidar_luecken_ignorieren=True,
                                                    lidar_xy=None)))


if __name__ == '__main__':
    unittest.main()
