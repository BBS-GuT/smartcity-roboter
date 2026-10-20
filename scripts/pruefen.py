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
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SKIPS = re.compile(r'^OK \([^\n)]*\bskipped=[1-9][0-9]*[^\n)]*\)\s*$', re.MULTILINE)


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


def stop_tree(process):
    """Nur den selbst gestarteten Testprozess und seine Nachkommen beenden."""
    if os.name == 'nt':
        result = subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                capture_output=True, timeout=5)
        if result.returncode:
            process.kill()
            return 'WARNUNG: Beendigung aller Kindprozesse nicht bestaetigt.\n'
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=5)
    return ''


def run_test(test, root, env, timeout):
    # Geerbte PIPE-Handles eines Kindes koennen communicate() unter Windows
    # trotz Timeout blockieren. Eine temporaere Datei vermeidet diese Wartefalle
    # und erhaelt stdout/stderr gemeinsam in ihrer Ausgabereihenfolge.
    options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen([sys.executable, '-u', str(test)], cwd=root, env=env,
                                   stdout=output, stderr=subprocess.STDOUT, **options)
        warning = ''
        try:
            process.wait(timeout=timeout)
            status = 'OK' if process.returncode == 0 else f'FEHLER (Exitcode {process.returncode})'
        except subprocess.TimeoutExpired:
            status = f'TIMEOUT ({timeout:g}s)'
            try:
                warning = stop_tree(process)
            except (OSError, subprocess.TimeoutExpired) as error:
                process.kill()
                warning = f'WARNUNG: Prozessbaum konnte nicht vollstaendig beendet werden: {error}\n'
        except BaseException:
            stop_tree(process)
            raise
        output.seek(0)
        log = output.read().decode('utf-8', errors='replace') + warning
    if status == 'OK' and SKIPS.search(log):
        status = 'UNVOLLSTAENDIG (unittest-Skips)'
    return status, log


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
            status, log = run_test(test, root, env, timeout)
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
