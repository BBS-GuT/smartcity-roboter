import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
sys.path.insert(0, str(ROOT / 'mqtt'))
from m1_protocol import Inbox, envelope
from m1_map import align_markers, fuse
from m1_local_map import from_npz
from m1_routes import advise, choose
from m1_start_slots import transform as start_transform, validate as validate_slots
from m1_map_transport import package, publish, verify_package

T = 1792656000
START = 'a' * 32


class ProtocolTest(unittest.TestCase):
    def test_schema_file_is_versioned(self):
        schema = json.loads((ROOT / 'schemas/m1-v1.schema.json').read_text(encoding='utf-8'))
        self.assertEqual(schema['properties']['schema_version']['const'], 'm1/1')
        self.assertEqual(len(schema['allOf']), 3)

    def message(self, seq=1, start=START):
        return envelope('RM01', start, seq, 'intention', 'city', 1,
                        {'current_section': 'A', 'next_section': 'B'}, now=T)

    def test_replay_identity_age_and_old_start(self):
        inbox = Inbox()
        raw = json.dumps(self.message()).encode()
        inbox.accept(raw, topic_robot='RM01', authenticated_robot='RM01', now=T)
        for kwargs in ({'topic_robot': 'RM01'}, {'topic_robot': 'RM02'}):
            with self.assertRaises(ValueError):
                inbox.accept(raw, now=T, **kwargs)
        inbox.accept(json.dumps(self.message(1, 'b' * 32)).encode(), topic_robot='RM01', now=T)
        with self.assertRaises(ValueError):
            inbox.accept(json.dumps(self.message(2)).encode(), topic_robot='RM01', now=T)
        with self.assertRaises(ValueError):
            Inbox().accept(raw, topic_robot='RM01', now=T + 6)
        with self.assertRaises(ValueError):
            Inbox().accept(raw, topic_robot='RM01', authenticated_robot='RM02', now=T)


