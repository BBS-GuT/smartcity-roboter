#!/usr/bin/env python3
# Prueft das Greif-Lernen (lib/greifen.py), das Lesen der Arm-Masse aus einer URDF (lib/urdf.py) und die
# Uebungswelt (sim/greifen_welt.py). Ohne ROS, dauert wenige Sekunden.
# Aufruf: python3 tests/test_greifen.py
import os
import sys
import tempfile

import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, '..', 'lib'))
sys.path.insert(0, os.path.join(HIER, '..', 'sim'))
import arm as armlib   # noqa: E402
import greifen         # noqa: E402
import urdf            # noqa: E402

fehler = 0


def pruefe(name, ok, info=''):
    global fehler
    fehler += not ok
    print(f"{'OK  ' if ok else 'FEHLER'} {name} {info}")


# ---------------- Ablagestellen ----------------
alle = armlib.ablagestellen(-1, 0.03)
pruefe('Ablagestellen: bevorzugte Seite zuerst, beide Seiten, ausserhalb des Fahrschlauchs',
       alle[0][1] < 0 and any(a[1] > 0 for a in alle) and min(abs(a[1]) for a in alle) >= 0.17)
frei = armlib.ablagestellen(-1, 0.03, belegt=[(0.10, -0.18)])
pruefe('Ablagestellen: belegte Stelle (LiDAR) faellt weg', (0.10, -0.18, 0.03) not in frei and len(frei) < len(alle))
kin = armlib.Kinematik()
p = greifen.plane({'vor': 0.16, 'seite': 0.0, 'breite': 0.04, 'hoehe': 0.04}, -1, kin.inverse,
                  [90, 120, 10, 20, 90, 30], 30, 130, erkunden=False)
pruefe('Wegraeumen planbar (Standardmasse)', not p.get('fehler'), p.get('info', p.get('fehler')))
p = greifen.plane({'vor': 0.16, 'seite': 0.0, 'breite': 0.04, 'hoehe': 0.04}, -1,
                  lambda x, y, z: kin.inverse(x, y, z) if abs(y) < 0.1 else None,
                  [90, 120, 10, 20, 90, 30], 30, 130, erkunden=False)
pruefe('greifen ja, ablegen nein -> ablage_fehlt, kein Naeherfahren', p.get('ablage_fehlt') and not p.get('naeher'),
       p.get('fehler'))

# ---------------- Greifkraft nach Breite, Ausprobieren begrenzt ----------------
a3, z3 = armlib.greifer_fuer_breite(0.03)
a5, z5 = armlib.greifer_fuer_breite(0.05)
pruefe('Greifer: breiter -> weniger weit zu, nie ueber greifer_zu, erst anlegen, dann zu',
       z5 < z3 <= armlib.greifer_werte()[1] and a3 < z3 and a5 < z5, f'3 cm: {a3}/{z3}, 5 cm: {a5}/{z5}')
p = greifen.plane({'vor': 0.16, 'seite': 0.0, 'breite': 0.04, 'hoehe': 0.04}, -1, kin.inverse,
                  [90, 120, 10, 20, 90, 30], 30, z5, anlegen=a5, erkunden=False)
texte = [t for t, _, _ in p.get('schritte', [])]
pruefe('mit anlegen: erst Greifer anlegen, dann zugreifen', texte.index('Greifer anlegen') + 1 == texte.index('zugreifen'))


class Wild:
    """Politik, die beim Ausprobieren 4 cm daneben vorschlaegt."""
    schluessel = 'test'

    def vorschlag(self, obj, rng, erkunden):
        return np.array([0.0, 0.04, 0.0]), np.zeros(3)


p = greifen.plane({'vor': 0.16, 'seite': 0.0, 'breite': 0.03, 'hoehe': 0.07}, -1, kin.inverse,
                  [90, 120, 10, 20, 90, 30], 30, 130, politik=Wild())
r = greifen.spielraum({'vor': 0.16, 'seite': 0.0, 'breite': 0.03, 'hoehe': 0.07})[0]
pruefe('Ausprobieren bleibt im Spielraum des Greifers', abs(p['korrektur'][1]) <= greifen.ERKUNDEN_ANTEIL * r + 1e-9,
       f"{p['korrektur'][1] * 100:.1f} cm")

# ---------------- Regel: wann ist gegriffen? ----------------
pruefe('Greifer mittig im Wuerfel -> gegriffen', greifen.trifft((0.27, 0.0, 0.02), (0.27, 0.0), 0.045, 0.045)[0])
pruefe('3 cm daneben -> nicht gegriffen', not greifen.trifft((0.30, 0.0, 0.02), (0.27, 0.0), 0.045, 0.045)[0])
pruefe('ueber dem Wuerfel -> nicht gegriffen', not greifen.trifft((0.27, 0.0, 0.05), (0.27, 0.0), 0.045, 0.045)[0])
pruefe('im Boden -> nicht gegriffen', not greifen.trifft((0.27, 0.0, 0.001), (0.27, 0.0), 0.045, 0.045)[0])


