#!/usr/bin/env python3
# Werkzeug zum Einstellen der Ampel-Erkennung. FAEHRT NICHT (sendet nichts an /cmd_vel).
#
# Live mit Kamera: Panel -> System -> "Ampel einstellen" (Fenster geht am Roboter-Bildschirm auf)
# Mit gespeicherten Fotos (ohne Roboter, auch auf dem Laptop):
#     python3 line_follower/ampel_kalibrieren.py --bilder ampel_bilder
#
# Tasten (Fenster "Ampel" muss angeklickt sein):
#   s = aktuelles Bild in ampel_bilder/ speichern
#   w = Werte in config/ampel.yaml speichern (gilt nach Neustart von KI/Linienfolger)
#   n / b = naechstes / vorheriges Foto (nur mit --bilder)
#   q oder Esc = beenden
# Maus ueber dem Bild: Lupe + Farbwerte (H, S, V) des Pixels unter der Maus.
import argparse
import glob
import os
import sys
import time

import cv2

import ampel

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
YAML = os.path.join(REPO, 'config', 'ampel.yaml')
BILDER = os.path.join(REPO, 'ampel_bilder')

# (Name, Reglermaximum, Faktor): Reglerwert = Wert * Faktor (Regler kennen nur ganze Zahlen)
REGLER = [
    ('red_top', 100, 100), ('red_bottom', 100, 100), ('red_left', 100, 100), ('red_right', 100, 100),
    ('red_hue_max', 30, 1), ('red_hue_min2', 180, 1),
    ('red_sat_min', 255, 1), ('red_val_min', 255, 1), ('red_core_val', 255, 1),
    ('red_min_area', 500, 1), ('red_max_area', 10000, 1),
    ('red_max_aspect', 100, 10), ('red_min_fill', 100, 100), ('red_peak_min', 255, 1),
    ('red_dark_val', 255, 1), ('red_dark_frac', 100, 100),
]


def lade_yaml():
    werte = dict(ampel.STANDARD)
    if os.path.exists(YAML):
        try:
            import yaml
            with open(YAML) as f:
                daten = yaml.safe_load(f) or {}
            werte.update(daten.get('line_follower', {}).get('ros__parameters', {}))
            print(f'Werte geladen aus {YAML}')
        except Exception as e:
            print(f'Konnte {YAML} nicht lesen ({e}), nehme Standardwerte')
    return werte


def speichere_yaml(werte):
    os.makedirs(os.path.dirname(YAML), exist_ok=True)
    zeilen = ['# Ampel-Einstellungen, erzeugt mit ampel_kalibrieren.py am ' + time.strftime('%d.%m.%Y %H:%M'),
              '# Wird von Panel, KI und Linienfolger automatisch geladen.',
              'line_follower:', '  ros__parameters:']
    for name, std in ampel.STANDARD.items():
        w = werte[name]
        # Typ wie im Standard, sonst meckert ROS (z. B. 3 statt 3.0)
        zeilen.append(f'    {name}: {float(w):.2f}' if isinstance(std, float) else f'    {name}: {int(w)}')
    with open(YAML, 'w') as f:
        f.write('\n'.join(zeilen) + '\n')
    print(f'Gespeichert: {YAML}')
    print('Ins Repository:  git add config/ampel.yaml && git commit -m "Ampelwerte eingestellt" && git push')


