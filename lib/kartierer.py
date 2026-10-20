#!/usr/bin/env python3
# Kartierer: verbindet die Sensoren mit Karte und Lokalisierung (lib/karte.py). Ohne ROS, damit man ihn testen
# und eine aufgenommene Messfahrt am Laptop genau so noch einmal durchrechnen kann (kartograf/abspielen.py).
# Der Kartograf (kartograf/kartograf.py) macht aus jeder ROS-Nachricht ein dict und gibt es hierher.
#
# Was er zusaetzlich zur Karte macht (Selbstpruefung, weil am echten Roboter vieles ungeprueft ist):
#   Zeitstempel     Nachrichten kommen manchmal gesammelt an (Rechner ausgelastet). Darum rechnet er mit den
#                   Zeitstempeln der Nachrichten (wenn sie plausibel sind), nicht mit der Ankunftszeit.
#   Lagesensor      Nullpunkt im Stand lernen. Dreht er andersherum (falsch eingebaut) oder misst er zu viel/wenig
#                   Drehung? -> Vergleich mit der Drehung, die der LiDAR sieht (Scan mit Scan vergleichen).
#   LiDAR           Zaehlt er die Winkel andersherum (gespiegelt)? Wo sitzt er GENAU und wohin schaut "vorne"?
#                   -> aus vielen sicheren Abgleichen: wie bewegt sich der LiDAR, wenn die Raeder sagen
#                   "geradeaus" bzw. "auf der Stelle drehen"? (siehe Kalibrierung)
#   Scan entzerren  Der LiDAR misst nicht alles gleichzeitig (eine Umdrehung dauert bei 6 Hz 0,17 s).
#                   Faehrt der Roboter dabei eine Kurve, wird jeder Strahl auf seine Messzeit zurueckgerechnet.
#   Kamera          Bodenfoto nur mit der Position ZUR AUFNAHMEZEIT und nur, wenn der Abgleich gerade sicher ist.
import math
import time

import numpy as np

import karte as K

STANDARD = {
    'scan_topics': ['/scan0', '/scan1'],
    'scan_front_deg': [0.0, 0.0],     # Richtung "vorne" je LiDAR (Grad)
    'scan_spiegeln': [False, False],  # LiDAR zaehlt die Winkel im Uhrzeigersinn (wird auch selbst erkannt)
    'obstacle_min_range': 0.08,
    'lidar_x': 0.0,                   # LiDAR so weit vor der Robotermitte (m)
    'karte_min_abstand': 0.15,        # naeher (m) nicht in die Karte (eigene Teile, Beruehrung)
    'scan_dauer': 0.0,                # Dauer einer LiDAR-Umdrehung (s), falls der LiDAR sie nicht meldet. 0 = nicht entzerren
    'selbst_kalibrieren': True,       # gelernte Korrekturen (Lagesensor, LiDAR-Einbau) auch anwenden
}


def zeit_aus_stamp(stamp):
    """ROS-Zeitstempel (sec, nanosec) oder Zahl -> Sekunden (0 = fehlt)."""
    if stamp is None:
        return 0.0
    if isinstance(stamp, (int, float)):
        return float(stamp)
    return stamp.sec + stamp.nanosec * 1e-9


class Uhr:
    """Rechnet die Zeitstempel EINES Topics in die eigene Uhr um.
    Laufen die Uhren gleich (Abstand Stempel -> Ankunft zwischen 0 und 1 s): Zeitstempel direkt.
    Andere Uhr (z. B. Board ohne Zeitabgleich): nur die Abstaende zwischen den Stempeln zaehlen.
    Kein oder unsinniger Stempel: Ankunftszeit (dann hilft das Ganze nicht, ist aber auch nicht schlechter)."""

    def __init__(self):
        self.versatz = []        # Ankunft - Stempel der letzten Nachrichten
        self.letzter = 0.0
        self.art = 'unbekannt'   # synchron | eigene Uhr | Ankunftszeit
        self.ankunft = []        # Ankunftszeiten (ohne Stempel)
        self.virtuell = None

    def _ohne_stempel(self, empfang):
        """Kein Zeitstempel: Nachrichten kommen evtl. gesammelt an (Rechner ausgelastet). Dann werden sie
        gleichmaessig verteilt (mittlerer Abstand der letzten 50), sonst ginge bei der Drehrate Drehung verloren."""
        self.art = 'Ankunftszeit'
        self.ankunft = (self.ankunft + [empfang])[-50:]
        if len(self.ankunft) < 10 or self.virtuell is None:
            self.virtuell = empfang
            return empfang
        periode = (self.ankunft[-1] - self.ankunft[0]) / (len(self.ankunft) - 1)
        self.virtuell = min(max(self.virtuell + periode, empfang - 0.5), empfang)
        return self.virtuell

    def zeit(self, stamp, empfang):
        if not stamp or stamp <= 0 or stamp < self.letzter - 1e-6:
            self.letzter = 0.0 if not stamp else stamp
            return self._ohne_stempel(empfang)
        self.letzter = stamp
        self.versatz = (self.versatz + [empfang - stamp])[-100:]
        v = np.array(self.versatz)
        if -0.05 < float(np.median(v)) < 1.0:
            self.art = 'synchron'
            t = stamp
        else:
            self.art = 'eigene Uhr'
            t = stamp + float(v.min())
        if not (empfang - 2.0 < t < empfang + 0.05):
            return self._ohne_stempel(empfang)
        return t


