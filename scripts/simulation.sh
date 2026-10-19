#!/bin/bash
# Simulation OHNE Roboter, z. B. in einer Linux-VM auf dem Laptop (Anleitung: docs/simulation.md).
#   scripts/simulation.sh einrichten -> installiert ROS 2 Humble + Python-Pakete (einmalig, fragt vorher)
#   scripts/simulation.sh            -> Simulator + Panel, Browser geht auf: http://localhost:8080
#                                       START druecken, Kamera-Ansicht "Simulation" = Welt von oben
#   scripts/simulation.sh pruefen    -> faehrt gut 2 Minuten und prueft automatisch alles
#                                       (Linie, Ampel, Zebrastreifen, Wuerfel wegraeumen, Stoppschild,
#                                        Einbahnstrasse, Karte)
#   scripts/simulation.sh schwer     -> wie ohne Zusatz, aber wie in echt: grosser Raum, zwei LiDARs mit
#                                       versetztem Einbau, Lagesensor misst 3 % falsch, Scans kommen spaeter an
# Nutzt eine EIGENE Domain-ID (77), damit nie ein echter Roboter (Domain 30) mitfaehrt,
# eigene Arm-Einstellungen (sim/arm_sim.yaml, Kopie in /tmp) und eine eigene Karte "sim".
if [ "$1" = "einrichten" ]; then
    . /etc/os-release
    if [ "$VERSION_CODENAME" != "jammy" ]; then
        echo "Dieses System ist $PRETTY_NAME. ROS 2 Humble gibt es fertig nur fuer Ubuntu 22.04 (jammy)."
        echo "-> VM mit Ubuntu 22.04 anlegen (docs/simulation.md)."; exit 1
    fi
    read -r -p "ROS 2 Humble und Python-Pakete installieren (braucht sudo, ca. 1 GB)? (j/n) " ok
    [ "$ok" = "j" ] || exit 1
    set -e
    sudo apt-get update
    sudo apt-get install -y software-properties-common curl git
    sudo add-apt-repository -y universe
    if [ ! -f /etc/apt/sources.list.d/ros2.list ]; then
        sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
            -o /usr/share/keyrings/ros-archive-keyring.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu jammy main" \
            | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
    fi
    sudo apt-get update
    sudo apt-get install -y ros-humble-ros-base ros-humble-cv-bridge python3-opencv python3-yaml python3-pip
    # onnxruntime rechnet die KI-Erkennung; numpy<2, sonst geht cv_bridge von Humble nicht
    pip3 install --user "onnxruntime<1.20" "numpy<2"
    echo; echo "Fertig. Simulation starten: scripts/simulation.sh"
    exit 0
fi

export ROS_DOMAIN_ID_OVERRIDE=77
source "$(dirname "$0")/env.sh"
if [ "$ROS_DOMAIN_ID" = "30" ]; then echo "Domain-ID 30 = Roboter. Abbruch."; exit 1; fi
command -v ros2 >/dev/null || { echo "ROS 2 nicht gefunden -> scripts/simulation.sh einrichten"; exit 1; }
export SMARTCITY_ARM_YAML=/tmp/smartcity_arm_sim.yaml
cp "$REPO_DIR/sim/arm_sim.yaml" "$SMARTCITY_ARM_YAML"     # immer frisch: Arm-Geometrie der Simulation
if [ "$1" = "pruefen" ]; then
    exec python3 "$REPO_DIR/sim/pruefen.py"
fi
SIM_ARGS=()
if [ "$1" = "schwer" ]; then
    SIM_ARGS=(--ros-args -p halle:=true -p imu_skala:=1.03 -p lidar_umlauf:=0.12 -p lidar_verzoegerung:=0.1
              -p "lidar1_einbau:=[-0.12,0.0,4.0]")
fi
python3 "$REPO_DIR/sim/simulator.py" "${SIM_ARGS[@]}" &
SIM=$!
sleep 3   # Simulator zuerst, sonst sucht das Panel nach der echten Kamera
python3 "$REPO_DIR/panel/panel.py" --port 8080 --autostart --karte sim &
PANEL=$!
trap 'kill -TERM $PANEL $SIM 2>/dev/null; wait $PANEL 2>/dev/null' EXIT
for _ in $(seq 40); do curl -s -o /dev/null http://localhost:8080/api/status && break; sleep 0.5; done
echo "Panel: http://localhost:8080  (START druecken, Kamera -> Simulation zeigt die Welt von oben)"
command -v xdg-open >/dev/null && xdg-open http://localhost:8080 >/dev/null 2>&1 &
echo "Beenden: Strg+C in diesem Fenster."
wait $PANEL
