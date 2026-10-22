#!/usr/bin/env python3
# Fahr-Gehirn (ohne ROS, damit testbar): verbindet Fahrplan, Blinker, Messung und Lernen.
#
# Zustand nach aussen (spaeter fuer Panel / KI-Zentrale / Wechsel mit dem Arm-Gehirn):
#   'gestoppt'  faehrt nicht, laufende Runde wird nicht gewertet
#   'faehrt'    faehrt nach Fahrplan und misst
#   'pausiert'  steht, alles bleibt erhalten (Runde, offene Kreuzung, Fahrplan); 'weiter' macht genau dort weiter.
#               Der ROS-Knoten gibt /cmd_vel waehrenddessen frei (ein anderes Gehirn darf fahren).
# Kommandos: start | stopp | pause | weiter | fahrplan <nr> (Roboter wurde umgesetzt, naechste Kreuzung = Plan-Nr.)
#
# Ablauf an einer Kreuzung:
#   1. Der Linienfolger sieht Aeste (linie.py) und fragt kreuzung_waehlen(): Ast nach Fahrplan, Blinker an.
#   2. takt() misst, bis er 'messweg' m weiter ist: wie weit hat er sich gedreht? -> gefahrene Richtung.
#   3. Ergebnis in logs/fahrgehirn/kreuzungen.csv, Blinker aus, Fahrplan weiter.
#   Ist der ganze Plan durch, ist eine Runde fertig: runden.csv, Lernen, Lernstand speichern.
import math
import statistics
import threading
import time

import messung as m
from fahrplan import Fahrplan, richtung_aus_ast

ZUSTAENDE = ('gestoppt', 'faehrt', 'pausiert')
DREHBEGINN_GRAD = 15.0     # ab so viel Drehung seit der Wahl gilt: er biegt ab (fuer den Blink-Vorlauf)
HILFE_NACH = 10.0          # so lange (s) ohne Linie stehen -> 'hilfe_noetig' im Zustand (er faehrt nie blind los)


