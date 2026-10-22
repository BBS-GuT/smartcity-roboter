#!/usr/bin/env python3
# Prueft die Entscheidungen der KI-Zentrale mit ausgedachten Wahrnehmungen (kein Roboter noetig).
# Aufruf: python3 tests/test_entscheider.py
import math
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ki'))
from entscheider import Entscheider, STANDARD  # noqa: E402

fehler = 0


class Lauf:
    """Spielt Bilder im Abstand von 0,1 s ab."""

    def __init__(self, **kw):
        self.e = Entscheider(**kw)
        self.t = 100.0
        self.nr = 0

    def schritt(self, n=1, **w):
        befehl = None
        for _ in range(n):
            # Eigener Planerthread: auf sein Ergebnis warten, bevor die Testuhr weitergeht.
            a = self.e.ablauf
            ende = time.monotonic() + 3.0
            while a is not None and a.phase in ('vorpruefen', 'planen') and getattr(a, 'plan', 1) is None:
                if time.monotonic() >= ende:
                    raise AssertionError(f'Testplaner in {a.phase} wurde nicht fertig')
                time.sleep(0.001)
            self.t += 0.1
            self.nr += 1
            daten = {'bild_nr': self.nr, 'bild_zeit': self.t, 'aufnahme': self.t, 'objekte': [], 'ampel': None,
                     'stoppschild': False, 'lidar': float('inf'), 'tiefe_hindernis': False,
                     'lidar_hinten': 1.0}   # hinten frei (sonst faehrt er nicht rueckwaerts)
            daten.update(w)
            befehl = self.e.update(self.t, daten)
        return befehl

    def bis(self, arm, max_schritte=40, **w):
        """Schritte machen, bis ein Arm-Befehl kommt (oder max_schritte erreicht)."""
        for _ in range(max_schritte):
            befehl = self.schritt(1, **w)
            if befehl['arm'] == arm:
                return befehl
        return befehl


def pruefe(name, befehl, aktion, arm='egal'):
    global fehler
    ok = befehl['aktion'] == aktion and (arm == 'egal' or befehl['arm'] == arm)
    fehler += not ok
    print(f"{'OK  ' if ok else 'FEHLER'} {name}: {befehl['aktion']} ({befehl['grund']}) arm={befehl['arm']}")


l = Lauf()
pruefe('freie Fahrt', l.schritt(3), 'fahren')
pruefe('Rot 1 Bild (noch nicht sicher)', l.schritt(1, ampel='rot'), 'fahren')
pruefe('Rot 2 Bilder -> Stopp', l.schritt(1, ampel='rot'), 'stopp')
pruefe('Ampel kurz verdeckt -> weiter warten', l.schritt(5, ampel=None), 'stopp')
pruefe('Gruen -> weiter', l.schritt(2, ampel='gruen'), 'fahren')
pruefe('Gelb -> Stopp', l.schritt(2, ampel='gelb'), 'stopp')
# GB/B1: Rot verschwindet nicht durch Timeout - Ampel nicht mehr zu sehen ist keine Freigabe
pruefe('Ampel weg, auch lange -> weiter Halt (kein Timeout)', l.schritt(100, ampel=None), 'stopp')
pruefe('erst Gruen gibt frei', l.schritt(2, ampel='gruen'), 'fahren')
# Rot, Ampel danach ausser Sicht: haelt, sagt warum - bis der Bediener STOPP + START drueckt
l = Lauf()
l.schritt(2, ampel='rot')
b = l.schritt(60, ampel=None)
pruefe('Rot ausser Sicht -> Halt mit Hinweis auf START', b, 'stopp')
ok = 'STOPP, dann START' in b['grund']
l.e.fahrt_aktiv = False
l.schritt(1)
l.e.kommando(l.t, 'start')
l.e.fahrt_aktiv = True
b = l.schritt(3, ampel=None)
ok = ok and b['aktion'] == 'fahren'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Rot-Halt: ausdruecklicher START gibt frei ({b['grund']})")
l.e.fahrt_aktiv = False                          # Statusausfall ohne START gibt Rot NICHT frei
l2 = Lauf()
l2.schritt(2, ampel='rot')
l2.e.fahrt_aktiv = False
l2.schritt(15, ampel=None)
l2.e.fahrt_aktiv = True
pruefe('Rot + Statusausfall/Wiederkehr ohne START -> weiter Halt', l2.schritt(3, ampel=None), 'stopp')
# zwei Haltegruende gleichzeitig: Gruen hebt den Hindernishalt nicht auf
KLOTZ = {'vor': 0.3, 'seite': 0.0, 'breite': 0.05, 'hoehe': 0.05, 'quelle': 'tiefe'}   # Kamera sieht ihn
l = Lauf()
l.schritt(2, ampel='rot')
pruefe('Rot + Hindernis -> Halt', l.schritt(3, ampel='rot', lidar=0.3, objekt=KLOTZ), 'stopp')
pruefe('Gruen, Hindernis noch da -> weiter Halt', l.schritt(15, ampel='gruen', lidar=0.3, objekt=KLOTZ), 'stopp')
pruefe('Gruen und Hindernis weg -> weiter', l.schritt(30, ampel='gruen'), 'fahren')

l = Lauf()
pruefe('Stoppschild -> halten', l.schritt(2, stoppschild=True), 'stopp')
pruefe('nach 3 s weiter, obwohl Schild noch sichtbar', l.schritt(31, stoppschild=True), 'fahren')
pruefe('Schild lange sichtbar (langsam vorbei) -> kein 2. Halt', l.schritt(80, stoppschild=True), 'fahren')
l.schritt(25)
pruefe('naechstes Schild (nach 2,5 s ohne Schild) -> wieder halten', l.schritt(2, stoppschild=True), 'stopp')

l = Lauf()
pruefe('LiDAR meldet etwas -> erst anhalten, Kamera prueft',
       l.e.update(l.t + 0.05, {'bild_nr': 0, 'bild_zeit': l.t, 'lidar': 0.3}), 'stopp')
pruefe('LiDAR + Kamera-KI sieht Person -> Stopp',
       l.schritt(1, lidar=0.3, objekte=[{'name': 'Person', 'im_weg': True}]), 'stopp')
pruefe('Person weg, LiDAR frei -> noch kurz warten', l.schritt(1), 'stopp')
pruefe('nach 1 s frei -> weiter', l.schritt(10), 'fahren')
pruefe('LiDAR + Tiefenkamera -> Stopp', l.schritt(1, lidar=0.3, tiefe_hindernis=True), 'stopp')
l = Lauf()
pruefe('LiDAR ohne Bestaetigung -> nach dem Anschauen langsam', l.schritt(15, lidar=0.3), 'langsam')
pruefe('LiDAR ohne Bestaetigung, aber naeher als 20 cm -> halten', l.schritt(1, lidar=0.18), 'stopp')
pruefe('NOTBREMSE unter 12 cm, ohne KI', l.schritt(1, lidar=0.10), 'stopp')
pruefe('kein LiDAR -> Stopp', l.schritt(1, lidar=None), 'stopp')
l = Lauf()
l.schritt(1)
pruefe('KI-Bild veraltet -> Stopp',
       l.e.update(l.t + 3.0, {'bild_nr': l.nr, 'bild_zeit': l.t, 'lidar': float('inf')}), 'stopp')

# LiDAR meldet etwas, Kamera sieht nichts (z. B. Hauskante in der Kurve)
l = Lauf()
b = l.schritt(5, lidar=0.3)
pruefe('LiDAR 30 cm, Kamera schaut noch hin -> Stopp', b, 'stopp')
pruefe('Kamera sieht nach >= 1 s nichts -> langsam', l.schritt(15, lidar=0.3), 'langsam')
pruefe('kein zweites Anschauen fuer dieselbe Meldung', l.schritt(30, lidar=0.3), 'langsam')
pruefe('naeher als 20 cm -> halten', l.schritt(1, lidar=0.18), 'stopp')
l = Lauf()
l.schritt(3, lidar=0.3)
pruefe('Fehlalarm: LiDAR und Kamera sehen nichts mehr -> weiter', l.schritt(20, lidar=1.0), 'fahren')
# langsame KI: Anschauen wartet auf genug BILDER, nicht nur auf die Zeit
l = Lauf()
l.schritt(1, lidar=0.3)
for _ in range(30):                     # 3 s, aber kein neues Bild
    l.t += 0.1
    b = l.e.update(l.t, {'bild_nr': l.nr, 'bild_zeit': l.t, 'lidar': 0.3, 'objekte': []})
pruefe('KI liefert keine neuen Bilder -> wartet weiter mit dem Urteil', b, 'stopp')

# KI ueberlastet und Roboter rollt nach: Kamera sieht den Wuerfel in 2 Bildern (22 cm), dann nicht mehr
# (zu nah, unter dem Blickfeld) -> darf NICHT "frei" daraus machen, sondern faehrt zurueck und schaut nochmal
l = Lauf()
NAH_WEG = {'vor': 0.22, 'seite': 0.0, 'breite': 0.04, 'hoehe': 0.045, 'quelle': 'tiefe'}
aktionen, gefahren = [], 0.0
for k in range(150):
    l.t += 0.1
    if k % 8 == 0:
        l.nr += 1                            # nur alle 0,8 s ein KI-Bild
    sichtbar = k < 16 or gefahren < -0.06    # erst wieder zu sehen, wenn er 6 cm zurueckgefahren ist
    b = l.e.update(l.t, {'bild_nr': l.nr, 'bild_zeit': l.t, 'lidar': float('inf'), 'objekte': [], 'lidar_hinten': 1.0,
                         'objekt': dict(NAH_WEG, vor=0.22 - gefahren) if sichtbar else None})
    if b.get('manoever'):
        gefahren += b['manoever']['lin'] * 0.1
    aktionen.append(b['aktion'])
