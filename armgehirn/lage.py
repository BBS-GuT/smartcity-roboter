#!/usr/bin/env python3
# Arm-Gehirn: Lageschaetzung der Kamera kalibrieren (systematischer Versatz Kamera/Tiefe). Ohne ROS.
#
# Die Tiefenkamera misst, wo der Gegenstand liegt. Ist sie etwas anders eingebaut als angenommen (Hoehe, Neigung,
# Massstab der Tiefe), liegt die Messung systematisch daneben - vorne anders als hinten. Das gleicht auch das
# Greif-Lernen aus (es lernt eine lageabhaengige Korrektur), aber MIT bekannter Lage geht es schneller und man sieht,
# WO der Fehler entsteht (Kamera oder Arm):
#   Gegenstand auf Markierungen mit bekannter Lage legen (Papierschablone, MARKIERUNGEN), messen lassen.
#   Ausgleichsrechnung: wahre Lage = M * (1, gemessen vorne, gemessen seitlich)  (6 Zahlen, "affin")
# Gespeichert in config/lokal/armgehirn.json unter 'lage_kalibrierung'. Ab mind. 4 Markierungen.
import numpy as np

# Vorschlag fuer eine Schablone (Mitte des Gegenstands, m vor der Robotermitte / links): am Roboter anpassen
# (config/lokal/arm.yaml -> armgehirn: markierungen: [[x, y], ...])
MARKIERUNGEN = [[0.15, 0.0], [0.18, 0.0], [0.15, 0.05], [0.15, -0.05], [0.18, 0.05], [0.18, -0.05]]


def rechnen(paare, regulierung=1e-4):
    """paare: [((vor_gemessen, seite_gemessen), (vor_wahr, seite_wahr)), ...] (Mitten). -> {'M', 'rest_cm', 'n'}
    oder None (zu wenige)."""
    if len(paare) < 4:
        return None
    X = np.array([[1.0, g[0], g[1]] for g, _ in paare])
    Y = np.array([w for _, w in paare], dtype=float)
    # leicht zur "keine Aenderung" hingezogen (wenige Punkte duerfen nichts Wildes ergeben)
    ziel = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    L = np.diag([regulierung, regulierung, regulierung]) * len(X)
    M = np.linalg.solve(X.T @ X + L, X.T @ Y + L @ ziel)
    rest = Y - X @ M
    return {'M': np.round(M, 5).tolist(), 'rest_cm': round(float(np.sqrt((rest ** 2).sum(axis=1).mean()) * 100), 2),
            'vorher_cm': round(float(np.sqrt(((Y - X[:, 1:]) ** 2).sum(axis=1).mean()) * 100), 2), 'n': len(X)}


def anwenden(objekt, kalibrierung):
    """Gemessenen Gegenstand korrigieren (Mitte verschieben, Groesse bleibt). Ohne Kalibrierung unveraendert."""
    if not kalibrierung or objekt is None:
        return objekt
    M = np.array(kalibrierung['M'])
    mx, my = objekt['vor'] + objekt['breite'] / 2, objekt['seite']
    x, y = np.array([1.0, mx, my]) @ M
    return dict(objekt, vor=float(x) - objekt['breite'] / 2, seite=float(y))
