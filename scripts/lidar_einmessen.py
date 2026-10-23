#!/usr/bin/env python3
# LiDAR-Einbaupose am Geraet einmessen (#66) und Rohdaten vor der Abnahme pruefen (#67).
# Sendet NIE Fahr- oder Armbefehle: nur LaserScan lesen, rechnen, Text ausgeben.
#
# Ablauf (Anleitung und Messblatt: docs/geraete/RM01-lidar-geometrie.md):
#   source scripts/env.sh
#   python3 scripts/lidar_einmessen.py aufnehmen hintergrund        # Roboter steht, nichts Neues in der Naehe
#   python3 scripts/lidar_einmessen.py aufnehmen ziel1              # duennen Stab an gemessene Stelle stellen ...
#   python3 scripts/lidar_einmessen.py standcheck config/lokal/lidar_einmessung/hintergrund.json
#   python3 scripts/lidar_einmessen.py auswerten config/lokal/lidar_einmessung/messung.yaml   # auch ohne ROS
#
# Aufnahmen landen in config/lokal/lidar_einmessung/ (nicht im Repository: Rohdaten bleiben privat).
# Rechnung wie im Produkt (lib/lidar.py): p_basis = R(-scan_front_deg) * p_sensor + (x, y), x vorne, y links, m.
# Das Ergebnis ist ein VORSCHLAG fuer config/lokal/roboter.yaml - erst mit Datum/Pruefer/Unsicherheit im Messblatt
# eintragen. Hoehe (z), Neigung der Messebene und Fahrzeuggrenzen misst dieses Werkzeug nicht.
import argparse
import datetime
import json
import math
import os
import subprocess
import sys
import time

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(REPO, 'lib'))
import lidar  # noqa: E402

ORDNER = os.path.join(REPO, 'config', 'lokal', 'lidar_einmessung')
EIGENE_TEILE = 0.12      # m: so nahe Treffer sind meist eigene Teile (Notbremse-Abstand, #58)
MIN_NAEHER = 0.05        # m: um so viel muss ein Ziel naeher sein als der Hintergrund
MIN_STRAHLEN = 2         # ein einzelner Strahl ist Rauschen, kein Ziel
MIN_GUELTIG = 0.8        # Anteil der Scans, in denen ein Strahl gueltig sein muss (sonst unbekannt)
MIN_SPANNE = 0.15        # m: so weit muessen die Ziele mindestens auseinander stehen (sonst Drehung unbestimmt)


# ---------------- Aufnahme lesen ----------------
def scan_als_dict(msg, empfang_ros):
    """Ein LaserScan als JSON-faehiges dict (inf/NaN bleiben erhalten: json schreibt Infinity/NaN)."""
    st = msg.header.stamp
    return {'frame_id': msg.header.frame_id, 'stamp': st.sec + st.nanosec * 1e-9, 'empfang_ros': empfang_ros,
            'angle_min': float(msg.angle_min), 'angle_max': float(msg.angle_max),
            'angle_increment': float(msg.angle_increment), 'range_min': float(msg.range_min),
            'range_max': float(msg.range_max), 'ranges': [float(r) for r in msg.ranges]}


def geometrie(scans):
    """Gemeinsame Strahlgeometrie aller Scans eines Kanals oder ValueError (Treiber hat umgestellt)."""
    if not scans:
        raise ValueError('keine Scans')
    schluessel = ('frame_id', 'angle_min', 'angle_increment', 'range_min', 'range_max')
    erster = scans[0]
    for s in scans[1:]:
        if any(s[k] != erster[k] for k in schluessel) or len(s['ranges']) != len(erster['ranges']):
            raise ValueError('Scans eines Kanals haben verschiedene Frames/Winkel/Strahlzahl')
    winkel = erster['angle_min'] + np.arange(len(erster['ranges'])) * erster['angle_increment']
    return erster, np.arctan2(np.sin(winkel), np.cos(winkel))


