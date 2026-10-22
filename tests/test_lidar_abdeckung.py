#!/usr/bin/env python3
"""L7 (#79): Gueltige LiDAR-Punkte neben dem Fahrbereich ersetzen keine Messung IM Fahrbereich.

Ein Strahl ohne gueltige Messung (0, NaN, inf, ausserhalb) im benoetigten Bereich macht diesen unbekannt.
Nur ROS-/Publisherattrappen, kein Geraet. Aufruf: python3 tests/test_lidar_abdeckung.py
"""
import math
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lidar_qualitaet as q  # noqa: E402  (Attrappen und Helfer fuer Scans/Knoten)

lidar = q.lidar
N = 360                     # Strahl k zeigt nach k - 180 Grad (vorne = 180, links = 270, hinten = 0)


def gegenbeispiel():
    """Aus #79: vorderer Strahl ungueltig (0), allein der linke gueltig (3 m)."""
    return q.scan([0.0, 3.0], angle_min=0.0, angle_increment=math.pi / 2, range_min=0.1, range_max=6.0)


def mit_luecke(grad, wert=0.0, rest=3.0, breite=1):
    """Ueberall 'rest' m, nur um 'grad' (0 = vorne, 90 = links, 180 = hinten) 'breite' Strahlen mit 'wert'."""
    r = [rest] * N
    for k in range(breite):
        r[(180 + grad + k) % N] = wert
    return q.scan(r)


def links_kurve(radius=0.4):
    return [(radius * math.sin(a / 20), radius - radius * math.cos(a / 20)) for a in range(1, 31)]


