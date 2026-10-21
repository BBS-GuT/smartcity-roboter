"""Gemeinsamer Testlauf fuer Wegraeum-Regressionen: echter Entscheider, kuenstliche Uhr, reiner Planerstub.

Kein ROS, kein Geraet. Phasen werden nur gelesen, nie gesetzt. Rechnet der eigene Planerthread (Phasen
'vorpruefen' und 'planen'), wartet der Lauf auf sein Ergebnis, ohne die Testuhr weiterzudrehen; nach 3 s
Wallclock endet das mit einem ausdruecklichen Fehler statt weiterzulaufen.
"""
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ki'))
from entscheider import Entscheider  # noqa: E402

AKTEURE = ('Person', 'Hund', 'Auto')
FAHR = [90, 120, 10, 20, 90, 30]
POSEN = {'fahrstellung': FAHR}
PRUEF_POSEN = {'fahrstellung': FAHR, 'pruefblick': [90, 120, 10, 0, 90, 30]}
GREIFEN = [90, 100, 60, 60, 90, 130]


def planer(objekt, seite):
    """Kleiner gueltiger Plan; Greifer 130 = zugegriffen (dann gilt das Hindernis im Test als weggenommen)."""
    return {'schritte': [('zugreifen', GREIFEN, 1.0), ('zurueck in Fahrstellung', FAHR, 1.5)]}


class Lauf:
    """Bilder im Abstand von 0,1 s; die Welt folgt grob den Fahrwuenschen (Strecke aus 'lin')."""

    def __init__(self, posen=None, planer_fn=planer):
        self.e = Entscheider(arm_erlaubt=True, posen=dict(posen or POSEN), planer=planer_fn)
        self.t, self.nr, self.strecke = 100.0, 0, 0.0
        self.bild_zeit = self.t
        self.letzter = None

    def phase(self):
        a = self.e.ablauf
        return None if a is None else a.phase

    def schritt(self, akteur=None, im_weg=True, neu=True, **w):
        """Ein Zyklus 0,1 s spaeter. neu=False: die KI hat seitdem kein neues Bild ausgewertet (alte Bildnummer und
        alte Aufnahmezeit)."""
        a = self.e.ablauf
        ende = time.monotonic() + 3.0
        while a is not None and a.phase in ('vorpruefen', 'planen') and getattr(a, 'plan', 1) is None:
            if time.monotonic() >= ende:
                raise AssertionError(f'Testplaner in {a.phase} wurde nicht fertig')
            time.sleep(0.001)
        m = (self.letzter or {}).get('manoever') or {}
        self.strecke += m.get('lin', 0.0) * 0.1
        self.t = round(self.t + 0.1, 3)
        if neu:                          # neues Bild: Nummer und Aufnahmezeit neu; sonst beides eingefroren
            self.nr, self.bild_zeit = self.nr + 1, self.t
        daten = {'bild_nr': self.nr, 'bild_zeit': self.bild_zeit, 'ampel': None, 'stoppschild': False,
                 'lidar': float('inf'), 'lidar_hinten': 1.0, 'tiefe_hindernis': False, 'strecke': self.strecke,
                 'objekte': [] if akteur is None else [{'name': akteur, 'im_weg': im_weg}]}
        daten.update(w)
        self.letzter = self.e.update(self.t, daten)
        return self.letzter


def bewegt(befehl):
    """Neuer Arm- oder Fahrwunsch?"""
    return befehl['arm'] is not None or befehl['aktion'] != 'stopp' or befehl.get('manoever') is not None
