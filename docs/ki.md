# KI-Zentrale

## Aufbau

```
 Kamera ──► Kamera-KI (YOLO) ──┐
            + Ampelfarbe        │
            + Ersatz: LED, Form │
            + Zebrastreifen     │
            + Einfahrt verboten │
 LiDAR (Fahrschlauch) ─────────►├──► Entscheider ──► /ki/befehl ──► Linienfolger ──► Motoren
 Tiefenkamera (Bodenmodell) ───┘    (ki/entscheider.py)                (lenkt nach Linie, führt Manöver aus,
                                     + Abläufe (ki/ablaeufe.py)          eigene Notbremse)
                                         │
                                         └──► Arm (nur wenn freigegeben, nur im Stand, nur während der Fahrt)
```

- **ki/zentrale.py**: ROS-Programm. Wertet die Sinne aus und schickt 10× pro Sekunde einen Befehl mit Grund.
- **ki/entscheider.py**: Entscheidungslogik, ohne ROS testbar (`python3 tests/test_entscheider.py`).
- **ki/ablaeufe.py**: Abläufe aus mehreren Schritten: Zebrastreifen, Wenden, Wegräumen, Umschauen.
- **line_follower/line_follower.py**: lenkt nach der schwarzen Linie, fährt nur, wenn die KI es erlaubt, und führt deren Manöver aus. Manöver sind z. B. wenden oder zum Greifen ausrichten. Sie sind begrenzt: max. 0,10 m/s vor, 0,08 m/s seitwärts, 1,2 rad/s drehen.

## Wie entscheidet die KI? (wichtigstes zuerst)

| # | Situation | Entscheidung |
|---|---|---|
| 1 | LiDAR: etwas näher als **12 cm** | **STOPP sofort, ohne KI-Prüfung** (Eigenschutz) |
| 2 | kein LiDAR oder keine Kamerabilder | STOPP (wer nichts sieht, fährt nicht) |
| – | ein Ablauf läuft (Zebrastreifen, Wenden, Wegräumen, Umschauen) | der Ablauf bestimmt, 1 und 2 gelten trotzdem |
| 3 | LiDAR (**im Fahrschlauch**, näher als **45 cm**) und/oder Tiefenkamera (etwas ragt aus der Fahrbahn, näher als 35 cm) | **STOPP, Kamera schaut genau hin**, dann wegräumen oder warten (siehe unten) |
| 4 | Kamera-KI sieht Person/Auto/… im Weg | STOPP |
| 6 | Schild **"Einfahrt verboten"** (2 Bilder hintereinander) | **wenden**: auf der Stelle drehen, bis die Linie wieder genau vorne liegt (gemessen mit dem Lagesensor, mind. 150°) |
| 7 | **Zebrastreifen** näher als 33 cm | anhalten, Kamera nach **links**, dann nach **rechts** drehen (Arm), zurück. Sieht er eine Person oder steht etwas am Zebrastreifen (LiDAR, ±30 cm seitlich): warten und neu schauen. Sonst weiter. Ohne Arm-Freigabe: anhalten und geradeaus schauen |
| 8 | Ampel rot oder gelb | STOPP, bis **grün** erkannt wird (oder die Ampel 4 s nicht mehr zu sehen ist) |
| 9 | Stoppschild (nah, d. h. groß im Bild) | 3 s halten, dann weiter. Dasselbe Schild löst erst wieder aus, wenn es 2 s weg war |


**Wenden** (Einbahnstraße) bricht ab und der Roboter bleibt stehen, wenn der Lagesensor nach 2,5 s keine Drehung meldet (IMU fehlt, falsch eingebaut, Räder blockiert) oder nach 7 s nicht fertig ist. Weiter geht es erst nach STOPP und neuem START. So dreht er nicht endlos im Kreis.

