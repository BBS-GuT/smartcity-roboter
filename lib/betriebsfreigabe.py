"""Kennungsgebundene Betriebsfreigabe; reine Logik ohne ROS-Abhaengigkeit."""
import time


class Betriebsfreigabe:
    def __init__(self):
        self.session_id = None
        self.alte_sessions = set()
        self.generation = -1
        self.start_id = None
        self.angefordert = False
        self.freigegeben = False
        self.empfangen = float('-inf')
        self.abgelaufen = False

    def empfang(self, auftrag, jetzt=None):
        jetzt = time.monotonic() if jetzt is None else jetzt
        session = auftrag.get('session_id')
        if not isinstance(session, str) or not session or session in self.alte_sessions:
            return False
        g, sid = auftrag.get('generation'), auftrag.get('start_id')
        if type(g) is not int or g < 0 or not isinstance(sid, str) or not sid:
            return False
        if session != self.session_id:
            if self.session_id is not None:
                if auftrag.get('angefordert') is not False:
                    return False
                self.alte_sessions.add(self.session_id)
            self.session_id = session
            self.generation = -1
            self.freigegeben = False
        if g < self.generation or (g == self.generation and sid != self.start_id):
            return False
        if g > self.generation:
            self.generation, self.start_id = g, sid
            self.freigegeben = False
            self.abgelaufen = False
            self.angefordert = auftrag.get('angefordert') is True
        elif not auftrag.get('angefordert'):
            self.angefordert = self.freigegeben = False
        # Eine verlorene Verbindung braucht einen neuen bewussten START.
        self.empfangen = jetzt
        return True

    def pruefen(self, bereit, jetzt=None):
        jetzt = time.monotonic() if jetzt is None else jetzt
        if self.generation < 0:
            return False  # Noch kein Freigabeweg angefordert, initiale Bedien-Sperre.
        if jetzt - self.empfangen > .6:
            self.abgelaufen = True
            self.freigegeben = False
        elif self.angefordert and bereit and not self.abgelaufen:
            self.freigegeben = True
        return self.freigegeben

    def status(self):
        return dict(session_id=self.session_id, generation=self.generation, start_id=self.start_id,
                    betrieb_angefordert=self.angefordert,
                    betrieb_freigegeben=self.freigegeben,
                    freigabeweg_ausgefallen=self.abgelaufen)
