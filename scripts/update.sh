#!/bin/bash
# Holt die neueste Version aus dem Repository (git pull).
# Eigene Einstellungen (Arm-Posen, LiDAR-Winkel ...) stehen in config/lokal/ und bleiben erhalten.
# Fruehere Panel-Versionen haben direkt in config/arm.yaml und config/roboter.yaml gespeichert.
# Solche Aenderungen wuerden "git pull" blockieren. Darum werden sie vorher nach config/lokal/
# uebernommen, eine Sicherung angelegt und die beiden Dateien auf den Stand des Repositorys gesetzt.
cd "$(dirname "$0")/.." || exit 1
for datei in config/arm.yaml config/roboter.yaml; do
    if ! git diff --quiet -- "$datei" 2>/dev/null; then
        mkdir -p config/lokal
        sicherung="config/lokal/sicherung_$(date +%Y%m%d_%H%M%S)_$(basename "$datei")"
        cp "$datei" "$sicherung"
        python3 lib/einstellungen.py "$datei" || { echo "Uebernehmen hat nicht geklappt -> Abbruch"; exit 1; }
        git checkout -- "$datei"
        echo "Sicherung der alten Datei: $sicherung"
    fi
done
git pull
