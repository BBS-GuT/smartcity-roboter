#!/usr/bin/env python3
"""Isolated review probes for SmartCity main b9f6442 (no robot or ROS required).

Run with Python and NumPy, for example:
  python3 docs/pruefungen/2026-10-20-probes.py --repo /path/to/reviewed/checkout

These probes call unchanged repository methods with the repository's ROS
test doubles. OpenCV is an import-only stub: no OpenCV operation is executed.
For the three image timestamp probes only, LinienSucher.suche is replaced by
a deterministic synthetic result. This verifies time gating, not detection.
The panel probe executes unchanged AST-extracted methods with a recording
publisher and an empty child-process registry. It creates no real process.
Exit 0 means the documented observations were reproduced, not that safety
requirements passed. The JSON explicitly distinguishes control and findings.
"""

from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import types
from unittest.mock import patch


EXPECTED_COMMIT = 'b9f64424d92f64ed4f391a96b6c6718caae43bcd'
SOURCE_FILES = (
    'line_follower/line_follower.py', 'line_follower/linie.py',
    'lib/lidar.py', 'ki/entscheider.py', 'ki/ablaeufe.py', 'panel/panel.py',
    'tests/attrappen/rclpy/node.py', 'tests/attrappen/cv_bridge.py',
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path,
                        default=Path(__file__).with_name('2026-10-20-probes-neulauf.json'))
    args = parser.parse_args()
    repo = args.repo.resolve(strict=True)
    output = args.output.resolve()
    sys.dont_write_bytecode = True
    for directory in ('ki', 'lib', 'line_follower', 'tests/attrappen'):
        sys.path.insert(0, str(repo / directory))

    # Only importing these modules requires the cv2 name. All executed paths
    # use NumPy; image detection below is explicitly deterministic.
    sys.modules['cv2'] = types.ModuleType('cv2')
    import numpy as np
    import line_follower as lf
    from entscheider import Entscheider

    clock = [1000.0]
    observations = []

    def scan(ranges):
        return types.SimpleNamespace(
            ranges=ranges, angle_min=-math.pi,
            angle_increment=2 * math.pi / 360,
            range_min=0.05, range_max=12.0,
        )

    def new_follower():
        node = lf.LineFollower()
        node.gedaechtnis.hinzufuegen([(0.05 + 0.02 * k, 0.0) for k in range(40)])
        node.bild_zeit = clock[0]
        node.ki = (clock[0], {'aktion': 'fahren', 'faktor': 1.0, 'grund': 'frei'})
        node.on_scan(scan([2.0] * 360), '/scan0', 0)
        return node

    def observe(probe_id, requirement, setup, expected_safe, actual, reproduced,
                goal_deviation=True, limitations=None):
        observations.append({
            'id': probe_id,
            'requirements': requirement,
            'setup': setup,
            'expected_safe_behavior': expected_safe,
            'actual': actual,
            'observation_reproduced': bool(reproduced),
            'goal_deviation_observed': bool(goal_deviation and reproduced),
            'limitations': limitations or [],
        })

    with patch.object(time, 'time', side_effect=lambda: clock[0]), \
            patch.object(time, 'sleep', return_value=None):
        node = new_follower()
        node.on_scan(scan([float('nan')] * 360), '/scan0', 0)
        cmd = node.entscheide()
        observe('invalid_nan_lidar', ['GB-13', 'GB-14'],
                'Fresh scan0 contains 360 NaN ranges; synthetic line and AI command are fresh.',
                'Unknown/invalid required scan prevents movement.',
                {'command': cmd, 'scan_distance_is_infinite': math.isinf(node.scans['/scan0'][1])},
                math.isinf(node.scans['/scan0'][1]) and cmd[0] > 0)

        node = new_follower()
        cmd = node.entscheide()
        observe('missing_scan1', ['GB-12', 'GB-13'],
                'Configured topics are scan0 and scan1; only scan0 has ever arrived.',
                'Missing required scan prevents movement, or explicitly validated replacement is selected.',
                {'configured_topics': node.p('scan_topics'),
                 'received_topics': sorted(node.scans), 'command': cmd},
                '/scan1' in node.p('scan_topics') and '/scan1' not in node.scans and cmd[0] > 0,
                limitations=['The required sensor matrix has not been finalized; this demonstrates the current one-of-N policy.'])

        node = new_follower()
        node.scans.clear()
        node.bild_zeit = 0.0
        node.ki = (clock[0], {'aktion': 'manoever',
                            'manoever': {'lin': 0.0, 'quer': 0.0, 'dreh': 0.8}})
        cmd = node.entscheide()
        observe('notbrake_camera_bypass', ['GB-13', 'GB-14'],
                'No LiDAR, no camera frames, fresh AI turn request.',
                'Missing required perception prevents the turn.',
                {'command': cmd, 'notbrake_reason': node.notbremse()},
                cmd[0] == 0 and cmd[2] == 0.8)

        for age, name, is_finding in ((0.7, 'image_age_0_7s_control', False),
                                      (6.0, 'image_age_6s_fallback', True),
                                      (-1.0, 'image_future_1s_fallback', True)):
            node = new_follower()
            node.bild_zeit = 0.0  # Ensure the rate limiter accepts the probe frame.
            node._p.update(show=False, publish_image=False)
            detector_calls = []

            def deterministic_line(image):
                detector_calls.append(tuple(image.shape))
                return {'gefunden': True,
                        'boden': [(0.05 + 0.02 * k, 0.0) for k in range(40)],
                        'punkte': []}

            node.sucher.suche = deterministic_line
            stamp = clock[0] - age
            seconds = int(stamp)
            msg = types.SimpleNamespace(
                header=types.SimpleNamespace(stamp=types.SimpleNamespace(
                    sec=seconds, nanosec=round((stamp - seconds) * 1e9))),
                img=np.zeros((8, 8, 3), dtype=np.uint8),
            )
            node.on_image(msg)
            cmd = node.entscheide()
            reproduced = ((cmd[0] > 0 and not node.stempel_ok) if is_finding
                          else (cmd[:3] == (0.0, 0.0, 0.0) and node.stempel_ok))
            observe(name, ['GB-13'],
                    f'Image capture age {age}s; original on_image and entscheide methods; deterministic line detection.',
                    'Capture older than the maximum, or invalid capture time, prevents movement.',
                    {'capture_age_s': age, 'timestamp_accepted': node.stempel_ok,
                     'reported_capture_age_s': node.bild_alter, 'command': cmd,
                     'detector_calls': len(detector_calls)},
                    reproduced, goal_deviation=is_finding,
                    limitations=['LinienSucher.suche is replaced only for this timestamp probe; detection accuracy is not tested.'])

        decider = Entscheider()

        def decide(at, frame, **extra):
            perception = dict(bild_nr=frame, bild_zeit=at, lidar=float('inf'),
                              objekte=[], gier=0.0)
            perception.update(extra)
            return decider.update(at, perception)

        decide(100.0, 0, einfahrt_verboten=True)
        decide(100.1, 1, einfahrt_verboten=True)
        decide(100.7, 2)
        transition = decide(103.3, 3)
        latched = decider.fehler_halt
        following = decide(103.4, 4)
        observe('failed_turn_one_tick_drive', ['GB-13', 'GB-14'],
                'Turn requested; yaw remains zero until Wenden reports failure.',
                'The failure transition itself issues STOPP and latches the error.',
                {'failure_transition': transition, 'error_latched': latched,
                 'following_tick': following},
                bool(latched) and transition['aktion'] == 'fahren' and following['aktion'] == 'stopp')

        decider = Entscheider(arm_erlaubt=False)
        commands = []
        for frame in range(16):
            at = 200.0 + frame * 0.1
            commands.append(decider.update(at, dict(
                bild_nr=frame, bild_zeit=at, lidar=0.15, objekte=[],
                tiefe_hindernis=False, lidar_hinten=1.0)))
        last = commands[-1]
        observe('reverse_without_arm_or_avoidance', ['GB-04', 'GB-12', 'GB-14'],
                'Default decider: arm disabled, avoidance disabled; obstacle 0.15m ahead, camera sees none, rear reports 1m free.',
                'Blocked-road basic operation waits; any permitted perception maneuver requires explicit policy and clearance.',
                {'arm_enabled': decider.arm_freigabe, 'avoidance_enabled': decider.c['ausweichen'],
                 'command': last, 'phase': decider.ablauf.phase if decider.ablauf else None},
                not decider.arm_freigabe and not decider.c['ausweichen']
                and last.get('manoever', {}).get('lin', 0) < 0,
                limitations=['The probe demonstrates reverse movement, not whether the physical robot leaves its line.'])

        # Load the unchanged original methods in isolation. No HTTP server,
        # real process, shell command, ROS graph or hardware is involved.
        panel_path = repo / 'panel/panel.py'
        tree = ast.parse(panel_path.read_text(encoding='utf-8'))
        process_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Prozesse')
        panel_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'PanelNode')
        standstill = next(n for n in panel_class.body if isinstance(n, ast.FunctionDef) and n.name == 'stillstand')
        handler = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'mache_handler')
        action = next(n for n in handler.body if isinstance(n, ast.FunctionDef) and n.name == 'aktion')
        scope = {'time': time, 'Twist': lf.Twist}
        selected = ast.Module(body=[process_class, standstill, action], type_ignores=[])
        exec(compile(selected, str(panel_path), 'exec'), scope)

        class RecordingPublisher:
            def __init__(self):
                self.messages = []

            def publish(self, msg):
                self.messages.append(msg)

        node_type = type('PanelStopProbeNode', (), {'stillstand': scope['stillstand']})
        panel_node = node_type()
        panel_node.cmd_pub = RecordingPublisher()
        processes = scope['Prozesse']()
        stop_calls = []
        original_stop = processes.stopp

        def recording_stop(name, *a, **kw):
            stop_calls.append({'name': name, 'registered': name in processes.p})
            return original_stop(name, *a, **kw)

        processes.stopp = recording_stop
        scope.update(node=panel_node, prozesse=processes)
        reply = scope['aktion']('stopp', {}, True)
        observe('panel_stop_unregistered_publisher', ['GB-14'],
                'Foreign line follower is represented by absence from the panel child registry; original action, Prozesse, and stillstand methods execute.',
                'STOPP prevents subsequent movement from all sources, including unregistered publishers.',
                {'reply': reply, 'zero_messages_sent': len(panel_node.cmd_pub.messages),
                 'stop_calls': stop_calls, 'tracked_child_names': sorted(processes.p),
                 'foreign_process_termination_attempted': False},
                reply == 'Gestoppt' and len(panel_node.cmd_pub.messages) == 10
                and stop_calls == [{'name': 'fahren', 'registered': False}],
                limitations=['No real foreign process is launched. The probe proves the finite publication and empty-registry return path; continued physical motion is not measured.'])

    git_path = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
    try:
        commit = subprocess.run([str(git_path) if git_path.exists() else 'git', '-C', str(repo),
                                 'rev-parse', 'HEAD'], check=True, capture_output=True,
                                text=True, timeout=15).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit = None
    reproduced = sum(x['observation_reproduced'] for x in observations)
    findings = sum(x['goal_deviation_observed'] for x in observations)
    result = {
        'schema_version': '1.0',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'repository': str(repo), 'repository_commit': commit,
        'expected_review_commit': EXPECTED_COMMIT,
        'commit_matches_review': commit == EXPECTED_COMMIT,
        'python_executable': sys.executable, 'numpy_version': np.__version__,
        'test_method': 'Unchanged original methods, repository ROS doubles, controlled wall clock; no ROS or hardware.',
        'opencv_stub': 'Import-only empty module; no OpenCV operation executed.',
        'image_detector_override': 'Three timestamp probes use deterministic LinienSucher.suche; their original on_image/entscheide methods are unchanged.',
        'source_sha256': {name: hashlib.sha256((repo / name).read_bytes()).hexdigest() for name in SOURCE_FILES},
        'counts': {'total': len(observations), 'observations_reproduced': reproduced,
                   'goal_deviations_observed': findings,
                   'positive_controls': sum(not x['goal_deviation_observed'] for x in observations if x['observation_reproduced']),
                   'unreproduced': len(observations) - reproduced},
        'observations': observations,
        'interpretation': 'Reproduction success is evidence of the recorded behavior, not passing safety acceptance. No hardware behavior or real camera detection is validated.',
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(f'{reproduced}/{len(observations)} observations reproduced; {findings} goal deviations; output: {output}')
    if commit != EXPECTED_COMMIT:
        print(f'Note: commit is {commit!r}, expected {EXPECTED_COMMIT}. Source hashes are recorded.')
    return 0 if reproduced == len(observations) else 1


if __name__ == '__main__':
    raise SystemExit(main())