# ---------------- Lernen in einer ausgedachten Welt (schnell, ohne Bilder) ----------------
def welt_versuch(pol, rng, richtig, erkunden=True, lernen=True):
    """Wuerfel zufaellig; Erfolg, wenn die Korrektur nah genug an der 'richtigen' liegt (wie trifft())."""
    obj = {'vor': 0.25 + rng.uniform(-0.02, 0.02), 'seite': rng.uniform(-0.04, 0.04), 'breite': 0.045, 'hoehe': 0.045}
    a, _ = pol.vorschlag(obj, rng, erkunden)
    e = np.array(a) - richtig + rng.normal(0, 0.002, 3)        # Rest-Fehler + etwas Messrauschen
    r, zlo, zhi = greifen.spielraum(obj)
    ok = bool(np.hypot(e[0], e[1]) < r and zlo < e[2] < zhi)
    if lernen:
        pol.ergebnis(obj, a, ok)
    return ok


rng = np.random.default_rng(3)
richtig = np.array([0.025, -0.018, 0.004])   # so weit greift dieser "Roboter" ohne Korrektur daneben
pol = greifen.Politik('test', lokal=None, vortrainiert=None)
vorher = np.mean([welt_versuch(pol, rng, richtig, False, False) for _ in range(100)])
lernkurve = [welt_versuch(pol, rng, richtig) for _ in range(40)]
nachher = np.mean([welt_versuch(pol, rng, richtig, False, False) for _ in range(100)])
abstand = np.linalg.norm(pol.W[:, 0] - richtig)
pruefe('Lernen aus Erfolg/Misserfolg: nach 40 Versuchen deutlich besser', nachher >= 0.9 and nachher > vorher + 0.3,
       f'(ohne Lernen {vorher:.0%}, nach 40 Versuchen {nachher:.0%}, Lernkurve je 10: '
       f'{[f"{np.mean(lernkurve[i:i + 10]):.0%}" for i in range(0, 40, 10)]})')
pruefe('gelernte Korrektur liegt nahe an der richtigen', abstand < 0.012,
       f'(gelernt {np.round(pol.W[:, 0] * 100, 1)} cm, richtig {richtig * 100} cm)')
pruefe('Unsicherheit ist kleiner geworden', np.all(pol.unsicher < greifen.STREUUNG_START), f'({np.round(pol.unsicher * 100, 2)} cm)')
pruefe('Ausprobieren bleibt im sicheren Bereich (Gitter +-4 cm / +-2 cm)',
       all(np.all(np.abs(pol.vorschlag({'vor': 0.25, 'seite': 0, 'breite': 0.045, 'hoehe': 0.045}, rng)[0] - pol.W @ greifen.merkmale(
           {'vor': 0.25, 'seite': 0, 'breite': 0.045, 'hoehe': 0.045})) <= [0.081, 0.081, 0.041]) for _ in range(50)))

# Vorwissen hilft: Start nahe an der richtigen Korrektur -> von Anfang an besser
pol_v = greifen.Politik('test', None, None, modell={'W': np.column_stack([richtig + 0.004, np.zeros((3, 3))]).tolist(),
                                                     'streuung': [0.006, 0.006, 0.004]})
mit = np.mean([welt_versuch(pol_v, rng, richtig, False, False) for _ in range(100)])
pruefe('mit gutem Vorwissen (Vortraining) sofort besser als ohne', mit > vorher + 0.3, f'({mit:.0%} statt {vorher:.0%})')

# ---------------- Speichern, Laden, Zuruecksetzen ----------------
with tempfile.TemporaryDirectory() as d:
    lokal, vort = os.path.join(d, 'lokal', 'greifen.json'), os.path.join(d, 'vort.json')
    import json
    with open(vort, 'w') as f:
        json.dump({'modelle': {'eigene': {'W': np.zeros((3, 4)).tolist(), 'streuung': [0.01, 0.01, 0.006]}}}, f)
    p1 = greifen.Politik('eigene', lokal, vort)
    for _ in range(15):
        welt_versuch(p1, rng, richtig)
    p1.speichern()
    p2 = greifen.Politik('eigene', lokal, vort)
    pruefe('gespeichertes Lernen wird wieder geladen (config/lokal/greifen.json)',
           p2.versuche == 15 and np.allclose(p2.W, p1.W, atol=1e-4) and 'weitergelernt' in p2.herkunft)
    stand = greifen.lernstand_dateien(lokal, vort)
    pruefe('Lernstand fuers Panel', stand['modelle'][0]['versuche'] == 15 and stand['lokal'], f"({stand['modelle'][0]})")
    p2.zuruecksetzen()
    pruefe('Gelerntes zuruecksetzen -> wieder Vortraining, Datei weg',
           p2.versuche == 0 and not os.path.exists(lokal) and np.allclose(p2.W, 0))

# ---------------- Vortrainiertes Modell im Repository ----------------
pv = greifen.Politik('eigene', lokal=None)
pruefe('models/greifen.json vorhanden und lesbar (Modelle eigene + sim)',
       os.path.exists(greifen.VORTRAINIERT) and pv.herkunft.startswith('vortrainiert')
       and greifen.Politik('sim', lokal=None).herkunft.startswith('vortrainiert'))

