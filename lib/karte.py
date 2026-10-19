#!/usr/bin/env python3
# Kartierung (ohne ROS, damit testbar). Wird vom Kartografen (kartograf/kartograf.py) benutzt.
#
# Die Karte besteht aus mehreren Schichten, jede aus einem anderen Sensor:
#   Belegung   (LiDAR)        2D-Gitter, 2 cm je Zelle: frei / belegt / unbekannt.
#                             Jede Messung macht Zellen "sicherer" (Log-Odds), darum wird die Karte
#                             mit jeder Fahrt genauer. Was nur einmal im Weg stand (Person), verblasst.
#   Bodenbild  (Kamera)       Foto des Bodens von oben (1 cm je Pixel): Linien, Zebrastreifen ...
#   Wolke3D    (Tiefenkamera) Punkte UEBER dem Boden (Wuerfel, Schilder, Haeuser) als 3D-Wuerfelchen (2 cm)
#   Marker     (KI)           Ampeln, Stoppschilder, Zebrastreifen, Einbahnstrassen, Hindernisse
#
# Wo ist der Roboter? (Lokalisierung)
#   1. Mitrechnen: Raddrehung (Odometrie) + Drehrate (IMU) -> neue Position. Wird mit der Zeit ungenau.
#   2. Scan-Abgleich: Der LiDAR-Scan wird so lange verschoben/gedreht, bis er am besten auf die
#      bisherige Karte passt -> Fehler aus 1. wird laufend korrigiert.
#   3. Neue Fahrt mit vorhandener Karte: Der erste Scan wird in ALLEN Drehungen ueber die ganze Karte
#      geschoben (globale Suche), bis er passt. Danach weiter wie 2.
#   Zwei LiDARs: Der erste (Haupt-LiDAR) baut die Karte. Wo der zweite GENAU sitzt (ein paar Grad/cm
#   anders als eingestellt), lernt die Lokalisierung selbst, indem sie seine Scans auf die Karte schiebt.
#   Erst danach zaehlen seine Punkte mit. Ohne das dreht sich die Karte mit jeder Runde etwas weiter.
#   Scans kommen etwas spaeter an, als sie gemessen wurden: abgeglichen wird mit der Position ZUR MESSZEIT.
import json
import math
import os
import time

import cv2
import numpy as np

AUFLOESUNG = 0.02        # m je Zelle (Belegung, 3D)
BODEN_AUFLOESUNG = 0.01  # m je Pixel (Bodenbild)
GROESSE = 16.0           # m, Karte reicht von -8 bis +8 m um den Startpunkt der ersten Fahrt
LO_BELEGT, LO_FREI, LO_MAX = 0.85, -0.4, 5.0   # Log-Odds je Messung und Grenze

STANDARD = {
    # LiDAR-Messungen weiter weg nicht verwenden (m). Der T-mini Plus misst bis 12 m. In einem grossen Raum
    # mit wenigen Dingen in der Naehe sind die fernen Waende das Einzige, woran der Abgleich die Drehung erkennt.
    'max_reichweite': 8.0,
    'abgleich_xy': 0.06,       # Scan-Abgleich sucht +- so viel (m) ...
    'abgleich_w': 3.0,         # ... und +- so viel (Grad) um die mitgerechnete Position
    'min_guete': 0.35,         # so viel Anteil der Scanpunkte muss auf Belegtes passen, sonst nicht korrigieren
    'global_guete': 0.55,      # globale Suche: so gut muss es passen
}
# Passt der Abgleich laenger nicht, wird weiter gesucht (der Fehler vom Mitrechnen waechst mit der Zeit):
# (seit so vielen s unsicher, +- m, +- Grad)
SUCHFENSTER = ((0.0, None, None), (1.0, 0.15, 8.0), (3.0, 0.30, 15.0), (8.0, 0.50, 25.0))


def drehe(punkte, w):
    c, s = math.cos(w), math.sin(w)
    return punkte @ np.array([[c, s], [-s, c]], dtype=np.float64)


def in_karte(pose, punkte):
    """Punkte (N,2) im Roboter-System -> Karten-System."""
    return drehe(np.asarray(punkte, dtype=np.float64), pose[2]) + np.array(pose[:2])


def winkel(w):
    return (w + math.pi) % (2 * math.pi) - math.pi


