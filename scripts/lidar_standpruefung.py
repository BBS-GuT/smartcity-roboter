#!/usr/bin/env python3
# Statische LiDAR-Etappe der Geraeteabnahme (#67) gefuehrt protokollieren.
# Sendet NIE Fahr- oder Armbefehle: liest nur /line_follower/status und /ki/befehl, fragt die pruefende Person
# nach jedem Schritt und schreibt den versionsbezogenen Bericht docs/abnahme/RM01-lidar-halt-<Datum>.md.
#
# Voraussetzung: Linienfolger im TESTMODUS (Panel -> TEST oder drive:=false) und KI-Zentrale laufen, "KI darf den
# Arm bewegen" ist AUS. Laeuft der Linienfolger mit drive=true oder darf die KI den Arm bewegen, bricht das Werkzeug
# ab. Ablauf und Faelle: docs/abnahme/lidar-messung-und-ausfallpruefung.md (S01-S11). Bewegte Faelle (M01-M06)
# sind eine eigene, gesondert freigegebene Etappe und werden hier nie als bestanden eingetragen.
#
#   source scripts/env.sh && python3 scripts/lidar_standpruefung.py --geraet RM01 --pruefer "Name" --beobachter "Name"
#   python3 scripts/lidar_standpruefung.py ... --nur S01 S03a     # einzelne Faelle
#
# Gemessen wird nur, was die Software meldet (Haltegrund, rechnerischer Befehl im Testmodus) und wann sie es
# meldet, gerechnet ab der Bestaetigung durch die pruefende Person (Bedienzeit steckt mit drin). Das ist KEINE
# Motor-Haltzeit: tatsaechlicher Stillstand, Restweg und Wiederanlauf gehoeren zu M01-M06.
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(REPO, 'lib'))

LIDAR_HALT = ('KEIN LIDAR', 'LIDAR UNBEKANNT', 'NOTBREMSE')
LIDAR_PARAMETER = ('scan_topics', 'scan_frames', 'scan_front_deg', 'scan_einbau_xy', 'scan_einbau_quelle',
                   'fahrzeug_grenzen', 'obstacle_check', 'notbremse_dist', 'obstacle_half_deg',
                   'obstacle_min_range', 'direction', 'fahrschlauch_breite', 'fahrschlauch_laenge')
FENSTER = 6.0       # s beobachten je Fall
EINSCHWINGEN = 2.0  # s nach der Bestaetigung: erst danach muss der Zustand stabil sein


@dataclass
class Fall:
    id: str
    titel: str
    anleitung: str
    erwartung: str          # 'frei' | 'halt' | 'notbremse' | 'ki_abstand'
    enthaelt: tuple = ()    # zusaetzlich im LiDAR-Haltegrund erwartet (eines davon), Platzhalter {A}/{B}
    soll: str = ''