ok = 'fahren' not in aktionen and 'manoever' in aktionen
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Hindernis gesehen, dann zu nah fuer die Kamera -> zurueck statt drueberfahren "
      f"({gefahren * 100:.0f} cm, zuletzt {aktionen[-1]})")

# ---------------- Zebrastreifen ----------------
POSEN = {'fahrstellung': [90, 120, 10, 20, 90, 30],
         'blick_links': [135, 120, 10, 20, 90, 30], 'blick_rechts': [45, 120, 10, 20, 90, 30]}
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'))
import arm as armlib  # noqa: E402
import greifen        # noqa: E402
SIM_GEO = {'schulter': [0.037, 0.0, 0.13], 'oberarm': 0.083, 'unterarm': 0.083, 'hand': 0.155}   # sim/arm_sim.yaml
KIN = armlib.Kinematik(SIM_GEO)


def planer(obj, seite, kin=KIN):
    """wie ki/zentrale.py (eigene Kinematik, ohne Lernen)"""
    return greifen.plane(obj, seite, kin.inverse, POSEN['fahrstellung'], 30, 130)


def arm_befehle(lauf, n, **w):
    """n Schritte, sammelt alle Arm-Befehle."""
    arme, letzter = [], None
    for _ in range(n):
        letzter = lauf.schritt(1, **w)
        a = letzter['arm']
        if a:
            arme.append(a if isinstance(a, str) else a.get('pose') or tuple(a['winkel']))
    return arme, letzter


# #70 / Scopeentscheidung #8: am Zebrastreifen kein eigenstaendiger Arm-/Kameraschwenk. Ersetzt den frueheren Test
# "umschauen links, rechts, zurueck" (blick_links, blick_rechts, fahrstellung), der genau diesen Schwenk verlangte.
# Freigabe nur mit gueltiger Beobachtung: neue, frische Bilder MIT LiDAR-Daten am Ueberweg (hier lidar_breit, frei).
FREI = {'lidar_breit': 1.0}
l = Lauf(arm_erlaubt=True, posen=POSEN)
pruefe('Zebrastreifen 50 cm -> noch fahren', l.schritt(2, zebra={'abstand': 0.5}, **FREI), 'fahren')
pruefe('Zebrastreifen 30 cm -> anhalten', l.schritt(1, zebra={'abstand': 0.3}, **FREI), 'stopp')
folge = [l.schritt(1, zebra={'abstand': 0.3}, **FREI) for _ in range(80)]
arme = [x['arm'] for x in folge if x['arm']]
erst = next(i for i, x in enumerate(folge) if x['aktion'] == 'fahren')
ok = arme == [] and erst >= STANDARD['anschauen_bilder'] and all(x['aktion'] == 'stopp' for x in folge[:erst])
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} #70: Armfreigabe + Posen -> kein Armschwenk am Zebrastreifen, haelt bis frei "
      f"(Arm {arme}, {erst} Zyklen Halt)")
b = folge[-1]
pruefe('niemand da -> weiter', b, 'fahren')
pruefe('derselbe Zebrastreifen -> kein zweiter Halt', l.schritt(20, zebra={'abstand': 0.2}), 'fahren')
l = Lauf(arm_erlaubt=True, posen=POSEN)
l.schritt(1, zebra={'abstand': 0.3}, **FREI)
arme, b = arm_befehle(l, 80, zebra={'abstand': 0.3}, objekte=[{'name': 'Person', 'im_weg': False}], **FREI)
pruefe('Person gesehen -> wartet weiter', b, 'stopp')
ok = arme == []
arme, b = arm_befehle(l, 120, zebra={'abstand': 0.3}, **FREI)
pruefe('Person weg -> weiter', b, 'fahren')
ok = ok and arme == []
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Person am Zebrastreifen: auch beim Warten kein Armbefehl")
l = Lauf()
l.schritt(1, zebra={'abstand': 0.3})
arme, b = arm_befehle(l, 30, zebra={'abstand': 0.3}, lidar_breit=0.35)
ok = arme == [] and b['aktion'] == 'stopp'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} ohne Arm-Freigabe: kein Arm, etwas auf dem Zebrastreifen -> wartet ({b['grund']})")
pruefe('ohne Arm, frei -> weiter', l.schritt(80, zebra={'abstand': 0.3}, **FREI), 'fahren')
# LiDAR-Punkte: nur der Bereich am Zebrastreifen zaehlt (Haus/Wand daneben nicht)
import numpy as np  # noqa: E402
wand = np.array([[0.3 + 0.02 * k, -0.40] for k in range(20)])       # 40 cm rechts: Wand/Haus
fussgaenger = np.array([[0.36, -0.20], [0.37, -0.21]])               # wartet rechts am Zebrastreifen
l = Lauf(arm_erlaubt=True, posen=POSEN)
l.schritt(1, zebra={'abstand': 0.3}, lidar_xy=wand)
arme, b = arm_befehle(l, 80, zebra={'abstand': 0.3}, lidar_xy=wand)
pruefe('nur Wand neben der Strasse -> weiter', b, 'fahren')
l = Lauf(arm_erlaubt=True, posen=POSEN)
l.schritt(1, zebra={'abstand': 0.3}, lidar_xy=np.vstack([wand, fussgaenger]))
arme, b = arm_befehle(l, 80, zebra={'abstand': 0.3}, lidar_xy=np.vstack([wand, fussgaenger]))
pruefe('Fussgaenger am Zebrastreifen (LiDAR) -> wartet', b, 'stopp')
arme, b = arm_befehle(l, 120, zebra={'abstand': 0.3}, lidar_xy=wand)
pruefe('Fussgaenger weg -> weiter', b, 'fahren')
links = np.array([[0.36, 0.20], [0.37, 0.21]])                     # wartet links am Zebrastreifen
l = Lauf(arm_erlaubt=True, posen=POSEN)
l.schritt(1, zebra={'abstand': 0.3}, lidar_xy=np.vstack([wand, links]))
arme, b = arm_befehle(l, 80, zebra={'abstand': 0.3}, lidar_xy=np.vstack([wand, links]))
ok = b['aktion'] == 'stopp' and 'links' in b['grund'] and arme == []
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Fussgaenger links am Zebrastreifen (LiDAR) -> wartet, kein Arm ({b['grund']})")

# Zebrastreifen waehrend eines anderen Ablaufs gesehen (Hindernis anschauen), danach zu nah fuer die Kamera
# -> muss trotzdem am Zebrastreifen halten und umschauen (nicht einfach drueberfahren)
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
l.schritt(1, objekt={'vor': 0.32, 'seite': 0.0, 'breite': 0.03, 'hoehe': 0.03, 'quelle': 'tiefe'})
l.schritt(3, zebra={'abstand': 0.30})          # Zebrastreifen im Bild, waehrend er das Hindernis anschaut
b = l.schritt(40)                               # Hindernis weg, Zebrastreifen nicht mehr zu sehen
ok = l.e.ablauf is not None and l.e.ablauf.name == 'zebra' and b['aktion'] == 'stopp'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Zebrastreifen waehrend Hindernis-Pruefung gesehen -> haelt danach trotzdem am "
      f"Zebrastreifen ({b['grund']})")

# ---------------- #70: kein Armschwenk am Zebrastreifen, keine Freigabe ohne gueltige Beobachtung ----------------
# Reproduktion aus dem Issue (unveraendert): globale Armfreigabe, Posen vorhanden, Zebrastreifen in 0,30 m.
# Ausgangsstand: blick_links bei t=600,5 (rot). Nach dem Fix: kein Armbefehl.
from ablaeufe import Zebrastreifen  # noqa: E402
posen = {name: [90] * 6 for name in ('fahrstellung', 'blick_links', 'blick_rechts')}
e = Entscheider(arm_erlaubt=True, posen=posen)
befehle = []
for i in range(6):
    t = 600.0 + 0.1 * i
    befehle.append(e.update(t, dict(bild_nr=i, bild_zeit=t, lidar=float('inf'), objekte=[], gier=0.0, ampel=None,
                                    stoppschild=False, zebra={'abstand': 0.3})))
ok = not any(b['arm'] for b in befehle) and all(b['aktion'] == 'stopp' for b in befehle[1:])
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} #70 Reproduktion: Armfreigabe + Posen + Zebra 0,30 m -> Halt ohne Armbefehl "
      f"({[b['arm'] for b in befehle if b['arm']]})")


def zebra_lauf(n, **w):
    """Zebrastreifen in 0,30 m mit Armfreigabe und Posen; n Zyklen mit Wahrnehmung w. Rueckgabe: alle Befehle."""
    lauf = Lauf(arm_erlaubt=True, posen=POSEN)
    lauf.schritt(1, zebra={'abstand': 0.3}, **FREI)
    return lauf, [lauf.schritt(1, zebra={'abstand': 0.3}, **w) for _ in range(n)]