class FahrGehirn:
    def __init__(self, plan, lernen, protokoll, blinker, log=print, messweg=0.7, wahl_warten=5, lernen_an=True):
        self.lernen, self.protokoll, self.blinker, self.log = lernen, protokoll, blinker, log
        self.plan = Fahrplan(plan, lernen.stand.get('fahrplan_index', 0))
        self.messweg = messweg          # so weit nach der Wahl wird die Drehung gemessen (m)
        self.wahl_warten = wahl_warten  # so viele Bilder auf den Wunsch-Ast warten, dann den naechstbesten nehmen
        self.lernen_an = lernen_an      # False = nur messen, Parameter bleiben fest
        self.lock = threading.RLock()
        self.zustand = 'gestoppt'
        self.zustand_seit = time.time()
        self.runde = None               # RundenMessung oder None
        self.kreuzung = None            # KreuzungsMessung der Kreuzung, die gerade durchfahren wird
        self.drehbeginn = None
        self.weg = 0.0                  # gesamt gefahrene Strecke (m)
        self.weg_letzte = None          # Strecke bei der letzten Kreuzung (fuer "nicht erkannt" vermuten)
        self.linie_weg_vorher = False
        self.meldung = ''               # letzte wichtige Meldung (Lernen) fuer die Anzeige
        self.parameter_neu = True       # Knoten soll die Parameter (neu) uebernehmen
        self._gier = 0.0                # letzte bekannte eigene Drehung (rad)
        self.ohne_linie_seit = None     # seit wann steht er ohne Linie (Suche vorbei)
        self.hilfe_noetig = False

    # ---------------- Schnittstelle nach aussen ----------------
    def kommando(self, text, jetzt=None):
        """start | stopp | pause | weiter | fahrplan <nr>. Rueckgabe: Antwort (Text)."""
        jetzt = time.time() if jetzt is None else jetzt
        teile = text.strip().lower().split()
        if not teile:
            return 'leeres Kommando'
        with self.lock:
            k = teile[0]
            if k in ('start', 'weiter'):
                if k == 'weiter' and self.zustand != 'pausiert':
                    return f'weiter geht nur aus "pausiert" (jetzt {self.zustand})'
                if self.runde is None:
                    self._runde_beginnen(jetzt)
                self._setze('faehrt', jetzt)
                return 'faehrt'
            if k == 'pause':
                if self.zustand != 'faehrt':
                    return f'pause geht nur beim Fahren (jetzt {self.zustand})'
                self._setze('pausiert', jetzt)
                return 'pausiert'
            if k == 'stopp':
                if self.runde is not None and self.runde.gestoert is None:
                    self.runde.gestoert = 'gestoppt'
                self._setze('gestoppt', jetzt)
                self.blinker.setze('aus')
                return 'gestoppt'
            if k == 'fahrplan' and len(teile) == 2 and teile[1].isdigit():
                return self.umsetzen(int(teile[1]), jetzt)
        return f'unbekanntes Kommando: {text!r} (start, stopp, pause, weiter, fahrplan <nr>)'

    def _setze(self, zustand, jetzt):
        if zustand != self.zustand:
            self.zustand, self.zustand_seit = zustand, jetzt
            self.log(f'Fahr-Gehirn: {zustand}')

    def umsetzen(self, index, jetzt=None):
        """Roboter wurde von Hand umgesetzt: naechste Kreuzung ist Plan-Position 'index'. Eine offene Kreuzung wird
        mit dem bis jetzt Gemessenen ausgewertet; uebersprungene Plan-Positionen zaehlen als 'nicht erkannt'."""
        jetzt = time.time() if jetzt is None else jetzt
        with self.lock:
            index %= len(self.plan.plan)
            if self.kreuzung is not None:
                self._kreuzung_abschliessen(jetzt, self._gier)
            while self.plan.index != index:
                self._nicht_erkannt(jetzt, 'uebersprungen (umgesetzt)')
            self.weg_letzte = None
            self.blinker.setze('aus')
            self._speichern()
            return f'Fahrplan: naechste Kreuzung Nr. {index} ({self.plan.aktuell})'

    def zustand_info(self):
        """Fuer /fahrgehirn/zustand (JSON)."""
        with self.lock:
            s = self.lernen.stand
            return {'zustand': self.zustand, 'fahrplan': list(self.plan.plan), 'fahrplan_index': self.plan.index,
                    'naechste_richtung': self.plan.aktuell, 'blinker': self.blinker.zustand,
                    'kreuzung_aktiv': self.kreuzung is not None, 'runden_gesamt': s['runden_gesamt'],
                    'runde_gewertet': None if self.runde is None else self.runde.gestoert is None,
                    'phase': s['phase'], 'versuch': self._versuch_text(), 'parameter': self.parameter(),
                    'meldung': self.meldung, 'lernen': self.lernen_an, 'hilfe_noetig': self.hilfe_noetig}

    def parameter(self):
        return self.lernen.parameter()

    def kreuzung_aktiv(self):
        return self.kreuzung is not None

    # ---------------- Kreuzung (vom Linienfolger, Kamera-Thread) ----------------
    def kreuzung_waehlen(self, richtungen, gier, jetzt=None):
        """Aeste dieser Kreuzung (rad, + = links) -> gewaehlter Ast (rad) oder None (Wunsch-Ast noch nicht zu sehen).
        Wird von line_follower/linie.py beim ersten Sehen der Kreuzung gefragt (LinienSucher.waehler)."""
        jetzt = time.time() if jetzt is None else jetzt
        with self.lock:
            if self.kreuzung is not None and self.kreuzung.d['gewaehlt']:
                # neue Kreuzung, bevor die vorige fertig gemessen war: vorige jetzt auswerten
                self._kreuzung_abschliessen(jetzt, gier)
            if self.kreuzung is None:
                self.kreuzung = m.KreuzungsMessung(jetzt, self._runden_nr(), self.plan.index, self.plan.aktuell, gier,
                                                   self.weg, self._versuch_text())
                self.drehbeginn = None
                if self.plan.aktuell in ('links', 'rechts'):
                    self._blinken(self.plan.aktuell, jetzt)   # so frueh wie moeglich: beim ersten Sehen
            k = self.kreuzung
            ast = self.plan.ast_waehlen(richtungen)
            richtung = self.plan.aktuell
            if ast is None:
                k.wartet += 1
                if k.wartet < self.wahl_warten:
                    return None
                ast = Fahrplan.naechster_ast(richtungen, self.plan.aktuell)
                self.log(f'Fahr-Gehirn: "{self.plan.aktuell}" gibt es hier nicht '
                         f'(Aeste {[round(math.degrees(r)) for r in richtungen]} Grad) -> naechstbester Ast')
                richtung = richtung_aus_ast(math.degrees(ast))
            k.gewaehlt(jetzt, [math.degrees(r) for r in richtungen], richtung, gier, self.weg)
            self._blinken(richtung if richtung != 'geradeaus' else 'aus', jetzt)
            return ast

    def _blinken(self, richtung, jetzt):
        self.blinker.setze(richtung)
        if self.kreuzung is not None and richtung != 'aus' and self.kreuzung.blink_zeit is None:
            self.kreuzung.blink_zeit = jetzt

    # ---------------- Takt (20x pro Sekunde, vom Fahrbefehl) ----------------
    def takt(self, jetzt, dt, lin, dreh, lokal, status, gier, steht_absichtlich=False):
        """lin/dreh: gerade befohlen, lokal: Linie am Roboter (Gedaechtnis.lokal()) oder None, status: Text des
        Linienfolgers, gier: eigene Drehung (rad, Gedaechtnis), steht_absichtlich: Hindernis/Pause."""
        with self.lock:
            self._gier = gier
            weg_neu = status.startswith('KEINE LINIE') or status.startswith('Linie weg')
            linie_weg_neu = weg_neu and not self.linie_weg_vorher and not steht_absichtlich
            self.linie_weg_vorher = weg_neu
            # Linie verloren und Suche vorbei: er steht (faehrt nie blind los). Nach HILFE_NACH s melden.
            if status.startswith('KEINE LINIE') and self.zustand == 'faehrt':
                if self.ohne_linie_seit is None:
                    self.ohne_linie_seit = jetzt
                elif jetzt - self.ohne_linie_seit > HILFE_NACH and not self.hilfe_noetig:
                    self.hilfe_noetig = True
                    self.log(f'Fahr-Gehirn: steht seit {HILFE_NACH:.0f} s ohne Linie -> HILFE NOETIG: Roboter auf '
                             'die Linie setzen (dann faehrt er allein weiter) oder pause + fahrplan <nr>')
            else:
                self.ohne_linie_seit, self.hilfe_noetig = None, False
            if self.zustand != 'faehrt':
                if self.runde is not None:
                    self.runde.takt(dt, 0.0, 0.0, None, False, True)
                return
            self.weg += abs(lin) * dt
            if self.runde is not None:
                self.runde.takt(dt, lin, dreh, lokal, linie_weg_neu, steht_absichtlich)
            k = self.kreuzung
            if k is not None:
                k.takt(None if lokal is None else lokal['quer'], lin, linie_weg_neu)
                if k.gewaehlt_zeit is not None:
                    if self.drehbeginn is None and abs(k.drehung(gier)) > DREHBEGINN_GRAD:
                        self.drehbeginn = jetzt
                    if self.weg - k.weg0 >= self.messweg:
                        self._kreuzung_abschliessen(jetzt, gier)
                elif self.weg - k.weg0 >= self.messweg + 0.3:
                    # gesehen, aber der Wunsch-Ast kam nie und die Kreuzung ist vorbei
                    self._kreuzung_abschliessen(jetzt, gier, m.RICHTUNG_FEHLT)
            else:
                self._verpasst_pruefen(jetzt)

    def _verpasst_pruefen(self, jetzt):
        """Auf dem Roboter gibt es keine Wahrheit: Ist er viel weiter gefahren als sonst von der vorigen bis zu dieser
        Kreuzung (mind. 3 Messungen), war sie vermutlich da und er hat sie nicht erkannt."""
        if self.weg_letzte is None:
            return
        bisher = self.lernen.stand['strecken'].get(str(self.plan.index), [])
        if len(bisher) < 3:
            return
        typisch = statistics.median(bisher)
        if self.weg - self.weg_letzte > 1.6 * typisch + 0.3:
            self._nicht_erkannt(jetzt, f'vermutet: {self.weg - self.weg_letzte:.1f} m ohne Kreuzung '
                                       f'(sonst {typisch:.1f} m)')
            self.weg_letzte = self.weg

    def _nicht_erkannt(self, jetzt, grund):
        k = m.KreuzungsMessung(jetzt, self._runden_nr(), self.plan.index, self.plan.aktuell, 0.0, self.weg,
                               self._versuch_text())
        k.d.update({'erkannt': False, 'ergebnis': m.NICHT_ERKANNT, 'hinweis': grund})
        self._kreuzung_fertig(jetzt, k.d)

    def _kreuzung_abschliessen(self, jetzt, gier, ergebnis=None):
        k = self.kreuzung
        d = k.abschliessen(jetzt, gier, ergebnis, self.drehbeginn)
        if self.weg_letzte is not None and d['ergebnis'] != m.RICHTUNG_FEHLT:
            liste = self.lernen.stand['strecken'].setdefault(str(self.plan.index), [])
            liste.append(round(k.weg0 - self.weg_letzte, 2))
            del liste[:-10]
        self.weg_letzte = k.weg0
        self.kreuzung = None
        self.blinker.setze('aus')
        self.log(f"Kreuzung {d['plan_pos']}: gewuenscht {d['gewuenscht']}, gefahren {d['gefahren']} "
                 f"({d['drehung_grad']:+.0f} Grad) -> {d['ergebnis']}")
        self._kreuzung_fertig(jetzt, d)

    def _kreuzung_fertig(self, jetzt, d):
        self.protokoll.kreuzung(d)
        if self.runde is not None:
            self.runde.kreuzungen.append(d)
        if self.plan.weiter():
            self._runde_ende(jetzt)
        self._speichern()

    # ---------------- Runde ----------------
    def _runden_nr(self):
        return self.lernen.stand['runden_alle'] + 1

    def _runde_beginnen(self, jetzt):
        self.runde = m.RundenMessung(jetzt, self._runden_nr())
        if self.plan.index != 0:
            self.runde.gestoert = f'Start mitten im Fahrplan (Nr. {self.plan.index})'

    def _versuch_text(self):
        k = self.lernen.stand['kandidat']
        if self.lernen.stand['phase'] == 'kandidat' and k:
            return f"{k['name']}={k['parameter'][k['name']]}"
        return 'champion'

    def _runde_ende(self, jetzt):
        r = self.runde
        if r is None:
            return
        phase = self.lernen.stand['phase']
        zeile = r.abschliessen(jetzt, phase, self._versuch_text(), self.parameter())
        if r.gestoert:
            zeile['gewertet'] = False
            self.log(f'Runde nicht gewertet: {r.gestoert}')
        self.protokoll.runde(zeile)
        if zeile['gewertet']:
            letzte = self.protokoll.gewertete_runden()[-5:]
            art, text = m.diagnose(letzte)
            self.log(f"Runde {zeile['runde']} fertig: Kreuzungen {zeile['kreuzungen_ok']}/{zeile['kreuzungen']}, "
                     f"Abweichung {zeile['abw_mittel_cm']} cm, Linie weg {zeile['linie_weg']}x, "
                     f"Wertung {zeile['wertung']}. {text}")
            if self.lernen_an:
                aenderung = self.lernen.runde_fertig(zeile['wertung'], art)
            else:
                self.lernen.stand['runden_gesamt'] += 1
                aenderung = None
            if aenderung:
                self.meldung = aenderung
                self.log('Lernen: ' + aenderung)
                self.parameter_neu = True
            bloecke = self.protokoll.fortschritt()
            if bloecke and int(bloecke[-1]['bis_runde']) == zeile['runde']:
                z = bloecke[-1]
                self.log(f"FORTSCHRITT bis Runde {z['bis_runde']}: Abbiegen {z['abbiege_quote']}, "
                         f"Abweichung {z['abw_mittel_cm']} cm, Pendeln {z['pendeln_cm']} cm, "
                         f"Wertung {z['wertung_mittel']} (logs/fahrgehirn/fortschritt.csv)")
        self.lernen.stand['runden_alle'] += 1
        self.runde = m.RundenMessung(jetzt, self._runden_nr())

    def _speichern(self):
        self.lernen.stand['fahrplan_index'] = self.plan.index
        self.lernen.speichern()
