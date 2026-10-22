#!/usr/bin/env python3
# Testet, wann der Linienfolger faehrt und wann nicht - ohne ROS (mit Attrappen).
# Aufruf: python3 tests/test_line_follower.py
# Die Zusammenarbeit mit KI und Simulator testet: scripts/simulation.sh pruefen (braucht ROS 2)
import math
import os
import sys
import time
import types

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, 'attrappen'))
sys.path.insert(0, os.path.join(HIER, '..', 'line_follower'))
import line_follower as lf  # noqa: E402

fehler = 0


def check(name, ergebnis, faehrt):
    global fehler
    lin, quer, ang, status = ergebnis
    ok = (abs(lin) > 0) == faehrt
    fehler += not ok
    print(f"{'OK  ' if ok else 'FEHLER'} {name}: {lin:.2f} m/s - {status}")


_scan_nr = [0]


def stempel():
    """Aufnahmezeit 50 ms vor jetzt, je Scan etwas spaeter (jeder Scan ist ein neuer, kein doppelter)."""
    _scan_nr[0] += 1
    t = time.time() - 0.05 + _scan_nr[0] * 1e-6
    return types.SimpleNamespace(stamp=types.SimpleNamespace(sec=int(t), nanosec=int((t % 1) * 1e9)))


def scan(abstand, index_vorne=180):
    r = [2.0] * 360
    for k in range(index_vorne - 3, index_vorne + 4):
        r[k] = abstand
    return types.SimpleNamespace(ranges=r, angle_min=-math.pi, angle_increment=2 * math.pi / 360,
                                 angle_max=math.pi - 2 * math.pi / 360,
                                 range_min=0.05, range_max=12.0, header=stempel())


def gerade_linie(n):
    # gerade Linie direkt vor dem Roboter ins Linien-Gedaechtnis legen
    n.gedaechtnis.hinzufuegen([(0.05 + 0.02 * k, 0.0) for k in range(30)])


def neu():
    n = lf.LineFollower()
    jetzt = time.time()
    gerade_linie(n)
    n.bild_zeit = jetzt
    n.stempel_ok = True  # gueltiges frisches Bild fuer diese Entscheidungspruefungen
    n.ki = (jetzt, {'aktion': 'fahren', 'faktor': 1.0, 'grund': 'Weg frei'})
    n.on_scan(scan(1.0), '/scan0', 0)
    n.on_scan(scan(1.0), '/scan1', 1)    # beide Kanaele in scan_topics sind Pflicht
    return n


n = neu()
check('alles frei', n.entscheide(), True)
n.on_scan(scan(0.10), '/scan0', 0)
check('Notbremse 10 cm (eigene, ohne KI)', n.entscheide(), False)
n = neu()
n.on_scan(scan(0.10, index_vorne=0), '/scan0', 0)
check('10 cm HINTEN -> faehrt', n.entscheide(), True)
n = neu()
n.scans.clear()
check('kein LiDAR -> Stopp', n.entscheide(), False)
n = neu()
n.ki = (time.time() - 2, n.ki[1])
check('KI antwortet nicht -> Stopp', n.entscheide(), False)
n = neu()
n.ki = (time.time(), {'aktion': 'stopp', 'grund': 'Rote Ampel'})
check('KI sagt stopp', n.entscheide(), False)
n = neu()
n.ki = (time.time(), {'aktion': 'langsam', 'faktor': 0.5, 'grund': 'LiDAR unbestaetigt'})
lin, _, _, _ = n.entscheide()
check('KI sagt langsam (halbe Geschwindigkeit)', (lin, 0, 0, f'{lin:.3f} m/s'), True)
if abs(lin - 0.075) > 0.001:
    fehler += 1
    print('FEHLER  langsam ist nicht halb so schnell')
n = neu()
n.gedaechtnis = lf.linie.Gedaechtnis()
n.lenkung.verloren_seit = time.time() - 10  # sucht schon laenger als such_zeit
check('keine Linie (Suche vorbei) -> Stopp', n.entscheide(), False)
n = neu()
n.entscheide()                            # Linie einmal gesehen ...
n.gedaechtnis = lf.linie.Gedaechtnis()    # ... und jetzt weg
lin, quer, dreh, status = n.entscheide()
ok = lin == 0 and abs(dreh) > 0
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Linie gerade verloren -> dreht sich auf der Stelle und sucht: {status}")
n = neu()
n.ki = (time.time(), {'aktion': 'manoever', 'grund': 'wenden',
                      'manoever': {'lin': 0.5, 'quer': 0.0, 'dreh': 3.0, 'text': 'test'}})
lin, quer, dreh, status = n.entscheide()
ok = lin <= lf.MANOEVER_MAX['lin'] and dreh <= lf.MANOEVER_MAX['dreh']
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} KI-Manoever wird begrenzt: {lin:.2f} m/s, {dreh:.2f} rad/s")
n = neu()
n.on_scan(scan(0.10), '/scan0', 0)
n.ki = (time.time(), {'aktion': 'manoever', 'grund': 'ausrichten',
                      'manoever': {'lin': 0.03, 'quer': 0.0, 'dreh': 0.0, 'text': 'vor'}})
