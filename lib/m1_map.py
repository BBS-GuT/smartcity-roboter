"""Conservative M1 map alignment and fusion, independent of ROS and driving."""
import hashlib
import json
import math

import numpy as np


def align_markers(local, reference, *, max_error_m=0.03):
    """Unique, named, non-collinear anchors determine an SE(2) transform."""
    names = sorted(set(local) & set(reference))
    if len(names) < 3:
        raise ValueError('at least three shared markers required')
    src = np.asarray([local[name] for name in names], dtype=float)
    dst = np.asarray([reference[name] for name in names], dtype=float)
    if src.shape != (len(names), 2) or dst.shape != src.shape or not np.isfinite(src).all() or not np.isfinite(dst).all():
        raise ValueError('invalid markers')
    x, y = src - src.mean(axis=0), dst - dst.mean(axis=0)
    if min(np.linalg.svd(x, compute_uv=False)) < 0.05 or min(np.linalg.svd(y, compute_uv=False)) < 0.05:
        raise ValueError('ambiguous marker geometry')
    u, _, vt = np.linalg.svd(x.T @ y)
    correction = np.eye(2)
    correction[1, 1] = np.linalg.det(u @ vt)
    rotation = u @ correction @ vt
    shift = dst.mean(axis=0) - src.mean(axis=0) @ rotation
    residual = np.linalg.norm(src @ rotation + shift - dst, axis=1)
    if residual.max() > max_error_m:
        raise ValueError('marker alignment error exceeds 3 cm')
    baseline = max(np.linalg.norm(src[a] - src[b]) for a in range(len(src)) for b in range(a))
    angle_uncertainty = math.degrees(math.asin(min(1, float(residual.max()) / baseline)))
    if angle_uncertainty > 1:
        raise ValueError('marker angle uncertainty exceeds 1 degree')
    yaw = math.atan2(rotation[0, 1], rotation[0, 0])
    return {'x_m': float(shift[0]), 'y_m': float(shift[1]), 'yaw_rad': yaw,
            'max_error_m': float(residual.max()), 'angle_uncertainty_deg': angle_uncertainty,
            'anchors': names}


def transform_points(points, transform):
    yaw = transform['yaw_rad']
    rotation = np.array([[math.cos(yaw), math.sin(yaw)],
                         [-math.sin(yaw), math.cos(yaw)]])
    return np.asarray(points, dtype=float) @ rotation + [transform['x_m'], transform['y_m']]


def fuse(maps, *, map_id, resolution_m=0.02, min_coverage=0.1, reference_markers=None):
    """Fuse verified occupancy/floor layers; unknown stays unknown.

    Each map provides cells as {ix,iy,occupancy, floor_rgb?, dynamic?} and a
    verified SE(2) transform. Dynamic objects never become static walls.
    """
    if not 0 < resolution_m <= 0.1 or not maps or len({m['robot'] for m in maps}) < 2:
        raise ValueError('two independent robot maps required')
    joined = {}
    contributions = {}
    source_hashes = {}
    for source in maps:
        if (source.get('alignment', {}).get('max_error_m', 1) > 0.03 or
                source.get('alignment', {}).get('angle_uncertainty_deg', 0) > 1 or
                source.get('quality') != 'verified'):
            raise ValueError('unverified transform or map')
        cells = source.get('cells', [])
        if not cells or len(cells) > 1_000_000:
            raise ValueError('empty or oversized source map')
        source_hashes[source['robot']] = hashlib.sha256(json.dumps(
            {'cells': cells, 'alignment': source['alignment'], 'origin_m': source.get('origin_m', 0)},
            sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        resolution = source.get('resolution_m')
        if not isinstance(resolution, (int, float)) or not 0 < resolution <= 0.1:
            raise ValueError('invalid source resolution')
        static = [cell for cell in cells if not cell.get('dynamic')]
        if len(static) / len(cells) < min_coverage:
            raise ValueError('insufficient static coverage')
        origin = source.get('origin_m', 0)
        if not isinstance(origin, (int, float)) or not math.isfinite(origin):
            raise ValueError('invalid source origin')
        coords = np.array([[origin + (c['ix'] + 0.5) * resolution,
                            origin + (c['iy'] + 0.5) * resolution] for c in static])
        shifted = transform_points(coords, source['alignment'])
        contributions[source['robot']] = 0
        for cell, (x, y) in zip(static, shifted):
            value = cell.get('occupancy')
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100):
                raise ValueError('invalid occupancy')
            rgb = cell.get('floor_rgb')
            if rgb is not None and (not isinstance(rgb, list) or len(rgb) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in rgb)):
                raise ValueError('invalid floor color')
            if value is None and rgb is None:
                continue
            key = (math.floor(x / resolution_m), math.floor(y / resolution_m))
            joined.setdefault(key, []).append((value, rgb, source['robot']))
            contributions[source['robot']] += 1
    if any(count == 0 for count in contributions.values()):
        raise ValueError('source has no usable cells')
    fused = []
    conflicts = overlap = 0
    for (ix, iy), samples in sorted(joined.items()):
        occupied = [s[0] for s in samples if s[0] is not None]
        if len({s[2] for s in samples}) > 1:
            overlap += 1
            if occupied and max(occupied) - min(occupied) > 60:
                conflicts += 1
        floors = [s[1] for s in samples if s[1] is not None]
        fused.append({'ix': ix, 'iy': iy,
                      'occupancy': round(sum(occupied) / len(occupied)) if occupied else None,
                      'floor_rgb': [round(sum(rgb[c] for rgb in floors) / len(floors)) for c in range(3)] if floors else None})
    if overlap == 0 or conflicts / overlap > 0.05:
        raise ValueError('overlap conflict too high')
    quality = {'overlap_cells': overlap, 'conflict_cells': conflicts,
               'conflict_ratio': conflicts / overlap if overlap else None,
               'coverage_cells': len(fused)}
    payload = {'schema_version': 'm1-map/1', 'map_id': map_id,
               'frame_id': 'shared/' + map_id,
               'resolution_m': resolution_m, 'cells': fused,
               'sources': sorted(contributions), 'source_hashes': source_hashes,
               'reference_markers': reference_markers or {}, 'quality': quality}
    payload['version'] = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:16]
    return payload
