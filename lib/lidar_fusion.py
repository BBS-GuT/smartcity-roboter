#!/usr/bin/env python3
"""Conservative free-space queries in base_link. No ROS or motion commands.

This module alone does not authorize motion: consumers must first require every
configured source, fresh reception/acquisition times and a confirmed vehicle hull.
"""
from dataclasses import dataclass
from functools import cached_property
import math

import numpy as np

import lidar


@dataclass(frozen=True)
class Messfeld:
    origin: np.ndarray
    angles: np.ndarray
    ranges: np.ndarray
    valid: np.ndarray
    increment: float
    minimum: float

    @cached_property
    def kreisdaten(self):
        """Circular search/range-minimum tables for this immutable scan only."""
        angles = np.concatenate((self.angles - 2 * math.pi, self.angles, self.angles + 2 * math.pi))
        invalid = np.concatenate(([0], np.cumsum(~np.tile(self.valid, 3))))
        limit = min(self.increment + 1e-7, 2 * lidar.STRAHL_RADIUS_MAX + 1e-9)
        gaps = np.concatenate(([0], np.cumsum(np.diff(angles) > limit)))
        minima = [np.tile(self.ranges, 3)]
        size = 1
        while 2 * size <= len(angles):
            previous = minima[-1]
            minima.append(np.minimum(previous[:-size], previous[size:]))
            size *= 2
        return angles, invalid, gaps, minima, limit

    def zellen_frei(self, unten, oben):
        """Conservatively prove complete axis-aligned cells, not just corners.

        All beams spanning a cell must be valid. Thus a narrow invalid ray
        through the interior cannot be hidden by four valid corner queries.
        A cell straddling the origin, a blind sector, or a return is unknown.
        """
        unten = np.asarray(unten, dtype=float).reshape(-1, 2)
        oben = np.asarray(oben, dtype=float).reshape(-1, 2)
        if unten.shape != oben.shape:
            raise ValueError('Zellgrenzen passen nicht zusammen')
        result = np.zeros(len(unten), dtype=bool)
        if not len(unten) or len(self.angles) < 2:
            return result
        low, high = unten - self.origin, oben - self.origin
        usable = (np.isfinite(low).all(axis=1) & np.isfinite(high).all(axis=1)
                  & (high > low).all(axis=1) & ~((low <= 0) & (high >= 0)).all(axis=1))
        rows = np.flatnonzero(usable)
        low, high = low[rows], high[rows]
        middle = (low + high) / 2
        center = np.arctan2(middle[:, 1], middle[:, 0])[:, None]
        corners = np.stack((np.arctan2(low[:, 1], low[:, 0]), np.arctan2(high[:, 1], low[:, 0]),
                            np.arctan2(low[:, 1], high[:, 0]), np.arctan2(high[:, 1], high[:, 0])), axis=1)
        relative = np.arctan2(np.sin(corners - center), np.cos(corners - center))
        start, end = relative.min(axis=1), relative.max(axis=1)
        angles, invalid, gaps, minima, limit = self.kreisdaten
        left = np.searchsorted(angles, center[:, 0] + start, side='left') - 1
        right = np.searchsorted(angles, center[:, 0] + end, side='right')
        covered = (end - start < math.pi) & (left >= 0) & (right < len(angles)) & (right > left)
        left, right = np.clip(left, 0, len(angles) - 1), np.clip(right, 0, len(angles) - 1)
        covered &= (invalid[right + 1] == invalid[left]) & (gaps[right] == gaps[left])
        # Two overlapping power-of-two intervals give the exact minimum of
        # every spanned beam, including invalid rays through a cell's interior.
        count = right - left + 1
        level = np.floor(np.log2(np.maximum(count, 1))).astype(int)
        shortest = np.zeros(len(rows))
        for k, table in enumerate(minima):
            selected = level == k
            shortest[selected] = np.minimum(table[left[selected]], table[right[selected] - (1 << k) + 1])
        nearest = np.linalg.norm(np.maximum(np.maximum(low, -high), 0), axis=1)
        furthest = np.linalg.norm(np.maximum(np.abs(low), np.abs(high)), axis=1)
        result[rows] = covered & (nearest > self.minimum) & (furthest < shortest * math.cos(limit / 2))
        return result

    def frei(self, points):
        """Points proven free by adjacent valid rays; missing rays stay unknown.

        The shorter return bounds the whole angular interval conservatively.
        Nothing behind a return is free. No interpolation over invalid bins or
        over the blind sector of a partial scan is allowed.
        """
        points = np.asarray(points, dtype=float).reshape(-1, 2)
        relative = points - self.origin
        distance = np.linalg.norm(relative, axis=1)
        angle = np.arctan2(relative[:, 1], relative[:, 0])
        result = np.zeros(len(points), dtype=bool)
        if len(self.angles) < 2:
            return result
        right = np.searchsorted(self.angles, angle) % len(self.angles)
        left = (right - 1) % len(self.angles)
        span = (self.angles[right] - self.angles[left]) % (2 * math.pi)
        # A wrapped pair across a 90-degree blind sector is not a measured cell.
        covered = ((span > 0) & (span <= self.increment + 1e-7)
                   & (span <= 2 * lidar.STRAHL_RADIUS_MAX + 1e-9))
        radius = np.minimum(self.ranges[left], self.ranges[right]) * np.cos(span / 2)
        return (covered & self.valid[left] & self.valid[right]
                & np.isfinite(points).all(axis=1)
                & (distance > self.minimum) & (distance < radius))


