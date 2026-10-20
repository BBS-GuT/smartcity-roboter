# Karte (Kartograf)

Dateien: `kartograf/kartograf.py` (ROS-Programm), `lib/kartierer.py` (Sensoren → Karte, Selbstprüfung), `lib/karte.py` (Karte und Scan-Abgleich), `lib/aufnahme.py` (Messfahrt aufzeichnen), `kartograf/abspielen.py` (Messfahrt am Laptop auswerten). Alles außer `kartograf.py` geht ohne ROS: `python3 tests/test_karte.py`.
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

1. **Mitrechnen**: Radgeschwindigkeit (`/odom_raw`) + Drehrate vom Lagesensor (`/imu/data_raw`). Wird mit der Zeit ungenau.
2. **Scan-Abgleich**: Jeder LiDAR-Scan wird ein paar Zentimeter und Grad hin und her geschoben, bis er am besten auf die bisherige Karte passt. Das korrigiert den Fehler aus 1 laufend. Passt es länger nicht, sucht er **weiter** (nach 1 s ±15 cm/±8°, nach 3 s ±30 cm/±15°, nach 8 s ±50 cm/±25°; erst grob, dann fein). Je weiter er sucht, desto besser muss es passen, sonst rastet er an einer falschen Stelle ein.
3. **Neue Fahrt**: Ist schon eine Karte da, wird der erste Scan in allen Drehungen über die ganze Karte geschoben (globale Suche, unter 1 s). Erst wenn die Stelle **eindeutig** passt, wird weiter eingetragen. Vorher steht im Panel "suche Position in der Karte …".

**Reichweite:** Der T-mini Plus misst bis 12 m. Verwendet werden Punkte bis 8 m (`max_reichweite`, früher 4 m). In einem großen Raum mit wenigen Dingen in der Nähe sind die fernen Wände oft das Einzige, woran der Abgleich die Drehung sicher erkennt.

**Zwei LiDARs:** Die beiden LiDARs sitzen diagonal versetzt an zwei Ecken (Yahbooms Unterlagen widersprechen sich, welcher an welcher: Kurs „hinten links = /scan0, vorne rechts = /scan1“, Produktseite „vorne links und hinten rechts“). Werden beide Scans so zusammengelegt, als säßen sie in der Mitte, passt die Karte nie ganz, und sie dreht sich mit jeder Runde weiter. Darum baut nur der erste LiDAR (`scan_topics[0]`) die Karte. Den genauen Einbau des zweiten lernt der Kartograf selbst, indem er dessen Scans auf die Karte schiebt (25 passende Messungen, die wenig streuen). Klappt das lange nicht, sucht er einmal sehr weit (±40 cm, ganz herum), z. B. wenn der zweite LiDAR an der gegenüberliegenden Ecke sitzt oder „vorne“ ganz anders liegt. Erst danach zählen seine Punkte mit. Das Ergebnis wird mit der Karte gespeichert (`einbau` in `karte.npz`) und steht im Panel unter der Karte, z. B. „LiDAR /scan1: Einbau gelernt: −24,0 / −20,0 cm, +0,0 Grad“.

**Zeitpunkt:** Jeder Scan wird mit der Position zu **seiner Messzeit** abgeglichen. Dafür nimmt der Kartograf die **Zeitstempel** der Nachrichten, nicht die Ankunftszeit: Auf einem ausgelasteten Roboter kommen Odometrie und Lagesensor oft gesammelt an (mehrere auf einmal). Mit der Ankunftszeit ginge dabei Strecke und Drehung verloren. Je Topic prüft er, ob die Stempel brauchbar sind (Panel/Abspielen: „synchron“, „eigene Uhr“ oder „Ankunftszeit“). Ohne Stempel verteilt er gesammelte Nachrichten gleichmäßig. Ein Scan wird erst abgeglichen, wenn die Odometrie bis zu seiner Messzeit da ist. Jeder Scan wird nur einmal verwendet. Eingetragen wird nur, wenn der Abgleich sicher passt, oder in neuem Gebiet.

