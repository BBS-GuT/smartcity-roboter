# Modelle

- `yolov8n.onnx`: YOLOv8n von Ultralytics (COCO, 80 Klassen), exportiert mit `imgsz=320 opset=12`. Lizenz AGPL-3.0. Siehe `docs/ki.md`.
- `greifen.json`: vortrainierte Greif-Korrektur (`lib/greifen.py`), erzeugt im Simulator mit `python3 sim/greifen_trainieren.py`. Siehe `docs/greifarm.md`, „Greifen lernen“. Auf dem Roboter Weitergelerntes liegt in `config/lokal/greifen.json`.
