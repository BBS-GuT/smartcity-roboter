"""Zielgerichtete Offline-Regressionen zum Entwurf; kein ROS, keine Geraete."""
import dataclasses
import json
import math
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from basis import lese_quelle

import numpy as np
from prototyp import Einbau, Zeitgrenzen, pruefe_scan, pruefe_pflichtquellen, transformiere

ROOT = Path(__file__).resolve().parent


def nachricht(ranges=(3.0, 3.0, 3.0), *, frame='laser1_frame', stamp=100.0):
    sec = math.floor(stamp)
    return NS(ranges=list(ranges), range_min=0.05, range_max=12.0,
              angle_min=-0.01, angle_increment=0.01,
              header=NS(frame_id=frame, stamp=NS(sec=sec, nanosec=round((stamp-sec)*1e9))))


class Entwurf(unittest.TestCase):
    # Synthetische Testwerte, KEINE freigegebenen Geraetegrenzen/Einbauwerte.
    einbau = Einbau('laser1_frame', 0.10766, -0.09078, 0.0, True)
    grenzen = Zeitgrenzen(empfang_max=1.0, aufnahme_max=0.5, zukunft_max=0.02)

    def pruefe(self, msg=None, **aenderungen):
        werte = dict(empfang_mono=20.0, jetzt_mono=20.1, aufnahme_jetzt=100.1,
                     zeitbasis_bestaetigt=True, grenzen=self.grenzen)
        werte.update(aenderungen)
        return pruefe_scan(msg or nachricht(), self.einbau, (0, 1, 2), **werte)

    def test_gueltige_frische_kontrolle(self):
        self.assertTrue(self.pruefe().verwertbar)

    def test_vollstaendig_ungueltig_bleibt_unbekannt(self):
        for value in (0, float('nan'), float('inf'), -float('inf'), 0.01, 13):
            with self.subTest(value=value):
                b = self.pruefe(nachricht((value, value, value)))
                self.assertFalse(b.verwertbar)
                self.assertEqual(len(b.basis_xy), 0)
                self.assertIn('Kritische_Messung_unbekannt', b.gruende)

    def test_eine_kritische_luecke_verhindert_verwertbar(self):
        b = self.pruefe(nachricht((3, 0, 3)))
        self.assertFalse(b.verwertbar)
        self.assertEqual((b.kritisch_gueltig, b.kritisch_gesamt), (2, 3))
        self.assertEqual(len(b.basis_xy), 2)

    def test_luecke_ausserhalb_explizitem_pruefbereich_bleibt_sichtbar(self):
        b = pruefe_scan(nachricht((0, 3, 3)), self.einbau, (1, 2),
                        empfang_mono=20, jetzt_mono=20.1, aufnahme_jetzt=100.1,
                        zeitbasis_bestaetigt=True, grenzen=self.grenzen)
        self.assertTrue(b.verwertbar)
        self.assertEqual(b.gueltig.tolist(), [False, True, True])

    def test_alter_empfang(self):
        self.assertIn('Empfang_ungueltig_oder_alt', self.pruefe(empfang_mono=18).gruende)

    def test_alte_aufnahme_trotz_frischem_empfang(self):
        self.assertIn('Aufnahme_zu_alt', self.pruefe(nachricht(stamp=98)).gruende)

    def test_zukunftsaufnahme(self):
        self.assertIn('Aufnahme_in_Zukunft', self.pruefe(nachricht(stamp=101)).gruende)

    def test_kein_oder_ruecklaeufiger_stempel(self):
        self.assertIn('Aufnahmestempel_ungueltig', self.pruefe(nachricht(stamp=0)).gruende)
        self.assertIn('Aufnahmestempel_steht_oder_laeuft_zurueck',
                      self.pruefe(letzter_stempel=100).gruende)

    def test_ungeklaerte_zeitbasis(self):
        self.assertFalse(self.pruefe(zeitbasis_bestaetigt=False).verwertbar)

    def test_falscher_frame(self):
        self.assertIn('Sensorframe_falsch', self.pruefe(nachricht(frame='base_link')).gruende)

    def test_unbestaetigte_einbauwerte(self):
        b = pruefe_scan(nachricht(), dataclasses.replace(self.einbau, bestaetigt=False), (0, 1, 2),
                        empfang_mono=20, jetzt_mono=20.1, aufnahme_jetzt=100.1,
                        zeitbasis_bestaetigt=True, grenzen=self.grenzen)
        self.assertFalse(b.verwertbar)

    def test_fehlende_und_ungueltige_pflichtquelle(self):
        gut, schlecht = self.pruefe(), self.pruefe(nachricht((0, 0, 0)))
        self.assertFalse(pruefe_pflichtquellen({'vorne': gut}, ('vorne', 'hinten'))[0])
        self.assertFalse(pruefe_pflichtquellen({'vorne': gut, 'hinten': schlecht}, ('vorne', 'hinten'))[0])
        self.assertTrue(pruefe_pflichtquellen({'vorne': gut, 'hinten': gut}, ('vorne', 'hinten'))[0])
        self.assertFalse(pruefe_pflichtquellen({'vorne': gut}, ())[0])

    def test_rotation_translation_einmalig(self):
        e = Einbau('synthetisch', 0.2, -0.1, math.pi/2, True)
        np.testing.assert_allclose(transformiere([[1, 0]], e), [[0.2, 0.9]], atol=1e-12)
        self.assertEqual(transformiere([], e).shape, (0, 2))

    def test_gleicher_punkt_aus_beiden_sensoren(self):
        hinten = Einbau('laser0_frame', -0.11617, 0.09156, 0, True)
        basis = np.array([[0.6, 0.05]])
        vorne_lokal = basis - [self.einbau.x, self.einbau.y]
        hinten_lokal = basis - [hinten.x, hinten.y]
        np.testing.assert_allclose(transformiere(vorne_lokal, self.einbau), basis)
        np.testing.assert_allclose(transformiere(hinten_lokal, hinten), basis)

    def test_leere_messung_und_unbekannter_pruefbereich(self):
        self.assertFalse(self.pruefe(nachricht(())).verwertbar)
        b = pruefe_scan(nachricht(), self.einbau, (), empfang_mono=20, jetzt_mono=20.1,
                        aufnahme_jetzt=100.1, zeitbasis_bestaetigt=True, grenzen=self.grenzen)
        self.assertIn('Kritische_Abdeckung_nicht_definiert', b.gruende)

    def test_drei_geometrische_fehlerfaelle(self):
        # Vorhandene, hashgepruefte reine Produktfunktion fuer die Gegenkontrolle.
        quellen = json.loads((ROOT/'quellen.json').read_text(encoding='utf-8'))
        import hashlib
        code = lese_quelle('lib/lidar.py')
        self.assertEqual(hashlib.sha256(code.encode()).hexdigest(),
                         quellen['dateien']['lib/lidar.py']['normalisiert_sha256'])
        scope = {}; exec(compile(code, 'gesicherte_lidar_funktion', 'exec'), scope)
        schlauch = scope['fahrschlauch']
        punkt = np.array([[0.30, 0.20]])
        self.assertIsNone(schlauch(punkt))
        self.assertIsNotNone(schlauch(transformiere(punkt, self.einbau)))
        punkt = np.array([[0.40, -0.10]])
        self.assertIsNotNone(schlauch(punkt))
        self.assertIsNone(schlauch(transformiere(punkt, self.einbau)))
        hinten = Einbau('laser0_frame', -0.11617, 0.09156, 0, True)
        punkt = transformiere([[-0.30, -0.20]], hinten)[0]
        self.assertTrue(punkt[0] < -0.05 and abs(punkt[1]) < 0.15)

    def test_sicherheitsrelevante_metadaten(self):
        msg = nachricht(); msg.angle_increment = 0
        self.assertIn('Metadaten_ungueltig', self.pruefe(msg).gruende)
        msg = nachricht(); msg.range_max = msg.range_min
        self.assertFalse(self.pruefe(msg).verwertbar)

    def test_stempelfelder_kanonisch_pruefen(self):
        for sec, ns in [(99, 1_000_000_000), (100, -1), (100.0, 0), (100, True)]:
            with self.subTest(sec=sec, ns=ns):
                msg = nachricht(); msg.header.stamp = NS(sec=sec, nanosec=ns)
                self.assertIn('Aufnahmestempel_ungueltig', self.pruefe(msg).gruende)

    def test_strahlindizes_nicht_stillschweigend_runden(self):
        for indices in [(0.9, 1.9, 2.9), (0, 0, 1), (-1, 0, 1), (True, 0, 2)]:
            with self.subTest(indices=indices):
                b = pruefe_scan(nachricht(), self.einbau, indices,
                                empfang_mono=20, jetzt_mono=20.1, aufnahme_jetzt=100.1,
                                zeitbasis_bestaetigt=True, grenzen=self.grenzen)
                self.assertIn('Kritische_Abdeckung_nicht_definiert', b.gruende)


if __name__ == '__main__':
    unittest.main(verbosity=2)
