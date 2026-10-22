#!/bin/bash
# Gemeinsame ROS-Umgebung fuer alle Skripte. Wird von den anderen Skripten geladen.
[ -f /opt/ros/humble/setup.bash ] && source /opt/ros/humble/setup.bash
for ws in "$HOME/yahboomcar_ws" "$HOME/M3Pro_ws" "$HOME/mircoROS_agent"; do
    if [ -f "$ws/install/setup.bash" ]; then
        source "$ws/install/setup.bash"
    fi
done
# Domain-ID: Programme mit derselben Nummer hoeren sich gegenseitig. Alle Roboter haben ab Werk 30.
# Fahren mehrere Roboter gleichzeitig, braucht jeder eine eigene Nummer: in ~/ros_domain_id eintragen
# (z. B. "31"). ACHTUNG: Der Yahboom-Teil (micro-ROS-Agent im Autostart) muss dieselbe Nummer haben,
# sonst sehen unsere Programme den Roboter nicht mehr (siehe Wiki, Seite Roboter-und-Netz). Ohne Datei: 30.
DOMAIN_DATEI="$HOME/ros_domain_id"
DOMAIN_STANDARD=30
[ -f "$DOMAIN_DATEI" ] && DOMAIN_STANDARD="$(tr -dc '0-9' < "$DOMAIN_DATEI")"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID_OVERRIDE:-${DOMAIN_STANDARD:-30}}"

# Groesserer Shared-Memory-Bereich fuer Fast DDS, damit Kamerabilder (~900 KB) fluessig
# ankommen (in der Simulation: 15 statt 1 Bild pro Sekunde). Gilt nur fuer Programme,
# die ueber unsere Skripte starten.
export FASTRTPS_DEFAULT_PROFILES_FILE="${FASTRTPS_DEFAULT_PROFILES_FILE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/config/fastdds.xml}"

# Pfad zum Repository (Ordner ueber scripts/)
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export REPO_DIR

# Einstellungsdateien fuer ROS-Programme (spaetere gelten vor frueheren, siehe lib/einstellungen.py):
# Standard (Repository), Ampelwerte (falls kalibriert), eigene Werte dieses Roboters (config/lokal/).
PARAMS=(--params-file "$REPO_DIR/config/roboter.yaml")
[ -f "$REPO_DIR/config/ampel.yaml" ] && PARAMS+=(--params-file "$REPO_DIR/config/ampel.yaml")
[ -f "$REPO_DIR/config/lokal/roboter.yaml" ] && PARAMS+=(--params-file "$REPO_DIR/config/lokal/roboter.yaml")

# Sucht eine Launch-Datei in einem ROS-Paket. Gibt den Pfad aus oder nichts.
# Beispiel: finde_launch slam_mapping slam_toolbox.launch.py
finde_launch() {
    local prefix
    prefix=$(ros2 pkg prefix "$1" 2>/dev/null) || return 1
    [ -f "$prefix/share/$1/launch/$2" ] && echo "$prefix/share/$1/launch/$2"
}