class Kalibrierung:
    """Lernt, wie die Sensoren WIRKLICH messen, aus vielen sicheren Scan-Abgleichen.

    Zwischen zwei sicheren Abgleichen kennt man, wie sich der LiDAR bewegt hat (Karte). Die Raeder und der
    Lagesensor sagen, wie sich der Roboter bewegt hat. Beides muss zusammenpassen:
      Drehung:   LiDAR-Drehung = Skala * (Lagesensor - Nullpunkt)            -> Skala und Nullpunkt
      Strecke:   Faehrt der Roboter geradeaus, faehrt der LiDAR in SEINE Richtung "vorne" -> wohin er schaut
                 Dreht sich der Roboter, beschreibt der LiDAR einen Kreis um die Robotermitte -> wo er sitzt
    ("Hand-Auge-Kalibrierung", eine lineare Ausgleichsrechnung)."""
    PROBEN = 300

    def __init__(self, gespeichert=None):
        g = gespeichert or {}
        self.imu_vorzeichen = float(g.get('imu_vorzeichen', 1.0))
        self.imu_skala = float(g.get('imu_skala', 1.0))
        self.gyro_bias = float(g.get('gyro_bias', 0.0))
        self.bias_aus_stand = False
        self.odom_skala = float(g.get('odom_skala', 1.0))
        # Haupt-LiDAR gegenueber der Robotermitte. Noch nicht gelernt = gespeichert als None (nicht fehlend!)
        self.einbau = tuple(g.get('einbau') or (0.0, 0.0, 0.0))
        self.einbau_gelernt = bool(g.get('einbau'))
        self.spiegeln = bool(g.get('spiegeln', False))
        self.dreh_proben = []      # (lidar_drehung, imu_roh_integral, dauer)
        self.weg_proben = []       # (to_x, to_y, lidar_drehung, tm_x, tm_y)
        self.ergebnis = {}         # letzte Schaetzung (auch wenn noch nicht angewendet) fuer die Diagnose
        self.meldungen = []        # (zeit, text) was gelernt/geaendert wurde

    def speichern(self):
        return {'imu_vorzeichen': self.imu_vorzeichen, 'imu_skala': round(self.imu_skala, 4),
                'gyro_bias': round(self.gyro_bias, 5), 'odom_skala': round(self.odom_skala, 4),
                'einbau': [round(v, 4) for v in self.einbau] if self.einbau_gelernt else None,
                'spiegeln': self.spiegeln}

    def drehrate(self, gz):
        return self.imu_vorzeichen * self.imu_skala * (gz - self.gyro_bias)

    def melden(self, text, jetzt=None):
        self.meldungen = (self.meldungen + [(jetzt or time.time(), text)])[-20:]

    # ---- Proben sammeln ----
    def probe(self, lidar_schritt, odom_schritt, imu_roh, dauer):
        """lidar_schritt: Bewegung des LiDARs zwischen zwei sicheren Abgleichen (dx, dy, dw) im LiDAR-System,
        odom_schritt: Bewegung des Roboters laut Raedern (dx, dy, dw), imu_roh: Integral der rohen Drehrate."""
        self.dreh_proben = (self.dreh_proben + [(lidar_schritt[2], imu_roh, dauer)])[-self.PROBEN:]
        weg = math.hypot(odom_schritt[0], odom_schritt[1])
        if weg > 0.03 or abs(lidar_schritt[2]) > math.radians(10):
            self.weg_proben = (self.weg_proben + [(odom_schritt[0], odom_schritt[1], lidar_schritt[2],
                                                   lidar_schritt[0], lidar_schritt[1])])[-self.PROBEN:]

    # ---- Ausrechnen ----
    def drehung_schaetzen(self):
        """Skala (inkl. Vorzeichen) und Nullpunkt des Lagesensors aus den Proben. None = zu wenig/unklar."""
        if len(self.dreh_proben) < 20:
            return None
        p = np.array(self.dreh_proben)
        ziel, roh, dt = p[:, 0], p[:, 1], p[:, 2]
        if np.abs(ziel).sum() < math.radians(90):
            return None          # zu wenig gedreht
        if self.bias_aus_stand:  # Nullpunkt aus dem Stand ist genauer -> nur die Skala
            x = (roh - self.gyro_bias * dt)[:, None]
        else:
            x = np.column_stack([roh, -dt])
        gut = np.ones(len(p), bool)
        for _ in range(3):        # Ausreisser (falsche Abgleiche) weglassen
            loesung, *_ = np.linalg.lstsq(x[gut], ziel[gut], rcond=None)
            rest = ziel - x @ loesung
            grenze = max(3 * np.median(np.abs(rest[gut])) * 1.48, math.radians(0.5))
            gut = np.abs(rest) < grenze
            if gut.sum() < 15:
                return None
        k = float(loesung[0])
        bias = self.gyro_bias if self.bias_aus_stand else float(loesung[1]) / k if abs(k) > 1e-6 else 0.0
        fehler_k = float(np.std(rest[gut]) / max(1e-9, math.sqrt((x[gut, 0] ** 2).sum())))   # Unsicherheit der Skala
        return {'skala': k, 'bias': bias, 'fehler': fehler_k, 'n': int(gut.sum())}

    def einbau_schaetzen(self, gewicht_ort=0.3):
        """Wohin schaut der Haupt-LiDAR und wo sitzt er? Ausgleichsrechnung ueber alle Weg-Proben.
        Unbekannte: a = s*cos(ew), b = s*sin(ew), tx, ty (s = Raeder messen s-mal die wahre Strecke).
        Gleichung je Probe: R(ew) * t_lidar * s = s * (R(dw) - 1) * t_einbau + t_raeder"""
        if len(self.weg_proben) < 25:
            return None
        p = np.array(self.weg_proben)
        tox, toy, dw, tmx, tmy = p.T
        c, s = np.cos(dw), np.sin(dw)
        zeilen_x = np.column_stack([tmx, -tmy, -(c - 1), s])
        zeilen_y = np.column_stack([tmy, tmx, -s, -(c - 1)])
        a = np.vstack([zeilen_x, zeilen_y])
        b = np.concatenate([tox, toy])
        # Ort nur, wenn genug gedreht wurde: sonst sanft Richtung "Mitte" ziehen (Ridge)
        reg = np.diag([0.0, 0.0, gewicht_ort, gewicht_ort])
        gut = np.ones(len(b), bool)
        for _ in range(3):
            ata = a[gut].T @ a[gut] + reg
            loesung = np.linalg.solve(ata, a[gut].T @ b[gut])
            rest = b - a @ loesung
            grenze = max(3 * np.median(np.abs(rest[gut])) * 1.48, 0.004)
            gut = np.abs(rest) < grenze
            if gut.sum() < 30:
                return None
        sigma2 = float((rest[gut] ** 2).mean())
        kov = np.linalg.inv(a[gut].T @ a[gut] + reg) * sigma2
        la, lb, tx, ty = loesung
        skala = math.hypot(la, lb)
        if skala < 0.3:
            return None
        ew = math.atan2(lb, la)
        f_w = math.sqrt(max(0.0, (kov[0, 0] * lb ** 2 + kov[1, 1] * la ** 2) / skala ** 4))
        f_ort = math.sqrt(max(kov[2, 2], kov[3, 3])) / skala
        # Ort nur glauben, wenn genug Drehung in den Proben steckt
        drehung = float(np.abs(dw).sum())
        return {'w': ew, 'x': tx / skala, 'y': ty / skala, 'odom_skala': skala, 'fehler_w': f_w,
                'fehler_ort': f_ort, 'n': int(gut.sum() // 2), 'drehung': drehung}

    def lernen(self, jetzt, anwenden=True):
        """Neu schaetzen und (wenn sicher genug) uebernehmen. Rueckgabe: Text, falls sich etwas geaendert hat."""
        text = []
        d = self.drehung_schaetzen()
        if d:
            self.ergebnis['drehung'] = d
            k = d['skala']
            if anwenden and d['fehler'] < 0.01 and 0.7 < abs(k) < 1.4:
                # die Proben sind ROH (ohne Korrektur) -> das Ergebnis gilt direkt
                if np.sign(k) != self.imu_vorzeichen:
                    self.imu_vorzeichen = float(np.sign(k))
                    text.append('Lagesensor misst andersherum - korrigiert')
                if abs(abs(k) - self.imu_skala) > 0.01:
                    text.append(f'Lagesensor misst {1 / abs(k):.0%} der Drehung')
                self.imu_skala = abs(k)
                if not self.bias_aus_stand:
                    self.gyro_bias = d['bias']
        e = self.einbau_schaetzen()
        if e:
            self.ergebnis['einbau'] = e
            if anwenden and e['fehler_w'] < math.radians(1.5) and 0.7 < e['odom_skala'] < 1.4:
                ort_ok = e['fehler_ort'] < 0.015 and e['drehung'] > math.radians(360) and math.hypot(e['x'], e['y']) < 0.35
                neu = (e['x'] if ort_ok else self.einbau[0] * self.einbau_gelernt,
                       e['y'] if ort_ok else self.einbau[1] * self.einbau_gelernt, e['w'])
                alt = self.einbau
                if (abs(K.winkel(neu[2] - alt[2])) > math.radians(1.0) or math.hypot(neu[0] - alt[0], neu[1] - alt[1]) > 0.01
                        or not self.einbau_gelernt):
                    self.einbau, self.einbau_gelernt = neu, True
                    text.append(f'LiDAR-Einbau {neu[0] * 100:+.0f} / {neu[1] * 100:+.0f} cm, "vorne" {math.degrees(neu[2]):+.0f} Grad'
                                + ('' if ort_ok else ' (Ort noch unsicher)'))
                if abs(e['odom_skala'] - self.odom_skala) > 0.03:
                    text.append(f'Raeder messen {e["odom_skala"]:.0%} der Strecke')
                self.odom_skala = e['odom_skala']
        if text:
            self.melden('; '.join(text), jetzt)
            return '; '.join(text)
        return None

    def warnungen(self):
        """Hinweise fuers Panel: was sollte man an den Einstellungen aendern?"""
        w = []
        if self.spiegeln:
            w.append('LiDAR zaehlt die Winkel andersherum (gespiegelt) - korrigiert. Dauerhaft: scan_spiegeln: [true, true]')
        if self.imu_vorzeichen < 0:
            w.append('Lagesensor misst die Drehung falsch herum - wird korrigiert')
        if abs(self.imu_skala - 1.0) > 0.1:
            w.append(f'Lagesensor misst {self.imu_skala:.0%} der Drehung (Einheit? Kalibrierung?) - wird korrigiert')
        if self.einbau_gelernt and abs(K.winkel(self.einbau[2])) > math.radians(10):
            w.append(f'LiDAR-Richtung vermutlich um {math.degrees(self.einbau[2]):+.0f} Grad falsch: '
                     f'scan_front_deg anpassen (Panel -> LiDAR). Die Karte rechnet es heraus, die Hinderniserkennung nicht!')
        return w

    def text(self):
        t = (f'Lagesensor x{self.imu_vorzeichen * self.imu_skala:.3f}, Nullpunkt {math.degrees(self.gyro_bias):+.2f} Grad/s'
             f'; Raeder {self.odom_skala:.0%}')
        if self.einbau_gelernt:
            t += (f'; LiDAR {self.einbau[0] * 100:+.0f} / {self.einbau[1] * 100:+.0f} cm, '
                  f'vorne {math.degrees(self.einbau[2]):+.1f} Grad')
        return t


class Drehpruefung:
    """Grobe Selbstpruefung: dreht der LiDAR-Scan genauso wie Lagesensor und Raeder?
    Zwei Scans, zwischen denen sich der Roboter etwas gedreht hat, werden aufeinander geschoben (weite Suche,
    unabhaengig von der Karte). Dreht der Scan andersherum oder viel mehr/weniger -> etwas ist falsch eingestellt."""

    def __init__(self):
        self.ref = None         # (zeit, punkte, imu_winkel, odom_winkel)
        self.proben = []        # (scan_drehung, imu_drehung, odom_drehung)

    def scan(self, zeit, punkte, imu_w, odom_w):
        """Rueckgabe: (scan, imu, odom) Drehung in rad, wenn eine Probe entstanden ist, sonst None."""
        if self.ref is None or zeit - self.ref[0] > 3.0:
            self.ref = (zeit, punkte, imu_w, odom_w)
            return None
        d_imu, d_odom = imu_w - self.ref[2], odom_w - self.ref[3]
        gross = max(abs(d_imu), abs(d_odom))
        if gross < math.radians(15) and zeit - self.ref[0] < 1.5:
            return None
        ref = self.ref
        self.ref = (zeit, punkte, imu_w, odom_w)
        if gross < math.radians(8) or gross > math.radians(60):
            return None
        d_scan = scan_zu_scan(ref[1], punkte)
        if d_scan is None:
            return None
        self.proben = (self.proben + [(d_scan[2], d_imu, d_odom)])[-30:]
        return d_scan[2], d_imu, d_odom

    def urteil(self):
        """(verhaeltnis_imu, verhaeltnis_odom) Scan-Drehung / Sensor-Drehung (Median) oder None."""
        if len(self.proben) < 6:
            return None
        p = np.array(self.proben)
        imu = p[np.abs(p[:, 1]) > math.radians(8)]
        odo = p[np.abs(p[:, 2]) > math.radians(8)]
        r_imu = float(np.median(imu[:, 0] / imu[:, 1])) if len(imu) >= 5 else None
        r_odo = float(np.median(odo[:, 0] / odo[:, 2])) if len(odo) >= 5 else None
        return r_imu, r_odo


def scan_zu_scan(alt, neu, w_grad=70.0, xy=0.2):
    """Wie hat sich der LiDAR zwischen zwei Scans bewegt (neu im System von alt)? Rueckgabe (dx, dy, dw) oder None."""
    alt = np.asarray(alt)[np.hypot(*np.asarray(alt).T) < 6.0]
    neu = np.asarray(neu)[np.hypot(*np.asarray(neu).T) < 6.0]
    if len(alt) < 30 or len(neu) < 30:
        return None
    b = K.Belegung(groesse=13.0, cfg={'max_reichweite': 6.0})
    ij, ok = b.zellen(alt)
    b.lo[ij[ok, 1], ij[ok, 0]] = K.LO_MAX
    pose, guete = b.abgleichen((0.0, 0.0, 0.0), neu, xy, w_grad, min_guete=0.45)
    return pose


class Kartierer:
    """Sensoren -> Karte + Position. Alle Zeiten in Sekunden (Ankunftszeit der Nachricht = 'empfang')."""

    def __init__(self, karte, cfg=None):
        self.karte = karte
        self.c = dict(STANDARD)
        self.c.update({k: v for k, v in (cfg or {}).items() if v is not None})
        self.namen = list(self.c['scan_topics'])
        # Gespeicherte Selbstkalibrierung nur, wenn sie auch angewendet werden soll. Sonst Rohwerte wie eingestellt
        # (eine einmal falsch gelernte Korrektur verdreht sonst jede weitere Karte)
        self.kal = Kalibrierung(karte.kalibrierung if self.c['selbst_kalibrieren'] else None)
        self.lok = K.Lokalisierung(karte)
        self.uhren = {}
        self.scans = {}               # name -> Liste der letzten Scans (zeit, punkte, empfang)
        self.dreh = 0.0               # aktuelle Drehrate (rad/s)
        self.v = 0.0
        # Mitrechnen
        self.odom_t = self.odom_empfang = None
        self.odom_alt = None          # letzte Odometrie-Nachricht (fuer Positions-Unterschiede)
        self.twist_gesehen = self.pose_gesehen = 0.0   # wann zuletzt Geschwindigkeit / Positionsaenderung
        self.imu_t = self.imu_empfang = None
        self.imu_offen = 0.0          # Drehung (korrigiert) seit der letzten Odometrie
        self.imu_roh = 0.0            # Integral der rohen Drehrate (fuer die Kalibrierung)
        self.imu_winkel = 0.0         # Integral der korrigierten Drehrate
        self.odom_winkel = 0.0        # Drehung laut Raedern
        self.imu_az = []
        self.stand_drehraten = []
        self.steht = False
        self.bewegung_puffer = []     # (zeit, art, daten, empfang) Odometrie + Lagesensor, nach Messzeit sortiert
        self.zuletzt = {}             # art -> (zeit, empfang) der letzten Nachricht
        self.roboter = (0.0, 0.0, 0.0)   # mitgerechnete Roboterposition (Raeder + Lagesensor, eigenes System)
        self.verlauf = []             # (zeit, roboter, imu_roh, imu_winkel, odom_winkel) fuer Kalibrierung
        self.letzter_sicherer = None
        self.proben_neu = 0
        self.drehpruefung = Drehpruefung()
        self.diagnose = []            # je Scan: zeit, guete, sicher, fenster, punkte
        self.meldung = None           # letzter wichtiger Hinweis (Text)
        self.neu_seit = None          # Zeit, zu der wegen eines groben Fehlers neu angefangen wurde
        self.zaehler = {}

    def _zeit(self, topic, stamp, empfang):
        return self.uhren.setdefault(topic, Uhr()).zeit(stamp, empfang)

    def _zaehlen(self, n):
        self.zaehler[n] = self.zaehler.get(n, 0) + 1

    # ---------------- Bewegung ----------------
    def imu(self, empfang, d):
        """d: stamp, g (Drehrate x, y, z rad/s), a (Beschleunigung, optional)."""
        self._zaehlen('imu')
        self._einsortieren(self._zeit('imu', d.get('stamp'), empfang), 'imu', d, empfang)

    def odom(self, empfang, d):
        """d: stamp, vx, vy, wz (Geschwindigkeiten), x, y, w (Position, optional)."""
        self._zaehlen('odom')
        self._einsortieren(self._zeit('odom', d.get('stamp'), empfang), 'odom', d, empfang)

    def _einsortieren(self, t, art, d, empfang):
        """Odometrie und Lagesensor in der Reihenfolge ihrer Messzeit verarbeiten, nicht in der Ankunfts-
        Reihenfolge (kommen sie gesammelt an, waere die Drehung sonst zur falschen Zeit verbucht).
        Eine Nachricht wartet, bis vom anderen Sensor etwas Spaeteres da ist (hoechstens 0,5 s)."""
        self.zuletzt[art] = (t, empfang)
        self.bewegung_puffer.append((t, art, d, empfang))
        self.bewegung_puffer.sort(key=lambda x: x[0])
        while self.bewegung_puffer:
            t0, art0, d0, e0 = self.bewegung_puffer[0]
            andere = self.zuletzt.get('odom' if art0 == 'imu' else 'imu')
            tot = andere is None or empfang - andere[1] > 1.0
            if not (tot or andere[0] >= t0 or empfang - e0 > 0.5):
                break
            self.bewegung_puffer.pop(0)
            (self._imu_schritt if art0 == 'imu' else self._odom_schritt)(t0, e0, d0)

    def _imu_schritt(self, t, empfang, d):
        gz = float(d['g'][2])
        if d.get('a'):
            self.imu_az = (self.imu_az + [float(d['a'][2])])[-50:]
        if self.imu_t is not None:
            dt = t - self.imu_t
            if 0 < dt < 0.25:
                if self.steht and abs(gz - self.kal.gyro_bias) < 0.05:
                    # Stand: der Sensor misst trotzdem etwas (Nullpunktfehler) -> lernen, Drehung = 0
                    self.stand_drehraten = (self.stand_drehraten + [gz])[-300:]
                    if len(self.stand_drehraten) >= 50:
                        self.kal.gyro_bias, self.kal.bias_aus_stand = float(np.median(self.stand_drehraten)), True
                    w = 0.0
                else:
                    w = self.kal.drehrate(gz)
                self.imu_roh += gz * dt
                self.imu_offen += w * dt
                self.imu_winkel += w * dt
                self.dreh = w
        self.imu_t, self.imu_empfang = t, empfang
        if self.odom_empfang is None or empfang - self.odom_empfang > 0.5:
            # keine Odometrie: wenigstens die Drehung mitrechnen (Strecke macht der Scan-Abgleich)
            self._schritt(0.0, 0.0, self.imu_offen, t)
            self.imu_offen = 0.0

    def _odom_schritt(self, t, empfang, d):
        vx, vy, wz = float(d.get('vx', 0.0)), float(d.get('vy', 0.0)), float(d.get('wz', 0.0))
        pose = (float(d['x']), float(d['y']), float(d['w'])) if d.get('x') is not None else None
        if abs(vx) > 1e-4 or abs(vy) > 1e-4 or abs(wz) > 1e-4:
            self.twist_gesehen = empfang
        alt, self.odom_alt = self.odom_alt, (t, pose)
        if self.odom_t is None:
            self.odom_t, self.odom_empfang = t, empfang
            return
        dt = t - self.odom_t
        if dt <= 0:
            return
        self.odom_t, self.odom_empfang = t, empfang
        dt = min(dt, 0.5)
        delta = K.relativ(alt[1], pose) if pose is not None and alt and alt[1] is not None else None
        if delta is not None and (abs(delta[0]) > 1e-5 or abs(delta[1]) > 1e-5 or abs(delta[2]) > 1e-5):
            self.pose_gesehen = empfang
        stempel_ok = self.uhren['odom'].art != 'Ankunftszeit'
        if delta is not None and (empfang - self.twist_gesehen > 1.0 or not stempel_ok) and empfang - self.pose_gesehen < 1.0:
            # keine Geschwindigkeiten (oder keine Zeitstempel): Positions-Unterschied nehmen, geht nichts verloren
            dx, dy, dw_odom = delta
            if dt > 0:
                vx, vy, wz = dx / dt, dy / dt, dw_odom / dt
        else:
            dx, dy, dw_odom = vx * dt, vy * dt, wz * dt
        self.v = math.hypot(vx, vy)
        self.steht = self.v < 0.01 and abs(wz) < 0.005     # langsamer als 1 cm/s und dreht nicht
        self.odom_winkel += dw_odom
        if self.imu_empfang is not None and empfang - self.imu_empfang < 0.3:
            dw = self.imu_offen       # Drehung lieber vom Lagesensor (Mecanum-Raeder rutschen beim Drehen)
            self.imu_offen = 0.0
        else:
            dw = 0.0 if self.steht else dw_odom
            self.dreh = wz
        s = 1.0 / self.kal.odom_skala if self.c['selbst_kalibrieren'] else 1.0
        self._schritt(dx * s, dy * s, dw, t)

    def _schritt(self, dx, dy, dw, t):
        """Roboter hat sich so bewegt (Roboter-System) -> LiDAR-System umrechnen und mitrechnen."""
        self.roboter = K.verknuepfen(self.roboter, (dx, dy, dw))
        self.verlauf.append((t, self.roboter, self.imu_roh, self.imu_winkel, self.odom_winkel))
        if len(self.verlauf) > 600:
            self.verlauf = self.verlauf[-400:]
        e = self.kal.einbau if self.c['selbst_kalibrieren'] else (0.0, 0.0, 0.0)
        if e != (0.0, 0.0, 0.0):
            # sitzt der LiDAR nicht in der Mitte / schaut nicht nach vorne: seine Bewegung ist eine andere
            schritt = K.verknuepfen(K.relativ(e, (0.0, 0.0, 0.0)), K.verknuepfen((dx, dy, dw), e))
        else:
            schritt = (dx, dy, dw)
        self.lok.bewegen(*schritt, t)

    def _verlauf_bei(self, zeit):
        """(roboter, imu_roh, imu_winkel, odom_winkel) zur Zeit 'zeit' (zwischen zwei Eintraegen gemittelt) oder None."""
        if not self.verlauf or zeit < self.verlauf[0][0]:
            return None
        nach = None
        for v in reversed(self.verlauf):
            if v[0] <= zeit:
                if nach is None or nach[0] - v[0] < 1e-6:
                    return v[1:]
                a = (zeit - v[0]) / (nach[0] - v[0])
                r = K.relativ(v[1], nach[1])
                return (K.verknuepfen(v[1], (r[0] * a, r[1] * a, r[2] * a)),) + tuple(
                    x + (y - x) * a for x, y in zip(v[2:], nach[2:]))
            nach = v
        return None

    # ---------------- LiDAR ----------------
    def scan(self, empfang, name, d):
        """d: stamp, amin, ainc, rmin, rmax, ti (time_increment), st (scan_time), r (Abstaende, inf/0 = keine)."""
        self._zaehlen(name)
        if name not in self.namen:
            return
        i = self.namen.index(name)
        r = np.asarray(d['r'], dtype=np.float64)
        n = len(r)
        if n < 10:
            return
        t = self._zeit(name, d.get('stamp'), empfang)
        a = d['amin'] + np.arange(n) * d['ainc']
        spiegeln = self.c['scan_spiegeln'][i] if i < len(self.c['scan_spiegeln']) else False
        if spiegeln != self.kal.spiegeln:     # Einstellung und Selbstkorrektur heben sich auf, wenn beide da sind
            a = -a
        fronts = self.c['scan_front_deg']
        a = a - math.radians(fronts[i] if i < len(fronts) else 0.0)
        min_r = max(d.get('rmin', 0.0), self.c['obstacle_min_range'], self.c['karte_min_abstand'])
        with np.errstate(invalid='ignore'):
            ok = np.isfinite(r) & (r > min_r) & (r < d.get('rmax', 100.0))
        xy = np.column_stack([r[ok] * np.cos(a[ok]), r[ok] * np.sin(a[ok])])
        xy[:, 0] += self.c['lidar_x']
        # Umlauf: wie lange dauert eine Umdrehung, wann wurde welcher Strahl gemessen?
        dauer = d.get('ti', 0.0) * n if d.get('ti', 0.0) > 0 else (d.get('st', 0.0) or self.c['scan_dauer'])
        ende = t
        if dauer > 0 and self.uhren[name].art == 'synchron' and t + dauer <= empfang + 0.02:
            ende = t + dauer               # Zeitstempel = erster Strahl (so ist es in ROS ueblich)
        if 0 < dauer < 0.5 and abs(self.dreh) > 0.05:
            xy = self._entzerren(xy, np.nonzero(ok)[0], n, ende, dauer)
        self.scans[name] = (self.scans.get(name, []) + [(ende, xy, empfang)])[-4:]

    def _entzerren(self, xy, idx, n, ende, dauer):
        """Jeden Strahl auf die Position am Ende des Umlaufs umrechnen (12 Stuecke, das reicht)."""
        ziel = self.lok.odom_bei(ende)
        aus = xy.copy()
        for k in range(12):
            m = (idx >= k * n // 12) & (idx < (k + 1) * n // 12)
            if not m.any():
                continue
            t_k = ende - dauer * (1 - (k + 0.5) / 12)
            aus[m] = K.in_karte(K.relativ(ziel, self.lok.odom_bei(t_k)), xy[m])
        return aus

    def verarbeiten(self, jetzt):
        """Neuesten Scan abgleichen und eintragen (5x pro Sekunde aufrufen).
        Rueckgabe: True, wenn die globale Suche (Position in vorhandener Karte) gestartet werden sollte."""
        haupt = self.namen[0]
        liste = [s for s in self.scans.get(haupt, []) if jetzt - s[2] < 1.0]
        if not liste:
            return False
        # Odometrie/Lagesensor kommen evtl. gesammelt an: nur Scans nehmen, bis zu deren Messzeit die Bewegung
        # schon da ist. Sonst wird mit einer alten Position abgeglichen und die Bewegung danach doppelt gezaehlt.
        v = self.lok.verlauf
        bereit = [s for s in liste if not v or s[0] <= v[-1][0] + 0.02 or not self._bewegung_lebt(jetzt)]
        if not bereit:
            if jetzt - liste[0][2] < 0.6:
                return False         # kurz warten
            bereit = liste           # wartet zu lange: trotzdem
        zeit, punkte, _ = bereit[-1]
        self.scans[haupt] = [s for s in liste if s[0] > zeit]      # jeden Scan nur einmal verwenden
        weitere = {}
        for name in self.namen[1:]:
            andere = [s for s in self.scans.get(name, []) if jetzt - s[2] < 1.0 and s[0] <= zeit + 0.1]
            if andere:
                z, p, _ = min(andere, key=lambda s: abs(s[0] - zeit))
                weitere[name] = (z, p)
                self.scans[name] = [s for s in self.scans[name] if s[0] > z]
        if abs(self.dreh) > 1.5:
            return False             # dreht sehr schnell: nur mitrechnen
        lok = self.lok
        self._selbstpruefung(zeit, punkte)
        if self.lok is not lok:
            return False             # gerade neu angefangen: dieser Scan ist noch falsch umgerechnet
        self.lok.scan(punkte, jetzt, eintragen=abs(self.dreh) < 0.6, scan_zeit=zeit, weitere=weitere)
        a = self.lok.letzter_abgleich
        if a:
            self.diagnose.append((round(zeit, 3), round(a['guete'], 3), int(a['sicher']), a['fenster'], a['punkte']))
            if len(self.diagnose) > 50000:
                self.diagnose = self.diagnose[-40000:]
            self._kalibrierprobe(a, jetzt)
        return self.lok.pose is None and len(self.lok.puffer) >= 3

    def _bewegung_lebt(self, jetzt):
        """Kommen ueberhaupt Odometrie oder Lagesensor an?"""
        return any(e is not None and jetzt - e < 1.0 for e in (self.odom_empfang, self.imu_empfang))

    def _selbstpruefung(self, zeit, punkte):
        v = self._verlauf_bei(zeit)
        if v is None:
            return
        probe = self.drehpruefung.scan(zeit, punkte, v[2], v[3])
        if probe is None:
            return
        u = self.drehpruefung.urteil()
        if u is None:
            return
        r_imu, r_odo = u
        if not self.c['selbst_kalibrieren']:
            # nur melden, nichts umstellen (Einstellungen pruefen: scan_spiegeln, IMU)
            if r_imu is not None and not 0.7 <= r_imu <= 1.4:
                text = f'Selbstpruefung: Scan dreht {r_imu:+.2f}x so viel wie der Lagesensor (Einstellungen pruefen)'
                if not self.kal.meldungen or self.kal.meldungen[-1][1] != text:
                    self.kal.melden(text, zeit)
                    self.meldung = text
            return
        az = float(np.median(self.imu_az)) if self.imu_az else 9.8
        if r_imu is not None and r_imu < -0.5:
            if (r_odo is not None and r_odo < -0.5) or (r_odo is None and az > 0):
                # Raeder UND Lagesensor drehen andersherum als der Scan -> der LiDAR ist gespiegelt
                self.kal.spiegeln = not self.kal.spiegeln
                self._neu_anfangen('LiDAR zaehlt die Winkel andersherum (gespiegelt) - korrigiert', zeit)
            else:
                self.kal.imu_vorzeichen *= -1
                self.kal.dreh_proben = []
                self._neu_anfangen('Lagesensor misst die Drehung falsch herum - korrigiert', zeit)
        elif r_imu is not None and (r_imu > 1.4 or r_imu < 0.7):
            self.kal.imu_skala *= r_imu
            self.kal.dreh_proben = []
            self.drehpruefung = Drehpruefung()
            self.kal.melden(f'Lagesensor misst {1 / r_imu:.0%} der Drehung - korrigiert', zeit)
            self.meldung = self.kal.meldungen[-1][1]

    def _neu_anfangen(self, grund, zeit):
        """Grober Fehler erkannt, die bisherige Karte dieser Fahrt ist unbrauchbar -> neu anfangen."""
        self.kal.melden(grund, zeit)
        self.meldung = grund
        self.neu_seit = zeit
        if self.karte.fahrten <= 1:
            self.karte.belegung.leeren()
            self.karte.boden.anzahl[:] = 0
            self.karte.einbau = {}
            self.karte.fahrten = 0
            self.lok = K.Lokalisierung(self.karte)
        else:
            self.lok.pose, self.lok.puffer = None, []     # vorhandene Karte: Position neu suchen
        self.drehpruefung = Drehpruefung()                # alter Vergleichs-Scan passt nicht mehr
        self.letzter_sicherer = None
        self.scans = {}

    def _kalibrierprobe(self, a, jetzt):
        """Zwei sichere Abgleiche nacheinander -> eine Probe fuer die Kalibrierung."""
        if not a['sicher']:
            if self.letzter_sicherer and a['zeit'] - self.letzter_sicherer[0] > 3.0:
                self.letzter_sicherer = None
            return
        v = self._verlauf_bei(a['zeit'])
        if v is None:
            return
        jetzt_probe = (a['zeit'], a['pose'], v[0], v[1])
        alt = self.letzter_sicherer
        if alt is None or a['zeit'] - alt[0] < 0.6:
            if alt is None:
                self.letzter_sicherer = jetzt_probe
            return
        self.letzter_sicherer = jetzt_probe
        if a['zeit'] - alt[0] > 3.0:
            return
        lidar_schritt = K.relativ(alt[1], a['pose'])
        odom_schritt = K.relativ(alt[2], v[0])
        self.kal.probe(lidar_schritt, odom_schritt, v[1] - alt[3], a['zeit'] - alt[0])
        self.proben_neu += 1
        if self.proben_neu >= 10:        # alle 10 Proben neu ausrechnen
            self.proben_neu = 0
            text = self.kal.lernen(jetzt, anwenden=self.c['selbst_kalibrieren'])
            if text:
                self.meldung = text
                self.karte.kalibrierung = self.kal.speichern()

    def global_suchen(self):
        """Position in der vorhandenen Karte suchen (dauert, eigener Thread im Kartografen)."""
        return self.lok.global_suchen()

    # ---------------- Kamera ----------------
    def roboter_pose_bei(self, zeit=None):
        """Wo war die ROBOTERMITTE (nicht der LiDAR) zur Zeit 'zeit' in der Karte? None = unbekannt."""
        p = self.lok.pose if zeit is None else self.lok.pose_bei(zeit)
        if p is None:
            return None
        e = self.kal.einbau if self.c['selbst_kalibrieren'] else (0.0, 0.0, 0.0)
        return K.verknuepfen(p, K.relativ(e, (0.0, 0.0, 0.0)))

    def bild_pose(self, empfang, stamp, max_alter=1.5):
        """Pose zur Aufnahmezeit eines Kamerabilds, oder (None, Grund), wenn man es besser nicht eintraegt."""
        if self.lok.pose is None:
            return None, 'Position unbekannt'
        t = self._zeit('kamera', stamp, empfang)
        if self.lok.zuletzt_sicher is None or empfang - self.lok.zuletzt_sicher > 1.0:
            return None, 'Abgleich gerade unsicher'
        if empfang - t > max_alter or not self.lok.verlauf or t < self.lok.verlauf[0][0]:
            return None, 'Bild zu alt'
        v0, v1 = self._verlauf_bei(t - 0.15), self._verlauf_bei(t + 0.15)
        if v0 and v1 and abs(v1[2] - v0[2]) > 0.8 * 0.3:     # schneller als 0,8 rad/s: Bild verwischt
            return None, 'dreht sich'
        return self.roboter_pose_bei(t), None

    # ---------------- Ausgabe ----------------
    def sicher_anteil(self, sekunden=10.0):
        if not self.diagnose:
            return None
        ende = self.diagnose[-1][0]
        d = [x for x in self.diagnose[-200:] if x[0] > ende - sekunden]
        return sum(x[2] for x in d) / len(d) if d else None

    def warnungen(self):
        w = self.kal.warnungen()
        anteil = self.sicher_anteil(30.0)
        if anteil is not None and len(self.diagnose) > 100 and anteil < 0.5:
            w.append(f'Scan-Abgleich passt oft nicht ({anteil:.0%} sicher in 30 s): wenig Waende/Gegenstaende '
                     'in LiDAR-Hoehe? Bitte Messfahrt aufzeichnen.')
        if self.imu_az and float(np.median(self.imu_az)) < -5:
            w.append('Lagesensor steht auf dem Kopf? (Beschleunigung z negativ)')
        for n, u in self.uhren.items():
            if u.art == 'Ankunftszeit' and self.zaehler.get(n, 0) > 50 and n in ('odom', 'imu'):
                w.append(f'{n}: keine brauchbaren Zeitstempel - bei ausgelastetem Rechner ungenau')
        return w

    def meldung_pose(self, jetzt):
        """Inhalt fuer /karte/pose."""
        aus = {'zeit': jetzt, 'status': self.lok.status, 'guete': round(self.lok.guete, 2),
               'fahrten': self.karte.fahrten, 'lidar_einbau': self.lok.einbau_text(),
               'sicher_anteil': None if self.sicher_anteil() is None else round(self.sicher_anteil(), 2),
               'kalibrierung': self.kal.text(), 'warnungen': self.warnungen(),
               'meldung': self.kal.meldungen[-1][1] if self.kal.meldungen else None}
        p = self.roboter_pose_bei()
        if p is not None:
            aus.update({'x': round(p[0], 3), 'y': round(p[1], 3), 'w': round(p[2], 3)})
        return aus
