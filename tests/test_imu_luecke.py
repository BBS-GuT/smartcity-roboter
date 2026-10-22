"""IMU-Luecken mit echten Kartierer-Eingaben; synthetisch, keine Geraeteabnahme."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
import karte as K
import kartierer as KR


def referenz(t, v, omega):
    if not omega:
        return v * t, 0., 0.
    return (v / omega * math.sin(omega * t),
            v / omega * (1 - math.cos(omega * t)), K.winkel(omega * t))


def bogen(ausfall, omega=0.5, v=0.15, fenster=(2., 3.5), nur_twist=False):
    kr = KR.Kartierer(K.Karte('/nicht/benutzt'), {'selbst_kalibrieren': False})
    start = 1000.
    events = [(start + i / 50, 'imu') for i in range(300)]
    events += [(start + i / 20 + 0.003, 'odom') for i in range(120)]
    for t, art in sorted(events):
        if fenster[0] <= t - start < fenster[1] and art in ausfall:
            continue
        if art == 'imu':
            kr.imu(t, {'stamp': t, 'g': [0., 0., omega], 'a': [0., 0., 9.8]})
        else:
            daten = {'stamp': t, 'vx': v, 'vy': 0., 'wz': omega}
            if not nur_twist:
                daten.update(zip(('x', 'y', 'w'), referenz(t - start, v, omega)))
            kr.odom(t, daten)
    return kr, [(t - start, pose) for t, pose, *_ in kr.verlauf]


class ImuLueckeTest(unittest.TestCase):
    def pruefe(self, ausfall, omega, v=0.15, fenster=(2., 3.5)):
        kr, verlauf = bogen(ausfall, omega, v, fenster)
        t, pose = verlauf[-1]
        # Die beiden noch gepufferten Nachrichten gehoeren nicht zur Referenz.
        # Ohne IMU am Ende wird die letzte Odometrie sofort verarbeitet.
        self.assertAlmostEqual(t, 5.953, places=9)
        self.assertEqual(len(kr.bewegung_puffer), 0 if fenster[1] == 6. else 2)
        x, y, w = referenz(t, v, omega)
        fehler = math.hypot(pose[0] - x, pose[1] - y)
        winkel = abs(K.winkel(pose[2] - w))
        print(f'{sorted(ausfall)} Fenster={fenster} v={v} omega={omega}: '
              f't={t:.9f}, Position={fehler:.9f} m, Winkel={winkel:.9f} rad')
        # Vor Fix festgelegt: 8 mm / 0.01 rad bewahren die #32-Kontrollen.
        # Ein IMU-Takt liefert hoechstens 0.01 rad bzw. auf 0.9 m Bogen
        # weniger als 9 mm; hier enger als ein Odomtakt (0.025 rad).
        # Die urspruenglichen 67.285 mm / 0.1415 rad sind ausgeschlossen.
        self.assertLess(fehler, 0.008)
        self.assertLess(winkel, 0.01)
        return kr, verlauf

    def test_imu_ausfall_beide_drehrichtungen(self):
        for omega in (-0.5, 0.5):
            with self.subTest(omega=omega):
                self.pruefe({'imu'}, omega)

    def test_rueckkehr_verlauf(self):
        for omega in (-0.5, 0.5):
            with self.subTest(omega=omega):
                _, verlauf = bogen({'imu'}, omega)
                rueckkehr = [(t, pose) for t, pose in verlauf if 3.45 <= t <= 4.]
                self.assertGreater(len(rueckkehr), 8)
                for t, pose in rueckkehr:
                    # Durchgehend enger als ein Odomtakt; kein nur finaler Test.
                    self.assertLess(abs(K.winkel(pose[2] - omega * t)), 0.01)
                for (t0, p0), (t1, p1) in zip(rueckkehr, rueckkehr[1:]):
                    # Kein Nachholsprung: maximal ein IMU-Takt Zeitversatz
                    # zwischen zwei benachbarten Odometrie-Eintraegen.
                    schritt = K.winkel(p1[2] - p0[2])
                    self.assertGreaterEqual(omega * schritt, 0.)
                    self.assertLess(abs(schritt - omega * (t1 - t0)), 0.01)

    def test_kontrollen(self):
        for ausfall in (set(), {'odom'}, {'odom', 'imu'}):
            for omega in (-0.5, 0.5):
                with self.subTest(ausfall=ausfall, omega=omega):
                    self.pruefe(ausfall, omega)

    def test_stillstand(self):
        for ausfall in (set(), {'imu'}, {'odom'}, {'imu', 'odom'}):
            with self.subTest(ausfall=ausfall):
                kr, _ = self.pruefe(ausfall, 0., 0.)
                self.assertEqual(kr.roboter, (0., 0., 0.))

    def test_imu_luecke_am_beginn_und_ende(self):
        for fenster in ((0., 1.5), (4.5, 6.)):
            for omega in (-0.5, 0.5):
                with self.subTest(fenster=fenster, omega=omega):
                    self.pruefe({'imu'}, omega, fenster=fenster)

    def test_kurze_imu_luecke(self):
        # Rueckkehr vor der bisherigen 0,25-s-Lueckenmarkierung: das letzte
        # IMU-Intervall darf bereits ersetzte Odom-Zeit nicht doppelt liefern.
        for omega in (-0.5, 0.5):
            with self.subTest(omega=omega):
                self.pruefe({'imu'}, omega, fenster=(2., 2.18))

    def test_reiner_twist_bei_imu_luecke(self):
        for omega in (-0.5, 0.5):
            with self.subTest(omega=omega):
                _, normal = bogen(set(), omega, nur_twist=True)
                kr, verlauf = bogen({'imu'}, omega, nur_twist=True)
                t, pose = verlauf[-1]
                self.assertAlmostEqual(t, 5.953, places=9)
                self.assertEqual(len(kr.bewegung_puffer), 2)
                self.assertLess(abs(K.winkel(pose[2] - omega * t)), 0.01)
                # Twist integriert vx*dt statt exakter Bogensehnen. Gegen die
                # ungestoerte Twist-Kontrolle hoechstens 2 mm zusaetzlich.
                self.assertLess(math.hypot(pose[0] - normal[-1][1][0],
                                           pose[1] - normal[-1][1][1]), 0.002)
                for zeit, p in verlauf:
                    if 3.45 <= zeit <= 4.:
                        self.assertLess(abs(K.winkel(p[2] - omega * zeit)), 0.01)


if __name__ == '__main__':
    unittest.main()