**Versperrter Weg:** Er hält an und wartet (Zieldefinition GB-04, Gegenverkehr regelt die Infrastruktur). Automatisches Ausweichen (zurück + wenden nach zufälliger Wartezeit) gibt es weiterhin, ist aber **aus** (`ausweichen: true` schaltet es ein).

**Werte ändern:** Alle Zahlen aus `ki/entscheider.py` (`STANDARD`) sind Einstellungen der KI-Zentrale. Man trägt sie in `config/lokal/roboter.yaml` unter `ki_zentrale:` → `ros__parameters:` ein, z. B. `zebra_halt: 0.30`, und startet die KI neu.

**Fahrschlauch:** Der Linienfolger meldet, wo die Linie vor dem Roboter verläuft. Die KI prüft nur den Streifen von **30 cm Breite** (`fahrschlauch_breite`, Roboterbreite + Rand, **nachmessen**) entlang dieser Linie. Dasselbe gilt für die Tiefenkamera. Früher war es ein gerader Kegel nach vorne. Dann hielt er in jeder Kurve vor Häusern am Rand, und in einer Kurve hielt die Tiefenkamera einen Fußgänger am Straßenrand für ein Hindernis.

**Warum hat die Notbremse unter 12 cm das letzte Wort und nicht die KI?** Die KI kennt nur 80 Dinge. Einen Schuh, ein Kabel oder einen Karton kennt sie nicht. Darum: ganz nah = sofort stopp.

## Hindernis wegräumen (ki/ablaeufe.py, `Wegraeumen`)

1. **Anhalten, anschauen:** mindestens 1 s **und** mindestens 5 neue KI-Bilder (höchstens 8 s). Ist die KI langsam, wartet er also länger, statt nach einem halben Blick zu entscheiden. Er misst mit der Tiefenkamera: wo, wie breit, wie hoch.
2. **Urteil:**
   - Kamera und LiDAR sehen nichts mehr → weiter (Fehlalarm).
   - Nur der LiDAR sieht etwas → LANGSAM, ab 20 cm STOPP. Ist es näher als 22 cm (zu nah für die Kamera), fährt er bis zu 10 cm zurück und schaut nochmal.
   - Lebewesen, Fahrzeug, zu groß, am Rand, kurz nach einem Zebrastreifen, Arm nicht freigegeben → **warten**, bis der Weg frei ist.
3. **In Greifweite fahren:** geregelt nach dem, was die Kamera misst (nicht nach der Zeit), bis die Vorderkante 25 cm vor der Robotermitte liegt.
4. **Planen:** Die KI rechnet die Servowinkel für jeden Schritt aus (inverse Kinematik). Auf dem Roboter macht das Yahbooms Kinematik-Dienst mit dem echten Armmodell, siehe [greifarm.md](greifarm.md). Erreicht der Arm einen Punkt nicht, wird nichts bewegt und er wartet.
5. **Ausführen:** Greifer auf → über das Hindernis → runter → zu → anheben → zur Seite (die Seite, auf der der LiDAR weniger sieht, sonst rechts) → absetzen → loslassen → Fahrstellung.
6. **Prüfen:** Kamera wieder nach vorne, mindestens 1,5 s und 5 Bilder. Sieht sie im Weg noch etwas → 2. Versuch (ab 1.), danach aufgeben und warten. Sonst „Weg ist frei (geprüft)“ → weiter.

Der Arm bewegt sich nur, wenn er freigegeben ist (Panel → Arm) und das Fahrprogramm **fährt** (START). Im TEST und nach STOPP bewegt die KI den Arm nie. Ein laufender Ablauf wird abgebrochen. Beim nächsten START fährt der Arm zuerst in die Fahrstellung.

## Die Sinne

