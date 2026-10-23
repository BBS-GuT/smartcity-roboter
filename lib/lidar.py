#!/usr/bin/env python3
# LiDAR-Auswertung (ohne ROS-Abhaengigkeit, damit testbar).
#
# Ein LiDAR misst in einer DUENNEN WAAGRECHTEN SCHEIBE auf seiner eigenen Hoehe
# den Abstand rundherum. Ein Schuh erscheint deshalb nur als kurzer Bogen
# (seine Vorderkante), nicht als Flaeche. Was niedriger oder hoeher als die
# Scheibe ist, sieht er gar nicht.
from dataclasses import dataclass
import math
from numbers import Integral

import numpy as np

# Ein Strahl gilt hoechstens fuer +-1 Grad um seine Richtung als Messung (halber Strahlabstand, aber nie mehr):
# ein 3-cm-Hindernis am Ende des Fahrschlauchs (0,8 m) ist ca. 2 Grad breit. Groebere Scans (oder ein kaputter
# riesiger angle_increment) decken so nur Teile ab -> der Rest ist unbekannt.
STRAHL_RADIUS_MAX = math.radians(1.0)

# Aufnahmezeit (header.stamp) eines Scans: so alt darf sie bei der Auswertung hoechstens sein (s). Gleiche Grenze
# wie fuer den Empfang (1 s, schon vorher so) - keine eigene, am Geraet nicht gemessene Toleranz.
AUFNAHME_MAX = 1.0


def scan_pruefen(msg):
    """Ist der Scan ueberhaupt verwertbar? None = ja, sonst der Grund (Text).

    Unbrauchbar: kaputte Bereichs-/Winkelangaben, keine Messwerte oder kein einziger gueltiger Wert
    (alle 0 unter range_min, NaN, inf, ausserhalb range_max). Ein solcher Scan sagt NICHTS ueber den Weg -
    er darf nie als "frei" gelten (vorher: keine Punkte -> kein Hindernis -> frei). Die Verbraucher
    halten dann wie ohne LiDAR; der naechste verwertbare Scan desselben Kanals gibt wieder frei.
    """
    try:
        meta = [float(msg.range_min), float(msg.range_max), float(msg.angle_min), float(msg.angle_increment),
                float(msg.angle_max)]
        r = np.asarray(msg.ranges, dtype=np.float64)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return 'Scan unlesbar'
    if (not all(math.isfinite(v) for v in meta) or meta[0] < 0 or meta[1] <= meta[0] or meta[3] == 0):
        return 'Bereichs-/Winkelangaben ungueltig'
    if r.ndim != 1 or r.size == 0:
        return 'keine Messwerte'
    if not winkelspanne_ok(r.size, meta[3]):
        return 'Winkelangaben ungueltig (mehr als eine Umdrehung)'
    # angle_max muss zur Strahlgeometrie passen (angle_min + (N-1) * angle_increment). Ein Strahlabstand
    # Spielraum: manche Treiber rechnen angle_increment = Spanne / N statt / (N-1).
    if abs(meta[2] + (r.size - 1) * meta[3] - meta[4]) > abs(meta[3]) + 1e-6:
        return 'Winkelangaben widerspruechlich (angle_max passt nicht zu Strahlzahl und -abstand)'
    if not np.any(np.isfinite(r) & (r > meta[0]) & (r < meta[1])):
        return 'kein gueltiger Messwert (alle 0/NaN/inf/ausserhalb)'
    return None


def aufnahme_alter(aufnahme, jetzt, max_alter=AUFNAHME_MAX, *, max_zukunft=0.0):
    """Ist die Aufnahmezeit (s, ROS-Zeit) bei 'jetzt' (gleiche Uhr) noch aktuell? None = ja, sonst Grund.
    Standard: keine Zukunft. Ein ausdruecklicher Spielraum fuer kleine Sensoruhrabweichungen
    ist auf 100 ms begrenzt; Aufnahmealter und monotones Empfangsalter bleiben eigene Pruefungen."""
    if not isinstance(max_zukunft, (int, float)) or not 0.0 <= max_zukunft <= .1:
        return 'Uhrspielraum ungueltig (maximal 0.1 s)'
    if aufnahme is None:
        return 'keine gueltige Aufnahmezeit'
    alter = jetzt - aufnahme
    if alter < -max_zukunft:
        return f'Aufnahmezeit {-alter:.2f} s in der Zukunft (andere Uhr?)'
    if alter > max_alter:
        return f'Aufnahme {alter:.1f} s alt'
    return None