**Scan entzerren:** Ein LiDAR misst nicht alles gleichzeitig. Bei 6 Hz dauert eine Umdrehung 0,17 s. In einer Kurve hat sich der Roboter dabei schon ein paar Grad gedreht. Meldet der LiDAR `time_increment` oder `scan_time` (oder ist `scan_dauer` eingestellt), wird jeder Strahl auf seine Messzeit zurückgerechnet.

**Jede Fahrt macht die Karte genauer:** Jede Messung macht eine Zelle "sicherer". Was öfter gesehen wird, wird fester. Was nur einmal im Weg stand (z. B. eine Person), verblasst wieder. Das Bodenfoto wird gemittelt, die 3D-Punkte werden gezählt (erst ab 2 Messungen angezeigt).

**Bodenfoto:** Jedes Kamerabild wird mit der Position **zur Aufnahmezeit** eingetragen (Zeitstempel des Bildes, Bilder kommen oft 0,3 s und mehr zu spät), nur wenn der Scan-Abgleich gerade sicher ist und sich der Roboter nicht schnell dreht. Vorher wurde die Position beim Auswerten genommen: In Kurven lagen die Bildstücke dann fächerförmig verdreht.

**Umschauen:** Steht `umschauen_auto:=true`, bittet der Kartograf die KI, kurz anzuhalten und mit der Kamera nach links und rechts zu schauen. Das passiert höchstens alle 1,5 m und nur dort, wo das Bodenfoto noch Lücken hat. Im Panel gibt es dafür auch einen Knopf. Die KI macht das nur während der Fahrt, nur wenn der Arm freigegeben ist und die Posen "Blick links/rechts" da sind. Am Zebrastreifen schaut sie sowieso.

## Selbstprüfung und Selbstkalibrierung

Auf dem echten Roboter ist vieles **ungeprüft**: wohin „vorne“ bei den LiDARs zeigt, in welche Richtung sie die Winkel zählen, ob der Lagesensor richtig herum misst, ob `/odom_raw` Geschwindigkeiten liefert. Jeder dieser Fehler lässt die Karte wegdrehen. Darum prüft der Kartograf selbst:

| Was | Wie | Was passiert |
|---|---|---|
| Lagesensor-Nullpunkt | im Stand (Räder sagen „steht“) | wird abgezogen |
| Lagesensor-Skala und -Nullpunkt (auch ohne Stand) | Drehung zwischen zwei sicheren Abgleichen gegen die Messung des Lagesensors (Ausgleichsrechnung über viele Proben) | wird angewendet, Panel zeigt z. B. „Lagesensor x0,971“ |
| Lagesensor dreht andersherum oder misst grob falsch | zwei Scans werden ohne Karte aufeinander geschoben (weite Suche): dreht der Scan genauso wie Lagesensor und Räder? | Vorzeichen/Skala korrigiert, Karte dieser Fahrt neu angefangen |
| LiDAR zählt die Winkel andersherum (gespiegelt) | wie oben: Scan dreht andersherum als Lagesensor **und** Räder | Scans werden gespiegelt, Karte dieser Fahrt neu angefangen, Hinweis im Panel |
| Wohin „vorne“ beim Haupt-LiDAR zeigt und wo er sitzt | fährt der Roboter laut Rädern geradeaus, fährt der LiDAR in **seine** Richtung „vorne“; dreht sich der Roboter, beschreibt der LiDAR einen Kreis um die Robotermitte (Hand-Auge-Kalibrierung) | wird beim Mitrechnen angewendet; die gemeldete Position ist die der Robotermitte. Bei mehr als 10° Hinweis „LiDAR-Richtung vermutlich falsch“ (die Hinderniserkennung braucht trotzdem das richtige `scan_front_deg`) |
| Räder messen zu kurz/lang | ebenfalls aus der Hand-Auge-Kalibrierung | wird angewendet |

