#!/bin/bash
# Startet die Kartierung mit LiDAR (slam_toolbox).
# Danach in einem zweiten Fenster: scripts/karte_anzeigen.sh
# Mit dem Gamepad LANGSAM durch alle Strassen fahren (Roboter steht dabei auf dem Brett).
# Speichern (dieses Fenster offen lassen!): scripts/karte_speichern.sh NAME
#
# Welcher Yahboom-Befehl auf dem M3 Pro richtig ist, war nicht sicher bekannt.
# Deshalb werden mehrere bekannte Namen der Reihe nach probiert.
source "$(dirname "$0")/env.sh"

if ros2 node list 2>/dev/null | grep -q slam_toolbox; then
    echo "slam_toolbox laeuft schon. Erst das andere Fenster mit Strg+C beenden."; exit 1
fi

# Paket + Datei, in dieser Reihenfolge probieren
KANDIDATEN=(
    "slam_mapping slam_toolbox.launch.py"     # Yahboom-Anleitung M3 Pro (laut Projektunterlagen)
    "m3_bringup slam_toolbox.launch.py"       # Yahboom-Anleitung ROSMASTER M3
)
for k in "${KANDIDATEN[@]}"; do
    set -- $k
    DATEI=$(finde_launch "$1" "$2")
    if [ -n "$DATEI" ]; then
        echo "Starte: ros2 launch $1 $2"
        exec ros2 launch "$1" "$2"
    fi
    echo "nicht vorhanden: $1/$2"
done

echo
echo "Keine bekannte SLAM-Startdatei gefunden. Gefundene Launch-Dateien mit 'slam' im Namen:"
for ws in "$HOME/yahboomcar_ws" "$HOME/M3Pro_ws" /opt/ros/humble; do
    find "$ws" -path "*/share/*/launch/*" -iname "*slam*" 2>/dev/null
done
echo
echo "Bitte scripts/karte_diagnose.sh ausfuehren und die Ausgabe weitergeben."
exit 1