check('Notbremse sperrt Vorwaerts-Manoever', n.entscheide(), False)
n.ki = (time.time(), {'aktion': 'manoever', 'grund': 'wenden',
                      'manoever': {'lin': 0.0, 'quer': 0.0, 'dreh': 0.8, 'text': 'wenden'}})
lin, quer, dreh, status = n.entscheide()
ok = lin == 0 and quer == 0 and dreh == 0
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} GB-14: Notbremse sperrt auch Drehen auf der Stelle: {status}")


# ---- L6 (#65): Notbremse prueft den TATSAECHLICHEN Befehl (nicht den Parameter direction) ----
def hinten_10cm(n):
    for t, i in (('/scan0', 0), ('/scan1', 1)):
        n.on_scan(scan(0.10, index_vorne=0), t, i)          # hinten 10 cm, vorne 2 m


def manoever(n, **wunsch):
    n.ki = (time.time(), {'aktion': 'manoever', 'grund': 'test', 'manoever': dict(wunsch, text='test')})


def halt_mit(name, ergebnis, text):
    global fehler
    lin, quer, dreh, status = ergebnis
    ok = (lin, quer, dreh) == (0.0, 0.0, 0.0) and text in status
    fehler += not ok
    print(f"{'OK  ' if ok else 'FEHLER'} {name}: {lin:.2f} m/s - {status}")


n = neu()
hinten_10cm(n)
manoever(n, lin=-0.05)
halt_mit('direction=+1, hinten 10 cm, KI-Manoever rueckwaerts -> Null + Grund hinten', n.entscheide(),
         'NOTBREMSE 10 cm hinten')
n._p['drive'] = True
n.steuern()
cmd = n.pub.letzte
ok = (cmd.linear.x, cmd.linear.y, cmd.angular.z) == (0.0, 0.0, 0.0)
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} ... und die Publisherattrappe bekommt den Nullbefehl")
n = neu()
n._p['direction'] = -1.0
hinten_10cm(n)
halt_mit('direction=-1, hinten 10 cm -> stoppt weiterhin', n.entscheide(), 'hinten')
n = neu()
hinten_10cm(n)
check('direction=+1, hinten 10 cm, Linie vorwaerts -> faehrt (vorne frei)', n.entscheide(), True)
n._p['direction'] = -1.0                  # Richtungswechsel OHNE neuen Scan
halt_mit('Richtungswechsel ohne neuen Scan -> richtiger Bereich (hinten)', n.entscheide(), 'hinten')
n = neu()
hinten_10cm(n)
manoever(n, lin=0.05)
check('hinten 10 cm, KI-Manoever vorwaerts -> faehrt', n.entscheide(), True)
for wunsch in ({'dreh': 0.8}, {'quer': 0.05}, {'quer': -0.05, 'dreh': -0.5}):
    n = neu()
    hinten_10cm(n)
    manoever(n, **wunsch)
    halt_mit(f'hinten 10 cm, KI-Manoever {wunsch} auf der Stelle -> Halt', n.entscheide(), 'hinten')
n = neu()
hinten_10cm(n)
manoever(n)
ergebnis = n.entscheide()
ok = ergebnis[:3] == (0.0, 0.0, 0.0)
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Haltwunsch (Manoever 0) bleibt Null: {ergebnis[3]}")
n = neu()
n.on_scan(scan(0.10), '/scan1', 1)
manoever(n, lin=-0.05)
halt_mit('vorne 10 cm (direction=+1), KI-Manoever rueckwaerts -> haelt wie bisher', n.entscheide(), 'vorne')

n = neu()
n.set_parameters([lf.Parameter('kamera_neigung', value=30.0)])
ok = n.sucher.c['kamera_neigung'] == 30.0 and n.sucher.groesse is None
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Einstellung im Betrieb aendern (ros2 param set) wirkt sofort")
n = neu()
n.bild_zeit = time.time() - 1
check('keine Kamerabilder -> Stopp', n.entscheide(), False)
# RM02 22.10.: Linienbilder setzen aus, die KI hat aber frisch aufgenommene Bilder -> ihr Manoever gilt.
# Massgeblich ist die Aufnahmezeit (Kamera-Stempel), nicht wann die KI ausgewertet hat (Review PR #126).
for ki_alter, faehrt in ((0.2, True), (1.5, False), (None, False), (-1.0, False)):
    n = neu()
    n.bild_zeit = time.time() - 1
    n.ki = (time.time(), {'aktion': 'manoever', 'grund': 'ausrichten', 'bild_alter': 0.0,
                          'aufnahme': None if ki_alter is None else time.time() - ki_alter,
                          'manoever': {'lin': 0.03, 'quer': 0.0, 'dreh': 0.0, 'text': 'vor'}})
    check(f'keine Linienbilder, KI-Manoever mit KI-Aufnahme {ki_alter} s alt', n.entscheide(), faehrt)
