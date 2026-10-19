#!/usr/bin/env python3
# Simulierte SmartCity (ohne ROS, damit testbar): Strecke, Haeuser, Ampel, Schilder,
# Zebrastreifen, Holzwuerfel, Fussgaenger. Erzeugt Kamera-, Tiefen- und LiDAR-Bilder
# aus der Sicht des Roboters.
#
# Koordinaten: Meter, x nach rechts, y nach oben (Draufsicht). Roboter: x = vorne, y = links.
import math

import cv2
import numpy as np

AUFLOESUNG = 0.005           # Meter pro Pixel im Weltbild
BREITE, HOEHE = 3.0, 2.2     # Welt in Metern
LIDAR_HOEHE = 0.10           # LiDAR misst in dieser Hoehe -> niedrigere Dinge sieht er NICHT

# Kamera (am Arm in Fahrstellung). Werte geschaetzt, am echten Roboter unbekannt.
KAMERA = {'x': 0.12, 'hoehe': 0.22, 'neigung_deg': 32.0, 'fov_deg': 70.0, 'breite': 640, 'hoehe_px': 480,
          'arm_basis_x': 0.05}


# --------------------------------------------------------------------------- Strecke
def strecke(x0=0.4, y0=0.4, x1=2.6, y1=1.8, r=0.25, schritt=0.005):
    """Abgerundetes Rechteck gegen den Uhrzeigersinn. Rueckgabe: Punkte (N, 2) und Laenge."""
    teile = []

    def gerade(a, b):
        n = max(2, int(math.dist(a, b) / schritt))
        teile.append(np.linspace(a, b, n, endpoint=False))

    def bogen(cx, cy, w0):
        n = max(2, int(r * math.pi / 2 / schritt))
        w = np.linspace(w0, w0 + math.pi / 2, n, endpoint=False)
        teile.append(np.stack([cx + r * np.cos(w), cy + r * np.sin(w)], axis=1))

    gerade((x0 + r, y0), (x1 - r, y0)); bogen(x1 - r, y0 + r, -math.pi / 2)
    gerade((x1, y0 + r), (x1, y1 - r)); bogen(x1 - r, y1 - r, 0)
    gerade((x1 - r, y1), (x0 + r, y1)); bogen(x0 + r, y1 - r, math.pi / 2)
    gerade((x0, y1 - r), (x0, y0 + r)); bogen(x0 + r, y0 + r, math.pi)
    p = np.concatenate(teile)
    return p, float(np.sum(np.linalg.norm(np.diff(np.vstack([p, p[:1]]), axis=0), axis=1)))


