"""Read the existing karte.npz into a bounded M1 map contribution."""
import json
import math

import numpy as np


def from_npz(path, *, robot, alignment, max_cells=200000):
    with np.load(path, allow_pickle=False) as saved:
        info = json.loads(str(saved['info']))
        lo = saved['belegung']
        floor = saved['boden_farbe']
        count = saved['boden_anzahl']
    resolution = float(info['aufloesung'])
    origin = float(info['ursprung'])
    if not 0 < resolution <= 0.1 or not math.isfinite(origin) or lo.ndim != 2:
        raise ValueError('invalid local map geometry')
    if floor.shape[:2] != count.shape or floor.ndim != 3 or floor.shape[2] != 3:
        raise ValueError('invalid floor layer')
    known = np.argwhere(np.abs(lo) >= 0.5)
    if len(known) > max_cells:
        raise ValueError('local map exceeds export limit')
    floor_ratio_y = floor.shape[0] / lo.shape[0]
    floor_ratio_x = floor.shape[1] / lo.shape[1]
    cells = []
    for iy, ix in known:
        value = float(lo[iy, ix])
        probability = 1 / (1 + math.exp(-value))
        fiy, fix = int((iy + .5) * floor_ratio_y), int((ix + .5) * floor_ratio_x)
        rgb = floor[fiy, fix].tolist() if count[fiy, fix] > 0 else None
        cells.append({'ix': int(ix), 'iy': int(iy), 'occupancy': round(probability * 100),
                      'floor_rgb': rgb})
    return {'robot': robot, 'resolution_m': resolution, 'origin_m': origin,
            'alignment': alignment, 'quality': 'verified' if cells else 'unknown',
            'cells': cells}