# negativ: ohne LiDAR-Daten (nur Kamera, leere Objektliste) -> Zeit allein gibt nicht frei
lauf, folge = zebra_lauf(200)
ok = all(x['aktion'] == 'stopp' and not x['arm'] for x in folge) and 'keine LiDAR-Daten' in folge[-1]['grund']
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} #70 ohne LiDAR-Daten am Ueberweg -> bleibt stehen ({folge[-1]['grund']})")
# negativ: LiDAR nur bei jedem zweiten Bild -> keine lueckenlose Beobachtung, bleibt stehen
lauf = Lauf(arm_erlaubt=True, posen=POSEN)
lauf.schritt(1, zebra={'abstand': 0.3}, **FREI)
folge = [lauf.schritt(1, zebra={'abstand': 0.3}, **(FREI if k % 2 else {})) for k in range(200)]
ok = all(x['aktion'] == 'stopp' for x in folge)
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} #70 LiDAR mit Luecken -> bleibt stehen ({folge[-1]['grund']})")
# negativ: keine neuen Bilder (Bildnummer bleibt, Aufnahmezeit frisch) -> bleibt stehen
lauf = Lauf(arm_erlaubt=True, posen=POSEN)
lauf.schritt(1, zebra={'abstand': 0.3}, **FREI)
nr = lauf.nr
folge = [lauf.schritt(1, zebra={'abstand': 0.3}, bild_nr=nr, bild_zeit=lauf.t + 0.1, **FREI) for _ in range(200)]
ok = all(x['aktion'] == 'stopp' and not x['arm'] for x in folge) and 'zu wenige neue Kamerabilder' in folge[-1]['grund']
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} #70 keine neuen Kamerabilder -> bleibt stehen ({folge[-1]['grund']})")
# negativ: veraltete Bilder (neue Nummer, alte Aufnahmezeit) -> bleibt stehen
lauf = Lauf(arm_erlaubt=True, posen=POSEN)
lauf.schritt(1, zebra={'abstand': 0.3}, **FREI)
t0 = lauf.t
folge = [lauf.schritt(1, zebra={'abstand': 0.3}, bild_zeit=t0, **FREI) for _ in range(200)]
ok = all(x['aktion'] == 'stopp' and not x['arm'] for x in folge)
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} #70 veraltete Kamerabilder -> bleibt stehen ({folge[-1]['grund']})")
# negativ (Codex-Review PR #158): frisch ausgewertet, aber alte oder fehlende AUFNAHME -> bleibt stehen
for name, aufnahme in (('Aufnahme 3 s alt', lambda lauf: lauf.t + 0.1 - 3.0), ('Aufnahme fehlt', lambda lauf: None)):
    lauf = Lauf(arm_erlaubt=True, posen=POSEN)
    lauf.schritt(1, zebra={'abstand': 0.3}, **FREI)
    folge = [lauf.schritt(1, zebra={'abstand': 0.3}, aufnahme=aufnahme(lauf), **FREI) for _ in range(200)]
    ok = all(x['aktion'] == 'stopp' for x in folge) and 'Aufnahmezeit' in folge[-1]['grund']
    fehler += not ok
    print(f"{'OK  ' if ok else 'FEHLER'} #70 {name} (Auswertung frisch) -> bleibt stehen ({folge[-1]['grund']})")
# negativ (Codex-Review PR #158): STOPP/TEST waehrend der Beobachtung -> Ablauf endet nicht im Stillstand,
# nach START wird der Ueberweg neu beobachtet (nicht gesperrt/uebersprungen)
lauf = Lauf(arm_erlaubt=True, posen=POSEN)
lauf.schritt(1, zebra={'abstand': 0.3}, **FREI)
lauf.e.fahrt_aktiv = False
lauf.schritt(200, **FREI)
ok = lauf.e.ablauf is not None and lauf.e.ablauf.name == 'zebra' and not lauf.e.zebra_gesperrt
lauf.e.fahrt_aktiv = True
nach = [lauf.schritt(1, **FREI) for _ in range(60)]
erst = next((i for i, x in enumerate(nach) if x['aktion'] == 'fahren'), None)
ok = ok and erst is not None and erst * 0.1 >= 0.5 + STANDARD['zebra_schauen']
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} #70 STOPP am Zebrastreifen -> nach START neu beobachtet (frei nach {erst} Zyklen)")
# direkt am Ablauf (ohne den Frische-Halt des Entscheiders davor): alte Bilder, Kamera nicht vorne, keine neuen
# Bilder geben nie frei; gueltige freie Beobachtung gibt frei. Nie ein Armbefehl.
def ablauf_lauf(n, w_von):
    a = Zebrastreifen(0.0, STANDARD, 0.3)
    bs = [a.schritt(0.0, {})]
    for k in range(1, n + 1):
        t = 0.1 * k
        b = a.schritt(t, w_von(k, t))
        bs.append(b)
        if b is None:
            break
    return a, bs


faelle = {'alt': lambda k, t: dict(bild_nr=k, bild_zeit=t - 2.0, objekte=[], **FREI),
          'kamera weg': lambda k, t: dict(bild_nr=k, bild_zeit=t, aufnahme=t, objekte=[], kamera_vorne=False, **FREI),
          'kein neues Bild': lambda k, t: dict(bild_nr=1, bild_zeit=t, objekte=[], **FREI),
          'leer ohne LiDAR': lambda k, t: dict(bild_nr=k, bild_zeit=t, aufnahme=t, objekte=[])}
for name, w_von in faelle.items():
    a, bs = ablauf_lauf(300, w_von)
    ok = bs[-1] is not None and a.ergebnis is None and not any(b['arm'] for b in bs if b)
    ok = ok and a.braucht_arm is False and a.arm_bewegt is False
    fehler += not ok
    print(f"{'OK  ' if ok else 'FEHLER'} #70 Ablauf direkt, {name} -> keine Freigabe ({bs[-1]['grund'] if bs[-1] else 'frei!'})")
a, bs = ablauf_lauf(300, lambda k, t: dict(bild_nr=k, bild_zeit=t, aufnahme=t, objekte=[], **FREI))
ok = bs[-1] is None and a.ergebnis == 'ok' and a.bilder >= STANDARD['anschauen_bilder']
ok = ok and not any(b['arm'] for b in bs if b)
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} #70 Ablauf direkt, gueltige freie Beobachtung -> frei ({a.bilder} Bilder)")
# positiv im ganzen Entscheider: gueltige freie Beobachtung mit LiDAR-Punkten (lidar_xy) -> weiter, ohne Arm
lauf, folge = zebra_lauf(80, lidar_xy=wand)
ok = folge[-1]['aktion'] == 'fahren' and not any(x['arm'] for x in folge)
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} #70 gueltige freie Beobachtung (LiDAR-Punkte) -> weiter ohne Arm ({folge[-1]['grund']})")
# Codex-Review PR #154: Ausfall WAEHREND des Beobachtens (Entscheider haelt vorher, ruft den Ablauf nicht auf) ->
# gezaehlte Bilder verfallen; nach der Rueckkehr braucht er wieder anschauen_bilder neue gueltige Bilder
for name, ausfall in (('LiDAR-Ausfall', lambda lauf: dict(lidar=None)),
                      ('keine frischen Bilder', lambda lauf: dict(bild_zeit=lauf.t - 3.0)),
                      ('Notbremse', lambda lauf: dict(lidar=0.05))):
    lauf = Lauf(arm_erlaubt=True, posen=POSEN)
    lauf.schritt(1, zebra={'abstand': 0.3}, **FREI)
    lauf.schritt(9, zebra={'abstand': 0.3}, **FREI)                   # 0,5 s Halt + 4 gueltige Bilder
    vorher = lauf.e.ablauf.bilder if lauf.e.ablauf else -1
    for _ in range(30):
        lauf.schritt(1, zebra={'abstand': 0.3}, **dict(FREI, **ausfall(lauf)))
    nach = [lauf.schritt(1, zebra={'abstand': 0.3}, **FREI) for _ in range(20)]
    erst = next((i for i, x in enumerate(nach) if x['aktion'] == 'fahren'), None)
    ok = 0 < vorher < STANDARD['anschauen_bilder'] and erst is not None and erst + 1 >= STANDARD['anschauen_bilder']
    ok = ok and not any(x['arm'] for x in nach)
    fehler += not ok
    print(f"{'OK  ' if ok else 'FEHLER'} #70 {name} beim Beobachten -> Zaehlung neu ({vorher} Bilder verfallen, "
          f"frei erst im {erst + 1 if erst is not None else '-'}. neuen Zyklus)")
# Armschalter waehrend des Halts aus: Zebrastreifen bleibt (kein Arm-Ablauf), haelt weiter bis frei
lauf = Lauf(arm_erlaubt=True, posen=POSEN)
lauf.schritt(3, zebra={'abstand': 0.3}, **FREI)
lauf.e.arm_freigabe = False
b = lauf.schritt(1, zebra={'abstand': 0.3}, **FREI)
ok = b['aktion'] == 'stopp' and lauf.e.ablauf is not None and lauf.e.ablauf.name == 'zebra'
ok = ok and lauf.schritt(80, zebra={'abstand': 0.3}, **FREI)['aktion'] == 'fahren'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} #70 Armschalter am Zebrastreifen aus -> haelt weiter, dann weiter wenn frei")

# ---------------- Einbahnstrasse ----------------
l = Lauf()
pruefe('Einfahrt verboten 1 Bild -> noch nichts', l.schritt(1, einfahrt_verboten=True), 'fahren')
pruefe('Einfahrt verboten 2 Bilder -> anhalten', l.schritt(1, einfahrt_verboten=True), 'stopp')
l2 = Lauf()
l2.schritt(1, einfahrt_verboten=True)
l2.schritt(1)                                   # ein Bild ohne Schild dazwischen (KI langsam, unscharf)
pruefe('Einfahrt verboten mit Luecke (ja, nein, ja) -> trotzdem anhalten', l2.schritt(1, einfahrt_verboten=True), 'stopp')
b = l.schritt(10, gier=0.0)
ok = b['aktion'] == 'manoever' and b['manoever']['dreh'] > 0
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} dreht auf der Stelle: {b['grund']}")
VORNE = {'kamera': True, 'kamera_quer': 0.01, 'kamera_kurs': 0.05}
pruefe('nach 100 Grad noch nicht fertig', l.schritt(1, gier=math.radians(100), linie=VORNE), 'manoever')
pruefe('160 Grad, Linie noch schraeg (40 Grad) -> weiter drehen',
       l.schritt(1, gier=math.radians(160), linie=dict(VORNE, kamera_kurs=math.radians(40))), 'manoever')