FAELLE = [
    Fall('S01', 'Beide Quellen frisch, Pruefbereich frei',
         'Beide LiDARs laufen, im Bereich vor dem Roboter (mind. 1 m) steht nichts.', 'frei',
         soll='Kein LiDAR-Haltegrund; KI meldet einen Abstand (kein "unbekannt"). Allein keine Fahrfreigabe.'),
    Fall('S02a', 'Quelle {A} vollstaendig ungueltig',
         'Sensor {A} vollstaendig abdecken (z. B. Becher darueber), {B} frei lassen.', 'halt',
         soll='LiDAR-Halt; KI "unbekannt" oder Hindernis. Rechnerischer Befehl 0.'),
    Fall('S02b', 'Quelle {B} vollstaendig ungueltig',
         'Abdeckung von {A} entfernen, jetzt Sensor {B} vollstaendig abdecken.', 'halt',
         soll='LiDAR-Halt; KI "unbekannt" oder Hindernis. Rechnerischer Befehl 0.'),
    Fall('S11a', 'Rueckkehr nach S02', 'Alle Abdeckungen entfernen.', 'frei',
         soll='LiDAR-Haltegrund verschwindet nach gueltigen frischen Daten.'),
    Fall('S04a', 'Quelle {A} faellt im Betrieb aus',
         'GENAU beim Bestaetigen den Treiber/Stecker von {A} trennen ({B} laeuft weiter).', 'halt', ('{A}',),
         soll='Halt mit Grund fuer {A} nach Ablauf der Altersgrenze; {B} ersetzt {A} nicht.'),
    Fall('S11b', 'Rueckkehr {A}', '{A} wieder verbinden/starten und warten, bis Scans kommen.', 'frei',
         soll='LiDAR-Haltegrund verschwindet.'),
    Fall('S04b', 'Quelle {B} faellt im Betrieb aus',
         'GENAU beim Bestaetigen den Treiber/Stecker von {B} trennen ({A} laeuft weiter).', 'halt', ('{B}',),
         soll='Halt mit Grund fuer {B}; {A} ersetzt {B} nicht.'),
    Fall('S11c', 'Rueckkehr {B}', '{B} wieder verbinden/starten und warten, bis Scans kommen.', 'frei',
         soll='LiDAR-Haltegrund verschwindet.'),
    Fall('S03', 'Quelle fehlt seit Start',
         'Linienfolger beenden, {A} getrennt lassen, Linienfolger im TESTMODUS neu starten.', 'halt',
         ('{A}',), soll='"noch nie ein Scan" bzw. fehlende Pflichtquelle {A}: Halt.'),
    Fall('S07', 'Unbekannte/widerspruechliche Geometrie',
         'In config/lokal/roboter.yaml z. B. scan_frames entfernen oder einen Frame falsch setzen, Linienfolger '
         'und KI neu starten. Danach Konfiguration zuruecksetzen und neu starten.', 'halt',
         ('Geometrie', 'Frame', 'Einbau', 'doppelt', 'fahrzeug_grenzen'),
         soll='Halt wegen Geometrie/Frame, keine Ersatzpose.'),
    Fall('S08', 'Gemeinsame Messluecke im Fahrbereich',
         'Wenn moeglich: einen Bereich vor dem Roboter fuer BEIDE Sensoren ohne Echo machen (z. B. schwarzer '
         'Samt, offene Tuer ins Leere), ohne festen Gegenstand im Schutzbereich.', 'halt',
         ('nicht gemeinsam gemessen', 'nicht gemessen', 'ohne Messung'),
         soll='LIDAR UNBEKANNT (Abdeckung), kein Freiraum trotz gueltiger Punkte daneben.'),
    Fall('S09a', 'Ziel direkt vor der Fahrzeugfront',
         'Zielkoerper (hoeher als die Messebene) mittig, ca. 5-8 cm vor die vorderste Fahrzeugkante stellen.',
         'notbremse', soll='NOTBREMSE im Roboterbezug.'),
    Fall('S09b', 'Ziel im Fahrschlauch, ausserhalb des Notbremsbereichs',
         'Zielkoerper mittig vor den Roboter stellen; den Abstand (m) vom Ursprung base_link messen.',
         'ki_abstand', soll='KI meldet das Ziel im Fahrschlauch passend zum gemessenen Abstand.'),
    Fall('S09c', 'Ziel seitlich ausserhalb von Fahrschlauch und Schutzbereich',
         'Zielkoerper deutlich seitlich neben den Fahrschlauch stellen (z. B. 0,5 m vor, 0,4 m seitlich).', 'frei',
         soll='Kein falscher Hindernisbeleg im Roboterbezug.'),
    Fall('S09d', 'Ziel direkt hinter dem Heck (nur mit direction:=-1.0)',
         'Linienfolger im TESTMODUS mit -p direction:=-1.0 starten, Ziel ca. 5-8 cm hinter die hinterste Kante.',
         'notbremse', soll='NOTBREMSE hinten. Danach Linienfolger wieder normal (direction 1.0) starten.'),
]
BEWEGT = [('M01', 'Langsame Vor-/Rueckfahrt gegen bekanntes Ziel'), ('M02', 'Pflichtkanal faellt waehrend Fahrt aus'),
          ('M03', 'Seitwaerts/Drehung/Kurve gegen Ziel oder Ecke'), ('M04', 'Niedriges Ziel unter der Messebene'),
          ('M05', 'Bedien-STOPP, Fahrprozess-/Senderausfall'), ('M06', 'Wiederanlauf nach Rueckkehr/STOPP')]


