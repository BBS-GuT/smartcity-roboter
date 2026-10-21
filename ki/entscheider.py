#!/usr/bin/env python3
# Entscheidungslogik der KI-Zentrale (ohne ROS, damit testbar).
#
# Die KI bekommt laufend, was die "Sinne" melden, und entscheidet:
#   fahren   - Linienfolger darf fahren
#   langsam  - fahren, aber langsamer (z. B. LiDAR meldet etwas, Kamera sieht nichts)
#   stopp    - anhalten
# Jede Entscheidung hat einen Grund (Text), der im Panel angezeigt wird.
#
# Rangfolge (wichtigstes zuerst):
#   1. LiDAR sehr nah (Notbremse)      -> stopp, OHNE KI-Pruefung (Eigenschutz geht vor)
#   2. KI bekommt keine Bilder / kein LiDAR -> stopp (wer nichts sieht, faehrt nicht)
#   3. Hindernis: LiDAR (im Pruefbereich) und/oder Tiefenkamera melden etwas im Weg -> ANHALTEN und
#      WEGRAEUMEN (ki/ablaeufe.py): Kamera schaut genau hin (mehrere Bilder, auch laenger, wenn die KI
#      langsam ist), dann:
#        Kamera sieht nichts, LiDAR auch nicht mehr -> weiter
#        nur LiDAR (Kamera sieht nichts)            -> langsam, naeher als lidar_halt -> stopp
#        Lebewesen/Fahrzeug, zu gross, am Rand, am Zebrastreifen, Arm nicht freigegeben -> warten, bis frei
#        sonst: Armbewegung ausrechnen (Kinematik), wegraeumen, PRUEFEN ob frei, erst dann weiter
#      Der LiDAR prueft nur den FAHRSCHLAUCH (Streifen entlang der Linie, siehe ki/zentrale.py).
#   4. KI sieht Person/Auto/... im Weg  -> stopp
#   5. Schild "Einfahrt verboten" (Einbahnstrasse) -> WENDEN
#   6. Zebrastreifen -> anhalten, umschauen, warten bis frei
#   7. Ampel rot/gelb -> stopp, bis gruen (oder Ampel nicht mehr zu sehen)
#   8. Stoppschild -> kurz halten, dann weiter
# Mehrschrittige Ablaeufe (Zebrastreifen, Wenden, Wegraeumen) stehen in ki/ablaeufe.py.

import random

from ablaeufe import Zebrastreifen, Wenden, Wegraeumen, Umschauen, Ausweichen, akteure_nah

