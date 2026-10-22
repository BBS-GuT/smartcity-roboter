#!/usr/bin/env python3
# Greifen lernen (ohne ROS, nur numpy, damit testbar und auf dem Roboter ohne PyTorch).
#
# Idee in einem Satz: Die Kinematik rechnet aus, wohin der Greifer muss (Zielpunkt). Weil Masse, Servos und
# Kamera nie ganz genau stimmen, greift er trotzdem etwas daneben. Darum zielt er auf
#     Zielpunkt + Korrektur
# und die Korrektur (dx vorne, dy links, dz hoch, in m) LERNT er aus seinen Greifversuchen - und zwar
# ABHAENGIG VON DER LAGE des Gegenstands (weiter vorne/hinten, links/rechts). Grund: Ein Fehler der Kamera
# (Massstab, Neigung) oder des Arms (Durchhaengen, Servo-Nullpunkt) wirkt vorne anders als hinten, links
# anders als rechts. Eine feste Grundkorrektur gleicht das nur in der Mitte aus.
#
# Fachbegriffe kurz: "Reinforcement Learning" = Lernen durch Ausprobieren und Belohnung (Erfolg/Misserfolg)
# statt durch vorgerechnete Loesungen. Hier in einer kleinen, nachvollziehbaren Form ("Bayes-Lernen mit
# Thompson-Sampling", ein "kontextueller Bandit"; gerechnet mit "Importance Sampling" = gewichteten Stichproben):
#
#   Korrektur = Vortraining (W0 * Merkmale)  +  c  +  B * (vorne, seitlich)
#   c = gelernte Grundkorrektur (3 Zahlen), B = gelernte Lageabhaengigkeit (3 x 2 Zahlen) -> 9 Unbekannte.
#   Er hat 3000 VERMUTUNGEN (Stichproben) fuer diese 9 Zahlen, jede mit einem Gewicht (= wie wahrscheinlich).
#   1. Vorher (Vorwissen): c streut wie im Vortraining gemessen, B ist klein (hoechstens einige mm je 5 cm).
#   2. Ausprobieren: Er zieht zufaellig eine Vermutung - wahrscheinliche oefter - und zielt damit.
#      So probiert er am Anfang verschiedene Korrekturen aus und wird sicherer, je mehr er weiss.
#      Nie weiter als +-4 cm (vorne/seitlich) bzw. +-2 cm (hoch) vom Vortraining (sichere Grenzen).
#   3. Belohnung (genauer als frueher nur "Weg frei?"): gegriffen (Gegenstand weg UND an der Ablage) /
#      verschoben (beruehrt, aber nicht gefasst = knapp daneben) / unberuehrt (liegt unveraendert da) /
#      daneben (nur "nicht frei" bekannt, Grundbetrieb).
#   4. Lernen (Satz von Bayes): Jede Vermutung wird danach gewichtet, wie gut sie ALLE gemerkten Versuche
#      erklaert: Bei "gegriffen" passen die Vermutungen, bei denen der Greifer innerhalb der Greiferoeffnung
#      um den Gegenstand gelandet waere; bei "verschoben" die, bei denen eine Backe ihn knapp getroffen haette.
#      Ein einzelner Versuch zaehlt nicht voll (kann Pech sein), aeltere zaehlen etwas weniger. Danach werden
#      neue Vermutungen dort gezogen, wo die guten liegen (mehrere Runden), damit es mit 9 Zahlen genau wird.
#   Ohne Ausprobieren (z. B. beim Pruefen) nimmt er den Mittelwert aller Vermutungen.
#   Hat der letzte Versuch geklappt, wiederholt er meist diese Korrektur ("Gewinner bleibt", WIEDERHOLEN).
# Alles ist aus den gemerkten Versuchen und einer festen Zufallszahl (SAAT) berechnet: nach einem Neustart
# kommt aus denselben Versuchen genau derselbe Lernstand heraus.
#
# Vortraining: im Simulator (sim/greifen_trainieren.py) an hunderten zufaellig veraenderten Uebungsrobotern
# ("Domain Randomization": andere Armmasse, Servo-Nullpunkte, Durchhaengen, Kamera-Lage, Rauschen ...).
# Es lernt: was bei allen Robotern gleich daneben geht (W0) und wie verschieden sie sind (Streuung =
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
ERKUNDEN_ANTEIL = 0.4    # beim Ausprobieren hoechstens so viel des Spielraums von der besten Korrektur abweichen
NAEHER_MAX = 0.15       # so weit faehrt er hoechstens blind naeher heran, wenn der Arm nicht hinreicht (m)
GRENZE = np.array([0.04, 0.04, 0.02])   # gelernte Korrektur nie weiter als so weit vom Vortraining (m)
STREUUNG_START = np.array([0.012, 0.012, 0.007])   # Vorwissen ohne Vortraining: so unsicher (m)
STEIGUNG_START = 0.01   # Vorwissen: so stark aendert sich die Korrektur etwa je 5 cm Lage (m, Streuung)
LAGE = (1, 2)           # Merkmale, von denen die gelernte Korrektur abhaengt: weiter vorne, weiter links
P_TREFFER, P_DANEBEN = 0.92, 0.06   # Wahrscheinlichkeit fuer Erfolg, wenn die Vermutung stimmt / nicht stimmt
P_KNAPP, P_ANSTOSSEN = 0.6, 0.05    # "verschoben", wenn eine Backe ihn knapp trifft / sonst (Rutschen, Pech)
KNAPP = 0.015           # Backe trifft den Gegenstand: bis so weit ausserhalb des Spielraums (m, Backenbreite)
WEICH = 0.003           # Rand der Greiferoeffnung ist nicht scharf (Messrauschen), m
VERGESSEN = 0.985       # Gewicht eines Versuchs sinkt mit jedem neueren Versuch
SPEICHER = 150          # so viele Versuche merkt er sich
WIEDERHOLEN = 0.7       # nach einem Erfolg: so oft dieselbe Korrektur nochmal (sonst neu ziehen)
STICHPROBEN, RUNDEN, SAAT = 3000, 5, 2026   # Vermutungen, Verfeinerungsrunden, feste Zufallszahl
# Ergebnis eines Versuchs (letzte Zahl je gemerktem Versuch)
DANEBEN, GEGRIFFEN, VERSCHOBEN, UNBERUEHRT = 0.0, 1.0, 2.0, 3.0
ERGEBNISSE = {True: GEGRIFFEN, False: DANEBEN, 'gegriffen': GEGRIFFEN, 'abgelegt': GEGRIFFEN,
              'verloren': GEGRIFFEN,      # war gefasst, unterwegs verloren: Greifpunkt stimmte
              'verschoben': VERSCHOBEN, 'unberuehrt': UNBERUEHRT, 'daneben': DANEBEN}