class MapTest(unittest.TestCase):
    def test_existing_npz_geometry_and_floor(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'karte.npz'
            np.savez_compressed(path, info=json.dumps({'aufloesung': .02, 'ursprung': -1}),
                                belegung=np.array([[2, 0], [0, -2]], np.float16),
                                boden_farbe=np.array([[[10, 20, 30], [0, 0, 0]],
                                                      [[0, 0, 0], [1, 2, 3]]], np.uint8),
                                boden_anzahl=np.array([[1, 0], [0, 1]], np.uint8))
            source = from_npz(path, robot='RM01', alignment={'x_m': 0, 'y_m': 0,
                                                               'yaw_rad': 0, 'max_error_m': 0})
            self.assertEqual(source['origin_m'], -1)
            self.assertEqual(len(source['cells']), 2)
            self.assertEqual(source['cells'][0]['floor_rgb'], [10, 20, 30])
    def test_alignment_and_ambiguity(self):
        local = {'a': (0, 0), 'b': (1, 0), 'c': (0, 1)}
        reference = {'a': (2, 3), 'b': (2, 4), 'c': (1, 3)}
        transform = align_markers(local, reference)
        self.assertAlmostEqual(transform['yaw_rad'], 1.57079632679)
        self.assertLess(transform['max_error_m'], 1e-9)
        with self.assertRaises(ValueError):
            align_markers(local, {'a': (2, 3), 'b': (2, 4), 'c': (5, 3)})
        with self.assertRaises(ValueError):
            align_markers({'a': (0, 0), 'b': (1, 0), 'c': (2, 0)}, reference)

    def test_fusion_drops_dynamic_and_bad_overlap(self):
        base = {'resolution_m': .02, 'quality': 'verified',
                'alignment': {'x_m': 0, 'y_m': 0, 'yaw_rad': 0, 'max_error_m': 0}}
        one = dict(base, robot='RM01', cells=[{'ix': 0, 'iy': 0, 'occupancy': 100, 'floor_rgb': [1, 2, 3]},
                                              {'ix': 1, 'iy': 0, 'occupancy': 100, 'dynamic': True}])
        two = dict(base, robot='RM02', cells=[{'ix': 0, 'iy': 0, 'occupancy': 90}])
        fused = fuse([one, two], map_id='city')
        self.assertEqual(len(fused['cells']), 1)
        self.assertEqual(fused['cells'][0]['occupancy'], 95)
        self.assertEqual(fused['sources'], ['RM01', 'RM02'])
        bad = dict(two, cells=[{'ix': 0, 'iy': 0, 'occupancy': 0}])
        with self.assertRaises(ValueError):
            fuse([one, bad], map_id='city')
        with self.assertRaises(ValueError):
            fuse([one, dict(two, quality='unknown')], map_id='city')

    def test_export_pointer_after_ack(self):
        data = fuse([dict(robot=r, resolution_m=.02, quality='verified',
                          alignment={'x_m': 0, 'y_m': 0, 'yaw_rad': 0, 'max_error_m': 0},
                          cells=[{'ix': 0, 'iy': 0, 'occupancy': 50}]) for r in ('RM01', 'RM02')], map_id='city')
        files, manifest = package(data)
        self.assertTrue(files['occupancy.png'].startswith(b'\x89PNG'))
        self.assertEqual(json.loads(manifest)['files']['map.json']['sha256'], hashlib.sha256(files['map.json']).hexdigest())
        class Ack:
            def wait_for_publish(self, timeout): pass
            def is_published(self): return True
        class Client:
            def __init__(self): self.topics = []
            def publish(self, topic, *_args, **_kwargs):
                self.topics.append(topic)
                return Ack()
        client = Client()
        pointer = publish(client, data)
        self.assertTrue(client.topics[-1].endswith('/current'))
        self.assertIn('/manifest.json/', client.topics[-2])
        self.assertEqual(verify_package(pointer, manifest, files)['version'], data['version'])
        with self.assertRaises(ValueError):
            verify_package(pointer, manifest, dict(files, **{'occupancy.png': b'bad'}))
        with self.assertRaises(ValueError):
            verify_package(pointer, manifest, files, now=pointer['published_at_unix_s'] + 301)


class RouteTest(unittest.TestCase):
    def test_local_fallback_and_lower_id_yields(self):
        peer = {'robot': 'RM01', 'current_section': 'A', 'next_section': 'B',
                'map_id': 'city', 'map_version': 1, 'observed_at': T}
        args = (['B', 'C'], 'RM02', 'A', [peer], 'B')
        self.assertEqual(choose(*args, map_id='city', map_version=1, now=T), 'C')
        self.assertEqual(choose(*args, map_id='city', map_version=1, now=T+4), 'B')
        self.assertEqual(choose(*args, map_id='other', map_version=1, now=T), 'B')
        self.assertIn(choose(*args, map_id='city', map_version=1, now=T), ['B', 'C'])
        visited = dict(peer, current_section='X', next_section='Y', recent_sections=['B'])
        self.assertEqual(choose(['B', 'C'], 'RM02', 'A', [visited], 'B',
                                map_id='city', map_version=1, now=T), 'C')

    def test_four_robots_and_no_safe_exit(self):
        peers = [
            {'robot': 'RM01', 'current_section': 'A', 'next_section': 'B'},
            {'robot': 'RM02', 'current_section': 'C', 'next_section': 'A'},
            {'robot': 'RM03', 'current_section': 'X', 'next_section': 'D'},
        ]
        peers = [dict(peer, map_id='city', map_version=1, observed_at=T) for peer in peers]
        result = advise(['B', 'C', 'D', 'E'], 'RM04', 'A', peers, 'B',
                        map_id='city', map_version=1, now=T)
        self.assertEqual(result['selected_exit'], 'E')
        self.assertFalse(result['requires_local_hold'])
        blocked = advise(['B', 'D'], 'RM04', 'A', peers, 'B',
                         map_id='city', map_version=1, now=T)
        self.assertEqual(blocked['selected_exit'], 'B')
        self.assertTrue(blocked['requires_local_hold'])
        self.assertEqual(advise(['B', 'D'], 'RM04', 'A', peers, 'B',
                                map_id='city', map_version=1, now=T+4)['reason'],
                         'no_fresh_peer_data')


class StartSlotTest(unittest.TestCase):
    def test_four_slots_give_only_approximate_common_positions(self):
        slots = {'RM0' + str(index): {'x_m': float(index), 'y_m': 0.0,
                                      'yaw_rad': 1.5707963267948966,
                                      'position_uncertainty_m': .05,
                                      'heading_uncertainty_deg': 5}
                 for index in range(1, 5)}
        config = {'map_id': 'future-field', 'frame_id': 'site-plan/meters', 'slots': slots}
        validate_slots(config)
        result = start_transform(config, 'RM04',
                                 {'x_m': 2, 'y_m': 3, 'yaw_rad': 0},
                                 {'x_m': 3, 'y_m': 3, 'yaw_rad': 0})
        self.assertAlmostEqual(result['x_m'], 4)
        self.assertAlmostEqual(result['y_m'], 1)
        self.assertEqual(result['quality'], 'approximate')
        self.assertGreater(result['position_uncertainty_m'], .05)
        with self.assertRaises(ValueError):
            validate_slots(dict(config, slots=dict(slots, RM04=slots['RM03'])))


if __name__ == '__main__':
    unittest.main()
