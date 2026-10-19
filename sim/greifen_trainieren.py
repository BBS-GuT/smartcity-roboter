#!/usr/bin/env python3
# Greifen im Simulator vortrainieren und messen, ob das Lernen etwas bringt (ohne ROS, nur numpy).
#
# Aufruf:  python3 sim/greifen_trainieren.py              (ca. 5-10 Minuten)
#          python3 sim/greifen_trainieren.py --schnell    (kleiner, ca. 1-2 Minuten, zum Ausprobieren)
#          python3 sim/greifen_trainieren.py --nur-pruefen   (vorhandenes models/greifen.json nur pruefen)
#   --png docs/bilder/greifen_lernkurve.png   Lernkurve zusaetzlich als Bild
#
# 1. Vortraining: tausende Greifversuche, alle paar Versuche ein anders gebauter Uebungsroboter
#    (Domain Randomization, sim/greifen_welt.py). Gleiches Lernverfahren wie auf dem Roboter (lib/greifen.py).
#    Ergebnis: models/greifen.json
# 2. Pruefung an NEUEN Zufallsrobotern (andere Zufallszahlen als im Training = "echte" Roboter, die das
#    Vortraining nicht kannte). Gemessen wird die Erfolgsquote
#      a) ohne Lernen (nur Kinematik),  b) mit Vortraining (ohne weiterzulernen),
#      c) nach weiterem Lernen auf genau diesem Roboter (40 Versuche), d) zum Vergleich: c) ohne Vortraining.
import argparse
import json
import os
import sys
import time

for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_v, '1')   # viele kleine Rechnungen: ein Kern ist schneller (und stoert den Rest nicht)
import numpy as np  # noqa: E402

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, '..', 'lib'))
import greifen_welt as GW   # noqa: E402
import greifen              # noqa: E402

SAAT_TRAINING, SAAT_PRUEFUNG = 1000, 777000     # verschiedene Zufallszahlen: Pruefroboter sind neu
# Bauart des Arms (Nennmasse des Planers) -> Name des Modells in models/greifen.json
#   m3pro: echter Roboter (Masse aus config/arm.yaml bzw. Yahbooms URDF) -> 'eigene'
#   sim:   ROS-Simulator (sim/arm_sim.yaml)                             -> 'sim'
MODELLE = {'m3pro': 'eigene', 'sim': 'sim'}


def balken(q, breite=30):
    n = int(round(q * breite))
    return '#' * n + '.' * (breite - n)


def wuerfel_liste(welt, n):
    """n Wuerfel mit ihrer Messung (Messen = Rendern ist der langsame Teil, darum nur einmal)."""
    aus, versuche = [], 0
    while len(aus) < n and versuche < 5 * n:
        versuche += 1
        w = dict(welt.neuer_wuerfel())
        obj = welt.messen()
        if obj is not None:
            aus.append((w, obj))
    return aus


def versuch(welt, politik, erkunden, lernen, wuerfel=None):
    """Ein Greifversuch. wuerfel: (Wuerfel, Messung) oder None = neuen Wuerfel legen und messen.
    Rueckgabe True/False, None = Kamera sieht nichts / nicht erreichbar (zaehlt nicht)."""
    if wuerfel is None:
        welt.neuer_wuerfel()
        obj = welt.messen()
        if obj is None:
            return None
    else:
        welt.wuerfel, obj = dict(wuerfel[0]), wuerfel[1]
    ok, plan, _ = welt.greifen(obj, politik, erkunden)
    if ok is None:
        return None
    if lernen and politik is not None and plan.get('lernen'):
        politik.ergebnis(plan['lernen']['obj'], plan['lernen']['a'], ok)
    return bool(ok)