def aufnahme_pruefen(msg, jetzt, vorher=None, max_alter=AUFNAHME_MAX, *, max_zukunft=0.0):
    """Aufnahmezeit eines Scans beim Empfang pruefen (header.stamp, unabhaengig von der Empfangszeit).

    jetzt: ROS-Zeit des Empfaengers in s (Node-Uhr, dieselbe Uhrdomaene wie header.stamp; ohne use_sim_time
    ist das die Systemzeit, mit der die LiDAR-Treiber und der Simulator stempeln). vorher: neueste AKZEPTIERTE Aufnahmezeit dieses Kanals oder None
    (die Verbraucher ruecken sie nur mit akzeptierten, groesseren Stempeln vor - ein zurueckgesetzter Stempel
    bleibt so ungueltig, bis er die Marke ueberholt).
    Rueckgabe: (aufnahme s oder None, Grund oder None). Grund 'doppelt' = derselbe Scan nochmal (nichts Neues).
    """
    try:
        sec, ns = msg.header.stamp.sec, msg.header.stamp.nanosec
    except AttributeError:
        return None, 'keine Aufnahmezeit (header.stamp)'
    if not (isinstance(sec, Integral) and isinstance(ns, Integral) and not isinstance(sec, bool)
            and not isinstance(ns, bool) and sec >= 0 and 0 <= ns < 1_000_000_000 and sec + ns > 0):
        return None, 'Aufnahmezeit ungueltig (null/kaputt)'
    aufnahme = int(sec) + int(ns) * 1e-9
    if vorher is not None and aufnahme == vorher:
        return aufnahme, 'doppelt'
    grund = aufnahme_alter(aufnahme, jetzt, max_alter, max_zukunft=max_zukunft)
    if grund is None and vorher is not None and aufnahme < vorher:
        grund = f'Aufnahmezeit laeuft {vorher - aufnahme:.2f} s zurueck'
    return aufnahme, grund


def pflichtkanaele(scans, topics, jetzt, max_alter=1.0):
    """Liegen ALLE Pflichtkanaele (scan_topics) frisch vor? Ein frischer zweiter Kanal ersetzt keinen fehlenden.

    scans: {topic: (empfangszeit, ...)}, Empfangszeit und jetzt monoton (time.monotonic).
    Rueckgabe: (Eintraege der Pflichtkanaele in deren Reihenfolge, Grund oder None). Bei einem Grund ist die
    Liste leer: dann gilt der LiDAR als unbekannt (Halt). Kanaele ausserhalb von topics zaehlen nicht.
    """
    topics = list(topics or [])
    if not topics:
        return [], 'keine LiDAR-Kanaele eingestellt (scan_topics leer)'
    gruende = []
    for t in topics:
        if t not in scans:
            gruende.append(f'{t}: noch nie ein Scan')
            continue
        alter = jetzt - scans[t][0]
        if not 0.0 <= alter < max_alter:
            gruende.append(f'{t}: letzter Scan vor {alter:.1f} s')
    if gruende:
        return [], '; '.join(gruende)
    return [scans[t] for t in topics], None


def winkel_und_abstand(msg, front_deg=0.0):
    """Gueltige Messpunkte eines LaserScan.

    Rueckgabe: (winkel, abstand) als numpy-Arrays. Winkel in Bogenmass relativ
    zu "vorne" (0 = vorne, positiv = links), Abstand in Metern.
    """
    r = np.asarray(msg.ranges, dtype=np.float32)
    a = msg.angle_min + np.arange(len(r), dtype=np.float32) * msg.angle_increment - math.radians(front_deg)
    gut = np.isfinite(r) & (r > msg.range_min) & (r < msg.range_max)
    a = np.arctan2(np.sin(a[gut]), np.cos(a[gut]))  # auf -pi..pi bringen
    return a, r[gut]


def naechster_vorne(msg, front_deg=0.0, halb_deg=30.0, min_abstand=0.08, rueckwaerts=False):
    """Kleinster Abstand im Sektor vorne (+- halb_deg). inf = nichts gesehen.

    min_abstand: noch naeher = Teile des eigenen Roboters, ignorieren.
    rueckwaerts: True = Sektor hinten pruefen (Roboter faehrt rueckwaerts).
    """
    a, r = winkel_und_abstand(msg, front_deg + (180.0 if rueckwaerts else 0.0))
    im_sektor = (np.abs(a) <= math.radians(halb_deg)) & (r > min_abstand)
    return float(r[im_sektor].min()) if np.any(im_sektor) else float('inf')