def median_scan(scans):
    """(Winkel im Sensorbezug, Median je Strahl). NaN = Strahl in weniger als MIN_GUELTIG der Scans gueltig."""
    erster, winkel = geometrie(scans)
    r = np.array([s['ranges'] for s in scans], dtype=np.float64)
    gut = np.isfinite(r) & (r > erster['range_min']) & (r < erster['range_max'])
    median = np.full(r.shape[1], np.nan)
    stabil = gut.mean(axis=0) >= MIN_GUELTIG
    for k in np.flatnonzero(stabil):
        median[k] = np.median(r[gut[:, k], k])
    return winkel, median


def _laeufe(maske, rundum):
    """Zusammenhaengende True-Bereiche als Liste von Indexlisten (bei vollem Kreis auch ueber das Ende hinweg)."""
    idx = np.flatnonzero(maske)
    if not len(idx):
        return []
    laeufe, aktuell = [], [idx[0]]
    for k in idx[1:]:
        if k == aktuell[-1] + 1:
            aktuell.append(k)
        else:
            laeufe.append(aktuell)
            aktuell = [k]
    laeufe.append(aktuell)
    if rundum and len(laeufe) > 1 and laeufe[0][0] == 0 and laeufe[-1][-1] == len(maske) - 1:
        laeufe[0] = laeufe.pop() + laeufe[0]
    return laeufe


def _rundum(erster):
    return len(erster['ranges']) * abs(erster['angle_increment']) >= 2 * math.pi - 1e-6


def _sektoren(winkel, laeufe):
    return [(round(math.degrees(winkel[l[0]]), 1), round(math.degrees(winkel[l[-1]]), 1)) for l in laeufe]


# ---------------- Standcheck: offene Fragen aus #58 vor jeder Abnahme ----------------
def standcheck(scans, max_alter=lidar.AUFNAHME_MAX):
    """Was liefert ein Kanal wirklich? Frame, Zeitstempel, ungueltige Sektoren, Werte auf range_max, eigene Teile.
    Nur Befund, keine Freigabe. Rueckgabe: dict mit Zahlen und 'hinweise' (Liste Text)."""
    erster, winkel = geometrie(scans)
    r = np.array([s['ranges'] for s in scans], dtype=np.float64)
    rmin, rmax = erster['range_min'], erster['range_max']
    gut = np.isfinite(r) & (r > rmin) & (r < rmax)
    alter = np.array([s['empfang_ros'] - s['stamp'] for s in scans])
    stempel = [s['stamp'] for s in scans]
    rundum = _rundum(erster)
    ungueltig = _laeufe(gut.mean(axis=0) < 0.5, rundum)
    _, median = median_scan(scans)
    nah = _laeufe(np.isfinite(median) & (median < EIGENE_TEILE), rundum)
    b = {'frame_id': erster['frame_id'], 'scans': len(scans), 'strahlen': r.shape[1],
         'spanne_grad': round(math.degrees(r.shape[1] * abs(erster['angle_increment'])), 1),
         'range_min': rmin, 'range_max': rmax,
         'anteil_ungueltig': round(float(1 - gut.mean()), 4),
         'null_oder_unter_min': int(np.sum(np.isfinite(r) & (r <= rmin))),
         'nan': int(np.sum(np.isnan(r))), 'inf': int(np.sum(np.isinf(r))),
         'genau_range_max': int(np.sum(r == rmax)), 'ueber_range_max': int(np.sum(np.isfinite(r) & (r > rmax))),
         'alter_min_s': round(float(alter.min()), 3), 'alter_max_s': round(float(alter.max()), 3),
         'stempel_doppelt_oder_rueckwaerts': int(np.sum(np.diff(stempel) <= 0)),
         'ungueltige_sektoren_grad': _sektoren(winkel, ungueltig),
         'nahe_treffer_sektoren_grad': _sektoren(winkel, nah)}
    h = []
    if alter.min() < 0:
        h.append(f'Aufnahmezeit bis {-alter.min():.3f} s in der Zukunft: Uhren pruefen (Produkt haelt dann)')
    if alter.max() > max_alter:
        h.append(f'Aufnahme bis {alter.max():.2f} s alt (> {max_alter} s): Produkt haelt dann')
    if b['stempel_doppelt_oder_rueckwaerts']:
        h.append('doppelte oder rueckwaerts laufende Zeitstempel')
    if b['genau_range_max']:
        h.append(f"{b['genau_range_max']} Werte genau auf range_max: gelten als ungueltig (unbekannt, nicht frei)")
    if b['inf']:
        h.append(f"{b['inf']} inf-Werte: Bedeutung (kein Echo?) beim Treiber klaeren; gelten als ungueltig")
    if ungueltig:
        h.append(f'{len(ungueltig)} Sektor(en) meist ohne Messung (Sensorwinkel): Blindzone/eigener Aufbau? '
                 'Nur ein anderer LiDAR kann sie abdecken')
    if nah:
        h.append(f'Treffer naeher als {EIGENE_TEILE * 100:.0f} cm (Sensorwinkel): eigene Teile? '
                 'Muessen innerhalb fahrzeug_grenzen liegen, sonst haelt die Notbremse')
    b['hinweise'] = h
    return b