- **Kamera-KI**: YOLO. Mit Grafikkarte (Jetson): über Ultralytics/TensorRT, z. B. Yahbooms `~/ultralytics/ultralytics/yolo11n.engine` (sucht selbst, `erkennung/yolo.py`). Ohne: `models/yolov8n.onnx` auf dem Prozessor. Im Panel steht, was läuft (z. B. „TensorRT (Grafikkarte)“). 80 Dinge aus dem COCO-Datensatz, u. a. Person, Auto, Bus, Fahrrad, Hund, Ampel, Stoppschild. Findet sie eine **Ampel**, schaut sie im Kasten nach, welche Lampe leuchtet.
- **Ersatz, wenn die KI nichts findet**:
  - LED-Erkennung für die winzigen SmartCity-Ampeln (`line_follower/ampel.py`, einstellbar im Panel → System → „Ampel einstellen“),
  - Achteck-Form für Stoppschilder (`line_follower/schilder.py`).
- **Einfahrt verboten**: roter Kreis mit waagrechtem weißem Balken (`schilder.finde_einfahrt_verboten`).
- **Zebrastreifen**: In der Draufsicht des Linienfolgers sind mindestens 4 gleich breite, parallele Balken nebeneinander (`lib/zebra.py`).
- **LiDAR**: nächster Punkt im Fahrschlauch (`lib/lidar.py`). Richtung "vorne" je LiDAR im Panel einstellbar.
- **Tiefenkamera**: Für jeden Bildpunkt wird die Höhe über dem Boden ausgerechnet. Den Boden lernt sie, solange der Weg frei ist (`lib/tiefe.py`). Erkennt auch den 4,5 cm hohen Würfel.
- **Wohin schaut die Kamera?** Die KI hört `/arm6_joints` mit (KI, Panel und Gamepad senden dorthin). Steht der Arm nicht in der Fahrstellung, werden Draufsicht, Zebrastreifen und Tiefe nicht ausgewertet. Linienfolger und Kartograf bekommen das ebenfalls mitgeteilt.

## Getestet (in der VM, nicht auf dem Roboter)

- Entscheidungslogik: `tests/test_entscheider.py`.
- Komplette Simulation mit ROS 2 Humble (`scripts/simulation.sh pruefen`), alles bestanden:
  - Ampel, Zebrastreifen mit Fußgänger,
  - Würfel anschauen, Armbewegung berechnen, wegräumen, Weg prüfen,
  - Stoppschild, Einbahnstraße (gewendet bei ca. 160°),
  - Karte.

## Grenzen (ehrlich)

- Das Modell wurde mit **echten Fotos** trainiert. Spielfiguren und Spielzeugautos erkennt es nur teilweise oder gar nicht. In der Simulation hielt es eine gezeichnete Fläche einmal kurz für eine Katze. Für die SmartCity braucht man wahrscheinlich ein **eigenes Modell**: ca. 100–300 Fotos der echten Figuren, Autos, Schilder und Ampeln machen, markieren (z. B. Roboflow oder Label Studio), mit Ultralytics trainieren, als ONNX exportieren, nach `models/` legen und die Namen in `erkennung/yolo.py` anpassen.
- Zebrastreifen-, Einbahn- und Würfelerkennung sind nur mit **gezeichneten** Bildern getestet. Echte Schilder können anders aussehen (Größe, Farbe, Licht).
- Die Rechenzeit auf dem Jetson ist noch nicht gemessen. Das Panel zeigt sie an ("ms/Bild").

## Modell neu exportieren (auf einem Laptop mit Internet)

```bash
pip install ultralytics
yolo export model=yolov8n.pt format=onnx imgsz=320 opset=12
```

Auf dem Roboter läuft das Modell mit **onnxruntime** (`installieren.sh` bietet die Installation an).

## Roboter-eigene KI (Yahboom)

Yahboom liefert "KI-Großmodell"-Funktionen mit (Sprachmodell, auf RM03 liegt Dify). Ob dort etwas **lokal** läuft, ist ungeprüft: `scripts/ki_suchen.sh > ki.txt`. Ein Sprachmodell ist für schnelle Fahrentscheidungen zu langsam. **API-Schlüssel nie ins Repository!**

Lizenz: YOLOv8 von Ultralytics steht unter AGPL-3.0.