def winkelspanne_ok(anzahl, angle_increment):
    """Ueberdecken die Strahlen hoechstens eine Umdrehung (plus einen Schritt Ueberlapp)? Mehrfach umlaufende
    Winkelangaben (kaputte Metadaten, z. B. 360 Strahlen zu je 181 Grad) wuerden die Messwerte ueber alle
    Richtungen verteilen und eine Abdeckung vortaeuschen."""
    inc = abs(float(angle_increment))
    return (anzahl - 1) * inc <= 2 * math.pi + inc + 1e-9


def ungueltige_winkel(msg, front_deg=0.0):
    """Richtungen (rad, relativ zu vorne, -pi..pi) OHNE gueltige Messung, rundherum in Schritten von hoechstens
    einem Strahlabstand (und 1 Grad). Gemessen ist eine Richtung nur, wenn ein Strahl hoechstens einen halben
    Strahlabstand (und STRAHL_RADIUS_MAX) entfernt liegt und alle so nahen Strahlen gueltig sind. Unbekannt sind also Strahlen ohne Messung (0 unter
    range_min, NaN, inf, ausserhalb range_max) und Richtungen, die der Scan gar nicht enthaelt (Teilscan). Dort
    weiss man nichts: in der ganzen Richtung kann ein Hindernis stehen. Auch +inf ist kein bestaetigtes "frei bis
    zur Reichweite" (die Treiberkodierung dafuer ist nicht belegt)."""
    r = np.asarray(msg.ranges, dtype=np.float64)
    inc = abs(float(msg.angle_increment))
    gut = np.isfinite(r) & (r > msg.range_min) & (r < msg.range_max)
    a = msg.angle_min + np.arange(len(r)) * msg.angle_increment - math.radians(front_deg)
    a = np.arctan2(np.sin(a), np.cos(a))
    ordnung = np.argsort(a)
    a, gut = a[ordnung], gut[ordnung]
    # Raster hoechstens 1 Grad, aber nie feiner als 0,1 Grad: ein kaputter winziger angle_increment (z. B. 1e-6)
    # erzeugt sonst Millionen Pruefrichtungen. Solche Scans decken dann nur winzige Bereiche ab -> unbekannt/Halt.
    n = int(math.ceil(2 * math.pi / max(min(inc, math.radians(1.0)), math.radians(0.1))))
    w = -math.pi + (np.arange(n) + 0.5) * 2 * math.pi / n           # Pruefrichtungen rundherum
    if not len(a) or not winkelspanne_ok(len(a), inc):
        return w                                                    # nichts verlaesslich gemessen
    j = np.searchsorted(a, w)
    kandidaten = np.stack([(j - 1) % len(a), j % len(a)], axis=1)    # Nachbarstrahlen (auch ueber +-pi hinweg)
    abstand = np.abs(np.arctan2(np.sin(w[:, None] - a[kandidaten]), np.cos(w[:, None] - a[kandidaten])))
    nah = abstand <= min(inc / 2, STRAHL_RADIUS_MAX) + 1e-9
    # gemessen: mindestens ein Strahl nah genug, und JEDER nahe Strahl gueltig (genau dazwischen: beide)
    gemessen = nah.any(axis=1) & (gut[kandidaten] | ~nah).all(axis=1)
    return w[~gemessen]