STANDARD = {
    'notbremse_dist': 0.12,    # LiDAR naeher (m) -> sofort Stopp, ohne Rueckfrage
    'pruef_dist': 0.45,        # LiDAR naeher (m) -> KI prueft
    'lidar_halt': 0.20,        # LiDAR (im Fahrschlauch) naeher, aber nicht bestaetigt -> trotzdem halten
    'lidar_pflicht': True,     # ohne LiDAR-Daten nicht fahren
    'frei_zeit': 1.0,          # so lange muss der Weg frei sein, bis ein Hindernis-Stopp endet (s)
    'langsam_faktor': 0.5,     # Geschwindigkeit bei "langsam"
    'ki_max_alter': 1.5,       # aelteres KI-Bild = KI sieht nichts -> stopp (s)
    'ampel_bilder': 2,         # so viele KI-Bilder hintereinander dieselbe Farbe, bis sie gilt
    'schild_bilder': 2,
    'schild_warten': 3.0,      # am Stoppschild so lange halten (s)
    'schild_weg': 2.0,         # nach dem Halten: Schild erst wieder beachten, wenn es so lange
                               # nicht mehr zu sehen war (sonst haelt er beim Vorbeifahren nochmal)
    'arm_zeit': 1.5,           # so lange braucht der Arm fuer eine Bewegung (s)
    # Zebrastreifen
    'zebra_halt': 0.33,        # Zebrastreifen naeher als das (m, ab Robotermitte) -> anhalten
    'zebra_lidar': 0.5,        # ohne LiDAR-Punkte: etwas naeher als das (breit vorne) -> jemand kommt
    'zebra_seite': 0.28,       # LiDAR-Punkte bis so weit links/rechts der Fahrlinie gehoeren zum Zebrastreifen
    'zebra_tiefe': 0.25,       # ... und bis so weit hinter seiner vorderen Kante (m)
    'zebra_schauen': 0.8,      # so lange in jede Richtung schauen (s), nachdem der Arm steht
    'zebra_warten': 2.0,       # jemand da -> so lange warten, dann neu schauen (s)
    'zebra_weg': 2.0,          # nach dem Ueberqueren: erst wieder beachten, wenn so lange nicht gesehen
    # Einbahnstrasse
    'einfahrt_bilder': 2,      # so viele der letzten 4 Bilder "Einfahrt verboten" -> wenden
    'wenden_dreh': 0.8,        # Drehgeschwindigkeit beim Wenden (rad/s, + = links herum)
    'wenden_max_zeit': 7.0,    # laenger -> abbrechen und anhalten (180 Grad dauern bei 0,8 rad/s ca. 4 s)
    # Hindernis wegraeumen (Arm, Kinematik - keine eingelernten Greif-Posen noetig)
    'tiefe_halt': 0.35,        # Tiefenkamera sieht etwas im Weg naeher als das (m) -> anhalten, anschauen
    'anschauen_min': 1.0,      # so lange mindestens hinschauen (s) ...
    'anschauen_bilder': 5,     # ... und mindestens so viele neue KI-Bilder (langsame KI -> dauert laenger)
    'anschauen_max': 8.0,      # laenger nie (s)
    'lebewesen_weg': 3.0,      # Hindernis wegen Person/Tier nicht angefasst: so lange niemand mehr in Sicht (s)
                               # -> nochmal hinschauen (statt zu warten, bis der Weg frei ist)
    'kamera_min_sicht': 0.22,  # LiDAR meldet etwas naeher als das, Kamera sieht nichts -> etwas zurueck
    'sicht_zurueck': 0.10,     # ... hoechstens so weit (m)
    'aufheben_max_breite': 0.08,
    'aufheben_max_hoehe': 0.12,
    'aufheben_max_quer': 0.12,  # nur wegraeumen, was so nah an der Linie liegt (m) - am Rand steht vielleicht jemand.
                                # 12 statt 8 cm (Projektinhaber 21.10.): in Kurven lagen Hindernisse 9-14 cm neben der
                                # Linie, aber im Fahrschlauch (+-15 cm) - er wartete dann nur
    'zebra_kein_aufheben': 3.0,  # so lange nach einem gesehenen Zebrastreifen nichts anfassen (s): Fussgaenger!
    'greif_vor': 0.28,         # so weit vor der Robotermitte soll die Vorderkante liegen (m): Kamera sieht es
                               # noch sicher (RM02 20.10.: bei 27 cm gesehen, unter ~25 cm verloren). Reicht der
                               # Arm nicht hin, faehrt er danach blind naeher (naeher_max)
    'greif_toleranz': 0.02,    # +- so genau (m)
    'greif_seite': 0.025,      # weiter seitlich (m) -> seitlich hinfahren (sonst dreht der Arm und fasst schraeg;
                               # 6 cm waren zu grob, RM02 21.10.)
    'greif_winkel': 0.10,      # Roboter steht schraeger als das (rad, ca. 6 Grad) zur Strasse am Hindernis (Kurve)
                               # -> erst gerade drehen, dann greifen
    'blind_warten': 1.0,       # Hindernis beim Heranfahren so lange (s) nicht gesehen, laut Radzaehler in Greifweite
                               # -> mit der letzten Messung greifen (niedrige Gegenstaende verschwinden frueh)
    'kontrolle_zeit': 1.5,     # nach dem Wegraeumen so lange pruefen, ob der Weg frei ist (s)
    'kontrolle_bereich': 0.45,  # in diesem Abstand (m) darf die Tiefenkamera dann nichts mehr sehen
    'versuche': 4,             # so oft versuchen (jeder Fehlversuch wird gelernt), dann warten
    'naeher_max': 0.12,        # reicht der Arm nicht hin: hoechstens so weit blind naeher heranfahren (m)
    'naeher_tempo': 0.03,      # ... so schnell (m/s)
    'notbremse_abbruch': 5.0,  # Notbremse waehrend des Wegraeumens laenger als das (s) -> abbrechen
    # Weg lange versperrt (z. B. zwei Roboter stehen sich gegenueber): nach einer ZUFAELLIGEN Wartezeit
    # weicht einer aus (zurueck + wenden). Zufall, damit nicht beide gleichzeitig ausweichen.
    'ausweichen': False,       # AUS im Grundbetrieb (Zieldefinition GB-04: bei versperrtem Weg anhalten, nicht
                               # ausweichen; Gegenverkehr regelt die Infrastruktur). true = nach Wartezeit wenden
    'blockiert_min': 12.0,     # s
    'blockiert_max': 25.0,     # s
    'zurueck_strecke': 0.15,   # so weit zurueck (m), nur wenn hinten frei
    'zurueck_tempo': 0.05,     # m/s
    'hinten_frei': 0.25,       # LiDAR hinten mindestens so weit frei (m), sonst nicht zurueck
}



