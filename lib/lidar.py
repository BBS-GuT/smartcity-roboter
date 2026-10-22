#!/usr/bin/env python3
# LiDAR-Auswertung (ohne ROS-Abhaengigkeit, damit testbar).
#
# Ein LiDAR misst in einer DUENNEN WAAGRECHTEN SCHEIBE auf seiner eigenen Hoehe
# den Abstand rundherum. Ein Schuh erscheint deshalb nur als kurzer Bogen
# (seine Vorderkante), nicht als Flaeche. Was niedriger oder hoeher als die
# Scheibe ist, sieht er gar nicht.
import math

import numpy as np


def scan_pruefen(msg):
    """Ist der Scan ueberhaupt verwertbar? None = ja, sonst der Grund (Text).

    Unbrauchbar: kaputte Bereichs-/Winkelangaben, keine Messwerte oder kein einziger gueltiger Wert
    (alle 0 unter range_min, NaN, inf, ausserhalb range_max). Ein solcher Scan sagt NICHTS ueber den Weg -
    er darf nie als "frei" gelten (vorher: keine Punkte -> kein Hindernis -> frei). Die Verbraucher
    halten dann wie ohne LiDAR; der naechste verwertbare Scan desselben Kanals gibt wieder frei.
    """
    try:
        meta = [float(msg.range_min), float(msg.range_max), float(msg.angle_min), float(msg.angle_increment)]
        r = np.asarray(msg.ranges, dtype=np.float64)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return 'Scan unlesbar'
    if (not all(math.isfinite(v) for v in meta) or meta[0] < 0 or meta[1] <= meta[0] or meta[3] == 0):
        return 'Bereichs-/Winkelangaben ungueltig'
    if r.ndim != 1 or r.size == 0:
        return 'keine Messwerte'
    if not np.any(np.isfinite(r) & (r > meta[0]) & (r < meta[1])):
        return 'kein gueltiger Messwert (alle 0/NaN/inf/ausserhalb)'
    return None


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
    quer, entlang = abstand_zum_weg(xy, weg, laenge)
    im_kegel = np.abs(np.arctan2(xy[:, 1], xy[:, 0])) <= math.radians(nah_halb_deg)
    drin = (quer < halbe_breite) & (entlang > 0.0) & (entlang <= laenge) & ((entlang > nah) | im_kegel)
    if not np.any(drin):
        return None
    xy, entlang, quer = xy[drin], entlang[drin], quer[drin]
    k = int(np.argmin(entlang))
    teil = np.hypot(xy[:, 0] - xy[k, 0], xy[:, 1] - xy[k, 1]) < 0.04
    return {'abstand': float(entlang[k]), 'vor': float(xy[k, 0]), 'seite': float(np.mean(xy[teil, 1])),
            'breite': float(np.ptp(xy[teil, 1]) + 0.01), 'quer': float(quer[k])}
