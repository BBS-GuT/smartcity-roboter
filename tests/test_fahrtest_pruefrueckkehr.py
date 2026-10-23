"""Bound inspection return keeps source, epoch, target and stationary guards."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'ki'), str(ROOT / 'lib')]
from ablaeufe import Wegraeumen
from entscheider import STANDARD
from fahrtest import befehl_sichern


class InspectionReturn(unittest.TestCase):
    def setUp(self):
        self.betrieb = dict(session_id='panel', generation=1, start_id='start', betrieb_freigegeben=True)
        self.w = dict(betrieb=self.betrieb, aktionsquittung_pflicht=True,
                      raeumziel_id='target', raeumziel_freigegeben=True,
                      raeum_umgebung_frei=True, chassis_frei=True,
                      blick='pruef', strecke_gemessen=True, raeum_stillstand=True,
                      lidar=float('inf'), tiefe_gueltig=True, tiefe_hindernis=False,
                      tiefe_aufnahme=110., tiefe_empfang=20., aufnahme=110.)
        self.a = Wegraeumen(100., dict(STANDARD))
        self.a.phase, self.a.ziel_id = 'pruefblick', 'target'
        self.a.arm_bewegt = True
        self.a.pruef_bilder = self.a.pruef_tiefe = 0
        self.w['raeum_auftrag_id'] = self.a.auftrag_id
        self.command = self.a.schritt(110., self.w)

    def checked(self, w=None, command=None):
        return befehl_sichern(command or self.command, w or self.w, 110.1, 20.1, False)

    def test_actual_inspection_return_is_authorised_and_committed_only_on_ack(self):
        self.assertEqual(self.command['arm'], {'pose':'fahrstellung'})
        self.assertEqual(self.a.phase, 'pruefblick')
        allowed = self.checked()
        self.assertEqual(allowed['arm'], {'pose':'fahrstellung'})
        self.assertTrue(allowed['raeumfreigabe']['zugelassen'])
        self.a.schritt(110.2, dict(self.w, aktionsstatus=dict(allowed['raeumfreigabe'], status='ausgefuehrt')))
        self.assertEqual(self.a.phase, 'pruef_zurueck')

    def test_invalid_sources_target_motion_and_epoch_remain_vetoes_without_progress(self):
        for change in (dict(raeum_auftrag_id='other'), dict(raeum_stillstand=False), dict(strecke_gemessen=False), dict(lidar=None),
                       dict(tiefe_gueltig=False), dict(tiefe_aufnahme=109.), dict(tiefe_empfang=19.),
                       dict(aufnahme=109.), dict(raeumziel_id='other'), dict(raeumziel_freigegeben=False),
                       dict(raeum_umgebung_frei=False), dict(chassis_frei=False),
                       dict(betrieb=dict(self.betrieb, generation=2)),
                       dict(betrieb=dict(self.betrieb, betrieb_freigegeben=False))):
            with self.subTest(change=change):
                denied = self.checked(w=dict(self.w, **change))
                self.assertIsNone(denied['arm'])
                self.a.schritt(110.2, dict(self.w, aktionsstatus=denied['aktionsstatus']))
                self.assertEqual(self.a.phase, 'pruefblick')

    def test_exception_cannot_authorise_another_arm_or_motor_command(self):
        for extra in (dict(arm={'pose':'pruefblick'}), dict(arm={'pose':'fahrstellung','greifer':'auf'}),
                      dict(arm={'winkel':[90]*6}), dict(manoever={'lin':-.1}), dict(aktion='manoever')):
            self.assertIsNone(self.checked(command=dict(self.command, **extra))['arm'])


if __name__ == '__main__':
    unittest.main()
