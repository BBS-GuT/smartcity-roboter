#!/usr/bin/env python3
# Fahr-Gehirn: eigener Modus, der NUR faehrt - Linie folgen, an Kreuzungen nach festem Fahrplan abbiegen, vorher
# blinken, bei Hindernissen anhalten und warten. Kein Arm, kein Wegraeumen, keine Karte, keine KI-Zentrale noetig.
# Faehrt endlos Runde um Runde, misst jede Kreuzung und Runde und lernt dabei die Fahrparameter.
#
# Start: scripts/fahrgehirn_training.sh   Not-Aus: scripts/stopp.sh   Erklaerung: docs/fahrgehirn.md
#
# Aufbau: Linienerkennung, Lenkung, Linien-Gedaechtnis und LiDAR-Notbremse kommen unveraendert vom Linienfolger
# (Unterklasse von line_follower.LineFollower). Neu dazu:
#   - Hindernis-Regel (fahrgehirn/sicherheit.py): VOR allem anderen geprueft, fest, nicht gelernt
#   - Fahrplan statt Zufall an Kreuzungen (fahrgehirn/fahrplan.py, Haken LinienSucher.waehler in linie.py)
#   - Blinker-Schnittstelle (fahrgehirn/blinker.py), Messung (messung.py), Lernen (lernen.py)
#
# ROS-Schnittstelle (fuer spaeter: Panel, KI-Zentrale, Wechsel mit dem Arm-Gehirn):
#   /fahrgehirn/kommando  std_msgs/String  'start' | 'stopp' | 'pause' | 'weiter' | 'fahrplan <nr>'
#   /fahrgehirn/zustand   std_msgs/String  JSON (zustand, Fahrplan, Blinker, Parameter, Lernphase ...), 2x pro s
#   /fahrgehirn/blinker   std_msgs/String  'links' | 'rechts' | 'aus' (bei jeder Aenderung)
#   /fahrgehirn/antwort   std_msgs/String  Antwort auf ein Kommando
# Pausiert oder gestoppt: nach 0,5 s Stopp-Befehlen sendet er KEINE Fahrbefehle mehr (/cmd_vel ist frei fuer andere).
import json
import math
import os
import sys
import threading
import time

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HIER, '..'))
sys.path.insert(0, os.path.join(REPO, 'line_follower'))
sys.path.insert(0, HIER)
import line_follower as lf   # noqa: E402  (setzt auch die Thread-Grenzen fuer numpy/OpenCV)

import numpy as np  # noqa: E402
import rclpy  # noqa: E402
from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy  # noqa: E402
from sensor_msgs.msg import Image  # noqa: E402
from std_msgs.msg import String  # noqa: E402

import lidar  # noqa: E402  (lib/, Pfad setzt line_follower)
from tiefe import Bodenmodell  # noqa: E402
import lernen as lernmodul  # noqa: E402
import messung  # noqa: E402
from blinker import BlinkerAttrappe  # noqa: E402
from fahrplan import ZIEL_GRAD  # noqa: E402
from gehirn import FahrGehirn  # noqa: E402
from sicherheit import HindernisRegel, im_pfad_schlauch, kreuzungs_pfad  # noqa: E402

FREIGABE_NACH = 0.5    # s nach Pause/Stopp: so lange noch Stopp-Befehle, dann /cmd_vel freigeben


class _Fahrbefehle:
    """Haengt vor dem /cmd_vel-Publisher: Pausiert/gestoppt -> nach FREIGABE_NACH nichts mehr senden."""

    def __init__(self, pub, knoten):
        self.pub, self.knoten = pub, knoten

    def publish(self, msg):
        g = self.knoten.gehirn
        if g.zustand != 'faehrt' and time.time() - g.zustand_seit > FREIGABE_NACH:
            return
        self.pub.publish(msg)


