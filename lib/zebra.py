#!/usr/bin/env python3
# Zebrastreifen erkennen (ohne ROS, damit testbar).
#
# Arbeitet in der Draufsicht (Vogelperspektive) der Linienerkennung: Dort ist ein Zebrastreifen
# eine Reihe gleich breiter, paralleler Balken NEBENEINANDER quer ueber die Strasse.
# Eine Bildzeile der Draufsicht, die mindestens 'min_balken' solcher Balken mit aehnlichem Abstand
# schneidet, gehoert zum Zebrastreifen. Die schwarze Fahrlinie ist nur EIN Balken -> stoert nicht.
# UNGETESTET mit echten Zebrastreifen: Breiten/Abstaende ggf. anpassen.
import numpy as np

STANDARD = {
    'min_balken': 4,          # so viele Balken nebeneinander
    'balken_min': 0.010,      # Balkenbreite in Metern
    'balken_max': 0.045,
    'abstand_toleranz': 0.5,  # Abstaende duerfen so viel (Anteil) vom Mittelwert abweichen
    'min_zeilen': 4,          # so viele Zeilen der Draufsicht muessen passen (gegen Zufall)
}


def finde_zebra(vogel, raster, vorne_max, cfg=None):
    """vogel: Schwarz-Weiss-Draufsicht (255 = dunkel), raster: Meter pro Pixel,
    vorne_max: Abstand (m) der obersten Draufsicht-Zeile vom Roboter.
    Rueckgabe: None oder {'abstand': m bis zur nahen Kante, 'balken': Anzahl}."""
    c = dict(STANDARD)
    c.update(cfg or {})
    if vogel is None:
        return None
    # Balkenanfaenge/-enden aller Zeilen auf einmal (schnell); genauer pruefen nur Zeilen mit genug passenden Balken
    d = np.diff(np.pad((vogel > 0).astype(np.int8), ((0, 0), (1, 1))), axis=1)
    ay, ax = np.nonzero(d == 1)
    ey, ex = np.nonzero(d == -1)               # zeilenweise sortiert: zu jedem Anfang gehoert das Ende daneben
    breiten = (ex - ax) * raster
    passt = (breiten >= c['balken_min']) & (breiten <= c['balken_max'])
    zahl = np.bincount(ay[passt], minlength=vogel.shape[0])
    treffer = []
    for py in np.nonzero(zahl >= c['min_balken'])[0]:
        sel = ay == py
        anfang, ende, ok = ax[sel], ex[sel], passt[sel]
        mitten = ((anfang + ende) / 2.0)[ok] * raster
        abst = np.diff(mitten)
        if len(abst) == 0 or abst.mean() <= 0:
            continue
        regelmaessig = np.abs(abst - np.median(abst)) <= c['abstand_toleranz'] * np.median(abst)
        if regelmaessig.sum() + 1 >= c['min_balken']:
            treffer.append((int(py), int(ok.sum())))
    if len(treffer) < c['min_zeilen']:
        return None
    naechste = max(p for p, _ in treffer)          # unterste Zeile = am naechsten am Roboter
    return {'abstand': float(vorne_max - naechste * raster), 'balken': max(n for _, n in treffer)}
