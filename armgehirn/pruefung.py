#!/usr/bin/env python3
# Arm-Gehirn: Hat das Greifen wirklich geklappt? (ohne ROS, testbar)
#
# Frueher (Grundbetrieb) gab es nur "Weg frei ja/nein". Das zaehlt auch einen Gegenstand, den der Greifer nur zur
# Seite aus dem Bild geschoben hat, als Erfolg - und das Lernen lernt dann eine falsche Korrektur.
# Jetzt drei Blicke/Quellen:
#   1. alter Ort: Liegt er nach dem Greifen noch dort (Kamera, Greifblick)? Wie weit verschoben?
#   2. Ablagestelle: Liegt er dort (Kamera, Arm zur Ablage gedreht)? Wie weit neben der Sollstelle?
#   3. Greifer (falls der Roboter die Servo-Stellung melden kann; der M3 Pro kann es bisher nicht): Blieb der
#      Greifer beim Zudruecken am Gegenstand stehen (gefasst) oder lief er durch (leer)?
# Ergebnis und Belohnung (0..1) - feiner als frueher:
#   abgelegt    1.0  alter Ort frei UND an der Ablage                  -> Greifpunkt stimmte
#   verloren    0.5  war gefasst (Greifer), liegt aber nicht an der Ablage -> Greifpunkt stimmte, Halt nicht
#   verschoben  0.2  liegt noch (fast) da, aber bewegt (>= 1 cm), oder anderswo im Bild -> knapp daneben
#   unberuehrt  0.0  liegt unveraendert da                             -> daneben
#   unklar      -    Kamera konnte nicht pruefen / weg, aber nirgends zu sehen -> wird NICHT gelernt
import math

STANDARD = {
    'alter_ort': 0.03,        # so nah (m) am alten Ort: das ist er noch
    'bewegt': 0.01,           # ab so viel (m) gilt er als verschoben
    'ablage_toleranz': 0.04,  # so nah (m) an der Ablagestelle: dort abgelegt
}
BELOHNUNG = {'abgelegt': 1.0, 'verloren': 0.5, 'verschoben': 0.2, 'unberuehrt': 0.0, 'unklar': None}


def _abstand(o, punkt):
    return math.hypot(mitte(o)[0] - punkt[0], o['seite'] - punkt[1])


def mitte(o):
    """Mitte des Gegenstands (x, y) im Roboter-System ('vor' ist die Vorderkante, 'laenge' die gemessene Tiefe in
    Fahrtrichtung; ohne sie wie frueher die Breite)."""
    return (o['vor'] + tiefe(o) / 2, o['seite'])


def tiefe(o):
    return o.get('tiefe_x') or o.get('laenge') or o['breite']


def bewerte(vorher, alter_blick, ablage_blick, ablage, greifer=None, cfg=None):
    """vorher: Gegenstand vor dem Greifen (vor, seite, breite, hoehe).
    alter_blick: Gegenstaende, die die Kamera danach im Greifblick sieht (Liste, leer = nichts), None = kein Blick.
    ablage_blick: Gegenstaende im Blick zur Ablage (Roboter-System), None = kein Blick moeglich.
    ablage: Sollstelle (x, y). greifer: True = gefasst, False = leer, None = unbekannt.
    Rueckgabe {'ergebnis', 'belohnung', 'alter_ort_frei', 'verschiebung_m', 'ablage_abweichung_m', 'text'}."""
    c = dict(STANDARD)
    c.update(cfg or {})
    alt = mitte(vorher)
    aus = {'alter_ort_frei': None, 'verschiebung_m': None, 'ablage_abweichung_m': None}

    def fertig(ergebnis, text):
        aus.update(ergebnis=ergebnis, belohnung=BELOHNUNG[ergebnis], text=text)
        return aus
    if alter_blick is None:
        return fertig('unklar', 'Kamera konnte den alten Ort nicht pruefen')
    nah = sorted(alter_blick, key=lambda o: _abstand(o, alt))
    if nah and _abstand(nah[0], alt) <= c['alter_ort']:
        d = _abstand(nah[0], alt)
        aus.update(alter_ort_frei=False, verschiebung_m=d)
        if greifer is True:
            return fertig('unklar', f'Greifer meldet gefasst, aber er liegt noch da ({d * 100:.1f} cm bewegt)')
        if d >= c['bewegt']:
            return fertig('verschoben', f'liegt noch da, {d * 100:.1f} cm verschoben (knapp daneben)')
        return fertig('unberuehrt', f'liegt unveraendert da ({d * 100:.1f} cm) -> daneben')
    aus['alter_ort_frei'] = True
    if ablage_blick is not None:
        an = sorted(ablage_blick, key=lambda o: _abstand(o, ablage))
        if an and _abstand(an[0], ablage) <= c['ablage_toleranz']:
            aus['ablage_abweichung_m'] = _abstand(an[0], ablage)
            if greifer is False:
                return fertig('unklar', 'liegt an der Ablage, aber Greifer meldet leer')
            return fertig('abgelegt', f"abgelegt ({aus['ablage_abweichung_m'] * 100:.1f} cm neben der Ablagestelle)")
    if nah:
        aus['verschiebung_m'] = _abstand(nah[0], alt)
        return fertig('verschoben', f"weggeschoben ({aus['verschiebung_m'] * 100:.1f} cm), nicht gegriffen")
    if greifer is True:
        return fertig('verloren', 'war gefasst, liegt aber nicht an der Ablage (unterwegs verloren?)')
    if ablage_blick is None:
        return fertig('unklar', 'alter Ort frei, Ablage konnte nicht geprueft werden')
    return fertig('unklar', 'alter Ort frei, aber weder an der Ablage noch sonst im Bild (weggeschoben oder verloren?)')