def beispiele(rng, familie, n_roboter, je_roboter, ausgabe=print):
    """Uebungsdaten: fuer jeden Wuerfel die Merkmale und die IDEALE Korrektur (im Simulator bekannt)."""
    daten, t0 = [], time.time()
    for i in range(n_roboter):
        if i and i % 50 == 0:
            ausgabe(f'    {i} von {n_roboter} Uebungsrobotern ({time.time() - t0:.0f} s)')
        welt = GW.Uebungswelt(GW.zufalls_roboter(rng, familie), rng)
        zeilen, versuche = [], 0
        while len(zeilen) < je_roboter and versuche < 5 * je_roboter:   # Kamera sieht nie etwas? -> naechster
            versuche += 1
            welt.neuer_wuerfel()
            obj = welt.messen()
            if obj is None:
                continue
            a, obj = welt.ideale_korrektur(obj)
            if a is not None:
                zeilen.append((greifen.merkmale(obj), a))
        if zeilen:
            daten.append(zeilen)
    return daten


def modell_rechnen(daten):
    """Ausgleichsrechnung (lineare Regression) ueber alle Uebungsroboter:
      W        Korrektur = W * Merkmale, die im Mittel ueber ALLE Roboter am besten passt
      streuung wie verschieden die Roboter sind (Streuung ihrer eigenen Grundkorrektur um W) =
               so breit muss er auf einem neuen Roboter anfangs suchen."""
    if not daten:
        return None
    P = np.array([phi for zeilen in daten for phi, _ in zeilen])
    A = np.array([a for zeilen in daten for _, a in zeilen])
    L = np.diag([1e-6, 2e-3, 2e-3, 2e-3]) * len(P)            # Schraegen nur, wenn die Daten es hergeben
    W = np.linalg.solve(P.T @ P + L, P.T @ A).T
    eigen = np.array([np.mean([a - W @ phi for phi, a in zeilen], axis=0) for zeilen in daten])
    streuung = np.clip(eigen.std(axis=0) if len(daten) > 1 else greifen.STREUUNG_START, 0.004, 0.02)
    return {'W': np.round(W, 5).tolist(), 'streuung': np.round(streuung, 5).tolist()}


def vortrainieren(n_roboter, je_roboter, familie, ausgabe=print):
    """Vortraining im Simulator: an vielen zufaellig gebauten Uebungsrobotern messen, welche Korrektur ideal
    gewesen waere (das weiss nur der Simulator), und daraus die Ausgleichsrechnung. Lernkurve: wie gut greift
    ein NEUER Roboter mit dem Modell aus den ersten n Uebungsrobotern (ohne auf ihm selbst zu lernen)?"""
    rng = np.random.default_rng(SAAT_TRAINING + (0 if familie == 'm3pro' else 1))
    t0 = time.time()
    daten = beispiele(rng, familie, n_roboter, je_roboter)
    ausgabe(f'  {n_roboter} Uebungsroboter x {je_roboter} Wuerfel gemessen ({time.time() - t0:.0f} s)')
    pruef_rng = np.random.default_rng(SAAT_TRAINING + 500 + (0 if familie == 'm3pro' else 1))
    pruef_welten = []
    for k in range(8):
        welt = GW.Uebungswelt(GW.zufalls_roboter(pruef_rng, familie), np.random.default_rng(4242 + k))
        pruef_welten.append((welt, wuerfel_liste(welt, 15)))
    kurve = []
    for n in [k for k in (0, 5, 10, 25, 50, 100, 200, 400, 800) if k <= n_roboter]:
        modell = modell_rechnen(daten[:n])
        werte = []
        for (welt, liste) in pruef_welten:
            pol = greifen.Politik('x', None, None, modell=modell) if modell else None
            werte += [e for e in (versuch(welt, pol, False, False, w) for w in liste) if e is not None]
        q = float(np.mean(werte))
        kurve.append((n * je_roboter, q))
        ausgabe(f'  nach {n:4d} Uebungsrobotern ({n * je_roboter:5d} Wuerfeln): neue Roboter greifen {q * 100:5.1f} % '
                f'|{balken(q)}|')
    modell = modell_rechnen(daten)
    W = np.array(modell['W'])
    ausgabe(f'  Grundkorrektur {np.round(W[:, 0] * 100, 1)} cm (vorne/links/hoch), '
            f'Roboter streuen {np.round(np.array(modell["streuung"]) * 100, 1)} cm ({time.time() - t0:.0f} s)')
    return modell, kurve