n = neu()
n.bild_zeit = time.time() - 1
n.on_scan(scan(0.10), '/scan0', 0)
n.ki = (time.time(), {'aktion': 'manoever', 'grund': 'ausrichten', 'aufnahme': time.time() - 0.1,
                      'manoever': {'lin': 0.03, 'quer': 0.0, 'dreh': 0.0, 'text': 'vor'}})
check('keine Linienbilder: Notbremse sperrt KI-Manoever weiter', n.entscheide(), False)
n = neu()
n._p['ki_pflicht'] = False
n.ki = (0.0, None)
check('ohne KI-Pflicht (Test ohne KI)', n.entscheide(), True)
n = neu()
n.on_tempo(types.SimpleNamespace(data=0.9))
check('Tempo vom Panel wird auf 0,5 m/s begrenzt', (n.p('speed'), 0, 0, f"speed={n.p('speed')}"), True)
if n.p('speed') != 0.5:
    fehler += 1
    print('FEHLER  Begrenzung greift nicht')


# ---- Verzoegerung selbst messen: Drehung kommt 0,15 s spaeter, traege (0,1 s) und 5 % schwaecher ----
lerner = lf.linie.Verzoegerung()
befehle = [0.8 * math.sin(i * 0.05 * 1.3) + (0.5 if (i // 40) % 2 else -0.5) for i in range(300)]
drehung = 0.0
for i, b in enumerate(befehle):
    spaet = befehle[max(0, i - 3)]                  # 3 Takte = 0,15 s spaeter
    drehung += (1 - math.exp(-0.05 / 0.1)) * (0.95 * spaet - drehung)
    lerner.hinzu(b, drehung)
erg = lerner.schaetzen()
ok = erg is not None and abs(erg['totzeit'] - 0.15) <= 0.03 and abs(erg['faktor'] - 0.95) < 0.05
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Verzoegerung Lenkbefehl -> Drehung selbst gemessen: {erg}")
n = neu()
n.bewegung_quelle = 'Radzaehler + Lagesensor'
n.verzoegerung.ergebnis = {'totzeit': 0.25, 'traegheit': 0.1, 'faktor': 0.95, 'guete': 0.9}
ok = abs(n.vorhersage_zeit() - (0.25 - n.p('motor_totzeit'))) < 1e-6
n.bewegung_quelle = 'Fahrbefehle'
ok = ok and n.vorhersage_zeit() == 0.0
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Vorhersage = gemessene Totzeit - Motor-Anteil, ohne Messung keine Vorhersage")

# ---- Stand: Nullpunktfehler des Lagesensors lernen (sonst verdreht sich das Gedaechtnis im Stand) ----
n = neu()
n.pruef_imu = [10.0, 20]                     # Lagesensor gilt schon als plausibel
n.letzter_cmd = (0.0, 0.0, 0.0)
for _ in range(300):
    n.imu = (time.time(), 0.003)
    _, _, dreh = n.bewegung(0.05)
ok = abs(n.gyro_null - 0.003) < 0.0005 and abs(dreh) < 0.0005
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Stand: Nullpunkt des Lagesensors gelernt ({n.gyro_null:.4f} rad/s)")
n = neu()
n.on_ki(types.SimpleNamespace(data='{"aktion": "stopp", "kamera_ok": false}'))
ok = time.time() - n.kamera_weg_bis < 1.0
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Kamera schaut weg (Arm): gemerkt, Bilder bis 0,5 s danach zaehlen nicht")

# ---- Kurve voraus: Gerade 20 cm, dann Kurve mit 25 cm Radius -> bremst schon vorher ----
g = lf.linie.Gedaechtnis()
punkte = [(0.01 * k, 0.0) for k in range(20)]
punkte += [(0.2 + 0.25 * math.sin(a / 100), 0.25 - 0.25 * math.cos(a / 100)) for a in range(0, 157, 3)]
g.hinzufuegen(punkte)
k_vor = g.kruemmung_voraus()
lenkung = lf.linie.Lenkung()
v_vor, _, _ = lenkung.berechne({'gefunden': False}, 0.35, time.time(), {'quer': 0.0, 'kurs': 0.0, 'kruemmung': 0.0},
                               k_vor)
ok = 2.5 < k_vor < 6.0 and v_vor < 0.25
fehler += not ok
print(f"{'OK  ' if ok else 'FEHLER'} Kurve voraus erkannt (Kruemmung {k_vor:.1f} 1/m) -> schon auf der Geraden "
      f"langsamer: {v_vor:.2f} m/s")

print('\nAlle Tests bestanden.' if not fehler else f'\n{fehler} Test(s) fehlgeschlagen.')
sys.exit(1 if fehler else 0)
