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

Updates nur im Wartungsfenster durchführen: zuerst TEST/Fahrt mit STOPP beenden und alle betroffenen Anwendungsprozesse geordnet beenden. Den Ablauf [Quellstand und Anwendungsstart](Startprotokoll#quellstand-und-anwendungsstart) vollständig befolgen. Das Update erfolgt über `scripts/update.sh` bei beendeten Anwendungen. Wurde stattdessen Panel → System → „Neueste Version holen“ bei laufendem Panel benutzt, anschließend ebenfalls alle betroffenen Prozesse einschließlich Panelserver, KI, Kartograf und Linienfolger geordnet beenden und über den dokumentierten Startweg neu starten; getrennt gestartete Instanzen berücksichtigen. Nur die Browserseite neu zu öffnen oder zu laden reicht nicht. Bei alten oder unklaren Prozessen keinen TEST und keine Fahrt beginnen.

- Eigene Einstellungen in `config/lokal/` (Arm-Stellungen, LiDAR-Winkel, Kamera, Gelerntes) bleiben erhalten. Der Ordner ist nicht im Repository.
- **Nicht während einer Abnahme oder Messfahrt updaten.** Erst nach bestätigtem Anwendungsneustart den vollständigen Commit und sauberen Arbeitsbaum gemäß [Startprotokoll](Startprotokoll#quellstand-und-anwendungsstart) nachweisen und den passenden Kalibrier- oder Fahrcheck ausführen. Der Panel-Systemcheck allein genügt nicht; ein Roboter-Neustart ist dafür nicht erforderlich.

## Panel-Fenster ohne Browser

Auf dem Jetson startet Chromium oft nicht. Lösung: [Panel-Browser auf dem Jetson](Panel-Browser-auf-dem-Jetson).

## Danach

Vor der ersten Fahrt: [Erste Inbetriebnahme](Erste-Inbetriebnahme).