def freie_reichweite(msg, front_deg=0.0, n=1440):
    """Wie weit ist jede Richtung frei GEMESSEN? Array mit n Werten (m) fuer die Richtungen
    -pi + (k + 0,5) * 2pi/n (relativ zu vorne). Gueltiger Strahl: bis zu seinem Treffer (dahinter verdeckt, also
    unbekannt). Kein Strahl in der Naehe (Regeln wie ungueltige_winkel) oder ein ungueltiger: 0. Liegen zwei
    Strahlen gleich nah, gilt der kuerzere. Fuer Bereiche, die ganz gemessen sein muessen (Zebrastreifen #156)."""
    w = -math.pi + (np.arange(n) + 0.5) * 2 * math.pi / n
    frei = np.zeros(n)
    try:
        r = np.asarray(msg.ranges, dtype=np.float64)
        inc = abs(float(msg.angle_increment))
    except (AttributeError, TypeError, ValueError):
        return frei
    if not len(r) or not inc or not winkelspanne_ok(len(r), inc):
        return frei
    gut = np.isfinite(r) & (r > msg.range_min) & (r < msg.range_max)
    r = np.where(gut, r, 0.0)
    a = msg.angle_min + np.arange(len(r)) * msg.angle_increment - math.radians(front_deg)
    a = np.arctan2(np.sin(a), np.cos(a))
    ordnung = np.argsort(a)
    a, r = a[ordnung], r[ordnung]
    j = np.searchsorted(a, w)
    kandidaten = np.stack([(j - 1) % len(a), j % len(a)], axis=1)
    abstand = np.abs(np.arctan2(np.sin(w[:, None] - a[kandidaten]), np.cos(w[:, None] - a[kandidaten])))
    nah = abstand <= min(inc / 2, STRAHL_RADIUS_MAX) + 1e-9
    werte = np.where(nah, r[kandidaten], np.inf).min(axis=1)
    frei[nah.any(axis=1)] = werte[nah.any(axis=1)]
    return frei


def sektor_abdeckung(msg, front_deg=0.0, halb_deg=30.0, rueckwaerts=False):
    """Ist der Sektor vorne (bzw. hinten) +-halb_deg vollstaendig gemessen? None = ja, sonst Grund (Text).
    Gueltige Punkte daneben ersetzen keine Messung IM Sektor: schon eine Richtung ohne Messung darin = unbekannt,
    auch wenn der Scan diese Richtung gar nicht enthaelt."""
    a = ungueltige_winkel(msg, front_deg + (180.0 if rueckwaerts else 0.0))
    im = np.abs(a) <= math.radians(halb_deg)
    if not np.any(im):
        return None
    a = a[im]
    return f'{math.degrees(a.min()):+.0f} bis {math.degrees(a.max()):+.0f} Grad teils ohne Messung'


def luecke_im_bereich(winkel, im_bereich, reichweite, schritt=0.04):
    """Wo beginnt der erste unbekannte Teil eines Bereichs? winkel: ungueltige_winkel(). Jeder Strahl ohne Messung
    wird vom LiDAR bis 'reichweite' (m) abgetastet; im_bereich(xy) -> (Maske, Abstand je Punkt im Bereichsmass).
    Rueckgabe: kleinster Abstand eines unbekannten Punkts im Bereich, None = Bereich voll gemessen."""
    winkel = np.asarray(winkel, dtype=np.float64)
    if not len(winkel):
        return None
    s = np.arange(schritt, reichweite + schritt / 2, schritt)
    xy = np.stack([np.cos(winkel)[:, None] * s, np.sin(winkel)[:, None] * s], axis=-1).reshape(-1, 2)
    drin, abstand = im_bereich(xy)
    return float(np.min(abstand[drin])) if np.any(drin) else None


def punkte(msg, front_deg=0.0, max_punkte=360):
    """Punkte fuer die Anzeige: Liste [x, y] in Metern, x = vorne, y = links."""
    a, r = winkel_und_abstand(msg, front_deg)
    if len(r) > max_punkte:
        schritt = int(math.ceil(len(r) / max_punkte))
        a, r = a[::schritt], r[::schritt]
    x, y = r * np.cos(a), r * np.sin(a)
    return [[round(float(px), 3), round(float(py), 3)] for px, py in zip(x, y)]


def naechstes_objekt(msg, front_deg=0.0, halb_deg=30.0, min_abstand=0.08):
    """Naechster Gegenstand vorne: dict vor, seite (m, Mitte), breite (m) oder None.
    Breite = Punkte, die hoechstens 4 cm hinter dem naechsten Punkt liegen."""
    a, r = winkel_und_abstand(msg, front_deg)
    im_sektor = (np.abs(a) <= math.radians(halb_deg)) & (r > min_abstand)
    if not np.any(im_sektor):
        return None
    a, r = a[im_sektor], r[im_sektor]
    i = int(np.argmin(r))
    x, y = r * np.cos(a), r * np.sin(a)
    teil = np.hypot(x - x[i], y - y[i]) < 0.04
    return {'vor': float(x[i]), 'seite': float(np.mean(y[teil])),
            'breite': float(np.ptp(y[teil]) + 0.01), 'abstand': float(r[i])}


