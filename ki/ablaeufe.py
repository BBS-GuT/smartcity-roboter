#!/usr/bin/env python3
# Ablaeufe der KI, die mehrere Schritte brauchen (ohne ROS, damit testbar):
#   Zebrastreifen  - anhalten, umschauen (Arm links/rechts), warten bis frei, weiter
#   Wenden         - Einbahnstrasse von der falschen Seite: auf der Stelle umdrehen
#   Wegraeumen     - Hindernis genau anschauen, Armbewegung ausrechnen, wegraeumen, pruefen ob frei
#
# Jeder Ablauf hat schritt(jetzt, w) -> Befehl (dict) oder None (= fertig, Ergebnis in .ergebnis).
# Befehl: {'aktion': 'stopp' | 'manoever', 'grund': Text, 'arm': None | {'pose', 'greifer'} | {'winkel', 'zeit_ms'},
#          'manoever': {'lin', 'quer', 'dreh', 'text'}}
# w = Wahrnehmung (siehe ki/entscheider.py).
import math
import os
import sys
import threading

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'))
from lidar import abstand_zum_weg  # noqa: E402

LEBEWESEN = {'Person', 'Hund', 'Katze', 'Pferd', 'Vogel', 'Schaf', 'Kuh', 'Teddy'}
FAHRZEUGE = {'Auto', 'Bus', 'LKW', 'Motorrad', 'Fahrrad', 'Zug'}


def akteure_nah(w):
    """Namen der Personen/Tiere/Fahrzeuge, die beim Wegraeumen zaehlen: nur NAHE (die Zentrale misst den Abstand mit
    der Tiefenkamera, siehe ki/zentrale.py akteur_nah). Fehlt die Angabe 'nah', zaehlt es (lieber einmal zu viel).
    Weiter weg im Hintergrund (Zuschauer, geparkte Autos) zaehlt nicht."""
    return [o['name'] for o in w.get('objekte', []) if o['name'] in LEBEWESEN | FAHRZEUGE and o.get('nah', True)]


def akteur_einordnen(o, abstand, beachten, grenze):
    """Setzt bei einer Person/einem Tier/Fahrzeug der Kamera-KI 'abstand', 'nah' und 'im_weg' (ki/zentrale.py).
    beachten False (Projektinhaber 22.10., Parameter akteure_beachten): halten ihn nie auf - weder beim Wegraeumen
    ('nah') noch als 'KI sieht im Weg'. Sonst zaehlt nah, was naeher als grenze (m) ist oder ohne sichere Tiefe."""
    o['abstand'] = abstand
    o['nah'] = bool(beachten) and (abstand is None or abstand < grenze)
    if not beachten:
        o['im_weg'] = False


def befehl(aktion, grund, arm=None, manoever=None):
    return {'aktion': aktion, 'faktor': 0.0 if aktion == 'stopp' else 1.0, 'grund': grund,
            'arm': arm, 'manoever': manoever}


class Ablauf:
    name = ''
    braucht_arm = False     # bewegt dieser Ablauf den Arm? (dann nur, solange das Fahrprogramm faehrt)

    def __init__(self, jetzt, c):
        self.c = c
        self.phase, self.seit = None, jetzt
        self.ergebnis = None             # 'ok' | 'fehler'
        self.ereignisse = []             # (text, art)
        self.arm_bewegt = False          # steht der Arm evtl. nicht in Fahrstellung?

    def _phase(self, jetzt, phase):
        self.phase, self.seit = phase, jetzt
        self.s_phase = None    # Strecke (Wegraeumen._gefahren) neu zaehlen - auch wenn dieselbe Phase wiederkommt

    def dauer(self, jetzt):
        return jetzt - self.seit


class Zebrastreifen(Ablauf):
    """Vor dem Zebrastreifen anhalten, mit Kamera und LiDAR nach vorne beobachten, erst weiterfahren, wenn eine
    gueltige Beobachtung den Ueberweg frei zeigt.

    Kein eigenstaendiger Arm-/Kameraschwenk (#70, Scopeentscheidung #8): die Freigabe fuer das Wegraeumen umfasst
    keinen Schwenk am Ueberweg, vorhandene Posen allein sind keine Erlaubnis. Dieser Ablauf gibt nie Armbefehle aus.

    Frei ist der Ueberweg nur nach mindestens anschauen_bilder NEUEN, FRISCHEN Kamerabildern im Beobachtungsfenster,
    zu denen jeweils LiDAR-Daten fuer den Ueberweg vorliegen (lidar_xy oder lidar_breit) und die keine Belegung zeigen.
    Ablaufende Zeit, leere Objektlisten, fehlende oder alte Daten zaehlen nicht als frei: dann bleibt er stehen.
    Ganz ungueltige Scans, fehlende/alte Kanaele und Luecken im Fahrschlauch meldet die Zentrale als keine LiDAR-Daten
    (#60/#61/#62/#79) -> Halt. Vertragsluecke (#156): ob die Ueberwegzone SEITLICH neben dem Fahrschlauch (bis
    zebra_seite) gemessen ist, sagt die Wahrnehmung nicht - Strahlen ohne Messung dort sind hier nicht von frei zu
    unterscheiden."""
    name = 'zebra'
    braucht_arm = False     # bewegt den Arm nie (#70)

    def __init__(self, jetzt, c, posen, abstand=0.3):
        super().__init__(jetzt, c)
        self.mit_arm = bool(posen.get('blick_links') and posen.get('blick_rechts') and posen.get('fahrstellung'))
        self.braucht_arm = self.mit_arm
        self.abstand = abstand      # Zebrastreifen so weit voraus (m), gemessen beim Anhalten
        self.weg = None             # Linie voraus beim Anhalten (Bereich wird ENTLANG der Strasse geprueft)
        self.jemand = False
        self.runde = 0
        self.bilder = 0             # gueltige Beobachtungen (neues, frisches Bild + LiDAR am Ueberweg) im Fenster
        self.bild_nr = None         # zuletzt gezaehltes Bild
        self.luecke = None          # warum zuletzt ein Bild nicht zaehlte (fuer den Haltegrund)
        self.grund_warten = ''
        self.zuletzt = jetzt          # Zeit des letzten schritt(): fehlt ein Zyklus, war die Beobachtung nicht lueckenlos
        self._phase(jetzt, 'halt')

    def _beobachten(self, w):
        # Fussgaenger sind Spielfiguren (Projektinhaber 21.10.): nur Figuren in der Naehe des Ueberwegs zaehlen.
        # Zuschauer im Raum (echte Menschen, weit weg) hielten ihn sonst ewig fest. Ohne Abstand/Groesse: zaehlt.
        if any(o['name'] in LEBEWESEN and o.get('spielfigur') is not False
               and (o.get('abstand') is None or o['abstand'] <= self.c['zebra_figur_abstand'])
               for o in w.get('objekte', [])):
            self.jemand = 'Person gesehen'
        self._lidar_belegung(w)

    def _lidar_belegung(self, w):
        """Sieht der LiDAR etwas AUF oder direkt NEBEN dem Zebrastreifen (wartender Fussgaenger)? Laeuft in JEDEM
        Zyklus, nicht nur bei neuen Kamerabildern: stockt die Kamera, zaehlt die aktuelle LiDAR-Belegung trotzdem
        (Codex-Review PR #158). Nur dieser Bereich zaehlt, damit Haeuser und Waende nicht als Fussgaenger gelten."""
        xy = w.get('lidar_xy')
        if w.get('weg'):
            # Linie voraus jedes Mal neu nehmen: beim Anhalten (z. B. direkt nach einer Kurve) ist sie oft noch
            # ungenau, ein paar Bilder spaeter stimmt sie. Mit der alten wuerde er ewig den falschen Bereich pruefen.
            self.weg = w['weg']
        if xy is not None:
            xy = np.asarray(xy).reshape(-1, 2)
            if self.weg:
                # entlang der Linie messen: steht der Roboter (noch) schraeg, zaehlt trotzdem nur der Bereich
                # am Zebrastreifen, nicht Waende/Haeuser daneben
                quer, entlang = abstand_zum_weg(xy, self.weg, self.abstand + self.c['zebra_tiefe'] + 0.2)
                zone = ((entlang > self.abstand - 0.10) & (entlang < self.abstand + self.c['zebra_tiefe'])
                        & (quer < self.c['zebra_seite']))
            else:
                zone = ((xy[:, 0] > self.abstand - 0.10) & (xy[:, 0] < self.abstand + self.c['zebra_tiefe'])
                        & (np.abs(xy[:, 1]) < self.c['zebra_seite']))
            if zone.any():
                x, y = xy[zone][np.argmin(xy[zone][:, 0])]
                seite = 'links' if y > 0 else 'rechts'
                self.jemand = f'etwas am Zebrastreifen, {abs(y) * 100:.0f} cm {seite} (LiDAR)'
        elif w.get('lidar_breit') is not None and w['lidar_breit'] < self.c['zebra_lidar']:
            self.jemand = f"etwas {w['lidar_breit'] * 100:.0f} cm vor mir (LiDAR)"

    def schritt(self, jetzt, w):
        c, d = self.c, self.dauer(jetzt)
        self.zuletzt = jetzt
        if self.phase == 'halt':
            if d >= 0.5:
                # neues Beobachtungsfenster: nichts aus frueheren Runden zaehlt mit
                self.jemand, self.bilder, self.bild_nr, self.luecke = False, 0, None, None
                self._phase(jetzt, 'beobachten')
            return befehl('stopp', 'Zebrastreifen: anhalten')
        if self.phase == 'beobachten':
            # Nur neue, frische Bilder mit LiDAR-Daten am Ueberweg zaehlen. Fehlt etwas, faengt die Zaehlung von
            # vorne an (die Beobachtung muss lueckenlos sein). Kein neues Bild: zaehlt nicht.
            nr = w.get('bild_nr')
            if nr is not None and nr != self.bild_nr:
                self.bild_nr = nr
                aufnahme = w.get('aufnahme')
                if jetzt - w.get('bild_zeit', float('-inf')) > c['ki_max_alter']:
                    self.bilder, self.luecke = 0, 'Kamerabild zu alt'
                elif aufnahme is None or not 0.0 <= jetzt - aufnahme <= c['ki_max_alter']:
                    # bild_zeit ist die Auswertung; ein verzoegertes/wiederholtes Bild zeigt eine alte Szene
                    self.bilder, self.luecke = 0, 'Aufnahmezeit des Kamerabilds fehlt oder zu alt'
                elif w.get('kamera_vorne') is False:
                    self.bilder, self.luecke = 0, 'Kamera schaut nicht nach vorne'
                else:
                    self._beobachten(w)    # Person/Tier im Bild haelt auch ohne LiDAR-Daten
                    if w.get('lidar_xy') is None and w.get('lidar_breit') is None:
                        self.bilder, self.luecke = 0, 'keine LiDAR-Daten am Ueberweg'
                    else:
                        self.bilder += 1
            self._lidar_belegung(w)     # auch ohne neues Bild: aktuelle LiDAR-Belegung vor jeder Entscheidung
            if d >= c['zebra_schauen'] + 1.0 and (self.jemand or self.bilder >= c['anschauen_bilder']):
                return self._entscheiden(jetzt)
            if d >= c['zebra_schauen'] + 1.0:
                # Zeit allein ist keine Freigabe: ohne genug gueltige Beobachtungen bleibt er stehen
                warum = self.luecke or 'zu wenige neue Kamerabilder'
                return befehl('stopp', f"Zebrastreifen: Beobachtung unvollstaendig ({warum}, "
                                       f"{self.bilder}/{c['anschauen_bilder']} Bilder) -> bleibe stehen")
            return befehl('stopp', 'Zebrastreifen: beobachte den Ueberweg')
        if self.phase == 'warten':
            if d >= c['zebra_warten']:
                self._phase(jetzt, 'halt')
                self.seit = jetzt - 0.5
            return befehl('stopp', f'Zebrastreifen: warte ({self.grund_warten})')
        return None

    def _entscheiden(self, jetzt):
        if self.jemand:
            self.runde += 1
            self.grund_warten = self.jemand
            self.ereignisse.append((f'Zebrastreifen: {self.jemand} -> warte', 'stopp'))
            self._phase(jetzt, 'warten')
            return befehl('stopp', f'Zebrastreifen: {self.jemand} -> warte')
        self.ereignisse.append((f"Zebrastreifen frei ({self.bilder} Bilder mit LiDAR) -> weiter", 'fahren'))
        self.ergebnis = 'ok'
        return None

    def pausieren(self, jetzt):
        """Fahrprogramm aus (STOPP/TEST): keine Beobachtung zaehlt, der Ablauf darf nicht im Stillstand fertig
        werden. Nach START beginnt er wieder mit dem Halt und braucht ein neues, vollstaendiges Fenster."""
        self.jemand, self.bilder, self.bild_nr, self.luecke = False, 0, None, None
        self._phase(jetzt, 'halt')

    def unterbrochen(self, grund):
        """Der Entscheider hat in diesem Zyklus schon vorher gehalten (kein LiDAR, keine frischen Bilder, Notbremse,
        ...) und schritt() nicht aufgerufen: Die Beobachtung war nicht lueckenlos, gezaehlte Bilder verfallen.
        (Codex-Review PR #154: sonst gab nach einem LiDAR-Ausfall schon ein einziges Bild frei.)"""
        if self.phase == 'beobachten':
            self.bilder, self.luecke = 0, f'unterbrochen: {grund}'