pruefe('170 Grad + Linie mittig vorne -> fertig, faehrt', l.schritt(1, gier=math.radians(170), linie=VORNE), 'fahren')
l = Lauf()
l.schritt(2, einfahrt_verboten=True)
l.schritt(10, gier=0.0)
pruefe('Gedaechtnis: 170 Grad, Linie unter dem Roboter gerade -> fertig',
       l.schritt(1, gier=math.radians(170), linie={'kamera': False, 'quer': 0.01, 'kurs': 0.1}), 'fahren')
pruefe('Schild noch sichtbar -> nicht nochmal wenden', l.schritt(5, gier=math.radians(170), einfahrt_verboten=True), 'fahren')

# ---------------- Wegraeumen ----------------
GREIF = STANDARD['greif_vor']
# etwas weiter als die Greifweite, aber naeher als tiefe_halt (sonst haelt er gar nicht an)
WUERFEL = {'vor': min(GREIF + 0.03, STANDARD['tiefe_halt'] - 0.01), 'seite': 0.02, 'breite': 0.045, 'hoehe': 0.045, 'quelle': 'tiefe'}
NAH = dict(WUERFEL, vor=GREIF - 0.03)


def wegraeumen(lauf, n, objekt_bis_greifen=WUERFEL, danach=None, **w):
    """Simuliert die Welt grob: Wuerfel kommt naeher, wenn der Roboter vorfaehrt; nach dem Greifen weg."""
    obj, arme, gruende, letzter = dict(objekt_bis_greifen), [], [], None
    for _ in range(n):
        letzter = lauf.schritt(1, objekt=obj, **w)
        m = letzter.get('manoever')
        if m and obj:
            obj = dict(obj, vor=obj['vor'] - m['lin'] * 0.1, seite=obj['seite'] - m['quer'] * 0.1)
        a = letzter['arm']
        if a and not isinstance(a, str) and a.get('winkel'):
            arme.append(a['winkel'])
            if a['winkel'][5] == 130:            # zugegriffen -> Wuerfel ist weg
                obj = danach
        gruende.append(letzter['grund'])
    return arme, letzter, gruende


l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
b = l.schritt(1, objekt=WUERFEL)
pruefe('Wuerfel (Tiefenkamera) -> anhalten und anschauen', b, 'stopp')
arme, b, gruende = wegraeumen(l, 400)
ok = len(arme) == 9 and arme[-1] == POSEN['fahrstellung'] and any('Greifweite' in g for g in gruende)
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} angeschaut, in Greifweite gefahren, {len(arme)} berechnete Armbewegungen "
      f"(keine eingelernten Posen), zurueck in Fahrstellung")
ok = any('pruefe, ob der Weg frei' in g for g in gruende)
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} nach dem Wegraeumen wird der Weg geprueft")
pruefe('Weg frei (geprueft) -> weiter', b, 'fahren')
ereignisse = [t for _, t, _ in l.e.ereignisse]
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
l.schritt(1, objekt=NAH)
arme, b, gruende = wegraeumen(l, 1000, NAH, danach=NAH)    # liegt nach dem Greifen immer noch da
ok = len(arme) == 9 * STANDARD['versuche'] and b['aktion'] == 'stopp'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} liegt danach noch da -> {STANDARD['versuche']} Versuche, dann aufgeben und warten "
      f"({len(arme)} Armbewegungen, {b['grund']})")
pruefe('kein dritter Versuch, solange er da liegt', l.schritt(30, objekt=NAH), 'stopp', None)
pruefe('Wuerfel weg -> weiter', l.schritt(30), 'fahren')
# Zu nah fuer die Kamera: Pruefblick (Kamera nach unten) statt zurueckfahren, dort messen, greifen und kontrollieren
PRUEF_POSEN = dict(POSEN, pruefblick=[90, 120, 10, 0, 90, 30])
PRUEF_OBJ = dict(WUERFEL, vor=0.18, blick='pruef', blick_winkel=PRUEF_POSEN['pruefblick'])
l = Lauf(arm_erlaubt=True, posen=PRUEF_POSEN, planer=planer)
pose, gegriffen, posen_folge, b = 'fahrstellung', False, [], None
for _ in range(400):
    da = not gegriffen
    b = l.schritt(1, lidar=0.18 if da else float('inf'),
                  objekt=PRUEF_OBJ if da and pose == 'pruefblick' else None)
    a = b['arm']
    if isinstance(a, dict) and a.get('pose'):
        pose = a['pose']
        posen_folge.append(pose)
    elif a == 'fahrstellung':
        pose = 'fahrstellung'
        posen_folge.append(pose)
    elif isinstance(a, dict) and a.get('winkel'):
        pose = 'bewegt'
        gegriffen = gegriffen or a['winkel'][5] == 130
    if b['aktion'] == 'fahren':
        break
texte = [t for _, t, _ in l.e.ereignisse]
ok = (posen_folge[:1] == ['pruefblick'] and gegriffen and posen_folge.count('pruefblick') >= 2
      and any(t.startswith('Hindernis im Pruefblick gesehen') for t in texte)
      and not any('fahre etwas zurueck' in t for t in texte) and b['aktion'] == 'fahren')
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} zu nah -> Pruefblick, dort vermessen, gegriffen, im Pruefblick kontrolliert, "
      f"weiter (Posen {posen_folge}, {b['grund']})")
l = Lauf(arm_erlaubt=True, posen=PRUEF_POSEN, planer=planer)
gruende = []
for _ in range(120):
    b = l.schritt(1, lidar=0.18)
    gruende.append(b['grund'])
texte = [t for _, t, _ in l.e.ereignisse]
ok = (sum('Pruefblick: nichts gesehen' in t for t in texte) == 1 and any('fahre etwas zurueck' in g for g in gruende))
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Pruefblick sieht nichts -> Kamera zurueck, dann wie bisher etwas zurueck "
      f"({b['grund']})")

# Keine Ablagestelle: schon VOR dem Heranfahren erkennen und gar nicht erst losfahren
l = Lauf(arm_erlaubt=True, posen=POSEN,
         planer=lambda o, s: {'fehler': 'keine erreichbare Ablagestelle (Test)', 'ablage_fehlt': True})
l.schritt(1, objekt=WUERFEL)
arme, b, gruende = wegraeumen(l, 60)
ok = (not arme and not any('Greifweite' in g for g in gruende) and b['aktion'] == 'stopp'
      and any('vor dem Heranfahren' in t for _, t, _ in l.e.ereignisse))
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} keine Ablagestelle -> vorher erkannt, kein Manoever ({b['grund']})")
gesehen = []
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=lambda o, s: gesehen.append(o) or planer(o, s))
l.schritt(1, objekt=WUERFEL)
wegraeumen(l, 400, lidar_xy=np.array([[0.10, 0.25], [0.30, 0.0]]))
ok = (len(gesehen) >= 2 and gesehen[0].get('belegt') is not None and len(gesehen[0]['belegt']) == 1
      and abs(gesehen[0]['vor'] - STANDARD['greif_vor']) < 1e-9)
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Vorpruefung rechnet fuer die Greifweite und bekommt LiDAR-Punkte neben der Strasse")

l = Lauf(arm_erlaubt=True, posen=POSEN, planer=lambda o, s: {'fehler': 'Test: nicht erreichbar'})
l.schritt(1, objekt=NAH)
arme, b, gruende = wegraeumen(l, 100, NAH, danach=NAH)
pruefe('Arm erreicht es nicht -> keine Bewegung, warten', b, 'stopp', None)
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
b = l.schritt(30, objekt=WUERFEL, objekte=[{'name': 'Person', 'im_weg': False}])
pruefe('Person in Sicht -> nie anfassen, nur warten', b, 'stopp', None)
# Person (z. B. Hand beim Hinlegen) nur beim Anschauen in Sicht, Hindernis bleibt liegen: nach ein paar Sekunden
# ohne Person schaut er nochmal hin und raeumt weg (vorher wartete er, bis der Weg frei war - also ewig)
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
l.schritt(15, objekt=NAH, objekte=[{'name': 'Person', 'im_weg': False}])
war_person = (l.e.bestaetigt or '').startswith('Hindernis ist Person')
arme, b, _ = wegraeumen(l, 120, NAH)
ok = war_person and len(arme) > 0
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Person beim Anschauen, dann weg -> schaut nochmal hin, raeumt weg ({len(arme)} Arm-Befehle)")
# nur EIN Bild mit Person (Fehlerkennung) blockiert nicht
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
l.schritt(3, objekt=NAH)                                              # Anschauen laeuft ...
l.schritt(1, objekt=NAH, objekte=[{'name': 'Person', 'im_weg': False}])   # ... ein Bild mit "Person"
arme, b, _ = wegraeumen(l, 60, NAH)
ok = len(arme) > 0 and not (l.e.bestaetigt or '').startswith('Hindernis ist Person')
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} nur ein Bild mit Person (Fehlerkennung) -> raeumt trotzdem weg ({len(arme)} Arm-Befehle)")
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
pruefe('zu breit (20 cm) -> warten statt greifen', l.schritt(30, objekt=dict(WUERFEL, breite=0.2)), 'stopp', None)
l = Lauf(arm_erlaubt=False, posen=POSEN, planer=None)
b = l.schritt(30, objekt=WUERFEL)
pruefe('ohne Arm-Freigabe -> Kamera bestaetigt, warten', b, 'stopp', None)
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
pruefe('LiDAR 15 cm, Kamera sieht nichts -> etwas zurueck, damit die Kamera es sieht',
       l.schritt(15, lidar=0.15, lidar_hinten=1.0), 'manoever')