**Standard seit 20.10.: AUS** (`selbst_kalibrieren: false`). Auf dem Roboter hatte sich die Karte nach dem Lernen verdreht/verdoppelt. Ohne Selbstkalibrierung rechnet die Karte mit den eingestellten Werten, die Selbstprüfung meldet Auffälligkeiten nur und stellt nichts um. Einschalten erst, wenn eine Messfahrt-Aufnahme mit `--setze selbst_kalibrieren=true` besser aussieht (siehe unten). Eingeschaltet wird das Gelernte mit der Karte gespeichert (`kalibrierung` in `karte.npz`) und gilt beim nächsten Start sofort. „Neue Karte“ fängt auch die Kalibrierung neu an.

**Im Panel** (Karte): „Scan-Abgleich sicher: 95 %“ (grün ab 80 %), „Gelernt: …“, die letzte Änderung und ein gelber Kasten mit Hinweisen, z. B. „LiDAR-Richtung vermutlich um +90 Grad falsch: scan_front_deg anpassen“ oder „Scan-Abgleich passt oft nicht … Bitte Messfahrt aufzeichnen“. Auf dem Dashboard erscheint dann „Karte: Hinweis, siehe Seite Karte“.

## Messfahrt aufzeichnen und schicken

Wenn die Karte auf dem Roboter nicht passt, kann man **ohne Roboter** nachsehen, warum. Dafür nimmt man eine Messfahrt auf:

1. Panel → **Karte** → **Messfahrt aufzeichnen**. (Der Kartograf muss laufen, er startet mit der KI.)
2. 2–3 Runden **normal fahren** (START), mit Kurven, Halten an der Ampel und Wenden. Am besten einmal kurz stehen bleiben (dann lernt der Lagesensor seinen Nullpunkt).
3. **Aufnahme stoppen** (gleicher Knopf, er zeigt Dauer und Größe). Nach 30 min oder 400 MB hört sie von selbst auf.
4. **Aufnahme herunterladen** (lädt die neueste) oder die Datei aus `karten/aufnahmen/` auf dem Roboter holen, z. B. `scp jetson@<roboter>:smartcity-roboter/karten/aufnahmen/*.jsonl.gz .`
5. Die Datei schicken (etwa 1–3 MB pro Minute, je nach Kamerabildern). Dazu am besten einen Satz, was man gesehen hat („Karte dreht sich in jeder Runde nach links“).

In der Datei steht: beide LiDAR-Scans (`/scan0`, `/scan1`), `/odom_raw`, `/imu/data_raw`, wohin der Arm geschickt wurde (`/arm6_joints`), was die KI über die Kamera meldet, die Position, die der Kartograf live gerechnet hat (`/karte/pose`), und 2 Kamerabilder je Sekunde (verkleinert). Alles mit Ankunftszeit und Zeitstempel, dazu die Einstellungen des Kartografen. Das Tiefenbild ist **nicht** dabei.

### Auswerten (am Laptop, ohne ROS)

```bash
python3 kartograf/abspielen.py smartcity_20261019_101500.jsonl.gz
python3 kartograf/abspielen.py aufnahme.jsonl.gz --setze scan_front_deg=[90,90]      # Einstellung ausprobieren
python3 kartograf/abspielen.py aufnahme.jsonl.gz --setze selbst_kalibrieren=false    # ohne Selbstkalibrierung
```

Es braucht nur Python 3 mit `numpy` und `opencv-python`. Die Aufnahme wird genau so durchgerechnet wie im Kartografen. Ausgabe:

- **Nachrichten:** wie oft (Hz), Lücken, ob sie gesammelt ankommen, Abstand Zeitstempel → Ankunft, ob `/odom_raw` Geschwindigkeiten hat, wie der Lagesensor liegt (Beschleunigung z positiv = richtig herum).
- **LiDAR:** Strahlen je Scan, Winkelschritt, `time_increment`/`scan_time`, welche Winkel meistens verdeckt sind (eigener Aufbau, näher als 20 cm).
- **Lokalisierung:** Anteil sicherer Abgleiche je Minute, Güte, längste unsichere Zeit.
- **Selbstkalibrierung:** Skala/Nullpunkt des Lagesensors, wohin „vorne“ beim Haupt-LiDAR zeigt und wo er sitzt, Scan-gegen-Scan-Drehung (+1 = passt, −1 = andersherum), was gelernt wurde.
- **Vergleich mit live:** wie weit die Position von dem abweicht, was der Roboter während der Fahrt gerechnet hat.
- Bilder: `karte.png` (Karte mit gefahrenem Weg) und `diagnose.png` (Güte des Abgleichs über die Zeit) im Ordner `<aufnahme>_auswertung/`.