def lidar_grund(status):
    """LiDAR-Haltegrund aus dem Statustext des Linienfolgers oder None."""
    if not isinstance(status, str):
        return None
    return status if any(s in status for s in LIDAR_HALT) else None


def platzhalter(text, a, b):
    return text.replace('{A}', a).replace('{B}', b)


def bewerten(fall, proben, start, quellen, abstand_soll=None, toleranz=0.05):
    """Ein Fall aus den beobachteten Proben. proben: [(zeit, 'lf'|'ki', dict)], start: Bestaetigungszeit.
    Rueckgabe: dict status ('bestanden' | 'nicht bestanden' | 'blockiert'), ist (Text), werte (dict)."""
    a, b = quellen
    lf = [(t, d) for t, q, d in proben if q == 'lf']
    ki = [(t, d) for t, q, d in proben if q == 'ki']
    werte = {'proben_linienfolger': len(lf), 'proben_ki': len(ki)}
    if not lf:
        return {'status': 'blockiert', 'ist': 'keine Statusmeldung vom Linienfolger', 'werte': werte}
    if any(d.get('drive') is not False for _, d in lf):
        return {'status': 'blockiert', 'ist': 'Linienfolger NICHT im Testmodus (drive) - abgebrochen',
                'werte': werte, 'abbruch': True}
    if any(d.get('arm_erlaubt') for _, d in ki):
        return {'status': 'blockiert', 'ist': 'KI darf den Arm bewegen - abgebrochen', 'werte': werte,
                'abbruch': True}
    stabil = [(t, d) for t, d in lf if t >= start + EINSCHWINGEN]
    stabil_ki = [(t, d) for t, d in ki if t >= start + EINSCHWINGEN]
    if not stabil:
        return {'status': 'blockiert', 'ist': 'nach dem Einschwingen keine Statusmeldung mehr', 'werte': werte}
    gruende = sorted({g for _, d in stabil if (g := lidar_grund(d.get('status')))})
    werte['lidar_gruende'] = [g[:160] for g in gruende]
    befehle = {(d.get('linear'), d.get('quer'), d.get('angular')) for _, d in stabil if lidar_grund(d.get('status'))}
    werte['befehl_bei_halt'] = sorted(befehle)
    ki_lidar = [d.get('lidar') for _, d in stabil_ki]
    werte['ki_lidar'] = sorted({v for v in ki_lidar if v is not None}) + (['unbekannt'] if None in ki_lidar else [])
    erste = next((t for t, d in lf if t >= start and lidar_grund(d.get('status'))), None)
    werte['erster_halt_nach_s'] = None if erste is None else round(erste - start, 2)
    alle_halt = all(lidar_grund(d.get('status')) for _, d in stabil)
    kein_halt = not any(lidar_grund(d.get('status')) for _, d in stabil)
    null = befehle <= {(0.0, 0.0, 0.0), (0, 0, 0)}
    fehler = []
    if fall.erwartung == 'frei':
        if not kein_halt:
            fehler.append('LiDAR-Haltegrund vorhanden')
        if fall.id == 'S01' and (not stabil_ki or None in ki_lidar):
            fehler.append('KI meldet LiDAR unbekannt oder keine KI-Meldung')
    elif fall.erwartung in ('halt', 'notbremse'):
        if not alle_halt:
            fehler.append('nicht durchgehend LiDAR-Halt')
        if not null:
            fehler.append(f'rechnerischer Befehl bei Halt nicht 0: {sorted(befehle)}')
        if fall.erwartung == 'notbremse' and not all('NOTBREMSE' in (d.get('status') or '') for _, d in stabil):
            fehler.append('kein NOTBREMSE-Grund')
        erwartet = [platzhalter(e, a, b) for e in fall.enthaelt]
        if erwartet and not all(any(e in g for e in erwartet) for g in gruende):
            fehler.append(f'Grund nennt nicht {" / ".join(erwartet)}')
    elif fall.erwartung == 'ki_abstand':
        zahlen = [v for v in ki_lidar if isinstance(v, (int, float)) and v < 99.0]
        if abstand_soll is None:
            return {'status': 'blockiert', 'ist': 'kein gemessener Sollabstand eingegeben', 'werte': werte}
        werte['abstand_soll_m'] = abstand_soll
        if not stabil_ki or len(zahlen) != len(ki_lidar):
            fehler.append('KI meldet das Ziel nicht durchgehend')
        elif max(abs(v - abstand_soll) for v in zahlen) > toleranz:
            fehler.append(f'KI-Abstand {min(zahlen):.3f}-{max(zahlen):.3f} m statt {abstand_soll:.3f} '
                          f'+-{toleranz:.2f} m')
    ist = '; '.join(werte['lidar_gruende']) or 'kein LiDAR-Haltegrund'
    return {'status': 'nicht bestanden' if fehler else 'bestanden', 'ist': ist, 'fehler': fehler, 'werte': werte}