# ---------------- Wegraeumen: Arm reicht nicht hin, Lernen, klare Gruende ----------------
M3PRO = armlib.Kinematik()              # Masse des echten Arms (Standard): reicht nicht bis 27 cm
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=lambda o, s: planer(o, s, M3PRO))
l.schritt(1, objekt=WUERFEL)
arme, b, gruende = wegraeumen(l, 600, lidar_hinten=1.0)
ok = (any('naeher heran' in g for g in gruende) and len(arme) == 9 and any('fahre zurueck' in g for g in gruende)
      and b['aktion'] == 'fahren')
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Arm reicht nicht hin -> blind naeher, greifen ({len(arme)} Bewegungen), "
      f"wieder zurueck, pruefen, weiter ({b['grund']})")

meldungen = []


def merke(plan, erfolg):
    meldungen.append(erfolg)
    return f'Greifversuch {len(meldungen)}: {"Erfolg" if erfolg else "daneben"}'


def lernplaner(o, s):
    p = planer(o, s)
    p['lernen'] = {'modell': 'test', 'a': [0, 0, 0], 'obj': o}
    return p


l = Lauf(arm_erlaubt=True, posen=POSEN, planer=lernplaner, rueckmeldung=merke)
l.schritt(1, objekt=WUERFEL)
wegraeumen(l, 400)
texte = [t for _, t, _ in l.e.ereignisse]
ok = meldungen == [True] and any(t.startswith('Greifversuch 1: Erfolg') for t in texte)
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Erfolg wird ans Lernen gemeldet und als Ereignis gezeigt: {meldungen}")
meldungen.clear()
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=lernplaner, rueckmeldung=merke)
l.schritt(1, objekt=NAH)
wegraeumen(l, 1000, NAH, danach=NAH)
ok = meldungen == [False] * STANDARD['versuche']
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} liegt danach noch da -> alle Fehlversuche ans Lernen gemeldet: {meldungen}")

l = Lauf(arm_erlaubt=False, posen=POSEN, planer=planer)
b = l.schritt(30, objekt=WUERFEL)
ok = b['aktion'] == 'stopp' and any('Panel -> Arm' in t for _, t, _ in l.e.ereignisse)
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Arm ausgeschaltet -> Ereignis sagt klar warum: "
      f"{[t for _, t, _ in l.e.ereignisse if 'raeume nicht' in t]}")
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
l.e.fahrt_aktiv = False
b = l.schritt(30, objekt=WUERFEL)
ok = any('nur bei START' in t for _, t, _ in l.e.ereignisse)
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} nur TEST -> Grund 'nur bei START' im Ereignis")

# Person taucht waehrend des Greifens auf -> Arm und Roboter halten still (kein Armbefehl, Greifer bleibt),
# nach 2 s ohne Person geht es weiter
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
l.schritt(1, objekt=NAH)
arme, b, _ = wegraeumen(l, 45, NAH)
ok_vorher = len(arme) > 0
PERSON = [{'name': 'Person', 'im_weg': False}]
waehrend = [l.schritt(1, objekt=NAH, objekte=PERSON) for _ in range(40)]       # 4 s Person in Sicht
ok_still = all(x['aktion'] == 'stopp' and not x['arm'] for x in waehrend) and l.e.ablauf is not None
arme2, b, _ = wegraeumen(l, 300, NAH)
ok = ok_vorher and ok_still and len(arme2) > 0 and b['aktion'] == 'fahren'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Person waehrend des Greifens -> Arm haelt still, danach macht er weiter "
      f"({len(arme2)} weitere Armbewegungen, dann {b['aktion']})")
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
l.schritt(1, objekt=NAH)
wegraeumen(l, 45, NAH)
l.e.arm_freigabe = False                         # Panel: Haken aus, waehrend der Arm unten ist
b = l.schritt(1, objekt=NAH)
b2 = l.schritt(1)
ok = (l.e.ablauf is None or not l.e.ablauf.braucht_arm) and 'fahrstellung' in (b['arm'], b2['arm'])
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Arm-Freigabe waehrend des Greifens ausgeschaltet -> Abbruch, Arm zurueck in Fahrstellung")

# Notbremse waehrend des Greifens: pausieren, nach 5 s abbrechen
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
l.schritt(1, objekt=NAH)
arme, b, _ = wegraeumen(l, 45, NAH)
arme2, b, _ = [], l.schritt(30, objekt=NAH, lidar=0.08), None
ok1 = b['arm'] is None and l.e.ablauf is not None          # 3 s: nur Pause
b = l.schritt(30, objekt=NAH, lidar=0.08)
ok2 = l.e.ablauf is None
b = l.schritt(2, objekt=NAH)
ok3 = b['arm'] == 'fahrstellung' or l.e.arm_warten_bis > l.t
ok = ok1 and ok2 and ok3
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Notbremse beim Greifen: erst Pause, nach 5 s Abbruch, danach Arm zurueck")

# ---------------- Umschauen fuer die Karte ----------------
l = Lauf(arm_erlaubt=True, posen=POSEN)
l.schritt(2)
print('     ', l.e.kommando(l.t, 'umschauen'))
arme, b = arm_befehle(l, 90)
ok = arme == ['blick_links', 'blick_rechts', 'fahrstellung'] and b['aktion'] == 'fahren'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Umschauen auf Wunsch: {arme}, danach {b['aktion']}")
l = Lauf()
ok = 'geht nicht' in l.e.kommando(l.t, 'umschauen')
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Umschauen ohne Arm-Freigabe wird abgelehnt")

# ---------------- Wegraeumen: Sicherheitsregeln ----------------
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
pruefe('Gegenstand am Strassenrand (14 cm neben der Linie) -> nicht greifen, warten',
       l.schritt(30, objekt=dict(WUERFEL, quer=0.14)), 'stopp', None)
# Projektinhaber 21.10.: bis 12 cm neben der Linie (Kurve, aber im Fahrschlauch) wird weggeraeumt
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
l.schritt(1, objekt=dict(WUERFEL, quer=0.11))
arme, b, _ = wegraeumen(l, 400, dict(WUERFEL, quer=0.11))
ok = len(arme) == 9 and b['aktion'] == 'fahren'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Gegenstand in der Kurve 11 cm neben der Linie -> wird weggeraeumt ({len(arme)} Arm-Befehle)")
# RM02 21.10.: am Rand bestaetigt, liegt aber knapp hinter tiefe_halt (37 cm) -> fuhr wieder an und blieb dann mit
# "wegnehmen, dann STOPP und START" stehen. Jetzt: wartet davor und faehrt von selbst weiter, wenn es weg ist.
RAND = dict(WUERFEL, vor=0.34, quer=0.14)
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
s = {'strecke': 0.0}
l.schritt(25, objekt=RAND, **s)
folge = [l.schritt(1, objekt=dict(RAND, vor=0.37), **s) for _ in range(30)]
ok1 = all(x['aktion'] == 'stopp' and 'STOPP und START' not in x['grund'] for x in folge)
folge2 = [l.schritt(1, objekt=dict(RAND, vor=0.37) if k % 3 else None, **s) for k in range(30)]   # flackert
ok2 = all(x['aktion'] == 'stopp' for x in folge2)
b = l.schritt(30, **s)                                    # weggenommen
ok = ok1 and ok2 and b['aktion'] == 'fahren'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} am Rand bestaetigt, 37 cm voraus -> wartet (auch wenn die Kamera flackert), "
      f"weggenommen -> faehrt ohne START weiter ({folge[-1]['grund']} / {b['grund']})")
# Codex-Review: bestaetigt, dann ein leeres Bild und die KI haengt (gleiches Bild) -> nicht nach frei_zeit losfahren
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
l.schritt(25, objekt=RAND, strecke=0.0)
l.schritt(5, objekt=dict(RAND, vor=0.37), strecke=0.0)
l.schritt(1, strecke=0.0)                                 # ein Bild ohne Hindernis ...
haengt = []
for k in range(14):                                       # ... dann 1,4 s kein neues Bild (unter ki_max_alter)
    l.t += 0.1
    haengt.append(l.e.update(l.t, {'bild_nr': l.nr, 'bild_zeit': l.t - 0.1 * (k + 1), 'objekte': [],
                                   'lidar': float('inf'), 'tiefe_hindernis': False, 'strecke': 0.0}))
b = l.schritt(5, strecke=0.0)                             # wieder frische Bilder, frei -> weiter
ok = all(x['aktion'] == 'stopp' for x in haengt) and b['aktion'] == 'fahren'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} bestaetigt, KI haengt nach einem leeren Bild -> faehrt nicht los, erst mit "
      f"frischen Bildern ({haengt[-1]['grund']} / {b['grund']})")
# Codex-Review: bestaetigt, ein leeres Tiefenbild, dann steht der Tiefenstrom (Farbbilder laufen) -> nicht losfahren
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
l.schritt(25, objekt=RAND, strecke=0.0, tiefe_nr=1)
for k in range(5):
    l.schritt(1, objekt=dict(RAND, vor=0.37), strecke=0.0, tiefe_nr=2 + k)
folge = [l.schritt(1, strecke=0.0, tiefe_nr=10) for _ in range(30)]     # dasselbe leere Tiefenbild, 3 s lang
ok = all(x['aktion'] == 'stopp' for x in folge)
nr = iter(range(11, 100))
b = [l.schritt(1, strecke=0.0, tiefe_nr=next(nr)) for _ in range(15)][-1]   # neue Tiefenbilder, frei -> weiter
ok = ok and b['aktion'] == 'fahren'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} bestaetigt, Tiefenbild steht (nur Farbbilder neu) -> faehrt nicht los, erst mit "
      f"neuen Tiefenbildern ({folge[-1]['grund']} / {b['grund']})")
