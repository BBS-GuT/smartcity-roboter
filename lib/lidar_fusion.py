#!/usr/bin/env python3
"""Conservative free-space queries in base_link. No ROS or motion commands.

This module alone does not authorize motion: consumers must first require every
configured source, fresh reception/acquisition times and a confirmed vehicle hull.
"""
from dataclasses import dataclass
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
        for i, (low, high) in enumerate(zip(unten, oben)):
            if not (np.isfinite(low).all() and np.isfinite(high).all() and (high > low).all()):
                continue
            if ((low <= self.origin) & (self.origin <= high)).all():
                continue
            corners = np.array([[low[0], low[1]], [low[0], high[1]],
                                [high[0], low[1]], [high[0], high[1]]]) - self.origin
            middle = (low + high) / 2 - self.origin
            center_angle = math.atan2(middle[1], middle[0])
            corner_angles = np.arctan2(corners[:, 1], corners[:, 0])
            relative = np.arctan2(np.sin(corner_angles - center_angle),
                                  np.cos(corner_angles - center_angle))
            start, end = relative.min(), relative.max()
            if end - start >= math.pi:
                continue
            angles = np.arctan2(np.sin(self.angles - center_angle),
                                np.cos(self.angles - center_angle))
            order = np.argsort(angles)
            angles = angles[order]
            left = np.searchsorted(angles, start, side='left') - 1
            right = np.searchsorted(angles, end, side='right')
            if left < 0 or right >= len(angles):
                continue
            indices = order[left:right + 1]
            spans = np.diff(angles[left:right + 1])
            if not len(spans) or np.any(spans > min(self.increment + 1e-7,
                                                   2 * lidar.STRAHL_RADIUS_MAX + 1e-9)):
                continue
            if not self.valid[indices].all():
                continue
            nearest = np.linalg.norm(np.maximum(np.maximum(low - self.origin,
                                                           self.origin - high), 0))
            radius = self.ranges[indices].min() * math.cos(spans.max() / 2)
            result[i] = nearest > self.minimum and np.linalg.norm(corners, axis=1).max() < radius
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
        gap = float(max(0.0, np.min(distance[~free] - radius[~free]))) if np.any(~free) else None
        obj = lidar.fahrschlauch(self.points, weg, halbe_breite=half_width,
                                laenge=length, nah=0.0, nah_halb_deg=180.0)
        return obj, gap

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
