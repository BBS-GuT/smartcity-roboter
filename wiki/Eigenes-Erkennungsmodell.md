# Eigenes Erkennungsmodell (YOLO)

Wie die KI die Kamera auswertet, steht in [`docs/ki.md`](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/ki.md#die-sinne). Hier nur, wie man das Modell austauscht.

## Was gerade läuft

- Mit Grafikkarte (Jetson): Ultralytics/TensorRT, z. B. Yahbooms `~/ultralytics/ultralytics/yolo11n.engine` (`erkennung/yolo.py` sucht selbst).
- Ohne: `models/yolov8n.onnx` auf dem Prozessor mit **onnxruntime** (`installieren.sh` bietet die Installation an).
- Im Panel steht, was läuft (z. B. „TensorRT (Grafikkarte)“) und wie lange ein Bild dauert („ms/Bild“).

## Standardmodell neu exportieren (auf einem Laptop mit Internet)

```bash
pip install ultralytics
yolo export model=yolov8n.pt format=onnx imgsz=320 opset=12
```

Ergebnis nach `models/yolov8n.onnx` legen.

## Warum ein eigenes Modell?

YOLOv8n wurde mit **echten Fotos** (COCO-Datensatz, 80 Klassen) trainiert. Spielfiguren und Spielzeugautos erkennt es nur teilweise, die SmartCity-Ampeln werden noch nicht sauber erkannt.

## Eigenes Modell trainieren (Vorschlag, noch nicht gemacht)

1. 100–300 Fotos der echten Figuren, Autos, Schilder und Ampeln machen, möglichst aus Sicht der Roboterkamera und bei verschiedenem Licht.
2. Markieren, z. B. mit Roboflow oder Label Studio.
3. Mit Ultralytics trainieren und als ONNX exportieren (`imgsz=320 opset=12` wie oben).
4. Nach `models/` legen und die Klassennamen in `erkennung/yolo.py` anpassen.
5. Erst in der Simulation, dann am Roboter im TEST-Modus prüfen.

`erkennung/*` gehört zu Bereich B ([Auftragsregister](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/auftraege/README.md)), Änderungen dort abstimmen.

**Lizenz:** YOLOv8 von Ultralytics steht unter AGPL-3.0.

## Yahbooms eigene KI

Yahboom liefert „KI-Großmodell“-Funktionen mit (Sprachmodell, auf RM03 liegt Dify). Ob dort etwas **lokal** läuft, ist ungeprüft: `scripts/ki_suchen.sh > ki.txt`. Ein Sprachmodell ist für schnelle Fahrentscheidungen zu langsam. **API-Schlüssel nie ins Repository!**
