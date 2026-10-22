#!/usr/bin/env python3
"""Update and restart only this user's read-only MQTT live test."""
import os
from pathlib import Path
import shlex
import signal
import socket
import subprocess
import sys
import time
import urllib.request


TARGET = Path.home() / 'smartcity-roboter/mqtt/robot_live_test.py'
SOURCE = 'http://10.0.12.100:8765/robot_live_test.py'
VIEWER_PORT = 8766


def owns_test_command(arguments):
    try:
        words = shlex.split(arguments)
    except ValueError:
        return False
    if not words or Path(words[0]).name not in ('python', 'python3', 'python3.10'):
        return False
    return any(Path(word) == TARGET for word in words[1:])


def listener_free():
    with socket.socket() as client:
        client.settimeout(0.3)
        return client.connect_ex(('127.0.0.1', VIEWER_PORT)) != 0


def main():
    if not TARGET.parent.is_dir():
        raise RuntimeError('Roboter-Repo unter ~/smartcity-roboter fehlt')
    with urllib.request.urlopen(SOURCE, timeout=10) as response:
        updated = response.read(100_000)
    if not updated.startswith(b'#!/usr/bin/env python3') or b'VIEWER_PORT = 8766' not in updated:
        raise RuntimeError('Unerwartete Testdatei empfangen')
    compile(updated, str(TARGET), 'exec')
    temporary = TARGET.with_name(TARGET.name + '.new')
    temporary.write_bytes(updated)
    os.replace(temporary, TARGET)
    print('Korrigierter Test gespeichert.', flush=True)

    rows = subprocess.check_output(['ps', '-eo', 'pid=,args='], text=True)
    for line in rows.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2:
            continue
        pid = int(parts[0])
        if pid != os.getpid() and owns_test_command(parts[1]):
            print(f'Beende alten MQTT-Test (PID {pid}) geordnet ...', flush=True)
            os.kill(pid, signal.SIGINT)

    deadline = time.monotonic() + 20
    while not listener_free():
        if time.monotonic() >= deadline:
            raise RuntimeError('Port 8766 ist noch belegt; kein anderer Prozess wurde beendet')
        time.sleep(.25)
    print('Starte korrigierten Test ...', flush=True)
    os.execv(sys.executable, [sys.executable, str(TARGET)])


if __name__ == '__main__':
    main()
