#!/bin/bash
# Laedt eine gespeicherte Karte und zeigt sie in RViz (noch KEINE Navigation, faehrt nicht).
# Aufruf: scripts/karte_laden.sh smartcity     (ohne Fenster: ... smartcity rviz:=false)
source "$(dirname "$0")/env.sh"
export DISPLAY="${DISPLAY:-:0}"
NAME="${1:-smartcity}"; shift
MAP="$REPO_DIR/maps/$NAME.yaml"
if [ ! -f "$MAP" ]; then
    echo "Karte $MAP nicht gefunden. Vorhanden:"; ls "$REPO_DIR/maps" 2>/dev/null; exit 1
fi
if ros2 node list 2>/dev/null | grep -q slam_toolbox; then
    echo "slam_toolbox laeuft noch (karte_erstellen.sh). Erst beenden, sonst gibt es zwei Karten."; exit 1
fi
exec ros2 launch "$REPO_DIR/launch/karte_laden.launch.py" map:="$MAP" rviz_config:="$REPO_DIR/config/karte.rviz" "$@"