class Belegung:
    """2D-Belegungsgitter aus LiDAR-Scans (Log-Odds: >0 belegt, <0 frei, 0 unbekannt)."""

    def __init__(self, groesse=GROESSE, aufl=AUFLOESUNG, cfg=None):
        self.aufl = aufl
        self.n = int(round(groesse / aufl))
        self.ursprung = -groesse / 2.0
        self.lo = np.zeros((self.n, self.n), np.float32)    # [iy, ix]
        self.c = dict(STANDARD)
        self.c.update(cfg or {})
        self._treffer = {}      # Trefferkarten fuer den Abgleich je Unschaerfe (werden bei Bedarf neu berechnet)
        self._treffer_stand = {}
        self.stand = 0          # zaehlt jedes Eintragen (Trefferkarte nur neu rechnen, wenn sich etwas getan hat)

    def zellen(self, xy):
        ij = np.floor((np.asarray(xy) - self.ursprung) / self.aufl).astype(np.int64)
        ok = (ij[:, 0] >= 0) & (ij[:, 0] < self.n) & (ij[:, 1] >= 0) & (ij[:, 1] < self.n)
        return ij, ok

    def eintragen(self, pose, punkte, gewicht=1.0):
        """Scan eintragen: Zellen auf dem Strahl werden freier, die Endpunkte belegter.
        gewicht=2: zaehlt doppelt (erster Scan einer neuen Karte: sofort etwas zum Abgleichen da)."""
        p = np.asarray(punkte, dtype=np.float64)
        r = np.hypot(p[:, 0], p[:, 1])
        p = p[(r > 0.05) & (r < self.c['max_reichweite'])]
        if len(p) == 0:
            return
        r = np.hypot(p[:, 0], p[:, 1])
        # freie Zellen: Strahlen vom LiDAR bis kurz vor den Treffer als Linien malen (OpenCV, schnell auch bei 8 m)
        kurz = p * (np.maximum(r - 1.5 * self.aufl, 0.0) / r)[:, None]
        start = np.floor((np.array(pose[:2]) - self.ursprung) / self.aufl).astype(np.int32)
        ziel = np.floor((in_karte(pose, kurz) - self.ursprung) / self.aufl).astype(np.int32)
        x0, y0 = np.minimum(ziel.min(axis=0), start)
        x1, y1 = np.maximum(ziel.max(axis=0), start) + 1
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, self.n), min(y1, self.n)
        idx = np.zeros(0, np.int64)
        if x1 > x0 and y1 > y0:
            maske = np.zeros((y1 - y0, x1 - x0), np.uint8)
            linien = np.stack([np.broadcast_to(start, ziel.shape), ziel], axis=1) - np.array([x0, y0], np.int32)
            cv2.polylines(maske, list(linien.reshape(-1, 2, 1, 2)), False, 1)
            yy, xx = np.nonzero(maske)
            idx = (yy + y0).astype(np.int64) * self.n + (xx + x0)
        ende = in_karte(pose, p)
        ije, oke = self.zellen(ende)
        idx_e = np.unique(ije[oke, 1] * self.n + ije[oke, 0])
        idx = np.setdiff1d(idx, idx_e, assume_unique=True)
        self.stand += 1
        flach = self.lo.ravel()
        flach[idx] += LO_FREI * gewicht
        flach[idx_e] += LO_BELEGT * gewicht
        np.clip(self.lo, -LO_MAX, LO_MAX, out=self.lo)

    # ---------------- Abgleich ----------------
    def trefferkarte(self, neu=False, unschaerfe=1.2):
        """1.0 auf belegten Zellen, nach aussen abfallend (fuer den Scan-Abgleich).
        unschaerfe (Zellen): groesser fuer die grobe Suche (sonst rutscht sie zwischen den Suchschritten durch)."""
        u = round(unschaerfe, 1)
        # neu rechnen nach 3x Eintragen (nicht nach Uhrzeit: so rechnet das Abspielen einer Aufnahme genau gleich)
        if u not in self._treffer or neu or not 0 <= self.stand - self._treffer_stand[u] < 3:
            belegt = (self.lo > 1.0).astype(np.uint8)
            abstand = cv2.distanceTransform(1 - belegt, cv2.DIST_L2, 3)
            self._treffer[u] = np.exp(-(abstand ** 2) / (2 * u ** 2)).astype(np.float32)
            self._treffer_stand[u] = self.stand
        return self._treffer[u]

    def leeren(self):
        """Alles vergessen (z. B. wenn ein grober Einstellungsfehler erkannt wurde)."""
        self.lo[:] = 0
        self._treffer, self._treffer_stand = {}, {}

    def bekannt(self):
        return bool((self.lo > 1.0).sum() > 50)

    def bekannt_anteil(self, pose, punkte):
        """Anteil der Scanpunkte, die in schon vermessenen Zellen landen (frei oder belegt).
        Klein = neues Gebiet (dort kann der Abgleich nicht gut passen, eintragen ist trotzdem richtig)."""
        p = np.asarray(punkte, dtype=np.float64)
        p = p[np.hypot(p[:, 0], p[:, 1]) < self.c['max_reichweite']]
        if len(p) == 0:
            return 0.0
        ij, ok = self.zellen(in_karte(pose, p))
        return float((np.abs(self.lo[ij[ok, 1], ij[ok, 0]]) > 0.5).sum() / len(p))

    def guete(self, pose, punkte):
        """Anteil (0..1) der Scanpunkte, die auf Belegtes treffen."""
        t = self.trefferkarte()
        ij, ok = self.zellen(in_karte(pose, punkte))
        if not ok.any():
            return 0.0
        return float(t[ij[ok, 1], ij[ok, 0]].sum() / len(punkte))

    def abgleichen(self, pose, punkte, xy=None, w=None, min_guete=None):
        """Beste Position in der Naehe der mitgerechneten. Rueckgabe: (pose, guete) oder (None, guete).
        xy (m) / w (Grad): so weit suchen (Standard: abgleich_xy / abgleich_w). Weite Suche: erst grob, dann fein."""
        p = np.asarray(punkte, dtype=np.float64)
        # nur Punkte, die auch eingetragen werden (weiter weg steht nichts in der Karte -> zaehlte als "passt nicht")
        p = p[np.hypot(p[:, 0], p[:, 1]) < self.c['max_reichweite']]
        if len(p) < 10:
            return None, 0.0
        if len(p) > 240:
            p = p[np.linspace(0, len(p) - 1, 240).astype(int)]
        xy = self.c['abgleich_xy'] if xy is None else xy
        w = math.radians(self.c['abgleich_w'] if w is None else w)
        # Suchstufen: jede sucht um das beste Ergebnis der vorigen, mit kleineren Schritten
        stufen = []
        while True:
            schritt_xy, schritt_w = max(self.aufl, xy / 4), max(math.radians(1.0), min(w / 6, math.radians(4.0)))
            stufen.append((xy, schritt_xy, w, schritt_w))
            if schritt_xy <= self.aufl + 1e-9 and schritt_w <= math.radians(1.0) + 1e-9:
                break
            xy, w = schritt_xy, schritt_w
        stufen.append((self.aufl, self.aufl / 2, math.radians(0.75), math.radians(0.25)))
        beste = (self.guete(pose, p), tuple(pose))
        for xy, schritt_xy, w, schritt_w in stufen:
            t = self.trefferkarte(unschaerfe=max(1.2, 0.6 * schritt_xy / self.aufl))
            mitte = beste[1]
            # grobe Stufen: mit der unscharfen Karte neu bewerten (sonst wird ein besseres Grob-Ergebnis verworfen)
            beste = (self._bewerten(t, mitte, p), mitte)
            versatz = np.arange(-xy, xy + 1e-9, schritt_xy)
            dx, dy = np.meshgrid(versatz, versatz)
            dx, dy = dx.ravel(), dy.ravel()
            for dw in np.arange(-w, w + 1e-9, schritt_w):
                q = drehe(p, mitte[2] + dw)
                xs = q[:, 0][None, :] + mitte[0] + dx[:, None]          # (K, N)
                ys = q[:, 1][None, :] + mitte[1] + dy[:, None]
                ix = np.clip(((xs - self.ursprung) / self.aufl).astype(np.int64), 0, self.n - 1)
                iy = np.clip(((ys - self.ursprung) / self.aufl).astype(np.int64), 0, self.n - 1)
                werte = t[iy, ix].sum(axis=1) / len(p)
                k = int(np.argmax(werte))
                if werte[k] > beste[0] + 1e-6:
                    beste = (float(werte[k]), (mitte[0] + dx[k], mitte[1] + dy[k], winkel(mitte[2] + dw)))
        if beste[0] < (self.c['min_guete'] if min_guete is None else min_guete):
            return None, beste[0]
        return beste[1], beste[0]

    def _bewerten(self, t, pose, p):
        ij, ok = self.zellen(in_karte(pose, p))
        return float(t[ij[ok, 1], ij[ok, 0]].sum() / len(p)) if ok.any() else 0.0

    def global_suchen(self, punkte, schritt_grad=2.0):
        """Position in der ganzen Karte suchen (neue Fahrt). Rueckgabe: (pose, guete, eindeutig)."""
        belegt = (self.lo > 1.0).astype(np.uint8)
        if belegt.sum() < 50:
            return None, 0.0, False
        p = np.asarray(punkte, dtype=np.float64)
        p = p[np.hypot(p[:, 0], p[:, 1]) < 3.0]
        if len(p) < 30:
            return None, 0.0, False
        # grob mit 4 cm suchen (schneller), nur im bekannten Bereich
        f = 2
        ys, xs = np.nonzero(belegt)
        rand = int(3.2 / self.aufl)
        y0, y1 = max(0, ys.min() - rand), min(self.n, ys.max() + rand)
        x0, x1 = max(0, xs.min() - rand), min(self.n, xs.max() + rand)
        t = self.trefferkarte(neu=True)[y0:y1, x0:x1]
        t_klein = cv2.resize(t, ((x1 - x0) // f, (y1 - y0) // f), interpolation=cv2.INTER_AREA)
        halb = int(3.0 / (self.aufl * f)) + 1
        kandidaten = []
        for w in np.radians(np.arange(0.0, 360.0, schritt_grad)):
            q = drehe(p, w)
            vorlage = np.zeros((2 * halb + 1, 2 * halb + 1), np.float32)
            ij = np.floor(q / (self.aufl * f)).astype(int) + halb
            ok = (ij >= 0).all(axis=1) & (ij <= 2 * halb).all(axis=1)
            vorlage[ij[ok, 1], ij[ok, 0]] = 1.0
            if t_klein.shape[0] < vorlage.shape[0] or t_klein.shape[1] < vorlage.shape[1]:
                return None, 0.0, False
            erg = cv2.matchTemplate(t_klein, vorlage, cv2.TM_CCORR)
            _, wert, _, ort = cv2.minMaxLoc(erg)
            x = x0 * self.aufl + self.ursprung + (ort[0] + halb + 0.5) * self.aufl * f
            y = y0 * self.aufl + self.ursprung + (ort[1] + halb + 0.5) * self.aufl * f
            kandidaten.append((wert / ok.sum(), (x, y, winkel(w))))
        kandidaten.sort(key=lambda k: -k[0])
        # die besten 3 fein nachpruefen
        beste = (0.0, None)
        for _, pose in kandidaten[:3]:
            fein, g = self.abgleichen(pose, p)
            if fein is not None and g > beste[0]:
                beste = (g, fein)
        if beste[1] is None:
            return None, 0.0, False
        # eindeutig? Ein deutlich anderer Ort darf nicht fast genauso gut passen
        zweite = 0.0
        for g, pose in kandidaten[3:40]:
            weit = math.hypot(pose[0] - beste[1][0], pose[1] - beste[1][1]) > 0.3
            if weit or abs(winkel(pose[2] - beste[1][2])) > math.radians(20):
                zweite = max(zweite, self.guete(pose, p))
        eindeutig = beste[0] >= self.c['global_guete'] and zweite < 0.85 * beste[0]
        return beste[1], beste[0], eindeutig


class Bodenbild:
    """Farbfoto des Bodens von oben, zusammengesetzt aus vielen Kamerabildern."""

    def __init__(self, groesse=GROESSE, aufl=BODEN_AUFLOESUNG):
        self.aufl = aufl
        self.n = int(round(groesse / aufl))
        self.ursprung = -groesse / 2.0
        self.farbe = np.zeros((self.n, self.n, 3), np.uint8)    # [iy, ix] BGR
        self.anzahl = np.zeros((self.n, self.n), np.uint8)

    def eintragen(self, pose, boden_xy, farben):
        """boden_xy: (N,2) Bodenpunkte im Roboter-System, farben: (N,3) BGR."""
        ij = np.floor((in_karte(pose, boden_xy) - self.ursprung) / self.aufl).astype(np.int64)
        ok = (ij[:, 0] >= 0) & (ij[:, 0] < self.n) & (ij[:, 1] >= 0) & (ij[:, 1] < self.n)
        ij, farben = ij[ok], np.asarray(farben)[ok].astype(np.float32)
        idx = ij[:, 1] * self.n + ij[:, 0]
        idx, erste = np.unique(idx, return_index=True)
        farben = farben[erste]
        alt_n = self.anzahl.ravel()[idx].astype(np.float32)
        anteil = 1.0 / np.minimum(alt_n + 1, 10)[:, None]   # gleitender Mittelwert (neue Fahrten zaehlen mit)
        f = self.farbe.reshape(-1, 3)
        f[idx] = (f[idx] * (1 - anteil) + farben * anteil).astype(np.uint8)
        self.anzahl.ravel()[idx] = np.minimum(alt_n + 1, 250).astype(np.uint8)


class Wolke3D:
    """Punkte UEBER dem Boden aus der Tiefenkamera, als Wuerfelchen (Voxel) zusammengefasst."""

    def __init__(self, aufl=AUFLOESUNG):
        self.aufl = aufl
        self.schluessel = np.zeros(0, np.int64)
        self.farbe = np.zeros((0, 3), np.float32)
        self.anzahl = np.zeros(0, np.int32)

    @staticmethod
    def _schluessel(ijk):
        ijk = ijk + 2 ** 20
        return (ijk[:, 0] << 42) | (ijk[:, 1] << 21) | ijk[:, 2]

    @staticmethod
    def _zurueck(s):
        return np.stack([(s >> 42) & 0x1FFFFF, (s >> 21) & 0x1FFFFF, s & 0x1FFFFF], axis=1) - 2 ** 20

    def eintragen(self, pose, punkte_xyz, farben):
        """punkte_xyz: (N,3) im Roboter-System (z = Hoehe ueber dem Boden), farben (N,3) BGR."""
        if len(punkte_xyz) == 0:
            return
        p = np.asarray(punkte_xyz, dtype=np.float64)
        xy = in_karte(pose, p[:, :2])
        ijk = np.floor(np.column_stack([xy, p[:, 2]]) / self.aufl).astype(np.int64)
        s = self._schluessel(ijk)
        alle_s = np.concatenate([self.schluessel, s])
        alle_f = np.concatenate([self.farbe * self.anzahl[:, None], np.asarray(farben, np.float32)])
        alle_n = np.concatenate([self.anzahl, np.ones(len(s), np.int32)])
        u, inv = np.unique(alle_s, return_inverse=True)
        n = np.bincount(inv, weights=alle_n).astype(np.int32)
        f = np.stack([np.bincount(inv, weights=alle_f[:, k]) for k in range(3)], axis=1) / n[:, None]
        self.schluessel, self.farbe, self.anzahl = u, f.astype(np.float32), np.minimum(n, 1000)

    def punkte(self, min_anzahl=2):
        ok = self.anzahl >= min_anzahl
        ijk = self._zurueck(self.schluessel[ok])
        return (ijk + 0.5) * self.aufl, self.farbe[ok]


MARKER_ARTEN = {
    'ampel': 'Ampel', 'stoppschild': 'Stoppschild', 'zebra': 'Zebrastreifen',
    'einfahrt_verboten': 'Einfahrt verboten', 'hindernis': 'Hindernis', 'person': 'Person',
}


class Marker:
    """Was die KI erkannt hat, mit Ort in der Karte. Gleiches in der Naehe wird zusammengefasst."""

    def __init__(self):
        self.liste = []

    def melden(self, art, x, y, jetzt=None, fahrt=0):
        jetzt = time.time() if jetzt is None else jetzt
        for m in self.liste:
            if m['art'] == art and math.hypot(m['x'] - x, m['y'] - y) < 0.35:
                n = min(m['anzahl'], 30)
                m['x'] += (x - m['x']) / (n + 1)
                m['y'] += (y - m['y']) / (n + 1)
                m['anzahl'] += 1
                m['zuletzt'], m['fahrt'] = jetzt, fahrt
                return m
        m = {'art': art, 'name': MARKER_ARTEN.get(art, art), 'x': x, 'y': y, 'anzahl': 1,
             'zuerst': jetzt, 'zuletzt': jetzt, 'fahrt': fahrt}
        self.liste.append(m)
        return m

    def sichere(self):
        """Nur Marker, die mehrmals gesehen wurden (gegen Fehlalarme)."""
        return [m for m in self.liste if m['anzahl'] >= 3]


class Karte:
    """Alle Schichten zusammen + Speichern/Laden/Export."""

    def __init__(self, ordner, cfg=None):
        self.ordner = ordner
        self.belegung = Belegung(cfg=cfg)
        self.boden = Bodenbild()
        self.wolke = Wolke3D()
        self.marker = Marker()
        self.fahrten = 0
        self.letzte_pose = None
        self.einbau = {}        # weitere LiDARs: Name -> gelernte Einbau-Korrektur (dx, dy, dw) oder None
        self.kalibrierung = {}  # selbst gelernt: Lagesensor-Skala, Haupt-LiDAR-Einbau ... (lib/kartierer.py)

    # ---------------- Speichern ----------------
    def laden(self):
        datei = os.path.join(self.ordner, 'karte.npz')
        if not os.path.exists(datei):
            return False
        d = np.load(datei)
        if d['belegung'].shape == self.belegung.lo.shape:
            self.belegung.lo[:] = d['belegung'].astype(np.float32)
        if d['boden_farbe'].shape == self.boden.farbe.shape:
            self.boden.farbe[:] = d['boden_farbe']
            self.boden.anzahl[:] = d['boden_anzahl']
        self.wolke.schluessel = d['wolke_schluessel']
        self.wolke.farbe = d['wolke_farbe'].astype(np.float32)
        self.wolke.anzahl = d['wolke_anzahl']
        info = json.loads(str(d['info']))
        self.fahrten = info.get('fahrten', 0)
        self.letzte_pose = info.get('letzte_pose')
        self.einbau = info.get('einbau', {})
        self.kalibrierung = info.get('kalibrierung', {})
        self.marker.liste = [m for m in info.get('marker', []) if m['art'] not in ('hindernis', 'person')]
        return True

    def speichern(self):
        os.makedirs(self.ordner, exist_ok=True)
        info = {'fahrten': self.fahrten, 'letzte_pose': self.letzte_pose, 'marker': self.marker.liste,
                'einbau': self.einbau, 'kalibrierung': self.kalibrierung,
                'aufloesung': self.belegung.aufl, 'ursprung': self.belegung.ursprung}
        tmp = os.path.join(self.ordner, 'karte_neu.npz')
        np.savez_compressed(tmp, belegung=self.belegung.lo.astype(np.float16),
                            boden_farbe=self.boden.farbe, boden_anzahl=self.boden.anzahl,
                            wolke_schluessel=self.wolke.schluessel, wolke_farbe=self.wolke.farbe.astype(np.uint8),
                            wolke_anzahl=self.wolke.anzahl, info=json.dumps(info))
        os.replace(tmp, os.path.join(self.ordner, 'karte.npz'))

    # ---------------- Anzeige ----------------
    def bereich(self, rand=0.3):
        """Bekannter Bereich (x0, y0, x1, y1) in m oder None."""
        lo = self.belegung.lo
        ys, xs = np.nonzero(np.abs(lo) > 0.5)
        by, bx = np.nonzero(self.boden.anzahl[::2, ::2] > 0)
        if len(xs) == 0 and len(bx) == 0:
            return None
        a, u = self.belegung.aufl, self.belegung.ursprung
        werte_x = np.concatenate([xs * a, bx * self.boden.aufl * 2]) + u
        werte_y = np.concatenate([ys * a, by * self.boden.aufl * 2]) + u
        return (float(werte_x.min() - rand), float(werte_y.min() - rand),
                float(werte_x.max() + rand), float(werte_y.max() + rand))

    def bild(self, bereich=None):
        """2D-Karte als Farbbild (BGR, 1 Pixel = 1 cm, oben = +y). Rueckgabe: (bild, bereich)."""
        bereich = bereich or self.bereich()
        if bereich is None:
            return None, None
        x0, y0, x1, y1 = bereich
        a = self.boden.aufl
        i0, i1 = int((x0 - self.boden.ursprung) / a), int((x1 - self.boden.ursprung) / a)
        j0, j1 = int((y0 - self.boden.ursprung) / a), int((y1 - self.boden.ursprung) / a)
        i0, j0 = max(i0, 0), max(j0, 0)
        i1, j1 = min(i1, self.boden.n), min(j1, self.boden.n)
        # Belegung auf 1 cm hochrechnen
        f = int(round(self.belegung.aufl / a))
        bi0, bi1, bj0, bj1 = i0 // f, (i1 + f - 1) // f, j0 // f, (j1 + f - 1) // f
        lo = np.repeat(np.repeat(self.belegung.lo[bj0:bj1, bi0:bi1], f, axis=0), f, axis=1)
        lo = lo[j0 - bj0 * f:j0 - bj0 * f + (j1 - j0), i0 - bi0 * f:i0 - bi0 * f + (i1 - i0)]
        bild = np.full(lo.shape + (3,), 150, np.uint8)               # unbekannt: grau
        bild[lo < -0.5] = (232, 232, 228)                             # frei: hell
        foto = self.boden.anzahl[j0:j1, i0:i1] > 0
        bild[foto] = self.boden.farbe[j0:j1, i0:i1][foto]             # Bodenfoto, wo gesehen
        belegt = lo > 1.0
        bild[belegt] = (60, 50, 40)                                   # Hindernis/Wand: dunkel
        return np.ascontiguousarray(bild[::-1]), (i0 * a + self.boden.ursprung, j0 * a + self.boden.ursprung,
                                                  i1 * a + self.boden.ursprung, j1 * a + self.boden.ursprung)

    def wolke_export(self, max_punkte=80000):
        """Alle 3D-Punkte zum Anschauen: Boden (Bodenfoto), Waende (LiDAR, hochgezogen), Gegenstaende (Tiefe).
        Rueckgabe: (xyz float32 (N,3), rgb uint8 (N,3))."""
        teile_p, teile_f = [], []
        # Boden: Bodenfoto mit 2 cm Abstand
        b = self.boden
        sel = b.anzahl[::2, ::2] > 0
        jj, ii = np.nonzero(sel)
        if len(ii):
            xs = (ii * 2 + 1) * b.aufl + b.ursprung
            ys = (jj * 2 + 1) * b.aufl + b.ursprung
            teile_p.append(np.column_stack([xs, ys, np.zeros_like(xs)]))
            teile_f.append(b.farbe[::2, ::2][sel][:, ::-1])
        # Waende: belegte Zellen als Saeulen 2-14 cm hoch
        g = self.belegung
        jj, ii = np.nonzero(g.lo > 1.5)
        if len(ii):
            xs = (ii + 0.5) * g.aufl + g.ursprung
            ys = (jj + 0.5) * g.aufl + g.ursprung
            for z in np.arange(0.02, 0.15, g.aufl):
                teile_p.append(np.column_stack([xs, ys, np.full_like(xs, z)]))
                teile_f.append(np.tile(np.array([[150, 120, 100]], np.uint8), (len(xs), 1)))
        # Gegenstaende aus der Tiefenkamera
        p, f = self.wolke.punkte()
        if len(p):
            teile_p.append(p)
            teile_f.append(f[:, ::-1].astype(np.uint8))
        if not teile_p:
            return np.zeros((0, 3), np.float32), np.zeros((0, 3), np.uint8)
        p = np.concatenate(teile_p).astype(np.float32)
        f = np.concatenate(teile_f).astype(np.uint8)
        if len(p) > max_punkte:
            wahl = np.linspace(0, len(p) - 1, max_punkte).astype(int)
            p, f = p[wahl], f[wahl]
        return p, f

    def ply(self):
        """3D-Karte als PLY-Datei (oeffnen z. B. mit MeshLab oder CloudCompare)."""
        p, f = self.wolke_export(max_punkte=500000)
        kopf = ('ply\nformat binary_little_endian 1.0\ncomment SmartCity-Karte\n'
                f'element vertex {len(p)}\nproperty float x\nproperty float y\nproperty float z\n'
                'property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n').encode()
        daten = np.zeros(len(p), dtype=[('x', '<f4'), ('y', '<f4'), ('z', '<f4'),
                                        ('r', 'u1'), ('g', 'u1'), ('b', 'u1')])
        daten['x'], daten['y'], daten['z'] = p[:, 0], p[:, 1], p[:, 2]
        daten['r'], daten['g'], daten['b'] = f[:, 0], f[:, 1], f[:, 2]
        return kopf + daten.tobytes()


# ---------------- Kamera -> Raum (gleiches Kameramodell wie Linienfolger/Tiefenkamera) ----------------
def kamera_strahlen(breite, hoehe, k, schritt=1):
    """Richtung je Bildpunkt im Roboter-System (Kamera in Fahrstellung). k: kamera_* Einstellungen."""
    f = (breite / 2) / math.tan(math.radians(k['kamera_fov']) / 2)
    u, v = np.meshgrid(np.arange(0, breite, schritt) - breite / 2 + 0.5,
                       np.arange(0, hoehe, schritt) - hoehe / 2 + 0.5)
    du, dv = u / f, v / f
    p = math.radians(k['kamera_neigung'])
    return math.cos(p) - dv * math.sin(p), -du, -math.sin(p) - dv * math.cos(p)


def kamera_drehen(xyz, gier_grad, k):
    """Arm hat die Kamera um die Hochachse gedreht (Servo 1): Punkte um den Armfuss mitdrehen."""
    if not gier_grad:
        return xyz
    basis = k.get('arm_basis_x', 0.05)
    w = math.radians(gier_grad)
    x, y = xyz[:, 0] - basis, xyz[:, 1]
    aus = xyz.copy()
    aus[:, 0] = basis + math.cos(w) * x - math.sin(w) * y
    aus[:, 1] = math.sin(w) * x + math.cos(w) * y
    return aus


def boden_aus_bild(bild, k, gier_grad=0.0, schritt=4, max_weit=0.9, tiefe_m=None):
    """Kamerabild -> Bodenpunkte (N,2) im Roboter-System + Farben (N,3). Annahme: ebener Boden.
    Mit Tiefenbild: Bildpunkte, die UEBER dem Boden liegen (Schild, Wuerfel), werden weggelassen."""
    h, w = bild.shape[:2]
    rx, ry, rz = kamera_strahlen(w, h, k, schritt)
    t = np.where(rz < -0.05, k['kamera_hoehe'] / np.maximum(-rz, 1e-6), np.inf)
    x, y = k['kamera_x'] + t * rx, t * ry
    ok = np.isfinite(t) & (np.hypot(x, y) < max_weit) & (x > 0.05)
    if tiefe_m is not None:
        d = cv2.resize(tiefe_m.astype(np.float32), (w, h), interpolation=cv2.INTER_NEAREST)[::schritt, ::schritt]
        ok &= ~((d > 0) & (d < 0.9 * t))     # Tiefe kuerzer als bis zum Boden -> etwas steht im Weg
    farben = bild[::schritt, ::schritt][ok]
    xyz = np.column_stack([x[ok], y[ok], np.zeros(ok.sum())])
    xyz = kamera_drehen(xyz, gier_grad, k)
    return xyz[:, :2], farben


def raum_aus_tiefe(tiefe_m, bild, k, gier_grad=0.0, schritt=4, min_hoehe=0.015, max_weit=1.5):
    """Tiefenbild (m) -> Punkte UEBER dem Boden (N,3) im Roboter-System + Farben (N,3).
    Annahme: Tiefenbild ist auf das Farbbild ausgerichtet (gleicher Blickwinkel)."""
    h, w = tiefe_m.shape
    rx, ry, rz = kamera_strahlen(w, h, k, schritt)
    t = tiefe_m[::schritt, ::schritt].astype(np.float32)
    x, y, z = k['kamera_x'] + t * rx, t * ry, k['kamera_hoehe'] + t * rz
    ok = (t > 0.12) & (t < max_weit) & (z > min_hoehe) & (z < 0.5)
    if bild is not None:
        farben = cv2.resize(bild, (w, h))[::schritt, ::schritt][ok]
    else:
        farben = np.full((ok.sum(), 3), 200, np.uint8)
    xyz = kamera_drehen(np.column_stack([x[ok], y[ok], z[ok]]), gier_grad, k)
    return xyz, farben


def verknuepfen(a, b):
    """Pose b (relativ zu a) an Pose a anhaengen."""
    c, s = math.cos(a[2]), math.sin(a[2])
    return (a[0] + c * b[0] - s * b[1], a[1] + s * b[0] + c * b[1], winkel(a[2] + b[2]))


def relativ(a, b):
    """Pose b im System von Pose a (Umkehrung von verknuepfen)."""
    c, s = math.cos(a[2]), math.sin(a[2])
    dx, dy = b[0] - a[0], b[1] - a[1]
    return (c * dx + s * dy, -s * dx + c * dy, winkel(b[2] - a[2]))


class LidarEinbau:
    """Wo sitzt ein weiterer LiDAR GENAU? Lernt die Abweichung (dx, dy, dw) gegenueber der Einstellung,
    indem seine Scans auf die Karte des Haupt-LiDARs geschoben werden (nur wenn die Position sicher ist)."""
    PROBEN = 25            # so viele passende Messungen ...
    STREUUNG_W = 1.0       # ... duerfen hoechstens so viel streuen (Grad) ...
    STREUUNG_XY = 0.02     # ... bzw. so viel (m), dann gilt die Korrektur

    def __init__(self, korrektur=None):
        self.korrektur = tuple(korrektur) if korrektur else None   # None = noch nicht gelernt
        self.proben = []
        self.letzte_probe = 0.0
        self.vermutung = (0.0, 0.0, 0.0)   # Startwert der Suche (aus der weiten Suche, s. u.)
        self.versuche = 0

    def probe(self, karte_belegung, pose, punkte, jetzt):
        """Eine Messung: Scan dieses LiDARs (ohne Korrektur) an der sicheren Position 'pose' abgleichen."""
        if jetzt - self.letzte_probe < 0.5:
            return
        self.letzte_probe = jetzt
        self.versuche += 1
        start = verknuepfen(pose, self.korrektur or self.vermutung)
        # weiter suchen als sonst: von Hand eingestellt kann er einige Grad daneben liegen
        neu, guete = karte_belegung.abgleichen(start, punkte, xy=0.12, w=10.0)
        if (neu is None or guete < 0.5) and self.korrektur is None and self.versuche % 10 == 0:
            # klappt lange nicht: sitzt er ganz anders (z. B. an der anderen Ecke, "vorne" um 90 Grad gedreht)?
            # -> einmal sehr weit suchen (+-40 cm, ganz herum) und von dort weiterlernen
            neu, guete = karte_belegung.abgleichen(start, punkte, xy=0.4, w=180.0, min_guete=0.5)
            if neu is not None:
                self.vermutung, self.proben = relativ(pose, neu), []
            return
        if neu is None or guete < 0.5:
            return
        self.proben = (self.proben + [relativ(pose, neu)])[-self.PROBEN * 2:]
        if len(self.proben) < self.PROBEN:
            return
        p = np.array(self.proben[-self.PROBEN:])
        p[:, 2] = p[0, 2] + np.array([winkel(v - p[0, 2]) for v in p[:, 2]])   # nicht ueber +-180 Grad springen
        mitte = np.median(p, axis=0)
        mitte[2] = winkel(mitte[2])
        if (np.degrees(np.std(p[:, 2])) < self.STREUUNG_W and np.std(p[:, 0]) < self.STREUUNG_XY
                and np.std(p[:, 1]) < self.STREUUNG_XY):
            alt = self.korrektur
            self.korrektur = tuple(round(float(v), 4) for v in mitte)
            return alt is None
        return False

    def anwenden(self, punkte):
        return in_karte(self.korrektur, punkte) if self.korrektur else punkte

    def text(self):
        if self.korrektur is None:
            return f'lerne Einbau ({len(self.proben)}/{self.PROBEN})'
        dx, dy, dw = self.korrektur
        return f'Einbau gelernt: {dx * 100:+.1f} / {dy * 100:+.1f} cm, {math.degrees(dw):+.1f} Grad'


class Lokalisierung:
    """Wo ist der Roboter in der Karte? Mitrechnen + Scan-Abgleich + (bei neuer Fahrt) globale Suche."""

    def __init__(self, karte):
        self.karte = karte
        self.odom = (0.0, 0.0, 0.0)     # mitgerechnete Position (eigenes System, driftet)
        self.verlauf = []               # (zeit, odom) der letzten Sekunden: wo war ich, als der Scan gemessen wurde?
        self.pose = None                # Position in der Karte, None = noch unbekannt
        self.guete = 0.0
        self.status = 'startet'
        self.letzter_eintrag = None     # (odom, zeit) beim letzten Eintragen in die Karte
        self.puffer = []                # Scans, solange die Position unbekannt ist: (odom, punkte)
        self.pfad = []                  # gefahrene Strecke dieser Fahrt (Karte)
        self.unsicher_seit = None       # seit wann passt der Abgleich nicht (dann weiter suchen)
        self.zuletzt_sicher = None      # Zeit des letzten sicheren Abgleichs
        self.letzter_abgleich = None    # fuer Selbstkalibrierung und Diagnose: zeit, pose, sicher, guete, fenster
        self.letzte_punkte = None       # letzter Scan (alle LiDARs zusammen, LiDAR-System) fuer die Anzeige
        # weitere LiDARs: Name -> LidarEinbau (gelernte Korrektur steht in der Karte, gilt fuer den naechsten Start)
        self.einbau = {name: LidarEinbau(k) for name, k in (karte.einbau or {}).items()}

    def bewegen(self, dx, dy, dw, zeit=None):
        """Bewegung seit dem letzten Aufruf im Roboter-System (aus Odometrie + IMU)."""
        schritt = (dx, dy, dw)
        self.odom = verknuepfen(self.odom, schritt)
        if self.pose is not None:
            self.pose = verknuepfen(self.pose, schritt)
        if zeit is not None:
            self.verlauf.append((zeit, self.odom))
            if len(self.verlauf) > 400 or (self.verlauf and zeit - self.verlauf[0][0] > 3.0):
                self.verlauf = self.verlauf[-200:]

    def odom_bei(self, zeit):
        """Mitgerechnete Position zur Zeit 'zeit' (aus dem Verlauf, zwischen zwei Eintraegen gemittelt)."""
        if zeit is None or not self.verlauf or zeit >= self.verlauf[-1][0]:
            return self.odom
        nach = None
        for t, o in reversed(self.verlauf):
            if t <= zeit:
                if nach is None or nach[0] - t < 1e-6:
                    return o
                a = (zeit - t) / (nach[0] - t)
                r = relativ(o, nach[1])
                return verknuepfen(o, (r[0] * a, r[1] * a, r[2] * a))
            nach = (t, o)
        return self.verlauf[0][1]

    def pose_bei(self, zeit):
        """Position in der Karte zur Zeit 'zeit' (z. B. Aufnahmezeit eines Kamerabilds) oder None."""
        if self.pose is None:
            return None
        return verknuepfen(self.pose, relativ(self.odom, self.odom_bei(zeit)))

    def einbau_text(self):
        return '; '.join(f'{n}: {e.text()}' for n, e in self.einbau.items())

    def scan(self, punkte, jetzt, eintragen=True, scan_zeit=None, weitere=None):
        """Neuer LiDAR-Scan (N,2) im Roboter-System. eintragen=False: nur abgleichen (z. B. beim schnellen Drehen).
        scan_zeit: wann er gemessen wurde (None = jetzt). weitere: {Name: (zeit, punkte)} der anderen LiDARs."""
        bel = self.karte.belegung
        odom_scan = self.odom_bei(scan_zeit)
        bis_jetzt = relativ(odom_scan, self.odom)          # Bewegung seit der Messung
        alle = [np.asarray(punkte, dtype=np.float64)]
        roh_weitere = {}
        for name, (zeit, p) in (weitere or {}).items():
            if len(p) == 0:
                continue
            # in das System des Haupt-Scans bringen (anderer Messzeitpunkt)
            p = in_karte(relativ(odom_scan, self.odom_bei(zeit)), p)
            roh_weitere[name] = p
            e = self.einbau.setdefault(name, LidarEinbau())
            if e.korrektur is not None:
                alle.append(e.anwenden(p))
        alle = np.concatenate(alle) if len(alle) > 1 else alle[0]
        self.letzte_punkte = alle
        if self.pose is None:
            if not bel.bekannt():
                self.pose, self.status = (0.0, 0.0, 0.0), 'neue Karte'
                self.karte.fahrten += 1
            else:
                self.puffer = (self.puffer + [(odom_scan, alle)])[-60:]
                return False
        pose_scan = verknuepfen(self.pose, relativ(self.odom, odom_scan))   # wo ich bei der Messung war
        sicher = not bel.bekannt()
        fenster = 0
        if bel.bekannt():
            # Passt es eine Weile nicht, weiter suchen (der Fehler der Odometrie waechst mit der Zeit).
            # Je weiter gesucht wird, desto besser muss es passen (sonst rastet er an einer falschen Stelle ein).
            dauer = jetzt - self.unsicher_seit if self.unsicher_seit is not None else 0.0
            fenster = max(i for i, (ab, _, _) in enumerate(SUCHFENSTER) if dauer >= ab)
            _, xy, w = SUCHFENSTER[fenster]
            neu, self.guete = bel.abgleichen(pose_scan, alle, xy, w, min_guete=bel.c['min_guete'] + 0.04 * fenster)
            if neu is not None:
                pose_scan, sicher = neu, True
                self.pose = verknuepfen(neu, bis_jetzt)
                self.status, self.unsicher_seit, self.zuletzt_sicher = 'ok', None, jetzt
            else:
                self.unsicher_seit = self.unsicher_seit or jetzt
                self.status = f'Abgleich unsicher ({self.guete:.0%}) - rechne mit'
                if fenster:
                    self.status += f', suche weiter (+-{SUCHFENSTER[fenster][1] * 100:.0f} cm)'
        else:
            self.zuletzt_sicher = jetzt
        self.letzter_abgleich = {'zeit': scan_zeit if scan_zeit is not None else jetzt, 'pose': pose_scan,
                                 'sicher': sicher and bel.bekannt(), 'guete': self.guete, 'fenster': fenster,
                                 'punkte': len(alle)}
        # Nur eintragen, was sicher ist: sonst wandert die Karte mit dem Fehler mit und dreht sich.
        # Ausnahme: neues Gebiet (dort kann der Abgleich nicht passen, weil noch nichts in der Karte steht).
        neues_gebiet = not sicher and bel.bekannt_anteil(pose_scan, alle) < 0.3
        if eintragen and (sicher or neues_gebiet) and self._weit_genug(jetzt):
            # leere Karte: erster Scan zaehlt doppelt, sonst passt der zweite evtl. schon nicht mehr genau darauf
            bel.eintragen(pose_scan, alle, gewicht=1.0 if bel.bekannt() else 2.0)
            self.letzter_eintrag = (self.odom, jetzt)
        # weitere LiDARs: Einbau lernen, wenn die Position sicher ist und die Karte schon etwas hat
        if sicher and bel.bekannt():
            for name, p in roh_weitere.items():
                if self.einbau[name].probe(bel, pose_scan, p, jetzt):
                    self.status = f'{name}: {self.einbau[name].text()}'
                self.karte.einbau[name] = self.einbau[name].korrektur
        if not self.pfad or math.hypot(self.pfad[-1][0] - self.pose[0], self.pfad[-1][1] - self.pose[1]) > 0.03:
            self.pfad.append((round(self.pose[0], 3), round(self.pose[1], 3)))
        return True

    def _weit_genug(self, jetzt):
        if self.letzter_eintrag is None:
            return True
        r = relativ(self.letzter_eintrag[0], self.odom)
        return math.hypot(r[0], r[1]) > 0.03 or abs(r[2]) > math.radians(3) or jetzt - self.letzter_eintrag[1] > 2.0

    def global_suchen(self):
        """Position in der vorhandenen Karte suchen (dauert einige Sekunden). True = gefunden."""
        if self.pose is not None or not self.puffer:
            return self.pose is not None
        odom_scan, punkte = self.puffer[-1]
        # die letzten Scans zusammenlegen (mehr Punkte = sicherer), alles relativ zum neuesten
        alle = [punkte] + [in_karte(relativ(odom_scan, o), p) for o, p in self.puffer[-8:-1]]
        pose, guete, eindeutig = self.karte.belegung.global_suchen(np.concatenate(alle))
        self.guete = guete
        if pose is None or not eindeutig:
            self.status = f'suche Position in der Karte ... (beste Uebereinstimmung {guete:.0%})'
            return False
        # gefundene Position gilt fuer den Zeitpunkt des Scans -> Bewegung seither dazurechnen
        self.pose = verknuepfen(pose, relativ(odom_scan, self.odom))
        self.status = f'Position gefunden ({guete:.0%})'
        self.karte.fahrten += 1
        for o, p in self.puffer:           # gepufferte Scans nachtragen
            self.karte.belegung.eintragen(verknuepfen(pose, relativ(odom_scan, o)), p)
        self.puffer = []
        return True
