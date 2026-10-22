#!/usr/bin/env python3
# Prueft die Stoppschild-Erkennung mit kuenstlichen Bildern.  Aufruf: python3 tests/test_schilder.py
import math
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'line_follower'))
import ampel  # noqa: E402
import schilder  # noqa: E402


def szene():
    return np.full((480, 640, 3), 200, np.uint8)


def vieleck(img, cx, cy, r, n, farbe, drehung=math.pi / 8):
    pts = np.array([[cx + r * math.cos(drehung + 2 * math.pi * i / n),
                     cy + r * math.sin(drehung + 2 * math.pi * i / n)] for i in range(n)], np.int32)
    cv2.fillPoly(img, [pts], farbe)


def pruefe(name, img, erwartet, ampel_erwartet=False):
    e = schilder.finde_stoppschild(img, {})
    a = ampel.finde_rot(img, {})
    ok = (e['treffer'] is not None) == erwartet and (a['treffer'] is not None) == ampel_erwartet
    print(f"{'OK  ' if ok else 'FEHLER'} {name}: schild={e['treffer']} "
          f"gruende={[k[4] or 'ok' for k in e['kandidaten']]} ampel={a['treffer']}")
    return ok


def main():
    r = []
    img = szene(); vieleck(img, 320, 200, 50, 8, (30, 30, 200))
    cv2.putText(img, 'STOP', (285, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    r.append(pruefe('Stoppschild nah', img, True))

    img = szene(); vieleck(img, 320, 200, 10, 8, (30, 30, 200))
    r.append(pruefe('Stoppschild weit weg (zu klein)', img, False))

    img = szene(); cv2.rectangle(img, (250, 150), (390, 250), (30, 30, 200), -1)
    r.append(pruefe('rotes Rechteck', img, False))

    img = szene(); cv2.circle(img, (320, 200), 50, (30, 30, 200), -1)
    r.append(pruefe('roter Kreis (Verbotsschild/Ball)', img, False))

    img = szene(); vieleck(img, 320, 200, 60, 3, (30, 30, 200), drehung=-math.pi / 2)
    r.append(pruefe('rotes Dreieck', img, False))

    print()
    print('Alle Tests bestanden.' if all(r) else f'{r.count(False)} Test(s) fehlgeschlagen.')
    return 0 if all(r) else 1


if __name__ == '__main__':
    sys.exit(main())
