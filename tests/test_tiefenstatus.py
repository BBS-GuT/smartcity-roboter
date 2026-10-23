"""Measured reference, curved health mask and bounded single clearing target."""
import json
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
from tiefe import Bodenmodell
from tiefenstatus import Zielbestaetigung, strahlen, wegmaske, tiefe_messung_gueltig, raeum_pruefung, fahrraum_frei

ASSET = ROOT / 'lib' / 'bodenreferenz_rm01.npz'
with np.load(ASSET) as data:
    META = json.loads(str(data['metadaten'].item()))


def model():
    m = Bodenmodell(META['kamera'])
    m.lade_referenz(ASSET, META['pose'])
    return m


class Reference(unittest.TestCase):
    def test_measured_correction_is_loaded_and_frozen(self):
        m = model()
        with np.load(ASSET) as data:
            raw = data['referenz_tiefe']
            _, _, rz = strahlen(m.k, raw.shape[1:])
            residual = m.k['kamera_hoehe'] + np.where(raw > .03, raw, np.nan) * rz
            measured = np.nanmedian(residual, axis=0)
            finite = np.isfinite(measured)
            np.testing.assert_allclose(m.korrektur[finite], measured[finite], atol=1e-7)
            before = m.korrektur.copy()
            for image in raw:
                # Restore source size; model deliberately samples every fourth pixel.
                image = np.repeat(np.repeat(image, 4, axis=0), 4, axis=1)
                self.assertEqual(m.pruefe(image, lernen=True), (False, None))
            np.testing.assert_array_equal(m.korrektur, before)
        self.assertFalse(m.korrektur.flags.writeable)
        self.assertEqual(len(m.referenz['quellen']), 2)

    def test_pose_geometry_size_frame_and_intrinsics_are_bound(self):
        m = model()
        self.assertTrue(m.referenz_passt((480, 640), META['frame'], META['pose'], META['k']))
        for shape, frame, pose, k in [((240, 320), META['frame'], META['pose'], META['k']),
                                      ((480, 640), 'camera_depth', META['pose'], META['k']),
                                      ((480, 640), META['frame'], [90]*6, META['k']),
                                      ((480, 640), META['frame'], META['pose'], [1]*9),
                                      ((480, 640), META['frame'], META['pose'], None)]:
            self.assertFalse(m.referenz_passt(shape, frame, pose, k))
        with self.assertRaises(ValueError):
            Bodenmodell(dict(META['kamera'], kamera_hoehe=.32)).lade_referenz(ASSET, META['pose'])
        with self.assertRaises(ValueError):
            m.lade_referenz(ASSET, [90]*6)


class Corridor(unittest.TestCase):
    def test_curved_missing_region_is_detected_without_mutating_model(self):
        m = model()
        rx, ry, rz = strahlen(m.k, (120, 160))
        depth = -m.k['kamera_hoehe'] / rz
        x, y = m.k['kamera_x'] + depth * rx, depth * ry
        curve = [[.2, 0], [.3, .16], [.4, .3]]
        straight, _, _ = wegmaske(x, y, m.c)
        curved, _, _ = wegmaske(x, y, m.c, curve)
        # Only holes which the old straight corridor could not see.
        holes = curved & ~straight
        self.assertGreater(holes.sum(), 25)
        image = np.full((120, 160), .4)
        image[holes] = 0
        image = image.repeat(4, 0).repeat(4, 1)
        self.assertTrue(tiefe_messung_gueltig(image, m))
        self.assertFalse(tiefe_messung_gueltig(image, m, curve))
        self.assertIsNone(m.strahlen)

    def test_one_pixel_and_missing_near_band_are_not_valid(self):
        m = model()
        image = np.zeros((480, 640))
        image[200, 300] = .4
        self.assertFalse(tiefe_messung_gueltig(image, m))
        image[:] = .4
        self.assertTrue(tiefe_messung_gueltig(image, m))
        image[320:] = 0
        self.assertFalse(tiefe_messung_gueltig(image, m))

    def test_two_ground_components_do_not_merge_into_target(self):
        m = model()
        # Analytic ground with two raised patches, no learned reference bias.
        m.korrektur = np.zeros((120,160))
        _, _, rz = strahlen(m.k, (120,160))
        image = -m.k['kamera_hoehe'] / rz
        image[60:75, 50:62] = (.06-m.k['kamera_hoehe']) / rz[60:75, 50:62]
        image[60:75, 95:107] = (.06-m.k['kamera_hoehe']) / rz[60:75, 95:107]
        hit, target = m.pruefe(image.repeat(4,0).repeat(4,1), False)
        self.assertTrue(hit)
        self.assertEqual(len(m.objekte), 2)
        self.assertLess(target['breite'], .08)
        self.assertNotEqual(m.objekte[0]['region'], m.objekte[1]['region'])


