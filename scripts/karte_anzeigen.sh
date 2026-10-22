#!/bin/bash
# Zeigt die Karte in RViz auf dem Roboter-Bildschirm (Karte, LiDAR-Punkte, Koordinatensysteme).
# Funktioniert waehrend karte_erstellen.sh und waehrend karte_laden.sh.
# Mit Yahboom-Ansicht stattdessen:  scripts/karte_anzeigen.sh yahboom
source "$(dirname "$0")/env.sh"
export DISPLAY="${DISPLAY:-:0}"
if [ "$1" = "yahboom" ]; then
    for k in "slam_mapping slam_view.launch.py"; do
        set -- $k
        [ -n "$(finde_launch "$1" "$2")" ] && exec ros2 launch "$1" "$2"
        echo "nicht vorhanden: $1/$2"
    done
    echo "Keine Yahboom-Ansicht gefunden, nehme eigene."
fi
exec rviz2 -d "$REPO_DIR/config/karte.rviz"
