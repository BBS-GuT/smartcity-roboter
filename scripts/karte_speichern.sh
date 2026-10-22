#!/bin/bash
# Speichert die aktuelle Karte ins Repository: maps/NAME.pgm + maps/NAME.yaml
# Aufruf: scripts/karte_speichern.sh smartcity
# karte_erstellen.sh muss dabei noch laufen.
source "$(dirname "$0")/env.sh"
NAME="${1:-smartcity}"
mkdir -p "$REPO_DIR/maps"

if ! ros2 topic list | grep -qx /map; then
    echo "Kein Topic /map. Laeuft scripts/karte_erstellen.sh?"; exit 1
fi
if [ -f "$REPO_DIR/maps/$NAME.yaml" ]; then
    read -r -p "maps/$NAME gibt es schon. Ueberschreiben? (j/n) " ok
    [ "$ok" = "j" ] || exit 1
fi

# Bild (.pgm) + Beschreibung (.yaml): das braucht spaeter die Navigation (nav2)
ros2 run nav2_map_server map_saver_cli -f "$REPO_DIR/maps/$NAME"

# Zusaetzlich den slam_toolbox-Zustand, damit man die Karte spaeter weiterbauen kann
if ros2 service list | grep -q /slam_toolbox/serialize_map; then
    ros2 service call /slam_toolbox/serialize_map slam_toolbox/srv/SerializePoseGraph \
        "{filename: '$REPO_DIR/maps/$NAME'}" > /dev/null && echo "slam_toolbox-Zustand gespeichert"
fi

ls -l "$REPO_DIR/maps/$NAME".*
echo
echo "Damit die anderen Roboter die Karte bekommen:"
echo "  cd $REPO_DIR && git add maps && git commit -m \"Karte $NAME\" && git push"
