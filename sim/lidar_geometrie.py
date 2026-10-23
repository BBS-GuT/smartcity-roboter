#!/usr/bin/env python3
"""Known synthetic geometry for the isolated simulator, never robot calibration."""
import argparse
import math
import os
from pathlib import Path
import sys
import tempfile

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
import arm  # noqa: E402
from welt import AUFLOESUNG, ARM_STRICH_PX, FAHRZEUG_GRENZEN, GREIFER_RADIUS_PX  # noqa: E402

LIDAR_STANDARD = (0.0, 0.0, 0.0)
LIDAR_SCHWER = (-.12, 0.0, 4.0)


def schwer_argumente():
    # Existing schwer profile: one definition for generator and consumers.
    return ['-p', 'halle:=true', '-p', 'imu_skala:=1.03', '-p', 'lidar_umlauf:=0.12',
            '-p', 'lidar_verzoegerung:=0.1', '-p',
            'lidar1_einbau:=[' + ','.join(str(v) for v in LIDAR_SCHWER) + ']']


def arm_punkte(pose, geo):
    """Projected link ends using the existing simulator's Kinematik convention."""
    g = arm.Kinematik(geo).g
    w = np.asarray(pose[:4]) + np.asarray(g['nullpunkte'][:4])
    pitch = np.cumsum(np.radians(90 - w[1:]))
    lengths = np.array([g['oberarm'], g['unterarm'], g['hand']])
    sag = math.radians(g['durchhang']) * max(0.0, float(np.sum(lengths * np.sin(pitch)))) / .25
    pitch += np.array([.6, 1, 1]) * sag
    radius = np.concatenate(([0.0], np.cumsum(lengths * np.sin(pitch))))
    yaw = math.radians(w[0] - 90) * g['servo1_links']
    return np.asarray(g['schulter'][:2]) + radius[:, None] * [math.cos(yaw), math.sin(yaw)]


def parameter(schwer=False, arm_datei=None):
    """Exact synthetic poses and driving envelope from the existing model.

    gemessen denotes known synthetic truth here; it never confirms a device.
    Both existing arm-model variants and the startup/driving poses are included.
    """
    with open(arm_datei or ROOT / 'sim' / 'arm_sim.yaml', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    front, back, left, right = FAHRZEUG_GRENZEN
    low, high = np.array([-back, -right]), np.array([front, left])
    poses = ([90, 120, 10, 20, 90, 30], data['posen']['fahrstellung'])
    models = (data['geometrie'], dict(data['geometrie'], **data['geometrie_simulator']))
    for geo in models:
        for pose in poses:
            points = arm_punkte(pose, geo)
            # Same link width / tip disk as Welt.draufsicht, in model metres.
            radii = np.full(len(points), ARM_STRICH_PX * AUFLOESUNG / 2)
            radii[-1] = GREIFER_RADIUS_PX * AUFLOESUNG
            low = np.minimum(low, (points - radii[:, None]).min(axis=0))
            high = np.maximum(high, (points + radii[:, None]).max(axis=0))
    lidars = (LIDAR_STANDARD, LIDAR_SCHWER if schwer else LIDAR_STANDARD)
    return {'scan_topics': ['/scan0', '/scan1'], 'scan_frames': ['laser0', 'laser1'],
            'scan_einbau_xy': [v for pose in lidars for v in pose[:2]],
            # Simulator yaw is +4 degrees; front_deg is its NEGATIVE.
            'scan_front_deg': [-pose[2] for pose in lidars],
            'scan_einbau_quelle': ['gemessen', 'gemessen'],
            'fahrzeug_grenzen': [float(high[0]), float(-low[0]), float(high[1]), float(-low[1])]}


def schreibe_parameter(schwer=False, arm_datei=None):
    if os.environ.get('ROS_DOMAIN_ID') != '77':
        raise ValueError('Synthetische LiDAR-Geometrie nur in Simulationsdomain 77')
    data = {'/**': {'ros__parameters': parameter(schwer, arm_datei)}}
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', prefix='smartcity-sim-',
                                     encoding='utf-8', delete=False) as f:
        f.write('# NUR synthetischer Simulator, keine Geraetekalibrierung.\n')
        yaml.safe_dump(data, f, sort_keys=False)
        return f.name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulator-argumente', action='store_true')
    args = parser.parse_args()
    schwer = bool(os.environ.get('SIM_SCHWER'))
    if args.simulator_argumente:
        print('\n'.join(schwer_argumente()) if schwer else '', end='\n' if schwer else '')
    else:
        print(schreibe_parameter(schwer, os.environ.get('SMARTCITY_ARM_YAML')))


if __name__ == '__main__':
    main()
