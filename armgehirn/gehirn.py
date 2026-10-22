#!/usr/bin/env python3
# Arm-Gehirn: ein eigener Modus, der NUR greift. Der Roboter faehrt dabei NICHT: Dieses Modul hat keinen Zugang
# zum Antrieb (kein Fahrbefehl, kein naeher heranfahren). Reicht der Arm nicht hin, meldet es "nicht erreichbar".
# Ohne ROS: Kamera, Tiefe und Arm kommen als Adapter herein (Roboter: armgehirn/knoten.py, Uebungswelt:
# sim/armgehirn_sim.py, Tests: Attrappen). Ablauf EINES Versuchs (versuch()):
#   1. umschauen   Arm in ausgerechnete Blickstellungen (armgehirn/blick.py), bis die Tiefenkamera etwas sieht.
#                  Welche Stellung sich bewaehrt, lernt er mit (Reihenfolge beim naechsten Mal).
#   2. entscheiden FESTE Sicherheitsregel (armgehirn/sicherheit.py): Person/Figur/unklar -> nicht anfassen.
#                  Kommt vor allem anderen; das Lernen kann sie nicht aendern.
#   3. planen      Kinematik + gelernte, lageabhaengige Korrektur (lib/greifen.py), feste Ablagestelle.
#   4. ausfuehren  Greifer auf -> ueber den Gegenstand -> runter -> zu -> anheben -> zur Ablage -> absetzen ->
#                  loslassen -> Grundstellung. Laeuft waehrenddessen ein Mensch ins Bild: KEIN Abbruch, der Arm
#                  haelt NICHT an (Projektvorgabe). Abbrechen nur ausdruecklich (abbrechen()): dann keine
#                  weitere Armbewegung, der Arm bleibt stehen, wo er ist.
#   5. pruefen     alter Ort frei? an der Ablage? (armgehirn/pruefung.py) -> Ergebnis + Belohnung
#   6. lernen      Greif-Lernen + Umschauen, nach JEDEM Versuch atomar gespeichert; Zeile ins Protokoll.
# Schnittstelle nach aussen (spaeter Panel / KI-Zentrale, im Wechsel mit dem Fahr-Gehirn):
#   start(erwartet=None)  "Objekt vor dir": Versuch im Hintergrund      abbrechen()  sofort keine Armbewegung mehr
#   status()              {'zustand': bereit|laeuft|fertig|abgebrochen|fehler, 'phase', 'ergebnis', 'antrieb': ...}
#   grundstellung()       Arm in die Grundstellung (z. B. nach abbrechen)    fahrstellung()  vor dem Entladen
import os
import sys
import threading
import time

import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__))
for _d in (HIER, os.path.join(HIER, '..', 'lib')):
    sys.path.insert(0, _d)
import arm as armlib       # noqa: E402
import blick as blicklib   # noqa: E402
import greifen             # noqa: E402
import lage as lagelib     # noqa: E402
import protokoll as prot   # noqa: E402
import pruefung            # noqa: E402
import sicherheit          # noqa: E402

STANDARD = {
    'ablage': [0.10, -0.18],   # feste Ablagestelle (Mitte, m vor der Robotermitte / links), rechts neben dem Roboter
    'bilder': 6,               # so viele Kamerabilder je Blick
    'blick_max': 6,            # so viele Blickstellungen hoechstens beim Umschauen
    'ruhe_s': 0.4,             # nach einer Armbewegung so lange warten, bis die Kamera ruhig ist
    'tempo_ms': 1500,          # Dauer einer Blick-Bewegung
    'erkunden': True,          # beim Greifen ausprobieren (Lernen); False: immer die beste Korrektur (Pruefen)
    'belohnung': 'fein',       # 'fein': abgelegt/verschoben/unberuehrt; 'grob': nur "alter Ort frei" (wie frueher)
}


class Abbruch(Exception):
    pass