class Umschauen(Ablauf):
    """Kurz anhalten und mit der Kamera (Arm) nach links und rechts schauen, z. B. fuer die Karte."""
    name = 'umschauen'
    braucht_arm = True

    def __init__(self, jetzt, c, grund='Umschauen'):
        super().__init__(jetzt, c)
        self.grund = grund
        self._phase(jetzt, 'halt')

    def schritt(self, jetzt, w):
        c, d = self.c, self.dauer(jetzt)
        schauen = c['arm_zeit'] + c['zebra_schauen']
        # Phase: (so lange, was gerade passiert, naechste Phase, Arm dafuer)
        folge = {'halt': (0.5, 'anhalten', 'links', {'pose': 'blick_links'}),
                 'links': (schauen, 'schaue nach links', 'rechts', {'pose': 'blick_rechts'}),
                 'rechts': (schauen, 'schaue nach rechts', 'mitte', {'pose': 'fahrstellung'}),
                 'mitte': (c['arm_zeit'], 'Kamera zurueck', None, None)}
        warte, text, naechste, arm = folge[self.phase]
        if d < warte:
            return befehl('stopp', f'{self.grund}: {text}')
        if naechste is None:
            self.arm_bewegt = False
            self.ergebnis = 'ok'
            return None
        self.arm_bewegt = True
        self._phase(jetzt, naechste)
        return befehl('stopp', f'{self.grund}: {folge[naechste][1]}', arm=arm)


class Wenden(Ablauf):
    """Auf der Stelle umdrehen (Einbahnstrasse von der falschen Seite), bis die Linie wieder vorne ist."""
    name = 'wenden'

    def __init__(self, jetzt, c, gier, grund='Einfahrt verboten -> wende'):
        super().__init__(jetzt, c)
        self.gier0 = gier
        self.grund = grund
        self._phase(jetzt, 'halt')

    def schritt(self, jetzt, w):
        c, d = self.c, self.dauer(jetzt)
        if self.phase == 'halt':
            if d >= 0.5:
                self._phase(jetzt, 'drehen')
                self.gier0 = w.get('gier', self.gier0)
            return befehl('stopp', self.grund)
        gedreht = abs(w.get('gier', self.gier0) - self.gier0)
        linie = w.get('linie') or {}
        # Linie wieder vorne: Roboter steht auf ihr und schaut (fast) in ihre Richtung.
        # Zuerst nach dem Linien-Gedaechtnis (kennt auch das Stueck direkt unter/hinter dem Roboter),
        # sonst nach dem Kamerabild.

        def passt(quer, kurs):
            return quer is not None and kurs is not None and abs(quer) < 0.06 and abs(kurs) < math.radians(20)
        linie_vorne = passt(linie.get('quer'), linie.get('kurs')) or (
            linie.get('kamera') and passt(linie.get('kamera_quer'), linie.get('kamera_kurs')))
        if (gedreht >= math.radians(150) and linie_vorne) or gedreht >= math.radians(215):
            self.ereignisse.append((f'Gewendet ({math.degrees(gedreht):.0f} Grad)', 'fahren'))
            self.ergebnis = 'ok'
            return None
        if d > 2.5 and gedreht < math.radians(15):
            # Er soll sich drehen, aber der Lagesensor meldet fast nichts: IMU fehlt/falsch eingebaut oder Raeder
            # blockiert. Nicht endlos im Kreis drehen -> anhalten.
            self.ereignisse.append(('Wenden abgebrochen: Lagesensor meldet keine Drehung (IMU/Raeder pruefen)', 'stopp'))
            self.ergebnis = 'fehler'
            return None
        if d > c['wenden_max_zeit']:
            self.ereignisse.append(('Wenden hat nicht geklappt (Zeit abgelaufen)', 'stopp'))
            self.ergebnis = 'fehler'
            return None
        return befehl('manoever', f'Wende ({math.degrees(gedreht):.0f} von ca. 180 Grad)',
                      manoever={'lin': 0.0, 'quer': 0.0, 'dreh': c['wenden_dreh'], 'text': 'wenden'})


