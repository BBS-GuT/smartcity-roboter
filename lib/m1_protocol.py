"""M1 MQTT messages: bounded, versioned data, never motor authority."""
from datetime import datetime, timezone
import json
import math
import re
import time

VERSION = 'm1/1'
KINDS = frozenset({'position', 'intention', 'map_state'})
ROBOT = re.compile(r'RM0[1-4]\Z')
START = re.compile(r'[a-f0-9]{32}\Z')
MAP_ID = re.compile(r'[A-Za-z0-9_.-]{1,64}\Z')


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _utc(value):
    if not isinstance(value, str):
        raise ValueError('UTC timestamp required')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('invalid UTC timestamp') from exc
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError('UTC timestamp required')
    return parsed.timestamp()


def validate(message, *, topic_robot=None, authenticated_robot=None, now=None):
    """Validate transport envelope and semantic bounds; return the same message."""
    if not isinstance(message, dict) or message.get('schema_version') != VERSION:
        raise ValueError('unsupported M1 schema version')
    robot = message.get('geraet')
    if not isinstance(robot, str) or not ROBOT.fullmatch(robot):
        raise ValueError('invalid robot ID')
    if topic_robot is not None and topic_robot != robot:
        raise ValueError('topic identity mismatch')
    if authenticated_robot is not None and authenticated_robot != robot:
        raise ValueError('authenticated identity mismatch')
    if not isinstance(message.get('start_id'), str) or not START.fullmatch(message['start_id']):
        raise ValueError('invalid start ID')
    if type(message.get('seq')) is not int or not 0 <= message['seq'] <= 2**63 - 1:
        raise ValueError('invalid sequence')
    if message.get('kind') not in KINDS:
        raise ValueError('unknown message kind')
    stamp = _utc(message.get('erzeugt_utc'))
    current = time.time() if now is None else now
    if stamp < current - 5 or stamp > current + 1:
        raise ValueError('stale or future message')
    ref = message.get('karten_bezug')
    if not isinstance(ref, dict) or not isinstance(ref.get('id'), str) or not MAP_ID.fullmatch(ref['id']):
        raise ValueError('invalid map reference')
    version = ref.get('version')
    if not ((type(version) is int and version >= 1) or
            (isinstance(version, str) and re.fullmatch(r'[a-f0-9]{16}', version))):
        raise ValueError('invalid map version')
    body = message.get('data')
    if not isinstance(body, dict):
        raise ValueError('data object required')
    kind = message['kind']
    if kind == 'position':
        pose = body.get('pose')
        section = body.get('section')
        if pose is None and section is None:
            raise ValueError('pose or section required')
        if pose is not None and (not isinstance(pose, dict) or
                any(not _number(pose.get(k)) for k in ('x_m', 'y_m', 'yaw_rad'))):
            raise ValueError('invalid pose')
        if section is not None and (not isinstance(section, str) or not section or len(section) > 64):
            raise ValueError('invalid section')
        if body.get('quality') not in ('verified', 'approximate', 'unknown'):
            raise ValueError('position quality required')
    elif kind == 'intention':
        if not isinstance(body.get('current_section'), str) or not body['current_section']:
            raise ValueError('current section required')
        if not isinstance(body.get('next_section'), str) or not body['next_section']:
            raise ValueError('next section required')
        if len(body['current_section']) > 64 or len(body['next_section']) > 64:
            raise ValueError('section too long')
    elif kind == 'map_state':
        if body.get('quality') not in ('verified', 'unknown') or not isinstance(body.get('manifest_sha256'), str) or not re.fullmatch(r'[a-f0-9]{64}', body['manifest_sha256']):
            raise ValueError('invalid map state')
    return message


def loads(raw, **kwargs):
    if len(raw) > 16384:
        raise ValueError('M1 message too large')
    return validate(json.loads(raw), **kwargs)


class Inbox:
    """Reject replays, retired starts, bad identities and stale messages."""

    def __init__(self):
        self.current = {}
        self.retired = {robot: set() for robot in ('RM01', 'RM02', 'RM03', 'RM04')}

    def accept(self, raw, *, topic_robot, authenticated_robot=None, now=None):
        item = loads(raw, topic_robot=topic_robot, authenticated_robot=authenticated_robot, now=now)
        robot, start, seq = item['geraet'], item['start_id'], item['seq']
        previous = self.current.get(robot)
        if start in self.retired[robot]:
            raise ValueError('retired start ID')
        if previous and start == previous[0] and seq <= previous[1]:
            raise ValueError('duplicate or reversed sequence')
        if previous and start != previous[0]:
            self.retired[robot].add(previous[0])
            # Four robots, bounded memory even after many restarts.
            if len(self.retired[robot]) > 128:
                self.retired[robot] = set(sorted(self.retired[robot])[-128:])
        self.current[robot] = (start, seq)
        return item


def envelope(robot, start, seq, kind, map_id, map_version, data, *, now=None):
    stamp = datetime.fromtimestamp(time.time() if now is None else now, timezone.utc)
    return validate({'schema_version': VERSION, 'geraet': robot, 'start_id': start,
                     'seq': seq, 'erzeugt_utc': stamp.isoformat().replace('+00:00', 'Z'),
                     'karten_bezug': {'id': map_id, 'version': map_version},
                     'kind': kind, 'data': data}, now=stamp.timestamp())