def messfeld(msg, front_deg, einbau):
    """Build a measured field, or return a reason. No assumed central origin."""
    reason = lidar.einbau_pruefen(
        einbau, getattr(getattr(msg, 'header', None), 'frame_id', None),
        nur_gemessen=True, front_deg=front_deg)
    if reason:
        return None, reason
    if not math.isfinite(front_deg):
        return None, 'scan_front_deg nicht endlich'
    reason = lidar.scan_pruefen(msg)
    if reason:
        return None, reason
    ranges = np.asarray(msg.ranges, dtype=float)
    angles = msg.angle_min + np.arange(len(ranges)) * msg.angle_increment - math.radians(front_deg)
    angles = np.arctan2(np.sin(angles), np.cos(angles))
    order = np.argsort(angles)
    valid = np.isfinite(ranges) & (ranges > msg.range_min) & (ranges < msg.range_max)
    origin = np.zeros(2) if einbau.frame == lidar.BASIS_FRAME else np.array([einbau.x, einbau.y])
    return Messfeld(origin, angles[order], ranges[order], valid[order],
                    abs(msg.angle_increment), msg.range_min), None


def gemeinsam_frei(fields, points):
    """Union of measured free space; an absent required field never releases.

    Required source freshness is deliberately not inferred from a second field.
    Each caller must validate it before passing the complete list here.
    """
    points = np.asarray(points, dtype=float).reshape(-1, 2)
    result = np.zeros(len(points), dtype=bool)
    if not fields or any(field is None for field in fields):
        return result
    for field in fields:
        result |= field.frei(points)
    return result


def gemeinsame_zellen(fields, unten, oben):
    """Each cell must be proven completely by at least one valid field."""
    result = np.zeros(len(unten), dtype=bool)
    if not fields or any(field is None for field in fields):
        return result
    for field in fields:
        result |= field.zellen_frei(unten, oben)
    return result


def _zellen(bounds, hull, step=0.02):
    """Cover the rectangle completely; split at the hull, never skip mixed cells."""
    xmin, xmax, ymin, ymax = bounds
    front, back, left, right = hull
    if not all(math.isfinite(v) for v in bounds) or xmin >= xmax or ymin >= ymax:
        raise ValueError('Pruefbereich ungueltig')
    if (math.ceil((xmax - xmin) / step) + 3) * (math.ceil((ymax - ymin) / step) + 3) > 20000:
        raise ValueError('Pruefbereich zu gross')
    axes = []
    for lo, hi, cuts in ((xmin, xmax, (-back, front)), (ymin, ymax, (-right, left))):
        values = [lo, hi, *np.arange(lo, hi, step), *(v for v in cuts if lo < v < hi)]
        axes.append(np.unique(np.asarray(values)))
    x, y = axes
    low = np.array([(a, b) for a in x[:-1] for b in y[:-1]])
    high = np.array([(a, b) for a in x[1:] for b in y[1:]])
    own = ((low[:, 0] >= -back - 1e-10) & (high[:, 0] <= front + 1e-10)
           & (low[:, 1] >= -right - 1e-10) & (high[:, 1] <= left + 1e-10))
    return low[~own], high[~own]