# RM02 21.10.: niedriger Wuerfel (3 cm) verschwindet beim Heranfahren unter dem Blickfeld -> "aus den Augen verloren".
# Jetzt: in Greifweite laut Radzaehler mit der letzten Messung greifen, danach zurueck und kontrollieren.
def lauf_28():
    """Blind-Greifen-Tests mit ihrer festen Welt-Geometrie: Greifweite 28 cm, Kamera verliert den niedrigen Wuerfel
    unter 30 cm (wie bis 21.10.). Geprueft wird die Logik, nicht der Standardabstand."""
    lauf = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
    lauf.e.c['greif_vor'] = 0.28
    return lauf


NIEDRIG = dict(WUERFEL, vor=0.34, seite=0.0, breite=0.03, hoehe=0.03)
WEG_GERADE = [(0.05 * k, 0.0) for k in range(1, 12)]     # Linie gerade voraus (blind greifen braucht den Winkel)
l = lauf_28()
welt = {'vor': 0.34, 'strecke': 0.0, 'da': True}
arme, gruende, b = [], [], None
for _ in range(600):
    sicht = welt['da'] and welt['vor'] > 0.30            # unter 30 cm sieht die Kamera ihn nicht mehr
    b = l.schritt(1, objekt=dict(NIEDRIG, vor=welt['vor']) if sicht else None, strecke=welt['strecke'],
                  strecke_gemessen=True, lidar_hinten=1.0, weg=WEG_GERADE)
    m = b.get('manoever')
    if m:
        welt['vor'] -= m['lin'] * 0.1
        welt['strecke'] += m['lin'] * 0.1
    a = b['arm']
    if a and not isinstance(a, str) and a.get('winkel'):
        arme.append(a['winkel'])
        if a['winkel'][5] == 130:
            welt['da'] = False
    gruende.append(b['grund'])
    if b['aktion'] == 'fahren':
        break
texte = [t for _, t, _ in l.e.ereignisse]
ok = (len(arme) >= 9 and any('greife nach der letzten Messung' in t for t in texte)
      and any('fahre zurueck, damit die Kamera' in g for g in gruende) and welt['vor'] > 0.30
      and not any('aus den Augen verloren' in t for t in texte) and b['aktion'] == 'fahren')
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} niedriger Wuerfel verschwindet beim Heranfahren -> greift nach Radzaehler, faehrt "
      f"zur Kontrolle zurueck ({welt['vor'] * 100:.0f} cm), weiter ({b['grund']})")
# Codex-Review: zuletzt schon in Greifweite gesehen (kaum vorgefahren) -> trotzdem zur Kontrolle zurueck
l = lauf_28()
welt = {'vor': 0.34, 'strecke': 0.0, 'da': True, 'nah': 0}
gruende, vorgefahren = [], []
for k in range(600):
    # KI langsam (beim Heranfahren nur jedes 4. Bild), 29-29,6 cm nicht zu sehen, darunter nur noch EIN Bild:
    # zuletzt schon in Greifweite gesehen, aber nicht 3x ruhig -> blind, fast ohne Fahrstrecke seit der Messung
    a = l.e.ablauf
    heran = a is not None and a.phase == 'abstand'
    sicht = welt['da'] and ((not heran or k % 4 == 0) and welt['vor'] > 0.296
                            or heran and welt['vor'] <= 0.2905 and welt['nah'] < 1)
    if sicht and heran and welt['vor'] <= 0.2905:
        welt['nah'] += 1
    if a is not None and a.phase == 'planen':
        vorgefahren.append(a.vorgefahren)
    b = l.schritt(1, objekt=dict(NIEDRIG, vor=welt['vor']) if sicht else None, strecke=welt['strecke'],
                  strecke_gemessen=True, lidar_hinten=1.0, weg=WEG_GERADE)
    m = b.get('manoever')
    if m:
        welt['vor'] -= m['lin'] * 0.1
        welt['strecke'] += m['lin'] * 0.1
    a = b['arm']
    if a and not isinstance(a, str) and a.get('winkel') and a['winkel'][5] == 130:
        welt['da'] = False
    gruende.append(b['grund'])
    if b['aktion'] == 'fahren':
        break
texte = [t for _, t, _ in l.e.ereignisse]
ok = (any('greife nach der letzten Messung' in t for t in texte) and vorgefahren and vorgefahren[0] <= 0.005
      and any('fahre zurueck, damit die Kamera' in g for g in gruende) and b['aktion'] == 'fahren')
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} blind gegriffen, kaum vorgefahren ({(vorgefahren or [0])[0] * 100:.1f} cm) "
      f"-> faehrt trotzdem zur Kontrolle zurueck ({welt['vor'] * 100:.1f} cm)")
# Codex-Review: beim letzten Sehen noch 6 cm seitlich -> nicht blind greifen (wuerde schraeg/daneben fassen)
l = lauf_28()
welt = {'vor': 0.34, 'strecke': 0.0}
for _ in range(200):
    sicht = welt['vor'] > 0.30
    b = l.schritt(1, objekt=dict(NIEDRIG, vor=welt['vor'], seite=0.06) if sicht else None, strecke=welt['strecke'],
                  strecke_gemessen=True)
    m = b.get('manoever')
    if m:
        welt['vor'] -= m['lin'] * 0.1
        welt['strecke'] += m['lin'] * 0.1
texte = [t for _, t, _ in l.e.ereignisse]
ok = not any('greife nach der letzten Messung' in t for t in texte) and b['aktion'] != 'fahren'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} beim letzten Sehen nicht ausgerichtet -> greift nicht blind ({b['grund']})")
# Review PR #78: Strecke nur aus Fahrbefehlen geschaetzt (keine Odometrie) -> nicht blind greifen
l = lauf_28()
welt = {'vor': 0.34, 'strecke': 0.0}
for _ in range(200):
    sicht = welt['vor'] > 0.30
    b = l.schritt(1, objekt=dict(NIEDRIG, vor=welt['vor']) if sicht else None, strecke=welt['strecke'],
                  strecke_gemessen=False)
    m = b.get('manoever')
    if m:
        welt['vor'] -= m['lin'] * 0.1
        welt['strecke'] += m['lin'] * 0.1
texte = [t for _, t, _ in l.e.ereignisse]
ok = not any('greife nach der letzten Messung' in t for t in texte) and b['aktion'] != 'fahren'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Strecke nur geschaetzt (keine Radzaehler) -> greift nicht blind ({b['grund']})")
# Codex-Review: Radzaehler fallen zwischen Sichtung und Greifweite kurz aus (Strecke dort aus Fahrbefehlen geschaetzt),
# danach wieder frisch -> trotzdem nicht blind greifen
l = lauf_28()
welt = {'vor': 0.34, 'strecke': 0.0, 'abschnitt': 1}
for _ in range(200):
    sicht = welt['vor'] > 0.30
    if not sicht:
        welt['abschnitt'] = 2                      # Luecke nach der letzten Sichtung
    b = l.schritt(1, objekt=dict(NIEDRIG, vor=welt['vor']) if sicht else None, strecke=welt['strecke'],
                  strecke_gemessen=True, odom_abschnitt=welt['abschnitt'])
    m = b.get('manoever')
    if m:
        welt['vor'] -= m['lin'] * 0.1
        welt['strecke'] += m['lin'] * 0.1
texte = [t for _, t, _ in l.e.ereignisse]
ok = not any('greife nach der letzten Messung' in t for t in texte) and b['aktion'] != 'fahren'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Radzaehler-Luecke seit der Sichtung -> greift nicht blind ({b['grund']})")
# Codex-Review: KI liefert in Greifweite 2 s keine neuen Bilder (haengt) -> kein blindes Greifen ohne frische Bilder
l = lauf_28()
welt = {'vor': 0.34, 'strecke': 0.0}
for _ in range(400):
    b = l.schritt(1, objekt=dict(NIEDRIG, vor=welt['vor']), strecke=welt['strecke'], strecke_gemessen=True)
    m = b.get('manoever')
    if m:
        welt['vor'] -= m['lin'] * 0.1
        welt['strecke'] += m['lin'] * 0.1
    if l.e.ablauf is not None and l.e.ablauf.phase == 'abstand' and welt['vor'] < 0.295:
        break
haengt = []
for _ in range(14):                           # 1,4 s ohne neues Bild (unter ki_max_alter)
    l.t += 0.1
    haengt.append(l.e.update(l.t, {'bild_nr': l.nr, 'bild_zeit': l.t - 0.1 * len(haengt) - 0.1, 'objekte': [],
                                   'lidar': float('inf'), 'tiefe_hindernis': False, 'strecke': welt['strecke'],
                                   'strecke_gemessen': True, 'objekt': dict(NIEDRIG, vor=welt['vor'])}))
texte = [t for _, t, _ in l.e.ereignisse]
ok = (not any('greife nach der letzten Messung' in t for t in texte)
      and not any(x['arm'] for x in haengt))
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} KI haengt in Greifweite (keine neuen Bilder) -> greift nicht blind")
# Codex-Review: Linie (weg) faellt waehrend des Geradedrehens aus -> nicht als "gerade" werten und planen
SCHRAEG = [(0.05 * k * math.cos(math.radians(20)), 0.05 * k * math.sin(math.radians(20))) for k in range(1, 12)]
l = lauf_28()
l.schritt(1, objekt=dict(WUERFEL, vor=0.28, seite=0.0), weg=SCHRAEG)
l.schritt(20, objekt=dict(WUERFEL, vor=0.28, seite=0.0), weg=SCHRAEG)
l.schritt(20, objekt=dict(WUERFEL, vor=0.28, seite=0.0))        # Linie weg, Roboter steht noch schraeg
ok = l.e.ablauf is not None and l.e.ablauf.phase == 'abstand'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Linie faellt beim Geradedrehen aus -> plant nicht schraeg "
      f"({l.e.ablauf.phase if l.e.ablauf else None})")