class Wegraeumen(Ablauf):
    """Hindernis im Weg (LiDAR und/oder Kamera haben etwas gemeldet). Ablauf:
      1. anschauen   anhalten, mit der Tiefenkamera mehrere Bilder lang genau hinschauen (wartet ruhig laenger,
                     wenn die KI langsam ist: es zaehlen BILDER, nicht nur Sekunden). Was ist es, wo genau, wie gross?
         pruefblick  Ist es zu nah fuer die Kamera (liegt unter ihrem Blickfeld), neigt er die Kamera nach unten
                     (Pose 'pruefblick') und misst es dort, statt zurueckzufahren. Dann gleich 3. planen, und
                     5. kontrolle ebenfalls im Pruefblick. Sieht er dort nichts: wie bisher (etwas zurueck).
         vorpruefen  noch im Stand: Armbewegung fuer die Greifweite schon einmal durchrechnen. Gibt es neben der
                     Strasse keine erreichbare, freie Ablagestelle (LiDAR schaut, wo schon etwas steht), gar nicht
                     erst heranfahren, sondern gleich warten.
      2. abstand     so weit heran/zurueck, dass der Arm es erreicht und die Kamera es noch sieht (geregelt nach
                     dem, was die Kamera misst, nicht nach der Zeit). Dabei seitlich mittig davor und in Kurven
                     gerade zur Strasse drehen. Verschwindet es (zu niedrig) in Greifweite laut Radzaehler: mit der
                     letzten Messung planen und nach dem Greifen zur Kontrolle so weit zurueck.
      3. planen      ausrechnen, wie der Arm sich bewegen muss (Kinematik + gelernte Korrektur, lib/greifen.py)
                     Reicht der Arm nicht hin: blind ein Stueck naeher heranfahren (Phase 'naeher'), neu planen
      4. ausfuehren  Greifer auf -> ueber das Ding -> runter -> zu -> hoch -> zur Seite -> ablegen -> Fahrstellung
                     (vorher blind herangefahren? dann wieder so weit zurueck, damit die Kamera den Platz sieht)
      5. kontrolle   Kamera wieder nach vorne, mehrere Bilder lang pruefen: ist der Weg WIRKLICH frei?
                     Das Ergebnis (frei = Erfolg) bekommt das Greif-Lernen (rueckmeldung).
                     Nein -> noch ein Versuch (ab 1.), danach aufgeben und warten.
    Sicherheit: Sieht die Kamera waehrenddessen eine Person, ein Tier oder ein Fahrzeug -> sofort abbrechen.
    Ohne Planer (Arm nicht freigegeben) nur 1.: bestaetigt -> warten, bis frei. Warum, steht in ohne_arm.
    ergebnis: 'frei' (weiter), 'unbestaetigt' (nur LiDAR, Kamera sieht nichts), 'bestaetigt' (da, nicht anfassen),
              'fehler' (Wegraeumen hat nicht geklappt)."""
    name = 'wegraeumen'
    braucht_arm = True
    # In diesen Phasen bewegt sich Roboter oder Arm (oder der naechste Schritt tut es): Person/Tier/Fahrzeug -> halten
    # 'kontrolle' haelt nur vor neuen Armbewegungen (Pruefblick, naechster Versuch), siehe _kontrolle_akteur
    HALT_PHASEN = ('vorpruefen', 'abstand', 'zurueck', 'pruefblick', 'pruef_zurueck', 'planen', 'naeher', 'ausfuehren',
                   'rueckweg')

    def __init__(self, jetzt, c, planer=None, darf_greifen=None, rueckmeldung=None, ohne_arm='', pruefblick=False):
        super().__init__(jetzt, c)
        self.planer = planer              # planer(objekt, ablage_seite) -> {'schritte': [...]} | {'fehler': Text}
        self.darf_greifen = darf_greifen  # darf_greifen(objekt, w) -> None (ja) oder Grund (nein)
        self.rueckmeldung = rueckmeldung  # rueckmeldung(plan, erfolg) -> Text (Greif-Lernen) oder None
        self.ohne_arm = ohne_arm or 'Arm nicht freigegeben'   # warum es keinen Planer gibt (fuers Panel)
        self.braucht_arm = planer is not None
        self.pruefblick = pruefblick and planer is not None   # Pose 'pruefblick' da (Kamera steiler nach unten)
        self.pruef_versucht = False       # schon im Pruefblick nachgesehen (einmal je Wegraeumen, sonst endlos)
        self.im_pruef = False             # Hindernis wurde im Pruefblick vermessen -> auch dort kontrollieren
        self.versuch = 1
        self.zurueck_gefahren = 0.0
        self.zuletzt_vermessen = None     # letzte Messung der Kamera in DIESEM Ablauf (bleibt ueber neues Anschauen)
        self.merk = None                  # (Abstand vorne m, Strecke dabei) der letzten Kamera-Messung - fuer den
                                          # Entscheider: wo liegt es, auch wenn die Kamera es nicht mehr sieht
        self.lebend_seit = self.lebend_zuletzt = None
        self.lebend_name = ''
        self.akteur_seit = self.akteur_zuletzt = None   # dasselbe fuer die Kontrolle
        self.letzter_schritt = jetzt
        self.s_alt, self.s_phase = None, None   # fuer _gefahren (gemessene Strecke)
        self.vorgefahren = 0.0            # so weit ist er blind naeher herangefahren (m)
        self.kontroll_rand = 0.0          # zur Kontrolle so viel weiter zurueck als vorgefahren (m)
        self.grund = ''
        self._anschauen(jetzt)

    def _anschauen(self, jetzt):
        self._phase(jetzt, 'anschauen')
        self.im_pruef = self.kontrolle_pruef = False   # neu hinschauen: gilt erst wieder nach Pruefblick-Messung
        self.kontrolle_blind = False
        self.messungen, self.lidar_werte, self.bilder, self.lebewesen = [], [], 0, None
        self.lebewesen_n = 0              # in so vielen Bildern Person/Tier/Fahrzeug gesehen
        self.gesehen = 0                  # Bilder, in denen die Tiefenkamera etwas sah (auch ohne Vermessung)

    def _gefahren(self, w, jetzt, tempo):
        """Strecke (m, + vorwaerts) seit dem letzten Aufruf in dieser Phase. Mit Radzaehlern (w['strecke'], von der
        Zentrale) die wirklich gefahrene Strecke - auch wenn die KI kurz haengt oder der Linienfolger den Befehl
        blockiert. Ohne: befohlenes Tempo x Zeit, Zeit begrenzt (sonst springt es nach einer Pause)."""
        if self.s_phase != self.phase:
            self.s_phase, self.s_alt, self.letzte = self.phase, w.get('strecke'), jetzt
            return 0.0
        s = w.get('strecke')
        if s is not None and self.s_alt is not None:
            ds, self.s_alt = s - self.s_alt, s
        else:
            ds = tempo * min(0.15, jetzt - self.letzte)
            self.s_alt = s
        self.letzte = jetzt
        return ds

    def _vorwaerts(self, b):
        """Befehl b faehrt vorwaerts? Dann merken: die letzte Messung ist ohne Radzaehler nicht mehr aktuell."""
        m = (b or {}).get('manoever') or {}
        if self.merk is not None and m.get('lin', 0.0) > 0:
            self.merk = (self.merk[0], self.merk[1], True)
        return b

    def _ende(self, ergebnis, text, art):
        self.ergebnis = ergebnis
        self.ereignisse.append((text, art))
        return None

    def schritt(self, jetzt, w):
        c, d = self.c, self.dauer(jetzt)
        if w.get('lidar_xy') is not None:
            self.letztes_w_xy = w['lidar_xy']
        neu = w.get('neues_bild')
        # NEUES Tiefenbild (Zentrale: tiefe_nr)? Laufen nur Farbbilder weiter, zaehlt dasselbe Tiefenbild nicht mehrfach
        # (ohne jede Nummer - nur in reinen Ablauftests - zaehlt jedes neue Bild)
        nr = w.get('tiefe_nr', w.get('bild_nr'))
        tiefe_neu = neu and (nr is None or nr != getattr(self, 'tiefe_nr', None))
        if neu:
            self.tiefe_nr = nr
        obj = w.get('objekt') if neu else None
        kamera_obj = obj if obj and obj.get('quelle') == 'tiefe' else None
        if kamera_obj:
            self.merk = (kamera_obj['vor'], w.get('strecke'), False)   # False: seitdem nicht vorwaerts gefahren
        lid = w.get('lidar')
        if self.phase in self.HALT_PHASEN:
            # Person/Tier/Fahrzeug taucht auf: Arm und Roboter halten STILL (keine neue Bewegung, Greifer bleibt
            # wie er ist - sonst fiele ein gehaltener Wuerfel irgendwo hin). Weiter erst, wenn 2 s niemand mehr da ist.
            lebend = akteure_nah(w) if neu else []
            if lebend:
                if self.lebend_seit is None:
                    self.lebend_seit = jetzt
                    self.ereignisse.append((f'Wegraeumen: {lebend[0]} in Sicht -> Arm haelt still, warte', 'stopp'))
                self.lebend_zuletzt, self.lebend_name = jetzt, lebend[0]
            if self.lebend_seit is not None:
                if jetzt - self.lebend_zuletzt < 2.0:
                    if jetzt - self.lebend_seit > 30.0:
                        return self._ende('fehler', f'Wegraeumen abgebrochen: {self.lebend_name} bleibt in Sicht', 'stopp')
                    self.seit += jetzt - self.letzter_schritt     # Wartezeit des laufenden Schritts anhalten
                    if self.phase == 'abstand':
                        # beim Warten verdeckt die Person evtl. den Gegenstand: zaehlt nicht als "aus den Augen
                        # verloren" (RM02 21.10.: nach jeder Person brach er sofort ab)
                        self.zuletzt_gesehen += jetzt - self.letzter_schritt
                    self.letzter_schritt, self.letzte = jetzt, jetzt
                    self.s_alt = w.get('strecke')
                    return befehl('stopp', f'Wegraeumen: {self.lebend_name} in Sicht -> Arm haelt still, warte')
                self.lebend_seit = None
                self.ereignisse.append(('Wegraeumen: niemand mehr in Sicht -> mache weiter', 'info'))
        vorher, self.letzter_schritt = self.letzter_schritt, jetzt
        c, d = self.c, self.dauer(jetzt)
        if self.phase == 'anschauen':
            if w.get('kamera_vorne') is False:
                # Arm faehrt noch in die Fahrstellung: Kamera misst noch nicht -> Bilder zaehlen nicht, Uhr steht
                self.seit += jetzt - vorher
                return befehl('stopp', 'Hindernis: warte, bis die Kamera wieder nach vorne schaut')
            if neu:
                self.bilder += 1
                if kamera_obj:
                    self.messungen.append(kamera_obj)
                    self.zuletzt_vermessen = kamera_obj
                if kamera_obj or w.get('tiefe_hindernis'):
                    self.gesehen += 1
                if lid is not None:
                    self.lidar_werte.append(lid)
                lebend = akteure_nah(w)
                if lebend:
                    # erst ab 2 Bildern: ein einzelnes Fehlbild (KI irrt sich kurz) soll nicht alles blockieren
                    self.lebewesen_n += 1
                    if self.lebewesen_n >= 2:
                        self.lebewesen = lebend[0]
            genug = d >= c['anschauen_min'] and self.bilder >= c['anschauen_bilder']
            if not genug and d < c['anschauen_max']:
                return befehl('stopp', f'Hindernis: schaue es mir genau an ({self.bilder} Bilder)')
            if neu and lebend and self.lebewesen is None:
                # erst ein Bild mit Person/Tier/Fahrzeug: noch nicht entscheiden (das koennte Arm oder Roboter bewegen),
                # das naechste Bild zeigt, ob es ein Fehlbild war
                return befehl('stopp', f'Hindernis: {lebend[0]} in Sicht? schaue nochmal hin')
            return self._entscheiden(jetzt, w)
        if self.phase == 'pruefblick':
            # erst messen, wenn der Arm sicher steht (die Zentrale misst ohnehin erst dann im Pruefblick)
            if d < c['arm_zeit'] + 0.5:
                return befehl('stopp', 'Hindernis zu nah fuer die Kamera -> Pruefblick (Kamera nach unten)')
            if neu:
                self.bilder += 1
                if w.get('blick') == 'pruef':     # Zentrale hat dieses Bild wirklich im Pruefblick ausgewertet
                    self.pruef_bilder += 1
                    self.pruef_tiefe += bool(w.get('tiefe_hindernis'))
                    if w.get('pruef_tiefe'):
                        self.pruef_diag = w['pruef_tiefe']
                if kamera_obj and kamera_obj.get('blick') == 'pruef':
                    self.messungen.append(kamera_obj)
            t = d - c['arm_zeit'] - 0.5
            if (t < c['anschauen_min'] or self.bilder < c['anschauen_bilder']) and t < c['anschauen_max']:
                return befehl('stopp', f'Hindernis: Pruefblick ({self.bilder} Bilder)')
            if len(self.messungen) >= 3:
                return self._pruef_gesehen(jetzt, w)
            # im Pruefblick nichts: Kamera zurueck nach vorne, dann wie bisher entscheiden (etwas zurueckfahren ...)
            # Diagnose (RM02 21.10.: Pruefblick sah nie etwas): Kam der Arm in die Pose? Sah die Tiefenkamera etwas?
            diag = getattr(self, 'pruef_diag', None)
            if diag:
                naechst = 'keiner' if diag[1] is None else f'{diag[1] * 100:.0f} cm'
                diag = f', gueltige Tiefe {diag[0]:.0%} des Bildes, naechster Messwert {naechst}'
            self.ereignisse.append((f'Pruefblick: nichts gesehen (im Pruefblick ausgewertet: {self.pruef_bilder} von '
                                    f'{self.bilder} Bildern, Tiefenkamera meldete etwas in {self.pruef_tiefe}'
                                    f'{diag or ""}) -> Kamera zurueck nach vorne', 'info'))
            self._phase(jetzt, 'pruef_zurueck')
            return befehl('stopp', 'Pruefblick: Kamera zurueck', arm={'pose': 'fahrstellung'})
        if self.phase == 'pruef_zurueck':
            if d < c['arm_zeit']:
                return befehl('stopp', 'Pruefblick: Kamera zurueck')
            self.arm_bewegt = False
            # in Fahrstellung frisch hinschauen (LiDAR, Kamera): die alten Zaehler koennen aus einem frueheren
            # Versuch stammen. Pruefblick nicht noch einmal (pruef_versucht).
            self._anschauen(jetzt)
            return befehl('stopp', 'Hindernis: schaue nochmal hin')
        if self.phase == 'zurueck':
            hinten = w.get('lidar_hinten')
            self.zurueck_gefahren -= self._gefahren(w, jetzt, -c['zurueck_tempo'])
            if not w.get('strecke_gemessen'):
                # Strecke nur aus Fahrbefehlen geschaetzt (Radzaehler weg): kein Nachweis, dass er wirklich
                # zurueckgefahren ist (ein blockierter Roboter "kaeme" so auch zurueck) -> danach nie "frei"
                self.zurueck_unbelegt = True
            # Zeitgrenze: melden die Radzaehler keine Bewegung (Rad blockiert, Odometrie weg), sonst ewig rueckwaerts.
            # Dann sicher anhalten und warten - nie so tun, als waere er zurueckgefahren (danach koennte "frei" folgen)
            if (d > 1.5 * c['sicht_zurueck'] / c['zurueck_tempo'] + 1.0       # erwartete Zeit + Reserve
                    and self.zurueck_gefahren < c['sicht_zurueck']):
                return self._ende('fehler', 'Wegraeumen: Zurueckfahren klappt nicht (Radzaehler melden keine '
                                            'Bewegung) -> warte', 'stopp')
            if hinten is None or hinten < c['hinten_frei'] or self.zurueck_gefahren >= c['sicht_zurueck']:
                self._anschauen(jetzt)
                return befehl('stopp', 'Hindernis: schaue nochmal hin')
            return befehl('manoever', 'Hindernis zu nah fuer die Kamera -> fahre etwas zurueck',
                          manoever={'lin': -c['zurueck_tempo'], 'quer': 0.0, 'dreh': 0.0, 'text': 'zurueck'})
        if self.phase == 'vorpruefen':
            if self.plan is None:
                if d > 6.0:
                    return self._ende('fehler', 'Wegraeumen: Ablagestelle suchen dauert zu lange -> warte', 'stopp')
                return befehl('stopp', 'Hindernis: suche eine Ablagestelle neben der Strasse ...')
            if self.plan.get('ablage_fehlt'):
                return self._ende('fehler', f"Wegraeumen geht nicht (vor dem Heranfahren geprueft): "
                                            f"{self.plan['fehler']} -> warte", 'stopp')
            if not self.plan.get('fehler'):
                self.ereignisse.append((f"Ablagestelle gefunden: {self.plan.get('info', '')}", 'info'))
            self.plan = None
            self._phase(jetzt, 'abstand')
            self.ruhig, self.zuletzt_gesehen = 0, jetzt
            self.messungen, self.schraeg_werte, self.abstand_letzt = [], [], None   # nur Messungen von hier an
            self.objekt_strecke = None        # Radstrecke der letzten Sichtung: nur aus DIESEM Heranfahren
            return befehl('stopp', 'Hindernis: fahre in Greifweite')
        if self.phase == 'abstand':
            # gemessen = Radzaehler frisch UND seit der letzten Sichtung ohne Luecke (Abschnitt gleich, siehe Zentrale)
            # leer zaehlt nur ein neues Tiefenbild (tiefe_neu, oben). Gesehen auch: ein stehendes Tiefenbild (nur Farbbilder
            # laufen weiter) ist keine neue Beobachtung - sonst regelte er minutenlang mit einem alten Fund (Review PR #126)
            frisch = kamera_obj if tiefe_neu else None
            return self._vorwaerts(self._abstand(jetzt, frisch, w.get('strecke'), w.get('weg'),
                                                 bool(w.get('strecke_gemessen')), w.get('odom_abschnitt'), tiefe_neu,
                                                 w.get('lidar_hinten')))
        if self.phase == 'planen':
            if self.plan is None:
                if d > 6.0:
                    return self._ende('fehler', 'Wegraeumen: Armbewegung ausrechnen dauert zu lange', 'stopp')
                return befehl('stopp', 'Hindernis: rechne aus, wie der Arm greifen muss ...')
            if self.plan.get('naeher') and self.vorgefahren + self.plan['naeher'] <= c['naeher_max'] + 1e-6:
                self.naeher_ziel, self.letzte = self.vorgefahren + self.plan['naeher'], jetzt
                self.ereignisse.append((f"Arm reicht nicht hin -> fahre {self.plan['naeher'] * 100:.0f} cm naeher heran", 'info'))
                self._phase(jetzt, 'naeher')
                return befehl('stopp', 'Hindernis: Arm reicht nicht hin, fahre naeher heran')
            if self.plan.get('fehler'):
                return self._ende('fehler', f"Wegraeumen geht nicht: {self.plan['fehler']} -> warte", 'stopp')
            self.ereignisse.append((f"Armbewegung berechnet: {self.plan.get('info', '')}", 'info'))
            self.schritte, self.nr = list(self.plan['schritte']), -1
            self.arm_bewegt = True
            self._phase(jetzt, 'ausfuehren')
            self.warte = 0.0
            d = 0.0
        if self.phase == 'naeher':
            # blind (Kamera sieht es so nah evtl. nicht mehr): nach gemessener Strecke (Radzaehler), langsam
            self.vorgefahren += self._gefahren(w, jetzt, c['naeher_tempo'])
            if self.vorgefahren >= self.naeher_ziel - 1e-4:
                o = dict(self.objekt_plan, vor=self.objekt_plan['vor'] - self.vorgefahren,
                         vor_gemessen=self.objekt_plan['vor'], belegt=self._belegt())
                self.plan = None
                self._phase(jetzt, 'planen')
                threading.Thread(target=self._planen, args=(o, self.seite), daemon=True).start()
                return befehl('stopp', 'Hindernis: rechne aus, wie der Arm greifen muss ...')
            return self._vorwaerts(befehl('manoever', f'Hindernis: fahre naeher heran ({self.vorgefahren * 100:.0f} cm)',
                                          manoever={'lin': c['naeher_tempo'], 'quer': 0.0, 'dreh': 0.0,
                                                    'text': 'naeher heran'}))
        if self.phase == 'rueckweg':
            self.vorgefahren += self._gefahren(w, jetzt, -c['naeher_tempo'])
            hinten = w.get('lidar_hinten')
            rand = self.kontroll_rand       # nach blindem Greifen etwas weiter zurueck als bis zur letzten Sichtung
            if self.vorgefahren <= 1e-4 - rand or hinten is None or hinten < c['hinten_frei'] or d > 10.0:
                if self.vorgefahren > 0.02 - rand:
                    # nicht ganz zurueck (hinten nicht frei): Kamera sieht den Platz evtl. nicht -> nicht lernen
                    self.kontrolle_unsicher = True
                    self.ereignisse.append(('Konnte nicht ganz zurueckfahren: Kontrolle unsicher, wird nicht gelernt',
                                            'info'))
                    # blind gegriffen: Kamera hat den Gegenstand an dieser Stelle nie gesehen -> "frei" waere geraten
                    self.kontrolle_blind = rand > 0
                self.vorgefahren, self.kontroll_rand = 0.0, 0.0
                self._phase(jetzt - c['arm_zeit'] * 0.5, 'kontrolle')
                self.kontrolle_bilder = self.kontrolle_da = 0
                return befehl('stopp', 'Wegraeumen: pruefe, ob der Weg frei ist')
            return befehl('manoever', 'Wegraeumen: fahre zurueck, damit die Kamera den Platz sieht',
                          manoever={'lin': -c['naeher_tempo'], 'quer': 0.0, 'dreh': 0.0, 'text': 'zurueck'})
        if self.phase == 'ausfuehren':
            if d < self.warte:
                return befehl('stopp', f'Wegraeumen: {self.schritte[self.nr][0]}')
            self.nr += 1
            if self.nr >= len(self.schritte):
                if self.vorgefahren > 0.005 or self.kontroll_rand > 0:   # blind gegriffen: immer zurueck zur Kontrolle
                    self._phase(jetzt, 'rueckweg')
                    self.letzte = jetzt
                    return befehl('stopp', 'Wegraeumen: Arm faehrt zurueck, dann fahre ich zurueck und pruefe')
                self._phase(jetzt, 'kontrolle')
                self.kontrolle_bilder = self.kontrolle_da = 0
                return befehl('stopp', 'Wegraeumen: Arm faehrt zurueck, dann pruefe ich den Weg')
            text, winkel, dauer = self.schritte[self.nr]
            self.seit, self.warte = jetzt, dauer
            return befehl('stopp', f'Wegraeumen: {text}', arm={'winkel': winkel, 'zeit_ms': int(dauer * 1000)})
        if self.phase == 'kontrolle':
            warten = self._kontrolle_akteur(jetzt, w, neu)
            if self.im_pruef:
                # Es lag zu nah fuer die Fahrstellung: dort saehe die Kamera es auch jetzt nicht -> im Pruefblick pruefen
                if not self.kontrolle_pruef and warten:
                    self.seit = jetzt                 # Kontrolle beginnt erst, wenn der Arm sich bewegen darf
                    return warten
                if not self.kontrolle_pruef:
                    self.kontrolle_pruef = True
                    # Uhr so stellen, dass das Zaehlen (unten, ab arm_zeit/2) erst beginnt, wenn der Arm steht
                    self._phase(jetzt + c['arm_zeit'] * 0.5 + 0.5, 'kontrolle')
                    return befehl('stopp', 'Wegraeumen: pruefe im Pruefblick, ob der Weg frei ist',
                                  arm={'pose': 'pruefblick'})
                if d < c['arm_zeit'] * 0.5:
                    return befehl('stopp', 'Wegraeumen: Pruefblick')
                kamera_obj = kamera_obj if kamera_obj and kamera_obj.get('blick') == 'pruef' else None
            elif d < c['arm_zeit'] * 0.5:
                return befehl('stopp', 'Wegraeumen: Arm faehrt zurueck in Fahrstellung')
            else:
                self.arm_bewegt = False      # ab jetzt schaut die Kamera wieder nach vorne
            if neu:
                self.kontrolle_bilder += bool(tiefe_neu)   # "frei" nur aus verschiedenen Tiefenbildern
                if (kamera_obj and kamera_obj['vor'] < c['kontrolle_bereich']) or (
                        lid is not None and lid < c['pruef_dist']):
                    self.kontrolle_da += 1
            if d < c['arm_zeit'] * 0.5 + c['kontrolle_zeit'] or self.kontrolle_bilder < c['anschauen_bilder']:
                return befehl('stopp', f'Wegraeumen: pruefe, ob der Weg frei ist ({self.kontrolle_bilder} Bilder)')
            if not getattr(self, 'kontrolle_unsicher', False):
                self._melden(self.kontrolle_da < 2)
            self.kontrolle_unsicher = False
            if getattr(self, 'kontrolle_blind', False) and self.kontrolle_da < 2:
                return self._ende('fehler', 'Wegraeumen: blind gegriffen und nicht weit genug zurueck, um zu pruefen '
                                            '-> warte', 'stopp')
            if self.kontrolle_da >= 2:
                if self.versuch < c['versuche'] and warten:
                    # naechster Versuch bewegt Arm/Roboter: erst, wenn niemand da ist (hoechstens 30 s, dann aufgeben)
                    if jetzt - self.akteur_seit > 30.0:
                        return self._ende('fehler', f'Wegraeumen abgebrochen: {self.lebend_name} bleibt in Sicht',
                                          'stopp')
                    return warten
                if self.versuch < c['versuche']:
                    self.versuch += 1
                    self.ereignisse.append((f'Weg noch nicht frei -> {self.versuch}. Versuch', 'stopp'))
                    im_pruef = self.im_pruef
                    self._anschauen(jetzt)
                    if im_pruef:
                        return self._pruefblick_start(jetzt)
                    return befehl('stopp', 'Hindernis: schaue nochmal hin')
                return self._ende('fehler', f'Wegraeumen: liegt nach {self.versuch} Versuchen noch da -> warte',
                                  'stopp')
            return self._ende('frei', 'Weg ist frei (geprueft) -> weiter', 'fahren')
        return None

    def _kontrolle_akteur(self, jetzt, w, neu):
        """Kontrolle: Person/Tier/Fahrzeug in den letzten 2 s gesehen? Dann Befehl zum Warten (vor neuen Arm- oder
        Fahrbewegungen), sonst None. Nur Zuschauen (Bilder zaehlen) geht weiter. Vor dem Pruefblick wartet er ohne
        Zeitgrenze (Arm steht in Fahrstellung, haelt nichts fest); vor einem neuen Versuch hoechstens 30 s."""
        lebend = akteure_nah(w) if neu else []
        if lebend:
            if self.akteur_seit is None:
                self.akteur_seit = jetzt
                self.ereignisse.append((f'Wegraeumen: {lebend[0]} in Sicht -> Arm bleibt, wo er ist, warte', 'stopp'))
            self.akteur_zuletzt, self.lebend_name = jetzt, lebend[0]
        if self.akteur_zuletzt is None or jetzt - self.akteur_zuletzt >= 2.0:
            self.akteur_seit = None
            return None
        return befehl('stopp', f'Wegraeumen: {self.lebend_name} in Sicht -> Arm haelt still, warte')

    def _entscheiden(self, jetzt, w):
        """Nach dem Anschauen: was ist es und was tun?"""
        c = self.c
        if self.lebewesen:
            return self._ende('bestaetigt', f'Hindernis ist {self.lebewesen} -> nicht anfassen, warte', 'stopp')
        if len(self.messungen) < 3 and self.gesehen >= 3:
            return self._ende('bestaetigt', 'Hindernis bestaetigt (Tiefenkamera) -> warte', 'stopp')
        if len(self.messungen) < 3 and (self.bilder < c['anschauen_bilder'] or self.gesehen > 0):
            # Zu wenige Bilder (KI ueberlastet) oder nur ab und zu etwas gesehen: KEIN Urteil "frei" daraus
            # machen - sonst faehrt er ueber etwas, das er nur nicht richtig sehen konnte. Stehen bleiben und
            # nochmal hinschauen.
            grund = (f'KI liefert zu wenige Bilder ({self.bilder})' if self.bilder < c['anschauen_bilder']
                     else f'Kamera sieht es nur in {self.gesehen} von {self.bilder} Bildern')
            self.ereignisse.append((f'Hindernis: {grund} -> schaue nochmal hin', 'info'))
            self._anschauen(jetzt)
            return befehl('stopp', f'Hindernis: {grund} -> schaue nochmal hin')
        if len(self.messungen) < 3 and self.pruefblick and not self.pruef_versucht:
            lid_nah = [x for x in self.lidar_werte if x < c['kamera_min_sicht']]
            if self.zuletzt_vermessen is not None or len(lid_nah) >= 2:
                # zu nah fuer die Kamera: erst mit dem Pruefblick (Kamera nach unten) hinschauen, nicht zurueckfahren
                self.ereignisse.append(('Hindernis zu nah fuer die Kamera -> Pruefblick (Kamera nach unten)', 'info'))
                return self._pruefblick_start(jetzt)
        if len(self.messungen) < 3 and self.zuletzt_vermessen is not None:
            # Vorhin hat die Kamera etwas gesehen, jetzt nicht mehr. Meist ist es nur zu nah (unter dem Blickfeld
            # der Kamera, z. B. weil er nach dem Halt noch etwas gerollt ist) -> zurueck, bis sie es wieder sieht.
            # Erst wenn es auch dann nicht mehr da ist, gilt der Weg als frei.
            if self.zurueck_gefahren < c['sicht_zurueck']:
                hinten = w.get('lidar_hinten')
                if hinten is None or hinten < c['hinten_frei']:
                    return self._ende('bestaetigt', 'Hindernis vorhin gesehen, jetzt zu nah fuer die Kamera, hinten '
                                                    'nicht frei -> warte', 'stopp')
                self.ereignisse.append(('Hindernis vorhin gesehen, jetzt nicht mehr (zu nah?) -> fahre etwas zurueck',
                                        'info'))
                self.letzte = jetzt
                self._phase(jetzt, 'zurueck')
                return befehl('stopp', 'Hindernis zu nah fuer die Kamera -> fahre etwas zurueck')
        if len(self.messungen) < 3:
            # Kamera sieht in allen Bildern nichts. Meldet der LiDAR noch etwas?
            lid = [x for x in self.lidar_werte if x < c['pruef_dist']]
            if len(lid) < 2:
                if getattr(self, 'zurueck_unbelegt', False):
                    return self._ende('fehler', 'Wegraeumen: zurueckgefahren ohne Radzaehler, Kamera sieht nichts '
                                                '-> nicht sicher frei, warte', 'stopp')
                if getattr(self, 'verloren_n', 0):
                    # beim Heranfahren verloren und auch nach dem Zurueckfahren nicht wiedergefunden: vielleicht nur
                    # zu niedrig fuer die Kamera, nicht weg -> nicht "frei" (er fuehre drueber)
                    return self._ende('fehler', 'Wegraeumen: Hindernis nach dem Zurueckfahren nicht wiedergefunden '
                                                '-> warte', 'stopp')
                return self._ende('frei', 'Kamera und LiDAR sehen nichts mehr -> weiter', 'fahren')
            naechst = float(np.median(lid))
            if naechst < c['kamera_min_sicht'] and self.zurueck_gefahren < c['sicht_zurueck']:
                self.letzte = jetzt
                self._phase(jetzt, 'zurueck')
                return befehl('stopp', 'Hindernis zu nah fuer die Kamera -> fahre etwas zurueck')
            return self._ende('unbestaetigt', f'LiDAR meldet etwas in {naechst * 100:.0f} cm, Kamera sieht nichts',
                              'info')
        o = self._mittel()
        self.objekt = o
        self.ereignisse.append((f"Hindernis gesehen: {o['vor'] * 100:.0f} cm voraus, {o['seite'] * 100:+.0f} cm seitlich, "
                                f"{o['breite'] * 100:.0f} cm breit, {o['hoehe'] * 100:.0f} cm hoch "
                                f"({len(self.messungen)} von {self.bilder} Bildern)", 'info'))
        if self.planer is None:
            return self._ende('bestaetigt', f'Hindernis bestaetigt (Kamera), raeume nicht weg: {self.ohne_arm} -> warte',
                              'stopp')
        nein = self.darf_greifen(o, w) if self.darf_greifen else None
        if nein:
            return self._ende('bestaetigt', f'Hindernis bestaetigt, {nein} -> warte', 'stopp')
        # Vor dem Heranfahren: wohin damit? Plan so rechnen, als stuende er schon in Greifweite.
        self.plan = None
        self.seite = self._ablage_seite(self.letztes_w_xy)
        probe = dict(o, vor=c['greif_vor'], vor_gemessen=o['vor'], belegt=self._belegt())
        self._phase(jetzt, 'vorpruefen')
        threading.Thread(target=self._planen, args=(probe, self.seite), daemon=True).start()
        return befehl('stopp', 'Hindernis: suche eine Ablagestelle neben der Strasse ...')

    def _pruefblick_start(self, jetzt):
        self.pruef_versucht = True
        self.messungen, self.bilder = [], 0
        self.pruef_bilder = self.pruef_tiefe = 0
        self.pruef_diag = None
        self.arm_bewegt = True
        self._phase(jetzt, 'pruefblick')
        return befehl('stopp', 'Hindernis zu nah fuer die Kamera -> Pruefblick (Kamera nach unten)',
                      arm={'pose': 'pruefblick'})

    def _pruef_gesehen(self, jetzt, w):
        """Im Pruefblick vermessen: gleich planen (es liegt schon nah genug, Heranfahren sieht die Kamera nicht)."""
        o = self._mittel()
        winkel = [x['blick_winkel'] for x in self.messungen if x.get('blick_winkel')]
        if winkel:
            o['blick_winkel'] = winkel[-1]
        self.objekt, self.im_pruef, self.kontrolle_pruef = o, True, False
        self.ereignisse.append((f"Hindernis im Pruefblick gesehen: {o['vor'] * 100:.0f} cm voraus, "
                                f"{o['seite'] * 100:+.0f} cm seitlich, {o['breite'] * 100:.0f} cm breit, "
                                f"{o['hoehe'] * 100:.0f} cm hoch ({len(self.messungen)} von {self.bilder} Bildern)", 'info'))
        nein = self.darf_greifen(o, w) if self.darf_greifen else None
        if nein:
            return self._ende('bestaetigt', f'Hindernis bestaetigt, {nein} -> warte', 'stopp')
        o['belegt'] = self._belegt()
        self.plan, self.objekt_plan = None, o
        self._phase(jetzt, 'planen')
        self.seite = seite = self._ablage_seite(self.letztes_w_xy)
        threading.Thread(target=self._planen, args=(o, seite), daemon=True).start()
        return befehl('stopp', 'Hindernis: rechne aus, wie der Arm greifen muss ...')

    def _mittel(self):
        m = self.messungen
        aus = {k: float(np.median([x[k] for x in m])) for k in ('vor', 'seite', 'breite', 'hoehe')}
        for k in ('pixel', 'tiefe_m'):        # fuer Yahbooms Kinematik (Kamerapunkt -> Arm)
            werte = [x[k] for x in m if x.get(k) is not None]
            if werte:
                aus[k] = [float(v) for v in np.median(np.array(werte, dtype=float).reshape(len(werte), -1), axis=0)]
                if k == 'tiefe_m':
                    aus[k] = aus[k][0]
        q = [x['quer'] for x in m if x.get('quer') is not None]
        if q:
            aus['quer'] = float(np.median(q))
        aus['quelle'] = 'tiefe'
        return aus

    def _verloren(self, jetzt, hinten, vor=None):
        """Beim Heranfahren aus den Augen verloren (und blind greifen geht nicht): etwas zurueck, bis die Kamera es
        wieder sieht, und neu anfangen (hoechstens zweimal). Vorher wartete er nur (RM02 21.10.: fast jeder Versuch).
        vor: wo es laut Radzaehler liegt. Weiter weg als die Greifweite sollte die Kamera es sehen -> zurueck hilft
        nicht (eher weggenommen), wie bisher warten."""
        c = self.c
        self.verloren_n = getattr(self, 'verloren_n', 0) + 1
        weit = vor is not None and vor > c['greif_vor'] + c['greif_toleranz']
        if self.verloren_n > 2 or weit or hinten is None or hinten < c['hinten_frei']:
            return self._ende('fehler', 'Wegraeumen: Hindernis beim Heranfahren aus den Augen verloren -> warte',
                              'stopp')
        self.ereignisse.append(('Hindernis beim Heranfahren aus den Augen verloren -> fahre etwas zurueck und '
                                'schaue nochmal hin', 'info'))
        self.zurueck_gefahren = 0.0      # eigenes Stueck zurueck fuer diesen Versuch (hoechstens sicht_zurueck)
        self.letzte = jetzt
        self._phase(jetzt, 'zurueck')
        return befehl('stopp', 'Hindernis aus den Augen verloren -> fahre etwas zurueck')

    def _abstand(self, jetzt, obj, strecke=None, weg=None, gemessen=False, abschnitt=None, neu=False, hinten=None):
        c = self.c
        schraeg = None
        if obj:
            self.objekt, self.zuletzt_gesehen = dict(obj), jetzt
            self.objekt_strecke, self.objekt_abschnitt = strecke, abschnitt
            self.leer_bilder = 0          # frische Bilder seit dieser Sichtung, in denen es fehlt
            if neu:                       # nur neue Tiefenbilder sind neue Messungen (Farbbilder laufen evtl. allein)
                self.messungen.append(obj)
                self.messungen = self.messungen[-5:]
            # Ruhig/ausgerichtet nach dem Median der letzten 3 Messungen: ein verrauschtes Tiefenbild setzt nicht
            # alles zurueck (RM02 22.10.: bei 33 cm 15 s lang nie 3x hintereinander in Toleranz)
            m3 = self.messungen[-3:] or [obj]  # noch keine neue Messung seit dem Start: diese (zaehlt nicht)
            fehler_vor = float(np.median([x['vor'] for x in m3])) - c['greif_vor']
            self.seite_median = float(np.median([x['seite'] for x in m3]))
            seitlich = abs(self.seite_median) > c['greif_seite']
            # Kurve: Roboter steht schraeg zur Strasse (und damit zum Gegenstand) -> erst gerade drehen
            schraeg = self._schraeg(weg, obj['vor'])
            if schraeg is not None:
                self.schraeg_zuletzt = schraeg
                self.schraeg_werte = (getattr(self, 'schraeg_werte', []) + [schraeg])[-3:]
            # Linie gerade unbekannt: zuletzt gemessene Schraeglage gilt weiter (nicht einfach "gerade")
            werte = getattr(self, 'schraeg_werte', [])
            bekannt = float(np.median(werte)) if werte else getattr(self, 'schraeg_zuletzt', None)
            # Winkel nie bekannt: Greifen mit Sicht wie bisher erlaubt (sonst ohne Linie nie), blind aber nicht
            gerade = bekannt is None or abs(bekannt) < c['greif_winkel']
            if neu:
                self.ruhig = (self.ruhig + 1 if len(self.messungen) >= 3 and abs(fehler_vor) < c['greif_toleranz']
                              and not seitlich and gerade else 0)
            self.ausgerichtet = not seitlich and bekannt is not None and abs(bekannt) < c['greif_winkel']
        else:
            s0 = getattr(self, 'objekt_strecke', None)
            # blind nur mit echten Radzaehlern: aus Fahrbefehlen geschaetzte Strecke ist kein Nachweis
            gemessen = gemessen and abschnitt == getattr(self, 'objekt_abschnitt', None)
            if neu:
                self.leer_bilder = getattr(self, 'leer_bilder', 0) + 1
            # "verschwunden" heisst: frische Bilder zeigen es nicht - nicht nur, dass die KI gerade keine liefert
            frisch_leer = getattr(self, 'leer_bilder', 0) >= c['anschauen_bilder']
            if (s0 is not None and strecke is not None and gemessen and frisch_leer
                    and getattr(self, 'ausgerichtet', False) and jetzt - self.zuletzt_gesehen > c['blind_warten']):
                # Niedrige Gegenstaende (3 cm) verschwinden schon ab ca. 30 cm unter dem Blickfeld der Kamera
                # (RM02 21.10.). Liegt die Greifweite nach Radzaehler erreicht: mit der letzten Messung greifen.
                gefahren = strecke - s0
                if abs(self.objekt['vor'] - gefahren - c['greif_vor']) < c['greif_toleranz']:
                    return self._blind_planen(jetzt, gefahren)
            if jetzt - self.zuletzt_gesehen > 2.5:
                vor = None if s0 is None or strecke is None else self.objekt['vor'] - (strecke - s0)
                return self._verloren(jetzt, hinten, vor)
        if self.ruhig >= 3:
            o = self._mittel()
            o['belegt'] = self._belegt()
            self.plan = None
            self.objekt_plan = o
            self._phase(jetzt, 'planen')
            self.seite = seite = self._ablage_seite(self.letztes_w_xy)
            threading.Thread(target=self._planen, args=(o, seite), daemon=True).start()
            return befehl('stopp', 'Hindernis: rechne aus, wie der Arm greifen muss ...')
        if self.dauer(jetzt) > c['greif_dauer']:
            return self._ende('fehler', 'Wegraeumen: in Greifweite fahren dauert zu lange', 'stopp')
        o = self.objekt
        vor = o['vor']
        s0 = getattr(self, 'objekt_strecke', None)
        # Einzelne Bilder ohne Treffer (verrauschte Tiefe) sind kein Grund anzuhalten: Drehen und Seitwaerts kurz
        # weiter wie zuletzt. Vorher wechselten STOPP und Manoever im Bildtakt, er kam nicht voran (RM02 22.10.)
        halten = getattr(self, 'abstand_letzt', None) or (0.0, 0.0)
        luecke = not obj and jetzt - self.zuletzt_gesehen < c['greif_luecke'] and any(halten)
        if not obj and s0 is not None and strecke is not None:
            # gerade nicht gesehen: mit den Radzaehlern weiterrechnen, sonst faehrt er mit der alten Messung ueber
            # die Greifweite hinaus (blind)
            vor -= strecke - s0
            if abs(vor - c['greif_vor']) < c['greif_toleranz'] / 2 and not luecke:
                return befehl('stopp', f"Hindernis: in Greifweite? schaue hin ({vor * 100:.0f} cm)")
        fehler = vor - c['greif_vor']
        lin = max(-0.03, min(0.03, 0.6 * fehler))
        if abs(fehler) >= c['greif_toleranz'] / 2:
            lin = math.copysign(max(abs(lin), c['greif_min_lin']), lin)
        quer = dreh = 0.0
        seite = self.seite_median if obj else 0.0             # seitlich nur nach frischer Messung (kein Zaehler)
        if abs(seite) > c['greif_seite'] * 0.6:
            quer = max(-0.03, min(0.03, 0.6 * seite))
            quer = math.copysign(max(abs(quer), c['greif_min_quer']), quer)
        if schraeg is not None and c['greif_winkel'] * 0.5 < abs(schraeg) < math.radians(35):   # sonst unplausibel
            dreh = max(-0.25, min(0.25, 0.8 * schraeg))        # auf der Stelle gerade zur Strasse drehen
            dreh = math.copysign(max(abs(dreh), c['greif_min_dreh']), dreh)
        if luecke:
            quer, dreh = halten
        if obj:
            self.abstand_letzt = (quer, dreh)
        if dreh:
            # erst auf der Stelle gerade drehen, dann heranfahren: beides zugleich brachte ihn in Greifweite, bevor er
            # gerade stand - dort sah die Kamera den Gegenstand nicht mehr (RM02 21.10.: "drehe +27 Grad", verloren).
            # Drehen um die Mitte aendert den Abstand kaum, die Kamera behaelt ihn im Blick. Auch nicht seitlich
            # schieben: wirklich auf der Stelle (sonst verlaesst die Fahrzeughuelle die Spur)
            lin = quer = 0.0
        gemerkt = getattr(self, 'schraeg_zuletzt', None)
        if not dreh and schraeg is None and gemerkt is not None and abs(gemerkt) >= c['greif_winkel']:
            # Linie gerade weg, zuletzt stand er aber schraeg: nicht naeher heran (dort verloere er es wieder), warten,
            # bis die Linie wieder da ist und er weiter gerade drehen kann
            lin = min(lin, 0.0)
            quer = 0.0
        if lin < 0 and (hinten is None or hinten < c['hinten_frei']):
            lin = 0.0                                          # rueckwaerts nur, wenn hinten frei
        text = f"Hindernis: fahre in Greifweite ({vor * 100:.0f} cm"
        if quer and obj:
            text += f", {seite * 100:+.0f} cm seitlich"
        if dreh:
            text += f", drehe {math.degrees(schraeg):+.0f} Grad gerade" if schraeg is not None else ", drehe weiter"
        return befehl('manoever', text + ')',
                      manoever={'lin': lin, 'quer': quer, 'dreh': dreh, 'text': 'in Greifweite'})

    def _blind_planen(self, jetzt, gefahren):
        """Gegenstand beim Heranfahren nicht mehr zu sehen, laut Radzaehler aber in Greifweite: mit der letzten Messung
        planen. Wie beim blinden Naeherfahren gilt die Strecke seit der Messung als vorgefahren -> nach dem Greifen
        faehrt er so weit zurueck, dass die Kamera den Platz wieder sieht (sonst waere die Kontrolle blind)."""
        o = dict(self.objekt, belegt=self._belegt())
        self.objekt_plan = o                      # 'vor' = Abstand bei der letzten Messung
        self.vorgefahren = max(0.0, gefahren)
        # Bei der letzten Sichtung stand die Kamera an ihrer Sichtgrenze: zur Kontrolle 3 cm weiter zurueck, sonst
        # saehe sie einen liegengebliebenen Gegenstand evtl. nicht und meldete "frei" (er fuehre drueber)
        self.kontroll_rand = 0.03
        rest = o['vor'] - self.vorgefahren
        self.ereignisse.append((f"Hindernis beim Heranfahren aus dem Blick (zu niedrig/zu nah fuer die Kamera), laut "
                                f"Radzaehler {rest * 100:.0f} cm voraus -> greife nach der letzten Messung", 'info'))
        self.plan = None
        self._phase(jetzt, 'planen')
        self.seite = self._ablage_seite(self.letztes_w_xy)
        threading.Thread(target=self._planen, args=(dict(o, vor=rest, vor_gemessen=o['vor']), self.seite),
                         daemon=True).start()
        return befehl('stopp', 'Hindernis: rechne aus, wie der Arm greifen muss ...')

    @staticmethod
    def _schraeg(weg, vor):
        """Wie schraeg steht der Roboter zur Strasse dort, wo der Gegenstand liegt (rad, + = Strasse zeigt nach links)?
        Aus der Linie vor dem Roboter (Linienfolger). None = unbekannt."""
        if not weg or len(weg) < 2:
            return None
        p = np.asarray(weg, dtype=float).reshape(-1, 2)
        um = p[np.abs(np.hypot(p[:, 0], p[:, 1]) - vor) < 0.08]   # weg ist nach Abstand sortiert
        if len(um) < 2:
            return None
        dx, dy = um[-1] - um[0]
        if math.hypot(dx, dy) < 0.04:
            return None
        return math.atan2(dy, dx)     # > 35 Grad: unplausibel zum Drehen, gilt aber auch nicht als gerade (Aufrufer)

    letztes_w_xy = None

    def _belegt(self):
        """LiDAR-Punkte (Roboter-System) fuer die Ablagesuche - ohne das Hindernis selbst (das liegt ja vorne)."""
        if self.letztes_w_xy is None:
            return None
        xy = np.asarray(self.letztes_w_xy, dtype=float).reshape(-1, 2)
        return xy[np.abs(xy[:, 1]) > 0.12]

    def _melden(self, erfolg):
        """Ergebnis des Greifversuchs an das Lernen geben (nur einmal je Versuch)."""
        plan, self.plan_gemeldet = getattr(self, 'plan', None), True
        if self.rueckmeldung is None or not plan or not plan.get('lernen') or plan.get('_gemeldet'):
            return
        plan['_gemeldet'] = True
        try:
            text = self.rueckmeldung(plan, erfolg)
        except Exception as e:      # Lernen darf den Ablauf nie stoeren
            text = f'Greif-Lernen: Fehler beim Speichern ({e})'
        if text:
            self.ereignisse.append((text, 'info'))

    def _planen(self, o, seite):
        try:
            self.plan = self.planer(o, seite)
        except Exception as e:   # Planer darf den Ablauf nie haengen lassen
            self.plan = {'fehler': f'Rechenfehler ({e})'}

    @staticmethod
    def _ablage_seite(xy):
        """Wohin damit? Auf die Seite, auf der der LiDAR neben dem Roboter weniger sieht (+1 links, -1 rechts).
        Gleich viel: rechts (Strassenrand bei Rechtsverkehr)."""
        if xy is None:
            return -1
        xy = np.asarray(xy).reshape(-1, 2)
        nah = (xy[:, 0] > -0.1) & (xy[:, 0] < 0.4) & (np.abs(xy[:, 1]) > 0.12) & (np.abs(xy[:, 1]) < 0.45)
        links, rechts = int((nah & (xy[:, 1] > 0)).sum()), int((nah & (xy[:, 1] < 0)).sum())
        return 1 if links < rechts else -1