# ---------------- Ziele finden und Pose schaetzen ----------------
def ziel_finden(hintergrund, mit_ziel, durchmesser=0.0):
    """Das EINE neu hinzugekommene Ziel (duenner senkrechter Stab) in einem Kanal.
    Rueckgabe: ((x, y) Stabmitte im Sensorbezug, None) oder (None, Grund). Mehrere neue Bereiche = mehrdeutig
    (z. B. Person noch im Bild): lieber keine Zahl als eine falsche."""
    erster, winkel = geometrie(hintergrund + mit_ziel)
    _, hg = median_scan(hintergrund)
    _, zg = median_scan(mit_ziel)
    neu = np.isfinite(zg) & (~np.isfinite(hg) | (hg - zg > MIN_NAEHER))
    laeufe = [l for l in _laeufe(neu, _rundum(erster)) if len(l) >= MIN_STRAHLEN]
    if not laeufe:
        return None, 'kein Ziel gefunden'
    if len(laeufe) > 1:
        return None, f'mehrdeutig: {len(laeufe)} neue Bereiche bei {_sektoren(winkel, laeufe)} Grad'
    l = np.asarray(laeufe[0])
    # Mitte des Stabs: Richtung = mittlere Strahlrichtung, Abstand = Vorderkante + halber Durchmesser
    w = math.atan2(np.sin(winkel[l]).mean(), np.cos(winkel[l]).mean())
    r = float(np.min(zg[l])) + durchmesser / 2
    return (r * math.cos(w), r * math.sin(w)), None


