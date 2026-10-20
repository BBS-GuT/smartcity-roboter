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

    def dauer(self, jetzt):
        return jetzt - self.seit


class Zebrastreifen(Ablauf):
    """Vor dem Zebrastreifen anhalten, umschauen, erst weiterfahren wenn niemand kommt."""
    name = 'zebra'

    def __init__(self, jetzt, c, posen, abstand=0.3):
        super().__init__(jetzt, c)
        self.mit_arm = bool(posen.get('blick_links') and posen.get('blick_rechts') and posen.get('fahrstellung'))
        self.braucht_arm = self.mit_arm
        self.abstand = abstand      # Zebrastreifen so weit voraus (m), gemessen beim Anhalten
        self.weg = None             # Linie voraus beim Anhalten (Bereich wird ENTLANG der Strasse geprueft)
        self.jemand = False
        self.runde = 0
        self._phase(jetzt, 'halt')

    def _beobachten(self, w):
        # Personen/Tiere irgendwo im Bild (nicht nur im Weg) ...
        if any(o['name'] in LEBEWESEN for o in w.get('objekte', [])):
            self.jemand = 'Person gesehen'
        # ... oder der LiDAR sieht etwas AUF oder direkt NEBEN dem Zebrastreifen (wartender Fussgaenger).
        # Nur dieser Bereich zaehlt, damit Haeuser und Waende nicht als Fussgaenger gelten.
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
        arm_ruhig = d > c['arm_zeit']
        if self.phase == 'halt':
            if d >= 0.5:
                self.jemand = False
                if self.mit_arm:
                    self.arm_bewegt = True
                    self._phase(jetzt, 'links')
                    return befehl('stopp', 'Zebrastreifen: schaue nach links', arm={'pose': 'blick_links'})
                self._phase(jetzt, 'geradeaus')
            return befehl('stopp', 'Zebrastreifen: anhalten')
        if self.phase in ('links', 'rechts', 'geradeaus'):
            if arm_ruhig or self.phase == 'geradeaus':
                self._beobachten(w)
            if self.phase == 'links' and d >= c['arm_zeit'] + c['zebra_schauen']:
                self._phase(jetzt, 'rechts')
                return befehl('stopp', 'Zebrastreifen: schaue nach rechts', arm={'pose': 'blick_rechts'})
            if self.phase == 'rechts' and d >= c['arm_zeit'] + c['zebra_schauen']:
                self._phase(jetzt, 'mitte')
                return befehl('stopp', 'Zebrastreifen: Kamera zurueck', arm={'pose': 'fahrstellung'})
            if self.phase == 'geradeaus' and d >= c['zebra_schauen'] + 1.0:
                return self._entscheiden(jetzt)
            return befehl('stopp', f'Zebrastreifen: schaue ({self.phase})')
        if self.phase == 'mitte':
            if d >= c['arm_zeit']:
                self.arm_bewegt = False
                self._beobachten(w)
                return self._entscheiden(jetzt)
            return befehl('stopp', 'Zebrastreifen: Kamera zurueck')
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
        self.ereignisse.append(('Zebrastreifen frei -> weiter', 'fahren'))
        self.ergebnis = 'ok'
        return None


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
         vorpruefen  noch im Stand: Armbewegung fuer die Greifweite schon einmal durchrechnen. Gibt es neben der
                     Strasse keine erreichbare, freie Ablagestelle (LiDAR schaut, wo schon etwas steht), gar nicht
                     erst heranfahren, sondern gleich warten.
      2. abstand     so weit heran/zurueck, dass der Arm es erreicht und die Kamera es noch sieht (geregelt nach
                     dem, was die Kamera misst, nicht nach der Zeit)
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

    def __init__(self, jetzt, c, planer=None, darf_greifen=None, rueckmeldung=None, ohne_arm=''):
        super().__init__(jetzt, c)
        self.planer = planer              # planer(objekt, ablage_seite) -> {'schritte': [...]} | {'fehler': Text}
        self.darf_greifen = darf_greifen  # darf_greifen(objekt, w) -> None (ja) oder Grund (nein)
        self.rueckmeldung = rueckmeldung  # rueckmeldung(plan, erfolg) -> Text (Greif-Lernen) oder None
        self.ohne_arm = ohne_arm or 'Arm nicht freigegeben'   # warum es keinen Planer gibt (fuers Panel)
        self.braucht_arm = planer is not None
        self.versuch = 1
        self.zurueck_gefahren = 0.0
        self.zuletzt_vermessen = None     # letzte Messung der Kamera in DIESEM Ablauf (bleibt ueber neues Anschauen)
        self.merk = None                  # (Abstand vorne m, Strecke dabei) der letzten Kamera-Messung - fuer den
                                          # Entscheider: wo liegt es, auch wenn die Kamera es nicht mehr sieht
        self.lebend_seit = self.lebend_zuletzt = None
        self.lebend_name = ''
        self.letzter_schritt = jetzt
        self.s_alt, self.s_phase = None, None   # fuer _gefahren (gemessene Strecke)
        self.vorgefahren = 0.0            # so weit ist er blind naeher herangefahren (m)
        self.grund = ''
        self._anschauen(jetzt)

    def _anschauen(self, jetzt):
        self._phase(jetzt, 'anschauen')
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
        obj = w.get('objekt') if neu else None
        kamera_obj = obj if obj and obj.get('quelle') == 'tiefe' else None
        if kamera_obj:
            self.merk = (kamera_obj['vor'], w.get('strecke'), False)   # False: seitdem nicht vorwaerts gefahren
        lid = w.get('lidar')
        if self.phase in ('abstand', 'zurueck', 'planen', 'naeher', 'ausfuehren', 'rueckweg'):
            # Person/Tier/Fahrzeug taucht auf: Arm und Roboter halten STILL (keine neue Bewegung, Greifer bleibt
            # wie er ist - sonst fiele ein gehaltener Wuerfel irgendwo hin). Weiter erst, wenn 2 s niemand mehr da ist.
            lebend = [o['name'] for o in w.get('objekte', []) if o['name'] in LEBEWESEN | FAHRZEUGE] if neu else []
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
                    self.letzter_schritt, self.letzte = jetzt, jetzt
                    self.s_alt = w.get('strecke')
                    return befehl('stopp', f'Wegraeumen: {self.lebend_name} in Sicht -> Arm haelt still, warte')
                self.lebend_seit = None
                self.ereignisse.append(('Wegraeumen: niemand mehr in Sicht -> mache weiter', 'info'))
        self.letzter_schritt = jetzt
        c, d = self.c, self.dauer(jetzt)
        if self.phase == 'anschauen':
            if neu:
                self.bilder += 1
                if kamera_obj:
                    self.messungen.append(kamera_obj)
                    self.zuletzt_vermessen = kamera_obj
                if kamera_obj or w.get('tiefe_hindernis'):
                    self.gesehen += 1
                if lid is not None:
                    self.lidar_werte.append(lid)
                lebend = [o['name'] for o in w.get('objekte', []) if o['name'] in LEBEWESEN | FAHRZEUGE]
                if lebend:
                    # erst ab 2 Bildern: ein einzelnes Fehlbild (KI irrt sich kurz) soll nicht alles blockieren
                    self.lebewesen_n += 1
                    if self.lebewesen_n >= 2:
                        self.lebewesen = lebend[0]
            genug = d >= c['anschauen_min'] and self.bilder >= c['anschauen_bilder']
            if not genug and d < c['anschauen_max']:
                return befehl('stopp', f'Hindernis: schaue es mir genau an ({self.bilder} Bilder)')
            return self._entscheiden(jetzt, w)
        if self.phase == 'zurueck':
            hinten = w.get('lidar_hinten')
            self.zurueck_gefahren -= self._gefahren(w, jetzt, -c['zurueck_tempo'])
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
            return befehl('stopp', 'Hindernis: fahre in Greifweite')
        if self.phase == 'abstand':
            return self._vorwaerts(self._abstand(jetzt, kamera_obj))
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
            if self.vorgefahren <= 1e-4 or hinten is None or hinten < c['hinten_frei'] or d > 10.0:
                if self.vorgefahren > 0.02:
                    # nicht ganz zurueck (hinten nicht frei): Kamera sieht den Platz evtl. nicht -> nicht lernen
                    self.kontrolle_unsicher = True
                    self.ereignisse.append(('Konnte nicht ganz zurueckfahren: Kontrolle unsicher, wird nicht gelernt',
                                            'info'))
                self.vorgefahren = 0.0
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
                if self.vorgefahren > 0.005:
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
            if d < c['arm_zeit'] * 0.5:
                return befehl('stopp', 'Wegraeumen: Arm faehrt zurueck in Fahrstellung')
            self.arm_bewegt = False      # ab jetzt schaut die Kamera wieder nach vorne
            if neu:
                self.kontrolle_bilder += 1
                if (kamera_obj and kamera_obj['vor'] < c['kontrolle_bereich']) or (
                        lid is not None and lid < c['pruef_dist']):
                    self.kontrolle_da += 1
            if d < c['arm_zeit'] * 0.5 + c['kontrolle_zeit'] or self.kontrolle_bilder < c['anschauen_bilder']:
                return befehl('stopp', f'Wegraeumen: pruefe, ob der Weg frei ist ({self.kontrolle_bilder} Bilder)')
            if not getattr(self, 'kontrolle_unsicher', False):
                self._melden(self.kontrolle_da < 2)
            self.kontrolle_unsicher = False
            if self.kontrolle_da >= 2:
                if self.versuch < c['versuche']:
                    self.versuch += 1
                    self.ereignisse.append((f'Weg noch nicht frei -> {self.versuch}. Versuch', 'stopp'))
                    self._anschauen(jetzt)
                    return befehl('stopp', 'Hindernis: schaue nochmal hin')
                return self._ende('fehler', f'Wegraeumen: liegt nach {self.versuch} Versuchen noch da -> warte',
                                  'stopp')
            return self._ende('frei', 'Weg ist frei (geprueft) -> weiter', 'fahren')
        return None

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

    def _abstand(self, jetzt, obj):
        c = self.c
        if obj:
            self.objekt, self.zuletzt_gesehen = dict(obj), jetzt
            fehler_vor = obj['vor'] - c['greif_vor']
            seitlich = abs(obj['seite']) > c['greif_seite']
            self.ruhig = self.ruhig + 1 if abs(fehler_vor) < c['greif_toleranz'] and not seitlich else 0
            self.messungen.append(obj)
            self.messungen = self.messungen[-5:]
        elif jetzt - self.zuletzt_gesehen > 2.5:
            return self._ende('fehler', 'Wegraeumen: Hindernis beim Heranfahren aus den Augen verloren -> warte', 'stopp')
        if self.ruhig >= 3:
            o = self._mittel()
            o['belegt'] = self._belegt()
            self.plan = None
            self.objekt_plan = o
            self._phase(jetzt, 'planen')
            self.seite = seite = self._ablage_seite(self.letztes_w_xy)
            threading.Thread(target=self._planen, args=(o, seite), daemon=True).start()
            return befehl('stopp', 'Hindernis: rechne aus, wie der Arm greifen muss ...')
        if self.dauer(jetzt) > 15:
            return self._ende('fehler', 'Wegraeumen: in Greifweite fahren dauert zu lange', 'stopp')
        o = self.objekt
        lin = max(-0.03, min(0.03, 0.6 * (o['vor'] - c['greif_vor'])))
        quer = 0.0
        if abs(o['seite']) > c['greif_seite'] * 0.6:
            quer = max(-0.03, min(0.03, 0.6 * o['seite']))
        return befehl('manoever', f"Hindernis: fahre in Greifweite ({o['vor'] * 100:.0f} cm)",
                      manoever={'lin': lin, 'quer': quer, 'dreh': 0.0, 'text': 'in Greifweite'})

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