## Was in der Simulation nachgestellt wurde (vorher/nachher)

Mit `sim/messfahrt.py` entsteht eine Messfahrt in der Simulationswelt, mit Fehlern, die es am echten Roboter geben kann (einzeln einschaltbar, Liste oben in der Datei). Sie wird wie eine echte Aufnahme mit `kartograf/abspielen.py` ausgewertet. Grundeinstellung: großer Raum (Wände 3–5 m weg, nur 2 Häuser in LiDAR-Höhe), 6 Hz mit Umlauf, 400 Strahlen, zweiter LiDAR 12 cm versetzt und 4° gedreht, Scans 50 ms verspätet, 4 Runden. „Vorher“ = Kartograf vor dieser Änderung (gleiche Aufnahme). Gemessen: Winkelfehler der Karte in Runde 2 und 4 (ausgerichtet am Anfang von Runde 2) und mittlerer Positionsfehler in Runde 4.

| Fehler | vorher: Winkel Runde 2 → 4 | vorher: Position Runde 4 | nachher: Winkel Runde 2 → 4 | nachher: Position Runde 4 |
|---|---|---|---|---|
| kein Zusatzfehler | -1,5° → -1,5° | 2,5 cm | -0,4° → -0,5° | 1,7 cm |
| Lagesensor misst 5 % zu viel | -1,5° → -1,4° | 2,6 cm | -0,3° → -0,3° | 2,1 cm |
| Lagesensor falsch herum | -39,9° → -38,8° | 141 cm | -0,4° → -0,8° | 2,5 cm |
| Lagesensor-Nullpunkt 1,7 °/s, kein Halt | -1,7° → -1,7° | 2,8 cm | -0,5° → -0,5° | 2,4 cm |
| `/odom_raw` ohne Geschwindigkeiten | -39,3° → -41,0° | 148 cm | -0,4° → -0,5° | 1,7 cm |
| LiDAR „vorne“ 15° falsch | -1,4° → -1,4° | 2,3 cm | -0,6° → -0,8° | 2,2 cm |
| LiDAR „vorne“ 90° falsch | -1,7° → -5,7° | 11 cm | -0,3° → -0,2° | 2,8 cm |
| LiDAR „vorne“ 180° falsch | -1,3° → -1,3° | 5,0 cm | -0,3° → -0,4° | 2,4 cm |
| LiDAR gespiegelt | -6,5° → -6,5° | 19 cm | -0,4° → -0,4° | 2,3 cm |
| Haupt-LiDAR 12/10 cm an der Ecke, Wenden | -2,1° → -2,1° | 14 cm | -0,7° → -0,7° | 1,5 cm |
| beide LiDARs an den Ecken, 90° verdeckt, Wenden | -1,7° → -1,7° | 16 cm | -0,8° → -1,0° | 2,0 cm |
| Odometrie/IMU kommen gesammelt (0,3 s) | -1,5° → -1,5° | 2,9 cm | -1,6° → -1,6° | 3,0 cm |
| gesammelt und ohne Zeitstempel | -1,5° → -1,5° | 2,9 cm | -3,7° → -3,9° | 6,4 cm |
| Halle 6 m, nur 1 Haus | -0,5° → -0,6° | 3,5 cm | -0,4° → -0,4° | 2,0 cm |
| Mecanum-Schlupf 15 % | -1,7° → -1,6° | 2,5 cm | -0,1° → +0,3° | 2,7 cm |
| Kombination (Ecken, verdeckt, IMU 3 %, Nullpunkt, Schlupf, Stau, Wenden) | +0,2° → +0,1° | 17 cm | -1,6° → -1,7° | 2,3 cm |