def pose_schaetzen(sensor_xy, basis_xy, unsicherheit=0.005):
    """Starre 2D-Ausgleichsrechnung: basis = R(phi) * sensor + t, ueber alle Ziele (mind. 2, besser 4+).
    Rueckgabe: dict x, y, front_deg (= -phi, wie scan_front_deg), Residuen, U(k=2) je Groesse, Jackknife-Spanne.
    Unsicherheitsmodell: je Ziel und Achse sigma = max(angegebene Unsicherheit, RMS-Residuum)."""
    s = np.asarray(sensor_xy, dtype=np.float64).reshape(-1, 2)
    b = np.asarray(basis_xy, dtype=np.float64).reshape(-1, 2)
    n = len(s)
    if n < 2 or len(b) != n:
        raise ValueError('mindestens 2 Ziele noetig')
    if max(np.hypot(*(b[i] - b[j])) for i in range(n) for j in range(i)) < MIN_SPANNE:
        raise ValueError(f'Ziele zu dicht beieinander (mind. {MIN_SPANNE * 100:.0f} cm Abstand)')

    def loesen(s, b):
        sm, bm = s.mean(axis=0), b.mean(axis=0)
        h = (s - sm).T @ (b - bm)
        phi = math.atan2(h[0, 1] - h[1, 0], h[0, 0] + h[1, 1])
        rot = np.array([[math.cos(phi), -math.sin(phi)], [math.sin(phi), math.cos(phi)]])
        return phi, bm - rot @ sm, rot

    phi, t, rot = loesen(s, b)
    res = b - (s @ rot.T + t)
    rms = float(math.sqrt((res ** 2).sum(axis=1).mean()))
    sigma = max(unsicherheit, rms / math.sqrt(2))       # rms ist 2D, sigma je Achse
    streu = float(((s - s.mean(axis=0)) ** 2).sum())
    var_phi = sigma ** 2 / streu
    d = np.array([[-math.sin(phi), -math.cos(phi)], [math.cos(phi), -math.sin(phi)]]) @ s.mean(axis=0)
    u_xy = np.sqrt(sigma ** 2 / n + d ** 2 * var_phi)
    ergebnis = {'x': float(t[0]), 'y': float(t[1]), 'front_deg': float(-math.degrees(phi)), 'ziele': n,
                'residuen_m': [float(v) for v in np.hypot(res[:, 0], res[:, 1])], 'rms_m': rms,
                'U_x_m': float(2 * u_xy[0]), 'U_y_m': float(2 * u_xy[1]),
                'U_front_deg': float(2 * math.degrees(math.sqrt(var_phi))), 'jackknife': None}
    if n >= 3:
        teile = []
        for k in range(n):
            m = np.arange(n) != k
            p, tt, _ = loesen(s[m], b[m])
            teile.append((tt[0], tt[1], -math.degrees(p)))
        teile = np.array(teile)
        dw = (teile[:, 2] - ergebnis['front_deg'] + 180) % 360 - 180
        ergebnis['jackknife'] = {'x_m': float(np.ptp(teile[:, 0])), 'y_m': float(np.ptp(teile[:, 1])),
                                 'front_deg': float(np.ptp(dw))}
    ergebnis['front_deg'] = (ergebnis['front_deg'] + 180) % 360 - 180
    return ergebnis


def _lade(pfad):
    with open(pfad) as f:
        return json.load(f)


def auswerten(messung, basis_ordner):
    """Messblatt (dict aus YAML) auswerten. Rueckgabe: (Ergebnis je Topic, Liste Probleme)."""
    def pfad(p):
        return p if os.path.isabs(p) else os.path.join(basis_ordner, p)

    hintergrund = _lade(pfad(messung['hintergrund']))['topics']
    durchmesser = float(messung.get('ziel_durchmesser', 0.0))
    u_ziel = float(messung.get('ziel_unsicherheit', 0.005))
    ziele = messung.get('ziele') or []
    ergebnis, probleme = {}, []
    for topic in hintergrund:          # Reihenfolge der Aufnahme = scan_topics
        sensor, basis, notizen = [], [], []
        for z in ziele:
            daten = _lade(pfad(z['aufnahme']))['topics'].get(topic)
            if not daten:
                notizen.append(f"{z['aufnahme']}: Kanal fehlt")
                continue
            try:
                xy, grund = ziel_finden(hintergrund[topic]['scans'], daten['scans'], durchmesser)
            except ValueError as e:
                xy, grund = None, str(e)
            if xy is None:
                notizen.append(f"{z['aufnahme']}: {grund}")
                continue
            sensor.append(xy)
            basis.append((float(z['x']), float(z['y'])))
        eintrag = {'frame_id': hintergrund[topic]['scans'][0]['frame_id'], 'notizen': notizen}
        try:
            eintrag.update(pose_schaetzen(sensor, basis, u_ziel))
        except ValueError as e:
            probleme.append(f'{topic}: {e} ({len(sensor)} Ziele erkannt)')
        band = (messung.get('sensoren') or {}).get(topic)
        if band and 'x' in eintrag:
            abweichung = math.hypot(eintrag['x'] - band['x'], eintrag['y'] - band['y'])
            grenze = math.hypot(max(eintrag['U_x_m'], eintrag['U_y_m']), float(band.get('unsicherheit', 0.01)))
            eintrag['massband_abweichung_m'] = abweichung
            eintrag['massband_passt'] = abweichung <= grenze
            if abweichung > grenze:
                probleme.append(f'{topic}: Massband und Zielmessung weichen {abweichung * 100:.1f} cm ab '
                                f'(erlaubt {grenze * 100:.1f} cm) - Topics vertauscht oder Messfehler?')
        ergebnis[topic] = eintrag
    frames = [e['frame_id'] for e in ergebnis.values() if e['frame_id'] != lidar.BASIS_FRAME]
    if len(set(frames)) != len(frames):
        probleme.append('mehrere Kanaele melden denselben Frame: Treiber-Frames eindeutig benennen (#64)')
    return ergebnis, probleme


