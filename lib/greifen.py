#!/usr/bin/env python3
# Greifen lernen (ohne ROS, nur numpy, damit testbar und auf dem Roboter ohne PyTorch).
#
# Idee in einem Satz: Die Kinematik rechnet aus, wohin der Greifer muss (Zielpunkt). Weil Masse, Servos und
# Kamera nie ganz genau stimmen, greift er trotzdem etwas daneben. Darum zielt er auf
#     Zielpunkt + Korrektur
# und die Korrektur (dx vorne, dy links, dz hoch, in m) LERNT er aus seinen Greifversuchen.
#
# Fachbegriffe kurz: "Reinforcement Learning" = Lernen durch Ausprobieren und Belohnung (Erfolg/Misserfolg)
# statt durch vorgerechnete Loesungen. Hier in einer kleinen, nachvollziehbaren Form ("Bayes-Lernen mit
# Thompson-Sampling", ein "kontextueller Bandit"):
#
#   Er hat eine Liste mit ca. 2600 VERMUTUNGEN, welche Korrektur die richtige ist (ein Gitter: -4..+4 cm
#   vorne/seitlich, -2..+2 cm hoch, alle 5 mm). Jede Vermutung hat eine Wahrscheinlichkeit.
#   1. Vorher (Vorwissen): Vermutungen nahe am Vortraining sind wahrscheinlich, weit weg unwahrscheinlich.
#   2. Ausprobieren: Er zieht zufaellig eine Vermutung - wahrscheinliche oefter - und zielt damit.
#      So probiert er am Anfang verschiedene Korrekturen aus und wird sicherer, je mehr er weiss.
#      Nie weiter als die Grenzen des Gitters (sichere, begrenzte Exploration).
#   3. Belohnung: Nach dem Wegraeumen prueft die Kamera den Weg. Frei = Erfolg, liegt noch da = Misserfolg.
#   4. Lernen (Satz von Bayes): Erfolg -> alle Vermutungen, bei denen dieser Versuch auch geklappt haette
#      (Greifer innerhalb der Greiferoeffnung um den Wuerfel), werden wahrscheinlicher. Misserfolg -> genau
#      diese werden unwahrscheinlicher. Ein einzelner Fehlversuch zaehlt nicht voll (er kann auch Pech sein).
#      Aeltere Versuche zaehlen etwas weniger (falls sich am Arm etwas veraendert).
#   Ohne Ausprobieren (z. B. beim Pruefen) nimmt er den Mittelwert aller Vermutungen.
# Wie die Korrektur von der Lage des Wuerfels abhaengt (weiter vorne/seitlich/hoeher), lernt das
# Vortraining (Ausgleichsgerade = lineare Regression), auf dem Roboter wird nur die Grundkorrektur gelernt.
#
# Vortraining: im Simulator (sim/greifen_trainieren.py) an hunderten zufaellig veraenderten Uebungsrobotern
# ("Domain Randomization": andere Armmasse, Servo-Nullpunkte, Durchhaengen, Kamera-Lage, Rauschen ...).
# Es lernt: was bei allen Robotern gleich daneben geht (Mittel) und wie verschieden sie sind (Streuung =
# wie breit er auf einem neuen Roboter anfangs suchen muss). Ergebnis: models/greifen.json (im Repository).
# Auf dem Roboter lernt er weiter: config/lokal/greifen.json (nicht im Repository, bleibt bei Updates).
# "Gelerntes zuruecksetzen" (Panel -> Arm) loescht diese Datei -> zurueck zum Vortraining.
import json
import math
import os
import time

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
VORTRAINIERT = os.path.join(REPO, 'models', 'greifen.json')
LOKAL = os.environ.get('SMARTCITY_GREIFEN', os.path.join(REPO, 'config', 'lokal', 'greifen.json'))

Z_MIN = 0.006           # Greifermitte nie tiefer als 6 mm ueber dem Boden (sonst stoesst er auf)
OEFFNUNG = 0.085        # so weit ist der Greifer offen (m, geschaetzt) -> so viel darf er danebenliegen
NAEHER_MAX = 0.12       # so weit faehrt er hoechstens blind naeher heran, wenn der Arm nicht hinreicht (m)
# Gitter der Vermutungen (m): vorne, links, hoch
GITTER_XY, GITTER_Z, SCHRITT = 0.04, 0.02, 0.005
STREUUNG_START = np.array([0.012, 0.012, 0.007])   # Vorwissen ohne Vortraining: so unsicher (m)
P_TREFFER, P_DANEBEN = 0.92, 0.06   # Wahrscheinlichkeit fuer Erfolg, wenn die Vermutung stimmt / nicht stimmt
WEICH = 0.003           # Rand der Greiferoeffnung ist nicht scharf (Messrauschen), m
VERGESSEN = 0.985       # Gewicht eines Versuchs sinkt mit jedem neueren Versuch
SPEICHER = 150          # so viele Versuche merkt er sich


