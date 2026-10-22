"""Synthetische Bewegung mit echten Kartierer-Eingaben, keine Geraeteabnahme."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
import karte as K
import kartierer as KR


def bogen(ausfall, v=0.15, omega=0.5, nur_twist=False):
    kr = KR.Kartierer(K.Karte('/nicht/benutzt'), {'selbst_kalibrieren': False})
    start = 1000.0
    events = [(start + i / 50, 'imu') for i in range(300)]
    events += [(start + i / 20 + 0.003, 'odom') for i in range(120)]
    for t, art in sorted(events):
        elapsed = t - start
        if 2.0 <= elapsed < 3.5 and art in ausfall:
            continue
        if art == 'imu':
            kr.imu(t, {'stamp': t, 'g': [0., 0., omega], 'a': [0., 0., 9.8]})
        else:
            x, y, w = referenz(elapsed, v, omega)
            daten = {'stamp': t, 'vx': v, 'vy': 0., 'wz': omega}
            if not nur_twist:
                daten.update(x=x, y=y, w=w)
            kr.odom(t, daten)
    return kr, kr.verlauf[-1][0] - start


def referenz(t, v, omega):
    if not omega:
        return v * t, 0., 0.
    return (v / omega * math.sin(omega * t),
            v / omega * (1 - math.cos(omega * t)), K.winkel(omega * t))


class OdomLueckeTest(unittest.TestCase):
    def pruefe(self, ausfall, omega, v=0.15):
        kr, t = bogen(ausfall, v, omega)
        self.assertAlmostEqual(t, 5.953, places=9)
        self.assertEqual(len(kr.bewegung_puffer), 2)
        x, y, w = referenz(t, v, omega)
        # Vor Produktfix festgelegt: hoechstens ein Odomtakt Winkelversatz
        # (0.5 rad/s * 0.05 s = 0.025 rad). Auf 0.9 m Bogenlaenge
        # erlaubt das konservativ 0.0225 m plus 0.00045 m Startversatz.
        # Enger fuer diesen rauschfreien Pose-Delta-Fall: 0.008 m / 0.01 rad,
        # inkl. bekannter gemeinsamer Luecke (0.0064 m / 0.0085 rad).
        # Der urspruengliche Odomfehler von 0.17 m ist klar ausgeschlossen.
        fehler = math.hypot(kr.roboter[0] - x, kr.roboter[1] - y)
        winkel = abs(K.winkel(kr.roboter[2] - w))
        print(f'{sorted(ausfall)} v={v} omega={omega}: t={t:.9f}, '
              f'Position={fehler:.9f} m, Winkel={winkel:.9f} rad')
        self.assertLess(fehler, 0.008)
        self.assertLess(winkel, 0.01)

    def test_odom_ausfall_beide_drehrichtungen(self):
        for omega in (-0.5, 0.5):
            with self.subTest(omega=omega):
                self.pruefe({'odom'}, omega)

    def test_ohne_luecke(self):
        for omega in (-0.5, 0.5):
            with self.subTest(omega=omega):
                self.pruefe(set(), omega)

    def test_gemeinsame_luecke(self):
        for omega in (-0.5, 0.5):
            with self.subTest(omega=omega):
                self.pruefe({'odom', 'imu'}, omega)

    def test_stillstand(self):
        for ausfall in (set(), {'odom'}, {'odom', 'imu'}):
            with self.subTest(ausfall=ausfall):
                self.pruefe(ausfall, 0., 0.)

    def test_twist_fallback_bleibt_unveraendert(self):
        # Enge Bereichskontrolle, keine Genauigkeitsbehauptung fuer Twist:
        # gemessene Software-Ausgaben der f188a00-Basis mit denselben Eingaben.
        # Ein begrenztes vx*dt ist kein Pose-Delta im alten Odombezug und darf
        # durch die neue Pose-Bezugskorrektur nicht zusaetzlich gedreht werden.
        basis = ((set(), (0.05867850377384914, 0.5950472340684612, 2.97)),
                 ({'odom'}, (-0.004915212962879483, 0.4477489316481933, 2.97)),
                 ({'odom', 'imu'}, (0.20047801177020416, 0.5233866367543205, 2.46)))
        for ausfall, erwartet in basis:
            for richtung in (-1, 1):
                with self.subTest(ausfall=ausfall, richtung=richtung):
                    kr, _ = bogen(ausfall, omega=richtung * 0.5, nur_twist=True)
                    for ist, soll in zip(kr.roboter, (erwartet[0], richtung * erwartet[1],
                                                    richtung * erwartet[2])):
                        self.assertAlmostEqual(ist, soll, delta=1e-10)


if __name__ == '__main__':
    unittest.main()
