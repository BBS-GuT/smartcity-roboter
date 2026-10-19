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
| `SIM_ANTRIEB=echt scripts/simulation.sh pruefen` | Antrieb wie in echt: Motoren reagieren später und träger, Mecanum-Räder rutschen in Kurven, Radzähler/Lagesensor nur 10× pro Sekunde (geschätzte Werte, siehe [linie.md](linie.md)). `SIM_TEMPO=0.35` dazu: schneller fahren |
| `python3 sim/linie_messen.py` | misst ohne ROS, wie genau der Linienfolger bei 0,15/0,25/0,35 m/s der Linie folgt (Tabelle, siehe [linie.md](linie.md)) |

Beenden: **Strg+C** im Terminal.

### Fehler wie am echten Roboter nachstellen (für die Karte)

Der Simulator hat Parameter für Fehler, die es am echten Roboter geben kann. Standard ist immer „kein Fehler“. Beispiel: `SIM_EXTRA="-p lidar0_einbau:=[0.0,0.0,90.0]" scripts/simulation.sh pruefen`.

| Parameter | Beispiel | Bedeutung |
|---|---|---|
| `halle`, `halle_rand`, `halle_haeuser` | `true`, `6.0`, `1` | großer Raum: Wände so weit (m) vom Spielfeld, nur so viele Häuser |
| `lidar0_einbau`, `lidar1_einbau` | `[0.12,0.10,90.0]` | wo der LiDAR sitzt (x, y in m) und wie weit „vorne“ gedreht ist (Grad) |
| `lidar_gespiegelt` | `true` | LiDAR zählt die Winkel andersherum |
| `lidar_hz`, `lidar_strahlen`, `lidar_umlauf` | `6.0`, `670`, `0.17` | Umdrehungen je s, Strahlen, Dauer einer Umdrehung (s) |
| `lidar_verdeckt` | `90.0` | so viel Grad verdeckt der eigene Aufbau je LiDAR |
| `lidar_verzoegerung` | `0.1` | Scan kommt so viel s später an |
| `imu_skala`, `imu_vorzeichen`, `gyro_bias` | `1.03`, `-1.0`, `0.03` | Lagesensor misst zu viel, falsch herum, Nullpunktfehler (rad/s) |
| `odom_twist`, `odom_rauschen` | `false`, `0.1` | `/odom_raw` ohne Geschwindigkeiten; Mecanum-Schlupf |
| `sensor_stau`, `stempel` | `0.3`, `null` | Odometrie/IMU kommen gesammelt an; Zeitstempel fehlen (`null`) oder andere Uhr (`versatz`) |

Schneller und ohne ROS geht es mit `python3 sim/messfahrt.py fahrt.jsonl.gz lidar0_einbau=0,0,90 imu_skala=1.03` und danach `python3 kartograf/abspielen.py fahrt.jsonl.gz` (siehe [karte.md](karte.md)). Das zeigt dann auch, wie weit die Karte je Runde wegdreht.

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