def roboter_pruefen(rob, saat, modell, n_test=20, n_lernen=40):
    """Ein neuer Roboter. Gleiche Testwuerfel fuer alle Varianten (fair). Rueckgabe: Quoten und Lernkurve."""
    welt = GW.Uebungswelt(rob, np.random.default_rng(saat))
    test, lern = wuerfel_liste(welt, n_test), wuerfel_liste(welt, n_lernen)
    if len(test) < n_test // 2 or len(lern) < n_lernen // 2:
        return None                    # Kamera dieses Roboters sieht den Wuerfel kaum (zaehlt nicht)

    def lauf(politik, erkunden, lernen, liste):
        werte = [versuch(welt, politik, erkunden, lernen, w) for w in liste]
        return [e for e in werte if e is not None]
    aus = {'ohne': np.mean(lauf(None, False, False, test))}
    vort = greifen.Politik('x', None, None, modell=modell) if modell else None
    aus['vortrainiert'] = np.mean(lauf(vort, False, False, test)) if vort else None
    for name, start in (('online', modell), ('online_ohne_vortraining', None)):
        pol = greifen.Politik('x', None, None, modell=start)
        kurve = lauf(pol, True, True, lern)                # lernt auf diesem Roboter (mit Ausprobieren)
        aus[name + '_kurve'] = (kurve + kurve[-1:] * n_lernen)[:n_lernen]
        aus[name] = np.mean(lauf(pol, False, False, test))   # danach: gleiche Testwuerfel, ohne Ausprobieren
    return aus


def pruefen(modell, n_roboter, familie, ausgabe=print):
    rng = np.random.default_rng(SAAT_PRUEFUNG + (0 if familie == 'm3pro' else 1))
    erg = []
    for k in range(n_roboter):
        rob = GW.zufalls_roboter(rng, familie)
        r = roboter_pruefen(rob, SAAT_PRUEFUNG + 10 * k, modell)
        if r is None:
            ausgabe(f'  Pruefroboter {k + 1}: Kamera sieht den Wuerfel kaum -> nicht gezaehlt')
            continue
        erg.append(r)
        if k == 0:
            e = rob['echt']
            ausgabe(f'  Beispiel "neuer echter Roboter" Nr. 1: Schulter {np.round(np.array(e["schulter"]) * 100, 1)} cm, '
                    f'Nullpunkte {np.round(e["nullpunkte"], 1)} Grad, Durchhang {e["durchhang"]:.1f} Grad, '
                    f'Kamera {rob["kamera"]["hoehe"] * 100:.1f} cm hoch / {rob["kamera"]["neigung_deg"]:.1f} Grad')
            ausgabe(f'    ohne Lernen {r["ohne"] * 100:.0f} %, vortrainiert {r["vortrainiert"] * 100:.0f} %, '
                    f'nach 40 Versuchen weitergelernt {r["online"] * 100:.0f} %')
    mittel = lambda key: float(np.mean([r[key] for r in erg]))
    kurve = np.mean([r['online_kurve'] for r in erg], axis=0)
    kurve0 = np.mean([r['online_ohne_vortraining_kurve'] for r in erg], axis=0)
    return {'familie': familie, 'roboter': len(erg), 'ohne_lernen': mittel('ohne'), 'vortrainiert': mittel('vortrainiert'),
            'online_40': mittel('online'), 'online_40_ohne_vortraining': mittel('online_ohne_vortraining'),
            'kurve_online': [float(np.mean(kurve[i:i + 10])) for i in range(0, len(kurve), 10)],
            'kurve_online_ohne_vortraining': [float(np.mean(kurve0[i:i + 10])) for i in range(0, len(kurve0), 10)]}