def punkte_xy(msg, front_deg=0.0, min_abstand=0.08):
    """Alle gueltigen Punkte als numpy-Array [[x, y], ...] (x vorne, y links), ohne eigene Roboterteile."""
    a, r = winkel_und_abstand(msg, front_deg)
    ok = r > min_abstand
    return np.stack([r[ok] * np.cos(a[ok]), r[ok] * np.sin(a[ok])], axis=1)


# ---------------- Sensor -> Roboter (L4 #63) ----------------
# Roboterbezug: base_link, x vorne, y links, Meter, Winkel gegen den Uhrzeigersinn positiv.
# Genau EINE Drehkonvention: die Drehung eines LiDARs kommt allein aus scan_front_deg (Grad, unter welchem
# Sensorwinkel er die Roboter-Vorderrichtung sieht; Panel -> LiDAR-Radar). Die Einbaupose ergaenzt nur die
# Verschiebung (x, y) des Sensorursprungs:  p_basis = R(-scan_front_deg) * p_sensor + (x, y).
# KI/Notbremse nutzen bestaetigte Posen ueber lidar_fusion (#64/#169); Vermessung siehe #66.
BASIS_FRAME = 'base_link'
EINBAU_QUELLEN = ('gemessen', 'werksmodell', 'unbekannt')


@dataclass(frozen=True)
class Einbau:
    """Wo ein LiDAR am Roboter sitzt. frame: erwarteter header.frame_id seiner Scans; x, y: Sensorursprung im
    Roboterbezug (m); quelle: 'gemessen' (am Geraet bestaetigt), 'werksmodell' (z. B. URDF, nur Rechenbezug) oder
    'unbekannt'. frame == base_link heisst: der Treiber liefert schon im Roboterbezug (dann x = y = 0)."""
    frame: str
    x: float
    y: float
    quelle: str


def einbau_aus_parametern(topics, frames, xy, quellen):
    """Einbau je Kanal aus den Parametern scan_frames, scan_einbau_xy ([x0, y0, x1, y1 ...]) und scan_einbau_quelle.
    Rueckgabe: ({topic: Einbau}, None) oder (None, Grund), wenn die Listen nicht zusammenpassen."""
    topics, frames, xy, quellen = list(topics), list(frames), list(xy), list(quellen)
    n = len(topics)
    if not n or len(frames) != n or len(xy) != 2 * n or len(quellen) != n:
        return None, f'Einbauangaben passen nicht zu {n} Kanaelen (frames {len(frames)}, xy {len(xy)}, ' \
                     f'quellen {len(quellen)})'
    einbau = {}
    for k, t in enumerate(topics):
        if not isinstance(frames[k], str) or not frames[k].strip():
            return None, f'{t}: Frame fehlt'
        if quellen[k] not in EINBAU_QUELLEN:
            return None, f'{t}: Quelle {quellen[k]!r} unbekannt (erlaubt: {", ".join(EINBAU_QUELLEN)})'
        try:
            x, y = float(xy[2 * k]), float(xy[2 * k + 1])
        except (TypeError, ValueError):
            return None, f'{t}: Einbau x/y keine Zahlen'
        einbau[t] = Einbau(frames[k].strip(), x, y, quellen[k])
    return einbau, None


def einbau_pruefen(einbau, frame_id, nur_gemessen=True, front_deg=0.0):
    """Darf dieser Scan (header.frame_id) mit diesem Einbau in den Roboterbezug? None = ja, sonst Grund.
    nur_gemessen: nur am Geraet bestaetigte Posen (Werksmodell ist keine Vermessung des Roboters)."""
    if einbau is None:
        return 'Einbaupose fehlt'
    if not isinstance(frame_id, str) or not frame_id:
        return 'Scan ohne Frame'
    if frame_id != einbau.frame:
        return f'Frame passt nicht (Scan {frame_id!r}, eingestellt {einbau.frame!r})'
    if einbau.quelle == 'unbekannt' or not (math.isfinite(einbau.x) and math.isfinite(einbau.y)):
        return 'Einbaupose unbekannt'
    if einbau.frame == BASIS_FRAME and (einbau.x, einbau.y) != (0.0, 0.0):
        return f'widerspruechlich: Scan schon in {BASIS_FRAME}, aber Verschiebung eingestellt'
    if einbau.frame == BASIS_FRAME and front_deg != 0.0:
        return f'widerspruechlich: Scan schon in {BASIS_FRAME}, aber scan_front_deg {front_deg} eingestellt'
    if nur_gemessen and einbau.quelle != 'gemessen':
        return f'Einbaupose nur {einbau.quelle}, nicht am Geraet vermessen'
    return None


