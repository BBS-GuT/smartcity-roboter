"""Read-only, bounded sensor detail serialization for the local MQTT adapter."""
import base64
from datetime import datetime, timezone
import hashlib
import json
import math
import zlib


def finite(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def stamp(message):
    header = getattr(message, 'header', None)
    ros_stamp = getattr(header, 'stamp', None)
    sec = getattr(ros_stamp, 'sec', 0)
    nanosec = getattr(ros_stamp, 'nanosec', 0)
    if sec > 0 and 0 <= nanosec < 1_000_000_000:
        return datetime.fromtimestamp(sec + nanosec / 1e9, timezone.utc).isoformat()
    return None


def identity(message, data, observed_at):
    source_stamp = stamp(message)
    frame_clock = source_stamp or str(observed_at)
    return {
        'captured_at': source_stamp,
        'frame_id': str(getattr(getattr(message, 'header', None), 'frame_id', '')),
        'frame_key': hashlib.sha256(frame_clock.encode() + data).hexdigest()[:16],
    }


def encoded_image(message, observed_at, data, kind, max_bytes=2_097_152):
    if not data or len(data) > max_bytes:
        raise ValueError('image size outside limit')
    result = identity(message, data, observed_at)
    result.update({'observed_at': datetime.fromtimestamp(observed_at, timezone.utc).isoformat(),
                   'kind': kind, 'width': int(message.width), 'height': int(message.height),
                   'encoding': str(message.encoding), 'step': int(message.step),
                   'is_bigendian': bool(message.is_bigendian),
                   'compression': 'zlib',
                   'data_b64': base64.b64encode(zlib.compress(data, 3)).decode('ascii')})
    return result


def encoded_jpeg(message, observed_at, data, width, height, max_bytes=262_144):
    if not data or len(data) > max_bytes:
        raise ValueError('JPEG size outside limit')
    result = identity(message, data, observed_at)
    result.update({'observed_at': datetime.fromtimestamp(observed_at, timezone.utc).isoformat(),
                   'kind': 'camera', 'width': int(width), 'height': int(height),
                   'encoding': 'jpeg', 'data_b64': base64.b64encode(data).decode('ascii')})
    return result


def encoded_scan(message, observed_at, topic, index, max_points=4096):
    ranges = list(message.ranges)
    intensities = list(message.intensities)
    if len(ranges) > max_points or len(intensities) > max_points:
        raise ValueError('scan point count outside limit')
    result = identity(message, json.dumps(ranges, default=str).encode(), observed_at)
    result.update({'observed_at': datetime.fromtimestamp(observed_at, timezone.utc).isoformat(),
                   'kind': 'scan', 'topic': topic, 'index': index,
                   'angle_min': finite(float(message.angle_min)),
                   'angle_max': finite(float(message.angle_max)),
                   'angle_increment': finite(float(message.angle_increment)),
                   'time_increment': finite(float(message.time_increment)),
                   'scan_time': finite(float(message.scan_time)),
                   'range_min': finite(float(message.range_min)),
                   'range_max': finite(float(message.range_max)),
                   'ranges': [finite(float(x)) for x in ranges],
                   'intensities': [finite(float(x)) for x in intensities]})
    return result
