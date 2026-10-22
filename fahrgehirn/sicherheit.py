#!/usr/bin/env python3
# Feste Sicherheitsregel des Fahr-Gehirns: Hindernis im Fahrweg -> STOPP und warten, bis frei. Nie wegraeumen.
#
# Diese Regel wird NICHT gelernt und hat Vorrang vor allem anderen (Fahrplan, Lernen, Linie). Das Lernen kann
# keinen dieser Werte aendern (fahrgehirn/lernen.py kennt sie nicht).
#   - Etwas im Fahrschlauch (Streifen entlang der Linie vor dem Roboter) naeher als halt_abstand -> STOPP.
#   - LiDAR oder Tiefenkamera unbekannt (fehlt, zu alt, Luecke im Fahrweg) -> STOPP (wer nichts sieht, faehrt nicht).
#   - Weiter erst, wenn der Weg frei_warten Sekunden LANG ununterbrochen frei war (kein Anfahren bei Flackern).
# Dazu bleibt die LiDAR-Notbremse des Linienfolgers (12 cm, line_follower.py) als zweite Sicherheit aktiv.
#
# Fahrschlauch an Kreuzungen: Das Linien-Gedaechtnis mittelt an einem T beide Arme zu "geradeaus". Ein Haus direkt
# hinter der Kreuzung lag dann scheinbar im Weg, der Abstand flackerte um die Grenze, und er stand fuer immer (Sim).
# Waehrend einer Kreuzung gilt darum der GEPLANTE Weg: bis zur Abzweigung, dann in die gewaehlte Richtung
# (kreuzungs_pfad). Was dort liegt, haelt ihn genauso wie sonst.
import math

import numpy as np

HALT_ABSTAND = 0.30       # m entlang der Linie: naeher -> Stopp (Bremsweg bei 0,25 m/s ca. 5 cm + Reserve)
HALT_ABSTAND_MIN = 0.20   # kleiner darf man ihn nicht einstellen
FREI_WARTEN = 1.0         # s ununterbrochen frei, bevor er wieder anfaehrt
FREI_WARTEN_MIN = 0.5


def kreuzungs_pfad(abzweig, richtung, ast_laenge=0.6):
    """Geplanter Weg ueber eine Kreuzung im Roboter-System: [(0, 0), Abzweigpunkt, Ende des Astes].
    abzweig: (x, y) des Abzweigpunkts (Roboter-System), richtung: gewaehlter Ast (rad, Roboter-System).
    Liegt der Abzweig schon hinter dem Roboter, beginnt der Ast am Roboter."""
    ax, ay = abzweig
    start = (ax, ay) if ax > 0.0 else (0.0, 0.0)
    ende = (start[0] + ast_laenge * math.cos(richtung), start[1] + ast_laenge * math.sin(richtung))
    return [(0.0, 0.0), start, ende] if ax > 0.0 else [(0.0, 0.0), ende]


def entlang_pfad(xy, pfad):
    """Je Punkt (N, 2): seitlicher Abstand zum Streckenzug pfad (beginnt beim Roboter) und Strecke entlang bis dort."""
    pfad = np.asarray(pfad, dtype=np.float64)
    seg = np.diff(pfad, axis=0)
    seglen = np.maximum(np.hypot(seg[:, 0], seg[:, 1]), 1e-6)
    kum = np.concatenate([[0.0], np.cumsum(seglen)])
    p = np.asarray(xy, dtype=np.float64).reshape(-1, 2)[:, None, :]
    a = pfad[None, :-1, :]
    t = np.clip(((p - a) * seg[None]).sum(-1) / seglen[None] ** 2, 0.0, 1.0)
    dist = np.hypot(*(p - (a + t[..., None] * seg[None])).transpose(2, 0, 1))
    j = np.argmin(dist, axis=1)
    i = np.arange(p.shape[0])
    return dist[i, j], kum[j] + t[i, j] * seglen[j]


def im_pfad_schlauch(xy, pfad, halbe_breite, laenge, nah=0.2, nah_halb_deg=30.0):
    """(Maske im Fahrschlauch, Strecke entlang) wie lidar.fahrschlauch, aber fuer einen beliebigen Streckenzug.
    Naeher als 'nah' zaehlt nur der Kegel +-nah_halb_deg nach vorne (seitlich direkt daneben: eigene Teile)."""
    xy = np.asarray(xy, dtype=np.float64).reshape(-1, 2)
    if not len(xy):
        return np.zeros(0, bool), np.zeros(0)
    quer, entlang = entlang_pfad(xy, pfad)
    im_kegel = np.abs(np.arctan2(xy[:, 1], xy[:, 0])) <= math.radians(nah_halb_deg)
    return (quer < halbe_breite) & (entlang > 0.0) & (entlang <= laenge) & ((entlang > nah) | im_kegel), entlang


class HindernisRegel:
    def __init__(self, halt_abstand=HALT_ABSTAND, frei_warten=FREI_WARTEN):
        self.halt_abstand = max(HALT_ABSTAND_MIN, float(halt_abstand))
        self.frei_warten = max(FREI_WARTEN_MIN, float(frei_warten))
        self.blockiert_bis = None    # Zeit der letzten Blockade (None = noch nie)
        self.grund = None            # letzter Haltgrund (fuer die Anzeige waehrend des Wartens)
        self.halte = 0               # so oft hat er schon wegen eines Hindernisses gehalten

    def pruefe(self, jetzt, lidar_abstand, tiefe='aus'):
        """lidar_abstand: naechstes Hindernis im Fahrschlauch (m, inf = frei), None = LiDAR unbekannt, 'aus' = nicht
        geprueft. tiefe: True = Hindernis, False = frei, None = unbekannt, 'aus' = nicht geprueft.
        Rueckgabe: Haltgrund (Text) oder None = darf fahren."""
        grund = None
        if lidar_abstand is None:
            grund = 'LIDAR UNBEKANNT'
        elif lidar_abstand != 'aus' and lidar_abstand < self.halt_abstand:
            grund = f'HINDERNIS {lidar_abstand * 100:.0f} cm (LiDAR)'
        elif tiefe is None:
            grund = 'TIEFENKAMERA UNBEKANNT'
        elif tiefe is True:
            grund = 'HINDERNIS (Tiefenkamera)'
        if grund:
            if self.blockiert_bis is None or jetzt - self.blockiert_bis >= self.frei_warten:
                self.halte += 1      # neuer Halt (nicht dasselbe Hindernis im naechsten Takt)
            self.blockiert_bis, self.grund = jetzt, grund
            return grund + ' -> STOPP, warte'
        if self.blockiert_bis is not None and jetzt - self.blockiert_bis < self.frei_warten:
            return f'{self.grund} weg, warte noch {self.frei_warten - (jetzt - self.blockiert_bis):.1f} s'
        return None