# ---------------- Pruefkopf und Bericht ----------------
def git_stand():
    def git(*args):
        try:
            return subprocess.run(['git', '-C', REPO, *args], capture_output=True, text=True, timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            return ''
    return {'sha': git('rev-parse', 'HEAD').strip() or None, 'aenderungen': git('status', '--porcelain').strip()}


def konfiguration():
    """Effektive LiDAR-Parameter aus denselben Dateien wie beim Start (spaetere gelten vor frueheren)."""
    import einstellungen
    dateien = einstellungen.dateien()
    werte = {}
    for knoten in ('line_follower', 'ki_zentrale'):
        alle = einstellungen.lade(knoten)
        werte[knoten] = {k: alle[k] for k in LIDAR_PARAMETER if k in alle}
    h = hashlib.sha256()
    for d in dateien:
        with open(d, 'rb') as f:
            h.update(f.read())
    return {'dateien': [os.path.relpath(d, REPO) for d in dateien], 'sha256': h.hexdigest(), 'werte': werte}


def _zelle(text):
    return str(text).replace('|', '/').replace('\n', ' ')


def bericht(kopf, ergebnisse):
    sha = kopf['git']['sha'] or 'unbekannt'
    a, b = kopf['quellen']
    baum = kopf['git']['aenderungen']
    baum = 'sauber' if not baum else 'NICHT sauber: ' + _zelle(baum[:300])
    cfg = kopf['konfiguration']
    z = [f"# {kopf['geraet']}: LiDAR-Halt, statische Etappe am {kopf['datum']}", '',
         'Bezug: [#67](https://github.com/BBS-GuT/smartcity-roboter/issues/67), Matrix: '
         '[Ausfallpruefung](lidar-messung-und-ausfallpruefung.md). Erzeugt mit `scripts/lidar_standpruefung.py`.',
         '**Nur statische Etappe im Testmodus: keine Fahr-/Armbefehle, keine gemessene Motor-Haltzeit, '
         'keine Fahrfreigabe.**', '', '## Pruefkopf', '', '| Feld | Eintrag |', '|---|---|',
         f"| Geraet / Pruefer / Beobachter | {_zelle(kopf['geraet'])} / {_zelle(kopf['pruefer'])} / "
         f"{_zelle(kopf['beobachter'])} |",
         f"| Beginn / Ende (UTC) | {kopf['beginn']} / {kopf.get('ende', 'offen')} |",
         f"| Installierter Commit | `{sha}` |",
         f'| Arbeitsbaum | {baum} |',
         f"| Konfiguration | {', '.join(cfg['dateien'])}; SHA256 `{cfg['sha256'][:16]}` |",
         f'| Quellen A / B | {a} / {b} |', '', 'Effektive LiDAR-Parameter je Programm:', '', '```']
    z += [f'{knoten}: {json.dumps(werte, ensure_ascii=False)}' for knoten, werte in cfg['werte'].items()]
    z += ['```', '', '## Statische Faelle', '',
          '| Fall | Soll | Ist (Haltegrund) | Messwerte | Status |', '|---|---|---|---|---|']
    for fall, e in ergebnisse:
        w = e.get('werte', {})
        mess = [f"erster Halt nach {w['erster_halt_nach_s']} s (inkl. Bedienzeit)"
                if w.get('erster_halt_nach_s') is not None else None,
                f"KI lidar {w.get('ki_lidar')}" if w.get('ki_lidar') else None,
                f"Befehl bei Halt {w.get('befehl_bei_halt')}" if w.get('befehl_bei_halt') else None,
                f"Soll {w['abstand_soll_m']} m" if 'abstand_soll_m' in w else None,
                f"Proben LF/KI {w.get('proben_linienfolger', 0)}/{w.get('proben_ki', 0)}"]
        ist = e['ist'] + (' — ' + '; '.join(e['fehler']) if e.get('fehler') else '')
        if e.get('notiz'):
            ist += f" (Notiz: {e['notiz']})"
        z.append(f"| {fall.id} {_zelle(platzhalter(fall.titel, a, b))} | {_zelle(platzhalter(fall.soll, a, b))} | "
                 f"{_zelle(ist)} | "
                 f"{_zelle('; '.join(m for m in mess if m))} | **{e['status']}** |")
    z += ['', '## Bewegte Faelle (eigene, gesondert freigegebene Etappe)', '',
          '| Fall | Status |', '|---|---|']
    z += [f'| {i} {t} | nicht durchgefuehrt (blockiert bis zur separaten Freigabe) |' for i, t in BEWEGT]
    z += ['', 'Status je Fall gilt nur fuer den oben genannten Commit und diese Konfiguration. Rohdaten: '
          f"`{kopf.get('rohdaten', 'config/lokal/lidar_standpruefung/')}` (privat). Vor Veroeffentlichung "
          'Geraete-/Netzdaten pruefen.', '']
    return '\n'.join(z)


# ---------------- ROS: nur lesen ----------------
class Beobachter:
    def __init__(self):
        import rclpy
        from std_msgs.msg import String
        self.rclpy = rclpy
        rclpy.init()
        self.node = rclpy.create_node('lidar_standpruefung')
        self.proben = []
        self.node.create_subscription(String, '/line_follower/status', lambda m: self._neu('lf', m), 10)
        self.node.create_subscription(String, '/ki/befehl', lambda m: self._neu('ki', m), 10)

    def _neu(self, quelle, msg):
        try:
            self.proben.append((time.monotonic(), quelle, json.loads(msg.data)))
        except ValueError:
            pass

    def beobachten(self, dauer):
        self.proben = []
        start = time.monotonic()
        while time.monotonic() - start < dauer:
            self.rclpy.spin_once(self.node, timeout_sec=0.05)
        return start, list(self.proben)

    def ende(self):
        self.node.destroy_node()
        self.rclpy.shutdown()


def durchfuehren(faelle, quellen, beobachter, frage=input, ausgabe=print, fenster=FENSTER):
    ergebnisse = []
    a, b = quellen
    for fall in faelle:
        ausgabe(f'\n{fall.id} {platzhalter(fall.titel, a, b)}\n  {platzhalter(fall.anleitung, a, b)}')
        ausgabe(f'  Soll: {platzhalter(fall.soll, a, b)}')
        antwort = frage('  Enter = durchfuehren, "s Grund" = blockiert/ueberspringen, "q" = Ende: ').strip()
        if antwort.lower() == 'q':
            break
        if antwort.lower().startswith('s'):
            ergebnisse.append((fall, {'status': 'blockiert', 'ist': 'nicht durchgefuehrt: '
                                      + (antwort[1:].strip() or 'ohne Grund')}))
            continue
        start, proben = beobachter.beobachten(fenster)
        soll_abstand = None
        if fall.erwartung == 'ki_abstand':
            try:
                eingabe = frage('  Gemessener Abstand Ziel-Vorderkante zum Ursprung (m): ')
                soll_abstand = float(eingabe.replace(',', '.'))
            except ValueError:
                soll_abstand = None
        e = bewerten(fall, proben, start, quellen, soll_abstand)
        notiz = frage(f"  Ergebnis: {e['status']} ({e['ist'][:120]}). Notiz (optional): ").strip()
        if notiz:
            e['notiz'] = notiz
        ergebnisse.append((fall, e))
        if e.get('abbruch'):
            ausgabe('ABBRUCH: ' + e['ist'])
            break
    return ergebnisse


def main(argv=None):
    ap = argparse.ArgumentParser(description='Statische LiDAR-Etappe (#67) protokollieren. Sendet nichts.')
    ap.add_argument('--geraet', required=True)
    ap.add_argument('--pruefer', required=True)
    ap.add_argument('--beobachter', required=True)
    ap.add_argument('--nur', nargs='+', default=None, help='nur diese Fall-IDs')
    ap.add_argument('--fenster', type=float, default=FENSTER)
    ap.add_argument('--bericht', default=None, help='Standard: docs/abnahme/<Geraet>-lidar-halt-<Datum>.md')
    args = ap.parse_args(argv)
    cfg = konfiguration()
    topics = cfg['werte']['line_follower'].get('scan_topics') or ['/scan0', '/scan1']
    if len(topics) != 2:
        print(f'Erwartet genau zwei Pflichtquellen, eingestellt: {topics}')
        return 1
    jetzt = datetime.datetime.now(datetime.timezone.utc)
    kopf = {'geraet': args.geraet, 'pruefer': args.pruefer, 'beobachter': args.beobachter,
            'datum': jetzt.date().isoformat(), 'beginn': jetzt.isoformat(timespec='seconds'),
            'git': git_stand(), 'konfiguration': cfg, 'quellen': list(topics)}
    faelle = [f for f in FAELLE if not args.nur or f.id in args.nur]
    beobachter = Beobachter()
    try:
        ergebnisse = durchfuehren(faelle, topics, beobachter, fenster=args.fenster)
    finally:
        beobachter.ende()
    kopf['ende'] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    ordner = os.path.join(REPO, 'config', 'lokal', 'lidar_standpruefung')
    os.makedirs(ordner, exist_ok=True)
    roh = os.path.join(ordner, f"{args.geraet}-{jetzt.strftime('%Y%m%d-%H%M%S')}.json")
    with open(roh, 'w') as f:
        json.dump({'kopf': kopf, 'ergebnisse': [(fall.id, e) for fall, e in ergebnisse]}, f, indent=1)
    kopf['rohdaten'] = os.path.relpath(roh, REPO)
    ziel = args.bericht or os.path.join(REPO, 'docs', 'abnahme', f"{args.geraet}-lidar-halt-{kopf['datum']}.md")
    basis, k = ziel, 2
    while os.path.exists(ziel):          # fruehere Ergebnisse nie ueberschreiben
        ziel = basis.replace('.md', f'-{k}.md')
        k += 1
    with open(ziel, 'w') as f:
        f.write(bericht(kopf, ergebnisse))
    print(f'\nBericht: {os.path.relpath(ziel, REPO)}\nRohdaten (privat): {kopf["rohdaten"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