def nach_basis(xy_vorne, einbau):
    """Punkte, die schon nach vorne gedreht sind (punkte_xy mit scan_front_deg), in den Roboterbezug: nur noch
    um den Sensorursprung verschieben. Schon im Roboterbezug gelieferte Scans (base_link) bleiben unveraendert."""
    xy = np.asarray(xy_vorne, dtype=np.float64).reshape(-1, 2)
    if einbau.frame == BASIS_FRAME:
        return xy.copy()
    return xy + np.array([einbau.x, einbau.y])


def sensor_zu_basis(xy_sensor, front_deg, einbau):
    """Punkte im eigenen Sensorbezug (Winkel wie im LaserScan) in den Roboterbezug:
    p_basis = R(-front_deg) * p_sensor + (x, y). Drehung und Verschiebung genau einmal. Scans schon in base_link
    duerfen weder gedreht noch verschoben werden (front_deg muss dann 0 sein)."""
    if einbau.frame == BASIS_FRAME and front_deg != 0.0:
        raise ValueError(f'Scan schon in {BASIS_FRAME}: scan_front_deg muss 0 sein, nicht {front_deg}')
    w = -math.radians(front_deg)
    c, s = math.cos(w), math.sin(w)
    xy = np.asarray(xy_sensor, dtype=np.float64).reshape(-1, 2) @ np.array([[c, s], [-s, c]])
    return nach_basis(xy, einbau)


def punkte_basis(msg, front_deg, einbau, min_abstand=0.08, nur_gemessen=True):
    """Gueltige Punkte eines Scans im Roboterbezug: (xy oder None, Grund oder None).
    Ohne passenden Frame oder bestaetigte Pose gibt es KEINE Punkte (unbekannt), keine Annahme 'Sensor = Mitte'."""
    grund = einbau_pruefen(einbau, getattr(getattr(msg, 'header', None), 'frame_id', None), nur_gemessen, front_deg)
    if grund:
        return None, grund
    return nach_basis(punkte_xy(msg, front_deg, min_abstand), einbau), None


def abstand_zum_weg(xy, weg=None, laenge=0.8):
    """Fuer jeden Punkt (N,2): seitlicher Abstand zum Weg und Strecke entlang des Wegs bis dorthin.
    weg: [(x, y), ...] Punkte der Linie vor dem Roboter (Roboter-System) oder None = geradeaus.
    Rueckgabe: (quer, entlang) als numpy-Arrays (m)."""
    pfad = [(0.0, 0.0)] + [tuple(p) for p in (weg or []) if p[0] > 0.02]
    if len(pfad) < 2:
        pfad.append((laenge, 0.0))
    pfad = np.array(pfad, dtype=np.float64)
    # Weg bis 'laenge' gerade verlaengern (Kamera sieht nicht so weit)
    seg = np.diff(pfad, axis=0)
    seglen = np.hypot(seg[:, 0], seg[:, 1])
    gesamt = seglen.sum()
    if gesamt < laenge and seglen[-1] > 1e-6:
        richtung = seg[-1] / seglen[-1]
        pfad = np.vstack([pfad, pfad[-1] + richtung * (laenge - gesamt)])
        seg = np.diff(pfad, axis=0)
        seglen = np.hypot(seg[:, 0], seg[:, 1])
    seglen = np.maximum(seglen, 1e-6)
    kum = np.concatenate([[0.0], np.cumsum(seglen)])
    p = np.asarray(xy, dtype=np.float64).reshape(-1, 2)[:, None, :]
    a = pfad[None, :-1, :]
    t = np.clip(((p - a) * seg[None]).sum(-1) / seglen[None] ** 2, 0.0, 1.0)
    naechst = a + t[..., None] * seg[None]
    dist = np.hypot(*(p - naechst).transpose(2, 0, 1))
    j = np.argmin(dist, axis=1)
    i = np.arange(p.shape[0])
    return dist[i, j], kum[j] + t[i, j] * seglen[j]