class Quelle:
    """Liefert Bilder: entweder aus ROS (Kamera) oder aus einem Ordner."""

    def __init__(self, args):
        self.dateien = []
        self.index = 0
        self.node = None
        self.bild = None
        if args.bilder:
            for endung in ('*.png', '*.jpg', '*.jpeg'):
                self.dateien += glob.glob(os.path.join(args.bilder, endung))
            self.dateien.sort()
            if not self.dateien:
                sys.exit(f'Keine Bilder in {args.bilder}')
            print(f'{len(self.dateien)} Bilder gefunden')
        else:
            import rclpy
            from cv_bridge import CvBridge
            from sensor_msgs.msg import Image
            rclpy.init()
            self.rclpy = rclpy
            self.node = rclpy.create_node('ampel_kalibrieren')
            bridge = CvBridge()

            def empfang(msg):
                self.bild = bridge.imgmsg_to_cv2(msg, 'bgr8')
            self.node.create_subscription(Image, args.topic, empfang, 10)
            print(f'Warte auf Bilder von {args.topic} ... (laeuft scripts/kamera.sh?)')

    def holen(self):
        if self.node is not None:
            self.rclpy.spin_once(self.node, timeout_sec=0.02)
            return self.bild
        if self.bild is None:
            self.bild = cv2.imread(self.dateien[self.index])
            print(f'Bild {self.index + 1}/{len(self.dateien)}: {self.dateien[self.index]}')
        return self.bild

    def blaettern(self, schritt):
        if self.dateien:
            self.index = (self.index + schritt) % len(self.dateien)
            self.bild = None

    def ende(self):
        if self.node is not None:
            self.node.destroy_node()
            self.rclpy.shutdown()


def main():
    ap = argparse.ArgumentParser(description='Ampel-Erkennung einstellen (faehrt nicht)')
    ap.add_argument('--bilder', help='Ordner mit Fotos statt Live-Kamera')
    ap.add_argument('--topic', default='/camera/color/image_raw', help='Kamera-Topic')
    args, _ = ap.parse_known_args()

    werte = lade_yaml()
    quelle = Quelle(args)
    maus = [0, 0]

    cv2.namedWindow('Ampel')
    cv2.namedWindow('Regler', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Regler', 500, 700)
    for name, maximum, faktor in REGLER:
        start = int(round(min(maximum, werte[name] * faktor)))
        cv2.createTrackbar(name, 'Regler', start, maximum, lambda _: None)

    def mausbewegung(ereignis, x, y, flags, param):
        maus[0], maus[1] = x, y
    cv2.setMouseCallback('Ampel', mausbewegung)

    treffer_folge = 0
    try:
        while True:
            img = quelle.holen()
            taste = cv2.waitKey(30) & 0xFF
            if img is None:
                if taste in (ord('q'), 27):
                    break
                continue
            for name, _, faktor in REGLER:
                wert = cv2.getTrackbarPos(name, 'Regler') / faktor
                werte[name] = wert if isinstance(ampel.STANDARD[name], float) else int(wert)

            erg = ampel.finde_rot(img, werte)
            treffer_folge = treffer_folge + 1 if erg['treffer'] else 0
            view = img.copy()
            ampel.zeichne(view, erg)
            h, w = img.shape[:2]
            mx, my = min(maus[0], w - 1), min(maus[1], h - 1)
            hh, ss, vv = cv2.cvtColor(img[my:my + 1, mx:mx + 1], cv2.COLOR_BGR2HSV)[0, 0]
            text = 'ROT ERKANNT' if erg['treffer'] else 'kein Rot'
            cv2.putText(view, f'{text}  ({treffer_folge} Bilder in Folge)', (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.putText(view, f'Maus x={mx} y={my}  H={hh} S={ss} V={vv}', (10, h - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
            cv2.imshow('Ampel', view)

            # Lupe: 4-fach vergroessert um die Maus herum (LEDs sind winzig)
            r = 40
            x0, y0 = max(0, mx - r), max(0, my - r)
            ausschnitt = view[y0:y0 + 2 * r, x0:x0 + 2 * r]
            if ausschnitt.size:
                cv2.imshow('Lupe', cv2.resize(ausschnitt, None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST))
            if erg['maske'] is not None:
                cv2.imshow('Maske Rot', erg['maske'])

            if taste in (ord('q'), 27):
                break
            elif taste == ord('s'):
                os.makedirs(BILDER, exist_ok=True)
                datei = os.path.join(BILDER, time.strftime('%Y%m%d_%H%M%S') + '.png')
                cv2.imwrite(datei, img)
                print(f'Bild gespeichert: {datei}')
            elif taste == ord('w'):
                speichere_yaml(werte)
            elif taste == ord('n'):
                quelle.blaettern(1)
            elif taste == ord('b'):
                quelle.blaettern(-1)
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        quelle.ende()


if __name__ == '__main__':
    main()