def _gitter():
    xy = np.arange(-GITTER_XY, GITTER_XY + 1e-9, SCHRITT)
    z = np.arange(-GITTER_Z, GITTER_Z + 1e-9, SCHRITT)
    gx, gy, gz = np.meshgrid(xy, xy, z, indexing='ij')
    return np.column_stack([gx.ravel(), gy.ravel(), gz.ravel()])


GITTER = _gitter()


def merkmale(obj):
    """Was er vom Wuerfel weiss (Zustand), auf etwa -1..1 gebracht: [1, weiter vorne, weiter links, hoeher]."""
    vor = obj['vor'] + obj.get('breite', 0.04) / 2
    return np.array([1.0, (vor - 0.27) / 0.05, obj.get('seite', 0.0) / 0.05, (obj.get('hoehe', 0.04) - 0.04) / 0.02])


def greifpunkt(obj):
    """Wohin laut Messung (Mitte des Wuerfels, Roboter-System x vorne, y links, z hoch). Ohne Korrektur."""
    return np.array([obj['vor'] + obj['breite'] / 2, obj['seite'], max(0.012, obj['hoehe'] / 2)])


def spielraum(obj):
    """Wie weit darf er danebengreifen und es klappt trotzdem? (seitlich m, z von, z bis) bezogen auf den
    Zielpunkt. Seitlich: halbe Greiferoeffnung minus halber Wuerfel. Hoch: zwischen Boden und Oberkante."""
    z = greifpunkt(obj)[2]
    return max(0.005, (OEFFNUNG - obj['breite']) / 2), 0.003 - z, obj['hoehe'] - 0.005 - z


def trifft(greifer, mitte, breite, hoehe, boden=0.0):
    """Wuerde der Greifer an Punkt 'greifer' (x, y, z) den Wuerfel (Mitte x, y; breite; hoehe) fassen?
    (ok, Grund). Gleiche Regel in Simulator und Training."""
    daneben = math.hypot(greifer[0] - mitte[0], greifer[1] - mitte[1])
    erlaubt = max(0.005, (OEFFNUNG - breite) / 2)
    if greifer[2] < boden + 0.003:
        return False, f'stoesst auf den Boden ({greifer[2] * 100:.1f} cm)'
    if daneben > erlaubt:
        return False, f'{daneben * 100:.1f} cm daneben (erlaubt {erlaubt * 100:.1f})'
    if greifer[2] > boden + hoehe - 0.005:
        return False, f'zu hoch ({greifer[2] * 100:.1f} cm, Wuerfel {hoehe * 100:.1f} cm)'
    return True, f'{daneben * 100:.1f} cm neben der Mitte'