def _tiefe_x(obj):
    """Ausdehnung in Fahrtrichtung fuer die Mitte (Mitte = Vorderkante + Haelfte davon). Das Arm-Gehirn misst sie
    ('tiefe_x', RM02 22.10.: laenglicher Klotz, Mitte mit der Breite 1,6 cm zu kurz); sonst wie bisher die Breite
    (quadratische Grundflaeche angenommen)."""
    return obj.get('tiefe_x') or obj.get('breite', 0.04)


def merkmale(obj):
    """Was er vom Wuerfel weiss (Zustand), auf etwa -1..1 gebracht: [1, weiter vorne, weiter links, hoeher]."""
    vor = obj['vor'] + _tiefe_x(obj) / 2
    return np.array([1.0, (vor - 0.27) / 0.05, obj.get('seite', 0.0) / 0.05, (obj.get('hoehe', 0.04) - 0.04) / 0.02])


def greifpunkt(obj):
    """Wohin laut Messung (Mitte des Wuerfels, Roboter-System x vorne, y links, z hoch). Ohne Korrektur."""
    return np.array([obj['vor'] + _tiefe_x(obj) / 2, obj['seite'], max(0.012, obj['hoehe'] / 2)])


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


def _rund(x):
    """Zahlen so gerundet, wie sie gespeichert werden: Speicher und Datei sind gleich (Neustart = gleicher Stand)."""
    return [round(float(v), 5) for v in x]


