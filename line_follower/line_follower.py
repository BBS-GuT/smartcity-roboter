#!/usr/bin/env python3
# Linienfolger: folgt der schwarzen Linie und gehorcht der KI-Zentrale.
#
# Start ueber das Panel (scripts/panel.sh): START = faehrt, TEST = zeigt nur an, faehrt NICHT.
# Das Panel startet Kamera und KI-Zentrale mit.
#
# Wer entscheidet was?
#   KI-Zentrale (ki/zentrale.py): ob gefahren werden darf (Ampel, Schild, Hindernis ...),
#                                 wie schnell (Faktor) und Manoever (wenden, ausrichten zum Greifen)
#   Linienfolger (diese Datei):   wohin gelenkt wird (Linie, line_follower/linie.py),
#                                 fuehrt Manoever aus, eigene LiDAR-Notbremse als zweite Sicherheit
#
# Wie er der Linie folgt (genauer in Kurven als frueher):
#   Kamerabild -> Draufsicht -> Mittellinie in Metern -> Gedaechtnis (rechnet die eigene Bewegung mit,
#   kennt dadurch die Linie auch direkt unter dem Roboter) -> Lenkung mit Kurvenvorsteuerung.
#   Linie weg: dreht sich zur Seite, wo sie zuletzt war, und sucht (such_zeit), dann Stopp.
#
# Sicherheit:
#   - Fahrbefehle gehen 20x pro Sekunde raus. Das Motorboard stoppt selbst, wenn
#     0,3 s lang kein Befehl kommt (Watchdog).
#   - Ohne Antwort der KI (ki_pflicht), ohne Kamerabilder oder ohne Linie: Stopp.
#   - Notbremse ueber LiDAR, unabhaengig von der KI (blockiert vorwaerts und seitwaerts,
#     einschliesslich Drehen und Rueckwaerts).
#
# Einstellungen: -p name:=wert beim Start oder  ros2 param set /line_follower name wert
import json
import os
import signal
import sys
import threading
import time

# Mathe-Bibliotheken (OpenBLAS/OpenMP) nur einen Thread: sonst warten auf dem Jetson Threads auf allen Kernen aktiv
# (RM02 20.10.: Linienfolger 200-500 % CPU, Rechner haengt, KI-Befehle kommen nicht an). Vor numpy/cv2 setzen!
for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_v, '1')

import cv2  # noqa: E402
cv2.setNumThreads(1)   # Bildgroessen hier klein: ein Thread reicht, die anderen Kerne bleiben frei
import rclpy
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data, QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image, CompressedImage, LaserScan, Imu
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
from std_msgs.msg import String, Float32
from cv_bridge import CvBridge

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(REPO, 'lib'))
sys.path.insert(0, os.path.join(REPO, 'line_follower'))
import lidar  # noqa: E402
import linie  # noqa: E402

# Grenzen fuer Manoever der KI (Sicherheit)
MANOEVER_MAX = {'lin': 0.10, 'quer': 0.08, 'dreh': 1.2}