class Target(unittest.TestCase):
    def scene(self):
        obj = dict(ziel_id='t1', bestaetigt=True, messzeit=10., vor=.3, seite=0.,
                   breite=.04, hoehe=.05, region={'min':[.3,-.02,.02], 'max':[.34,.02,.05]})
        return dict(objekt=obj,tiefe_gueltig=True,lidar=float('inf'),
                    lidar_xy=np.array([[.31,0.]]),tiefe_objekte=[obj],
                    aufnahme=100.,tiefe_aufnahme=100.,tiefe_empfang=10.)

    def test_only_exact_target_is_excluded_other_objects_remain(self):
        w = self.scene()
        hull = [.2,.2,.15,.15]
        result = raeum_pruefung(w,hull,10.1,jetzt=100.1)
        self.assertTrue(all(result[k] for k in ('raeumziel_freigegeben','raeum_umgebung_frei','chassis_frei')))
        w['lidar_xy'] = np.array([[.31,0.],[.4,.03]])
        self.assertFalse(raeum_pruefung(w,hull,10.1,jetzt=100.1)['raeum_umgebung_frei'])
        w = self.scene()
        w['tiefe_objekte'].append(dict(w['objekt'],ziel_id='other'))
        self.assertFalse(raeum_pruefung(w,hull,10.1,jetzt=100.1)['raeum_umgebung_frei'])
        self.assertFalse(raeum_pruefung(self.scene(),[.32,.2,.15,.15],10.1,jetzt=100.1)['chassis_frei'])

    def test_old_mismatched_data_cannot_bind_a_plan(self):
        for change in ({'tiefe_aufnahme':99.}, {'aufnahme':99.8}, {'tiefe_empfang':9.},
                       {'tiefe_gueltig':False}, {'tiefe_aufnahme':None}):
            w = dict(self.scene(),**change)
            self.assertFalse(raeum_pruefung(w,[.2,.2,.15,.15],10.1,jetzt=100.1)['raeumziel_freigegeben'])

    def test_post_grasp_checks_exclude_no_object(self):
        w = self.scene()
        cfg = dict(weg_breite=.15,weg_laenge=.6)
        self.assertEqual(fahrraum_frei(w,[.2,.2,.15,.15],cfg),(True,False))
        w.update(tiefe_objekte=[],lidar_xy=np.empty((0,2)))
        self.assertEqual(fahrraum_frei(w,[.2,.2,.15,.15],cfg),(True,True))

    def test_only_distinct_recent_consistent_measurements_confirm(self):
        z = Zielbestaetigung()
        obj = dict(vor=.2, seite=.01, breite=.04, hoehe=.05, region={'min':[.2,0,0],'max':[.24,.04,.05]})
        self.assertFalse(z.update([obj], 1, 10., 'fahr')['bestaetigt'])
        self.assertFalse(z.update([obj], 1, 10.1, 'fahr')['bestaetigt'])
        self.assertFalse(z.update([obj], 2, 10.1, 'fahr')['bestaetigt'])
        confirmed = z.update([obj], 3, 10.2, 'fahr')
        self.assertTrue(confirmed['bestaetigt'])
        changed = z.update([dict(obj, seite=.1)], 4, 10.3, 'fahr')
        self.assertFalse(changed['bestaetigt'])
        self.assertNotEqual(confirmed['ziel_id'], changed['ziel_id'])
        self.assertFalse(z.update([obj], 5, 11., 'fahr')['bestaetigt'])


if __name__ == '__main__':
    unittest.main()
