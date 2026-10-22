"""Sensor detail envelopes without ROS, hardware or a broker."""
import base64
import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
import zlib

spec = importlib.util.spec_from_file_location(
    'telemetry_detail', Path(__file__).resolve().parents[1] / 'panel/telemetry_detail.py')
detail = importlib.util.module_from_spec(spec)
spec.loader.exec_module(detail)


class TestTelemetryDetail(unittest.TestCase):
    def test_live_jpeg_preserves_bytes_and_distinguishes_new_frame(self):
        image = SimpleNamespace(header=SimpleNamespace(stamp=SimpleNamespace(sec=0, nanosec=0),
                                                       frame_id='camera_color'))
        first = detail.encoded_jpeg(image, 1000.0, b'\xff\xd8frame\xff\xd9', 640, 360)
        same = detail.encoded_jpeg(image, 1000.0, b'\xff\xd8frame\xff\xd9', 640, 360)
        newer = detail.encoded_jpeg(image, 1000.2, b'\xff\xd8frame\xff\xd9', 640, 360)
        self.assertEqual(base64.b64decode(first['data_b64']), b'\xff\xd8frame\xff\xd9')
        self.assertEqual(first['frame_key'], same['frame_key'])
        self.assertNotEqual(first['frame_key'], newer['frame_key'])
        self.assertEqual(first['frame_id'], 'camera_color')

    def test_native_depth_round_trip(self):
        image = SimpleNamespace(header=SimpleNamespace(stamp=SimpleNamespace(sec=100, nanosec=4),
                                                       frame_id='depth_optical'), width=2, height=2,
                                encoding='16UC1', step=4, is_bigendian=False)
        raw = b'\x01\x00\x02\x00\x03\x00\x04\x00'
        result = detail.encoded_image(image, 100.2, raw, 'depth')
        self.assertEqual(zlib.decompress(base64.b64decode(result['data_b64'])), raw)
        self.assertEqual(result['captured_at'], '1970-01-01T00:01:40+00:00')
        self.assertEqual((result['width'], result['height'], result['step']), (2, 2, 4))

    def test_scan_nonfinite_values_are_unknown_and_source_index_survives(self):
        scan = SimpleNamespace(header=SimpleNamespace(stamp=SimpleNamespace(sec=0, nanosec=0),
                                                      frame_id='scan_back'),
                               ranges=[0.2, float('inf'), float('nan')], intensities=[1.0],
                               angle_min=-1.0, angle_max=1.0, angle_increment=1.0,
                               time_increment=0.01, scan_time=0.1, range_min=0.1,
                               range_max=4.0)
        result = detail.encoded_scan(scan, 100.0, '/scan1', 1)
        self.assertEqual(result['ranges'], [0.2, None, None])
        self.assertEqual((result['topic'], result['index']), ('/scan1', 1))


if __name__ == '__main__':
    unittest.main()
