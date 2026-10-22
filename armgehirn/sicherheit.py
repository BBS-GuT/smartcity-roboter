#!/usr/bin/env python3
# Arm-Gehirn: Darf dieser Gegenstand weggeraeumt werden? FESTE Sicherheitsregel (nicht gelernt, ohne ROS).
#
# Sie hat Vorrang vor allem anderen: Das Greif-Lernen (lib/greifen.py) wird erst gefragt, WENN diese Regel
# "ja" sagt, und kann sie nie aendern. Im Zweifel: nicht greifen. Gegriffen wird nur, was EINDEUTIG als
# raeumbarer Gegenstand erkannt ist:
#   1. Keine Person/Figur, kein Tier, kein Fahrzeug im Bild (Kamera-KI, ab niedriger Sicherheit). Auch nicht
#      irgendwo anders im Bild: Der "Gegenstand" koennte ein Teil davon sein (Hand, Fuss, Bein einer Figur).
#   2. Die Tiefenkamera sieht den Gegenstand in genug Bildern und er liegt STILL (eine Hand bewegt sich).
#   3. Ganz im Bild (nicht am Bildrand abgeschnitten), Groesse und Form passen zu einem raeumbaren Gegenstand (z. B. Wuerfel 2-6 cm). Was deutlich hoeher als
#      breit ist, steht wie eine Figur -> nie (auch wenn die Kamera-KI die Figur nicht erkennt).
#   4. Optional (raeumbar_klassen, nur_klassen): Die Kamera-KI muss ihn als raeumbare Klasse erkennen
#      (braucht ein eigenes Modell; das Standardmodell kennt keine Wuerfel).
# Laeuft WAEHREND des Greifens ein Mensch ins Bild, aendert das nichts (Projektvorgabe): Die Regel gilt fuer die
# Entscheidung VOR dem Greifen. Abbrechen geht nur ausdruecklich von aussen (Arm-Gehirn: abbrechen()).
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ki'))
from ablaeufe import FAHRZEUGE, LEBEWESEN  # noqa: E402   gleiche Liste wie im Grundbetrieb

NIE_ANFASSEN = LEBEWESEN | FAHRZEUGE | {'Spielfigur', 'Figur', 'Mensch'}

STANDARD = {
    'breite_min': 0.015, 'breite_max': 0.06,  # m (Tiefenkamera misst Breiten eher zu klein, Uebungswelt ca. 25 %)
    'hoehe_min': 0.015, 'hoehe_max': 0.065,   # m
    'form_max': 2.6,          # hoeher als 2,6 x so breit: steht wie eine Figur -> nie anfassen
                              # (Tiefenkamera misst Breiten 20-40 % zu klein, Hoehen fast genau; an echten Figuren pruefen)
    'messungen_min': 4,       # in so vielen Bildern muss die Tiefenkamera ihn vermessen haben
    'gesehen_anteil': 0.7,    # ... und in mindestens diesem Anteil aller Bilder
    'still_max': 0.008,       # Lage (vorne/seitlich) streut ueber die Bilder hoechstens so viel (m)
    'ki_sicher': 0.25,        # Person/Tier/Fahrzeug zaehlt schon ab dieser Sicherheit der Kamera-KI
    'raeumbar_klassen': [],   # Klassen eines eigenen Modells, die eindeutig raeumbar sind (z. B. ['Wuerfel'])
    'nur_klassen': False,     # True: ohne erkannte raeumbare Klasse nie greifen
}