class ReineAbdeckung(unittest.TestCase):
    def test_gegenbeispiel(self):
        m = gegenbeispiel()
        self.assertIsNone(lidar.scan_pruefen(m))                       # Scan insgesamt nicht leer (kein L1-Fall)
        self.assertEqual(lidar.naechster_vorne(m), float('inf'))       # alte Auswertung: "frei"
        self.assertIsNotNone(lidar.sektor_abdeckung(m))                # neu: vorne unbekannt
        self.assertIsNotNone(lidar.fahrschlauch_luecke(lidar.ungueltige_winkel(m)))
        self.assertIsNone(lidar.sektor_abdeckung(m, halb_deg=10.0, front_deg=90.0))   # links gemessen

    def test_gueltige_fernmessung_ist_abgedeckt(self):
        m = q.scan(3.0)
        self.assertIsNone(lidar.sektor_abdeckung(m))
        self.assertIsNone(lidar.sektor_abdeckung(m, rueckwaerts=True))
        self.assertIsNone(lidar.fahrschlauch_luecke(lidar.ungueltige_winkel(m)))
        self.assertIsNone(lidar.hinten_luecke(lidar.ungueltige_winkel(m)))

    def test_einzelner_strahl_reicht_keine_quote(self):
        # 1 von 360 Strahlen (99,7 % gueltig) - genau im Fahrbereich: trotzdem unbekannt
        for wert in (0.0, float('nan'), float('inf'), 20.0):
            with self.subTest(wert=wert):
                m = mit_luecke(5, wert)
                self.assertIn('ohne Messung', lidar.sektor_abdeckung(m))
                self.assertIsNotNone(lidar.fahrschlauch_luecke(lidar.ungueltige_winkel(m)))

    def test_luecke_ausserhalb_des_bereichs(self):
        for grad in (60, 90, -90, 150, 180):
            with self.subTest(grad=grad):
                m = mit_luecke(grad)
                self.assertIsNone(lidar.sektor_abdeckung(m))
                self.assertIsNone(lidar.fahrschlauch_luecke(lidar.ungueltige_winkel(m)))
        self.assertIsNotNone(lidar.sektor_abdeckung(mit_luecke(180), rueckwaerts=True))
        self.assertEqual(lidar.hinten_luecke(lidar.ungueltige_winkel(mit_luecke(180))), 0.05)

    def test_bereich_folgt_dem_weg(self):
        winkel = lidar.ungueltige_winkel(mit_luecke(45))
        self.assertIsNone(lidar.fahrschlauch_luecke(winkel))                      # geradeaus: daneben
        self.assertIsNotNone(lidar.fahrschlauch_luecke(winkel, links_kurve()))    # Linkskurve: im Weg

    def test_kein_strahl_im_sektor(self):
        m = q.scan([3.0, 3.0], angle_min=math.radians(80), angle_increment=math.radians(10))
        self.assertIsNotNone(lidar.sektor_abdeckung(m))
        self.assertIsNotNone(lidar.fahrschlauch_luecke(lidar.ungueltige_winkel(m)))

    def test_teilscan_deckt_sektor_nur_teilweise(self):
        # Codex-Befund zu PR #143: nur Strahlen bei +20 und +30 Grad (gueltig) - links davon bis -30 Grad fehlt
        # jede Messung. Ein gueltiger Strahl im Sektor reicht nicht.
        m = q.scan([3.0, 3.0], angle_min=math.radians(20), angle_increment=math.radians(10))
        self.assertIn('-29 bis +15 Grad', lidar.sektor_abdeckung(m))
        self.assertIsNotNone(lidar.fahrschlauch_luecke(lidar.ungueltige_winkel(m)))
        self.assertIsNone(lidar.sektor_abdeckung(m, front_deg=25.0, halb_deg=9.0))   # 16..34 Grad: gemessen
        # dichter Teilscan nur -90..+90 Grad: vorne gemessen, hinten unbekannt
        halb = q.scan([3.0] * 181, angle_min=-math.pi / 2, angle_increment=math.radians(1))
        self.assertIsNone(lidar.sektor_abdeckung(halb))
        self.assertIsNone(lidar.fahrschlauch_luecke(lidar.ungueltige_winkel(halb)))
        self.assertIsNotNone(lidar.sektor_abdeckung(halb, rueckwaerts=True))
        self.assertIsNotNone(lidar.hinten_luecke(lidar.ungueltige_winkel(halb)))

    def test_winziger_winkelschritt_begrenzt_das_raster(self):
        # Codex-Befund zu PR #143: angle_increment 1e-6 (kaputt, aber endlich) darf kein Riesenraster erzeugen
        m = q.scan(3.0, angle_increment=1e-6)
        self.assertLessEqual(len(lidar.ungueltige_winkel(m)), 3600)
        self.assertIsNotNone(lidar.sektor_abdeckung(m))
        self.assertIsNotNone(lidar.fahrschlauch_luecke(lidar.ungueltige_winkel(m)))
        self.assertEqual(len(lidar.ungueltige_winkel(q.scan(3.0, angle_increment=1e-12))), 3600)

    def test_rueckwaerts_zaehlende_lidars(self):
        # angle_increment negativ (Uhrzeigersinn): gleiche Abdeckung
        r = [3.0] * N
        r[5] = 0.0                                                    # Strahl bei +175 Grad ... rueckwaerts gezaehlt
        m = q.scan(r, angle_min=math.pi, angle_increment=-2 * math.pi / N)
        self.assertIsNone(lidar.sektor_abdeckung(m))
        self.assertIsNotNone(lidar.sektor_abdeckung(m, rueckwaerts=True))


