# Browser / Anzeige des Panels

## Problem

Auf dem Jetson startet Chromium nicht (öffnet kurz, schließt sich wieder). Das ist ein bekanntes Jetson-Problem: Seit **snapd 2.70** brauchen Snap-Programme eine Kernel-Funktion (`CONFIG_SQUASHFS_XATTR`), die im Jetson-Kernel fehlt. Betroffen sind alle Snap-Browser (Chromium, Firefox).
Quellen: [JetsonHacks](https://jetsonhacks.com/2025/07/12/why-chromium-suddenly-broke-on-jetson-orin-and-how-to-bring-it-back/), [NVIDIA-Forum](https://forums.developer.nvidia.com/t/chromium-other-browsers-not-working-after-flashing-or-updating-heres-why-and-quick-fix/338891).

## Lösungen (alle in `scripts/browser_installieren.sh`, fragt vor jedem Schritt)

1. **Eigenes Panel-Fenster (empfohlen)**: `sudo apt install python3-gi gir1.2-webkit2-4.1`. Danach öffnet `scripts/panel.sh` das Panel in einem eigenen Vollbild-Fenster (`panel/fenster.py`), ganz ohne Browser. Fenster schließen = alles aus, der Roboter hält an. In der VM getestet (Ubuntu 24.04, WebKit 4.1).
2. **Chromium reparieren**: snapd auf 2.68.5 zurücksetzen und festhalten:
   ```bash
   sudo snap revert snapd
   # falls das nicht geht:
   snap download snapd --revision=24724
   sudo snap ack snapd_24724.assert
   sudo snap install snapd_24724.snap
   # danach immer:
   sudo snap refresh --hold snapd
   ```
3. **GNOME Web (Epiphany)** als normales Paket: `sudo apt install epiphany-browser`.

Ist apt blockiert: `sudo systemctl stop packagekit`.

## Vom Laptop

Laptop-Zugriff ist standardmäßig an (ausschalten: Panel → System). Die Adresse steht dort (und oben in der Kopfzeile), z. B. `http://10.0.12.62:8080`. Sie wird jedes Mal neu ermittelt, ändert sich also mit, wenn die VLANs umgestellt werden.

Das Live-Bild wird **Bild für Bild** geholt: Das nächste Bild wird erst angefordert, wenn das vorige angekommen ist. Vorher wurde ein Videostrom geschickt, der sich in langsamem WLAN aufgestaut hat (daher die starke Verzögerung).
