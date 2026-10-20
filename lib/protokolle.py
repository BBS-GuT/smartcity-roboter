# Protokolle (Logs) der vom Panel gestarteten Programme: anlegen, weiterschieben, als Archiv herunterladen.
#
#   logs/<name>.log      dieser Lauf
#   logs/<name>.alt.log  der Lauf davor
#
# Archiv: Jede Datei wird EINMAL komplett gelesen und genau dieser Stand ins Archiv geschrieben (Groesse = gelesene
# Bytes). Eine Datei, die waehrenddessen weitergeschrieben, umbenannt oder geloescht wird, kann das Archiv also
# nicht kaputt machen ("unexpected end of data"). Weiterschieben (neuer Lauf) und Archivieren warten aufeinander.
# Speicher ist begrenzt: pro Datei hoechstens MAX_DATEI (die NEUESTEN Bytes), insgesamt hoechstens MAX_GESAMT.
import io
import os
import tarfile
import threading
import time

MAX_DATEI = 1 * 1024 * 1024      # 1 MB pro Datei (das Ende ist das Interessante)
MAX_GESAMT = 8 * 1024 * 1024     # 8 MB fuer alle zusammen (vor dem Packen)
_lock = threading.Lock()


def neu_oeffnen(ordner, name):
    """Neuen Lauf beginnen: <name>.log -> <name>.alt.log, neue leere <name>.log. Rueckgabe: offene Datei."""
    with _lock:
        os.makedirs(ordner, exist_ok=True)
        datei = os.path.join(ordner, f'{name}.log')
        if os.path.exists(datei):
            os.replace(datei, os.path.join(ordner, f'{name}.alt.log'))
        return open(datei, 'w')


def _lesen(pfad, max_bytes):
    """Neueste max_bytes einer Datei. Rueckgabe: (Bytes, gekuerzt?)."""
    with open(pfad, 'rb') as f:
        f.seek(0, os.SEEK_END)
        groesse = f.tell()
        f.seek(max(0, groesse - max_bytes))
        return f.read(max_bytes), groesse > max_bytes


def archiv(ordner, max_datei=MAX_DATEI, max_gesamt=MAX_GESAMT):
    """Alle *.log aus ordner als .tar.gz (Bytes). Fehlt eine Datei oder ist sie nicht lesbar, steht das in
    logs/HINWEISE.txt im Archiv - das Archiv selbst ist immer vollstaendig."""
    hinweise, gesamt = [], 0
    puffer = io.BytesIO()
    with _lock, tarfile.open(fileobj=puffer, mode='w:gz') as tar:
        try:
            namen = sorted(n for n in os.listdir(ordner) if n.endswith('.log'))
        except OSError as e:
            namen = []
            hinweise.append(f'Ordner {ordner} nicht lesbar: {e}')
        for name in namen:
            platz = min(max_datei, max_gesamt - gesamt)
            if platz <= 0:
                hinweise.append(f'{name}: weggelassen (Archiv schon {max_gesamt // 1024} KB)')
                continue
            try:
                daten, gekuerzt = _lesen(os.path.join(ordner, name), platz)
            except OSError as e:          # gerade geloescht/umbenannt oder keine Rechte
                hinweise.append(f'{name}: nicht lesbar ({e.strerror or e})')
                continue
            if gekuerzt:
                hinweise.append(f'{name}: nur die letzten {len(daten)} Bytes (Grenze erreicht)')
            gesamt += len(daten)
            _hinzu(tar, f'logs/{name}', daten)
        if hinweise:
            _hinzu(tar, 'logs/HINWEISE.txt', ('\n'.join(hinweise) + '\n').encode())
    return puffer.getvalue()


def _hinzu(tar, name, daten):
    info = tarfile.TarInfo(name)
    info.size, info.mtime = len(daten), int(time.time())
    tar.addfile(info, io.BytesIO(daten))
