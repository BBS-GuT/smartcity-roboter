"""Reine B2-Wegwahl; keine Erkennung, Regelautoritaet oder Motorfreigabe.

Vertrag: docs/entwicklung/B2-verzweigungsfreigabe.md (b1ef110).
Alle Bestaetigungen muessen von einem belegten lokalen Produzenten kommen.
Ein solcher realer E1/B2-Produzent fehlt derzeit im normalen Fahrablauf.
"""
from dataclasses import dataclass
from fractions import Fraction
import math
import random


def _kennung(wert):
    return isinstance(wert, str) and bool(wert.strip())


def _zahl(wert):
    if type(wert) not in (int, float):
        return False
    try:
        return math.isfinite(wert)
    except OverflowError:
        return False


@dataclass(frozen=True)
class Bezug:
    geraet: str
    start: str
    quelle: str  # Beleg einschliesslich Karten-/Regelversion
    knoten: str
    zufahrt: str
    anfahrt: str
    bestaetigt: bool = False


@dataclass(frozen=True)
class Eingabe:
    bezug: Bezug
    sequenz: int
    aufnahme: float
    gueltig_fuer: float
    art: str = 'beobachtung'
    geometrie: frozenset = frozenset()
    erlaubt: frozenset | None = None
    erkannt: bool = True
    ueberweg: bool = False
    einfahrtsfreigabe: bool | None = None
    ausgang: str | None = None
    bestaetigt: bool = False  # positives Einfahrts-/Ausfahrtereignis


@dataclass(frozen=True)
class Ergebnis:
    lage: str
    ausgang: str | None
    grund: str | None