def entscheide(bilder, cfg=None, umgebung=None):
    """bilder: Liste je Kamerabild {'objekt': Tiefen-Objekt (vor, seite, breite, hoehe, ...) oder None,
    'objekte': Kamera-KI [{'name', 'sicher', 'box'}]}. umgebung: weitere Funde der Kamera-KI beim Umschauen
    (andere Blickrichtungen) - eine Person dort zaehlt genauso.
    Rueckgabe {'darf': bool, 'grund': Text, 'objekt': gemittelter Gegenstand oder None, 'art': 'raeumbar' |
    'verboten' | 'zweifel' | 'nichts'}. 'darf' ist nur True, wenn ALLE Pruefungen bestanden sind."""
    c = dict(STANDARD)
    c.update(cfg or {})
    if not bilder:
        return _nein('nichts', 'keine Kamerabilder', None)
    # 1. Person/Tier/Fahrzeug irgendwo im Bild -> nie (hat Vorrang vor allem)
    alle = [o for b in bilder for o in (b.get('objekte') or [])] + list(umgebung or [])
    verboten = sorted({o['name'] for o in alle if o.get('name') in NIE_ANFASSEN and o.get('sicher', 1.0) >= c['ki_sicher']})
    messungen = [b['objekt'] for b in bilder if b.get('objekt')]
    objekt = _mittel(messungen) if messungen else None
    if verboten:
        return _nein('verboten', f"{', '.join(verboten)} im Bild -> nie anfassen", objekt)
    if any(o.get('ki_fehlt') for o in alle):
        return _nein('zweifel', 'Kamera-KI laeuft nicht (koennte keine Person erkennen)', objekt)
    # 2. genug gesehen und still
    if len(messungen) < c['messungen_min'] or len(messungen) < c['gesehen_anteil'] * len(bilder):
        art = 'nichts' if not messungen else 'zweifel'
        return _nein(art, f'Tiefenkamera sieht es nur in {len(messungen)} von {len(bilder)} Bildern', objekt)
    if sum(bool(m.get('rand')) for m in messungen) > len(messungen) / 2:
        return _nein('zweifel', 'nur teilweise im Bild (beruehrt den Bildrand)', objekt)
    streuung = max(float(np.ptp([m['vor'] for m in messungen])), float(np.ptp([m['seite'] for m in messungen])))
    if streuung > c['still_max']:
        return _nein('zweifel', f'liegt nicht still (Lage schwankt um {streuung * 100:.1f} cm)', objekt)
    # 3. Groesse und Form
    b, h = objekt['breite'], objekt['hoehe']
    if h > c['form_max'] * b:
        return _nein('verboten', f'steht wie eine Figur ({h * 100:.1f} cm hoch, {b * 100:.1f} cm breit) -> nie anfassen',
                     objekt)
    if not c['breite_min'] <= b <= c['breite_max'] or not c['hoehe_min'] <= h <= c['hoehe_max']:
        return _nein('zweifel', f'Groesse passt nicht ({b * 100:.1f} cm breit, {h * 100:.1f} cm hoch)', objekt)
    # 4. Klasse (optional)
    klassen = set(c['raeumbar_klassen'] or [])
    erkannt = sorted({o['name'] for bb in bilder for o in (bb.get('objekte') or []) if o.get('name') in klassen})
    if c['nur_klassen'] and not erkannt:
        return _nein('zweifel', 'Kamera-KI erkennt keine raeumbare Klasse (nur_klassen)', objekt)
    grund = f"raeumbar: {b * 100:.1f} cm breit, {h * 100:.1f} cm hoch, still" + (f", erkannt als {erkannt[0]}" if erkannt else '')
    return {'darf': True, 'grund': grund, 'objekt': objekt, 'art': 'raeumbar'}


def _nein(art, grund, objekt):
    return {'darf': False, 'grund': grund, 'objekt': objekt, 'art': art}


def _mittel(m):
    aus = {k: float(np.median([x[k] for x in m])) for k in ('vor', 'seite', 'breite', 'hoehe')}
    if all(x.get('laenge') is not None for x in m):
        aus['laenge'] = float(np.median([x['laenge'] for x in m]))
    for k in ('pixel', 'tiefe_m'):
        werte = [x[k] for x in m if x.get(k) is not None]
        if werte:
            aus[k] = [float(v) for v in np.median(np.array(werte, dtype=float).reshape(len(werte), -1), axis=0)]
    return aus
