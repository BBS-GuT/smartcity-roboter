#!/usr/bin/env python3
# ROS-Einstellungen aus mehreren Dateien (spaetere gelten vor frueheren):
#   config/roboter.yaml        Standardwerte (im Repository)
#   config/ampel.yaml          Ampelwerte (Panel -> System -> Ampel einstellen, falls vorhanden)
#   config/lokal/roboter.yaml  eigene Werte DIESES Roboters (Panel speichert hierhin, nicht im Repository,
#                              damit "git pull" nie an gespeicherten Werten scheitert)
# Eigene Werte kann man auch von Hand eintragen, z. B. die gemessene Kameraneigung:
#   /**:
#     ros__parameters:
#       kamera_neigung: 30.0
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
STANDARD = os.path.join(REPO, 'config', 'roboter.yaml')
AMPEL = os.path.join(REPO, 'config', 'ampel.yaml')
LOKAL = os.path.join(REPO, 'config', 'lokal', 'roboter.yaml')


def dateien():
    """Vorhandene Einstellungsdateien in der richtigen Reihenfolge."""
    return [d for d in (STANDARD, AMPEL, LOKAL) if os.path.exists(d)]


def ros_argumente():
    """['--params-file', datei, ...] fuer den Start eines ROS-Programms."""
    args = []
    for d in dateien():
        args += ['--params-file', d]
    return args


def _lies(datei):
    try:
        import yaml
        with open(datei) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def lade(knoten=None):
    """Zusammengefuehrte Werte fuer '/**' und (falls angegeben) einen Knoten, z. B. 'line_follower'."""
    werte = {}
    for d in dateien():
        daten = _lies(d)
        for teil in ('/**', knoten):
            if teil:
                werte.update(((daten.get(teil) or {}).get('ros__parameters')) or {})
    return werte


def speichere(name, wert):
    """Wert fuer alle Programme ('/**') in config/lokal/roboter.yaml speichern."""
    import yaml
    daten = _lies(LOKAL)
    daten.setdefault('/**', {}).setdefault('ros__parameters', {})[name] = wert
    os.makedirs(os.path.dirname(LOKAL), exist_ok=True)
    with open(LOKAL, 'w') as f:
        f.write('# Eigene Einstellungen dieses Roboters (gelten vor config/roboter.yaml). Nicht im Repository.\n')
        yaml.safe_dump(daten, f, allow_unicode=True, sort_keys=False)


def umziehen(datei):
    """Frueher hat das Panel direkt in config/arm.yaml bzw. config/roboter.yaml gespeichert.
    Uebernimmt alles, was dort vom Stand im Repository abweicht, nach config/lokal/ (fuer update.sh)."""
    import subprocess
    import yaml
    name = os.path.basename(datei)
    original = subprocess.run(['git', '-C', REPO, 'show', f'HEAD:config/{name}'],
                              capture_output=True, text=True).stdout
    alt, jetzt = yaml.safe_load(original) or {}, _lies(datei)
    ziel = os.path.join(REPO, 'config', 'lokal', name)
    lokal = _lies(ziel)
    geaendert = []
    for teil, werte in jetzt.items():
        if isinstance(werte, dict):
            vorher = alt.get(teil) or {}
            for k, v in werte.items():
                if isinstance(v, dict):      # z. B. '/**': {'ros__parameters': {...}}
                    for k2, v2 in v.items():
                        if (vorher.get(k) or {}).get(k2) != v2:
                            lokal.setdefault(teil, {}).setdefault(k, {})[k2] = v2
                            geaendert.append(f'{teil}/{k2}')
                elif vorher.get(k) != v:     # z. B. posen: {'pruefblick': [...]}
                    lokal.setdefault(teil, {})[k] = v
                    geaendert.append(f'{teil}/{k}')
        elif alt.get(teil) != werte:         # z. B. ki_darf_arm_bewegen: true
            lokal[teil] = werte
            geaendert.append(teil)
    if geaendert:
        os.makedirs(os.path.dirname(ziel), exist_ok=True)
        with open(ziel, 'w') as f:
            f.write(f'# Eigene Einstellungen dieses Roboters (gelten vor config/{name}). Nicht im Repository.\n')
            yaml.safe_dump(lokal, f, allow_unicode=True, sort_keys=False)
    return geaendert


if __name__ == '__main__':
    import sys
    for d in sys.argv[1:]:
        print(f"{d}: uebernommen nach config/lokal/: {', '.join(umziehen(d)) or 'nichts'}")
