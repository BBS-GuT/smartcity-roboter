#!/usr/bin/env python3
# Arm-Gehirn in der Uebungswelt messen: Bringt das neue Lernen etwas? (ohne ROS, nur numpy/OpenCV)
#
# Aufruf:  python3 sim/armgehirn_messen.py               (ca. 15-30 Minuten)
#          python3 sim/armgehirn_messen.py --schnell     (ca. 3-5 Minuten)
# Fuer jeden NEUEN Zufallsroboter (Domain Randomization, Zufallszahlen anders als im Vortraining) laufen dieselben
# Gegenstaende (Lage zufaellig im Greifbereich, jeder 7. eine Spielfigur) durch alle Varianten:
#   vorher   = feste Grundkorrektur, Belohnung nur "alter Ort frei" (so lernte der Grundbetrieb bisher)
#   fein     = feste Grundkorrektur, feine Belohnung (abgelegt / verschoben / unberuehrt)
#   neu      = lageabhaengige Korrektur + feine Belohnung (Arm-Gehirn)
# Gemessen: Erfolg (abgelegt) je 10 Versuche beim Lernen, danach Erfolg auf 20 gleichen Pruefgegenstaenden ohne
# Ausprobieren, mittlerer Zielfehler (Greifermitte neben der Wuerfelmitte, nur im Simulator bekannt) und ob je eine
# Figur angefasst wurde. NUR Simulation - die Abnahme am echten Roboter ersetzt das nicht.
import argparse
import os
import sys

for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_v, '1')
import numpy as np  # noqa: E402

HIER = os.path.dirname(os.path.abspath(__file__))
for _d in (HIER, os.path.join(HIER, '..', 'lib'), os.path.join(HIER, '..', 'armgehirn')):
    sys.path.insert(0, _d)
import armgehirn_sim as AS   # noqa: E402
import greifen               # noqa: E402
import greifen_welt as GW    # noqa: E402
from augen import Augen      # noqa: E402
from gehirn import ArmGehirn  # noqa: E402

SAAT = 515000
VARIANTEN = {'vorher': {'lage': False, 'belohnung': 'grob'},
             'fein': {'lage': False, 'belohnung': 'fein'},
             'neu': {'lage': True, 'belohnung': 'fein'}}


def roboter_messen(k, n_lernen, n_pruefen, varianten, familie='m3pro', politik_fn=None):
    rng = np.random.default_rng(SAAT + k)
    rob = GW.zufalls_roboter(rng, familie)
    lagen = [('figur' if i % 7 == 6 else 'wuerfel', float(rng.uniform(*AS.BEREICH_X)), float(rng.uniform(*AS.BEREICH_Y)))
             for i in range(n_lernen)]
    pruef = [('wuerfel', float(rng.uniform(*AS.BEREICH_X)), float(rng.uniform(*AS.BEREICH_Y))) for _ in range(n_pruefen)]
    aus = {}
    for name in varianten:
        v = VARIANTEN.get(name, {'lage': True, 'belohnung': 'fein'})
        wrng = np.random.default_rng(SAAT + 1000 + k)        # gleiche Zufaelle der Welt fuer jede Variante
        welt = AS.SimWelt(rob, wrng)
        pol = politik_fn(name) if politik_fn else greifen.Politik('eigene', lokal=None, lage=v['lage'])
        g = ArmGehirn(Augen(welt), welt, welt.planer_kin, pol, GW.FAHR, AS.kamera_nenn(), auf=GW.AUF, zu=GW.ZU,
                      rng=wrng, cfg={'belohnung': v['belohnung']})
        g.einrichten()
        kurve, fehler, figur_angefasst = [], [], 0
        for art, x, y in lagen:
            welt.lege(art, x, y)
            e = g.versuch('nicht_greifen' if art == 'figur' else 'greifen')
            if art == 'figur':
                figur_angefasst += e['ergebnis'] not in ('nicht_gegriffen',)
            else:
                kurve.append(e['ergebnis'] == 'abgelegt')
            welt.raeumen()
        g.c['erkunden'] = False
        ok = []
        for art, x, y in pruef:
            welt.lege(art, x, y)
            e = g.versuch('greifen')
            ok.append(e['ergebnis'] == 'abgelegt')
            if welt.letzter_zielfehler is not None and e['ergebnis'] not in ('nicht_gegriffen', 'nicht_erreichbar'):
                fehler.append(welt.letzter_zielfehler)
            welt.raeumen()
        aus[name] = {'kurve': kurve, 'pruefung': float(np.mean(ok)), 'zielfehler_cm': float(np.mean(fehler) * 100) if fehler else None,
                     'figur_angefasst': figur_angefasst}
    return aus


def main():
    ap = argparse.ArgumentParser(description='Arm-Gehirn in der Uebungswelt messen')
    ap.add_argument('--roboter', type=int, default=12)
    ap.add_argument('--lernen', type=int, default=60, help='Lernversuche je Roboter (jeder 7. eine Figur)')
    ap.add_argument('--pruefen', type=int, default=20)
    ap.add_argument('--varianten', default='vorher,fein,neu')
    ap.add_argument('--schnell', action='store_true')
    a = ap.parse_args()
    if a.schnell:
        a.roboter, a.lernen, a.pruefen = 4, 40, 10
    varianten = a.varianten.split(',')
    alle = []
    for k in range(a.roboter):
        r = roboter_messen(k, a.lernen, a.pruefen, varianten)
        alle.append(r)
        print(f'Roboter {k + 1}: ' + ', '.join(f"{n} {r[n]['pruefung'] * 100:.0f} %" for n in varianten), flush=True)
    print(f'\nErgebnis an {a.roboter} neuen Zufallsrobotern (Bauart M3 Pro, Roboter faehrt nicht):')
    for n in varianten:
        kurven = np.array([[np.mean(r[n]['kurve'][i:i + 10]) for i in range(0, len(r[n]['kurve']), 10)] for r in alle])
        fehler = [r[n]['zielfehler_cm'] for r in alle if r[n]['zielfehler_cm'] is not None]
        print(f"  {n:7s} Lernen je 10: {' '.join(f'{q * 100:3.0f}%' for q in kurven.mean(axis=0))} | Pruefung "
              f"{np.mean([r[n]['pruefung'] for r in alle]) * 100:5.1f} % | Zielfehler {np.mean(fehler):.2f} cm | "
              f"Figur angefasst {sum(r[n]['figur_angefasst'] for r in alle)}x")


if __name__ == '__main__':
    main()
