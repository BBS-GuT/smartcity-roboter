#!/bin/bash
# Fahr-Gehirn-Training: faehrt endlos Runde um Runde nach Fahrplan, misst und lernt (docs/fahrgehirn.md).
# NUR fahren: kein Arm, kein Wegraeumen, keine KI-Zentrale. Vorher den Arm in Fahrstellung bringen (Kamera!).
#
#   scripts/fahrgehirn_training.sh                                   Fahrplan aus den Einstellungen/Standard
#   scripts/fahrgehirn_training.sh -p fahrplan:="links, rechts, geradeaus"   Fahrplan EINER Runde, der Reihe nach
#   scripts/fahrgehirn_training.sh -p fahrplan_start:=0             Roboter steht vor der 1. Kreuzung des Plans
#   scripts/fahrgehirn_training.sh -p lernen:=false                 nur messen, nichts aendern
#
# NOT-AUS: scripts/stopp.sh (beendet dieses Skript UND das Fahr-Gehirn, schickt Stopp an die Motoren).
# Fortschritt ansehen (auch waehrend der Fahrt, zweites Terminal): python3 fahrgehirn/auswerten.py
# Gelerntes: config/lokal/fahrgehirn.json   Protokolle: logs/fahrgehirn/   Zuruecksetzen: scripts/fahrgehirn_zuruecksetzen.sh
source "$(dirname "$0")/env.sh"
mkdir -p "$REPO_DIR/logs/fahrgehirn"

# Panel-Linienfolger und Fahr-Gehirn duerfen nie gleichzeitig fahren (zwei Fahrbefehle). Das Fahr-Gehirn prueft das
# beim Start selbst noch einmal ueber ROS.
if pgrep -f "line_follower/line_follower.py" > /dev/null; then
    echo "FEHLER: Der Linienfolger laeuft (Panel START?). Erst stoppen: scripts/stopp.sh"; exit 1
fi
if pgrep -f "ki/zentrale.py" > /dev/null; then
    echo "HINWEIS: Die KI-Zentrale laeuft. Das Fahr-Gehirn hoert nicht auf sie; sie kann aber den Arm (= Kamera)"
    echo "         bewegen. Fuer das Training Panel beenden oder in der KI die Arm-Freigabe aus lassen."
fi

KAMERA=""
if ! ros2 topic list 2>/dev/null | grep -q "^/camera/color/image_raw$"; then
    echo "Starte Kamera ..."
    bash "$REPO_DIR/scripts/kamera.sh" > "$REPO_DIR/logs/fahrgehirn/kamera.log" 2>&1 &
    KAMERA=$!
    sleep 5
fi
trap '[ -n "$KAMERA" ] && kill -INT $KAMERA 2>/dev/null' EXIT

# Endlos: stuerzt das Fahr-Gehirn ab (Fehlercode), startet es nach 5 s neu (Gelerntes wird geladen, die angefangene
# Runde zaehlt nicht). Normales Ende (Strg+C, stopp.sh) beendet auch dieses Skript.
while true; do
    echo "$(date '+%F %T') Fahr-Gehirn startet" | tee -a "$REPO_DIR/logs/fahrgehirn/start.log"
    PYTHONUNBUFFERED=1 python3 "$REPO_DIR/fahrgehirn/fahrgehirn.py" --ros-args "${PARAMS[@]}" \
        -p autostart:=true "$@" 2>&1 | tee -a "$REPO_DIR/logs/fahrgehirn/fahrgehirn.log"
    code=${PIPESTATUS[0]}
    [ "$code" -eq 0 ] && break
    # 3 = Startpruefung fehlgeschlagen (laeuft schon etwas) -> nicht endlos wiederholen
    [ "$code" -eq 3 ] && { echo "Fahr-Gehirn nicht gestartet (siehe oben)."; break; }
    echo "$(date '+%F %T') Fahr-Gehirn beendet mit Fehler $code -> Neustart in 5 s (Not-Aus: scripts/stopp.sh)" \
        | tee -a "$REPO_DIR/logs/fahrgehirn/start.log"
    sleep 5
done
