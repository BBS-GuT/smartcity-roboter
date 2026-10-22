#!/usr/bin/env python3
"""Publish immutable M1 map artifacts, then atomically point to their version."""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import threading
import time
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
from m1_protocol import MAP_ID  # noqa: E402


def png_bytes(map_data):
    cells = map_data['cells']
    if not cells or len(cells) > 1_000_000:
        raise ValueError('invalid map size')
    min_x = min(c['ix'] for c in cells)
    min_y = min(c['iy'] for c in cells)
    width = max(c['ix'] for c in cells) - min_x + 1
    height = max(c['iy'] for c in cells) - min_y + 1
    if width * height > 1_000_000:
        raise ValueError('map extent too large')
    pixels = bytearray([127] * (width * height))
    for cell in cells:
        value = cell['occupancy']
        if value is not None:
            pixels[(cell['iy'] - min_y) * width + cell['ix'] - min_x] = round((100 - value) * 255 / 100)
    def chunk(kind, payload):
        return struct.pack('!I', len(payload)) + kind + payload + struct.pack('!I', zlib.crc32(kind + payload))
    rows = b''.join(b'\x00' + pixels[y * width:(y + 1) * width] for y in range(height))
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 0, 0, 0, 0)) +
           chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b''))
    return png, {'origin_ix': min_x, 'origin_iy': min_y, 'width': width, 'height': height}


def package(map_data):
    map_id = map_data['map_id']
    if not isinstance(map_id, str) or not MAP_ID.fullmatch(map_id):
        raise ValueError('invalid map ID')
    png, extent = png_bytes(map_data)
    raw = json.dumps(map_data, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if len(raw) > 4_000_000:
        raise ValueError('map JSON too large')
    artifacts = {'occupancy.png': png, 'map.json': raw}
    manifest = {'schema_version': 'm1-map-manifest/1', 'map_id': map_id,
                'version': map_data['version'], 'resolution_m': map_data['resolution_m'],
                'frame_id': map_data['frame_id'],
                'origin_m': [extent['origin_ix'] * map_data['resolution_m'],
                             extent['origin_iy'] * map_data['resolution_m']],
                'extent': extent, 'quality': map_data['quality'], 'sources': map_data['sources'],
                'source_hashes': map_data['source_hashes'],
                'reference_markers': map_data['reference_markers'],
                'files': {name: {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
                          for name, data in artifacts.items()}}
    return artifacts, json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()


def verify_package(pointer, manifest_bytes, artifacts, *, now=None, max_age_s=300):
    """Receiver-side version/hash verification before using a retained map."""
    if pointer.get('schema_version') != 'm1-map-current/1':
        raise ValueError('unsupported map pointer')
    stamp = pointer.get('published_at_unix_s')
    current = time.time() if now is None else now
    if type(stamp) not in (int, float) or not 0 <= current - stamp <= max_age_s:
        raise ValueError('stale or future retained map pointer')
    if hashlib.sha256(manifest_bytes).hexdigest() != pointer.get('manifest_sha256'):
        raise ValueError('map manifest hash mismatch')
    manifest = json.loads(manifest_bytes)
    if (manifest.get('schema_version') != 'm1-map-manifest/1' or
            manifest.get('map_id') != pointer.get('map_id') or
            manifest.get('version') != pointer.get('version')):
        raise ValueError('map version mismatch')
    if set(artifacts) != set(manifest['files']):
        raise ValueError('incomplete map artifacts')
    for name, detail in manifest['files'].items():
        raw = artifacts[name]
        if len(raw) != detail['bytes'] or hashlib.sha256(raw).hexdigest() != detail['sha256']:
            raise ValueError('map artifact hash mismatch')
    return json.loads(artifacts['map.json'])


def publish(client, map_data, *, base='smartcity/map/shared', timeout=5):
    """All QoS1 artifacts must ACK before retained current pointer changes."""
    artifacts, manifest = package(map_data)
    prefix = f"{base}/{map_data['map_id']}/{map_data['version']}"
    for name, data in (*artifacts.items(), ('manifest.json', manifest)):
        chunks = [data[i:i + 32768] for i in range(0, len(data), 32768)]
        for index, chunk in enumerate(chunks):
            ack = client.publish(f'{prefix}/{name}/{index}', chunk, qos=1, retain=True)
            ack.wait_for_publish(timeout)
            if not ack.is_published():
                raise TimeoutError('map artifact not acknowledged')
        count = client.publish(f'{prefix}/{name}/chunks', str(len(chunks)), qos=1, retain=True)
        count.wait_for_publish(timeout)
        if not count.is_published():
            raise TimeoutError('map chunk count not acknowledged')
    pointer = {'schema_version': 'm1-map-current/1', 'map_id': map_data['map_id'],
               'version': map_data['version'], 'manifest_sha256': hashlib.sha256(manifest).hexdigest(),
               'published_at_unix_s': time.time()}
    ack = client.publish(f'{base}/current', json.dumps(pointer, sort_keys=True), qos=1, retain=True)
    ack.wait_for_publish(timeout)
    if not ack.is_published():
        raise TimeoutError('map pointer not acknowledged')
    return pointer


class LatestMapPublisher:
    """At most one waiting map, never blocks cartography callbacks."""

    def __init__(self, client):
        self.client = client
        self.pending = None
        self.lock = threading.Lock()
        self.wakeup = threading.Event()
        self.stop = threading.Event()
        self.last_error = None
        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()

    def submit(self, map_data):
        with self.lock:
            self.pending = map_data
        self.wakeup.set()

    def _run(self):
        while not self.stop.is_set():
            self.wakeup.wait(1)
            self.wakeup.clear()
            with self.lock:
                item, self.pending = self.pending, None
            if item is None:
                continue
            try:
                publish(self.client, item)
                self.last_error = None
            except Exception as exc:
                self.last_error = str(exc)

    def close(self):
        self.stop.set()
        self.wakeup.set()
        self.worker.join(timeout=6)