class Politik:
    """Greif-Politik = welche Korrektur fuer welchen Wuerfel. Ein Modell je Kinematik ('eigene' = echter Roboter
    mit eigener Rechnung, 'yahboom' = mit Yahbooms Dienst, 'sim' = ROS-Simulator), weil alle anders danebengreifen.
    W: 3 x 4 Zahlen, Korrektur = W * merkmale(Wuerfel). Gelernt werden Spalte 0 (Grundkorrektur) und die
    Spalten 1-2 (Abhaengigkeit von vorne/seitlich); Spalte 3 (Hoehe) kommt nur aus dem Vortraining."""

    def __init__(self, schluessel='eigene', lokal=LOKAL, vortrainiert=VORTRAINIERT, modell=None, lage=True):
        """lokal/vortrainiert: Dateien (None = keine). modell: {'W', 'streuung'} statt der vortrainierten Datei.
        lage=False: nur die feste Grundkorrektur lernen (wie bis Oktober 2026, zum Vergleich)."""
        self.schluessel, self.lokal, self.vortrainiert, self.modell = schluessel, lokal, vortrainiert, modell
        self.lage = tuple(LAGE) if lage else ()
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
        # [phi(4), a(3), r, zlo, zhi, ergebnis]; aeltere Dateien (nur Erfolg 1/0) passen genauso
        self.speicher = [_rund(x[:11]) for x in m.get('speicher', []) if len(x) >= 11]
        self.verlauf = list(m.get('verlauf', []))   # 1 / 0 je Versuch (die letzten 200)
        self.versuche, self.erfolge = int(m.get('versuche', 0)), int(m.get('erfolge', 0))
        if eigen:
            self.herkunft += ', auf diesem Roboter weitergelernt'
        self._rechnen()

    def als_dict(self):
        return {'W': np.round(self.W, 5).tolist(), 'unsicher_cm': np.round(self.unsicher * 100, 2).tolist(),
                'speicher': self.speicher[-SPEICHER:], 'verlauf': self.verlauf[-200:], 'versuche': self.versuche,
                'erfolge': self.erfolge, 'verfahren': 'lageabhaengig (Bayes, Stichproben)',
                'geaendert': time.strftime('%Y-%m-%d %H:%M:%S')}

    def speichern(self):
        """Nach JEDEM Versuch: erst eine Hilfsdatei fertig schreiben, dann umbenennen (Strom weg = alte Datei bleibt,
        nie eine halbe). Andere Modelle in derselben Datei bleiben erhalten."""
        if not self.lokal:
            return
        daten = _lies(self.lokal)
        if not daten and os.path.exists(self.lokal):
            # vorhanden, aber unlesbar: nicht einfach ueberschreiben (andere Modelle waeren weg) -> Sicherung
            os.replace(self.lokal, self.lokal + time.strftime('.kaputt_%Y%m%d_%H%M%S'))
        daten.setdefault('modelle', {})[self.schluessel] = self.als_dict()
        daten['hinweis'] = ('Auf diesem Roboter gelerntes Greifen (lib/greifen.py). Loeschen = zurueck zum '
                            'Vortraining (models/greifen.json). Panel -> Arm -> "Gelerntes zuruecksetzen".')
        os.makedirs(os.path.dirname(os.path.abspath(self.lokal)), exist_ok=True)
        tmp = self.lokal + '.neu'
        with open(tmp, 'w') as f:
            json.dump(daten, f, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.lokal)

    def zuruecksetzen(self):
        """Gelerntes dieses Roboters vergessen (zurueck zum Vortraining). Nur bewusst aufrufen (Panel-Knopf)."""
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
    def _vorhersage(self, th, phi):
        """Korrektur je Vermutung th (N x 9) fuer Merkmale phi (T x 4) -> N x T x 3."""
        aus = (phi @ self.W0.T)[None] + th[:, None, :3]
        if self.lage:
            # um die mittlere Lage der gemerkten Versuche (self.bezug): c = Korrektur dort, B = Aenderung je 5 cm.
            # So haengen c und B kaum voneinander ab -> schneller und genauer gelernt
            B = th[:, 3:].reshape(-1, 3, len(self.lage))
            aus = aus + np.einsum('nkj,tj->ntk', B, phi[:, list(self.lage)] - self.bezug)
        return aus

    def _log_wahrscheinlichkeit(self, th):
        """Wie gut erklaert jede Vermutung alle gemerkten Versuche? (log, N Werte)"""
        s = np.array(self.speicher, dtype=float)
        phi, a, r, zlo, zhi, erg = s[:, :4], s[:, 4:7], s[:, 7], s[:, 8], s[:, 9], s[:, 10]
        e = a[None] - self._vorhersage(th, phi)      # so weit haette er bei dieser Vermutung danebengelegen
        d = np.hypot(e[..., 0], e[..., 1]) - r        # > 0: ausserhalb des Spielraums
        hoehe_ok = _sig((e[..., 2] - zlo) / WEICH) * _sig((zhi - e[..., 2]) / WEICH)
        drin = _sig(-d / WEICH) * hoehe_ok
        knapp = _sig(d / WEICH) * _sig((KNAPP - d) / WEICH) * hoehe_ok
        p_t = P_DANEBEN + (P_TREFFER - P_DANEBEN) * drin
        p_v = np.minimum(P_ANSTOSSEN + (P_KNAPP - P_ANSTOSSEN) * knapp, 0.98 - p_t)
        p = np.where(erg == GEGRIFFEN, p_t, np.where(erg == VERSCHOBEN, p_v,
                                                    np.where(erg == UNBERUEHRT, 1.0 - p_t - p_v, 1.0 - p_t)))
        gewicht = VERGESSEN ** np.arange(len(s) - 1, -1, -1)
        return (np.log(np.maximum(p, 1e-6)) * gewicht).sum(axis=1)

    def _rechnen(self):
        """Gewichtete Vermutungen aus Vorwissen und allen gemerkten Versuchen (adaptives Importance Sampling:
        Vermutungen ziehen, gewichten, dort neu ziehen, wo die guten liegen; RUNDEN mal)."""
        rng = np.random.default_rng(SAAT)
        s = np.array(self.speicher, dtype=float).reshape(-1, 11)
        self.bezug = s[:, list(self.lage)].mean(axis=0) if len(s) and self.lage else np.zeros(len(self.lage))
        sd0 = np.concatenate([self.streuung0, np.full(3 * len(self.lage), STEIGUNG_START)])
        n, dim = STICHPROBEN, len(sd0)
        mu, cov = np.zeros(dim), np.diag(sd0 ** 2)
        runden = RUNDEN if self.speicher else 1
        for runde in range(runden):
            # Vorschlag: 85 % um die bisher besten Vermutungen (breiter gestreut), 15 % aus dem Vorwissen
            # (damit nichts verloren geht, falls die bisherigen Vermutungen alle falsch liegen)
            breit = cov * (1.0 if runde == 0 else 2.0) + np.eye(dim) * 1e-8
            L = np.linalg.cholesky(breit)
            k = n if runde == 0 else int(0.85 * n)
            th = np.vstack([mu + rng.standard_normal((k, dim)) @ L.T, rng.standard_normal((n - k, dim)) * sd0])
            log_vorwissen = -0.5 * ((th / sd0) ** 2).sum(axis=1) - np.log(sd0).sum()
            if runde == 0:
                log_vorschlag = log_vorwissen
            else:
                z = np.linalg.solve(L, (th - mu).T)
                log_q = -0.5 * (z ** 2).sum(axis=0) - np.log(np.diag(L)).sum()
                log_vorschlag = np.logaddexp(np.log(0.85) + log_q, np.log(0.15) + log_vorwissen)
            logw = log_vorwissen - log_vorschlag
            if self.speicher:
                logw = logw + self._log_wahrscheinlichkeit(th)
            w = np.exp(logw - logw.max())
            w /= w.sum()
            mu = w @ th
            diff = th - mu
            cov = (diff * w[:, None]).T @ diff + np.diag((sd0 * 0.02) ** 2)
        if not self.speicher:              # nichts gelernt: genau das Vorwissen (nicht der Zufall der Stichproben)
            mu, cov = np.zeros(dim), np.diag(sd0 ** 2)
        self.th, self.p = th, w
        self.anteil_wirksam = float(1.0 / (w ** 2).sum() / n)   # wie viele Vermutungen wirklich zaehlen
        self.mitte_th = np.clip(mu, *self._grenzen())
        self.unsicher = np.sqrt(np.diag(cov)[:3])
        self.W = self.W0.copy()
        self.W[:, 0] += self.mitte_th[:3]
        if self.lage:
            B = self.mitte_th[3:].reshape(3, len(self.lage))
            self.W[:, 0] -= B @ self.bezug
            self.W[:, list(self.lage)] += B

    def _grenzen(self):
        """Sichere Grenzen der gelernten Zahlen: Grundkorrektur +-GRENZE, Lageabhaengigkeit +-GRENZE/2 je 5 cm."""
        hoch = np.concatenate([GRENZE, np.repeat(GRENZE / 2, len(self.lage))])
        return -hoch, hoch

    # ---------------------------------------------------------------- Handeln
    def vorschlag(self, obj, rng=None, erkunden=True):
        """(Korrektur, beste Korrektur) fuer diesen Wuerfel. erkunden=True: Vermutung zufaellig ziehen.
        Nie weiter als GRENZE vom Vortraining (W0 * Merkmale)."""
        phi = merkmale(obj)
        basis = self.W0 @ phi
        mitte = self.W @ phi
        if not erkunden:
            return mitte, mitte
        rng = rng if rng is not None else np.random.default_rng()
        if self.speicher and self.speicher[-1][10] == GEGRIFFEN and rng.random() < WIEDERHOLEN:
            # "Was gerade geklappt hat, wiederholen": letzter Versuch gegriffen -> meist dieselbe Abweichung vom
            # gelernten Mittel nochmal (an die Lage dieses Gegenstands angepasst). Ab und zu trotzdem etwas Neues,
            # sonst lernt er die genaue Korrektur nie (Ausprobieren gegen Ausnutzen).
            x = self.speicher[-1]
            a = mitte + (np.array(x[4:7]) - self.W @ np.array(x[:4]))
        else:
            k = rng.choice(len(self.p), p=self.p)
            a = self._vorhersage(self.th[k:k + 1], phi[None])[0, 0]
        return basis + np.clip(a - basis, -GRENZE, GRENZE), mitte

    def ergebnis(self, obj, korrektur, erfolg):
        """Ergebnis eines Greifversuchs merken und daraus lernen. obj: gemessener Gegenstand (vor, seite, breite,
        hoehe); korrektur: wirklich angefahrene Korrektur (m); erfolg: True/False (gegriffen ja/nein) oder genauer
        'abgelegt' | 'verloren' | 'verschoben' | 'unberuehrt' | 'daneben' (siehe ERGEBNISSE)."""
        code = ERGEBNISSE[erfolg]
        r, zlo, zhi = spielraum(obj)
        self.speicher.append(_rund(list(merkmale(obj)) + list(korrektur) + [r, zlo, zhi, code]))
        self.speicher = self.speicher[-SPEICHER:]
        self.versuche += 1
        self.erfolge += code == GEGRIFFEN
        self.verlauf = (self.verlauf + [1 if code == GEGRIFFEN else 0])[-200:]
        self._rechnen()

    # ---------------------------------------------------------------- Anzeige
    def quote(self, n=20):
        v = self.verlauf[-n:]
        return sum(v) / len(v) if v else None

    def lernstand(self):
        q = self.quote()
        steigung = (self.W[:, list(LAGE)] - self.W0[:, list(LAGE)]) * 100
        return {'modell': self.schluessel, 'herkunft': self.herkunft, 'versuche': self.versuche,
                'erfolge': self.erfolge, 'quote_letzte_20': None if q is None else round(q, 2),
                'korrektur_cm': [round(float(v) * 100, 1) for v in self.W[:, 0]],
                'unsicher_cm': [round(float(v) * 100, 2) for v in self.unsicher],
                # gelernt: so viel aendert sich die Korrektur (vorne/links/hoch, cm) je 5 cm weiter vorne / links
                'lage_cm_je_5cm': {'vorne': [round(float(v), 2) for v in steigung[:, 0]],
                                   'links': [round(float(v), 2) for v in steigung[:, 1]]}}


