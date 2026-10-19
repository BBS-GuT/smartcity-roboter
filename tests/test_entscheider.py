#!/usr/bin/env python3
# Prueft die Entscheidungen der KI-Zentrale mit ausgedachten Wahrnehmungen (kein Roboter noetig).
# Aufruf: python3 tests/test_entscheider.py
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ki'))
from entscheider import Entscheider  # noqa: E402

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
            self.t += 0.1
            self.nr += 1
            daten = {'bild_nr': self.nr, 'bild_zeit': self.t, 'objekte': [], 'ampel': None,
                     'stoppschild': False, 'lidar': float('inf'), 'tiefe_hindernis': False}
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
pruefe('Ampel weg, nach Timeout -> weiter', l.schritt(45, ampel=None), 'fahren')

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

# ---------------- Zebrastreifen ----------------
POSEN = {'fahrstellung': [90, 120, 10, 20, 90, 30],
         'blick_links': [135, 120, 10, 20, 90, 30], 'blick_rechts': [45, 120, 10, 20, 90, 30]}
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'))
import arm as armlib  # noqa: E402
KIN = armlib.Kinematik()


def planer(obj, seite):
    """wie ki/zentrale.py (eigene Kinematik)"""
    greif = (obj['vor'] + obj['breite'] / 2, obj['seite'], max(0.012, obj['hoehe'] / 2))
    return armlib.plane_wegraeumen(KIN.inverse, greif, armlib.ablagestellen(seite, obj['hoehe'] / 2 + 0.01),
                                   obj['hoehe'], POSEN['fahrstellung'], 30, 130)


def arm_befehle(lauf, n, **w):
    """n Schritte, sammelt alle Arm-Befehle."""
    arme, letzter = [], None
    for _ in range(n):
        letzter = lauf.schritt(1, **w)
        a = letzter['arm']
        if a:
            arme.append(a if isinstance(a, str) else a.get('pose') or tuple(a['winkel']))
    return arme, letzter


l = Lauf(arm_erlaubt=True, posen=POSEN)
pruefe('Zebrastreifen 50 cm -> noch fahren', l.schritt(2, zebra={'abstand': 0.5}), 'fahren')
pruefe('Zebrastreifen 30 cm -> anhalten', l.schritt(1, zebra={'abstand': 0.3}), 'stopp')
arme, b = arm_befehle(l, 80, zebra={'abstand': 0.3})
ok = arme == ['blick_links', 'blick_rechts', 'fahrstellung']
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} umschauen links, rechts, zurueck: {arme}")
pruefe('niemand da -> weiter', b, 'fahren')
pruefe('derselbe Zebrastreifen -> kein zweiter Halt', l.schritt(20, zebra={'abstand': 0.2}), 'fahren')
l = Lauf(arm_erlaubt=True, posen=POSEN)
l.schritt(1, zebra={'abstand': 0.3})
arme, b = arm_befehle(l, 80, zebra={'abstand': 0.3}, objekte=[{'name': 'Person', 'im_weg': False}])
pruefe('Person gesehen -> wartet weiter', b, 'stopp')
arme, b = arm_befehle(l, 120, zebra={'abstand': 0.3})
pruefe('Person weg -> weiter', b, 'fahren')
l = Lauf()
l.schritt(1, zebra={'abstand': 0.3})
arme, b = arm_befehle(l, 30, zebra={'abstand': 0.3}, lidar_breit=0.35)
ok = arme == [] and b['aktion'] == 'stopp'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} ohne Arm-Freigabe: kein Arm, etwas auf dem Zebrastreifen -> wartet ({b['grund']})")
pruefe('ohne Arm, frei -> weiter', l.schritt(80, zebra={'abstand': 0.3}), 'fahren')
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

# ---------------- Einbahnstrasse ----------------
l = Lauf()
pruefe('Einfahrt verboten 1 Bild -> noch nichts', l.schritt(1, einfahrt_verboten=True), 'fahren')
pruefe('Einfahrt verboten 2 Bilder -> anhalten', l.schritt(1, einfahrt_verboten=True), 'stopp')
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
WUERFEL = {'vor': 0.31, 'seite': 0.02, 'breite': 0.045, 'hoehe': 0.045, 'quelle': 'tiefe'}
NAH = dict(WUERFEL, vor=0.25)


