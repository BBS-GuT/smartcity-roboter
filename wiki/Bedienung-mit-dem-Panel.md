# Bedienung mit dem Panel

Das Panel ist eine Webseite, die auf dem Roboter läuft (kleiner HTTP-Server in Python). Es zeigt alles an und hat die Knöpfe zum Fahren.

![Dashboard](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/bilder/panel_dashboard.jpg?raw=true)

## Starten und fahren

1. Im Dock auf **SmartCity Panel** klicken. Das startet Kamera, KI, Kartograf und das Panel.
2. **TEST**: Der Roboter zeigt alles an, fährt aber nicht. **Immer zuerst testen.**
3. **START**: Er fährt. **STOPP**: Er hält sofort an. Der STOPP-Knopf ist auf jeder Seite oben rechts.
4. Panel-Fenster schließen = Roboter hält an, alle Programme werden beendet.

**Not-Aus von außen** (z. B. per SSH): `scripts/stopp.sh`

**Sicherheit:** Neue Fahrprogramme immer zuerst im TEST-Modus. Eine Hand am STOPP, solange der Roboter fährt. Gamepad und Panel nicht gleichzeitig benutzen (beide senden an Motoren und Arm).

## Vom Laptop aus

Laptop-Zugriff ist standardmäßig **an**. Die Adresse steht im Panel oben in der Kopfzeile, z. B. `http://10.0.12.62:8080`. Sie wird bei jedem Aufruf neu ermittelt, weil sie sich mit den VLANs ändert.

**Achtung:** Solange der Zugriff an ist, kann **jeder im Netz**, der die Adresse kennt, den Roboter steuern. Ausschalten: Panel → System (oder `scripts/panel.sh --kein-netz`).

Tipp: Das Panel im Laptop-Browser ist besser als die Bildschirmfreigabe des Roboters. Die Fernsteuerung des Bildschirms (`gnome-remote-desktop`) kostet 50–130 % CPU.

## Die Seiten

| Seite | Inhalt |
|---|---|
| Dashboard | alles auf einen Blick: Entscheidung der KI, Karte, Kamera, LiDAR, Knöpfe, Abblendlicht-Schalter und Blinker-Anzeige ([Lichter](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/lichter.md)), Ereignisse. Passt auch auf den 7-Zoll-Bildschirm (1024×600) und aufs Handy |
| Karte | 2D/3D, verschieben, zoomen, herunterladen, Messfahrt aufzeichnen, neue Karte |
| Kamera / LiDAR | groß, LiDAR-Richtung „vorne“ einstellen |
| Arm | Servos einzeln bewegen, Posen speichern, Greifer einmessen, Greif-Lernen |
| Sensoren | Messrate, Bildalter, Quelle der Bewegung |
| System | Akku, IP-Adresse, Systemcheck, Update, Logs herunterladen, Ampel einstellen, Kartograf starten/stoppen |

| Karte (2D) | Karte (3D) |
|---|---|
| ![Karte 2D](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/bilder/panel_karte_2d.jpg?raw=true) | ![Karte 3D](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/bilder/panel_karte_3d.jpg?raw=true) |
| **LiDAR mit Fahrschlauch** | **Arm: Stellungen einlernen** |
| ![LiDAR](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/bilder/panel_lidar.jpg?raw=true) | ![Arm](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/bilder/panel_arm.jpg?raw=true) |

## Warum fährt er nicht?

Die KI schreibt bei jeder Entscheidung den Grund dazu. Er steht im Dashboard und in den Ereignissen, z. B. „Rote Ampel“, „KI antwortet nicht“, „KAMERABILDER ZU ALT“. Was die Meldungen bedeuten: [Fehlersuche](Fehlersuche).

Andere Karte (z. B. für einen anderen Raum): Panel mit `scripts/panel.sh --karte werkstatt` starten.