@dataclass(frozen=True)
class Sicht:
    fields: tuple
    hull: tuple  # front, back, left, right, positive distances from base_link
    points: np.ndarray

    def zone_frei(self, bounds):
        try:
            low, high = _zellen(bounds, self.hull)
        except (ValueError, OverflowError):
            return False
        return bool(len(low) and gemeinsame_zellen(self.fields, low, high).all())

    def flaeche_frei(self, mask, reach):
        try:
            low, high = _zellen((-reach, reach, -reach, reach), self.hull)
        except (ValueError, OverflowError):
            return False
        if not len(low):
            return False
        radius = np.linalg.norm(high - low, axis=1).max() / 2
        selected = mask((low + high) / 2, radius)[0]
        return bool(selected.any() and gemeinsame_zellen(self.fields, low[selected], high[selected]).all())

    def pfad(self, weg, half_width, length):
        """Object and first unobserved distance outside the measured hull.

        The legacy near-field cone only avoided assumed own parts. With a
        confirmed hull, the complete corridor outside it must be observed.
        """
        length += self.hull[0]  # the body front sweeps beyond the base_link path endpoint
        half_width = max(half_width, self.hull[2], self.hull[3])
        reach = max(length, 0.2) + half_width
        try:
            low, high = _zellen((-half_width, length + half_width, -reach, reach), self.hull)
        except (ValueError, OverflowError):
            return None, 0.0
        if not len(low):
            return None, 0.0
        center, radius = (low + high) / 2, np.linalg.norm(high - low, axis=1) / 2
        # Inflating by the complete cell radius includes cells touched only at an edge.
        lateral, distance = lidar.abstand_zum_weg(center, weg, length)
        inside = (lateral <= half_width + radius) & (distance <= length + radius)
        low, high, distance, radius = low[inside], high[inside], distance[inside], radius[inside]
        if not len(low):
            return None, 0.0
        free = gemeinsame_zellen(self.fields, low, high)
        obj = lidar.fahrschlauch(self.points, weg, halbe_breite=half_width,
                                laenge=length, nah=0.0, nah_halb_deg=180.0)
        unknown = ~free
        if obj is not None:
            # A return's own cell is occupied, not a missing measurement. Only
            # cells entirely before it can establish a separate coverage gap.
            # The unresolved end band is NEVER free: move the reported stopping
            # distance to its near edge, keeping the measured target coordinates.
            before = distance + radius < obj['abstand']
            occupied_end = unknown & ~before
            if occupied_end.any():
                obj = dict(obj, abstand=min(obj['abstand'], float(max(
                    0.0, np.min(distance[occupied_end] - radius[occupied_end])))))
            unknown &= before
        gap = float(max(0.0, np.min(distance[unknown] - radius[unknown]))) if unknown.any() else None
        return obj, gap

    def hinten(self, half_width, length=0.8):
        """Proven rear clearance from base_link, limited by the first unknown cell/hit.

        A wall farther away does not erase the observed space in front of it.
        A gap immediately outside the body remains unknown (None).
        """
        half_width = max(half_width, self.hull[2], self.hull[3])
        back = self.hull[1]
        try:
            low, high = _zellen((-back - length, -back, -half_width, half_width), self.hull)
        except (ValueError, OverflowError):
            return None
        if not len(low):
            return None
        free = gemeinsame_zellen(self.fields, low, high)
        distance = back + length
        if (~free).any():
            distance = min(distance, float(-high[~free, 0].max()))
        p = self.points
        rear = (p[:, 0] < -back) & (np.abs(p[:, 1]) <= half_width)
        if rear.any():
            distance = min(distance, float(-p[rear, 0].max()))
        return distance if distance > back + 1e-9 else None

    def schutz(self, directions, distance, turning=False):
        """Protect the translated hull; rotation checks the complete circumscribed disk."""
        front, back, left, right = self.hull
        if not math.isfinite(distance) or distance <= 0:
            return 'LIDAR UNBEKANNT: Schutzabstand ungueltig'
        if not directions or set(directions) - {'vorne', 'hinten', 'links', 'rechts'}:
            return 'LIDAR UNBEKANNT: Bewegungsrichtung ungueltig'
        radius = math.hypot(max(front, back), max(left, right)) + distance
        bounds = ((-radius, radius, -radius, radius) if turning else
                  (-back - distance * ('hinten' in directions),
                   front + distance * ('vorne' in directions),
                   -right - distance * ('rechts' in directions),
                   left + distance * ('links' in directions)))

        def relevant(lo, hi):
            x0, y0, x1, y1 = lo[:, 0], lo[:, 1], hi[:, 0], hi[:, 1]
            if turning:
                nearest = np.maximum(np.maximum(lo, -hi), 0)
                return np.linalg.norm(nearest, axis=1) <= radius
            # The expanded rectangle includes the swept corner of simultaneous
            # forward/sideways movement, not just the two separate side strips.
            return ((x1 >= bounds[0]) & (x0 <= bounds[1])
                    & (y1 >= bounds[2]) & (y0 <= bounds[3]))

        # An actual hit has priority over unknown coverage and is never filled in.
        if len(self.points) and relevant(self.points, self.points).any():
            return 'NOTBREMSE: Hindernis im Bewegungsbereich (Roboterbezug)'
        try:
            low, high = _zellen(bounds, self.hull)
        except (ValueError, OverflowError):
            return 'LIDAR UNBEKANNT: Schutzbereich ungueltig/zu gross'
        selected = relevant(low, high)
        if not gemeinsame_zellen(self.fields, low[selected], high[selected]).all():
            return 'LIDAR UNBEKANNT: Bewegungsbereich nicht gemeinsam gemessen (Roboterbezug)'
        return None