# Codex-Review: Farbbilder kommen, Tiefenbild steht (dasselbe) -> zaehlt nur einmal als "leer", kein blindes Greifen
l = lauf_28()
welt = {'vor': 0.34, 'strecke': 0.0, 'tnr': 0}
for _ in range(200):
    sicht = welt['vor'] > 0.30
    if sicht:
        welt['tnr'] += 1                          # nur solange es zu sehen ist, kommen neue Tiefenbilder
    b = l.schritt(1, objekt=dict(NIEDRIG, vor=welt['vor']) if sicht else None, strecke=welt['strecke'],
                  strecke_gemessen=True, tiefe_nr=welt['tnr'])
    m = b.get('manoever')
    if m:
        welt['vor'] -= m['lin'] * 0.1
        welt['strecke'] += m['lin'] * 0.1
texte = [t for _, t, _ in l.e.ereignisse]
ok = not any('greife nach der letzten Messung' in t for t in texte) and b['aktion'] != 'fahren'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Tiefenbild steht (nur Farbbilder neu) -> greift nicht blind ({b['grund']})")
# Codex-Review: nach blindem Greifen steht der Tiefenstrom auf einem leeren Bild (Farbbilder laufen) -> Kontrolle
# darf daraus kein "frei" machen (Gegenstand liegt noch da, waere von der Kontrollstelle aus sichtbar)
l = lauf_28()
welt = {'vor': 0.34, 'strecke': 0.0, 'tnr': 0, 'steht': False}
aktionen = []
for _ in range(700):
    a = l.e.ablauf
    if a is not None and a.phase in ('rueckweg', 'kontrolle'):
        welt['steht'] = True                         # ab dem Rueckweg kommen keine neuen Tiefenbilder mehr
    if not welt['steht']:
        welt['tnr'] += 1
    sicht = welt['vor'] > 0.30 and not welt['steht']
    b = l.schritt(1, objekt=dict(NIEDRIG, vor=welt['vor']) if sicht else None, strecke=welt['strecke'],
                  strecke_gemessen=True, tiefe_nr=welt['tnr'], lidar_hinten=1.0,
                  weg=WEG_GERADE)
    m = b.get('manoever')
    if m:
        welt['vor'] -= m['lin'] * 0.1
        welt['strecke'] += m['lin'] * 0.1
    aktionen.append(b['aktion'])
texte = [t for _, t, _ in l.e.ereignisse]
ok = any('greife nach der letzten Messung' in t for t in texte) and 'fahren' not in aktionen
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} nach blindem Greifen steht der Tiefenstrom -> Kontrolle meldet nicht frei "
      f"({b['grund']})")
# Codex-Review: Strassenwinkel nie bekannt (keine Linie) -> mit Sicht greifen wie bisher, aber nicht blind
l = lauf_28()
welt = {'vor': 0.34, 'strecke': 0.0}
for _ in range(200):
    sicht = welt['vor'] > 0.30
    b = l.schritt(1, objekt=dict(NIEDRIG, vor=welt['vor']) if sicht else None, strecke=welt['strecke'],
                  strecke_gemessen=True)
    m = b.get('manoever')
    if m:
        welt['vor'] -= m['lin'] * 0.1
        welt['strecke'] += m['lin'] * 0.1
texte = [t for _, t, _ in l.e.ereignisse]
ok = not any('greife nach der letzten Messung' in t for t in texte) and b['aktion'] != 'fahren'
l = lauf_28()
welt = {'vor': 0.34, 'strecke': 0.0}
for _ in range(200):
    sicht = welt['vor'] > 0.30
    b = l.schritt(1, objekt=dict(NIEDRIG, vor=welt['vor']) if sicht else None, strecke=welt['strecke'],
                  strecke_gemessen=True, weg=WEG_GERADE)
    m = b.get('manoever')
    if m:
        welt['vor'] -= m['lin'] * 0.1
        welt['strecke'] += m['lin'] * 0.1
ok = ok and any('greife nach der letzten Messung' in t for _, t, _ in l.e.ereignisse)
# sehr schraeg (40 Grad, nicht plausibel zum Drehen) gilt nicht als gerade -> plant nicht
SEHR_SCHRAEG = [(0.05 * k * math.cos(math.radians(40)), 0.05 * k * math.sin(math.radians(40))) for k in range(1, 12)]
l = lauf_28()
l.schritt(30, objekt=dict(WUERFEL, vor=0.28, seite=0.0), weg=SEHR_SCHRAEG)
ok = ok and l.e.ablauf is not None and l.e.ablauf.phase == 'abstand'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Winkel unbekannt -> nicht blind, mit gerader Linie blind ok, 40 Grad -> plant nicht")
# ohne Radzaehler bleibt es beim Abbruch (blind greifen nur mit gemessener Strecke)
l = lauf_28()
l.schritt(15, objekt=dict(NIEDRIG, vor=0.29))
b = l.schritt(40)
ok = any('aus den Augen verloren' in t for _, t, _ in l.e.ereignisse) and b['aktion'] != 'fahren'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} ohne Radzaehler: aus den Augen verloren -> wartet, greift nicht blind ({b['grund']})")
# Seitlich versetzt (3 cm): faehrt seitlich mittig davor (vorher erst ab 3,6 cm, dann drehte der Arm schraeg)
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
obj, quer, seite_beim_planen = dict(WUERFEL, seite=0.03), [], None
for _ in range(200):
    b = l.schritt(1, objekt=obj)
    m = b.get('manoever')
    if m:
        quer.append(m['quer'])
        obj = dict(obj, vor=obj['vor'] - m['lin'] * 0.1, seite=obj['seite'] - m['quer'] * 0.1)
    if l.e.ablauf is not None and l.e.ablauf.phase == 'planen':
        seite_beim_planen = obj['seite']
        break
ok = any(q > 0 for q in quer) and seite_beim_planen is not None and abs(seite_beim_planen) <= STANDARD['greif_seite']
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} 3 cm seitlich -> faehrt seitlich davor, plant bei "
      f"{(seite_beim_planen or 0) * 100:+.1f} cm")
# Kurve: Strasse am Hindernis 20 Grad nach links -> dreht sich gerade, greift erst dann
WEG_KURVE = [(0.05 * k * math.cos(math.radians(20)), 0.05 * k * math.sin(math.radians(20))) for k in range(1, 12)]
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
l.schritt(1, objekt=dict(WUERFEL, vor=GREIF, seite=0.0), weg=WEG_KURVE)
folge = [l.schritt(1, objekt=dict(WUERFEL, vor=GREIF, seite=0.0), weg=WEG_KURVE) for _ in range(40)]
dreht = [x for x in folge if x.get('manoever') and x['manoever']['dreh'] > 0]
# RM02 21.10.: beim Drehen nicht zugleich vorfahren (sonst ist er in Greifweite, bevor er gerade steht)
ok = (bool(dreht) and all(x['manoever']['lin'] == 0.0 for x in dreht)
      and l.e.ablauf is not None and l.e.ablauf.phase == 'abstand')
l2 = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
l2.schritt(1, objekt=dict(WUERFEL, vor=GREIF, seite=0.05), weg=WEG_KURVE)
folge2 = [l2.schritt(1, objekt=dict(WUERFEL, vor=GREIF, seite=0.05), weg=WEG_KURVE) for _ in range(40)]
dreht2 = [x for x in folge2 if x.get('manoever') and x['manoever']['dreh'] > 0]
ok = ok and bool(dreht2) and all(x['manoever']['quer'] == 0.0 for x in dreht2)   # auch seitlich: auf der Stelle
# Review PR #101: Linie faellt beim Geradedrehen kurz aus, zuletzt schraeg -> nicht naeher heranfahren
l3 = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
for _ in range(60):                                   # bis er zum Geradedrehen ansetzt
    b3 = l3.schritt(1, objekt=dict(WUERFEL, seite=0.0), weg=WEG_KURVE)
    if (b3.get('manoever') or {}).get('dreh', 0.0) > 0:
        break
ohne_linie = [l3.schritt(1, objekt=dict(WUERFEL, seite=0.0)) for _ in range(10)]
ok = ok and (b3.get('manoever') or {}).get('dreh', 0.0) > 0 and all(
    (x.get('manoever') or {}).get('lin', 0.0) <= 0.0 for x in ohne_linie)
gerade = [l.schritt(1, objekt=dict(WUERFEL, vor=GREIF, seite=0.0), weg=[(0.05 * k, 0.0) for k in range(1, 12)])
          for _ in range(10)]
ok = ok and l.e.ablauf is not None and l.e.ablauf.phase in ('planen', 'naeher', 'ausfuehren')
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Kurve: schraeg zur Strasse -> dreht erst gerade (ohne vorzufahren), dann planen "
      f"({dreht[0]['grund'] if dreht else '-'})")
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
l.schritt(1, zebra={'abstand': 0.6})
arme, b, _ = wegraeumen(l, 40)
ok = b['aktion'] == 'stopp' and not arme
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} kurz nach Zebrastreifen -> nichts anfassen (Fussgaenger!): {b['grund']}")