class Ausweichen(Wenden):
    """Weg lange versperrt (z. B. anderer Roboter kommt entgegen): etwas zurueck, dann wenden und
    in der Gegenrichtung weiterfahren. Rueckwaerts nur, wenn der LiDAR hinten frei meldet."""
    name = 'ausweichen'

    def __init__(self, jetzt, c, gier):
        super().__init__(jetzt, c, gier, 'Weg versperrt -> weiche aus (zurueck und wenden)')
        self._phase(jetzt, 'zurueck')
        self.gefahren = 0.0
        self.letzte_zeit = jetzt

    def schritt(self, jetzt, w):
        if self.phase == 'zurueck':
            c = self.c
            if 'lidar_hinten' not in w:                # erster Aufruf ohne Wahrnehmung: nur anhalten
                return befehl('stopp', self.grund)
            dt, self.letzte_zeit = jetzt - self.letzte_zeit, jetzt
            hinten = w.get('lidar_hinten')
            frei = hinten is not None and hinten > c['hinten_frei']
            if not frei or self.gefahren >= c['zurueck_strecke'] or self.dauer(jetzt) > 6.0:
                self._phase(jetzt - 0.5, 'halt')        # direkt weiter mit Wenden
                return befehl('stopp', self.grund)
            self.gefahren += c['zurueck_tempo'] * dt
            return befehl('manoever', f'Weiche aus: fahre zurueck ({self.gefahren * 100:.0f} cm)',
                          manoever={'lin': -c['zurueck_tempo'], 'quer': 0.0, 'dreh': 0.0, 'text': 'zurueck'})
        return super().schritt(jetzt, w)