def vorschlag(ergebnis, messung):
    """Textvorschlag fuer config/lokal/roboter.yaml (nur wenn jeder Kanal eine Pose hat)."""
    topics = list(ergebnis)
    if not topics or any('x' not in ergebnis[t] for t in topics):
        return None
    xy = [round(v, 4) + 0.0 for t in topics for v in (ergebnis[t]['x'], ergebnis[t]['y'])]   # + 0.0: kein -0.0
    return '\n'.join([
        f"# Vorschlag lidar_einmessen.py: {messung.get('geraet', '?')}, {messung.get('datum', '?')}, "
        f"Pruefer {messung.get('pruefer', '?')}.",
        '# Erst nach Eintrag im Messblatt (docs/geraete/) in config/lokal/roboter.yaml uebernehmen.',
        '/**:', '  ros__parameters:',
        f'    scan_topics: {json.dumps(topics)}',
        f"    scan_frames: {json.dumps([ergebnis[t]['frame_id'] for t in topics])}",
        f"    scan_front_deg: {json.dumps([round(ergebnis[t]['front_deg'], 2) + 0.0 for t in topics])}",
        f'    scan_einbau_xy: {json.dumps(xy)}',
        f"    scan_einbau_quelle: {json.dumps(['gemessen'] * len(topics))}",
        '    # fahrzeug_grenzen: [vorne, hinten, links, rechts]   # separat messen: ganze Fahrstellung'])


def bericht(ergebnis, probleme, messung):
    zeilen = [f"LiDAR-Einmessung {messung.get('geraet', '?')} am {messung.get('datum', '?')}, "
              f"Pruefer {messung.get('pruefer', '?')}, Bezug: {messung.get('bezug', '?')}", '']
    for t, e in ergebnis.items():
        zeilen.append(f"{t} (frame {e['frame_id']!r}):")
        if 'x' in e:
            jk = e['jackknife']
            zeilen += [f"  x {e['x']:+.4f} m (U {e['U_x_m'] * 100:.1f} cm), y {e['y']:+.4f} m "
                       f"(U {e['U_y_m'] * 100:.1f} cm), scan_front_deg {e['front_deg']:+.2f} "
                       f"(U {e['U_front_deg']:.2f} Grad), U mit k=2",
                       f"  {e['ziele']} Ziele, RMS {e['rms_m'] * 100:.1f} cm, groesstes Residuum "
                       f"{max(e['residuen_m']) * 100:.1f} cm"
                       + (f", Jackknife x/y/Winkel {jk['x_m'] * 100:.1f} cm / {jk['y_m'] * 100:.1f} cm / "
                          f"{jk['front_deg']:.2f} Grad" if jk else ', fuer Jackknife mind. 3 Ziele')]
            if 'massband_passt' in e:
                zeilen.append(f"  Massband-Abgleich: {e['massband_abweichung_m'] * 100:.1f} cm "
                              f"{'passt' if e['massband_passt'] else 'PASST NICHT'}")
        zeilen += [f'  - {n}' for n in e['notizen']]
    if probleme:
        zeilen += ['', 'PROBLEME (kein Vorschlag uebernehmen):'] + [f'  - {p}' for p in probleme]
    return '\n'.join(zeilen)