def bericht(p, ausgabe=print):
    ausgabe(f"\n  Ergebnis an {p['roboter']} NEUEN Robotern (Bauart {p['familie']}), je 20 gleiche Testwuerfel:")
    for text, key in (('a) ohne Lernen (nur Kinematik)', 'ohne_lernen'), ('b) vortrainiert, ohne weiterzulernen', 'vortrainiert'),
                      ('c) vortrainiert + 40 Versuche weitergelernt', 'online_40'),
                      ('d) zum Vergleich: 40 Versuche gelernt, OHNE Vortraining', 'online_40_ohne_vortraining')):
        ausgabe(f'    {text:58s} {p[key] * 100:5.1f} % |{balken(p[key])}|')
    ausgabe('    Lernkurve auf dem neuen Roboter (Erfolg je 10 Versuche, mit Ausprobieren):')
    for i, (q, q0) in enumerate(zip(p['kurve_online'], p['kurve_online_ohne_vortraining'])):
        ausgabe(f'      Versuch {i * 10 + 1:2d}-{i * 10 + 10:2d}: vortrainiert {q * 100:5.1f} % |{balken(q, 20)}|   '
                f'ohne Vortraining {q0 * 100:5.1f} % |{balken(q0, 20)}|')


def png_zeichnen(datei, _kurve_vortraining, pruefungen):
    """Bild (OpenCV, keine Zusatzpakete): links Lernkurve auf neuen Robotern, rechts die Erfolgsquoten."""
    import cv2
    p = pruefungen[0]
    B, H = 960, 440
    img = np.full((H, B, 3), 255, np.uint8)
    blau, orange, grau, text, linie = (178, 114, 31), (14, 127, 255), (150, 150, 150), (50, 50, 50), (225, 225, 225)
    schrift = cv2.FONT_HERSHEY_SIMPLEX

    def schreibe(t, x, y, g=0.5, f=text):
        cv2.putText(img, t, (int(x), int(y)), schrift, g, f, 1, cv2.LINE_AA)
    # links: Erfolg je 10 Versuche auf einem neuen Roboter
    x0, x1, y0, y1 = 70, 500, 70, H - 70
    schreibe(f'Lernen auf {p["roboter"]} neuen Robotern (Bauart {p["familie"]})', x0 - 10, 30, 0.55)
    yq = lambda q: int(y1 - q * (y1 - y0))
    for q in (0.0, 0.25, 0.5, 0.75, 1.0):
        cv2.line(img, (x0, yq(q)), (x1, yq(q)), linie, 1)
        schreibe(f'{q * 100:.0f} %', 18, yq(q) + 5, 0.45)
    n = len(p['kurve_online'])
    xs = [int(x0 + (i + 0.5) / n * (x1 - x0)) for i in range(n)]
    for kurve, farbe, name, dy in ((p['kurve_online'], blau, 'mit Vortraining', 0),
                                   (p['kurve_online_ohne_vortraining'], orange, 'ohne Vortraining', 20)):
        pts = np.array([(x, yq(q)) for x, q in zip(xs, kurve)], np.int32)
        cv2.polylines(img, [pts], False, farbe, 2, cv2.LINE_AA)
        for x, y in pts:
            cv2.circle(img, (int(x), int(y)), 4, farbe, -1, cv2.LINE_AA)
        ly = yq(0.3) + dy
        cv2.line(img, (x0 + 220, ly - 5), (x0 + 250, ly - 5), farbe, 2)
        schreibe(name, x0 + 258, ly, 0.45)
    for i, x in enumerate(xs):
        schreibe(f'{i * 10 + 1}-{i * 10 + 10}', x - 18, y1 + 18, 0.4)
    schreibe('Versuche', x1 - 70, y1 + 36, 0.45)
    # rechts: Erfolgsquote auf denselben Testwuerfeln
    bx = 560
    schreibe('Erfolgsquote, gleiche Testwuerfel', bx, 30, 0.55)
    werte = [('ohne Lernen', p['ohne_lernen'], grau), ('vortrainiert', p['vortrainiert'], blau),
             ('vortrainiert + 40 Versuche', p['online_40'], blau), ('40 Versuche ohne Vortraining', p['online_40_ohne_vortraining'], orange)]
    for i, (name, q, farbe) in enumerate(werte):
        y = 70 + i * 82
        cv2.rectangle(img, (bx, y), (bx + 300, y + 30), linie, -1)
        cv2.rectangle(img, (bx, y), (bx + int(q * 300), y + 30), farbe, -1)
        schreibe(f'{q * 100:.0f} %', bx + 308, y + 22, 0.55)
        schreibe(name, bx, y + 50, 0.45)
    schreibe('Simulator (sim/greifen_trainieren.py), nicht am echten Roboter gemessen', 18, H - 6, 0.4, grau)
    cv2.imwrite(datei, img)


