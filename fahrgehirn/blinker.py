#!/usr/bin/env python3
# Blinker-Schnittstelle des Fahr-Gehirns: setze('links' | 'rechts' | 'aus').
#
# Das Fahr-Gehirn kennt NUR diese eine Funktion. Was dahinter passiert, ist austauschbar:
#   BlinkerAttrappe   loggt nur (jetzt, die echte Lichttechnik ist noch nicht in main)
#   spaeter           echte Lichtsteuerung (Fork smartcity-roboter-lichter-2, lib/lichter.py): eine eigene Klasse mit
#                     derselben Funktion setze(), z. B. die Richtung an die Lichter weiterreichen. Das Fahr-Gehirn
#                     selbst aendert sich dafuer nicht.
# Zusaetzlich sendet der ROS-Knoten jede Aenderung auf /fahrgehirn/blinker (std_msgs/String) - auch daran kann sich
# die Lichtsteuerung haengen, ohne Code im Fahr-Gehirn.
import time

ZUSTAENDE = ('links', 'rechts', 'aus')


class Blinker:
    """Schnittstelle. Unterklassen ueberschreiben _schalten()."""

    def __init__(self):
        self.zustand = 'aus'

    def setze(self, richtung):
        if richtung not in ZUSTAENDE:
            raise ValueError(f'Blinker kennt nur {ZUSTAENDE}, nicht {richtung!r}')
        if richtung == self.zustand:
            return
        self.zustand = richtung
        self._schalten(richtung)

    def _schalten(self, richtung):
        raise NotImplementedError


class BlinkerAttrappe(Blinker):
    """Schaltet kein Licht, schreibt nur ins Log und merkt sich den Verlauf (fuer Tests und Auswertung)."""

    def __init__(self, log=print, uhr=time.time):
        super().__init__()
        self.log, self.uhr = log, uhr
        self.verlauf = []          # [(zeit, richtung), ...]

    def _schalten(self, richtung):
        self.verlauf.append((self.uhr(), richtung))
        self.log(f'BLINKER (Attrappe): {richtung}')