class Geometrie:
    """Optional measured geometry; incomplete configuration fails closed.

    No device coordinates are supplied by the product. Until geometry is supplied,
    the existing conservative path is retained. Fields carry the configuration
    fingerprint and timestamp, so a parameter/callback race cannot mix frames.
    """
    def __init__(self, node):
        self.node = node
        count = len(node.p('scan_topics'))
        for name, default in [('scan_frames', [''] * count),
                              ('scan_einbau_xy', [0.0] * (2 * count)),
                              ('scan_einbau_quelle', ['unbekannt'] * count),
                              ('fahrzeug_grenzen', [0.0] * 4)]:
            node.declare_parameter(name, default)
        self.received = {}

    def config(self):
        topics = tuple(self.node.p('scan_topics'))
        frames = tuple(self.node.p('scan_frames'))
        xy = tuple(self.node.p('scan_einbau_xy'))
        sources = tuple(self.node.p('scan_einbau_quelle'))
        hull = tuple(self.node.p('fahrzeug_grenzen'))
        fronts = tuple(self.node.p('scan_front_deg'))
        active = any(frames) or any(xy) or any(v != 'unbekannt' for v in sources) or any(hull)
        fingerprint = (topics, frames, xy, sources, hull, fronts)
        if not active:
            return False, None, None, fingerprint, None
        poses, reason = lidar.einbau_aus_parametern(topics, frames, xy, sources)
        if len(hull) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in hull):
            reason = reason or 'fahrzeug_grenzen fehlen/ungueltig (vorne, hinten, links, rechts)'
        if len(fronts) != len(topics) or not all(math.isfinite(v) for v in fronts):
            reason = reason or 'scan_front_deg passen nicht zu den Quellen'
        if reason is None:
            front, back, left, right = hull
            if any(not (-back <= pose.x <= front and -right <= pose.y <= left) for pose in poses.values()):
                reason = 'Sensorursprung liegt ausserhalb der angegebenen Fahrzeuggrenzen'
        return True, poses, hull, fingerprint, reason

    def aufnehmen(self, msg, topic, stamp):
        active, poses, hull, fingerprint, reason = self.config()
        if not active:
            return None
        field = None
        if reason is None:
            topics, _, _, _, _, fronts = fingerprint
            if topic not in topics:
                reason = 'unerwartete LiDAR-Quelle'
            else:
                field, reason = messfeld(msg, fronts[topics.index(topic)], poses[topic])
        self.received[topic] = (stamp, fingerprint, field)
        return reason

    def sicht(self, stamps):
        active, poses, hull, fingerprint, reason = self.config()
        if not active:
            return None, None
        if reason:
            return None, reason
        fields, points = [], []
        for topic in fingerprint[0]:
            entry = self.received.get(topic)
            if entry is None or entry[0] != stamps.get(topic) or entry[1] != fingerprint or entry[2] is None:
                return None, f'{topic}: Geometrie/Scanstand nicht eindeutig'
            field = entry[2]
            fields.append(field)
            indices = field.valid
            xy = field.origin + np.stack([np.cos(field.angles[indices]) * field.ranges[indices],
                                           np.sin(field.angles[indices]) * field.ranges[indices]], axis=1)
            front, back, left, right = hull
            own = ((xy[:, 0] >= -back) & (xy[:, 0] <= front)
                   & (xy[:, 1] >= -right) & (xy[:, 1] <= left))
            points.append(xy[~own])
        return Sicht(tuple(fields), hull, np.vstack(points)), None