class LineFollower(Node):
    def __init__(self):
        super().__init__('line_follower')
        dp = self.declare_parameter
        # ---- Allgemein ----
        dp('drive', False)          # False = nur anschauen, nicht fahren
        dp('show', True)            # Fenster anzeigen (braucht DISPLAY)
        dp('publish_image', True)   # Bild mit Linie fuers Panel senden
        dp('image_topic', '/camera/color/image_raw')
        dp('rate', 20.0)            # Fahrbefehle pro Sekunde (Board-Watchdog: 0,3 s)
        dp('max_bild_hz', 15.0)     # hoechstens so viele Kamerabilder/s auswerten (spart Rechenzeit)
        dp('ki_pflicht', True)      # ohne Befehl der KI-Zentrale nicht fahren
        dp('speed', 0.15)           # m/s auf gerader Strecke (in Kurven automatisch langsamer)
        dp('direction', 1.0)        # -1.0 = rueckwaerts fahren (Kamera schaut trotzdem nach vorne!)
        # ---- Linie + Lenkung (Erklaerung in line_follower/linie.py) ----
        for name, wert in linie.STANDARD.items():
            dp(name, wert)
        # ---- LiDAR-Notbremse (zweite Sicherheit, unabhaengig von der KI) ----
        dp('obstacle_check', True)
        dp('scan_topics', ['/scan0', '/scan1'])
        dp('scan_front_deg', [0.0, 0.0])
        dp('obstacle_half_deg', 30.0)
        dp('notbremse_dist', 0.12)  # naeher (m) -> sofort Stopp
        # ---- Kamerabilder: wie alt duerfen sie sein? (Aufnahme bis Auswertung) ----
        dp('bild_alter_langsam', 0.25)  # aelter (s) -> langsamer fahren
        dp('bild_alter_max', 0.6)       # aelter (s) -> STOPP (sonst lenkt er nach einem veralteten Bild)
        # ---- eigene Bewegung fuer das Linien-Gedaechtnis ----
        # auto = Radzaehler (/odom_raw) + Lagesensor (/imu/data_raw), wenn plausibel, sonst die eigenen
        # Fahrbefehle; 'befehl' = immer Fahrbefehle
        dp('bewegung', 'auto')
        # Selbst einstellen: waehrend der Fahrt messen, wie spaet und wie stark sich der Roboter auf einen Lenkbefehl
        # dreht (Lagesensor) -> Verzoegerung = 'vorhersage', Drehfaktor = Lenkbefehl entsprechend groesser
        dp('selbst_einstellen', True)
        dp('motor_totzeit', 0.1)    # so viel davon steckt in USB + Motorboard (GESCHAETZT) -> wird abgezogen
        dp('obstacle_min_range', 0.08)

        self.bridge = CvBridge()
        self.lock = threading.Lock()
        cfg = {n: self.p(n) for n in linie.STANDARD}
        self.sucher = linie.LinienSucher(cfg)
        self.lenkung = linie.Lenkung(cfg)
        self.gedaechtnis = linie.Gedaechtnis()
        self.verzoegerung = linie.Verzoegerung(takt=1.0 / self.p('rate'))
        self.linie_gesehen = False
        self.kamera_linie = (None, None)  # Linie nur nach Kamerabild: seitlich (m), Richtung (rad)
        self.bild_zeit = 0.0
        self.bild_zaehler, self.fps, self.fps_zeit = 0, 0.0, time.time()
        self.scans = {}
        self.ki = (0.0, None)            # (zeit, befehl)
        self.last_image_pub = 0.0
        self.status_text = 'startet ...'
        self.letzter_cmd = (0.0, 0.0, 0.0)  # vorwaerts, seitwaerts, drehen
        self.letzte_steuerung = time.time()
        self.anzeige = None              # (Bild, Maske) fuer die Fenster (zeigt der Haupt-Thread)
        self.bild_alter = 0.0            # Aufnahme bis Auswertung des letzten Bildes (s)
        self.linie_breite = None         # wie breit die Linie in der Draufsicht aussieht (m)
        self.kamera_weg_bis = 0.0        # zuletzt schaute die Kamera (Arm) woanders hin (Zeit)
        self.gyro_null = 0.0             # Nullpunktfehler des Lagesensors (rad/s), im Stand gelernt
        self.stempel_ok = False          # erst ein gepruefter Aufnahmezeitstempel erlaubt Bewegung
        self.odom = (0.0, 0.0, 0.0, 0.0)  # (Zeit, vorwaerts, seitwaerts, drehen) gemessen
        self.imu = (0.0, 0.0)            # (Zeit, Drehrate) gemessen
        # Plausibilitaet: passt die Messung zur Richtung der Befehle? (Summe Produkt, Anzahl)
        self.pruef_odom, self.pruef_imu = [0.0, 0], [0.0, 0]
        self.bewegung_quelle = 'Fahrbefehle'
        self.add_on_set_parameters_callback(self._parameter_geaendert)

        # Kamera in eigener Gruppe: eine langsame Bildauswertung blockiert nie die Fahrbefehle
        bild_gruppe = MutuallyExclusiveCallbackGroup()
        rest_gruppe = MutuallyExclusiveCallbackGroup()
        scan_gruppe = MutuallyExclusiveCallbackGroup()   # LiDAR eigene Gruppe: kommt nie zu spaet
        nur_neuestes = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT,
                                  history=HistoryPolicy.KEEP_LAST)
        self.create_subscription(Image, self.p('image_topic'), self.on_image, nur_neuestes,
                                 callback_group=bild_gruppe)
        for i, t in enumerate(self.p('scan_topics')):
            self.create_subscription(LaserScan, t, lambda m, t=t, i=i: self.on_scan(m, t, i),
                                     qos_profile_sensor_data, callback_group=scan_gruppe)
        self.create_subscription(String, '/ki/befehl', self.on_ki, 10, callback_group=rest_gruppe)
        self.create_subscription(Float32, '/line_follower/tempo', self.on_tempo, 10, callback_group=rest_gruppe)
        self.create_subscription(Odometry, '/odom_raw', self.on_odom, qos_profile_sensor_data, callback_group=scan_gruppe)
        self.create_subscription(Imu, '/imu/data_raw', self.on_imu, qos_profile_sensor_data, callback_group=scan_gruppe)
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.pub_status = self.create_publisher(String, '/line_follower/status', 10)
        self.pub_image = self.create_publisher(CompressedImage, '/line_follower/bild/compressed', 1)
        self.create_timer(1.0 / self.p('rate'), self.steuern, callback_group=rest_gruppe)
        self.get_logger().info('Linienfolger gestartet ' + ('(FAEHRT)' if self.p('drive') else '(TESTMODUS)'))

    def p(self, name):
        return self.get_parameter(name).value

    def _parameter_geaendert(self, params):
        # Einstellungen der Linie/Lenkung gelten sofort (z. B. ros2 param set ... kamera_neigung 30.0)
        from rcl_interfaces.msg import SetParametersResult
        for prm in params:
            if prm.name in linie.STANDARD:
                self.sucher.c[prm.name] = prm.value
                self.lenkung.c[prm.name] = prm.value
                if prm.name.startswith('kamera_') or prm.name == 'zeilen_oben':
                    self.sucher.groesse = None  # Draufsicht neu berechnen
        return SetParametersResult(successful=True)

    # ---------------- Eingaenge ----------------
    def on_scan(self, msg, topic, i):
        fronts = self.p('scan_front_deg')
        grund = lidar.scan_pruefen(msg)     # unbrauchbarer Scan = unbekannt -> Halt (nie "frei")
        d = None if grund else lidar.naechster_vorne(msg, fronts[i] if i < len(fronts) else 0.0,
                                                     self.p('obstacle_half_deg'), self.p('obstacle_min_range'),
                                                     rueckwaerts=self.p('direction') < 0)
        self.scans[topic] = (time.time(), d, grund)

    def on_odom(self, msg):
        t = msg.twist.twist
        self.odom = (time.time(), t.linear.x, t.linear.y, t.angular.z)

    def on_imu(self, msg):
        self.imu = (time.time(), msg.angular_velocity.z)

    def bewegung(self, dt):
        """Eigene Bewegung seit dem letzten Aufruf: (vorwaerts, seitwaerts, drehen) je Sekunde.
        Gemessen (Radzaehler, Lagesensor) ist genauer als befohlen (Anfahren, Schlupf). Gemessene Werte
        werden nur benutzt, wenn sie zur Richtung der Fahrbefehle passen (falsch eingebauter Sensor,
        falsches Vorzeichen -> sonst laege die Linie im Gedaechtnis spiegelverkehrt)."""
        lin, quer, dreh = self.letzter_cmd
        if self.p('bewegung') != 'auto':
            self.bewegung_quelle = 'Fahrbefehle'
            return lin, quer, dreh
        jetzt = time.time()
        quellen = []
        oz, ov, oq, ow = self.odom
        if jetzt - oz < 0.3:
            if abs(lin) > 0.05:
                self.pruef_odom[0] += ov * lin
                self.pruef_odom[1] += 1
            if self.pruef_odom[1] >= 20 and self.pruef_odom[0] > 0:
                lin, quer = ov, oq
                quellen.append('Radzaehler')
        iz, iw = self.imu
        if jetzt - iz < 0.3 and not any(self.letzter_cmd) and abs(iw - self.gyro_null) < 0.05:
            # Stand (keine Fahrbefehle): was der Lagesensor jetzt misst, ist sein Nullpunktfehler. Sonst wuerde
            # sich das Linien-Gedaechtnis im Stand langsam verdrehen (z. B. 11 s x 0,003 rad/s = 2 Grad).
            self.gyro_null += 0.02 * (iw - self.gyro_null)
        iw -= self.gyro_null
        if jetzt - iz < 0.3:
            if abs(dreh) > 0.1:
                self.pruef_imu[0] += iw * dreh
                self.pruef_imu[1] += 1
            if self.pruef_imu[1] >= 10 and self.pruef_imu[0] > 0:
                dreh = iw
                quellen.append('Lagesensor')
        self.bewegung_quelle = ' + '.join(quellen) or 'Fahrbefehle'
        return lin, quer, dreh

    def vorhersage_zeit(self):
        """Um wie viele Sekunden hinkt das Linien-Gedaechtnis hinterher? (gemessen oder eingestellt)
        Nur bei gemessener Bewegung: Mit Fahrbefehlen ist das Gedaechtnis nicht zu spaet, sondern eher zu frueh."""
        if self.bewegung_quelle == 'Fahrbefehle':
            return 0.0
        gemessen = self.verzoegerung.ergebnis
        if self.p('selbst_einstellen') and gemessen:
            # gemessen = Motoren (die zaehlen nicht, das Gedaechtnis kennt ja die wahre Bewegung) + Sensoren
            return max(0.0, min(0.3, gemessen['totzeit'] - self.p('motor_totzeit')))
        return self.p('vorhersage')

    def on_ki(self, msg):
        jetzt, alt = time.time(), self.ki[0]
        try:
            self.ki = (jetzt, json.loads(msg.data))
        except ValueError:
            return
        if alt and jetzt - alt > 0.6:     # Diagnose: wie lange war die KI still? (dann stand er)
            self.get_logger().warn(f"KI-Zentrale war {jetzt - alt:.1f} s still (KI-Bild {self.ki[1].get('ki_ms')} ms, "
                                   f"Takt max {self.ki[1].get('takt_max_ms')} ms)")
        if self.ki[1].get('kamera_ok') is False:
            self.kamera_weg_bis = self.ki[0]      # bis hierhin schaute die Kamera woanders hin

    def on_tempo(self, msg):
        # Geschwindigkeit vom Panel (Regler). Begrenzt auf 0..0,5 m/s.
        speed = max(0.0, min(0.5, float(msg.data)))
        self.set_parameters([Parameter('speed', value=speed)])

    def notbremse(self):
        """Grund (Text) oder None. Ein frischer, aber unbrauchbarer Scan haelt wie ein fehlender, bis derselbe
        Kanal wieder einen verwertbaren Scan liefert (dann sofort wieder frei, kein Nachlauf)."""
        if not self.p('obstacle_check'):
            return None
        jetzt = time.time()
        frisch = [(t, d, g) for t, (z, d, g) in self.scans.items() if jetzt - z < 1.0]
        if not frisch:
            if not self.scans:
                return 'KEIN LIDAR: noch nie ein Scan angekommen (obstacle_check:=false zum Abschalten)'
            alter = min(jetzt - z for z, _, _ in self.scans.values())
            return f'KEIN LIDAR: letzter Scan vor {alter:.1f} s'
        ungueltig = [f'{t}: {g}' for t, _, g in frisch if g]
        if ungueltig:
            return 'LIDAR UNBEKANNT (' + '; '.join(ungueltig) + ')'
        t, d, _ = min(frisch, key=lambda x: x[1])
        if d < self.p('notbremse_dist'):
            return f'NOTBREMSE {d * 100:.0f} cm ({t})'
        return None

    # ---------------- Kamera: Linie suchen ----------------
    def on_image(self, msg):
        jetzt = time.time()
        if jetzt - self.bild_zeit < 1.0 / self.p('max_bild_hz') - 0.005:
            return                    # Bild auslassen: entlastet den Rechner (Kamera liefert ~30/s)
        # Wann wurde das Bild aufgenommen? (Zeitstempel der Kamera, gleiche Uhr wie dieser Rechner)
        try:
            stamp = msg.header.stamp
            aufnahme = stamp.sec + stamp.nanosec * 1e-9
            stempel_ok = (stamp.sec >= 0 and 0 <= stamp.nanosec < 1_000_000_000
                          and aufnahme > 0 and 0.0 <= jetzt - aufnahme < 5.0)
        except (AttributeError, TypeError, ValueError, OverflowError):
            stempel_ok = False
        if not stempel_ok:
            # Keine Ersatz-Aufnahmezeit und keine ungueltigen Punkte im Gedaechtnis.
            with self.lock:
                self.stempel_ok = False
                self.linie_gesehen = False
                self.kamera_linie = (None, None)
            return
        img = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
        # Schaut die Kamera gerade woanders hin (KI dreht den Arm zum Umschauen/Greifen)? Dann passt die
        # Umrechnung auf den Boden nicht -> Bild nicht ins Linien-Gedaechtnis (Roboter steht dabei).
        ki_zeit, ki = self.ki
        kamera_weg = bool(ki) and jetzt - ki_zeit < 1.0 and ki.get('kamera_ok') is False
        # Auch Bilder, die kurz nach dem Zurueckdrehen ankommen, wurden evtl. noch mit gedrehter Kamera
        # aufgenommen (Bilder kommen verspaetet an, Arm braucht etwas bis zur Ruhe) -> 0,5 s Sicherheit
        if aufnahme < self.kamera_weg_bis + 0.5:
            kamera_weg = True
        with self.lock:
            ziel = self.gedaechtnis.linie(0.3)
            self.sucher.erwartung = ziel['ziel'] if ziel['gefunden'] else None
            pose = self.gedaechtnis.pose_bei(aufnahme)    # Lage beim Fotografieren (Wahl an Kreuzungen)
        if kamera_weg:
            # Ergebnis wuerde ohnehin verworfen und die Kreuzungswahl nicht geaendert -> Liniensuche sparen
            h = img.shape[0]
            erg = {'gefunden': False, 'boden': [], 'punkte': [],
                   'zeilen': (int(h * self.sucher.c['zeilen_oben']), h - 1)}
        else:
            erg = self.sucher.suche(img, pose[2], kamera_ok=True, pos=pose[:2])
        if erg.get('kreuzung_neu'):
            k = erg['kreuzung']
            seite = 'links' if k['wahl'] > 30 else 'rechts' if k['wahl'] < -30 else 'geradeaus'
            self.get_logger().info(f"Kreuzung: Aeste {k['aeste']} Grad -> zufaellig gewaehlt: {seite} "
                                   f"({k['wahl']:+d} Grad)")
        with self.lock:
            # Punkte dort eintragen, wo der Roboter bei der AUFNAHME stand (Bild kommt verspaetet an)
            self.stempel_ok = True
            self.gedaechtnis.hinzufuegen(erg['boden'], aufnahme)
            self.bild_alter = jetzt - aufnahme  # Alter am Empfang; entscheide addiert die verstrichene Zeit
            self.linie_gesehen = erg['gefunden']
            self.kamera_linie = (erg.get('quer'), erg.get('kurs')) if erg['gefunden'] else (None, None)
            if erg['gefunden'] and erg.get('breite') and erg['breite'][0]:
                self.linie_breite = erg['breite'][0]   # zum Pruefen der Kamera-Einstellung (docs/linie.md)
            self.bild_zeit = jetzt
            self.bild_zaehler += 1
            if jetzt - self.fps_zeit >= 1.0:
                self.fps = self.bild_zaehler / (jetzt - self.fps_zeit)
                self.bild_zaehler, self.fps_zeit = 0, jetzt

        want_pub = self.p('publish_image') and jetzt - self.last_image_pub > 0.1  # max. 10 Bilder/s
        if not (self.p('show') or want_pub):
            return
        view = img.copy()
        linie.zeichne(view, erg)
        h, w = view.shape[:2]
        mode = 'FAEHRT' if self.p('drive') else 'TESTMODUS (faehrt nicht)'
        cv2.putText(view, mode, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        cv2.putText(view, self.status_text[:70], (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        if erg.get('vogel') is not None:  # kleine Draufsicht rechts oben
            vogel = cv2.cvtColor(cv2.resize(erg['vogel'], (120, 106)), cv2.COLOR_GRAY2BGR)
            view[5:111, w - 125:w - 5] = vogel
            cv2.rectangle(view, (w - 125, 5), (w - 5, 111), (255, 255, 255), 1)
        if want_pub:
            self.last_image_pub = jetzt
            klein = cv2.resize(view, (640, int(h * 640 / w))) if w > 640 else view
            ok, jpg = cv2.imencode('.jpg', klein, [cv2.IMWRITE_JPEG_QUALITY, 65])
            if ok:
                out = CompressedImage(format='jpeg', data=jpg.tobytes())
                out.header = msg.header
                self.pub_image.publish(out)
        if self.p('show'):
            self.anzeige = (view, erg.get('vogel'))  # Fenster duerfen nur im Haupt-Thread geoeffnet werden

    # ---------------- Fahrbefehl (20x pro Sekunde) ----------------
    def entscheide(self):
        """Rueckgabe: (vorwaerts, seitwaerts, drehen, status)."""
        jetzt = time.time()
        with self.lock:
            bild_zeit = self.bild_zeit
            stempel_ok = self.stempel_ok
            bild_alter = self.bild_alter + max(0.0, jetzt - bild_zeit)
            ziel = self.gedaechtnis.linie(self.p('vorausschau'))
            # Die Motoren setzen einen Befehl erst nach ca. 'vorhersage' s um -> Linie dort ansehen,
            # wo der Roboter dann ist (er faehrt bis dahin ungefaehr wie zuletzt befohlen)
            lin, quer, dreh = self.letzter_cmd
            vorher = self.vorhersage_zeit()
            lokal = self.gedaechtnis.lokal(self.gedaechtnis.vorhersage(lin, quer, dreh, vorher) if vorher > 0 else None)
            k_voraus = self.gedaechtnis.kruemmung_voraus() if self.p('quer_beschl') > 0 else 0.0
        grund = self.notbremse()
        ki_zeit, ki = self.ki
        manoever = ki.get('manoever') if (ki and ki.get('aktion') == 'manoever' and jetzt - ki_zeit < 0.6) else None
        if grund:
            return 0.0, 0.0, 0.0, grund + ' -> STOPP'
        # Frisches KI-Manoever (zum Greifen ausrichten, wenden) braucht die Linienbilder nicht, nur ein frisch
        # AUFGENOMMENES Bild der KI (Kamera-Zeitstempel, nicht Auswertezeit). Vorher blockierte jeder Aussetzer der
        # Linienbilder das Heranfahren (RM02 22.10.).
        ki_aufnahme = ki.get('aufnahme') if ki else None
        if (manoever and self.p('ki_pflicht') and isinstance(ki_aufnahme, (int, float))
                and 0.0 <= jetzt - ki_aufnahme <= 0.5):
            return self._manoever(manoever, 'KI-Manoever: ')
        if jetzt - bild_zeit > 0.5:
            return 0.0, 0.0, 0.0, 'KEINE KAMERABILDER -> STOPP'
        if not stempel_ok:
            return 0.0, 0.0, 0.0, 'KAMERA-ZEITSTEMPEL UNGUELTIG -> STOPP'
        if bild_alter > self.p('bild_alter_max'):
            return 0.0, 0.0, 0.0, f'KAMERABILDER ZU ALT ({bild_alter:.2f} s) -> STOPP (Rechner ueberlastet?)'
        faktor = 1.0
        if self.p('ki_pflicht'):
            if ki is None or jetzt - ki_zeit > 0.6:
                return 0.0, 0.0, 0.0, 'KI-ZENTRALE ANTWORTET NICHT -> STOPP'
            if ki.get('aktion') == 'stopp':
                return 0.0, 0.0, 0.0, 'KI: ' + ki.get('grund', 'stopp')
            if manoever:
                return self._manoever(manoever, 'KI-Manoever: ')
            faktor = float(ki.get('faktor', 1.0))
        tempo = self.p('speed') * faktor
        if bild_alter > self.p('bild_alter_langsam'):   # Bilder kommen spaet -> langsamer
            tempo *= 0.5
        v, dreh, status = self.lenkung.berechne(ziel, tempo, jetzt, lokal, k_voraus)
        gemessen = self.verzoegerung.ergebnis
        if self.p('selbst_einstellen') and gemessen:
            # dreht er weniger als befohlen (Mecanum-Rollen rutschen)? -> entsprechend mehr befehlen
            dreh /= max(0.8, min(1.2, gemessen['faktor']))
        v *= self.p('direction')
        if ki and ki.get('aktion') == 'langsam':
            status += ' (langsam: ' + ki.get('grund', '') + ')'
        return v, 0.0, dreh, status

    def _manoever(self, m, text):
        """Fahrbefehl der KI (z. B. wenden, zum Greifen ausrichten), begrenzt."""
        lin = max(-MANOEVER_MAX['lin'], min(MANOEVER_MAX['lin'], float(m.get('lin', 0.0))))
        quer = max(-MANOEVER_MAX['quer'], min(MANOEVER_MAX['quer'], float(m.get('quer', 0.0))))
        dreh = max(-MANOEVER_MAX['dreh'], min(MANOEVER_MAX['dreh'], float(m.get('dreh', 0.0))))
        return lin, quer, dreh, text + m.get('text', '')

    def steuern(self):
        jetzt = time.time()
        dt = min(0.2, jetzt - self.letzte_steuerung)
        self.letzte_steuerung = jetzt
        with self.lock:
            # eigene Bewegung seit dem letzten Befehl ins Linien-Gedaechtnis rechnen
            lin_alt, quer_alt, dreh_alt = self.bewegung(dt)
            self.gedaechtnis.bewegen(lin_alt, dreh_alt, dt, quer_alt, jetzt)
        lin, quer, dreh, status = self.entscheide()
        self.status_text = status
        if self.p('drive'):
            t = Twist()
            t.linear.x, t.linear.y, t.angular.z = lin, quer, dreh
            self.pub.publish(t)
            self.letzter_cmd = (lin, quer, dreh)
            if 'Lagesensor' in self.bewegung_quelle:     # Verzoegerung Lenkbefehl -> gemessene Drehung lernen
                self.verzoegerung.hinzu(dreh, self.imu[1])
        else:
            self.letzter_cmd = (0.0, 0.0, 0.0)  # Testmodus: Roboter bewegt sich nicht
        with self.lock:
            lokal = self.gedaechtnis.lokal()
            weg = self.gedaechtnis.weg()
        self.pub_status.publish(String(data=json.dumps({
            'status': status, 'drive': self.p('drive'), 'linear': round(lin, 3), 'quer': round(quer, 3),
            'angular': round(dreh, 3), 'fps': round(self.fps, 1), 'speed': self.p('speed'),
            'linie': self.linie_gesehen or lokal is not None, 'linie_kamera': self.linie_gesehen,
            'linie_quer': None if lokal is None else round(lokal['quer'], 3),
            'bild_alter': round(self.bild_alter, 3), 'zeitstempel_ok': self.stempel_ok,
            'bewegung_quelle': self.bewegung_quelle,
            'linie_breite': None if self.linie_breite is None else round(self.linie_breite, 4),
            'verzoegerung': self.verzoegerung.ergebnis, 'vorhersage': round(self.vorhersage_zeit(), 3),
            'linie_kurs': None if lokal is None else round(lokal['kurs'], 3),
            'kamera_quer': None if self.kamera_linie[0] is None else round(self.kamera_linie[0], 3),
            'kamera_kurs': None if self.kamera_linie[1] is None else round(self.kamera_linie[1], 3),
            'kruemmung': None if lokal is None else round(lokal['kruemmung'], 2),
            'weg': weg})))   # Linie vor dem Roboter (fuer den LiDAR-Fahrschlauch der KI)
        self.get_logger().info(status, throttle_duration_sec=1.0)


def laeuft_schon(name):
    """Gibt es schon ein Programm mit diesem ROS-Namen? (zwei Linienfolger = zwei Fahrbefehle)"""
    pruefer = rclpy.create_node('pruefe_' + name + f'_{os.getpid()}')
    time.sleep(1.5)  # ROS braucht kurz, bis es die anderen kennt
    gefunden = name in pruefer.get_node_names()
    pruefer.destroy_node()
    return gefunden


def signale_abfangen():
    """Strg+C, Beenden und Fenster-zu immer als KeyboardInterrupt behandeln (sauberes Ende).
    Noetig, weil mit '&' aus Skripten gestartete Programme Strg+C sonst ignorieren."""
    def ende(*_):
        raise KeyboardInterrupt
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, ende)


def main():
    signale_abfangen()
    rclpy.init()
    if laeuft_schon('line_follower'):
        print('FEHLER: Es laeuft schon ein Linienfolger (scripts/stopp.sh beendet ihn) -> Abbruch.')
        rclpy.shutdown()
        sys.exit(1)
    node = LineFollower()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    threading.Thread(target=executor.spin, daemon=True).start()
    try:
        while rclpy.ok():
            if node.anzeige is not None:
                view, vogel = node.anzeige
                node.anzeige = None
                cv2.imshow('Linienfolger', view)
                if vogel is not None:
                    cv2.imshow('Draufsicht', vogel)
                cv2.waitKey(1)
            time.sleep(0.03)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if node.p('drive'):
                for _ in range(5):
                    node.pub.publish(Twist())
                    time.sleep(0.05)
        except Exception:
            pass
        cv2.destroyAllWindows()
        executor.shutdown()
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    main()
