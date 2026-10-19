#!/usr/bin/env python3
# Misst, wie genau der Linienfolger der Linie folgt - bei mehreren Tempos, OHNE ROS.
#
# Es laeuft der ECHTE Linienfolger (line_follower/line_follower.py, mit den ROS-Attrappen aus tests/attrappen),
# aber mit einer simulierten Uhr: Kamerabild, Radzaehler, Lagesensor und Antrieb (sim/antrieb.py) werden
# Schritt fuer Schritt nachgerechnet. Vorteil: Ergebnis haengt NICHT davon ab, wie ausgelastet der Rechner ist.
# Welt: Rundkurs aus sim/welt.py (Kurvenradius 25 cm), ohne Ampel/Wuerfel/Fussgaenger, eine Runde.
#
# Aufruf:  python3 sim/linie_messen.py                       (0,15 / 0,25 / 0,35 m/s, Antrieb 'echt', je 3 Fahrten)
#          python3 sim/linie_messen.py --antrieb ideal echt schwer   (ideal = wie frueher: Befehl = sofort Tempo)
#          python3 sim/linie_messen.py --tempo 0.35 --set vorhersage=0.2 selbst_einstellen=false
#          --kamera_hz 10 --latenz 0.2           langsamere Kamera, Bilder kommen spaeter an
#          --mess_hz 10 --mess_verz 0.05         Radzaehler/Lagesensor: so oft pro Sekunde, so viele s zu spaet
#                                                (Standard wie vermutlich beim Yahboom-Board, NICHT gemessen)
#
# Was die Spalten bedeuten (Abweichung = Abstand Robotermitte - Linienmitte, max = schlimmste der Fahrten):
#   max / Mittel     groesste / mittlere Abweichung auf der ganzen Runde (cm)
#   Gerade           groesste Abweichung auf den Geraden, ab 30 cm nach der Kurve (cm)
#   Kurve            groesste Abweichung in den Kurven und den ersten 30 cm danach (cm)
#   Pendeln          wie weit er auf den Geraden hin und her schwankt (cm, Schwankung um die eigene Mitte,
#                    ab 30 cm nach der Kurve) und wie oft (Schwingungen pro Sekunde, Hz)
#   Lenkunruhe       wie stark der Lenkbefehl auf den Geraden zappelt (rad/s, Standardabweichung)
#   v Kurve          mittleres Tempo in den Kurven, Runde = Zeit fuer eine Runde
#   gelernt          Totzeit, die der Linienfolger selbst gemessen hat (Lenkbefehl -> Lagesensor)
import argparse
import math
import os
import sys
import types
from multiprocessing import Pool

import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HIER, '..')
sys.path.insert(0, os.path.join(REPO, 'tests', 'attrappen'))   # unechtes ROS (wie in den Tests)
sys.path.insert(0, os.path.join(REPO, 'line_follower'))
sys.path.insert(0, HIER)
import line_follower as lf   # noqa: E402
from antrieb import Antrieb  # noqa: E402
import welt as welt_modul    # noqa: E402
from welt import Welt        # noqa: E402

SCHRITT = 0.005              # Rechenschritt der Physik (s)


class Uhr:
    """Simulierte Zeit statt time.time() im Linienfolger."""
    def __init__(self):
        self.t = 1000.0

    def time(self):
        return self.t


def strecken_kruemmung(welt):
    """Kruemmung (1/m) an jedem Streckenpunkt (0 = gerade, 4 = Kurve mit 25 cm Radius)."""
    r = np.unwrap(welt.richtung)
    ds = np.diff(np.concatenate([welt.s_werte, [welt.laenge]]))
    k = np.gradient(r) / np.maximum(ds, 1e-6)
    return np.convolve(k, np.ones(5) / 5, mode='same')


def antrieb_aus_text(text):
    """'echt' oder z. B. 'echt:schlupf=0,traegheit=0.3' (Profil mit geaenderten Werten)."""
    name, _, rest = text.partition(':')
    werte = {k: float(v) for k, v in (teil.split('=') for teil in rest.split(',') if teil)}
    return Antrieb(name, **werte)


