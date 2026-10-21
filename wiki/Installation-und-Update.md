# Installation und Update

## Installieren (einmal pro Roboter)

Am **Bildschirm des Roboters** ein Terminal öffnen (nicht über SSH, weil das Skript ein Symbol ins Dock legt):

```bash
cd ~
git clone https://github.com/BBS-GuT/smartcity-roboter.git   # Projekt herunterladen
cd ~/smartcity-roboter
scripts/installieren.sh          # Panel-Symbol ins Dock, Roboter-Name, KI-Bibliothek
```

`installieren.sh` fragt einmal nach dem Roboternamen (RM01–RM04) und speichert ihn in `~/roboter_name`. Es bietet außerdem `onnxruntime` für die KI an. An Yahboom-Dateien und am Autostart ändert es nichts.

**Roboter mit altem Klon:** Zeigt `git remote -v` noch auf `davidheinrich73/smartcity-roboter`, auf das neue Repository umstellen:

```bash
cd ~/smartcity-roboter
git remote set-url origin https://github.com/BBS-GuT/smartcity-roboter.git
git remote -v          # prüfen
```

## Update

Panel → System → „Neueste Version holen“ (oder `scripts/update.sh`). Danach das Panel neu öffnen.

- Eigene Einstellungen in `config/lokal/` (Arm-Stellungen, LiDAR-Winkel, Kamera, Gelerntes) bleiben erhalten. Der Ordner ist nicht im Repository.
- **Nicht während einer Abnahme oder Messfahrt updaten.** Für Prüfungen muss feststehen, welcher Commit drauf ist (`git rev-parse --short HEAD`, auch im Panel-Systemcheck).

## Panel-Fenster ohne Browser

Auf dem Jetson startet Chromium oft nicht. Lösung: [Panel-Browser auf dem Jetson](Panel-Browser-auf-dem-Jetson).

## Danach

Vor der ersten Fahrt: [Erste Inbetriebnahme](Erste-Inbetriebnahme).
