# Glossar

| Begriff | Erklärung |
|---|---|
| **ROS 2** | „Robot Operating System“. Kein Betriebssystem, sondern ein Baukasten: Programme schicken sich Nachrichten. Wir nutzen die Version **Humble** auf Ubuntu 22.04. |
| **Node** | Ein ROS-Programm, z. B. Linienfolger, KI-Zentrale, Kartograf. |
| **Topic** | Benannter Nachrichtenkanal, z. B. `/cmd_vel` (Fahrbefehle), `/scan0` (LiDAR). Programme veröffentlichen (publish) oder abonnieren (subscribe). |
| **Domain-ID** | Kanalnummer für ROS. Nur Programme mit derselben Nummer hören sich. Roboter: 30, Simulation: 77. Siehe [Roboter und Netz](Roboter-und-Netz). |
| **micro-ROS-Agent** | Verbindet das Motorboard (Mikrocontroller) mit ROS auf dem Jetson. Startet bei Yahboom automatisch. |
| **Jetson Orin** | Kleiner Computer von NVIDIA mit Grafikchip, rechnet auf dem Roboter alles. |
| **LiDAR** | Laser-Abstandsmesser, der sich dreht und rundherum misst. Der M3 Pro hat zwei (`/scan0`, `/scan1`), diagonal an zwei Ecken. |
| **Tiefenkamera** | Kamera, die zu jedem Bildpunkt den Abstand misst. Sieht auch flache Dinge unter der LiDAR-Ebene. |
| **IMU / Lagesensor** | Misst Drehung und Beschleunigung (`/imu/data_raw`). |
| **Odometrie** | Weg und Geschwindigkeit aus den Radzählern (`/odom_raw`). Wird mit der Zeit ungenau. |
| **Mecanum-Räder** | Räder mit schrägen Rollen, damit kann der Roboter auch seitwärts fahren. Rutschen in Kurven etwas. |
| **Watchdog** | Aufpasser-Zeitschaltung: kommt eine Zeit lang kein Befehl, hält das Board an. Unsere Zeit (0,3 s) ist noch nicht gemessen. |
| **Notbremse** | Etwas näher als 12 cm am LiDAR: sofort STOPP, ohne dass die KI gefragt wird. |
| **Fahrschlauch** | Der Streifen (30 cm breit) entlang der Linie, den der Roboter wirklich überfährt. Nur dort zählt etwas als Hindernis. |
| **Draufsicht** | Kamerabild umgerechnet, als würde man von oben auf den Boden schauen (1 Pixel = 4 mm). |
| **YOLO** | Fertiges neuronales Netz zur Objekterkennung (80 Dinge, z. B. Person, Auto, Ampel). Siehe [Eigenes Erkennungsmodell](Eigenes-Erkennungsmodell). |
| **ONNX / TensorRT** | Dateiformat für KI-Modelle (ONNX, läuft auf dem Prozessor) bzw. NVIDIAs schnelle Ausführung auf der Grafikkarte (TensorRT). |
| **Inverse Kinematik (IK)** | Vom Zielpunkt des Greifers rückwärts auf die Servowinkel rechnen. |
| **URDF** | Datei, die den Aufbau eines Roboters beschreibt (Glieder, Gelenke, Maße). |
| **Scan-Abgleich** | Den aktuellen LiDAR-Scan so lange schieben und drehen, bis er auf die Karte passt. So weiß der Roboter, wo er ist. |
| **Messfahrt** | Aufzeichnung aller Rohdaten einer Fahrt, zum Auswerten am Laptop. Siehe [Messfahrt aufzeichnen](Messfahrt-aufzeichnen). |
| **Panel** | Unsere Bedienoberfläche im Browser. Siehe [Bedienung mit dem Panel](Bedienung-mit-dem-Panel). |
| **MQTT** | Leichtes Nachrichtenprotokoll. Ein **Broker** (Server) verteilt Nachrichten an alle, die ein Topic abonniert haben. Damit sollen die Roboter ihre Daten an die Leitzentrale schicken. |
| **QoS / retained** | MQTT-Optionen: QoS 1 = Nachricht wird mindestens einmal zugestellt; retained = der Broker merkt sich die letzte Nachricht für neue Abonnenten. |
| **Grundbetrieb** | Das Ziel laut [Zieldefinition](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/zieldefinition-grundbetrieb.md): vier Roboter fahren gleichzeitig nach Verkehrsregeln, mit MQTT. |
| **GB-01 … GB-18** | Kennungen der Anforderungen in der Zieldefinition. |
| **A01 … A16** | Kennungen der Abnahmetests in der Zieldefinition. |
| **Bereiche A–E, O** | Aufteilung der Arbeit: A Sicherheit/Motor, B KI/Navigation, C Zustand/MQTT/Panel, D Tests/CI, E Geräte/Infrastruktur, O Orchestrierung. Siehe [Auftragsregister](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/auftraege/README.md). |
| **Branch / Commit / PR** | Siehe [Mitarbeiten mit Git](Mitarbeiten-mit-Git). |
| **CI** | Automatische Tests auf GitHub bei jedem Pull Request. Siehe [Testen ohne Roboter](Testen-ohne-Roboter#automatische-prüfung-auf-github-ci). |