def fahrt(tempo, antrieb='echt', kamera_hz=15.0, latenz=0.1, runden=1.0, einstellungen=None, aufzeichnen=False,
          messfehler=True, stempel_fehler=0.0, mess_verz=0.05, mess_hz=10.0, saat=0, kamera_wahr=None):
    uhr = Uhr()
    lf.time = types.SimpleNamespace(time=uhr.time, sleep=lambda s: None)
    # kamera_wahr: wo die Kamera WIRKLICH sitzt, z. B. {'hoehe': 0.31} (der Linienfolger glaubt seine Einstellung)
    alt_kamera = dict(welt_modul.KAMERA)
    welt_modul.KAMERA.update(kamera_wahr or {})
    try:
        welt = Welt(False, False, False)
        welt.kamera(welt.pose_bei(0.0))   # Sehstrahlen jetzt ausrechnen (merkt sich die Welt)
    finally:
        welt_modul.KAMERA.clear()
        welt_modul.KAMERA.update(alt_kamera)
    node = lf.LineFollower()
    node._p.update({'drive': True, 'show': False, 'publish_image': False, 'ki_pflicht': False,
                    'obstacle_check': False, 'speed': tempo})
    if einstellungen:
        node.set_parameters([lf.Parameter(n, value=v) for n, v in einstellungen.items()])
    motor = antrieb_aus_text(antrieb)
    rng = np.random.default_rng(3 + saat)
    k_strecke = strecken_kruemmung(welt)
    pose = list(welt.pose_bei(0.0))
    if saat:                         # andere Fahrt: Start etwas neben der Linie und schraeg
        pose[1] += float(rng.uniform(-0.01, 0.01))
        pose[2] += math.radians(float(rng.uniform(-3, 3)))
    messungen = []                   # Radzaehler/Lagesensor: (Ankunftszeit, odom, imu)
    unterwegs = []                   # Kamerabilder: (Ankunftszeit, Aufnahmezeit, Pose)
    naechstes_bild = naechster_befehl = naechste_messung = naechste_aufzeichnung = uhr.t
    gefahren, daten, quelle = 0.0, [], []
    ende = uhr.t + runden * welt.laenge / tempo * 2.5 + 5
    letzter_s = 0.0
    while uhr.t < ende:
        uhr.t += SCHRITT
        t = uhr.t
        # --- Physik: wahre Bewegung (mit Antrieb wie in echt) ---
        vor, quer, dreh = motor.schritt(SCHRITT, t)
        x, y, w = pose
        pose = [x + (vor * math.cos(w) - quer * math.sin(w)) * SCHRITT,
                y + (vor * math.sin(w) + quer * math.cos(w)) * SCHRITT, w + dreh * SCHRITT]
        gefahren += math.hypot(vor, quer) * SCHRITT
        # --- Kamera: Bild aufnehmen, kommt 'latenz' s spaeter beim Linienfolger an ---
        if t >= naechstes_bild:
            naechstes_bild += 1.0 / kamera_hz
            unterwegs.append((t + latenz, t, tuple(pose)))
        while unterwegs and unterwegs[0][0] <= t:
            _, aufnahme, p = unterwegs.pop(0)
            bild, _ = welt.kamera(p)
            aufnahme += stempel_fehler   # Zeitstempel zu spaet (Kameratreiber stempelt erst beim Empfang)
            msg = types.SimpleNamespace(img=bild, header=types.SimpleNamespace(
                stamp=types.SimpleNamespace(sec=int(aufnahme), nanosec=int((aufnahme % 1) * 1e9))))
            node.on_image(msg)
        # --- Radzaehler + Lagesensor ('mess_hz' pro Sekunde, kommen 'mess_verz' s spaeter an, Fehler wie im Simulator) ---
        if t >= naechste_messung:
            naechste_messung += 1.0 / mess_hz
            rv, rq, rw = motor.rad
            if not messfehler:          # Vergleich: Radzaehler messen genau die wahre Bewegung
                rv, rq, rw = vor / 0.97, quer / 0.97, (dreh - 0.004) / 1.02
            odom = types.SimpleNamespace(twist=types.SimpleNamespace(twist=types.SimpleNamespace(
                linear=types.SimpleNamespace(x=rv * 0.97, y=rq * 0.97),
                angular=types.SimpleNamespace(z=rw * 1.02 + 0.004))))
            imu = types.SimpleNamespace(angular_velocity=types.SimpleNamespace(
                z=dreh + (0.003 + float(rng.normal(0, 0.01)) if messfehler else 0.0)))
            messungen.append((t + mess_verz, odom, imu))
        while messungen and messungen[0][0] <= t:
            _, odom, imu = messungen.pop(0)
            node.on_odom(odom)
            node.on_imu(imu)
        # --- Aufzeichnen: wie weit ist der Roboter wirklich neben der Linie? (50x pro Sekunde) ---
        if t >= naechste_aufzeichnung:
            naechste_aufzeichnung += 0.02
            s, _ = welt.s_von(pose[0], pose[1])
            i = int(np.searchsorted(welt.s_werte, s))
            i = min(i, len(welt.punkte) - 1)
            px, py = welt.punkte[i]
            r = welt.richtung[i]
            seite = -(pose[0] - px) * math.sin(r) + (pose[1] - py) * math.cos(r)   # + = links der Linie
            daten.append((t, s, seite, k_strecke[i], node.letzter_cmd[0], node.letzter_cmd[2], vor, dreh))
            if aufzeichnen:
                lok = node.gedaechtnis.lokal()
                quelle.append((node.bewegung_quelle, None if lok is None else lok['quer'],
                               None if lok is None else lok['kurs'], None if lok is None else lok['kruemmung']))
            if abs(seite) > 0.15:
                break                # Linie verloren
            if gefahren > 0.5 and s < letzter_s - 1.0:
                runden -= 1          # Start/Ziel ueberfahren
                if runden <= 1e-6:
                    break
            letzter_s = s
        # --- Linienfolger: 20 Fahrbefehle pro Sekunde ---
        if t >= naechster_befehl:
            naechster_befehl += 1.0 / node.p('rate')
            node.steuern()
            lin, q, d = node.letzter_cmd
            motor.befehl(lin, q, d, t)
    d = np.array(daten)
    erg = auswerten(d, welt)
    lernen = getattr(node, 'verzoegerung', None)          # gibt es erst im neuen Linienfolger
    erg.update({'tempo': tempo, 'antrieb': antrieb, 'verzoegerung': lernen.ergebnis if lernen else None})
    if aufzeichnen:
        erg['daten'], erg['quelle'] = d, quelle
    return erg


