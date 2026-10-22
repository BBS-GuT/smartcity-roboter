#!/bin/bash
# Einmalig auf jedem Roboter ausfuehren (nach git clone):  scripts/installieren.sh
# Legt das Desktop-Symbol "SmartCity Panel" an. Aendert nichts an Yahboom-Dateien oder am Autostart.
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
chmod +x "$REPO_DIR"/scripts/*.sh

# Roboter-Namen merken (alle heissen "yahboom", so kann man sie unterscheiden)
if [ ! -f "$HOME/roboter_name" ]; then
    read -r -p "Welcher Roboter ist das? (z. B. RM02, leer = ueberspringen) " NAME
    [ -n "$NAME" ] && echo "$NAME" > "$HOME/roboter_name"
fi

INHALT="[Desktop Entry]
Type=Application
Name=SmartCity Panel
Comment=Startet Kamera, KI und das Control-Panel
Exec=bash -c '\"$REPO_DIR/scripts/panel.sh\"; echo; read -r -p \"Enter zum Schliessen\"'
Icon=applications-engineering
Terminal=true
Categories=Utility;"

# 1) Programm-Menue (Ubuntu: Super-Taste druecken, "SmartCity" tippen). Braucht kein "trusted".
MENUE="$HOME/.local/share/applications/smartcity-panel.desktop"
mkdir -p "$(dirname "$MENUE")"
echo "$INHALT" > "$MENUE"
echo "Im Programm-Menue angelegt: $MENUE"

# 2) Symbol auf dem Desktop
DESKTOP=$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")
mkdir -p "$DESKTOP"
DATEI="$DESKTOP/SmartCity-Panel.desktop"
echo "$INHALT" > "$DATEI"
chmod +x "$DATEI"

# Als "vertrauenswuerdig" markieren. gio braucht die Desktop-Sitzung; ueber SSH ist die
# nicht automatisch bekannt -> Adresse der Sitzung des Benutzers selbst angeben.
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}"
if gio set "$DATEI" metadata::trusted true 2>/dev/null; then
    echo "Desktop-Symbol angelegt und als vertrauenswuerdig markiert (GNOME): $DATEI"
else
    echo "Desktop-Symbol angelegt: $DATEI"
    echo "  Konnte es NICHT als vertrauenswuerdig markieren (keine Desktop-Sitzung gefunden)."
    echo "  -> Dieses Skript einmal direkt am Roboter-Bildschirm im Terminal ausfuehren."
fi
# Xfce-Desktop merkt sich stattdessen eine Pruefsumme der Datei
gio set "$DATEI" metadata::xfce-exe-checksum "$(sha256sum "$DATEI" | cut -d' ' -f1)" 2>/dev/null
echo "Desktop-Umgebung: ${XDG_CURRENT_DESKTOP:-unbekannt (ueber SSH nicht sichtbar)}"
echo "Erscheint das Symbol noch als 'nicht vertrauenswuerdig': einmal ab- und wieder anmelden."

# 3) Ins Dock (Leiste am Bildschirmrand) legen. Start dort braucht KEIN "trusted",
#    das ist der zuverlaessigste Weg unter Ubuntu/GNOME.
if command -v gsettings >/dev/null; then
    ALT=$(gsettings get org.gnome.shell favorite-apps 2>/dev/null)
    if [ -n "$ALT" ] && ! echo "$ALT" | grep -q smartcity-panel.desktop; then
        read -r -p "SmartCity Panel ins Dock (Leiste am Rand) legen? (j/n) " ok
        if [ "$ok" = "j" ]; then
            NEU=$(python3 -c "import ast,sys; l=ast.literal_eval(sys.argv[1].replace('@as ','')); print(l+['smartcity-panel.desktop'])" "$ALT")
            gsettings set org.gnome.shell favorite-apps "$NEU" && echo "Im Dock angelegt."
        fi
    fi
fi

# Kurzer Check, ob alles da ist
python3 -c "import cv2, yaml" 2>/dev/null && echo "Python-Pakete: ok" || echo "WARNUNG: python3-opencv oder python3-yaml fehlt"
[ -f "$REPO_DIR/models/yolov8n.onnx" ] && echo "KI-Modell: ok" || echo "KI-Modell fehlt (models/yolov8n.onnx)"

# onnxruntime fuehrt das KI-Modell aus (OpenCV 4.5 von Ubuntu 22.04 kann es nicht)
if python3 -c "import onnxruntime" 2>/dev/null; then
    echo "onnxruntime: ok"
else
    read -r -p "onnxruntime fehlt (fuer die KI-Erkennung). Jetzt fuer diesen Benutzer installieren? (j/n) " ok
    if [ "$ok" = "j" ]; then
        # numpy<2: sonst funktioniert cv_bridge von ROS Humble nicht mehr
        pip3 install --user "onnxruntime<1.20" "numpy<2"
    fi
fi
echo; echo "Anzeige fuer das Panel (Chromium geht auf dem Jetson oft nicht): scripts/browser_installieren.sh"