def _lies(datei):
    try:
        with open(datei) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _sig(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


class Politik:
    """Greif-Politik = welche Korrektur fuer welchen Wuerfel. Ein Modell je Kinematik ('eigene' = echter Roboter
    mit eigener Rechnung, 'yahboom' = mit Yahbooms Dienst, 'sim' = ROS-Simulator), weil alle anders danebengreifen.
    W: 3 x 4 Zahlen = Korrektur = W * merkmale(Wuerfel). Spalte 0 = Grundkorrektur (wird auf dem Roboter
    gelernt), Spalten 1-3 = Abhaengigkeit von der Lage (aus dem Vortraining)."""

    def __init__(self, schluessel='eigene', lokal=LOKAL, vortrainiert=VORTRAINIERT, modell=None):
        """lokal/vortrainiert: Dateien (None = keine). modell: {'W', 'streuung'} statt der vortrainierten Datei."""
        self.schluessel, self.lokal, self.vortrainiert, self.modell = schluessel, lokal, vortrainiert, modell
        self.laden()

    # ---------------------------------------------------------------- Datei
    def laden(self):
        basis = (_lies(self.vortrainiert).get('modelle') or {}).get(self.schluessel) if self.vortrainiert else None
        basis = self.modell or basis
        eigen = (_lies(self.lokal).get('modelle') or {}).get(self.schluessel) if self.lokal else None
        if basis:
            self.W0 = np.array(basis['W'], dtype=float)
            self.streuung0 = np.array(basis['streuung'], dtype=float)
            self.herkunft = 'vortrainiert (Simulator)'
        else:
            self.W0, self.streuung0, self.herkunft = np.zeros((3, 4)), STREUUNG_START.copy(), 'ohne Vortraining'
        m = eigen or {}
        self.speicher = [list(map(float, x)) for x in m.get('speicher', [])]   # [phi(4), a(3), r, zlo, zhi, erfolg]
        self.verlauf = list(m.get('verlauf', []))   # 1 / 0 je Versuch (die letzten 200)
        self.versuche, self.erfolge = int(m.get('versuche', 0)), int(m.get('erfolge', 0))
        if eigen:
            self.herkunft += ', auf diesem Roboter weitergelernt'
        self._rechnen()

    def als_dict(self):
        return {'W': np.round(self.W, 5).tolist(), 'unsicher_cm': np.round(self.unsicher * 100, 2).tolist(),
                'speicher': [[round(v, 5) for v in x] for x in self.speicher[-SPEICHER:]],
                'verlauf': self.verlauf[-200:], 'versuche': self.versuche, 'erfolge': self.erfolge,
                'geaendert': time.strftime('%Y-%m-%d %H:%M:%S')}

    def speichern(self):
        if not self.lokal:
            return
        daten = _lies(self.lokal)
        daten.setdefault('modelle', {})[self.schluessel] = self.als_dict()
        daten['hinweis'] = ('Auf diesem Roboter gelerntes Greifen (lib/greifen.py). Loeschen = zurueck zum '
                            'Vortraining (models/greifen.json). Panel -> Arm -> "Gelerntes zuruecksetzen".')
        os.makedirs(os.path.dirname(self.lokal), exist_ok=True)
        tmp = self.lokal + '.neu'
        with open(tmp, 'w') as f:
            json.dump(daten, f, indent=1)
        os.replace(tmp, self.lokal)      # erst fertig schreiben, dann tauschen (Strom weg = alte Datei bleibt)

    def zuruecksetzen(self):
        """Gelerntes dieses Roboters vergessen (zurueck zum Vortraining)."""
        if self.lokal and os.path.exists(self.lokal):
            daten = _lies(self.lokal)
            (daten.get('modelle') or {}).pop(self.schluessel, None)
            if daten.get('modelle'):
                with open(self.lokal + '.neu', 'w') as f:      # erst Hilfsdatei, dann umbenennen (nie halb)
                    json.dump(daten, f, indent=1)
                os.replace(self.lokal + '.neu', self.lokal)
            else:
                os.remove(self.lokal)
        self.laden()

    # ---------------------------------------------------------------- Rechnen (Satz von Bayes)
    def _rechnen(self):
        """Wahrscheinlichkeit jeder Vermutung (Grundkorrektur c) aus Vorwissen und allen gemerkten Versuchen."""
        c = GITTER + self.W0[:, 0]                      # Gitter um das Vorwissen herum
        logp = -0.5 * (((c - self.W0[:, 0]) / self.streuung0) ** 2).sum(axis=1)
        n = len(self.speicher)
        for i, x in enumerate(self.speicher):
            phi, a, r, zlo, zhi, erfolg = np.array(x[:4]), np.array(x[4:7]), x[7], x[8], x[9], x[10]
            e = a - (c + self.W0[:, 1:] @ phi[1:])       # so weit haette er bei dieser Vermutung danebengelegen
            drin = _sig((r - np.hypot(e[:, 0], e[:, 1])) / WEICH) * _sig((e[:, 2] - zlo) / WEICH) * _sig((zhi - e[:, 2]) / WEICH)
            p = P_DANEBEN + (P_TREFFER - P_DANEBEN) * drin
            logp += VERGESSEN ** (n - 1 - i) * np.log(p if erfolg > 0.5 else 1.0 - p)
        w = np.exp(logp - logp.max())
        self.c, self.p = c, w / w.sum()
        mitte = self.p @ c
        self.unsicher = np.sqrt(self.p @ (c - mitte) ** 2)
        self.W = self.W0.copy()
        self.W[:, 0] = mitte

    # ---------------------------------------------------------------- Handeln
    def vorschlag(self, obj, rng=None, erkunden=True):
        """(Korrektur, beste Korrektur) fuer diesen Wuerfel. erkunden=True: Vermutung zufaellig ziehen."""
        phi = merkmale(obj)
        mitte = self.W @ phi
        if not erkunden:
            return mitte, mitte
        rng = rng if rng is not None else np.random.default_rng()
        k = rng.choice(len(self.p), p=self.p)
        return self.c[k] + self.W0[:, 1:] @ phi[1:], mitte

    def ergebnis(self, obj, korrektur, erfolg):
        """Ergebnis eines Greifversuchs merken und daraus lernen. obj: gemessener Wuerfel (vor, seite, breite, hoehe)."""
        r, zlo, zhi = spielraum(obj)
        self.speicher.append(list(map(float, merkmale(obj))) + list(map(float, korrektur)) +
                             [float(r), float(zlo), float(zhi), 1.0 if erfolg else 0.0])
        self.speicher = self.speicher[-SPEICHER:]
        self.versuche += 1
        self.erfolge += bool(erfolg)
        self.verlauf = (self.verlauf + [1 if erfolg else 0])[-200:]
        self._rechnen()

    # ---------------------------------------------------------------- Anzeige
    def quote(self, n=20):
        v = self.verlauf[-n:]
        return sum(v) / len(v) if v else None

    def lernstand(self):
        q = self.quote()
        return {'modell': self.schluessel, 'herkunft': self.herkunft, 'versuche': self.versuche,
                'erfolge': self.erfolge, 'quote_letzte_20': None if q is None else round(q, 2),
                'korrektur_cm': [round(float(v) * 100, 1) for v in self.W[:, 0]],
                'unsicher_cm': [round(float(v) * 100, 2) for v in self.unsicher]}


def lernstand_dateien(lokal=LOKAL, vortrainiert=VORTRAINIERT):
    """Fuer das Panel: Lernstand aller Modelle, ohne etwas zu aendern."""
    aus = {'vortrainiert': os.path.exists(vortrainiert), 'lokal': os.path.exists(lokal), 'datei': lokal,
           'simulator': {n: {k: v.get('pruefung', {}).get(k) for k in ('ohne_lernen', 'vortrainiert', 'online_40', 'roboter')}
                         for n, v in (_lies(vortrainiert).get('vortraining') or {}).items()}}
    namen = set((_lies(vortrainiert).get('modelle') or {})) | set((_lies(lokal).get('modelle') or {}))
    aus['modelle'] = [Politik(n, lokal, vortrainiert).lernstand() for n in sorted(namen)]
    return aus


def plane(obj, seite, ik, fahr, auf, zu, politik=None, rng=None, punkt=None, boden=0.0, erkunden=True):
    """Armbewegung zum Wegraeumen: Zielpunkt (Messung) + gelernte Korrektur -> Servowinkel (ik).
    punkt: Zielpunkt schon umgerechnet (Yahboom-Kinematik), sonst aus obj. boden: Hoehe des Bodens im System
    der Kinematik. Rueckgabe wie arm.plane_wegraeumen, zusaetzlich 'lernen' (fuer politik.ergebnis) und
    'korrektur' (m). Erreicht der Arm den korrigierten Punkt nicht, nimmt er die beste Korrektur ohne
    Streuung, dann gar keine."""
    import arm as armlib
    h = obj['hoehe']
    basis = np.array(punkt if punkt is not None else greifpunkt(obj), dtype=float)
    versuche = [np.zeros(3)]
    if politik is not None:
        a, mitte = politik.vorschlag(obj, rng, erkunden)
        versuche = [a, mitte, np.zeros(3)]
    plan = None
    for a in versuche:
        g = basis + a
        g[2] = max(boden + Z_MIN, g[2])
        plan = armlib.plane_wegraeumen(ik, tuple(float(v) for v in g), armlib.ablagestellen(seite, boden + h / 2 + 0.01),
                                       h, fahr, auf, zu)
        if not plan.get('fehler'):
            plan['schritte'] = armlib.begrenze_tempo(plan['schritte'], fahr)
            plan['korrektur'] = [float(v) for v in a]
            plan['ziel'] = [float(v) for v in g]
            if politik is not None:
                plan['lernen'] = {'modell': politik.schluessel, 'a': plan['korrektur'],
                                  'obj': {k: float(obj[k]) for k in ('vor', 'seite', 'breite', 'hoehe')}}
                plan['info'] += (f", gelernte Korrektur {a[0] * 100:+.1f} / {a[1] * 100:+.1f} / {a[2] * 100:+.1f} cm")
            return plan
    # Nicht erreichbar: Wuerde es gehen, wenn er naeher heranfaehrt? (der Arm reicht nicht beliebig weit)
    # Gerechnet mit der besten gelernten Korrektur. Er faehrt so weit, dass der Zielpunkt gut 3 cm im
    # erreichbaren Bereich liegt (damit auch Korrekturen beim Ausprobieren noch gehen).
    ziel = versuche[1] if len(versuche) > 1 else versuche[0]
    geht = []
    for d in np.arange(0.01, NAEHER_MAX + 0.001, 0.01):
        g = basis + ziel - np.array([d, 0.0, 0.0])
        g[2] = max(boden + Z_MIN, g[2])
        p2 = armlib.plane_wegraeumen(ik, tuple(float(v) for v in g), armlib.ablagestellen(seite, boden + h / 2 + 0.01),
                                     h, fahr, auf, zu)
        if not p2.get('fehler'):
            geht.append(float(d))
        elif geht:
            break
    if geht:
        plan['naeher'] = round(min(geht[0] + 0.03, (geht[0] + geht[-1]) / 2), 3)
    return plan