# ---------------- STOPP / TEST: KI bewegt den Arm nie ----------------
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
l.schritt(1, objekt=NAH)
arme, b, _ = wegraeumen(l, 45, NAH)                 # anschauen, planen, erste Armbewegungen
ok_vorher = len(arme) > 0
l.e.fahrt_aktiv = False                          # STOPP gedrueckt
arme, b, _ = wegraeumen(l, 60, NAH)
ok = ok_vorher and arme == [] and l.e.ablauf is None
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} STOPP waehrend Wegraeumen: Ablauf abgebrochen, kein Arm-Befehl mehr ({b['grund']})")
l.e.fahrt_aktiv = True                           # wieder START
b = l.schritt(1)
ok = b['arm'] == 'fahrstellung'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} nach neuem START faehrt der Arm zuerst in die Fahrstellung: {b['grund']}")
# Wegraeumen hat nicht geklappt, Hindernis liegt noch da: wartet. STOPP + START -> schaut neu hin, versucht es nochmal
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
l.e.aufheben_gesperrt, l.e.bestaetigt = True, 'Wegraeumen hat nicht geklappt'
b = l.schritt(5, objekt=NAH)
ok_vorher = b['aktion'] == 'stopp' and l.e.ablauf is None
# B1: Statusausfall und -wiederkehr (fahrt_aktiv kurz False) ist KEIN START -> Sperre bleibt, kein Armversuch
l.e.fahrt_aktiv = False
l.schritt(11, objekt=NAH)
l.e.fahrt_aktiv = True
arme, b, _ = wegraeumen(l, 60, NAH)
ok = ok_vorher and l.e.aufheben_gesperrt and arme == [] and b['aktion'] == 'stopp'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Statusausfall + Wiederkehr quittiert nichts: Sperre bleibt, kein Armversuch ({b['grund']})")
l.e.fahrt_aktiv = False                          # STOPP
l.schritt(3, objekt=NAH)
l.e.kommando(l.t, 'start')                       # ausdruecklicher START am Panel
l.schritt(2, objekt=NAH)                         # Fahrprogramm startet noch
l.e.fahrt_aktiv = True
l.schritt(1, objekt=NAH)
arme, b, _ = wegraeumen(l, 60, NAH)
ok = not l.e.aufheben_gesperrt and len(arme) > 0
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} nach fehlgeschlagenem Wegraeumen: STOPP + START -> neuer Versuch ({len(arme)} Arm-Befehle)")
# Roboter-Log 20.10.: beim Heranfahren aus den Augen verloren (zu nah fuer die Kamera, unter dem LiDAR) ->
# "Weg ist wieder frei" -> drueber gefahren. Jetzt: gemerkte Stelle gilt nicht als frei, bis START.
for strecke in (False, True):
    l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
    s = {'strecke': 0.0} if strecke else {}
    b = l.schritt(15, objekt=dict(WUERFEL, vor=0.34), **s)           # anschauen -> in Greifweite fahren
    ok_anfang = l.e.ablauf is not None and l.e.ablauf.phase == 'abstand'
    if strecke:
        s = {'strecke': 0.04}                                          # 4 cm naeher heran: 30 cm, Kamera verliert es
    folge = [l.schritt(1, **s) for _ in range(80)]                     # Kamera + LiDAR sehen nichts mehr
    # noch bis 2,5 s blind weiter heran (Greifweite), aber nie 'fahren'; am Ende Halt mit Grund
    ok = (ok_anfang and all(x['aktion'] != 'fahren' for x in folge) and folge[-1]['aktion'] == 'stopp'
          and 'zu nah fuer die Kamera' in folge[-1]['grund'])
    l.e.fahrt_aktiv = False
    l.schritt(1, **s)
    l.e.kommando(l.t, 'start')
    l.e.fahrt_aktiv = True
    ok = ok and l.schritt(15, **s)['aktion'] == 'fahren'               # bewusster START (weggenommen)
    fehler += not ok
    print(f"{'OK  ' if ok else 'FEHLER'} Hindernis aus den Augen verloren ({'mit' if strecke else 'ohne'} Radzaehler)"
          f" -> bleibt stehen bis START, faehrt nicht drueber ({folge[-1]['grund']})")
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
s = {'strecke': 0.0}
l.schritt(15, objekt=dict(WUERFEL, vor=0.34), **s)
folge = [l.schritt(1, strecke=-0.05) for _ in range(40)]               # zurueckgerollt: weiter weg als beim Sehen
ok = folge[-1]['aktion'] == 'fahren' and l.e.hindernis_merk is None
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} gemerkte Stelle weit genug weg und Kamera sieht sie frei -> weiter ({folge[-1]['grund']})")
l = Lauf(arm_erlaubt=True, posen=POSEN)
l.e.fahrt_aktiv = False                          # nur TEST
arme, b = arm_befehle(l, 80, zebra={'abstand': 0.3})
ok = arme == [] and b['aktion'] == 'stopp' or arme == []
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} TEST-Modus am Zebrastreifen: kein Arm ({b['grund']})")
ok = 'nur waehrend der Fahrt' in l.e.kommando(l.t, 'umschauen')
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Umschauen im TEST-Modus abgelehnt")

# ---------------- Gegenseitiges Blockieren (z. B. zwei Roboter) ----------------
gegner = {'lidar': 0.3, 'objekte': [], 'tiefe_hindernis': True, 'lidar_hinten': 2.0}
# #49: Die Frist beginnt erst NACH dem Anschauen, nicht bei Testzeit 100.
# Nur diese beiden Faelle kontrollieren den Zufall; danach gilt wieder der echte Generator.
import random
from unittest.mock import patch

echtes_uniform = random.uniform
for frist in (12.0, 25.0):
    with patch('entscheider.random.uniform', return_value=frist) as zufall:
        l = Lauf(cfg={'ausweichen': True})
        for _ in range(50):                    # begrenztes Warten auf den tatsaechlichen Timerstart
            b = l.schritt(1, **gegner)
            if l.e.blockiert_seit is not None:
                break
        beginn = l.e.blockiert_seit
        timer_ok = (beginn is not None and b['aktion'] == 'stopp' and l.e.ablauf is None
                    and l.e.blockiert_grenze == frist)
        vorher_ok, nachher_ok, ablauf_nach, manoever_nach = False, False, None, None
        if timer_ok:
            # Alle 0,1-s-Schritte bis genau einen Schritt VOR der kontrollierten Frist pruefen.
            vorher = []
            for _ in range(round(frist / 0.1) - 1):
                b = l.schritt(1, **gegner)
                vorher.append(b['aktion'] == 'stopp' and l.e.ablauf is None
                              and l.e.blockiert_seit == beginn)
            vorher_ok = all(vorher) and 0 < frist - (l.t - beginn) < 0.101
            # Bis zur Frist: ein Zusatzschritt nur fuer die Rundung der 0,1-s-Testuhr.
            for _ in range(2):
                b = l.schritt(1, **gegner)
                if l.t - beginn >= frist:
                    break
            ablauf_ok = l.e.ablauf is not None and l.e.ablauf.name == 'ausweichen'
            if ablauf_ok:
                ablauf_nach = l.e.ablauf.seit - beginn
            # Der erste Ablaufaufruf bekommt noch keine Wahrnehmung und haelt.
            # Erst das naechste Bild liefert den hier ausdruecklich freien Rueckraum.
            b = l.schritt(1, **gegner)
            if b['aktion'] == 'manoever':
                manoever_nach = l.t - beginn
            nachher_ok = (ablauf_ok and frist <= ablauf_nach <= frist + 0.101
                          and manoever_nach is not None and 0 < manoever_nach - ablauf_nach < 0.101)
        zufall_ok = zufall.call_count == 1 and zufall.call_args.args == (12.0, 25.0)
    ok = timer_ok and vorher_ok and nachher_ok and zufall_ok and random.uniform is echtes_uniform
    fehler += not ok
    print(f"{'OK  ' if ok else 'FEHLER'} Blockadefrist {frist:g} s: Timerstart={beginn}, "
          f"Halt vor Frist={vorher_ok}, Ablauf nach {ablauf_nach} s, Manoever nach {manoever_nach} s, "
          f"Zufall wiederhergestellt={random.uniform is echtes_uniform}")
l = Lauf(cfg={'ausweichen': True})
for _ in range(300):
    b = l.schritt(1, lidar=0.3, tiefe_hindernis=True, lidar_hinten=0.1)
    if b['aktion'] == 'manoever':
        break
ok = b['aktion'] == 'manoever' and b['manoever']['lin'] >= 0
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} hinten nicht frei -> nicht rueckwaerts, nur wenden ({b['grund']})")

l = Lauf()
aktionen = [l.schritt(1, **gegner)['aktion'] for _ in range(400)]
ok = 'manoever' not in aktionen and aktionen[-1] == 'stopp'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Grundbetrieb (ausweichen aus): wartet auch nach 40 s, weicht nicht aus")
# Wenden, aber der Lagesensor meldet keine Drehung -> abbrechen und stehen bleiben
l = Lauf()
l.schritt(2, einfahrt_verboten=True)
folge = [l.schritt(1, gier=0.0) for _ in range(40)]
ok1 = all(x['aktion'] != 'fahren' for x in folge) and 'Wenden' in folge[-1]['grund']   # auch im Fehler-Zyklus
b = l.schritt(30, gier=0.0)
ok2 = b['aktion'] == 'stopp'
l.e.fahrt_aktiv = False                          # Statusausfall ...
l.schritt(1)
l.e.fahrt_aktiv = True                           # ... und Wiederkehr: Fehlerhalt bleibt
ok2 = ok2 and l.schritt(3)['aktion'] == 'stopp'
l.e.fahrt_aktiv = False                          # STOPP
l.schritt(1)
l.e.kommando(l.t, 'start')                       # START
l.e.fahrt_aktiv = True
b = l.schritt(3)
ok3 = b['aktion'] == 'fahren'
ok = ok1 and ok2 and ok3
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Wenden ohne gemessene Drehung -> Abbruch, bleibt stehen bis STOPP/START (nicht im Kreis)")

print()
print('Alle Tests bestanden.' if not fehler else f'{fehler} Test(s) fehlgeschlagen.')
sys.exit(1 if fehler else 0)
