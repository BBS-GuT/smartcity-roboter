#!/usr/bin/env python3
# Messfahrt aufzeichnen und wieder abspielen (ohne ROS, damit testbar).
#
# Wozu? Wenn die Karte auf dem echten Roboter nicht stimmt, nimmt man eine Fahrt auf (Panel -> Karte ->
# "Messfahrt aufzeichnen") und spielt sie am Laptop ab: kartograf/abspielen.py rechnet die Karte noch einmal
# genau so aus wie der Kartograf und sagt, was nicht passt (LiDAR-Richtung, Lagesensor, Zeitstempel ...).
#
# Datei: karten/aufnahmen/<karte>_<datum>.jsonl.gz - eine Zeile JSON je Nachricht, gzip-gepackt.
# Bricht die Aufnahme ab (Strom weg), ist alles bis kurz davor lesbar.
#   {"typ": "kopf", "zeit": ..., "cfg": {...Einstellungen des Kartografen...}, "quelle": "roboter"}
#   {"typ": "scan", "t": Empfangszeit, "name": "/scan0", "stamp": Zeitstempel, "amin", "ainc", "rmin", "rmax",
#    "ti" (time_increment), "st" (scan_time), "r": [Abstaende in mm, 0 = keine Messung]}
#   {"typ": "odom", "t", "stamp", "vx", "vy", "wz", "x", "y", "w"}      (Geschwindigkeiten + Position)
#   {"typ": "imu",  "t", "stamp", "g": [x, y, z] Drehrate rad/s, "a": [x, y, z] Beschleunigung m/s^2}
#   {"typ": "bild", "t", "stamp", "jpg": Base64-JPEG (verkleinert)}
#   {"typ": "arm",  "t", "winkel": [6 Servowinkel]}     {"typ": "ki", "t", "daten": {kamera_ok, kamera_gier}}
#   {"typ": "pose", "t", "daten": {... /karte/pose ...}}  {"typ": "wahr", "t", "x", "y", "w"} (nur Simulation)
import base64
import gzip
import json
import os
import queue
import threading
import time
import zlib

import numpy as np


def scan_zu_json(d):
    """Scan-Daten (wie Kartierer.scan sie bekommt) -> kleines JSON (Abstaende in mm)."""
    r = np.asarray(d['r'], dtype=np.float64)
    mm = np.where(np.isfinite(r), np.round(r * 1000.0), 0).clip(0, 65000).astype(int)
    aus = {k: d[k] for k in ('stamp', 'amin', 'ainc', 'rmin', 'rmax', 'ti', 'st') if k in d}
    aus['r'] = mm.tolist()
    return aus


def scan_aus_json(z):
    d = dict(z)
    r = np.asarray(z['r'], dtype=np.float64) / 1000.0
    r[r <= 0] = np.inf
    d['r'] = r
    return d


class Aufnahme:
    """Schreibt eine Messfahrt in eine Datei. Laeuft in einem eigenen Thread (bremst den Kartografen nicht)."""
    MAX_BYTES = 400 * 1024 * 1024     # hoechstens so gross (dann hoert sie von selbst auf)
    MAX_DAUER = 30 * 60               # hoechstens so lange (s)

    def __init__(self, datei, kopf=None, bild_hz=2.0, bild_breite=320):
        self.datei = datei
        self.bild_hz, self.bild_breite = bild_hz, bild_breite
        self.start = time.time()
        self.anzahl = 0
        self.letztes_bild = 0.0
        self.grund = ''                 # warum sie aufgehoert hat
        self.q = queue.Queue(maxsize=5000)
        self.laeuft = True
        os.makedirs(os.path.dirname(datei) or '.', exist_ok=True)
        self.f = gzip.open(datei, 'wt', compresslevel=3)
        self.schreiben({'typ': 'kopf', 'zeit': self.start, 'version': 1, **(kopf or {})})
        self.thread = threading.Thread(target=self._schleife, daemon=True)
        self.thread.start()

    def schreiben(self, eintrag):
        """Eintrag (dict) in die Warteschlange. Ist sie voll (Rechner ueberlastet), geht er verloren."""
        if not self.laeuft:
            return
        try:
            self.q.put_nowait(eintrag)
        except queue.Full:
            pass

    def scan(self, t, name, d):
        self.schreiben({'typ': 'scan', 't': t, 'name': name, **scan_zu_json(d)})

    def bild(self, t, stamp, bgr):
        """Kamerabild gedrosselt (bild_hz) und verkleinert als JPEG."""
        if self.bild_hz <= 0 or t - self.letztes_bild < 1.0 / self.bild_hz:
            return
        self.letztes_bild = t
        import cv2
        h, w = bgr.shape[:2]
        klein = cv2.resize(bgr, (self.bild_breite, int(h * self.bild_breite / w)), interpolation=cv2.INTER_AREA)
        ok, jpg = cv2.imencode('.jpg', klein, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ok:
            self.schreiben({'typ': 'bild', 't': t, 'stamp': stamp, 'jpg': base64.b64encode(jpg.tobytes()).decode()})

    def _schleife(self):
        letzte_flush = time.time()
        while self.laeuft or not self.q.empty():
            try:
                e = self.q.get(timeout=0.5)
            except queue.Empty:
                e = None
            if e is not None:
                self.f.write(json.dumps(e, separators=(',', ':')) + '\n')
                self.anzahl += 1
            if time.time() - letzte_flush > 2.0:
                self.f.flush()          # alle 2 s: so ist die Datei auch nach einem Absturz lesbar
                letzte_flush = time.time()
                if os.path.getsize(self.datei) > self.MAX_BYTES:
                    self.grund = 'Datei zu gross'
                    self.laeuft = False
                elif time.time() - self.start > self.MAX_DAUER:
                    self.grund = 'laenger als 30 min'
                    self.laeuft = False
        self.f.close()

    def stopp(self):
        self.laeuft = False
        self.thread.join(timeout=10)

    def info(self):
        try:
            groesse = os.path.getsize(self.datei)
        except OSError:
            groesse = 0
        return {'datei': os.path.basename(self.datei), 'dauer': round(time.time() - self.start, 1),
                'nachrichten': self.anzahl, 'mb': round(groesse / 1e6, 1), 'laeuft': self.laeuft, 'grund': self.grund}


def lesen(datei):
    """Alle Eintraege einer Aufnahme nacheinander (dicts). Abgebrochene Dateien: bis zur kaputten Stelle."""
    try:
        with gzip.open(datei, 'rt') as f:
            for zeile in f:
                try:
                    yield json.loads(zeile)
                except ValueError:
                    return          # letzte Zeile halb geschrieben
    except (EOFError, OSError, zlib.error):
        return