class Auswahl:
    """Ein Automat pro bestaetigtem Geraete-/Start-/Quellenbezug.

    historie={} initialisiert einen bekannten neuen Start gueltig leer;
    None oder ungueltige Daten halten. Zaehler werden kopiert und nur nach
    bestaetigter Ausfahrt erhoeht. RNG muss random() in [0,1) liefern.
    """

    def __init__(self, geraet, start, quelle, *, historie=None, zufall=None):
        if not all(_kennung(x) for x in (geraet, start, quelle)):
            raise ValueError('Erwarteter Geraete-/Start-/Quellenbezug fehlt')
        self._identitaet = (geraet, start, quelle)
        self._zufall = zufall if zufall is not None else random.Random()
        self._historie = None
        if isinstance(historie, dict) and all(
                isinstance(k, tuple) and len(k) == 3 and all(_kennung(x) for x in k)
                and type(v) is int and v >= 0 for k, v in historie.items()):
            self._historie = dict(historie)
        self._bezug = None
        self._ausgang = None
        self._phase = 'bereit'
        self._abgeschlossen = set()
        self._letzte = None
        self._jetzt = None
        self.ergebnis = Ergebnis('bereit', None, None)

    @property
    def historie(self):
        return None if self._historie is None else dict(self._historie)

    def _halt(self, grund):
        self.ergebnis = Ergebnis('halt', self._ausgang, grund)
        return self.ergebnis

    def _pruefen(self, e, jetzt):
        if not _zahl(jetzt) or (self._jetzt is not None and jetzt < self._jetzt):
            return 'zeit_ungueltig'
        self._jetzt = jetzt
        if not isinstance(e, Eingabe) or not isinstance(e.bezug, Bezug):
            return 'bezug_ungueltig'
        b = e.bezug
        if (b.geraet, b.start, b.quelle) != self._identitaet:
            return 'quelle_unpassend'
        if (b.bestaetigt is not True
                or not all(_kennung(x) for x in (b.knoten, b.zufahrt, b.anfahrt))):
            return 'bezug_ungueltig'
        if (type(e.sequenz) is not int or e.sequenz < 0
                or not _zahl(e.aufnahme) or not _zahl(e.gueltig_fuer)
                or e.aufnahme < 0 or e.gueltig_fuer <= 0 or e.aufnahme > jetzt):
            return 'zeit_ungueltig'
        if jetzt - e.aufnahme > e.gueltig_fuer:
            return 'beobachtung_veraltet'
        if e.art not in ('beobachtung', 'einfahrt', 'abschluss'):
            return 'ereignis_ungueltig'
        if self._letzte is not None:
            if e.sequenz < self._letzte.sequenz:
                return 'sequenz_ruecklaeufig'
            if e.sequenz == self._letzte.sequenz and e != self._letzte:
                return 'duplikat_widerspruechlich'
            if e.sequenz > self._letzte.sequenz and e.aufnahme < self._letzte.aufnahme:
                return 'zeit_ruecklaeufig'
        return None

    def schritt(self, e, jetzt, *, haltgruende=()):
        """Frischer Snapshot oder positives Ereignis; Halt loescht nie die Wahl.

        haltgruende enthaelt uebergeordnete Schutzstopps, keine nach Einfahrt
        bereits verbrauchte Ampel-Einfahrtsbedingung. Das Ergebnis gibt selbst
        bei leerem Haltgrund keine Motorfreigabe.
        """
        grund = self._pruefen(e, jetzt)
        if grund:
            return self._halt(grund)
        if haltgruende:
            return self._halt('schutzstopp')
        if self._letzte == e:
            return self.ergebnis  # keine neue Frische, kein RNG, kein Zaehler
        self._letzte = e
        b = e.bezug
        if self._historie is None:
            return self._halt('historie_unbekannt')
        # Anfahrtkennung ist einmalig innerhalb dieses Starts/Quellenbezugs.
        if b.anfahrt in self._abgeschlossen:
            return self._halt('anfahrt_abgeschlossen')
        if self._bezug is not None and b != self._bezug:
            return self._halt('anfahrt_konflikt')
        if e.art == 'abschluss':
            if (self._phase != 'raeumen' or e.bestaetigt is not True
                    or e.ausgang != self._ausgang):
                return self._halt('abschluss_unpassend')
            key = (b.knoten, b.zufahrt, self._ausgang)
            self._historie[key] = self._historie.get(key, 0) + 1
            self._abgeschlossen.add(b.anfahrt)
            self._phase = 'abgeschlossen'
            self.ergebnis = Ergebnis('abgeschlossen', self._ausgang, None)
            self._bezug = None
            self._ausgang = None
            return self.ergebnis
        if e.erkannt is not True or e.ueberweg is not False:
            return self._halt('erkennung_fehlt' if not e.erkannt else 'ueberweg')
        if (not isinstance(e.geometrie, frozenset)
                or not all(_kennung(x) for x in e.geometrie)):
            return self._halt('geometrie_ungueltig')
        if e.erlaubt is None:
            return self._halt('erlaubnis_unbekannt')
        if (not isinstance(e.erlaubt, frozenset)
                or not all(_kennung(x) for x in e.erlaubt)):
            return self._halt('erlaubnis_ungueltig')
        kandidaten = sorted(e.geometrie & e.erlaubt)
        if self._ausgang is not None:
            if self._ausgang not in e.erlaubt:
                return self._halt('ausgang_verboten')
            if self._ausgang not in e.geometrie:
                return self._halt('ausgang_nicht_sichtbar')
        elif not kandidaten:
            return self._halt('keine_erlaubte_ausfahrt')
        if self._phase != 'raeumen' and e.einfahrtsfreigabe is not True:
            return self._halt('einfahrt_gesperrt')
        if e.art == 'einfahrt':
            if (self._ausgang is None or e.bestaetigt is not True
                    or e.ausgang != self._ausgang):
                return self._halt('einfahrt_unpassend')
            self._phase = 'raeumen'
        elif self._ausgang is None:
            if len(kandidaten) == 1:
                wahl = kandidaten[0]
            else:
                gewichte = [Fraction(1, 1 + self._historie.get((b.knoten, b.zufahrt, a), 0))
                            for a in kandidaten]
                zug = self._zufall.random()
                if not _zahl(zug) or not 0 <= zug < 1:
                    return self._halt('zufall_ungueltig')
                rest = Fraction(zug) * sum(gewichte)
                wahl = kandidaten[-1]
                for a, gewicht in zip(kandidaten, gewichte):
                    rest -= gewicht
                    if rest < 0:
                        wahl = a
                        break
            self._ausgang, self._bezug, self._phase = wahl, b, 'gewaehlt'
        self.ergebnis = Ergebnis(self._phase, self._ausgang, None)
        return self.ergebnis
