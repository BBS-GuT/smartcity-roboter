# Messfahrt aufzeichnen und auswerten

Wenn die Karte auf dem Roboter nicht passt (dreht weg, doppelt, verschoben), kann man **ohne Roboter** nachsehen, warum. Dafür nimmt man eine Messfahrt auf und spielt sie am Laptop ab. Wie die Karte funktioniert und was die Ergebnisse bedeuten: [`docs/karte.md`](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/karte.md).

## Aufzeichnen (am Roboter)

1. Panel → **Karte** → **Messfahrt aufzeichnen**. (Der Kartograf muss laufen, er startet mit der KI.)
2. 2–3 Runden **normal fahren** (START), mit Kurven, Halten an der Ampel und Wenden. Am besten einmal kurz stehen bleiben (dann lernt der Lagesensor seinen Nullpunkt).
3. **Aufnahme stoppen** (gleicher Knopf, er zeigt Dauer und Größe). Nach 30 min oder 400 MB hört sie von selbst auf.
4. **Aufnahme herunterladen** (lädt die neueste) oder die Datei vom Roboter holen:
   ```bash
   scp jetson@<roboter>:smartcity-roboter/karten/aufnahmen/*.jsonl.gz .
   ```
5. Die Datei weitergeben (etwa 1–3 MB pro Minute). Dazu ein Satz, was man gesehen hat („Karte dreht sich in jeder Runde nach links“).

**Was drin ist:** beide LiDAR-Scans (`/scan0`, `/scan1`), `/odom_raw`, `/imu/data_raw`, Armbefehle (`/arm6_joints`), KI-Meldungen, die live gerechnete Position (`/karte/pose`) und 2 Kamerabilder je Sekunde (verkleinert). Alles mit Ankunftszeit und Zeitstempel, dazu die Einstellungen des Kartografen. Das Tiefenbild ist **nicht** dabei.

## Auswerten (am Laptop, ohne ROS)

Es braucht nur Python 3 mit `numpy` und `opencv-python`.

```bash
python3 kartograf/abspielen.py smartcity_20261019_101500.jsonl.gz
python3 kartograf/abspielen.py aufnahme.jsonl.gz --setze scan_front_deg=[90,90]      # Einstellung ausprobieren
python3 kartograf/abspielen.py aufnahme.jsonl.gz --setze selbst_kalibrieren=true     # mit Selbstkalibrierung
python3 kartograf/abspielen.py aufnahme.jsonl.gz --setze kamera_hoehe=0.31           # anderes Kameramodell
```

Die Aufnahme wird genau so durchgerechnet wie im Kartografen. Ausgabe:

- **Nachrichten:** wie oft (Hz), Lücken, ob sie gesammelt ankommen, Abstand Zeitstempel → Ankunft, ob `/odom_raw` Geschwindigkeiten hat, wie der Lagesensor liegt (Beschleunigung z positiv = richtig herum).
- **LiDAR:** Strahlen je Scan, Winkelschritt, `time_increment`/`scan_time`, welche Winkel meistens verdeckt sind (eigener Aufbau, näher als 20 cm).
- **Lokalisierung:** Anteil sicherer Abgleiche je Minute, Güte, längste unsichere Zeit.
- **Selbstkalibrierung:** Skala/Nullpunkt des Lagesensors, wohin „vorne“ beim Haupt-LiDAR zeigt und wo er sitzt, Scan-gegen-Scan-Drehung (+1 = passt, −1 = andersherum), was gelernt wurde.
- **Vergleich mit live:** wie weit die Position von dem abweicht, was der Roboter während der Fahrt gerechnet hat.
- Bilder `karte.png` (Karte mit gefahrenem Weg) und `diagnose.png` (Güte des Abgleichs über die Zeit) im Ordner `<aufnahme>_auswertung/`.

## Ohne Roboter üben

Mit `python3 sim/messfahrt.py fahrt.jsonl.gz lidar0_einbau=0,0,90 imu_skala=1.03` entsteht eine künstliche Messfahrt mit absichtlichen Fehlern, die man genauso auswertet (Liste der Fehler oben in `sim/messfahrt.py`).