class Entscheider:
    def __init__(self, cfg=None, arm_erlaubt=False, posen=None, planer=None, rueckmeldung=None, planer_fehlt=''):
        self.c = dict(STANDARD)
        self.c.update(cfg or {})
        self.arm_freigabe = arm_erlaubt    # Einstellung: KI darf den Arm bewegen (Panel, Seite Arm)
        self.planer = planer               # rechnet die Armbewegung zum Wegraeumen aus (ki/zentrale.py), None = keiner
        self.rueckmeldung = rueckmeldung   # Ergebnis eines Greifversuchs -> Greif-Lernen (ki/zentrale.py)
        self.planer_fehlt = planer_fehlt   # warum es keinen Planer gibt (Text fuers Panel)
        self.notbremse_seit = None
        self.fahrt_aktiv = True            # faehrt das Fahrprogramm gerade? (setzt die Zentrale; TEST/aus = False)
        self.posen = posen or {}
        # Ablaeufe
        self.ablauf = None
        self.zebra_gesperrt, self.zebra_zuletzt = False, 0.0
        self.zebra_merk = None        # zuletzt gesehener Zebrastreifen: (Abstand, Strecke dabei, Zeit) - falls die Kamera
                                      # ihn danach nicht mehr sieht (zu nah, KI langsam, anderer Ablauf lief gerade)
        self.einfahrt_n, self.einfahrt_gesperrt_bis = 0, 0.0
        self.einfahrt_bilder = []     # gesehen ja/nein in den letzten Bildern
        self.aufheben_gesperrt, self.weg_frei_seit = False, None
        self.umschauen_wunsch = None  # Zeit, zu der jemand (Kartograf/Panel) Umschauen gewuenscht hat
        self.fehler_halt = None       # Manoever fehlgeschlagen -> bleibt stehen bis STOPP + neuer START
        self.start_quittung = None    # Zeit eines ausdruecklichen START (Panel -> /ki/kommando 'start')
        self.blockiert_seit, self.blockiert_grenze = None, 0.0
        self.ereignisse = []          # (zeit, text, art) art: stopp | fahren | info
        self.letzte_bild_nr = -1
        # Ampel
        self.ampel_halt = False
        self.ampel_kand, self.ampel_n = None, 0
        self.ampel_zuletzt_rot = 0.0
        # Stoppschild
        self.schild_n = 0
        self.schild_bis = 0.0
        self.schild_gesperrt = False
        self.schild_zuletzt = 0.0
        # LiDAR / Hindernis
        self.hindernis_bis = 0.0
        self.meldung_seit = None      # seit wann meldet der LiDAR etwas im Pruefbereich
        self.geprueft_frei = False    # Kamera hat genau hingeschaut: sieht nichts (nur LiDAR meldet etwas)
        self.bestaetigt = None        # Kamera hat es gesehen, wird nicht angefasst (Grund) -> warten bis frei
        self.bestaetigt_lebewesen = False  # ... weil eine Person/ein Tier in Sicht war -> nochmal schauen, wenn weg
        self.hindernis_merk = None    # (Abstand m, Strecke dabei, seitdem vorgefahren): von der Kamera gesehen, nicht weggeraeumt. Ist es
                                      # zu nah fuer die Kamera, gilt der Weg NICHT als frei (sonst faehrt er drueber)
        self.lebewesen_zuletzt = 0.0  # wann die Kamera-KI zuletzt eine Person/ein Tier/ein Fahrzeug gesehen hat
        self.lebewesen_bild = float('-inf')   # ... Aufnahmezeit (bild_zeit) dieses Bildes
        # Arm
        self.arm_zurueck_noetig = False  # Arm steht evtl. nicht in Fahrstellung
        self.arm_zurueck_wegraeumen = False  # ... wegen eines Wegraeumens (dann erst zurueck, wenn niemand in Sicht ist)
        self.arm_warten_bis = 0.0
        self.letzte_aktion = None
        self.letzter_grund = None
        self.jetzt = 0.0

    @property
    def arm_erlaubt(self):
        """Arm nur bewegen, wenn freigegeben UND das Fahrprogramm wirklich faehrt (nicht im TEST, nicht nach STOPP)."""
        return self.arm_freigabe and self.fahrt_aktiv

    def kommando(self, jetzt, text):
        """Wunsch von aussen (Topic /ki/kommando). 'umschauen' = bei naechster Gelegenheit kurz anhalten
        und links/rechts schauen (fuer die Karte). Rueckgabe: Antworttext."""
        if text == 'umschauen':
            posen_da = all(self.posen.get(p) for p in ('blick_links', 'blick_rechts', 'fahrstellung'))
            if not (self.arm_freigabe and posen_da):
                return 'Umschauen geht nicht: Arm fuer die KI nicht freigegeben oder Posen fehlen'
            if not self.fahrt_aktiv:
                return 'Umschauen geht nur waehrend der Fahrt (START), nicht im TEST'
            self.umschauen_wunsch = jetzt
            return 'Umschauen vorgemerkt'
        if text == 'start':
            # Ausdruecklicher START am Panel (nicht: Status des Linienfolgers kam nach kurzer Pause wieder).
            # Wird angewendet, sobald das Fahrprogramm wirklich faehrt.
            self.start_quittung = jetzt
            return 'START quittiert'
        return f'unbekanntes Kommando: {text}'

    def _ereignis(self, jetzt, text, art='info'):
        self.ereignisse.append((jetzt, text, art))

    # ------------------------------------------------------------------ #
    def update(self, jetzt, w):
        """w = Wahrnehmung (dict):
          bild_nr, bild_zeit   Nummer/Zeit des zuletzt von der KI ausgewerteten Bildes
          objekte              [{name, sicher, im_weg}, ...] (Kamera-KI)
          ampel, ampel_quelle  'rot' | 'gelb' | 'gruen' | None
          stoppschild, schild_quelle   True/False
          lidar                naechster Abstand vorne (m), inf = frei, None = keine Daten
          tiefe_hindernis      True/False, None = Tiefenkamera nicht bereit
          lidar_breit          wie lidar, aber breiter Bereich vorne (Zebrastreifen)
          objekt               naechster Gegenstand {vor, seite, breite, hoehe} (Tiefenkamera/LiDAR)
          zebra                None | {abstand} ; einfahrt_verboten True/False
          gier                 aufsummierte Drehung (rad, IMU) ; linie {kamera, quer} vom Linienfolger
        Rueckgabe: {'aktion', 'faktor', 'grund', 'arm', 'manoever'}
        """
        self.jetzt = jetzt
        if not self.arm_freigabe and self.ablauf is not None and self.ablauf.braucht_arm:
            # Schalter "KI darf den Arm bewegen" waehrend eines Ablaufs ausgeschaltet: wie STOPP behandeln,
            # Arm faehrt zurueck in die Fahrstellung, bevor wieder gefahren wird
            self._ereignis(jetzt, f'{self.ablauf.name}: abgebrochen (Arm fuer die KI ausgeschaltet)', 'info')
            self._ablauf_abbrechen()
        if self.start_quittung is not None and jetzt - self.start_quittung > 15.0:
            self.start_quittung = None   # Fahrprogramm ist nach dem START nicht angelaufen
        if self.start_quittung is not None and self.fahrt_aktiv:
            # Ausdruecklicher START (Panel): quittiert einen Manoever-Fehler und ein fehlgeschlagenes Wegraeumen.
            # Sonst versucht er es vor demselben Hindernis nie wieder (nur wenn der Weg einmal frei war).
            # NUR so - ein Statusausfall und dessen Wiederkehr (fahrt_aktiv kurz False) quittiert nichts.
            self.start_quittung = None
            if self.fehler_halt or self.aufheben_gesperrt or self.bestaetigt:
                self._ereignis(jetzt, 'START quittiert: Fehler/Hindernis wird neu geprueft', 'info')
            if self.ampel_halt:
                # Bewusste Freigabe durch den Bediener (z. B. Gruen nicht erkennbar, Ampel ausser Sicht).
                # Ohne START bleibt Rot stehen (kein Timeout, B1). Sieht er gleich wieder Rot, haelt er wieder.
                self._ereignis(jetzt, 'START quittiert: Rot-Halt aufgehoben (Bediener)', 'info')
                self.ampel_halt = False
                self.ampel_kand, self.ampel_n = None, 0
            self.fehler_halt = None
            self.arm_zurueck_wegraeumen = False      # Bediener hat geschaut: Arm darf zurueck
            self.aufheben_gesperrt, self.bestaetigt, self.bestaetigt_lebewesen = False, None, False
            self.hindernis_merk = None
            self.meldung_seit, self.geprueft_frei = None, False
        if not self.fahrt_aktiv:
            # STOPP gedrueckt oder nur TEST: nichts am Arm bewegen, laufende Arm-Ablaeufe abbrechen.
            # Der Arm bleibt, wo er ist; beim naechsten START faehrt er zuerst in die Fahrstellung.
            if self.ablauf is not None and self.ablauf.braucht_arm:
                self._ereignis(jetzt, f'{self.ablauf.name}: abgebrochen (Fahrprogramm aus)', 'info')
                self._ablauf_abbrechen()
        neues_bild = w.get('bild_nr', -1) != self.letzte_bild_nr
        if neues_bild:
            self.letzte_bild_nr = w.get('bild_nr', -1)
            if akteure_nah(w):                 # nur nahe zaehlen (Hintergrund haelt das Wegraeumen nicht auf)
                self.lebewesen_zuletzt = jetzt
                self.lebewesen_bild = w.get('bild_zeit', 0.0)
            if self.ablauf is None and self.arm_in_fahrstellung:
                # Ampel/Schild nur zaehlen, wenn die Kamera normal nach vorne schaut (nicht beim
                # Umschauen oder Greifen). Sonst liefe z. B. die Haltezeit am Stoppschild waehrend
                # des Aufhebens ab. Nach dem Ablauf sieht die Kamera Ampel/Schild ja wieder.
                self._ampel_bild(jetzt, w)
                self._schild_bild(jetzt, w)
            # Treffer in den letzten 4 Bildern zaehlen (nicht nur direkt hintereinander): ist die KI langsam
            # und ein Bild dazwischen unscharf, faehrt er sonst am Schild vorbei in die Einbahnstrasse
            self.einfahrt_bilder = (self.einfahrt_bilder + [bool(w.get('einfahrt_verboten'))])[-4:]
            self.einfahrt_n = sum(self.einfahrt_bilder)
            if w.get('zebra'):
                self.zebra_zuletzt = jetzt
                if not self.zebra_gesperrt:
                    self.zebra_merk = (w['zebra']['abstand'], w.get('strecke'), jetzt)
        if self.zebra_gesperrt and self.ablauf is None and jetzt - self.zebra_zuletzt > self.c['zebra_weg']:
            self.zebra_gesperrt = False  # ueber den Zebrastreifen drueber
        # Kamera (am Arm) schaut gleich wieder nach vorne, faehrt aber noch dahin? Dann zaehlt ein Ablauf die Bilder
        # noch nicht (Zentrale misst dann keine Tiefe). Ohne Fahrt (TEST/STOPP) faehrt der Arm gar nicht zurueck.
        arm_kommt = (self.arm_zurueck_noetig and self.fahrt_aktiv) or jetzt < self.arm_warten_bis
        w = dict(w, neues_bild=neues_bild, kamera_vorne=not arm_kommt)

        befehl = self._entscheide(jetzt, w)
        befehl = self._blockade(jetzt, w, befehl)
        # Arm zuerst zurueck in Fahrstellung, bevor wieder gefahren wird
        # (nicht waehrend einer Notbremse: dann ist etwas sehr nah am Roboter)
        notbremse = befehl['grund'].startswith('NOTBREMSE')
        halten = self._akteur_haelt_arm(jetzt, w) if self.arm_zurueck_noetig and self.fahrt_aktiv else None
        if halten and not notbremse:
            # Arm kommt vom Wegraeumen und eine Person/ein Tier/ein Fahrzeug ist in Sicht (oder es fehlen frische Bilder,
            # dann ist nichts geprueft): Arm bleibt, wo er ist, und der Roboter steht
            befehl = self._b('stopp', f'Arm muss zurueck in Fahrstellung, aber {halten} -> warte')
        elif self.arm_zurueck_noetig and self.fahrt_aktiv and not notbremse:
            self.arm_zurueck_noetig = False
            self.arm_zurueck_wegraeumen = False
            self.arm_warten_bis = jetzt + self.c['arm_zeit']
            befehl = self._b('stopp', 'Arm faehrt zurueck in Fahrstellung', arm='fahrstellung')
        elif jetzt < self.arm_warten_bis and befehl['aktion'] != 'stopp':
            befehl = self._b('stopp', 'Arm faehrt zurueck in Fahrstellung')
        if not self.fahrt_aktiv and befehl.get('arm'):
            befehl = dict(befehl, arm=None)    # ohne fahrendes Fahrprogramm bewegt die KI den Arm nie
        if befehl['aktion'] != self.letzte_aktion or befehl['grund'] != self.letzter_grund:
            if befehl['aktion'] != self.letzte_aktion:
                art = befehl['aktion'] if befehl['aktion'] in ('stopp', 'langsam') else 'fahren'
                self._ereignis(jetzt, f"{befehl['aktion'].upper()}: {befehl['grund']}", art)
            self.letzte_aktion, self.letzter_grund = befehl['aktion'], befehl['grund']
        return befehl

    # ------------------------------------------------------------------ #
    def _ampel_bild(self, jetzt, w):
        farbe = w.get('ampel')
        if farbe == self.ampel_kand:
            self.ampel_n += 1
        else:
            self.ampel_kand, self.ampel_n = farbe, 1
        if self.ampel_n < self.c['ampel_bilder']:
            return
        quelle = w.get('ampel_quelle') or 'KI'
        if farbe in ('rot', 'gelb'):
            self.ampel_zuletzt_rot = jetzt
            if not self.ampel_halt:
                self.ampel_halt = True
                self._ereignis(jetzt, f'{farbe.capitalize()}e Ampel erkannt ({quelle})', 'stopp')
        elif farbe == 'gruen' and self.ampel_halt:
            self.ampel_halt = False
            self._ereignis(jetzt, f'Gruene Ampel erkannt ({quelle}) -> darf weiter', 'fahren')

    def _schild_bild(self, jetzt, w):
        if w.get('stoppschild'):
            self.schild_zuletzt = jetzt
        elif self.schild_gesperrt and jetzt >= self.schild_bis and jetzt - self.schild_zuletzt > self.c['schild_weg']:
            self.schild_gesperrt = False  # am Schild vorbei
        if not w.get('stoppschild') or self.schild_gesperrt:
            self.schild_n = 0
            return
        self.schild_n += 1
        if self.schild_n >= self.c['schild_bilder']:
            self.schild_n = 0
            self.schild_gesperrt = True
            self.schild_bis = jetzt + self.c['schild_warten']
            self._ereignis(jetzt, f"Stoppschild erkannt ({w.get('schild_quelle') or 'KI'})", 'stopp')

    # ------------------------------------------------------------------ #
    def _entscheide(self, jetzt, w):
        c = self.c
        d = w.get('lidar')
        ki_frisch = jetzt - w.get('bild_zeit', 0.0) <= c['ki_max_alter']
        im_weg = [o['name'] for o in w.get('objekte', []) if o.get('im_weg')]

        # 1. Notbremse
        if d is not None and d < c['notbremse_dist']:
            self.hindernis_bis = jetzt + c['frei_zeit']
            self.notbremse_seit = self.notbremse_seit or jetzt
            a = self.ablauf
            if a is not None and a.name == 'wegraeumen' and jetzt - self.notbremse_seit > c['notbremse_abbruch']:
                # Wegraeumen pausiert waehrend der Notbremse (kein neuer Arm-Befehl). Dauert es zu lange: abbrechen.
                # Der Arm faehrt erst nach der Notbremse zurueck (dann ist nichts mehr direkt am Roboter).
                self._ereignis(jetzt, 'Wegraeumen abgebrochen: Notbremse dauert zu lange', 'stopp')
                self._ablauf_abbrechen(nur_wenn_bewegt=True)
                self.aufheben_gesperrt = True
                self.bestaetigt, self.bestaetigt_lebewesen = 'Wegraeumen abgebrochen (Notbremse)', False
            return self._b('stopp', f'NOTBREMSE: LiDAR {d * 100:.0f} cm (ohne KI-Pruefung)')
        self.notbremse_seit = None
        if self.fehler_halt:
            return self._b('stopp', self.fehler_halt + ' -> bitte pruefen, dann STOPP und START')
        # 2. Blind?
        if d is None and c['lidar_pflicht']:
            return self._b('stopp', 'Kein LiDAR -> fahre nicht blind')
        if not ki_frisch:
            return self._b('stopp', 'KI bekommt keine Kamerabilder')

        # Laufender Ablauf (Zebrastreifen, Wenden, Wegraeumen) hat Vorrang
        if self.ablauf is not None:
            b = self.ablauf.schritt(jetzt, w)
            for text, art in self.ablauf.ereignisse:
                self._ereignis(jetzt, text, art)
            self.ablauf.ereignisse.clear()
            if b is not None:
                return self._mit_faktor(b)
            self._ablauf_ende(jetzt)
            if self.fehler_halt:          # z. B. Wenden fehlgeschlagen: schon in DIESEM Zyklus halten
                return self._b('stopp', self.fehler_halt + ' -> bitte pruefen, dann STOPP und START')

        obj = w.get('objekt')
        # Schon bestaetigt (wartet davor): 10 cm Spiel. Sonst lag es knapp hinter tiefe_halt (37 cm), er fuhr wieder
        # an und blieb dann an der gemerkten Stelle mit "wegnehmen, dann STOPP und START" stehen (RM02 21.10.)
        halt = c['tiefe_halt'] + (0.10 if self.bestaetigt else 0.0)
        tiefe_im_weg = obj is not None and obj.get('quelle') == 'tiefe' and obj['vor'] < halt
        im_pruefbereich = d is not None and d < c['pruef_dist']
        merk_rest = self._merk_rest(w)
        if merk_rest is not None and not (tiefe_im_weg or im_pruefbereich) and merk_rest < self._merk_sicht():
            # Vorhin gesehen, nicht weggeraeumt, jetzt zu nah fuer Kamera (und unter dem LiDAR): NICHT frei
            self.weg_frei_seit = None
            return self._b('stopp', f'Hindernis {max(0.0, merk_rest) * 100:.0f} cm voraus, zu nah fuer die Kamera '
                                    '-> warte (wegnehmen, dann STOPP und START)')
        if not (tiefe_im_weg or im_pruefbereich):
            self.weg_frei_seit = self.weg_frei_seit or jetzt
            if jetzt - self.weg_frei_seit > c['frei_zeit']:
                if self.meldung_seit is not None or self.bestaetigt:
                    self._ereignis(jetzt, 'Weg ist wieder frei', 'fahren')
                self.meldung_seit, self.geprueft_frei, self.bestaetigt = None, False, None
                self.hindernis_merk = None       # Kamera sieht die Stelle und sie ist frei
            if jetzt - self.weg_frei_seit > 2.0:
                self.aufheben_gesperrt = False
            if self.bestaetigt:
                # wartet vor einem bestaetigten Hindernis: erst weiter, wenn es frei_zeit lang weg ist (ein einzelnes
                # Bild ohne Treffer liess ihn sonst schon anfahren)
                return self._b('stopp', f'{self.bestaetigt}: Weg frei? schaue noch kurz hin')
        else:
            self.weg_frei_seit = None

        # 3. Hindernis (LiDAR und/oder Tiefenkamera): anhalten, Kamera schaut genau hin, ggf. wegraeumen
        if tiefe_im_weg or im_pruefbereich:
            if self.meldung_seit is None:
                self.meldung_seit = jetzt
                wer = ' + '.join(n for n, an in (('LiDAR', im_pruefbereich), ('Tiefenkamera', tiefe_im_weg)) if an)
                abst = d if im_pruefbereich else obj['vor']
                self._ereignis(jetzt, f'{wer}: etwas {abst * 100:.0f} cm voraus -> anhalten, Kamera prueft', 'stopp')
            if im_weg:
                self.hindernis_bis = jetzt + c['frei_zeit']
                return self._b('stopp', 'KI sieht im Weg: ' + ', '.join(im_weg))
            if self.bestaetigt and self.bestaetigt_lebewesen and jetzt - self.lebewesen_zuletzt > c['lebewesen_weg']:
                # Wegen einer Person (z. B. Hand beim Hinlegen) nicht angefasst. Die ist jetzt weg, das Hindernis
                # noch da: nochmal genau hinschauen statt ewig zu warten
                self._ereignis(jetzt, f'{self.bestaetigt}: niemand mehr in Sicht -> schaue nochmal hin', 'info')
                self.bestaetigt, self.bestaetigt_lebewesen = None, False
            if self.bestaetigt:
                return self._b('stopp', f'{self.bestaetigt} -> warte, bis der Weg frei ist')
            if tiefe_im_weg and self.geprueft_frei:
                # vorhin nur der LiDAR (Kamera sah nichts), jetzt sieht die Tiefenkamera etwas: neu anschauen
                self._ereignis(jetzt, 'Tiefenkamera sieht jetzt etwas -> schaue nochmal hin', 'info')
                self.geprueft_frei = False
            if not self.geprueft_frei:
                planer = self.planer if self._darf_arm() else None
                return self._ablauf_start(jetzt, Wegraeumen(jetzt, c, planer, self._darf_greifen, self.rueckmeldung,
                                                            self.warum_kein_arm(),
                                                            pruefblick=bool(self.posen.get('pruefblick'))))
            # Kamera hat hingeschaut und sieht nichts, nur der LiDAR meldet etwas (z. B. Hauskante in der Kurve)
            if d is not None and d < c['lidar_halt']:
                return self._b('stopp', f'LiDAR: etwas {d * 100:.0f} cm im Weg, Kamera sieht nichts -> halte')
            return self._b('langsam', 'LiDAR-Meldung, Kamera sieht nichts -> langsam', c['langsam_faktor'])

        if jetzt < self.hindernis_bis:
            return self._b('stopp', 'Hindernis war im Weg -> warte, bis der Weg frei ist')

        # 4. KI sieht etwas im Weg (auch ohne LiDAR, z. B. weiter weg oder unter der LiDAR-Scheibe)
        if im_weg:
            return self._b('stopp', 'KI sieht im Weg: ' + ', '.join(im_weg))
        # 5. Einbahnstrasse von der falschen Seite -> wenden
        if self.einfahrt_n >= c['einfahrt_bilder'] and jetzt >= self.einfahrt_gesperrt_bis:
            self.einfahrt_n, self.einfahrt_bilder = 0, []
            self._ereignis(jetzt, 'Schild "Einfahrt verboten" (Einbahnstrasse) -> wende', 'stopp')
            self.zebra_merk = None       # nach dem Wenden liegt er nicht mehr vor ihm
            return self._ablauf_start(jetzt, Wenden(jetzt, c, w.get('gier', 0.0)))
        # 6. Zebrastreifen -> anhalten und umschauen
        z = w.get('zebra')
        if not z and self.zebra_merk and not self.zebra_gesperrt:
            # Kamera sieht ihn gerade nicht mehr, vorhin aber schon: mit der gefahrenen Strecke weiterrechnen.
            # Sonst faehrt er drueber, wenn er ihn waehrend eines anderen Ablaufs (z. B. Hindernis anschauen)
            # gesehen hat und er danach zu nah fuer die Kamera ist.
            a, s0, t0 = self.zebra_merk
            s1 = w.get('strecke')
            rest = a - (s1 - s0) if s1 is not None and s0 is not None else a
            if rest < -0.3 or jetzt - t0 > 30.0:
                self.zebra_merk = None              # laengst drueber / zu alt
            elif rest <= c['zebra_halt']:
                z = {'abstand': max(0.05, rest)}
        if z and not self.zebra_gesperrt and z['abstand'] <= c['zebra_halt']:
            self.zebra_merk = None
            self._ereignis(jetzt, f"Zebrastreifen {z['abstand'] * 100:.0f} cm voraus -> anhalten, umschauen", 'stopp')
            posen = self.posen if self.arm_erlaubt else {}
            return self._ablauf_start(jetzt, Zebrastreifen(jetzt, c, posen, z['abstand']))
        # Umschauen (Wunsch von Kartograf/Panel): nur wenn sonst nichts los ist, Wunsch gilt 20 s
        if self.umschauen_wunsch is not None:
            if jetzt - self.umschauen_wunsch < 20.0 and not self.ampel_halt and jetzt >= self.schild_bis:
                self.umschauen_wunsch = None
                self._ereignis(jetzt, 'Schaue mich fuer die Karte um', 'info')
                return self._ablauf_start(jetzt, Umschauen(jetzt, c, 'Umschauen fuer die Karte'))
            if jetzt - self.umschauen_wunsch >= 20.0:
                self.umschauen_wunsch = None
        # 5./6. Verkehrsregeln
        if self.ampel_halt:
            if jetzt - self.ampel_zuletzt_rot > 4.0:
                return self._b('stopp', 'Rote Ampel nicht mehr zu sehen -> warte auf Gruen (oder STOPP, dann START)')
            return self._b('stopp', 'Rote Ampel -> warte auf Gruen')
        if jetzt < self.schild_bis:
            return self._b('stopp', f'Stoppschild -> halte noch {self.schild_bis - jetzt:.0f} s')
        return self._b('fahren', 'Weg frei')

    BLOCKADE_GRUENDE = ('NOTBREMSE', 'Hindernis', 'LiDAR: etwas', 'KI sieht im Weg', 'Wegraeumen hat nicht')

    def _blockade(self, jetzt, w, befehl):
        """Steht er schon lange vor einem Hindernis, weicht er nach zufaelliger Zeit aus."""
        blockiert = (befehl['aktion'] == 'stopp' and self.ablauf is None
                     and befehl['grund'].startswith(self.BLOCKADE_GRUENDE))
        if not blockiert or not self.fahrt_aktiv or not self.c['ausweichen']:
            self.blockiert_seit = None
            return befehl
        if self.blockiert_seit is None:
            self.blockiert_seit = jetzt
            self.blockiert_grenze = random.uniform(self.c['blockiert_min'], self.c['blockiert_max'])
        if jetzt - self.blockiert_seit < self.blockiert_grenze:
            return befehl
        self.blockiert_seit = None
        self._ereignis(jetzt, f'Weg seit {self.blockiert_grenze:.0f} s versperrt (vielleicht ein anderer Roboter) '
                              '-> weiche aus', 'stopp')
        self.hindernis_bis = 0.0
        return self._ablauf_start(jetzt, Ausweichen(jetzt, self.c, w.get('gier', 0.0)))

    # ------------------------------------------------------------------ #
    # Ablaeufe
    def _ablauf_start(self, jetzt, ablauf):
        self.ablauf = ablauf
        b = ablauf.schritt(jetzt, {})
        for text, art in ablauf.ereignisse:
            self._ereignis(jetzt, text, art)
        ablauf.ereignisse.clear()
        return self._mit_faktor(b) if b else self._b('stopp', ablauf.name)

    def _ablauf_abbrechen(self, nur_wenn_bewegt=False):
        """Laufenden Ablauf verwerfen (Arm ausgeschaltet, STOPP/Statusausfall, Notbremse zu lange). Beim Wegraeumen
        bleibt die Stelle gemerkt, an der die Kamera das Hindernis zuletzt gesehen hat: Fehlende neue Treffer sind
        danach keine Freisicht (sonst faehrt er nach der Armrueckkehr drueber). Frei erst wie sonst auch: Kamera sieht
        die Stelle frei, oder ausdruecklicher START."""
        a, self.ablauf = self.ablauf, None
        if a.arm_bewegt or (a.name == 'wegraeumen' and not nur_wenn_bewegt):
            self.arm_zurueck_noetig = True
        if a.arm_bewegt and a.name == 'wegraeumen':
            self.arm_zurueck_wegraeumen = True     # Arm steht wirklich woanders: erst zurueck, wenn niemand in Sicht
        if a.name == 'wegraeumen' and a.merk is not None:
            self.hindernis_merk = a.merk

    def _akteur_haelt_arm(self, jetzt, w):
        """Armrueckkehr nach einem Wegraeumen zurueckhalten? Grund (Text) oder None. Frei ist es erst, wenn ein FRISCHES
        Bild mindestens 2 s nach der letzten Sichtung niemanden mehr zeigt - ausbleibende Bilder sind keine Freipruefung."""
        if not self.arm_zurueck_wegraeumen:
            return None
        bild = w.get('bild_zeit', 0.0)
        if jetzt - bild > self.c['ki_max_alter']:
            return 'KI liefert keine frischen Bilder'
        if bild - self.lebewesen_bild < 2.0 or jetzt - self.lebewesen_zuletzt < 2.0:
            return 'jemand ist in Sicht'
        return None

    def _ablauf_ende(self, jetzt):
        a = self.ablauf
        self.ablauf = None
        if a.arm_bewegt:
            self.arm_zurueck_noetig = True
            self.arm_zurueck_wegraeumen = self.arm_zurueck_wegraeumen or a.name == 'wegraeumen'
        if a.name == 'zebra':
            self.zebra_gesperrt = True
            self.zebra_merk = None
            self.zebra_zuletzt = jetzt   # beim Umschauen sah die Kamera den Zebrastreifen nicht
        elif a.name in ('wenden', 'ausweichen'):
            self.einfahrt_gesperrt_bis = jetzt + 6.0
            self.einfahrt_n, self.einfahrt_bilder = 0, []
            if a.ergebnis != 'ok':
                # NICHT einfach weiterfahren (sonst in die Einbahnstrasse oder ins Hindernis)
                self.fehler_halt = 'Wenden hat nicht geklappt'
        elif a.name == 'wegraeumen':
            self.hindernis_bis = 0.0
            # nicht weggeraeumt (warten, Fehler, ...): Stelle merken, frei erst, wenn die Kamera sie frei sieht
            self.hindernis_merk = a.merk if a.ergebnis != 'frei' else None
            if a.ergebnis == 'unbestaetigt':
                self.geprueft_frei = True
            elif a.ergebnis == 'bestaetigt':
                self.bestaetigt = f'Hindernis ist {a.lebewesen}' if a.lebewesen else 'Hindernis'
                self.bestaetigt_lebewesen = bool(a.lebewesen)
            elif a.ergebnis == 'fehler':
                self.aufheben_gesperrt = True
                self.bestaetigt, self.bestaetigt_lebewesen = 'Wegraeumen hat nicht geklappt', False
            else:                        # frei: Fehlalarm oder weggeraeumt UND geprueft
                self.meldung_seit = None

    def _merk_sicht(self):
        """Ab diesem Abstand sieht die Kamera die gemerkte Stelle sicher: so weit wie bei der letzten Messung, bei
        der sie es WIRKLICH gesehen hat (1 cm Spiel fuer Messrauschen). Ist er naeher dran, gilt 'Kamera sieht
        nichts' nicht als frei - dort hat sie es (RM02 20.10.) schon einmal verloren."""
        return max(self.c['kamera_min_sicht'], self.hindernis_merk[0] - 0.01)

    def _merk_rest(self, w):
        """Wie weit liegt das gemerkte Hindernis noch voraus (m)? None = keins (mehr)."""
        if self.hindernis_merk is None:
            return None
        vor, s0, vorgefahren = self.hindernis_merk
        s1 = w.get('strecke')
        if s0 is not None and s1 is not None:
            rest = vor - (s1 - s0)
        else:
            # ohne Radzaehler: ist er seit der Messung vorwaerts gefahren, ist unbekannt wie weit -> direkt davor
            rest = 0.0 if vorgefahren else vor
        if rest < -0.25:              # weit dahinter: laengst vorbei
            self.hindernis_merk = None
            return None
        return rest

    def _darf_arm(self):
        return self.arm_erlaubt and self.planer is not None and not self.aufheben_gesperrt

    def warum_kein_arm(self):
        """Klartext, warum die KI gerade NICHTS wegraeumen wuerde (leer = sie darf)."""
        if not self.arm_freigabe:
            return 'Arm fuer die KI ausgeschaltet (Panel -> Arm -> "KI darf den Arm bewegen")'
        if not self.fahrt_aktiv:
            return 'Fahrprogramm faehrt nicht (nur TEST oder STOPP) - Arm nur bei START'
        if self.planer is None:
            return self.planer_fehlt or 'keine Kinematik zum Ausrechnen der Armbewegung'
        if self.aufheben_gesperrt:
            return 'letzter Versuch hat nicht geklappt, erst wenn der Weg einmal frei war wieder'
        return ''

    def _darf_greifen(self, obj, w):
        """None = darf wegraeumen, sonst der Grund, warum nicht (dann wartet er)."""
        if self.zebra_gesperrt or self.jetzt - self.zebra_zuletzt < self.c['zebra_kein_aufheben']:
            return 'am Zebrastreifen (Fussgaenger!) nichts anfassen'
        if obj.get('quer') is not None and obj['quer'] > self.c['aufheben_max_quer']:
            return f"liegt am Rand ({obj['quer'] * 100:.0f} cm neben der Linie)"
        if obj['breite'] > self.c['aufheben_max_breite'] or obj.get('hoehe', 0) > self.c['aufheben_max_hoehe']:
            return 'zu gross fuer den Greifer'
        return None

    @staticmethod
    def _mit_faktor(b):
        b = dict(b)
        b.setdefault('faktor', 0.0)
        return b

    @property
    def arm_in_fahrstellung(self):
        """Schaut die Kamera (am Arm) normal nach vorne? Nur dann stimmen Draufsicht, Linie und
        Tiefenkamera-Bodenmodell. Waehrend der Arm zurueckfaehrt (arm_warten_bis) noch nicht."""
        a = self.ablauf                    # einmal lesen: die KI fragt aus einem anderen Thread
        return (not self.arm_zurueck_noetig and self.jetzt >= self.arm_warten_bis
                and not (a is not None and a.arm_bewegt))

    @staticmethod
    def _b(aktion, grund, faktor=None, arm=None):
        if faktor is None:
            faktor = 0.0 if aktion == 'stopp' else 1.0
        return {'aktion': aktion, 'faktor': round(float(faktor), 2), 'grund': grund, 'arm': arm, 'manoever': None}