def fahrschlauch(xy, weg=None, halbe_breite=0.15, laenge=0.8, nah=0.2, nah_halb_deg=30.0):
    """Naechster Gegenstand im FAHRSCHLAUCH: dem Streifen, den der Roboter ueberfaehrt, wenn er dem
    Weg folgt (z. B. der Linie in eine Kurve hinein). Haeuser neben der Kurve stoeren so nicht.
    Naeher als 'nah' zaehlt zusaetzlich nur der Kegel +-nah_halb_deg nach vorne (wie frueher): seitlich
    direkt neben dem Roboter sieht der LiDAR evtl. eigene Teile (Raeder, Arm).

    xy: Punkte (punkte_xy), weg: [(x, y), ...] Punkte der Linie vor dem Roboter (Roboter-System)
    oder None = geradeaus. Rueckgabe: None oder dict abstand (m entlang des Wegs), vor, seite (m, Mitte
    im Roboter-System), breite (m), quer (m, seitlicher Abstand zur Wegmitte)."""
    if len(xy) == 0:
        return None
    xy = np.asarray(xy, dtype=np.float64).reshape(-1, 2)
    # Der Weg beginnt am Roboter: ein Punkt im Schlauch ist hoechstens (Strecke entlang) + (Abstand zum Weg) entfernt.
    # Weiter entfernte Punkte koennen nie drin sein -> vorher weglassen (Ergebnis gleich, viel weniger Rechnung).
    xy = xy[np.hypot(xy[:, 0], xy[:, 1]) < max(laenge, nah) + halbe_breite + 0.01]
    if len(xy) == 0:
        return None
    drin, entlang, quer = _im_schlauch(xy, weg, halbe_breite, laenge, nah, nah_halb_deg)
    if not np.any(drin):
        return None
    xy, entlang, quer = xy[drin], entlang[drin], quer[drin]
    k = int(np.argmin(entlang))
    teil = np.hypot(xy[:, 0] - xy[k, 0], xy[:, 1] - xy[k, 1]) < 0.04
    return {'abstand': float(entlang[k]), 'vor': float(xy[k, 0]), 'seite': float(np.mean(xy[teil, 1])),
            'breite': float(np.ptp(xy[teil, 1]) + 0.01), 'quer': float(quer[k])}


def _im_schlauch(xy, weg, halbe_breite, laenge, nah, nah_halb_deg):
    """(Maske: Punkt liegt im Fahrschlauch, Strecke entlang des Wegs, seitlicher Abstand zum Weg) je Punkt."""
    quer, entlang = abstand_zum_weg(xy, weg, laenge)
    im_kegel = np.abs(np.arctan2(xy[:, 1], xy[:, 0])) <= math.radians(nah_halb_deg)
    drin = (quer < halbe_breite) & (entlang > 0.0) & (entlang <= laenge) & ((entlang > nah) | im_kegel)
    return drin, entlang, quer


def fahrschlauch_luecke(winkel, weg=None, halbe_breite=0.15, laenge=0.8, nah=0.2, nah_halb_deg=30.0):
    """Erster NICHT gemessener Teil des Fahrschlauchs (gleiche Form wie fahrschlauch): Strecke entlang des Wegs (m)
    bis dorthin, None = ganz gemessen. winkel: ungueltige_winkel(). Gueltige Punkte neben dem Weg aendern daran
    nichts - sie sagen nichts ueber den Weg."""
    def im_bereich(xy):
        drin, entlang = np.zeros(len(xy), dtype=bool), np.zeros(len(xy))
        vorn = xy[:, 0] > -halbe_breite         # der Weg beginnt am Roboter und fuehrt nach vorne: spart Rechenzeit
        drin[vorn], entlang[vorn], _ = _im_schlauch(xy[vorn], weg, halbe_breite, laenge, nah, nah_halb_deg)
        return drin, entlang
    return luecke_im_bereich(winkel, im_bereich, max(laenge, nah) + halbe_breite)


def hinten_luecke(winkel, halbe_breite=0.15, ab=0.05):
    """Erster nicht gemessener Punkt im Streifen hinter dem Roboter (x < -ab, |y| < halbe_breite): Abstand nach
    hinten (m) oder None = ganz gemessen. winkel: ungueltige_winkel(). Ein Strahl vom LiDAR nach hinten tritt bei
    x = -ab in den Streifen ein, wenn er dort seitlich noch innerhalb liegt - dann ist ab schon unbekannt."""
    c, s = np.cos(winkel), np.sin(winkel)
    hinein = (c < 0) & (np.abs(s) * ab < halbe_breite * np.abs(c))
    return float(ab) if np.any(hinein) else None
