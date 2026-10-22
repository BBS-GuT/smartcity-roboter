#!/bin/bash
# Arm-Gehirn trainieren (nur Greifen, der Roboter FAEHRT NICHT). Siehe docs/armgehirn.md.
#   scripts/armgehirn_training.sh                Training (Versuch -> lernen -> speichern -> Taste -> naechster)
#   scripts/armgehirn_training.sh --einrichten   Boden neu lernen (Bereich vor und neben dem Roboter leer)
#   scripts/armgehirn_training.sh --kalibrieren  Lage der Kamera mit Markierungen kalibrieren
#   scripts/armgehirn_training.sh --sim          Uebungswelt am Laptop (ohne Roboter, ohne ROS)
# Vorher: Panel/Fahrprogramm beenden (Linienfolger und KI-Zentrale duerfen nicht laufen), Gamepad nicht benutzen.
# Die Kamera startet dieses Skript selbst, wenn sie nicht laeuft.
source "$(dirname "$0")/env.sh"
for a in "$@"; do
    if [ "$a" = "--sim" ]; then
        exec python3 "$REPO_DIR/armgehirn/training.py" "$@"
    fi
done
command -v ros2 >/dev/null || { echo "ROS 2 nicht gefunden"; exit 1; }
KAMERA=""
if ! ros2 topic list 2>/dev/null | grep -q '^/camera/depth/image_raw$'; then
    echo "Starte die Kamera ..."
    mkdir -p "$REPO_DIR/logs"
    # Eigene Prozessgruppe (set -m): Hintergrundprogramme eines Skripts ignorieren SIGINT (Strg+C), darum am Ende
    # die ganze Gruppe mit SIGTERM beenden, nach 10 s hart (RM02 22.10.: Skript hing nach dem Ende)
    set -m
    "$REPO_DIR/scripts/kamera.sh" > "$REPO_DIR/logs/armgehirn_kamera.log" 2>&1 &
    KAMERA=$!
    set +m
    trap 'echo "Beende die Kamera ..."; kill -TERM -- -$KAMERA 2>/dev/null
          for _ in $(seq 20); do kill -0 $KAMERA 2>/dev/null || break; sleep 0.5; done
          kill -KILL -- -$KAMERA 2>/dev/null' EXIT
    sleep 8
fi
python3 "$REPO_DIR/armgehirn/training.py" "$@"
