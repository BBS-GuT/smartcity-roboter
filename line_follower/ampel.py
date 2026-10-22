#!/usr/bin/env python3
# Ampel-Erkennung (rote LED). Ohne ROS, damit sie im Linienfolger, im
# Kalibrier-Werkzeug und in Tests gleich funktioniert.
#
# Idee: Eine leuchtende LED ist klein, rund, sehr hell und sitzt in einem
# SCHWARZEN Gehaeuse. Ein roter Gegenstand (Becher, Pullover, Lego) ist
# meist groesser, nicht so hell und hat eine helle Umgebung.
# Deshalb wird jeder rote Fleck mit mehreren Pruefungen gefiltert.
import cv2
import numpy as np

# Standardwerte. Name = ROS-Parameter im Linienfolger.
# UNGETESTET mit der echten Ampel -> mit ampel_kalibrieren.py einstellen
# und die guten Werte in config/ampel.yaml speichern.
STANDARD = {
    'red_top': 0.0,         # Suchbereich oben (Anteil Bildhoehe 0..1)
    'red_bottom': 0.6,      # Suchbereich unten
    'red_left': 0.0,        # Suchbereich links (Anteil Bildbreite 0..1)
    'red_right': 1.0,       # Suchbereich rechts
    'red_hue_max': 10,      # Rot = Farbton 0..red_hue_max ...
    'red_hue_min2': 170,    # ... oder red_hue_min2..180 (Rot liegt an beiden Enden)
    'red_sat_min': 100,     # wie kraeftig das Rot sein muss (0-255)
    'red_val_min': 200,     # wie hell das Rot sein muss (0-255)
    'red_core_val': 245,    # fast weisse Pixel (ueberstrahlte LED-Mitte) ab dieser Helligkeit mitzaehlen
    'red_min_area': 15,     # kleinere Flecken ignorieren (Pixel)
    'red_max_area': 1500,   # groessere Flecken = Gegenstand, keine LED
    'red_max_aspect': 2.5,  # Fleck darf hoechstens so viel breiter als hoch sein (und umgekehrt)
    'red_min_fill': 0.4,    # Anteil des Rahmens, den der Fleck fuellt (LED rund ~0.7)
    'red_peak_min': 230,    # hellster Pixel im Fleck muss mindestens so hell sein
    'red_dark_val': 80,     # Pixel dunkler als das zaehlen als "schwarzes Gehaeuse"
    'red_dark_frac': 0.4,   # so viel der Umgebung muss dunkel sein (0 = Pruefung aus)
    # Farbtoene der anderen Lampen (gleiche Filter wie Rot). UNGETESTET mit echter Ampel.
    'yellow_hue_min': 15, 'yellow_hue_max': 35,
    'green_hue_min': 40, 'green_hue_max': 95,
}

FARBEN = ('rot', 'gelb', 'gruen')