def wegraeumen(lauf, n, objekt_bis_greifen=WUERFEL, danach=None):
    """Simuliert die Welt grob: Wuerfel kommt naeher, wenn der Roboter vorfaehrt; nach dem Greifen weg."""
    obj, arme, gruende, letzter = dict(objekt_bis_greifen), [], [], None
    for _ in range(n):
        letzter = lauf.schritt(1, objekt=obj)
        m = letzter.get('manoever')
        if m:
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
arme, b, gruende = wegraeumen(l, 600, NAH, danach=NAH)     # liegt nach dem Greifen immer noch da
ok = len(arme) == 18 and b['aktion'] == 'stopp'
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} liegt danach noch da -> 2. Versuch, dann aufgeben und warten "
      f"({len(arme)} Armbewegungen, {b['grund']})")
pruefe('kein dritter Versuch, solange er da liegt', l.schritt(30, objekt=NAH), 'stopp', None)
pruefe('Wuerfel weg -> weiter', l.schritt(30), 'fahren')
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=lambda o, s: {'fehler': 'Test: nicht erreichbar'})
l.schritt(1, objekt=NAH)
arme, b, gruende = wegraeumen(l, 100, NAH, danach=NAH)
pruefe('Arm erreicht es nicht -> keine Bewegung, warten', b, 'stopp', None)
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
b = l.schritt(30, objekt=WUERFEL, objekte=[{'name': 'Person', 'im_weg': False}])
pruefe('Person in Sicht -> nie anfassen, nur warten', b, 'stopp', None)
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
pruefe('zu breit (20 cm) -> warten statt greifen', l.schritt(30, objekt=dict(WUERFEL, breite=0.2)), 'stopp', None)
l = Lauf(arm_erlaubt=False, posen=POSEN, planer=None)
b = l.schritt(30, objekt=WUERFEL)
pruefe('ohne Arm-Freigabe -> Kamera bestaetigt, warten', b, 'stopp', None)
l = Lauf(arm_erlaubt=True, posen=POSEN, planer=planer)
pruefe('LiDAR 15 cm, Kamera sieht nichts -> etwas zurueck, damit die Kamera es sieht',
       l.schritt(15, lidar=0.15, lidar_hinten=1.0), 'manoever')

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
pruefe('Gegenstand am Strassenrand (12 cm neben der Linie) -> nicht greifen, warten',
       l.schritt(30, objekt=dict(WUERFEL, quer=0.12)), 'stopp', None)
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
l = Lauf(cfg={'ausweichen': True})
gegner = {'lidar': 0.3, 'objekte': [], 'tiefe_hindernis': True, 'lidar_hinten': 2.0}
b = l.schritt(100, **gegner)                     # 10 s: wartet noch
ok1 = b['aktion'] == 'stopp' and l.e.ablauf is None
aktionen = [l.schritt(1, **gegner)['aktion'] for _ in range(160)]   # bis 26 s
ok2 = 'manoever' in aktionen
erstes = next((l2 for l2 in range(len(aktionen)) if aktionen[l2] == 'manoever'), None)
fehler += not (ok1 and ok2)
print(f"{'OK  ' if ok1 and ok2 else 'FEHLER'} Weg lange versperrt -> nach Zufallszeit ausweichen "
      f"(nach {10 + (erstes or 0) / 10:.1f} s)")
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
b = l.schritt(40, gier=0.0)
ok1 = b['aktion'] == 'stopp' and 'Wenden' in b['grund']
b = l.schritt(30, gier=0.0)
ok2 = b['aktion'] == 'stopp'
l.e.fahrt_aktiv = False
l.schritt(1)
l.e.fahrt_aktiv = True
b = l.schritt(3)
ok3 = b['aktion'] == 'fahren'
ok = ok1 and ok2 and ok3
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Wenden ohne gemessene Drehung -> Abbruch, bleibt stehen bis STOPP/START (nicht im Kreis)")

print()
print('Alle Tests bestanden.' if not fehler else f'{fehler} Test(s) fehlgeschlagen.')
sys.exit(1 if fehler else 0)