def main():
    ap = argparse.ArgumentParser(description='Greifen im Simulator vortrainieren und pruefen')
    ap.add_argument('--roboter', type=int, default=400, help='Uebungsroboter im Vortraining')
    ap.add_argument('--je-roboter', type=int, default=8, help='Wuerfel je Uebungsroboter')
    ap.add_argument('--pruefroboter', type=int, default=30)
    ap.add_argument('--schnell', action='store_true', help='kleiner Lauf zum Ausprobieren')
    ap.add_argument('--nur-pruefen', action='store_true', help='vorhandenes Modell nur pruefen')
    ap.add_argument('--modell', default=greifen.VORTRAINIERT)
    ap.add_argument('--png', default='')
    a = ap.parse_args()
    if a.schnell:
        a.roboter, a.pruefroboter = 100, 8
    alt = json.load(open(a.modell)) if os.path.exists(a.modell) else {}
    modelle, vortraining, pruefungen = {}, {}, []
    for familie, name in MODELLE.items():
        print(f'\n===== Bauart {familie} (Modell "{name}") =====')
        if a.nur_pruefen:
            modell = alt['modelle'][name]
            verlauf = alt.get('vortraining', {}).get(name, {}).get('lernkurve', [])
        else:
            print(f'Vortraining: {a.roboter} Uebungsroboter, je {a.je_roboter} Wuerfel ...')
            modell, verlauf = vortrainieren(a.roboter, a.je_roboter, familie)
        modelle[name] = modell
        print('Pruefung an neuen Zufallsrobotern (die das Vortraining nicht kannte) ...')
        p = pruefen(modell, a.pruefroboter if familie == 'm3pro' else max(4, a.pruefroboter // 2), familie)
        bericht(p)
        pruefungen.append(p)
        vortraining[name] = {'roboter': a.roboter, 'wuerfel_je_roboter': a.je_roboter, 'lernkurve': verlauf,
                             'pruefung': p}
    if not a.nur_pruefen:
        daten = {'version': 1,
                 'beschreibung': 'Vortrainierte Greif-Korrektur (lib/greifen.py), erzeugt mit sim/greifen_trainieren.py. '
                                 'eigene = echter Roboter (eigene Kinematik), sim = ROS-Simulator.',
                 'datum': time.strftime('%Y-%m-%d'), 'je_roboter': a.je_roboter,
                 'modelle': modelle, 'vortraining': vortraining}
        os.makedirs(os.path.dirname(a.modell), exist_ok=True)
        with open(a.modell, 'w') as f:
            json.dump(daten, f, separators=(',', ':'))
        print(f'\nModell gespeichert: {a.modell}')
    if a.png:
        png_zeichnen(a.png, vortraining['eigene']['lernkurve'], pruefungen)
        print(f'Lernkurve als Bild: {a.png}')


if __name__ == '__main__':
    main()
