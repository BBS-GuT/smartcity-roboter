# Karte (Kartograf)

Dateien: `kartograf/kartograf.py` (ROS-Programm), `lib/karte.py` (Rechnung, ohne ROS testbar: `python3 tests/test_karte.py`).
Der Kartograf **fährt nicht** und bewegt den Arm nicht. Er startet automatisch mit der KI (Panel → System → Kartograf starten/stoppen).

## Was in der Karte steckt (aus welchem Sensor)

| Schicht | Sensor | Inhalt |
|---|---|---|
| Belegung | erster LiDAR, der zweite sobald sein Einbau gelernt ist | 2D-Gitter, 2 cm je Zelle: frei / Wand oder Hindernis / unbekannt |
| Bodenfoto | Kamera | Foto des Bodens von oben (1 cm je Pixel): Linien, Zebrastreifen |
| 3D-Punkte | Tiefenkamera | alles, was aus dem Boden ragt (Würfel, Schilder, Figuren), als 2-cm-Würfelchen mit Farbe |
| Wände in 3D | LiDAR | belegte Zellen als 14 cm hohe Säulen |
| Marker | KI | Ampel, Stoppschild, Zebrastreifen, Einbahnstraße, Hindernis (nur aktuelle Fahrt) |

## Wo bin ich? (Lokalisierung)

1. **Mitrechnen**: Radgeschwindigkeit (`/odom_raw`) + Drehrate vom Lagesensor (`/imu/data_raw`). Wird mit der Zeit ungenau. In der Simulation sind es nach einer Runde 18 cm Fehler.
2. **Scan-Abgleich**: Jeder LiDAR-Scan wird ein paar Zentimeter und Grad hin und her geschoben, bis er am besten auf die bisherige Karte passt. Das korrigiert den Fehler aus 1 laufend. In der Simulation bleibt der Fehler unter 6 cm, im Mittel 1,3–2,9 cm.
3. **Neue Fahrt**: Ist schon eine Karte da, wird der erste Scan in allen Drehungen über die ganze Karte geschoben (globale Suche, unter 1 s). Erst wenn die Stelle **eindeutig** passt, wird weiter eingetragen. Vorher steht im Panel "suche Position in der Karte …".

**Zwei LiDARs:** Die beiden LiDARs sitzen diagonal versetzt an zwei Ecken (Yahbooms Unterlagen widersprechen sich, welcher an welcher: Kurs „hinten links = /scan0, vorne rechts = /scan1“, Produktseite „vorne links und hinten rechts“). Die Richtung „vorne“ stellt man im Panel nur ungefähr ein, und wo genau sie sitzen, weiß der Kartograf nicht. Werden beide Scans so zusammengelegt, als säßen sie in der Mitte, passt die Karte nie ganz, und sie **dreht sich mit jeder Runde weiter**. In der Simulation mit 12 cm Versatz und 4° Drehung: Winkelfehler 2,7° → 4,9° → 5,2° in den Runden 1, 3 und 5. Darum baut jetzt nur der erste LiDAR (`scan_topics[0]`) die Karte. Den genauen Einbau des zweiten lernt der Kartograf selbst, indem er dessen Scans auf die Karte schiebt. Dafür braucht es 25 passende Messungen, die wenig streuen. Erst danach zählen seine Punkte mit. Das Ergebnis wird mit der Karte gespeichert (`einbau` in `karte.npz`). Im Panel steht es unter der Karte, z. B. „LiDAR /scan1: Einbau gelernt: −12,0 / +0,0 cm, +4,0 Grad“. In der Simulation bleibt der Fehler dann über 5 Runden bei etwa 1°.

**Zeitpunkt:** Jeder Scan wird mit der Position zu **seiner Messzeit** abgeglichen, nicht mit der beim Auswerten (bis zu 0,5 s später). Jeder Scan wird nur einmal verwendet. Eingetragen wird nur, wenn der Abgleich sicher passt, oder in neuem Gebiet. Sonst würde die Karte den Fehler mitnehmen.

**Jede Fahrt macht die Karte genauer:** Jede Messung macht eine Zelle "sicherer". Was öfter gesehen wird, wird fester. Was nur einmal im Weg stand (z. B. eine Person), verblasst wieder. Das Bodenfoto wird gemittelt, die 3D-Punkte werden gezählt (erst ab 2 Messungen angezeigt).

**Umschauen:** Steht `umschauen_auto:=true`, bittet der Kartograf die KI, kurz anzuhalten und mit der Kamera nach links und rechts zu schauen. Das passiert höchstens alle 1,5 m und nur dort, wo das Bodenfoto noch Lücken hat. Im Panel gibt es dafür auch einen Knopf. Die KI macht das nur während der Fahrt, nur wenn der Arm freigegeben ist und die Posen "Blick links/rechts" da sind. Am Zebrastreifen schaut sie sowieso.

## Dateien (`karten/<name>/`, nicht im Repository)

| Datei | Inhalt |
|---|---|
| `karte.npz` | alles zum Weiterbauen (wird alle 30 s und beim Beenden gespeichert) |
| `karte.png` | 2D-Karte, 1 Pixel = 1 cm (Panel → Karte → "Bild herunterladen") |
| `karte.ply` | 3D-Karte (Panel → "3D herunterladen"), öffnen mit MeshLab oder CloudCompare |
| `karte.json`, `wolke.bin` | für das Panel |

**Neue Karte:** Panel → Karte → "Neue Karte". Die alte wird **umbenannt** (`karten/smartcity_alt_<Datum>`), nicht gelöscht.
Andere Karte (z. B. andere Stadt): Panel mit `scripts/panel.sh --karte werkstatt` starten.

## Einstellungen (in `config/lokal/roboter.yaml` unter `/**:` → `ros__parameters:`)

| Name | Standard | Bedeutung |
|---|---|---|
| `lidar_x` | 0.0 | LiDAR sitzt so weit vor der Robotermitte (m). **Nachmessen** |
| `arm_basis_x` | 0.05 | Drehachse von Servo 1 vor der Robotermitte (m), für Bilder beim Umschauen. Geschätzt |
| `kamera_*` | wie Linienfolger | Kameramaße, siehe `docs/linie.md` |
| `umschauen_auto` | false | KI um Umschauen bitten, wo die Karte Lücken hat |
| `odom_topic` / `imu_topic` | `/odom_raw` / `/imu/data_raw` | Quellen fürs Mitrechnen |

## Ungeprüft auf dem echten Roboter

- Ob `/odom_raw` Geschwindigkeiten (`twist`) liefert. Wenn nicht, rechnet der Kartograf nur mit IMU + Scan-Abgleich. Das reicht bei langsamer Fahrt, beim schnellen Drehen wird es ungenau.
- Ob das Tiefenbild auf das Farbbild ausgerichtet ist. Sonst sind die Farben der 3D-Punkte verschoben.
- Wo der erste LiDAR genau sitzt (`lidar_x`). Ein Versatz verschiebt nur die ganze Karte, sie dreht sich davon nicht. Den zweiten lernt der Kartograf selbst.
- Ob der Einbau des zweiten LiDARs auf dem echten Roboter sauber gelernt wird (in der Simulation: ja, auf 1 mm / 0,1° genau).
- Wie groß die echte SmartCity ist. Die Karte reicht ±8 m um den ersten Startpunkt.