Ergebnis: Mit einem falsch herum messenden Lagesensor oder einer `/odom_raw` ohne Geschwindigkeiten verlor die alte Version völlig den Halt (Position über 1 m daneben). Zeigte „vorne“ beim Haupt-LiDAR um 90° falsch, drehte sich die Karte **jede Runde um etwa 2° weiter** (−1,7° → −5,0° → −5,7° in den Runden 2, 3, 4) – das passt zum Bild vom echten Roboter. Ein gespiegelter LiDAR und ein LiDAR an der Ecke ergaben bleibende Fehler von 14–19 cm. Nicht nachstellen ließ sich eine Drift durch zu viel/wenig gemessene Drehung oder Nullpunkt allein: Das hat schon der alte Scan-Abgleich aufgefangen. Neu: in allen Fällen 1,5–3 cm Positionsfehler und höchstens 1,7° Winkelfehler, der von Runde zu Runde gleich bleibt, außer „gesammelt und ohne Zeitstempel“: Das wird etwas **schlechter** (−3,9° statt −1,5°, die Position hängt bis zu 0,3 s hinterher). Welche Ursache es auf dem echten Roboter wirklich ist, zeigt erst eine Messfahrt.

Wichtig fürs Nachrechnen: Das Abspielen rechnet genau wie live (in der ROS-Simulation aufgenommen und abgespielt: unter 1 cm Unterschied). Dafür rechnet die Karte nicht mehr mit der Uhrzeit (früher: Trefferkarte jede Sekunde neu), sondern nach jedem dritten Eintragen.

Gegenprobe in der ROS-Simulation (Simulator + KI + Linienfolger + Kartograf, großer Raum, 6 Hz, Lagesensor 3 % daneben, je ca. 230 s): Lagesensor falsch herum: vorher Position in Runde 2–3 über 1,5 m daneben, nachher 1,6–1,7 cm (Runde 2–4). Haupt-LiDAR 12/10 cm an der Ecke: vorher 15 cm, nachher 1,7–2,4 cm. Achtung: Mit verdecktem Sektor direkt am LiDAR (Messungen bei 10 cm) fährt der Linienfolger in der Simulation gar nicht los, weil er das als Hindernis vor sich sieht (`obstacle_min_range` 0,08 m).

Auch die ROS-Simulation (`sim/simulator.py`) kann diese Fehler nachstellen (Parameter siehe [simulation.md](simulation.md)).

## Dateien (`karten/<name>/`, nicht im Repository)

| Datei | Inhalt |
|---|---|
| `karte.npz` | alles zum Weiterbauen (wird alle 30 s und beim Beenden gespeichert) |
| `karte.png` | 2D-Karte, 1 Pixel = 1 cm (Panel → Karte → "Bild herunterladen") |
| `karte.ply` | 3D-Karte (Panel → "3D herunterladen"), öffnen mit MeshLab oder CloudCompare |
| `karte.json`, `wolke.bin` | für das Panel |
| `karten/aufnahmen/*.jsonl.gz` | Messfahrten (eine Zeile JSON je Nachricht, gzip). Auch nach einem Absturz bis kurz davor lesbar |

**Neue Karte:** Panel → Karte → "Neue Karte". Die alte wird **umbenannt** (`karten/smartcity_alt_<Datum>`), nicht gelöscht. Was über die Sensoren gelernt wurde, gilt weiter. Vorher wird ihr **aktueller** Stand gespeichert. Das Panel meldet nur dann Erfolg, wenn der Kartograf genau diesen Auftrag bestätigt. Klappt etwas nicht (z. B. keine Schreibrechte), bleibt die alte Karte aktiv und das Panel zeigt den Grund.
Andere Karte (z. B. andere Stadt): Panel mit `scripts/panel.sh --karte werkstatt` starten.

## Einstellungen (in `config/lokal/roboter.yaml` unter `/**:` → `ros__parameters:`)

