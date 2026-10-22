#!/bin/bash
# Startet die Kamera (Orbbec Dabai DCW2). Fenster offen lassen.
# RM02 22.10.: haeufig "KEINE KAMERABILDER" - die Kamera haengt an USB 2.0 und lieferte Farbe (30 fps, MJPG), Tiefe
# und Infrarot. Infrarot nutzt niemand, 15 fps Farbe reichen (Linie und KI). Weniger Daten ueber USB, weniger
# MJPG-Dekodieren auf dem Rechner. Eigene Werte gehen vor, z. B.: scripts/kamera.sh color_fps:=30
source "$(dirname "$0")/env.sh"
ros2 launch orbbec_camera dabai_dcw2.launch.py enable_ir:=false color_fps:=15 "$@"