def auswerten(d, welt):
    t, s, seite, k, cmd_v, cmd_dreh, vor, dreh = d.T
    gerade = np.abs(k) < 0.2
    kurve = np.abs(k) > 2.0
    # Pendeln: nur Geraden, ab 30 cm nach dem Kurvenende (Einschwingen nach der Kurve zaehlt nicht)
    ruhig = np.zeros(len(d), bool)
    seit_kurve = 0.0
    for i in range(len(d)):
        seit_kurve = 0.0 if not gerade[i] else seit_kurve + (vor[i] * (t[i] - t[i - 1]) if i else 0.0)
        ruhig[i] = gerade[i] and seit_kurve > 0.3 and vor[i] > 0.05
    amp, freq, unruhe, zeit = [], [], [], 0.0
    for teil in np.split(np.arange(len(d)), np.nonzero(np.diff(ruhig.astype(int)))[0] + 1):
        if not ruhig[teil[0]] or len(teil) < 25:
            continue
        a = seite[teil] - seite[teil].mean()
        dauer = t[teil[-1]] - t[teil[0]]
        # Nulldurchgaenge mit 1 mm Huelle zaehlen (Rauschen zaehlt nicht)
        n, zustand = 0, 0
        for wert in a:
            neu = 1 if wert > 0.001 else (-1 if wert < -0.001 else zustand)
            n += neu != zustand and zustand != 0
            zustand = neu
        amp.append(math.sqrt(2) * a.std())
        freq.append(n / 2 / dauer)
        unruhe.append(cmd_dreh[teil].std())
        zeit += dauer
    fahrt = vor > 0.05
    verloren = np.abs(seite).max() > 0.149
    return {
        'max': np.abs(seite[fahrt]).max() * 100, 'mittel': np.abs(seite[fahrt]).mean() * 100,
        'max_s': float(s[fahrt][np.argmax(np.abs(seite[fahrt]))]),
        'gerade': np.abs(seite[ruhig]).max() * 100, 'kurve': np.abs(seite[fahrt & ~ruhig]).max() * 100,
        'pendel': float(np.mean(amp)) * 100 if amp else float('nan'),
        'freq': float(np.mean(freq)) if freq else float('nan'),
        'unruhe': float(np.mean(unruhe)) if unruhe else float('nan'),
        'v_max': vor.max(), 'v_kurve': float(np.mean(vor[kurve])) if kurve.any() else float('nan'),
        'zeit': t[-1] - t[0], 'verloren': bool(verloren),
    }


