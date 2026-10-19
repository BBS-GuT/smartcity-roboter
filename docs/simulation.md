# Simulation (ohne Roboter, z. B. in einer VM auf dem Laptop)

Der Simulator ersetzt Roboter, Kamera, Tiefenkamera, beide LiDARs und den Arm. KI, Linienfolger, Kartograf und Panel laufen **unverändert** wie auf dem Roboter. Die Welt: ein Rundkurs mit Ampel, Zebrastreifen samt Fußgänger, Holzwürfel, Stoppschild, Einbahnstraße und Häusern.

Die Simulation nutzt eine **eigene Domain-ID (77)**. Die Roboter nutzen 30. So steuert die Simulation nie aus Versehen einen echten Roboter, auch nicht im selben WLAN.

## VM einrichten (einmalig)

1. **VirtualBox** (kostenlos) oder VMware auf dem Laptop installieren.
2. **Ubuntu 22.04 Desktop** herunterladen (ubuntu.com, Version **22.04**, nicht 24.04: ROS 2 Humble gibt es fertig nur für 22.04).
3. Neue VM anlegen: mindestens **4 Prozessorkerne**, **8 GB RAM**, **30 GB** Festplatte. Netzwerk: **NAT** (Standard). Damit ist die VM vom Roboter-Netz getrennt.
4. Ubuntu in der VM installieren, dann im Terminal:
   ```bash
   sudo apt install -y git
   git clone https://github.com/davidheinrich73/smartcity-roboter.git
   cd smartcity-roboter
   scripts/simulation.sh einrichten     # installiert ROS 2 Humble + Python-Pakete, fragt vorher
   ```
   Das dauert je nach Internet 5–15 Minuten.

## Starten

| Befehl | Was passiert |
|---|---|
| `scripts/simulation.sh` | Simulator + Panel. Der Browser geht auf `http://localhost:8080`. **START** drücken. Unter **Kamera → „Simulation“** sieht man die Welt von oben: grün = Roboter, Pfeil = vorne, orange = Arm, roter Punkt = Greifer hält etwas, blau = gefahrene Spur |
| `scripts/simulation.sh pruefen` | fährt gut 2 Minuten ohne Panel und prüft alles automatisch. Am Ende steht `Alles in Ordnung.` oder welche Prüfung fehlgeschlagen ist |
| `scripts/simulation.sh schwer` | wie ohne Zusatz, aber mit Fehlern wie in echt: großer Raum statt Wände am Spielfeld, zweiter LiDAR 12 cm versetzt und 4° verdreht, Lagesensor misst 3 % zu viel, Scans kommen 0,1 s zu spät |
| `SIM_SCHWER=1 scripts/simulation.sh pruefen` | Prüfung mit diesen Fehlern |

Beenden: **Strg+C** im Terminal.

Die Logs stehen in `/tmp/sim_*.log` (Prüfen) bzw. `/tmp/panel_*.log` (mit Panel). Die Karte der Simulation liegt in `karten/sim/`.

## Was die Simulation kann und was nicht

- Kamera, Tiefe und LiDAR werden aus der Welt berechnet. YOLO erkennt die gemalten Schilder teilweise, die eigenen Erkennungen (LED, Achteck, Zebrastreifen) funktionieren.
- Der **Arm** wird nachgerechnet: Aus den Servowinkeln ergibt sich, wo der Greifer ist. Nur wenn er den Würfel trifft, ist er gegriffen. Die Arm-Maße (`sim/arm_sim.yaml`) sind **ausgedacht**. Auf dem Roboter rechnet Yahbooms Kinematik-Dienst (siehe [greifarm.md](greifarm.md)).
- Die Kamera dreht in der Simulation nur mit Servo 1 mit (Umschauen). Beim Greifen bleibt ihr Bild gleich, das ist in echt anders.
- Ohne Grafikkarte rechnet die KI auf dem Prozessor (ca. 150 ms je Bild bei 4 Kernen). Mit nur 1 Kern ist sie zu langsam: Dann übersieht sie z. B. das Schild „Einfahrt verboten“. In der VM also mindestens 4 Kerne geben.
- **Die Simulation ist nicht die Wirklichkeit.** Was hier klappt, muss auf dem Roboter trotzdem getestet werden.

## Probleme

| Meldung | Lösung |
|---|---|
| `ROS 2 nicht gefunden` | `scripts/simulation.sh einrichten` |
| `Dieses System ist Ubuntu 24.04 …` | VM mit Ubuntu 22.04 anlegen |
| Panel bleibt bei „KI startet …“ | 10–20 s warten (KI-Modell lädt). Sonst `/tmp/panel_ki.log` ansehen |
| Browser geht nicht von selbst auf | in der VM `http://localhost:8080` öffnen |
| Panel vom Laptop selbst (außerhalb der VM) öffnen | in VirtualBox unter Netzwerk → Port-Weiterleitung: Host-Port 8080 → Gast-Port 8080, dann am Laptop `http://localhost:8080` |
