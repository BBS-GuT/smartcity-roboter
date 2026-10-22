"""Optional common display frame from surveyed, robot-specific start slots.

Manual placement is approximate. This transform must not certify a fused map
or provide a motor/collision clearance.
"""
import math

ROBOTS = frozenset({'RM01', 'RM02', 'RM03', 'RM04'})


def _pose(value):
    if not isinstance(value, dict):
        raise ValueError('pose object required')
    numbers = tuple(value.get(name) for name in ('x_m', 'y_m', 'yaw_rad'))
    if any(type(number) not in (int, float) or not math.isfinite(number)
           for number in numbers):
        raise ValueError('finite x_m, y_m and yaw_rad required')
    return numbers


def validate(config):
    """Require four distinct measured slots in one named site-plan frame."""
    if not isinstance(config, dict) or not isinstance(config.get('map_id'), str) or not config['map_id']:
        raise ValueError('map_id required')
    if config.get('frame_id') != 'site-plan/meters':
        raise ValueError('site-plan/meters frame required')
    slots = config.get('slots')
    if not isinstance(slots, dict) or set(slots) != ROBOTS:
        raise ValueError('one slot for each of RM01..RM04 required')
    coords = []
    for robot in sorted(ROBOTS):
        slot = slots[robot]
        x, y, _ = _pose(slot)
        for name in ('position_uncertainty_m', 'heading_uncertainty_deg'):
            value = slot.get(name)
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError('positive measured start uncertainty required')
        coords.append((x, y))
    if len(set(coords)) != 4:
        raise ValueError('start slots must be distinct')
    return config


def transform(config, robot, local_start_pose, local_pose):
    """Map a local pose into the site plan, with placement uncertainty attached."""
    slots = validate(config)['slots']
    if robot not in slots:
        raise ValueError('unknown robot')
    sx, sy, sw = _pose(slots[robot])
    lx, ly, lw = _pose(local_start_pose)
    x, y, yaw = _pose(local_pose)
    angle = sw - lw
    dx, dy = x - lx, y - ly
    gx = sx + math.cos(angle) * dx - math.sin(angle) * dy
    gy = sy + math.sin(angle) * dx + math.cos(angle) * dy
    distance = math.hypot(dx, dy)
    slot = slots[robot]
    # Heading uncertainty grows into position uncertainty away from start.
    error = slot['position_uncertainty_m'] + distance * math.sin(
        min(math.pi / 2, math.radians(slot['heading_uncertainty_deg'])))
    return {'map_id': config['map_id'], 'frame_id': config['frame_id'],
            'x_m': gx, 'y_m': gy, 'yaw_rad': (yaw + angle + math.pi) % (2 * math.pi) - math.pi,
            'position_uncertainty_m': error,
            'heading_uncertainty_deg': slot['heading_uncertainty_deg'],
            'quality': 'approximate', 'source': 'manual_start_slot'}