| Name | Standard | Bedeutung |
|---|---|---|
| `lidar_x` | 0.0 | LiDAR sitzt so weit vor der Robotermitte (m). Den genauen Ort lernt der Kartograf auch selbst |
| `scan_front_deg` | [0, 0] | Richtung „vorne“ je LiDAR (Panel → LiDAR). Für die Karte wird ein Fehler herausgerechnet, für die Hinderniserkennung nicht |
| `scan_spiegeln` | [false, false] | LiDAR zählt die Winkel im Uhrzeigersinn. Erkennt der Kartograf auch selbst (Hinweis im Panel) |
| `scan_dauer` | 0.0 | Dauer einer LiDAR-Umdrehung (s), nur falls der LiDAR weder `time_increment` noch `scan_time` meldet. 0 = nicht entzerren |
| `max_reichweite` | 8.0 | LiDAR-Punkte weiter weg nicht verwenden (m) |
| `selbst_kalibrieren` | false | gelernte Korrekturen (Lagesensor, Räder, LiDAR-Einbau, gespiegelt) anwenden |
| `aufnahme_bild_hz` | 2.0 | so viele Kamerabilder je Sekunde in die Messfahrt (0 = keine) |
| `arm_basis_x` | 0.05 | Drehachse von Servo 1 vor der Robotermitte (m), für Bilder beim Umschauen. Geschätzt |
| `kamera_*` | wie Linienfolger | Kameramaße, siehe `docs/linie.md` |
| `umschauen_auto` | false | KI um Umschauen bitten, wo die Karte Lücken hat |
| `odom_topic` / `imu_topic` | `/odom_raw` / `/imu/data_raw` | Quellen fürs Mitrechnen |

## Ungeprüft auf dem echten Roboter / offen

- **Welche Ursache es auf dem echten Roboter ist, ist nicht bewiesen.** Alle Zahlen oben stammen aus der Simulation. Eine echte Messfahrt (siehe oben) beantwortet das.
- Ob `/odom_raw` Geschwindigkeiten (`twist`) und eine Position liefert, und welche Einheiten/Vorzeichen `/imu/data_raw` hat. Der Kartograf kommt mit beidem zurecht (nimmt sonst die Positions-Unterschiede), meldet es aber nur in der Auswertung einer Messfahrt.
- Ob die Zeitstempel der Board-Nachrichten (micro-ROS) zur Uhr des Jetson passen. Wenn nicht, rechnet der Kartograf nur mit den Abständen der Stempel.
- Wie spät ein Scan ankommt, wenn das Board ihn erst beim Senden stempelt: Diese Verspätung kann der Kartograf nicht sehen (in der Simulation 50 ms, machte keine Probleme).
- Ob das Tiefenbild auf das Farbbild ausgerichtet ist. Sonst sind die Farben der 3D-Punkte verschoben.
- Ob der Armwinkel, den die KI für die Kamera meldet, stimmt (Bodenfoto beim Umschauen).
- **Kameramodell** (`kamera_hoehe`, `kamera_neigung`): Ein öffentliches URDF-Modell des M3 Pro hat die Armkamera in Fahrstellung bei ca. 31 cm Höhe, eingestellt sind 22 cm (ungeprüft). Ein falsches Modell verschiebt und verzerrt das Bodenfoto (in der Simulation: falsche Neigung 40° statt 32° → 13 % der Linienpixel über 5 cm daneben statt 6 %; falsche Höhe fällt bei Linien in Fahrtrichtung kaum auf), dreht die Karte aber nicht. Der Kartograf erkennt das **nicht** selbst. Mit einer Messfahrt kann man es ausprobieren: `--setze kamera_hoehe=0.31`.
- **Kein Schleifenschluss** (Loop Closure): Läuft die Position doch einmal weg, wird die Karte nicht nachträglich gerade gezogen. Dafür müsste man alle Scans aufheben und die Belegungskarte nach jeder Korrektur neu aufbauen. Das kostet viel Rechenzeit und Speicher auf dem Jetson und ist schwer stabil zu bekommen. Solange der Abgleich gegen die Karte sicher bleibt (das ist das Ziel der Selbstkalibrierung), schließt sich die Runde von selbst.
- Wie groß die echte SmartCity ist. Die Karte reicht ±8 m um den ersten Startpunkt.