# ---------------- Planen: Zielpunkt + Korrektur, naeher heranfahren ----------------
fahr = [90, 120, 10, 20, 90, 30]
obj = {'vor': 0.25, 'seite': 0.01, 'breite': 0.04, 'hoehe': 0.045}
sim_kin = armlib.Kinematik({'schulter': [0.037, 0.0, 0.13], 'oberarm': 0.083, 'unterarm': 0.083, 'hand': 0.155})
plan = greifen.plane(obj, -1, sim_kin.inverse, fahr, 30, 130, pol, rng)
ok = not plan.get('fehler') and plan.get('lernen') and abs(plan['ziel'][0] - (0.27 + plan['korrektur'][0])) < 1e-6
pruefe('Plan mit gelernter Korrektur, Lerndaten dabei', bool(ok), f"({plan.get('info', plan.get('fehler'))})")
langsam = all(max(abs(a - b) for a, b in zip(w1[:5], w0[:5])) / t <= 60.5
              for (_, w0, _), (_, w1, t) in zip([('', fahr, 0)] + plan['schritte'], plan['schritte']))
pruefe('Armbewegungen langsam (hoechstens 60 Grad/s je Servo)', langsam)
m3 = armlib.Kinematik()          # Standardmasse des echten Arms: reicht nicht bis 27 cm
plan = greifen.plane(obj, -1, m3.inverse, fahr, 30, 130)
pruefe('Arm reicht nicht hin -> Plan sagt, wie viel naeher', bool(plan.get('fehler')) and 0 < plan.get('naeher', 0) <= 0.12,
       f"({plan.get('naeher')} m)")
plan = greifen.plane(dict(obj, vor=obj['vor'] - plan['naeher']), -1, m3.inverse, fahr, 30, 130)
pruefe('... danach erreichbar', not plan.get('fehler'), f"({plan.get('info', plan.get('fehler'))})")

# ---------------- Arm-Masse aus einer URDF (xacro mit Platzhaltern) ----------------
URDF = '''<?xml version="1.0"?>
<robot name="test" xmlns:xacro="http://www.ros.org/wiki/xacro">
  <xacro:property name="l2" value="0.08285"/>
  <link name="base_link"/><link name="arm1"/><link name="arm2"/><link name="arm3"/><link name="arm4"/><link name="arm5"/>
  <link name="lwheel"/>
  <joint name="wheel" type="continuous"><parent link="base_link"/><child link="lwheel"/><origin xyz="0 0.1 0.04" rpy="${pi/2} 0 0"/></joint>
  <joint name="arm1_joint" type="revolute"><parent link="base_link"/><child link="arm1"/><origin xyz="0.0336 0 0.185"/><axis xyz="0 0 1"/></joint>
  <joint name="arm2_joint" type="revolute"><parent link="arm1"/><child link="arm2"/><origin xyz="0 0 0.033"/><axis xyz="0 -1 0"/></joint>
  <joint name="arm3_joint" type="revolute"><parent link="arm2"/><child link="arm3"/><origin xyz="0 0 ${l2}"/><axis xyz="0 -1 0"/></joint>
  <joint name="arm4_joint" type="revolute"><parent link="arm3"/><child link="arm4"/><origin xyz="0 0 ${l2}"/><axis xyz="0 -1 0"/></joint>
  <joint name="arm5_joint" type="revolute"><parent link="arm4"/><child link="arm5"/><origin xyz="0 0 0.0748"/><axis xyz="0 0 1"/></joint>
</robot>'''
with tempfile.TemporaryDirectory() as d:
    datei = os.path.join(d, 'm3pro.urdf.xacro')
    with open(datei, 'w') as f:
        f.write(URDF)
    geo = urdf.arm_geometrie(datei, greifpunkt=0.075)
    ok = geo and np.allclose(geo['schulter'], [0.0336, 0, 0.218], atol=1e-4) and abs(geo['oberarm'] - 0.08285) < 1e-3 \
        and abs(geo['hand'] - 0.1498) < 1e-3
    pruefe('Arm-Masse aus URDF/xacro gelesen', bool(ok), f'({geo})')
    os.environ['SMARTCITY_URDF'] = datei
    pruefe('URDF wird gefunden (SMARTCITY_URDF)', urdf.finde_urdf() == datei)
    del os.environ['SMARTCITY_URDF']

# ---------------- Uebungswelt (Bilder + echte Auswertung) ----------------
import greifen_welt as GW   # noqa: E402
rng = np.random.default_rng(11)
w = GW.Uebungswelt(GW.zufalls_roboter(rng, 'sim'), rng)
werte = []
for _ in range(6):
    w.neuer_wuerfel()
    o = w.messen()
    if o:
        werte.append(w.greifen(o, None)[0])
pruefe('Uebungswelt: misst Wuerfel und rechnet Greifversuche', len(werte) >= 4, f'({werte})')

print()
print('Alle Tests bestanden.' if not fehler else f'{fehler} Test(s) fehlgeschlagen.')
sys.exit(1 if fehler else 0)