def zusammenfassen(fahrten):
    """Mehrere Fahrten (gleiche Einstellung, andere Startlage) -> eine Zeile: max = schlimmste Fahrt, sonst Mittelwerte."""
    e = dict(fahrten[0])
    for name in ('max', 'gerade', 'kurve'):
        e[name] = max(f[name] for f in fahrten)
    for name in ('mittel', 'pendel', 'freq', 'unruhe', 'v_kurve', 'zeit'):
        e[name] = float(np.nanmean([f[name] for f in fahrten]))
    e['verloren'] = sum(f['verloren'] for f in fahrten)
    gelernt = [f['verzoegerung']['totzeit'] for f in fahrten if f.get('verzoegerung')]
    e['totzeit'] = float(np.mean(gelernt)) if gelernt else None
    return e


def tabelle(ergebnisse):
    print(f"{'Tempo':>5} {'Antrieb':>7} | {'max':>5} {'Mittel':>6} {'Gerade':>6} {'Kurve':>6} | "
          f"{'Pendeln':>7} {'Hz':>4} {'Lenkunruhe':>10} | {'v Kurve':>7} {'Runde':>5} | {'gelernt':>9}")
    print(f"{'m/s':>5} {'':>7} | {'cm':>5} {'cm':>6} {'cm':>6} {'cm':>6} | {'cm':>7} {'':>4} {'rad/s':>10} | "
          f"{'m/s':>7} {'s':>5} | {'Totzeit s':>9}")
    for e in ergebnisse:
        gelernt = '-' if e.get('totzeit') is None else f"{e['totzeit']:.2f}"
        print(f"{e['tempo']:5.2f} {e['antrieb']:>7} | {e['max']:5.1f} {e['mittel']:6.2f} {e['gerade']:6.1f} "
              f"{e['kurve']:6.1f} | {e['pendel']:7.2f} {e['freq']:4.1f} {e['unruhe']:10.3f} | "
              f"{e['v_kurve']:7.2f} {e['zeit']:5.1f} | {gelernt:>9}"
              + (f"  LINIE VERLOREN ({e['verloren']}x)" if e['verloren'] else ''))


def _eine(auftrag):
    tempo, antrieb, kw = auftrag
    return fahrt(tempo, antrieb, **kw)


def main():
    ap = argparse.ArgumentParser(description='Misst die Genauigkeit des Linienfolgers (ohne ROS).')
    ap.add_argument('--tempo', type=float, nargs='+', default=[0.15, 0.25, 0.35])
    ap.add_argument('--antrieb', nargs='+', default=['echt'], help='ideal, echt, schwer (sim/antrieb.py)')
    ap.add_argument('--kamera_hz', type=float, default=15.0, help='Kamerabilder pro Sekunde')
    ap.add_argument('--latenz', type=float, default=0.1, help='Aufnahme bis Ankunft beim Linienfolger (s)')
    ap.add_argument('--mess_hz', type=float, default=10.0, help='Radzaehler/Lagesensor pro Sekunde (Yahboom: ca. 10)')
    ap.add_argument('--mess_verz', type=float, default=0.05, help='Radzaehler/Lagesensor kommen so viele s spaeter an')
    ap.add_argument('--fahrten', type=int, default=3, help='so viele Fahrten je Zeile (andere Startlage)')
    ap.add_argument('--set', nargs='*', default=[], help='Einstellung des Linienfolgers, z. B. vorhersage=0.2')
    ap.add_argument('--parallel', type=int, default=3, help='so viele Fahrten gleichzeitig (Prozessorkerne)')
    a = ap.parse_args()
    einst = {}
    for e in a.set:
        n, v = e.split('=', 1)
        einst[n] = {'true': True, 'false': False}[v.lower()] if v.lower() in ('true', 'false') else float(v)
    kw = {'kamera_hz': a.kamera_hz, 'latenz': a.latenz, 'mess_hz': a.mess_hz, 'mess_verz': a.mess_verz,
          'einstellungen': einst}
    zeilen = [(v, an) for an in a.antrieb for v in a.tempo]
    auftraege = [(v, an, dict(kw, saat=s)) for v, an in zeilen for s in range(a.fahrten)]
    print(f'Kamera {a.kamera_hz:.0f} Bilder/s, {a.latenz * 1000:.0f} ms spaeter; Radzaehler/Lagesensor '
          f'{a.mess_hz:.0f}/s, {a.mess_verz * 1000:.0f} ms spaeter; {a.fahrten} Fahrten je Zeile'
          + (f'; Einstellungen {einst}' if einst else ''))
    with Pool(max(1, min(a.parallel, len(auftraege)))) as pool:
        alle = pool.map(_eine, auftraege)
    tabelle([zusammenfassen(alle[i * a.fahrten:(i + 1) * a.fahrten]) for i in range(len(zeilen))])


if __name__ == '__main__':
    main()