def lernstand_dateien(lokal=LOKAL, vortrainiert=VORTRAINIERT):
    """Fuer das Panel: Lernstand aller Modelle, ohne etwas zu aendern."""
    aus = {'vortrainiert': os.path.exists(vortrainiert), 'lokal': os.path.exists(lokal), 'datei': lokal,
           'simulator': {n: {k: v.get('pruefung', {}).get(k) for k in ('ohne_lernen', 'vortrainiert', 'online_40', 'roboter')}
                         for n, v in (_lies(vortrainiert).get('vortraining') or {}).items()}}
    namen = set((_lies(vortrainiert).get('modelle') or {})) | set((_lies(lokal).get('modelle') or {}))
    aus['modelle'] = [Politik(n, lokal, vortrainiert).lernstand() for n in sorted(namen)]
    return aus


def _merke(ik):
    """ik mit Gedaechtnis: dieselben Punkte (z. B. Ablagestellen beim Durchprobieren) nur einmal rechnen -
    Yahbooms Kinematik fragt jedes Mal einen ROS-Dienst."""
    schon = {}

    def neu(x, y, z):
        k = (round(x, 4), round(y, 4), round(z, 4))
        if k not in schon:
            schon[k] = ik(x, y, z)
        return schon[k]
    return neu


def plane(obj, seite, ik, fahr, auf, zu, politik=None, rng=None, punkt=None, boden=0.0, erkunden=True, anlegen=None,
          ablage=None):
    """Armbewegung zum Wegraeumen: Zielpunkt (Messung) + gelernte Korrektur -> Servowinkel (ik).
    punkt: Zielpunkt schon umgerechnet (Yahboom-Kinematik), sonst aus obj. boden: Hoehe des Bodens im System
    der Kinematik. ablage: feste Ablagestelle (x, y) im Roboter-System (Arm-Gehirn) statt der Suche neben der
    Strasse. fahr: Pose, in die der Arm am Ende zurueckfaehrt. Rueckgabe wie arm.plane_wegraeumen, zusaetzlich 'lernen' (fuer politik.ergebnis) und
    'korrektur' (m). Erreicht der Arm den korrigierten Punkt nicht, nimmt er die beste Korrektur ohne
    Streuung, dann gar keine."""
    import arm as armlib
    h = obj['hoehe']
    basis = np.array(punkt if punkt is not None else greifpunkt(obj), dtype=float)
    # Ablagestellen sind im Roboter-System gedacht; rechnet die Kinematik in einem anderen System (Yahboom:
    # base_link), um denselben Versatz verschieben wie den Greifpunkt. Belegte Stellen (LiDAR) fallen weg.
    versatz = basis[:2] - greifpunkt(obj)[:2] if punkt is not None else np.zeros(2)
    stellen = ([(ablage[0], ablage[1], boden + h / 2 + 0.01)] if ablage is not None
               else armlib.ablagestellen(seite, boden + h / 2 + 0.01, obj.get('belegt')))
    ablagen = [(x + float(versatz[0]), y + float(versatz[1]), z) for x, y, z in stellen]
    ik = _merke(ik)
    versuche = [np.zeros(3)]
    if politik is not None:
        a, mitte = politik.vorschlag(obj, rng, erkunden)
        # Ausprobieren nur innerhalb des Spielraums: weiter daneben trifft eine Backe den Gegenstand (er rutscht
        # weg oder wird verkantet gequetscht). RM02 20.10.: bis 3,5 cm seitlich ausprobiert -> 13 von 15 daneben.
        r, zlo, zhi = spielraum(obj)
        grenze = np.array([ERKUNDEN_ANTEIL * r, ERKUNDEN_ANTEIL * r, ERKUNDEN_ANTEIL * (zhi - zlo) / 2])
        a = mitte + np.clip(np.asarray(a, dtype=float) - mitte, -grenze, grenze)
        versuche = [a, mitte, np.zeros(3)]
    plan = None
    for a in versuche:
        g = basis + a
        g[2] = max(boden + Z_MIN, g[2])
        plan = armlib.plane_wegraeumen(ik, tuple(float(v) for v in g), ablagen, h, fahr, auf, zu, anlegen)
        if not plan.get('fehler'):
            plan['schritte'] = armlib.begrenze_tempo(plan['schritte'], fahr)
            # wirklich angefahrene Korrektur (nach Z_MIN): sonst lernt er aus einem Punkt, den er nie angefahren hat
            plan['korrektur'] = [float(v) for v in g - basis]
            plan['ziel'] = [float(v) for v in g]
            if politik is not None:
                plan['lernen'] = {'modell': politik.schluessel, 'a': plan['korrektur'],
                                  'obj': {k: float(obj[k]) for k in ('vor', 'seite', 'breite', 'hoehe', 'tiefe_x') if obj.get(k) is not None}}
                k = plan['korrektur']
                plan['info'] += (f", gelernte Korrektur {k[0] * 100:+.1f} / {k[1] * 100:+.1f} / {k[2] * 100:+.1f} cm")
            return plan
        if plan.get('ablage_fehlt'):
            return plan       # greifen ginge, ablegen nicht: naeher heranfahren hilft da nicht
    # Nicht erreichbar: Wuerde es gehen, wenn er naeher heranfaehrt? (der Arm reicht nicht beliebig weit)
    # Gerechnet mit der besten gelernten Korrektur. Er faehrt so weit, dass der Zielpunkt gut 3 cm im
    # erreichbaren Bereich liegt (damit auch Korrekturen beim Ausprobieren noch gehen).
    ziel = versuche[1] if len(versuche) > 1 else versuche[0]
    geht = []
    for d in np.arange(0.01, NAEHER_MAX + 0.001, 0.01):
        g = basis + ziel - np.array([d, 0.0, 0.0])
        g[2] = max(boden + Z_MIN, g[2])
        p2 = armlib.plane_wegraeumen(ik, tuple(float(v) for v in g), ablagen, h, fahr, auf, zu, anlegen)
        if not p2.get('fehler'):
            geht.append(float(d))
        elif p2.get('ablage_fehlt'):
            return p2         # naeher dran griffe er, haette aber keine Ablagestelle
        elif geht:
            break
    if geht:
        plan['naeher'] = round(min(geht[0] + 0.03, (geht[0] + geht[-1]) / 2), 3)
    return plan