# ---------------- ROS: nur lesen ----------------
def git_stand():
    def git(*args):
        try:
            return subprocess.run(['git', '-C', REPO, *args], capture_output=True, text=True, timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            return ''
    return {'sha': git('rev-parse', 'HEAD').strip() or None, 'sauber': git('status', '--porcelain') == ''}


def aufnehmen(name, topics, anzahl, ordner, wartezeit):
    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import LaserScan
    rclpy.init()
    node = rclpy.create_node('lidar_einmessen')
    daten = {t: [] for t in topics}

    def empfang(msg, topic):
        if len(daten[topic]) < anzahl:
            daten[topic].append(scan_als_dict(msg, node.get_clock().now().nanoseconds * 1e-9))

    for t in topics:
        node.create_subscription(LaserScan, t, lambda m, t=t: empfang(m, t), qos_profile_sensor_data)
    ende = time.monotonic() + wartezeit
    try:
        while time.monotonic() < ende and any(len(v) < anzahl for v in daten.values()):
            rclpy.spin_once(node, timeout_sec=0.1)
    finally:
        node.destroy_node()
        rclpy.shutdown()
    fehlt = [f'{t}: {len(v)}/{anzahl}' for t, v in daten.items() if len(v) < anzahl]
    os.makedirs(ordner, exist_ok=True)
    datei = os.path.join(ordner, f'{name}.json')
    with open(datei, 'w') as f:
        json.dump({'name': name, 'erstellt_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   'git': git_stand(), 'topics': {t: {'scans': v} for t, v in daten.items() if v}}, f)
    print(f'gespeichert: {datei}')
    if fehlt:
        print('ACHTUNG, zu wenige Scans: ' + ', '.join(fehlt))
        return 1
    return 0


def standard_topics():
    try:
        import einstellungen
        return list(einstellungen.lade().get('scan_topics') or [])
    except Exception:
        return ['/scan0', '/scan1']


def main(argv=None):
    ap = argparse.ArgumentParser(description='LiDAR-Einbaupose einmessen (#66), Rohdaten pruefen (#67). '
                                             'Sendet keine Fahr-/Armbefehle.')
    sub = ap.add_subparsers(dest='befehl', required=True)
    a = sub.add_parser('aufnehmen', help='Scans aller Kanaele speichern (ROS, nur lesen)')
    a.add_argument('name')
    a.add_argument('--topics', nargs='+', default=None)
    a.add_argument('--scans', type=int, default=30)
    a.add_argument('--ordner', default=ORDNER)
    a.add_argument('--wartezeit', type=float, default=20.0)
    s = sub.add_parser('standcheck', help='Frame, Zeitstempel, Blindsektoren, range_max, eigene Teile')
    s.add_argument('aufnahme')
    w = sub.add_parser('auswerten', help='Pose aus Messblatt (YAML) berechnen, ohne ROS')
    w.add_argument('messung')
    args = ap.parse_args(argv)
    if args.befehl == 'aufnehmen':
        return aufnehmen(args.name, args.topics or standard_topics(), args.scans, args.ordner, args.wartezeit)
    if args.befehl == 'standcheck':
        daten = _lade(args.aufnahme)
        print(f"Aufnahme {daten.get('name')}, Software {daten.get('git')}")
        for topic, kanal in sorted(daten['topics'].items()):
            b = standcheck(kanal['scans'])
            print(f'\n{topic}:')
            for k, v in b.items():
                if k != 'hinweise':
                    print(f'  {k}: {v}')
            for h in b['hinweise']:
                print(f'  ! {h}')
        return 0
    import yaml
    with open(args.messung) as f:
        messung = yaml.safe_load(f) or {}
    ergebnis, probleme = auswerten(messung, os.path.dirname(os.path.abspath(args.messung)))
    print(bericht(ergebnis, probleme, messung))
    text = None if probleme else vorschlag(ergebnis, messung)
    if text:
        print('\n' + text)
    return 1 if probleme or not text else 0


if __name__ == '__main__':
    sys.exit(main())