class Welt:
    def __init__(self, mit_einbahn=True, mit_wuerfel=True, mit_fussgaenger=True, halle=False):
        # halle=True: wie in echt - um das Spielfeld keine Waende, sondern ein grosser Raum (Waende 3-5 m weg).
        # Der LiDAR sieht dann viele Punkte weit weg und weniger Haeuser in der Naehe (schwerer fuer die Karte).
        self.halle = halle
        self.punkte, self.laenge = strecke()
        d = np.diff(np.vstack([self.punkte, self.punkte[:1]]), axis=0)
        self.richtung = np.arctan2(d[:, 1], d[:, 0])
        self.s_werte = np.concatenate([[0], np.cumsum(np.linalg.norm(d, axis=1))[:-1]])
        # Dinge entlang der Strecke (s = Meter ab Start)
        self.ampel_s, self.zebra_s, self.wuerfel_s, self.schild_s, self.einbahn_s = 1.2, 2.45, 3.75, 4.6, 5.85
        self.ampel = 'aus'
        self.zylinder = []     # dicts: x, y, r, h, farbe, name
        if mit_wuerfel:
            x, y, _ = self.pose_bei(self.wuerfel_s)
            self.zylinder.append({'x': x, 'y': y, 'r': 0.025, 'h': 0.045, 'farbe': (60, 120, 180), 'name': 'wuerfel'})
        if mit_fussgaenger:  # wartet rechts am Zebrastreifen (Gehweg), will rueber
            x, y, w = self.pose_bei(self.zebra_s + 0.05)
            self.zylinder.append({'x': x + 0.2 * math.sin(w), 'y': y - 0.2 * math.cos(w), 'r': 0.025, 'h': 0.14,
                                  'farbe': (40, 40, 160), 'name': 'fussgaenger'})
        self.schilder = []     # dicts: x, y, z, blick (Richtung, in die das Schild zeigt), art
        for s, art in [(self.ampel_s, 'ampel'), (self.schild_s, 'stopp')] + ([(self.einbahn_s, 'einfahrt_verboten')] if mit_einbahn else []):
            x, y, w = self.pose_bei(s)
            self.schilder.append({'x': x + 0.12 * math.sin(w), 'y': y - 0.12 * math.cos(w), 'z': 0.12,
                                  'blick': w + math.pi, 'art': art, 's': s})
        # Haeuser (Rechtecke x0, y0, x1, y1), Hoehe egal (hoeher als der LiDAR)
        self._cache = {}
        # mindestens 22 cm neben der Linie (Roboter ist ca. 30 cm breit)
        self.haeuser = [(0.0, 0.0, 0.18, 0.6), (2.82, 1.4, 3.0, 2.2), (1.0, 2.02, 1.7, 2.2), (1.9, 0.0, 2.4, 0.18),
                        (0.9, 0.8, 1.3, 1.35), (1.7, 0.75, 2.1, 1.2), (2.82, 0.2, 2.98, 0.55)]
        if halle:   # in der Halle: nur zwei Haeuser in LiDAR-Hoehe, der Rest ist weit weg
            self.haeuser = [self.haeuser[0], self.haeuser[4]]
        self._raster()

    def pose_bei(self, s):
        """Punkt + Richtung auf der Linie bei Strecke s."""
        i = int(np.searchsorted(self.s_werte, s % self.laenge, side='right') - 1)
        return float(self.punkte[i, 0]), float(self.punkte[i, 1]), float(self.richtung[i])

    def s_von(self, x, y):
        """Naechster Streckenpunkt: (s, seitlicher Abstand in m)."""
        d = np.hypot(self.punkte[:, 0] - x, self.punkte[:, 1] - y)
        i = int(np.argmin(d))
        return float(self.s_werte[i]), float(d[i])

    # ------------------------------------------------------------------ Bodenbild
    def _raster(self):
        h, w = int(HOEHE / AUFLOESUNG), int(BREITE / AUFLOESUNG)
        img = np.full((h, w, 3), 205, np.uint8)
        rng = np.random.default_rng(1)
        img = np.clip(img.astype(np.int16) + rng.normal(0, 5, img.shape).astype(np.int16), 0, 255).astype(np.uint8)
        px = self.welt_zu_pixel(self.punkte)
        cv2.polylines(img, [px.astype(np.int32)], True, (25, 25, 25), int(0.025 / AUFLOESUNG))
        # Zebrastreifen: Balken parallel zur Fahrtrichtung, quer ueber die Strasse
        x, y, wr = self.pose_bei(self.zebra_s)
        vor, links = np.array([math.cos(wr), math.sin(wr)]), np.array([-math.sin(wr), math.cos(wr)])
        for k in range(-3, 4):
            mitte = np.array([x, y]) + links * k * 0.04
            ecken = [mitte + vor * a + links * b for a, b in ((-0.04, -0.011), (0.04, -0.011), (0.04, 0.011), (-0.04, 0.011))]
            cv2.fillPoly(img, [self.welt_zu_pixel(np.array(ecken)).astype(np.int32)], (25, 25, 25))
        for x0, y0, x1, y1 in self.haeuser:
            a, b = self.welt_zu_pixel(np.array([[x0, y0], [x1, y1]])).astype(np.int32)
            cv2.rectangle(img, tuple(a), tuple(b), (90, 110, 150), -1)
        self.boden = img

    @staticmethod
    def welt_zu_pixel(p):
        p = np.asarray(p, dtype=np.float64)
        return np.stack([p[..., 0] / AUFLOESUNG, (HOEHE - p[..., 1]) / AUFLOESUNG], axis=-1)

    # ------------------------------------------------------------------ Draufsicht (zum Zuschauen)
    def draufsicht(self, pose, arm_dreh_deg=0.0, greifer=None, haelt=False, spur=()):
        """Bild der ganzen Welt von oben mit Roboter, Arm, Ampel, Wuerfel, Fussgaenger (BGR).
        greifer: (x, y) der Greiferspitze in der Welt oder None. spur: bisher gefahrene Punkte."""
        img = self.boden.copy()
        px = lambda p: tuple(int(v) for v in self.welt_zu_pixel(p))
        if len(spur) > 1:
            cv2.polylines(img, [self.welt_zu_pixel(np.array(spur)).astype(np.int32)], False, (200, 120, 40), 1)
        farbe_ampel = {'rot': (40, 40, 230), 'gelb': (40, 220, 240), 'gruen': (60, 200, 60), 'aus': (90, 90, 90)}
        for s in self.schilder:
            f = farbe_ampel[self.ampel] if s['art'] == 'ampel' else (30, 30, 200) if s['art'] == 'stopp' else (250, 250, 250)
            cv2.circle(img, px((s['x'], s['y'])), 7, f, -1)
            cv2.circle(img, px((s['x'], s['y'])), 7, (20, 20, 20), 1)
            text = {'ampel': 'Ampel', 'stopp': 'STOP', 'einfahrt_verboten': 'Einfahrt verb.'}[s['art']]
            cv2.putText(img, text, px((s['x'] + 0.03, s['y'] - 0.06)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (20, 20, 20), 1)
        for z in self.zylinder:
            cv2.circle(img, px((z['x'], z['y'])), max(3, int(z['r'] / AUFLOESUNG)), z['farbe'], -1)
            cv2.putText(img, z['name'], px((z['x'] + 0.03, z['y'] + 0.03)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (20, 20, 20), 1)
        x, y, w = pose
        c, s = math.cos(w), math.sin(w)
        ecken = [(x + c * a - s * b, y + s * a + c * b) for a, b in ((0.15, 0.12), (0.15, -0.12), (-0.15, -0.12), (-0.15, 0.12))]
        cv2.fillPoly(img, [self.welt_zu_pixel(np.array(ecken)).astype(np.int32)], (70, 160, 70))
        cv2.polylines(img, [self.welt_zu_pixel(np.array(ecken)).astype(np.int32)], True, (20, 60, 20), 2)
        cv2.arrowedLine(img, px((x, y)), px((x + 0.2 * c, y + 0.2 * s)), (255, 255, 255), 2, tipLength=0.3)
        # Arm: von der Basis in Richtung Servo 1, bis zum Greifer (falls bekannt)
        basis = (x + KAMERA['arm_basis_x'] * c, y + KAMERA['arm_basis_x'] * s)
        a = w + math.radians(arm_dreh_deg)
        ziel = greifer or (basis[0] + 0.12 * math.cos(a), basis[1] + 0.12 * math.sin(a))
        cv2.line(img, px(basis), px(ziel), (0, 140, 255), 3)
        cv2.circle(img, px(ziel), 5, (0, 0, 255) if haelt else (0, 140, 255), -1)
        return img

    # ------------------------------------------------------------------ Kamera
    @staticmethod
    def kamera_achsen(arm_dreh_deg=0.0):
        """Kamera-Position und Achsen (vor, rechts, unten) im Roboter-Koordinatensystem."""
        k = KAMERA
        p = math.radians(k['neigung_deg'])
        vor = np.array([math.cos(p), 0, -math.sin(p)])
        rechts = np.array([0, -1.0, 0])
        unten = np.array([-math.sin(p), 0, -math.cos(p)])
        c = np.array([k['x'], 0.0, k['hoehe']])
        if arm_dreh_deg:  # Servo 1 dreht die Kamera um die Arm-Basis
            a = math.radians(arm_dreh_deg)
            dreh = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
            basis = np.array([k['arm_basis_x'], 0, 0])
            c = basis + dreh @ (c - basis)
            vor, rechts, unten = dreh @ vor, dreh @ rechts, dreh @ unten
        return c, vor, rechts, unten

    def _strahlen(self, arm_dreh_deg=0.0, schritt=1):
        """Sehstrahlen aller Pixel im Roboter-Koordinatensystem: Ursprung (3,), Richtungen (H, W, 3)."""
        k = KAMERA
        b, h = k['breite'] // schritt, k['hoehe_px'] // schritt
        f = (b / 2) / math.tan(math.radians(k['fov_deg']) / 2)
        u, v = np.meshgrid(np.arange(b) - b / 2 + 0.5, np.arange(h) - h / 2 + 0.5)
        c, vor, rechts, unten = self.kamera_achsen(arm_dreh_deg)
        r = (u / f)[..., None] * rechts + (v / f)[..., None] * unten + vor
        return c, r, f

    def _vorberechnet(self, arm_dreh_deg, schritt):
        """Alles, was nicht von der Roboter-Position abhaengt (wird zwischengespeichert)."""
        schluessel = (round(arm_dreh_deg), schritt)
        if schluessel not in self._cache:
            c, r, f = self._strahlen(arm_dreh_deg, schritt)
            rz = r[..., 2]
            t_boden = np.where(rz < -1e-6, -c[2] / np.minimum(rz, -1e-6), np.inf)
            t_boden[t_boden > 3.0] = np.inf
            gx, gy = c[0] + t_boden * r[..., 0], c[1] + t_boden * r[..., 1]
            self._cache[schluessel] = (c, r, f, t_boden, gx, gy, ~np.isfinite(t_boden))
        return self._cache[schluessel]

    def kamera(self, pose, arm_dreh_deg=0.0, schritt=1):
        """Farbbild (BGR) und Tiefenbild (m, entlang der Blickachse) aus Sicht des Roboters."""
        x, y, w = pose
        c, r, f, t_boden, gx, gy, himmel = self._vorberechnet(arm_dreh_deg, schritt)
        cw, sw = math.cos(w), math.sin(w)
        with np.errstate(invalid='ignore'):
            mx = ((x + cw * gx - sw * gy) / AUFLOESUNG).astype(np.float32)
            my = ((HOEHE - (y + sw * gx + cw * gy)) / AUFLOESUNG).astype(np.float32)
        mx[himmel] = -1
        my[himmel] = -1
        bild = cv2.remap(self.boden, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(150, 150, 150))
        bild[himmel] = (170, 160, 150)  # Hintergrund ueber dem Boden
        tiefe = t_boden.copy()  # Richtung hat Kamera-z = 1 -> t = Tiefe entlang der Blickachse
        # Zylinder (Wuerfel, Fussgaenger) in Weltkoordinaten -> Roboterkoordinaten
        cwr, swr = math.cos(-w), math.sin(-w)
        for z in self.zylinder:
            zx, zy = cwr * (z['x'] - x) - swr * (z['y'] - y), swr * (z['x'] - x) + cwr * (z['y'] - y)
            if math.hypot(zx, zy) > 2.0:
                continue
            ox, oy = c[0] - zx, c[1] - zy
            a = r[..., 0] ** 2 + r[..., 1] ** 2
            bq = 2 * (ox * r[..., 0] + oy * r[..., 1])
            cq = ox ** 2 + oy ** 2 - z['r'] ** 2
            disk = bq ** 2 - 4 * a * cq
            t = np.where(disk >= 0, (-bq - np.sqrt(np.maximum(disk, 0))) / (2 * a), np.inf)
            hz = c[2] + t * r[..., 2]
            treffer = (t > 0) & (hz >= 0) & (hz <= z['h']) & (t < tiefe)
            tiefe[treffer] = t[treffer]
            bild[treffer] = z['farbe']
        self._schilder_malen(bild, pose, c, arm_dreh_deg, f)
        tiefe[~np.isfinite(tiefe)] = 0.0  # keine Messung
        return bild, tiefe

    def _schilder_malen(self, bild, pose, c, arm_dreh_deg, f):
        x, y, w = pose
        hp, bp = bild.shape[:2]
        c, vor, rechts, unten = self.kamera_achsen(arm_dreh_deg)
        for s in self.schilder:
            if s['art'] == 'ampel' and self.ampel == 'aus':
                continue
            # zeigt das Schild zum Roboter?
            if math.cos(s['blick']) * (x - s['x']) + math.sin(s['blick']) * (y - s['y']) <= 0:
                continue
            dx, dy = s['x'] - x, s['y'] - y
            d = np.array([math.cos(-w) * dx - math.sin(-w) * dy, math.sin(-w) * dx + math.cos(-w) * dy, s['z']]) - c
            zc, xc, yc = float(d @ vor), float(d @ rechts), float(d @ unten)
            if zc < 0.08 or zc > 1.6:
                continue
            u, v = int(bp / 2 + f * xc / zc), int(hp / 2 + f * yc / zc)
            groesse = f / zc
            if not (-50 < u < bp + 50 and -50 < v < hp + 50):
                continue
            if s['art'] == 'stopp':
                rr = max(3, int(0.03 * groesse))
                pts = np.array([[u + rr * math.cos(math.pi / 8 + i * math.pi / 4), v + rr * math.sin(math.pi / 8 + i * math.pi / 4)]
                                for i in range(8)], np.int32)
                cv2.fillPoly(bild, [pts], (30, 30, 200))
                cv2.putText(bild, 'STOP', (u - int(rr * 0.75), v + int(rr * 0.25)), cv2.FONT_HERSHEY_SIMPLEX,
                            max(0.2, rr / 40), (255, 255, 255), max(1, rr // 12))
            elif s['art'] == 'einfahrt_verboten':
                rr = max(3, int(0.03 * groesse))
                cv2.circle(bild, (u, v), rr, (30, 30, 200), -1)
                cv2.rectangle(bild, (u - int(rr * 0.7), v - max(1, int(rr * 0.17))),
                              (u + int(rr * 0.7), v + max(1, int(rr * 0.17))), (250, 250, 250), -1)
            elif s['art'] == 'ampel':
                rr = max(2, int(0.006 * groesse))
                cv2.rectangle(bild, (u - 5 * rr, v - 2 * rr), (u + 5 * rr, v + 2 * rr), (20, 20, 20), -1)
                for name, lx, bgr in (('gruen', u - 3 * rr, (60, 255, 60)), ('gelb', u, (60, 230, 255)), ('rot', u + 3 * rr, (60, 60, 255))):
                    if name == self.ampel:
                        cv2.circle(bild, (lx, v), rr + 1, bgr, -1)
                        cv2.circle(bild, (lx, v), max(1, rr - 1), (250, 250, 250), -1)
                    else:
                        cv2.circle(bild, (lx, v), rr, (40, 40, 40), -1)

    # ------------------------------------------------------------------ LiDAR
    def lidar(self, pose, n=360, rauschen=0.004, rng=None):
        """Abstaende fuer n Strahlen, Winkel -pi..pi relativ zur Roboter-Blickrichtung."""
        x, y, w = pose
        winkel = -math.pi + np.arange(n) * 2 * math.pi / n
        richt = np.stack([np.cos(winkel + w), np.sin(winkel + w)], axis=1)
        abstand = np.full(n, 8.0)
        segmente = []
        for x0, y0, x1, y1 in self.haeuser:
            segmente += [(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)]
        x0, y0, x1, y1 = (-3.0, -2.5, 7.5, 5.0) if self.halle else (0, 0, BREITE, HOEHE)
        segmente += [(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)]
        s = np.array(segmente)
        p = np.array([x, y])
        e = s[:, 2:] - s[:, :2]                     # (M, 2)
        q = s[:, :2] - p                            # (M, 2)
        nenner = richt[:, None, 0] * e[None, :, 1] - richt[:, None, 1] * e[None, :, 0]
        with np.errstate(divide='ignore', invalid='ignore'):
            t = (q[None, :, 0] * e[None, :, 1] - q[None, :, 1] * e[None, :, 0]) / nenner
            u = (q[None, :, 0] * richt[:, None, 1] - q[None, :, 1] * richt[:, None, 0]) / nenner
        gueltig = (t > 0) & (u >= 0) & (u <= 1)
        t = np.where(gueltig, t, np.inf)
        abstand = np.minimum(abstand, t.min(axis=1))
        for z in self.zylinder:
            if z['h'] < LIDAR_HOEHE:
                continue  # zu niedrig fuer die LiDAR-Ebene
            ox, oy = x - z['x'], y - z['y']
            bq = 2 * (ox * richt[:, 0] + oy * richt[:, 1])
            cq = ox ** 2 + oy ** 2 - z['r'] ** 2
            disk = bq ** 2 - 4 * cq
            tz = np.where(disk >= 0, (-bq - np.sqrt(np.maximum(disk, 0))) / 2, np.inf)
            tz[tz <= 0] = np.inf
            abstand = np.minimum(abstand, tz)
        rng = rng or np.random.default_rng()
        return (abstand + rng.normal(0, rauschen, n)).astype(np.float32), winkel