class Linienfolger(unittest.TestCase):
    def test_winziger_winkelschritt_haelt(self):
        self.halt(q.linienfolger(q.scan(3.0, angle_increment=1e-6)), 'LIDAR UNBEKANNT')

    def halt(self, n, text):
        lin, quer, dreh, status = n.entscheide()
        self.assertEqual((lin, quer, dreh), (0.0, 0.0, 0.0), status)
        self.assertIn(text, status)

    def test_gegenbeispiel_keine_vorwaertsfreigabe(self):
        self.halt(q.linienfolger(gegenbeispiel()), 'LIDAR UNBEKANNT (/scan0 vorne')

    def test_einzelne_luecke_vorne(self):
        n = q.linienfolger()
        n.on_scan(mit_luecke(-3, float('inf')), '/scan1', 1)
        self.halt(n, '/scan1 vorne: -4 bis -2 Grad teils ohne Messung')

    def test_echtes_hindernis_bleibt_haltgrund(self):
        r = [0.10 if 177 <= k <= 183 else 3.0 for k in range(N)]
        r[170] = r[190] = 0.0                                         # weitere unbekannte Strahlen vorne
        self.halt(q.linienfolger(q.scan(r)), 'NOTBREMSE 10 cm vorne')

    def test_luecke_ausserhalb_und_wiederfreigabe(self):
        n = q.linienfolger(mit_luecke(90))                            # links ohne Messung: Fahrweg vorne ok
        self.assertGreater(n.entscheide()[0], 0)
        n = q.linienfolger(mit_luecke(0))
        self.halt(n, 'vorne')
        for t, i in q.KANAELE:
            n.on_scan(q.scan(3.0), t, i)
        self.assertGreater(n.entscheide()[0], 0)

    def test_fahrbefehl_waehlt_den_bereich(self):
        n = q.linienfolger(mit_luecke(180))                           # nur hinten ohne Messung
        self.assertGreater(n.entscheide()[0], 0)                      # vorwaerts: ok
        for wunsch in ({'lin': -0.05}, {'dreh': 0.8}, {'quer': 0.05}):
            with self.subTest(wunsch=wunsch):
                n.ki = (time.time(), {'aktion': 'manoever', 'manoever': wunsch})
                self.halt(n, 'hinten: ')


class KiZentrale(unittest.TestCase):
    def test_gegenbeispiel_unbekannt(self):
        z = q.ki_zentrale(gegenbeispiel())
        self.assertEqual(z.lidar_pruefen(), (None, None, None))
        self.assertEqual(q.befehl(z)['aktion'], 'stopp')

    def test_winziger_winkelschritt_unbekannt(self):
        z = q.ki_zentrale(q.scan(3.0, angle_increment=1e-6))
        self.assertEqual(z.lidar_pruefen(), (None, None, None))

    def test_luecke_im_fahrschlauch(self):
        z = q.ki_zentrale()
        z._scan(mit_luecke(2, float('nan')), '/scan0', 0)
        self.assertEqual(z.lidar_pruefen(), (None, None, None))

    def test_luecke_neben_dem_weg_bleibt_frei(self):
        z = q.ki_zentrale(mit_luecke(90))
        self.assertEqual(z.lidar_pruefen()[0], float('inf'))
        self.assertEqual(q.befehl(z)['aktion'], 'fahren')

    def test_kurve_aus_dem_linienfolger(self):
        z = q.ki_zentrale(mit_luecke(45))
        self.assertEqual(z.lidar_pruefen()[0], float('inf'))
        z.linie_status = {'_zeit': time.time(), 'weg': links_kurve()}
        self.assertEqual(z.lidar_pruefen(), (None, None, None))

    def test_naeheres_echtes_hindernis_bleibt(self):
        r = [3.0] * N
        for k in range(177, 184):
            r[k] = 0.15                                               # Hindernis 15 cm vorne ...
        for k in (145, 215):
            r[k] = 0.0                                                # ... Luecken (+-35 Grad) erst ab ca. 21 cm
        z = q.ki_zentrale(q.scan(r))
        d, obj, _ = z.lidar_pruefen()
        self.assertAlmostEqual(d, 0.15, delta=0.01)
        self.assertEqual(obj['quelle'], 'lidar')

    def test_rueckraum_nur_so_weit_wie_gemessen(self):
        z = q.ki_zentrale(mit_luecke(180))                            # hinten ohne Messung, vorne frei
        z._entscheiden()
        self.assertLess(z.lidar_hinten(), 0.1)                        # kein erfundener Rueckraum
        z = q.ki_zentrale()
        z._entscheiden()
        self.assertAlmostEqual(z.lidar_hinten(), 3.0, delta=0.01)     # gemessen frei bis zur Wand


if __name__ == '__main__':
    unittest.main()