def _ring(hsv_v, mask, x, y, bw, bh):
    """Helligkeit rund um einen Fleck (ohne den Fleck selbst)."""
    h, w = hsv_v.shape
    pad = max(2, max(bw, bh) // 4 + 1)  # schmal, das Gehaeuse ist klein
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(w, x + bw + pad), min(h, y + bh + pad)
    v = hsv_v[y0:y1, x0:x1]
    m = mask[y0:y1, x0:x1]
    return v[m == 0]


def finde_rot(img, cfg):
    """Sucht eine leuchtende rote LED (siehe finde_lampe)."""
    return finde_lampe(img, cfg, 'rot')


def finde_ampel(img, cfg):
    """Sucht leuchtende rote, gelbe und gruene LEDs.

    Rueckgabe: {'farbe': 'rot' | 'gelb' | 'gruen' | None, 'lampen': {farbe: erg von finde_lampe}}
    Leuchten mehrere (z. B. Rot + Gelb), zaehlt die vorsichtigere Farbe (Rot vor Gelb vor Gruen).
    """
    lampen = {f: finde_lampe(img, cfg, f) for f in FARBEN}
    farbe = next((f for f in FARBEN if lampen[f]['treffer'] is not None), None)
    return {'farbe': farbe, 'lampen': lampen}


def farbe_in_box(img, box, val_min=200, sat_min=80, min_pixel=6, cfg=None):
    """Welche Lampe leuchtet in einem Kasten (z. B. Ampel, die die KI gefunden hat)?

    Zaehlt helle, kraeftig farbige Pixel je Farbe. Rueckgabe 'rot' | 'gelb' | 'gruen' | None.
    """
    x, y, bw, bh = [int(v) for v in box]
    h, w = img.shape[:2]
    teil = img[max(0, y):min(h, y + bh), max(0, x):min(w, x + bw)]
    if teil.size == 0:
        return None
    hsv = cv2.cvtColor(teil, cv2.COLOR_BGR2HSV)
    c = dict(STANDARD, **(cfg or {}))     # eingestellte Farbtoene (config/ampel.yaml) wie bei der LED-Erkennung
    zahl = {}
    for f in FARBEN:
        m = sum(cv2.countNonZero(cv2.inRange(hsv, (lo, sat_min, val_min), (hi, 255, 255)))
                for lo, hi in _farbtoene(c, f))
        zahl[f] = m
    beste = max(zahl, key=zahl.get)
    return beste if zahl[beste] >= min_pixel else None


def _farbtoene(c, farbe):
    if farbe == 'rot':
        return [(0, int(c['red_hue_max'])), (int(c['red_hue_min2']), 180)]
    if farbe == 'gelb':
        return [(int(c['yellow_hue_min']), int(c['yellow_hue_max']))]
    return [(int(c['green_hue_min']), int(c['green_hue_max']))]


def finde_lampe(img, cfg, farbe):
    """Sucht eine leuchtende LED der Farbe 'rot', 'gelb' oder 'gruen'.

    img: Farbbild (BGR), cfg: Dict mit den Werten aus STANDARD.
    Rueckgabe: dict mit
      bereich   (x0, y0, x1, y1) Suchbereich im Bild
      maske     Schwarz-Weiss-Bild der roten Pixel (nur Suchbereich)
      treffer   (x, y, b, h) beste LED im ganzen Bild oder None
      kandidaten Liste (x, y, b, h, grund) aller Flecken; grund '' = ok
    """
    c = dict(STANDARD)
    c.update(cfg)
    h, w = img.shape[:2]
    ry0, ry1 = int(h * c['red_top']), int(h * c['red_bottom'])
    rx0, rx1 = int(w * c['red_left']), int(w * c['red_right'])
    erg = {'bereich': (rx0, ry0, rx1, ry1), 'maske': None, 'treffer': None, 'kandidaten': []}
    part = img[ry0:ry1, rx0:rx1]
    if part.size == 0:
        return erg

    hsv = cv2.cvtColor(part, cv2.COLOR_BGR2HSV)
    s, v = int(c['red_sat_min']), int(c['red_val_min'])
    rot = np.zeros(hsv.shape[:2], np.uint8)  # Name "rot" historisch: Pixel der gesuchten Farbe
    for lo, hi in _farbtoene(c, farbe):
        rot |= cv2.inRange(hsv, (lo, s, v), (hi, 255, 255))
    # LED-Mitte ist oft ueberstrahlt (fast weiss). Solche Pixel zaehlen nur,
    # wenn sie direkt an rote Pixel grenzen (sonst wuerde jede Lampe zaehlen).
    hell = cv2.inRange(hsv[:, :, 2], int(c['red_core_val']), 255)
    nah = cv2.dilate(rot, None, iterations=2)
    maske = rot | (hell & nah)
    maske = cv2.morphologyEx(maske, cv2.MORPH_CLOSE, None)
    erg['maske'] = maske

    contours, _ = cv2.findContours(maske, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bester, beste_flaeche = None, 0
    for cnt in contours:
        flaeche = cv2.contourArea(cnt)
        x, y, bw, bh = cv2.boundingRect(cnt)
        pixel = bw * bh
        if pixel < 4 or flaeche < c['red_min_area']:
            continue  # winzige Flecken gar nicht erst anzeigen
        grund = ''
        if flaeche > c['red_max_area']:
            grund = 'zu gross'
        elif max(bw, bh) / max(1, min(bw, bh)) > c['red_max_aspect']:
            grund = 'zu laenglich'
        elif flaeche / pixel < c['red_min_fill']:
            grund = 'nicht rund'
        else:
            fleck = np.zeros_like(maske)
            cv2.drawContours(fleck, [cnt], -1, 255, -1)
            if hsv[:, :, 2][fleck > 0].max() < c['red_peak_min']:
                grund = 'zu dunkel'
            elif c['red_dark_frac'] > 0:
                umgebung = _ring(hsv[:, :, 2], maske, x, y, bw, bh)
                if umgebung.size and np.mean(umgebung < c['red_dark_val']) < c['red_dark_frac']:
                    grund = 'Umgebung hell'
        erg['kandidaten'].append((rx0 + x, ry0 + y, bw, bh, grund))
        if not grund and flaeche > beste_flaeche:
            bester, beste_flaeche = (rx0 + x, ry0 + y, bw, bh), flaeche
    erg['treffer'] = bester
    return erg


def zeichne(view, erg):
    """Malt Suchbereich, Kandidaten und Treffer ins Bild."""
    x0, y0, x1, y1 = erg['bereich']
    cv2.rectangle(view, (x0, y0), (x1, y1), (255, 0, 255), 1)  # lila: Suchbereich
    for x, y, bw, bh, grund in erg['kandidaten']:
        if grund:  # orange: verworfen, mit Grund
            cv2.rectangle(view, (x - 2, y - 2), (x + bw + 2, y + bh + 2), (0, 165, 255), 1)
            cv2.putText(view, grund, (x, max(10, y - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 165, 255), 1)
    if erg['treffer'] is not None:  # rot dick: erkannte Ampel
        x, y, bw, bh = erg['treffer']
        cv2.rectangle(view, (x - 4, y - 4), (x + bw + 4, y + bh + 4), (0, 0, 255), 3)
        cv2.putText(view, 'ROT', (x, max(12, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
