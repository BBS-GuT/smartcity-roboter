# Archivierter Offline-Analyseentwurf zu #59, keine Produktintegration.
"""Isolierter Analyseentwurf, keine Produktintegration und kein ROS/Hardwarezugriff.

Prueft Datenverwertbarkeit in explizit angegebenen kritischen Strahlen und
transformiert Messpunkte genau einmal aus dem erwarteten Sensorframe.
Die Festlegung der kritischen Abdeckung und der Grenzwerte ist NICHT implementiert.
Ein verwertbarer Scan bedeutet noch keine freie Fahrhuelle oder Motorfreigabe.
"""
from dataclasses import dataclass
import math
from numbers import Integral
import numpy as np


@dataclass(frozen=True)
class Einbau:
    frame: str
    x: float
    y: float
    yaw: float  # Radiant; positiver Winkel dreht nach links.
    bestaetigt: bool


@dataclass(frozen=True)
class Zeitgrenzen:
    empfang_max: float
    aufnahme_max: float
    zukunft_max: float


@dataclass
class Scanbefund:
    verwertbar: bool
    gruende: tuple
    basis_xy: np.ndarray
    gueltig: np.ndarray
    kritisch_gesamt: int
    kritisch_gueltig: int


def transformiere(sensor_xy, einbau):
    """p_B = R(yaw_BS) p_S + t_BS. Keine zweite front_deg-Korrektur."""
    punkte = np.asarray(sensor_xy, dtype=float).reshape(-1, 2)
    c, s = math.cos(einbau.yaw), math.sin(einbau.yaw)
    return punkte @ np.array([[c, s], [-s, c]]) + [einbau.x, einbau.y]


def pruefe_scan(msg, einbau, kritische_strahlen, *, empfang_mono, jetzt_mono,
                aufnahme_jetzt, zeitbasis_bestaetigt, grenzen, letzter_stempel=None):
    """Konservativer Prototyp: jeder explizit kritische Strahl muss endlich/gueltig sein.

    Diese strenge Demonstrationsregel ist KEINE abgenommene Abdeckungsquote.
    Ausserhalb des kritischen Bereichs bleiben Luecken in der Maske sichtbar.
    NaN, +/-Inf, 0 und Bereichsverletzungen werden nicht als Freiraum gewertet.
    Ein Treibervertrag fuer eindeutige 'kein Echo bis Reichweite'-Werte fehlt hier.
    aufnahme_jetzt und header.stamp muessen derselben bestaetigten Zeitbasis angehoeren.
    """
    r = np.asarray(msg.ranges, dtype=float)
    if r.ndim != 1:
        return Scanbefund(False, ('Messarray_ungueltig',), np.empty((0, 2)),
                          np.zeros(r.size, dtype=bool), 0, 0)
    kritisch_roh = tuple(kritische_strahlen)
    index_ok = (bool(kritisch_roh)
                and all(isinstance(k, Integral) and not isinstance(k, (bool, np.bool_))
                        and 0 <= k < len(r) for k in kritisch_roh)
                and len(set(kritisch_roh)) == len(kritisch_roh))
    kritisch = np.asarray(kritisch_roh, dtype=int) if index_ok else np.empty(0, dtype=int)
    gruende = []
    if not einbau.bestaetigt:
        gruende.append('Einbaugeometrie_nicht_bestaetigt')
    if msg.header.frame_id != einbau.frame:
        gruende.append('Sensorframe_falsch')
    if not zeitbasis_bestaetigt:
        gruende.append('Zeitbasis_nicht_bestaetigt')
    zahlen = [msg.range_min, msg.range_max, msg.angle_min, msg.angle_increment,
              empfang_mono, jetzt_mono, aufnahme_jetzt, einbau.x, einbau.y, einbau.yaw,
              grenzen.empfang_max, grenzen.aufnahme_max, grenzen.zukunft_max]
    if (not all(math.isfinite(float(v)) for v in zahlen)
            or msg.range_min < 0 or msg.range_max <= msg.range_min
            or msg.angle_increment == 0
            or min(grenzen.empfang_max, grenzen.aufnahme_max, grenzen.zukunft_max) < 0):
        return Scanbefund(False, tuple(gruende + ['Metadaten_ungueltig']),
                          np.empty((0, 2)), np.zeros(len(r), dtype=bool), len(kritisch_roh), 0)
    empfang_alter = jetzt_mono - empfang_mono
    if empfang_alter < 0 or empfang_alter > grenzen.empfang_max:
        gruende.append('Empfang_ungueltig_oder_alt')
    sec, ns = msg.header.stamp.sec, msg.header.stamp.nanosec
    kanonisch = (isinstance(sec, Integral) and not isinstance(sec, (bool, np.bool_))
                 and isinstance(ns, Integral) and not isinstance(ns, (bool, np.bool_))
                 and sec >= 0 and 0 <= ns < 1_000_000_000)
    stempel = sec + ns * 1e-9 if kanonisch else float('nan')
    if not kanonisch or not math.isfinite(stempel) or stempel <= 0:
        gruende.append('Aufnahmestempel_ungueltig')
    elif aufnahme_jetzt - stempel > grenzen.aufnahme_max:
        gruende.append('Aufnahme_zu_alt')
    elif stempel - aufnahme_jetzt > grenzen.zukunft_max:
        gruende.append('Aufnahme_in_Zukunft')
    if letzter_stempel is not None and stempel <= letzter_stempel:
        gruende.append('Aufnahmestempel_steht_oder_laeuft_zurueck')
    gueltig = np.isfinite(r) & (r > msg.range_min) & (r < msg.range_max)
    abdeckung_ok = index_ok
    anzahl = int(gueltig[kritisch].sum()) if abdeckung_ok else 0
    if not abdeckung_ok:
        gruende.append('Kritische_Abdeckung_nicht_definiert')
    elif anzahl != len(kritisch):
        gruende.append('Kritische_Messung_unbekannt')
    a = msg.angle_min + np.arange(len(r)) * msg.angle_increment
    sensor_xy = np.column_stack((r[gueltig] * np.cos(a[gueltig]),
                                 r[gueltig] * np.sin(a[gueltig])))
    xy = transformiere(sensor_xy, einbau)
    return Scanbefund(not gruende, tuple(gruende), xy, gueltig, len(kritisch_roh), anzahl)


def pruefe_pflichtquellen(befunde, pflichtquellen):
    """Nur Datenverwertbarkeit, weder Hindernisfreiheit noch Motorfreigabe."""
    pflicht = tuple(pflichtquellen)
    if not pflicht:
        return False, ('Pflichtquellen_nicht_definiert',)
    gruende = []
    for name in pflicht:
        if name not in befunde:
            gruende.append(name + ':fehlt')
        elif not befunde[name].verwertbar:
            gruende.extend(name + ':' + grund for grund in befunde[name].gruende)
    return not gruende, tuple(gruende)