class FahrGehirnKnoten(lf.LineFollower):
    def __init__(self):
        super().__init__('fahrgehirn')
        dp = self.declare_parameter
        dp('fahrplan', 'links, geradeaus, rechts')   # Richtungen der Kreuzungen einer Runde, der Reihe nach
        dp('fahrplan_start', -1)    # >= 0: naechste Kreuzung ist diese Plan-Nr. (-1 = gespeicherte Position)
        dp('autostart', False)      # gleich losfahren (Trainingsskript), sonst erst auf 'start'
        dp('lernen', True)          # False = nur messen, Parameter bleiben fest
        dp('messweg', 0.7)          # so weit (m) nach der Wahl wird die Drehung an der Kreuzung gemessen
        # Feste Sicherheitsregel (wird NICHT gelernt, fahrgehirn/sicherheit.py)
        dp('halt_abstand', 0.30)
        dp('frei_warten', 1.0)
        dp('fahrschlauch_breite', 0.30)
        dp('tiefe_pruefen', True)   # Tiefenkamera prueft zusaetzlich (sieht auch Dinge unter der LiDAR-Ebene)
        dp('depth_topic', '/camera/depth/image_raw')
        self._linienfolger_werte_uebernehmen()
        # Das Fahr-Gehirn faehrt ohne KI-Zentrale. Die eigene Hindernis-Regel ersetzt deren Halt.
        self.set_parameters([Parameter('ki_pflicht', value=False), Parameter('drive', value=True),
                             Parameter('show', value=False),    # kein Fenster: laeuft endlos, auch ohne Bildschirm
                             Parameter('abbiegen', value=True),
                             Parameter('abbiegen_halten', value=True)])   # Wahl halten, bis eingelenkt (linie.py)

        log = self.get_logger()
        self.blinker = BlinkerAttrappe(log=log.info)
        self.pub_blinker = self.create_publisher(String, '/fahrgehirn/blinker', 10)
        blinker_schalten = self.blinker._schalten

        def schalten(richtung):
            blinker_schalten(richtung)
            self.pub_blinker.publish(String(data=richtung))
        self.blinker._schalten = schalten

        self.lern = lernmodul.Lernen(log=log.info)
        self.gehirn = FahrGehirn(self.p('fahrplan'), self.lern, messung.Protokoll(), self.blinker, log=log.info,
                                 messweg=self.p('messweg'), lernen_an=self.p('lernen'))
        if self.p('fahrplan_start') >= 0:
            self.gehirn.umsetzen(self.p('fahrplan_start'))
        self.sucher.waehler = self.gehirn.kreuzung_waehlen
        self.abzweig = None              # Abzweigpunkt der aktuellen Kreuzung (x, y im Gedaechtnis-System)
        suche = self.sucher.suche

        def suche_und_merken(img, gier=None, kamera_ok=True, pos=None):
            erg = suche(img, gier, kamera_ok, pos)
            k = erg.get('kreuzung')
            if k and k.get('abzweig') is not None and pos is not None and gier is not None:
                self.abzweig = (pos[0] + k['abzweig'] * math.cos(gier), pos[1] + k['abzweig'] * math.sin(gier))
            return erg
        self.sucher.suche = suche_und_merken
        self.regel = HindernisRegel(self.p('halt_abstand'), self.p('frei_warten'))
        self.schlauch_scans = {}         # Kanal -> (Empfang, Punkte xy, Winkel ohne Messung)
        self.tiefe = (0.0, 'aus')        # (Empfang, Ergebnis True/False/None)
        self.boden = Bodenmodell({n: self.p(n) for n in ('kamera_hoehe', 'kamera_neigung', 'kamera_fov', 'kamera_x')},
                                 {'weg_breite': self.p('fahrschlauch_breite') / 2,
                                  'weg_laenge': self.regel.halt_abstand + 0.15})
        self.steht_hindernis = False
        self.lidar_grund = ''            # warum der LiDAR gerade als unbekannt gilt (fuer Log/Anzeige)
        self.pub = _Fahrbefehle(self.pub, self)
        self.pub_zustand = self.create_publisher(String, '/fahrgehirn/zustand', 10)
        self.pub_antwort = self.create_publisher(String, '/fahrgehirn/antwort', 10)
        self.create_subscription(String, '/fahrgehirn/kommando', self.on_kommando, 10)
        if self.p('tiefe_pruefen'):
            nur_neuestes = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT,
                                      history=HistoryPolicy.KEEP_LAST)
            self.create_subscription(Image, self.p('depth_topic'), self.on_tiefe, nur_neuestes)
        self.create_timer(0.5, self.zustand_senden)
        self.parameter_uebernehmen()
        log.info(f"Fahr-Gehirn bereit. Fahrplan {list(self.gehirn.plan.plan)}, naechste Kreuzung Nr. "
                 f"{self.gehirn.plan.index} ({self.gehirn.plan.aktuell}). Lernstand: {self.lern.pfad}")
        if self.p('autostart'):
            self.gehirn.kommando('start')

    def _linienfolger_werte_uebernehmen(self):
        """Eigene Werte, die in den Einstellungsdateien NUR unter 'line_follower:' stehen (z. B. Kamera), gelten auch
        hier - der Knoten heisst anders, ROS wuerde sie sonst nicht anwenden."""
        try:
            import einstellungen
            alle, lf_werte, eigene = einstellungen.lade(), einstellungen.lade('line_follower'), einstellungen.lade('fahrgehirn')
        except Exception as e:   # yaml fehlt o. ae.: nur die ROS-Parameter gelten
            self.get_logger().warn(f'Einstellungen des Linienfolgers nicht gelesen: {e}')
            return
        for k, v in lf_werte.items():
            if not self._hat(k) or alle.get(k) == v or k in eigene:
                continue
            try:
                alt = self.p(k)
                if isinstance(alt, float) and isinstance(v, int) and not isinstance(v, bool):
                    v = float(v)     # 30 statt 30.0 in der Datei: ROS wuerde den Typ ablehnen
                self.set_parameters([Parameter(k, value=v)])
            except Exception as e:
                self.get_logger().warn(f'line_follower/{k} = {v!r} nicht uebernommen: {e}')

    def _hat(self, name):
        try:
            self.get_parameter(name)
            return True
        except Exception:      # nicht deklariert (rclpy: ParameterNotDeclaredException)
            return False

    # ---------------- Lernen -> Fahrparameter ----------------
    def parameter_uebernehmen(self):
        werte = self.gehirn.parameter()
        self.set_parameters([Parameter(n, value=v) for n, v in werte.items() if n != 'kreuzung_tempo'])
        self.gehirn.parameter_neu = False
        self.get_logger().info('Fahrparameter: ' + ', '.join(f'{n}={v}' for n, v in werte.items()))

    def on_tempo(self, msg):
        self.get_logger().info('Fahr-Gehirn: Tempo vom Panel ignoriert (das Tempo wird gelernt, Grenzen in '
                               'fahrgehirn/lernen.py)', throttle_duration_sec=10.0)

    # ---------------- Sensoren fuer die Hindernis-Regel ----------------
    def on_scan(self, msg, topic, i):
        super().on_scan(msg, topic, i)
        e = self.scans.get(topic)
        if e is None or e[2]:                     # unbrauchbar: Regel haelt (Pflichtkanal ungueltig)
            self.schlauch_scans.pop(topic, None)
            return
        fronts = self.p('scan_front_deg')
        front = fronts[i] if i < len(fronts) else 0.0
        self.schlauch_scans[topic] = (e[0], lidar.punkte_xy(msg, front, self.p('obstacle_min_range')),
                                      lidar.ungueltige_winkel(msg, front))

    def on_tiefe(self, msg):
        try:
            d = self.bridge.imgmsg_to_cv2(msg, 'passthrough').astype(np.float32)
            if getattr(msg, 'encoding', '16UC1') != '32FC1':
                d /= 1000.0
            pfad = self.kreuzungs_weg()
            with self.lock:
                weg = pfad[1:] if pfad else self.gedaechtnis.weg()
            ergebnis, _ = self.boden.pruefe(d, lernen=not self.steht_hindernis, linie_voraus=weg or None)
        except Exception as e:
            self.get_logger().warn(f'Tiefenbild unbrauchbar: {e}', throttle_duration_sec=5.0)
            ergebnis = None
        self.tiefe = (time.time(), ergebnis)

    def kreuzungs_weg(self):
        """Waehrend einer Kreuzung: geplanter Weg (Roboter-System) bis zum Abzweig und in den gewaehlten Ast, sonst
        None (dann gilt die Linie aus dem Gedaechtnis). Siehe fahrgehirn/sicherheit.py."""
        k = self.gehirn.kreuzung
        if k is None:
            self.abzweig = None
            return None
        if not k.d['gewaehlt'] or self.abzweig is None:
            return None
        with self.lock:
            x, y, w = self.gedaechtnis.pose
        dx, dy = self.abzweig[0] - x, self.abzweig[1] - y
        abzweig = (math.cos(w) * dx + math.sin(w) * dy, -math.sin(w) * dx + math.cos(w) * dy)
        # Richtung: eigene Richtung bei der Wahl + genau 0 / +-90 Grad. Die geschaetzte Astrichtung schwankt um bis
        # zu 35 Grad; ein schraeger Weg zielte im Sim auf ein Haus neben der Strasse -> Dauerhalt
        richtung = math.remainder(k.gier0 + math.radians(ZIEL_GRAD[k.d['gewaehlt']]) - w, 2 * math.pi)
        if abs(richtung) < math.radians(30):
            # eingelenkt (oder geradeaus): das Gedaechtnis kennt die neue Linie genauer als der geschaetzte Abzweig
            # (Sim: Abzweig ca. 10 cm daneben geschaetzt -> Haus 20 cm neben dem Steg lag im Weg)
            return None
        return kreuzungs_pfad(abzweig, richtung)

    def lidar_abstand(self):
        """Naechstes Hindernis im Fahrschlauch (m, inf = frei), None = unbekannt, 'aus' = abgeschaltet."""
        if not self.p('obstacle_check'):
            return 'aus'
        topics = self.p('scan_topics')
        _, grund = lidar.pflichtkanaele(self.scans, topics, time.monotonic())
        if grund:
            self.lidar_grund = grund
            return None
        jetzt = self.ros_jetzt()
        pfad = self.kreuzungs_weg()
        with self.lock:
            weg = self.gedaechtnis.weg()
        halb, laenge = self.p('fahrschlauch_breite') / 2, self.regel.halt_abstand
        schlauch = dict(halbe_breite=halb, laenge=laenge, nah_halb_deg=self.p('obstacle_half_deg'))
        naechster = float('inf')
        for t in topics:
            e = self.schlauch_scans.get(t)
            alter = lidar.aufnahme_alter(self.scans[t][3], jetzt)
            if e is None or self.scans[t][2] or alter:
                self.lidar_grund = f'{t}: {self.scans[t][2] or alter or "kein verwertbarer Scan"}'
                return None
            if pfad is None:
                o = lidar.fahrschlauch(e[1], weg or None, **schlauch)
                abstand = o['abstand'] if o else float('inf')
                luecke = lidar.fahrschlauch_luecke(e[2], weg or None, **schlauch)
            else:
                drin, entlang = im_pfad_schlauch(e[1], pfad, halb, laenge, nah_halb_deg=schlauch['nah_halb_deg'])
                abstand = float(entlang[drin].min()) if drin.any() else float('inf')
                luecke = lidar.luecke_im_bereich(
                    e[2], lambda xy: im_pfad_schlauch(xy, pfad, halb, laenge, nah_halb_deg=schlauch['nah_halb_deg']),
                    laenge + halb)
            if luecke is not None:                # Teil des Fahrwegs nicht gemessen -> unbekannt
                self.lidar_grund = (f'{t} misst den Fahrweg ab {luecke * 100:.0f} cm nicht '
                                    '(Strahlen ohne Messwert: verdeckt, zu nah oder ins Leere)')
                return None
            naechster = min(naechster, abstand)
        return naechster

    def tiefe_ergebnis(self):
        if not self.p('tiefe_pruefen'):
            return 'aus'
        zeit, ergebnis = self.tiefe
        if time.time() - zeit > 0.5:
            return None                           # keine frischen Tiefenbilder: unbekannt -> Halt
        return ergebnis

    # ---------------- Entscheiden ----------------
    def entscheide(self):
        """Reihenfolge = Vorrang: 1. Hindernis-Regel  2. Zustand (pausiert/gestoppt)  3. Linienfolger (mit dessen
        Notbremse)  4. Tempo an Kreuzungen."""
        jetzt = time.time()
        grund = self.regel.pruefe(jetzt, self.lidar_abstand(), self.tiefe_ergebnis())
        if grund and grund.startswith('LIDAR UNBEKANNT'):
            grund = grund.replace('LIDAR UNBEKANNT', f'LIDAR UNBEKANNT ({self.lidar_grund})', 1)
        neu_halt = grund and not self.steht_hindernis
        self.steht_hindernis = bool(grund)
        if grund:
            if neu_halt and self.gehirn.runde is not None:
                self.gehirn.runde.halte += 1
            return 0.0, 0.0, 0.0, grund
        if self.gehirn.zustand != 'faehrt':
            return 0.0, 0.0, 0.0, f'Fahr-Gehirn {self.gehirn.zustand}'
        lin, quer, dreh, status = super().entscheide()
        if lin > 0 and self.gehirn.kreuzung_aktiv():
            f = self.gehirn.parameter()['kreuzung_tempo']
            lin, dreh = lin * f, dreh * f      # gleiche Bahn, nur langsamer
            status += f' (Kreuzung: {self.gehirn.plan.aktuell}, Tempo x{f:.1f})'
        return lin, quer, dreh, status

    def steuern(self):
        jetzt = time.time()
        dt = min(0.2, jetzt - self.letzte_steuerung)
        super().steuern()
        with self.lock:
            lokal = self.gedaechtnis.lokal()
            gier = self.gedaechtnis.pose[2]
        lin, _, dreh = self.letzter_cmd
        self.gehirn.takt(jetzt, dt, lin, dreh, lokal, self.status_text, gier, steht_absichtlich=self.steht_hindernis)
        if self.gehirn.parameter_neu:
            self.parameter_uebernehmen()

    # ---------------- Schnittstelle ----------------
    def on_kommando(self, msg):
        antwort = self.gehirn.kommando(msg.data)
        self.get_logger().info(f'Kommando {msg.data!r}: {antwort}')
        self.pub_antwort.publish(String(data=antwort))

    def zustand_senden(self):
        z = self.gehirn.zustand_info()
        z['halt'] = self.status_text if self.steht_hindernis else None
        self.pub_zustand.publish(String(data=json.dumps(z)))


def main():
    lf.signale_abfangen()
    rclpy.init()
    if lf.laeuft_schon('line_follower', 'fahrgehirn'):
        print('FEHLER: Es laeuft schon ein Linienfolger oder ein Fahr-Gehirn (scripts/stopp.sh beendet beide) '
              '-> Abbruch. Das Fahr-Gehirn ist ein eigener Modus: Panel-START nicht gleichzeitig benutzen.')
        rclpy.shutdown()
        sys.exit(3)              # eigener Code: scripts/fahrgehirn_training.sh startet dann nicht neu
    node = FahrGehirnKnoten()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    threading.Thread(target=executor.spin, daemon=True).start()
    try:
        while rclpy.ok():
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.gehirn.kommando('stopp')         # Runde nicht werten, Blinker aus, Lernstand ist schon gespeichert
            for _ in range(5):
                node.pub.pub.publish(lf.Twist())  # am Freigabe-Filter vorbei: Stopp geht IMMER raus
                time.sleep(0.05)
        except Exception:
            pass
        executor.shutdown()
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    main()
