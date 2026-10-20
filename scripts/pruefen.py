#!/usr/bin/env python3
"""Reine Softwaretests: python scripts/pruefen.py (keine ROS-Simulation).

Jedes tests/test_*.py laeuft separat, alphabetisch und mit Projektwurzel als cwd.
Fehler, Timeouts und von unittest gemeldete Skips verhindern einen Gesamterfolg.
"""
import argparse
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SKIPS = re.compile(r'^OK \(skipped=[1-9][0-9]*\)\s*$', re.MULTILINE)


def seconds(value):
    try:
        result = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError('Timeout muss eine Zahl sein') from error
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError('Timeout muss endlich und groesser als 0 sein')
    return result


def discover(root):
    """Nur Skriptpfade lesen; keine Tests oder Produktmodule importieren."""
    return sorted(path for path in (root / 'tests').glob('test_*.py') if path.is_file())


def output_text(value):
    # TimeoutExpired liefert auch bei text=True eventuell Bytes.
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return value or ''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT,
                        help='Projektwurzel (auch fuer isolierte Runnerprobes)')
    parser.add_argument('--list', action='store_true', help='Nur entdeckte Skripte auflisten')
    parser.add_argument('--timeout', type=seconds, default=300.0,
                        help='Standardtimeout pro Skript in Sekunden (Standard: 300)')
    parser.add_argument('--test-timeout', action='append', default=[], metavar='DATEI=SEKUNDEN',
                        help='Einzelnes Timeout, z.B. test_karte.py=600; mehrfach moeglich')
    parser.add_argument('--log-dir', type=Path, help='Zusaetzlich ein UTF-8-Log je Skript speichern')
    args = parser.parse_args(argv)
    root = args.root.resolve()
    tests = discover(root)
    if not tests:
        print(f'FEHLER: keine tests/test_*.py in {root}', file=sys.stderr)
        return 2
    overrides = {}
    for entry in args.test_timeout:
        name, separator, value = entry.partition('=')
        if not separator or name not in {test.name for test in tests}:
            parser.error(f'Unbekanntes Skript oder ungueltiger Override: {entry}')
        try:
            overrides[name] = seconds(value)
        except argparse.ArgumentTypeError as error:
            parser.error(str(error))
    if args.list:
        for test in tests:
            print(test.relative_to(root).as_posix())
        return 0
    if args.log_dir:
        args.log_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    results = []
    for test in tests:
        timeout = overrides.get(test.name, args.timeout)
        print(f'\nSTART {test.name} (Timeout {timeout:g}s)', flush=True)
        started = time.monotonic()
        try:
            process = subprocess.run([sys.executable, '-u', str(test)], cwd=root, env=env,
                                     capture_output=True, text=True, encoding='utf-8',
                                     errors='replace', timeout=timeout)
            log = process.stdout + process.stderr
            status = 'OK' if process.returncode == 0 else f'FEHLER (Exitcode {process.returncode})'
            if process.returncode == 0 and SKIPS.search(log):
                status = 'UNVOLLSTAENDIG (unittest-Skips)'
        except subprocess.TimeoutExpired as error:
            log = output_text(error.stdout) + output_text(error.stderr)
            status = f'TIMEOUT ({timeout:g}s)'
        except OSError as error:
            log = str(error)
            status = 'FEHLER (Prozessstart)'
        elapsed = time.monotonic() - started
        print(log, end='' if log.endswith('\n') else '\n', flush=True)
        print(f'{status}: {test.name} ({elapsed:.2f}s)', flush=True)
        if args.log_dir:
            (args.log_dir / (test.stem + '.log')).write_text(
                f'{status}: {test.name} ({elapsed:.2f}s)\n{log}', encoding='utf-8')
        results.append(status == 'OK')
    passed = sum(results)
    print(f'\nGesamt: {passed}/{len(results)} Skripte bestanden; '
          f'{len(results) - passed} fehlerhaft oder unvollstaendig.', flush=True)
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