class ArmGehirn:
    def __init__(self, augen, arm, kin, politik, fahr, kamera_fahr, cfg=None, protokoll=None, zustand_datei=None,
                 rng=None, auf=None, zu=None, sicherheit_cfg=None):
        """augen: Tiefe + Kamera-KI je Blick (armgehirn/augen.py), arm: fahre(winkel, ms) / warte(s) [/ greifer()],
        kin: Kinematik (inverse, g), politik: lib/greifen.Politik, fahr: Fahrstellung, kamera_fahr: Kameramasse dort."""
        self.augen, self.arm, self.kin, self.politik = augen, arm, kin, politik
        self.fahr, self.kamera_fahr = list(fahr), dict(kamera_fahr)
        self.c = dict(STANDARD)
        self.c.update(cfg or {})
        self.sicherheit_cfg = sicherheit_cfg
        self.protokoll = protokoll
        self.zustand_datei = zustand_datei
        self.rng = rng if rng is not None else np.random.default_rng()
        self.auf, self.zu = (auf, zu) if auf is not None else armlib.greifer_werte()
        zustand = prot.lade_zustand(zustand_datei) if zustand_datei else {}
        self.blick_lernen = blicklib.BlickLernen(zustand.get('blick'))
        self.lage_kalibrierung = zustand.get('lage_kalibrierung')
        self.links = -1 if self.kin.g.get('servo1_links', 1) < 0 else 1
        self.stellungen = blicklib.blickstellungen(self.kamera_fahr, self.fahr, self.kin.g)
        eigene = self.c.get('greifblick')       # eingelernte Pose (optional): zuerst probieren
        if eigene:
            k = armlib.kamera_fuer_pose(self.kamera_fahr, self.fahr, eigene, self.kin.g)
            if k:
                self.stellungen.insert(0, {'pose': list(eigene), 'kamera': k, 'sicht': blicklib.sichtbereich(k)})
        if not self.stellungen:
            raise ValueError('keine Blickstellung gefunden, aus der die Kamera den Greifbereich sieht')
        self.grund = list(self.stellungen[0]['pose'])
        self.grund[5] = self.auf
        self.zustand, self.phase, self.letztes = 'bereit', '', None
        self._abbruch = threading.Event()
        self._faden = None
        self.antrieb = 'gesperrt (Arm-Gehirn sendet keine Fahrbefehle)'

    # ---------------------------------------------------------------- Schnittstelle nach aussen
    def start(self, erwartet=None, wahr=None):
        """'Objekt vor dir': einen Versuch im Hintergrund starten. False, wenn schon einer laeuft."""
        if self.zustand == 'laeuft':
            return False
        self._abbruch.clear()
        self.zustand = 'laeuft'
        self._faden = threading.Thread(target=self.versuch, args=(erwartet, wahr), daemon=True)
        self._faden.start()
        return True

    def abbrechen(self):
        """Sofort keine weitere Armbewegung (der Arm bleibt stehen, wo er ist)."""
        self._abbruch.set()

    def warte_fertig(self, timeout=None):
        if self._faden is not None:
            self._faden.join(timeout)
        return self.letztes

    def status(self):
        return {'zustand': self.zustand, 'phase': self.phase, 'ergebnis': self.letztes, 'antrieb': self.antrieb,
                'lernstand': self.politik.lernstand(),
                'fortschritt': self.protokoll.stand() if self.protokoll else None}

    def grundstellung(self):
        return self.arm.fahre(self.grund, self.c['tempo_ms'])

    def fahrstellung(self):
        """Vor dem Uebergeben an das Fahr-Gehirn: Arm in die Fahrstellung (dort stimmt dessen Kameramodell)."""
        f = list(self.fahr)
        f[5] = self.auf
        return self.arm.fahre(f, self.c['tempo_ms'])

    # ---------------------------------------------------------------- Einrichten
    def _blicke(self):
        """Alle Blickstellungen: (Schluessel, Pose, Kameramasse, Drehung Grad)."""
        aus = []
        for s in self.stellungen:
            for grad in blicklib.DREHUNGEN:
                pose = blicklib.gedreht(s['pose'], grad, self.links)
                if pose:
                    pose[5] = self.auf
                    aus.append((blicklib.BlickLernen.schluessel(pose, grad), pose, s['kamera'], grad))
        return aus

    def _ablageblick(self, basis):
        grad = int(round(blicklib.drehung_zu(self.c['ablage'], self.kin.g['schulter'][0])))
        pose = blicklib.gedreht(basis['pose'], grad, self.links)
        if pose:
            pose[5] = self.auf
        return pose, grad

    def einrichten(self):
        """Boden in allen Blickstellungen kennenlernen. Der Bereich vor und neben dem Roboter muss LEER sein."""
        blicke = self._blicke() + [('ablage', *self._ablage_eintrag())]
        for schluessel, pose, kamera, grad in blicke:
            self._fahre(pose)
            self.augen.boden_lernen(schluessel, kamera)
        self._fahre(self.grund)
        self._speichern_zustand()
        return len(blicke)

    def _ablage_eintrag(self):
        pose, grad = self._ablageblick(self.stellungen[0])
        return pose, self.stellungen[0]['kamera'], grad

    # ---------------------------------------------------------------- Ein Versuch
    def _fahre(self, winkel, ms=None):
        if self._abbruch.is_set():
            raise Abbruch()
        fehler = self.arm.fahre(winkel, ms or self.c['tempo_ms'])
        if fehler:
            raise RuntimeError(f'Arm: {fehler}')
        self.arm.warte((ms or self.c['tempo_ms']) / 1000.0 + self.c['ruhe_s'])

    def _sehen(self, schluessel, kamera, grad):
        """Bilder in dieser Blickstellung, Gegenstaende ins Roboter-System umgerechnet."""
        bilder = self.augen.messen(schluessel, kamera, self.c['bilder'])
        sx = self.kin.g['schulter'][0]
        return [dict(b, objekt=blicklib.ins_roboter_system(b.get('objekt'), grad, sx)) for b in bilder]

    @staticmethod
    def _gegenstaende(bilder):
        """Was liegt da (mind. in der Haelfte der Bilder gesehen)? Liste mit hoechstens einem Gegenstand."""
        m = [b['objekt'] for b in bilder if b.get('objekt')]
        return [sicherheit._mittel(m)] if m and len(m) >= len(bilder) / 2 else []

    def _umschauen(self):
        """Blickstellungen der Reihe nach (bewaehrte zuerst), bis etwas zu sehen ist. -> (Bilder, Blick, KI-Funde
        aus den anderen Blicken, Anzahl Blicke)"""
        blicke = self.blick_lernen.reihenfolge(self._blicke(), self.rng)[:self.c['blick_max']]
        umgebung, teilweise = [], None
        for i, (schluessel, pose, kamera, grad) in enumerate(blicke):
            self.phase = f'umschauen ({i + 1}): {schluessel}'
            self._fahre(pose)
            bilder = self._sehen(schluessel, kamera, grad)
            # gefunden = in mind. der Haelfte der Bilder ganz zu sehen (am Bildrand abgeschnitten: weiter umschauen)
            gesehen = sum(1 for b in bilder if b.get('objekt') and not b['objekt'].get('rand')) >= max(2, len(bilder) // 2)
            self.blick_lernen.ergebnis(schluessel, gesehen)
            if gesehen:
                return bilder, (schluessel, pose, kamera, grad), umgebung, i + 1
            umgebung += [o for b in bilder for o in (b.get('objekte') or [])]
            if teilweise is None and any(b.get('objekt') for b in bilder):
                teilweise = (bilder, (schluessel, pose, kamera, grad))
        if teilweise:          # nur angeschnitten gesehen: die Sicherheitsregel entscheidet (-> zweifel)
            return teilweise[0], teilweise[1], umgebung, len(blicke)
        return [], None, umgebung, len(blicke)

    def versuch(self, erwartet=None, wahr=None):
        """Ein ganzer Versuch. erwartet: 'greifen' | 'nicht_greifen' | None (Training: was liegt da wirklich?).
        wahr: bekannte Lage (Mitte x, y) bei Markierung. Rueckgabe: Ergebnis-dict (auch in status()['ergebnis'])."""
        t0 = time.time()
        self.zustand = 'laeuft'
        zeile = {'erwartet': erwartet or '', 'modell': self.politik.schluessel}
        try:
            erg = self._versuch(zeile, wahr)
            self.zustand = 'fertig'
        except Abbruch:
            erg = {'ergebnis': 'abgebrochen', 'text': 'abgebrochen (Arm bleibt stehen, wo er ist)'}
            self.zustand = 'abgebrochen'
        except Exception as e:      # nie haengen bleiben: Fehler melden, Arm nicht weiter bewegen
            erg = {'ergebnis': 'fehler', 'text': f'Fehler: {e}'}
            self.zustand = 'fehler'
        self.phase = ''
        zeile.update(ergebnis=erg['ergebnis'], belohnung=erg.get('belohnung'), text=erg.get('text'),
                     dauer_s=round(time.time() - t0, 1))
        gegriffen = erg['ergebnis'] in ('abgelegt', 'verloren', 'verschoben', 'unberuehrt', 'unklar')
        if erwartet == 'nicht_greifen':
            zeile['richtig'] = not gegriffen and erg['ergebnis'] not in ('abgebrochen', 'fehler')
        elif erwartet == 'greifen':
            zeile['richtig'] = erg['ergebnis'] == 'abgelegt'
        erg['richtig'] = zeile.get('richtig')
        self._speichern_zustand()
        if self.protokoll is not None:
            erg['nr'] = self.protokoll.schreiben(zeile)['nr']
            erg['fortschritt'] = self.protokoll.stand()
        self.letztes = erg
        return erg

    def _versuch(self, zeile, wahr):
        # 1. umschauen
        self.phase = 'umschauen'
        bilder, blick, umgebung, n = self._umschauen()
        zeile.update(blick=blick[0] if blick else '', blick_versuche=n)
        # 2. entscheiden: FESTE Regel, vor allem anderen
        e = sicherheit.entscheide(bilder, self.sicherheit_cfg, umgebung)
        zeile.update(entscheidung=e['art'], grund=e['grund'])
        o = e['objekt']
        if o:
            zeile.update(gemessen_vor=o['vor'], gemessen_seite=o['seite'], breite=o['breite'], hoehe=o['hoehe'])
        if not e['darf']:
            self._fahre(self.grund)
            return {'ergebnis': 'nicht_gegriffen', 'art': e['art'], 'text': f"nicht gegriffen: {e['grund']}"}
        # 3. planen (Lage-Kalibrierung, dann Kinematik + gelernte Korrektur)
        self.phase = 'planen'
        o = lagelib.anwenden(o, self.lage_kalibrierung)
        zeile.update(kalibriert_vor=o['vor'], kalibriert_seite=o['seite'])
        if wahr is not None:
            m = pruefung.mitte(o)
            zeile.update(wahr_vor=wahr[0], wahr_seite=wahr[1],
                         lagefehler_cm=round(float(np.hypot(m[0] - wahr[0], m[1] - wahr[1])) * 100, 2))
        g = armlib.greifer_plan(o['breite'])
        plan = greifen.plane(o, 1 if self.c['ablage'][1] > 0 else -1, self.kin.inverse, self.grund, self.auf, g['zu'],
                             self.politik, self.rng, erkunden=self.c['erkunden'], anlegen=g['anlegen'],
                             ablage=self.c['ablage'])
        if plan.get('fehler') or plan.get('naeher'):
            self._fahre(self.grund)
            grund = plan.get('fehler', '')
            if plan.get('naeher'):
                grund = f"Arm reicht nicht hin (waere {plan['naeher'] * 100:.0f} cm naeher noetig; ich fahre nicht)"
            return {'ergebnis': 'nicht_erreichbar', 'text': f'nicht erreichbar: {grund} -> bitte naeher hinlegen'}
        zeile.update(ziel_x=plan['ziel'][0], ziel_y=plan['ziel'][1], ziel_z=plan['ziel'][2],
                     korrektur_x=plan['korrektur'][0], korrektur_y=plan['korrektur'][1], korrektur_z=plan['korrektur'][2])
        # 4. ausfuehren (Personen im Bild aendern nichts; nur abbrechen() stoppt)
        greifer = None
        for text, winkel, dauer in plan['schritte']:
            self.phase = f'ausfuehren: {text}'
            self._fahre(winkel, int(dauer * 1000))
            if text == 'zugreifen' and hasattr(self.arm, 'greifer'):
                greifer = self.arm.greifer()
        zeile['greifer'] = greifer
        # 5. pruefen: alter Ort (im Blick, in dem er gefunden wurde), dann Ablage
        self.phase = 'pruefen: alter Ort'
        schluessel, pose, kamera, grad = blick
        self._fahre(pose)
        alt = self._gegenstaende(self._sehen(schluessel, kamera, grad))
        self.phase = 'pruefen: Ablage'
        apose, akamera, agrad = self._ablage_eintrag()
        ablage_blick = None
        if apose and self.augen.kann('ablage'):
            self._fahre(apose)
            ablage_blick = self._gegenstaende(self._sehen('ablage', akamera, agrad))
        self._fahre(self.grund)
        b = pruefung.bewerte(o, alt, ablage_blick, self.c['ablage'], greifer)
        zielfehler = getattr(self.arm, 'letzter_zielfehler', None)      # nur in der Uebungswelt bekannt
        quelle = 'simulator' if zielfehler is not None else ('ablage' if b['ablage_abweichung_m'] is not None else '')
        if zielfehler is None:
            zielfehler = b['ablage_abweichung_m']
        zeile.update(alter_ort_frei=b['alter_ort_frei'],
                     verschiebung_cm=None if b['verschiebung_m'] is None else round(b['verschiebung_m'] * 100, 2),
                     ablage_abweichung_cm=None if b['ablage_abweichung_m'] is None else round(b['ablage_abweichung_m'] * 100, 2),
                     zielfehler_cm=None if zielfehler is None else round(zielfehler * 100, 2), zielfehler_quelle=quelle)
        # 6. lernen + speichern (unklar wird nicht gelernt: lieber nichts als etwas Falsches)
        if self.c['belohnung'] == 'grob' and plan.get('lernen'):       # nur zum Vergleich mit frueher
            self.politik.ergebnis(plan['lernen']['obj'], plan['lernen']['a'], bool(b['alter_ort_frei']))
            self.politik.speichern()
        elif b['ergebnis'] != 'unklar' and plan.get('lernen'):
            self.politik.ergebnis(plan['lernen']['obj'], plan['lernen']['a'], b['ergebnis'])
            self.politik.speichern()
        return {'ergebnis': b['ergebnis'], 'belohnung': b['belohnung'], 'text': b['text'], 'plan': plan['info'],
                'korrektur_cm': [round(v * 100, 1) for v in plan['korrektur']]}

    def nur_messen(self):
        """Umschauen und vermessen, NICHT greifen (Lage-Kalibrierung, Diagnose). -> Gegenstand (Roboter-System,
        ohne Kalibrierung) oder None."""
        bilder, blick, _, _ = self._umschauen()
        self._fahre(self.grund)
        self._speichern_zustand()
        m = [b['objekt'] for b in bilder if b.get('objekt')]
        return sicherheit._mittel(m) if m else None

    def _speichern_zustand(self):
        if not self.zustand_datei:
            return
        daten = prot.lade_zustand(self.zustand_datei)
        daten['blick'] = self.blick_lernen.als_dict()
        daten['boden'] = self.augen.als_dict() if hasattr(self.augen, 'als_dict') else daten.get('boden')
        if self.lage_kalibrierung:
            daten['lage_kalibrierung'] = self.lage_kalibrierung
        prot.speichere_zustand(daten, self.zustand_datei)
