#!/bin/bash
# Gelerntes des Fahr-Gehirns BEWUSST zuruecksetzen (passiert nie automatisch).
# Legt vorher Sicherungen an: config/lokal/fahrgehirn.json.sicherung_<Zeit> und logs/fahrgehirn_sicherung_<Zeit>/
#   scripts/fahrgehirn_zuruecksetzen.sh           fragt nach
#   scripts/fahrgehirn_zuruecksetzen.sh --ja      ohne Nachfrage
cd "$(dirname "$0")/.." || exit 1
if pgrep -f "fahrgehirn/fahrgehirn.py" > /dev/null; then
    echo "Das Fahr-Gehirn laeuft noch -> erst scripts/stopp.sh"; exit 1
fi
if [ "$1" != "--ja" ]; then
    read -r -p "Gelernte Fahrparameter und Protokolle des Fahr-Gehirns zuruecksetzen (Sicherung wird angelegt)? (j/n) " ok
    [ "$ok" = "j" ] || { echo "Abgebrochen, nichts geaendert."; exit 0; }
fi
python3 - <<'PY'
import os, sys, time
sys.path.insert(0, 'fahrgehirn')
import lernen, messung
sicherung = lernen.Lernen(log=lambda *_: None).zuruecksetzen()
print('Lernstand zurueckgesetzt.' + (f' Sicherung: {sicherung}' if sicherung else ' (es gab noch keinen)'))
if os.path.isdir(messung.PROTOKOLL) and os.listdir(messung.PROTOKOLL):
    ziel = messung.PROTOKOLL.rstrip('/') + '_sicherung_' + time.strftime('%Y%m%d_%H%M%S')
    os.replace(messung.PROTOKOLL, ziel)
    print(f'Protokolle verschoben nach: {ziel}')
PY
