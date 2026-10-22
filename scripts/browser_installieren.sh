#!/bin/bash
# Macht eine Anzeige fuer das Panel moeglich. Fragt vor jeder Aenderung nach.
#
# Hintergrund: Auf Jetson-Geraeten starten Chromium und Firefox als Snap-Paket oft nicht mehr,
# seit snapd 2.70 (dem Jetson-Kernel fehlt CONFIG_SQUASHFS_XATTR). Quellen im Wiki, Seite Panel-Browser-auf-dem-Jetson.
set -u
frage() { read -r -p "$1 (j/n) " a; [ "$a" = "j" ]; }
apt_installieren() {
    # apt kann durch packagekit blockiert sein
    sudo apt-get install -y "$@" || { sudo systemctl stop packagekit; sudo apt-get install -y "$@"; }
}

echo "1) Eigenes Panel-Fenster (EMPFOHLEN, klein, kein Browser noetig)"
echo "   installiert: python3-gi und gir1.2-webkit2-4.1 (WebKit, ca. 50 MB)"
if frage "   Installieren?"; then
    sudo apt-get update
    apt_installieren python3-gi gir1.2-webkit2-4.1 || apt_installieren python3-gi gir1.2-webkit2-4.0
fi
echo
echo "2) Chromium reparieren (snapd auf Version 2.68.5 zuruecksetzen und festhalten)"
echo "   aendert das Snap-System. Nur noetig, wenn ihr Chromium/Firefox auch sonst benutzen wollt."
if frage "   Ausfuehren?"; then
    if ! sudo snap revert snapd; then
        cd /tmp && snap download snapd --revision=24724 && \
            sudo snap ack snapd_24724.assert && sudo snap install snapd_24724.snap
    fi
    sudo snap refresh --hold snapd   # sonst kommt das kaputte Update wieder
    echo "   Fertig. Chromium testen: chromium-browser"
fi
echo
echo "3) Browser 'GNOME Web' (Epiphany) als normales Paket (kein Snap)"
if frage "   Installieren?"; then
    apt_installieren epiphany-browser
fi
echo
echo "Fertig. Panel starten: scripts/panel.sh (oder Symbol im Dock)"
