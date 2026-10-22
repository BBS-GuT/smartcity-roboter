#!/usr/bin/env python3
# Prueft die Ampel-Erkennung mit kuenstlichen Bildern (kein Roboter noetig).
# Aufruf:  python3 tests/test_ampel.py
# Ersetzt KEINEN Test mit der echten Ampel, zeigt aber, ob die Filter grundsaetzlich arbeiten.
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'line_follower'))
import ampel  # noqa: E402


def leere_szene():
    img = np.full((480, 640, 3), 200, np.uint8)  # helles Brett
    return img


def male_ampel(img, x, y, rot_an=True, r=6, gelb_an=False):
    # schwarzes Gehaeuse fuer 3 LEDs nebeneinander
    cv2.rectangle(img, (x - 2 * r, y - 2 * r), (x + 8 * r, y + 2 * r), (20, 20, 20), -1)
    cv2.circle(img, (x, y), r, (0, 60, 0), -1)               # gruen aus
    if gelb_an:
        cv2.circle(img, (x + 3 * r, y), r, (60, 230, 255), -1)  # gelb an
    else:
        cv2.circle(img, (x + 3 * r, y), r, (0, 60, 60), -1)      # gelb aus
    if rot_an:
        cv2.circle(img, (x + 6 * r, y), r + 2, (40, 40, 255), -1)  # roter Schein
        cv2.circle(img, (x + 6 * r, y), r - 2, (250, 250, 255), -1)  # ueberstrahlte Mitte
    else:
        cv2.circle(img, (x + 6 * r, y), r, (0, 0, 70), -1)


def pruefe(name, img, erwartet):
    erg = ampel.finde_rot(img, {})
    ok = (erg['treffer'] is not None) == erwartet
    gruende = [k[4] or 'ok' for k in erg['kandidaten']]
    print(f"{'OK  ' if ok else 'FEHLER'} {name}: treffer={erg['treffer']} kandidaten={gruende}")
    return ok


def main():
    ergebnisse = []

    img = leere_szene(); male_ampel(img, 300, 150)
    ergebnisse.append(pruefe('Ampel rot an', img, True))

    img = leere_szene(); male_ampel(img, 300, 150, r=3)
    ergebnisse.append(pruefe('Ampel rot an, weit weg (klein)', img, True))

    img = leere_szene(); male_ampel(img, 300, 150, gelb_an=True)
    ergebnisse.append(pruefe('Ampel rot + gelb an', img, True))

    img = leere_szene(); male_ampel(img, 300, 150, rot_an=False, gelb_an=True)
    ergebnisse.append(pruefe('Ampel nur gelb an', img, False))

    img = leere_szene(); male_ampel(img, 300, 150, rot_an=False)
    ergebnisse.append(pruefe('Ampel rot aus', img, False))

    img = leere_szene(); cv2.rectangle(img, (100, 100), (220, 250), (30, 30, 230), -1)
    ergebnisse.append(pruefe('grosser roter Becher', img, False))

    img = leere_szene(); cv2.circle(img, (400, 120), 7, (20, 20, 250), -1)
    ergebnisse.append(pruefe('kleiner roter Punkt auf hellem Brett', img, False))

    img = leere_szene(); cv2.rectangle(img, (100, 200), (400, 210), (30, 30, 240), -1)
    ergebnisse.append(pruefe('rotes Kabel (laenglich)', img, False))

    img = leere_szene(); cv2.circle(img, (400, 120), 7, (0, 0, 150), -1)
    cv2.rectangle(img, (380, 100), (420, 140), (20, 20, 20), 12)
    ergebnisse.append(pruefe('dunkelroter Punkt in schwarzem Rahmen (nicht leuchtend)', img, False))

    img = leere_szene(); male_ampel(img, 300, 150)
    cv2.rectangle(img, (50, 50), (200, 250), (30, 30, 230), -1)
    ergebnisse.append(pruefe('Ampel an + roter Gegenstand daneben', img, True))

    # Drei Farben (fuer die KI: welche Lampe leuchtet?)
    def farbe(name, img, erwartet):
        f = ampel.finde_ampel(img, {})['farbe']
        ok = f == erwartet
        print(f"{'OK  ' if ok else 'FEHLER'} {name}: erkannt={f}")
        return ok

    def ampel_farbig(an):
        img = leere_szene()
        r, x, y = 6, 300, 150
        cv2.rectangle(img, (x - 2 * r, y - 2 * r), (x + 8 * r, y + 2 * r), (20, 20, 20), -1)
        for name, lx, bgr in (('gruen', x, (60, 255, 60)), ('gelb', x + 3 * r, (60, 230, 255)), ('rot', x + 6 * r, (40, 40, 255))):
            if name == an:
                cv2.circle(img, (lx, y), r + 2, bgr, -1)
                cv2.circle(img, (lx, y), r - 2, (250, 250, 250), -1)
            else:
                cv2.circle(img, (lx, y), r, (40, 40, 40), -1)
        return img

    for f in ('rot', 'gelb', 'gruen'):
        ergebnisse.append(farbe(f'Ampel {f}', ampel_farbig(f), f))
    ergebnisse.append(farbe('Ampel aus', ampel_farbig(None), None))
    img = leere_szene(); cv2.rectangle(img, (100, 100), (220, 250), (40, 200, 40), -1)
    ergebnisse.append(farbe('gruener Gegenstand (kein Licht)', img, None))
    box = (300 - 12, 150 - 12, 60, 24)
    for f in ('rot', 'gruen'):
        k = ampel.farbe_in_box(ampel_farbig(f), box)
        ok = k == f
        print(f"{'OK  ' if ok else 'FEHLER'} Farbe im KI-Kasten ({f}): {k}")
        ergebnisse.append(ok)

    print()
    if all(ergebnisse):
        print('Alle Tests bestanden.')
        return 0
    print(f'{ergebnisse.count(False)} Test(s) fehlgeschlagen.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
