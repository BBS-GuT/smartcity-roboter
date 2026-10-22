#!/bin/bash
# Sucht, welche KI auf dem Roboter schon vorhanden ist. Aendert nichts, faehrt nicht.
# Ausgabe in Datei:  scripts/ki_suchen.sh > ki.txt 2>&1
echo "===== JETSON / GRAFIKKARTE ====="
cat /etc/nv_tegra_release 2>/dev/null || echo "keine nv_tegra_release"
python3 - <<'PY'
def probe(name, code):
    try:
        print(f'{name}: {eval(code)}')
    except Exception as e:
        print(f'{name}: nicht vorhanden ({type(e).__name__})')
probe('OpenCV', '__import__("cv2").__version__')
probe('OpenCV mit CUDA (Grafikkarte)', '__import__("cv2").cuda.getCudaEnabledDeviceCount()')
probe('PyTorch', '__import__("torch").__version__')
probe('PyTorch CUDA', '__import__("torch").cuda.is_available()')
probe('TensorRT', '__import__("tensorrt").__version__')
probe('onnxruntime', '__import__("onnxruntime").get_available_providers()')
probe('ultralytics (YOLO)', '__import__("ultralytics").__version__')
probe('mediapipe', '__import__("mediapipe").__version__')
PY
echo "===== LOKALE SPRACHMODELLE ====="
command -v ollama >/dev/null && { echo "ollama vorhanden:"; ollama list 2>&1; } || echo "ollama: nicht vorhanden"
systemctl list-units --type=service --no-pager 2>/dev/null | grep -iE "ollama|dify|llm|docker" || true
echo "===== DOCKER (z. B. Dify) ====="
docker ps --format '{{.Names}}  {{.Image}}' 2>&1 | head -20
echo "===== MODELL-DATEIEN IM HOME-ORDNER ====="
find "$HOME" -maxdepth 6 \( -name "*.onnx" -o -name "*.engine" -o -name "*.pt" -o -name "*.trt" -o -name "*.gguf" -o -name "*.tflite" \) \
    -not -path "*/smartcity-roboter/*" 2>/dev/null | head -50
echo "===== YAHBOOM KI-PAKETE ====="
for ws in "$HOME/yahboomcar_ws" "$HOME/M3Pro_ws"; do
    ls "$ws/src" 2>/dev/null | grep -iE "ai|llm|model|large|voice|yolo|vision|mediapipe|detect" | sed "s|^|$ws/src/|"
done
echo "===== API-SCHLUESSEL-DATEIEN (nur Namen, Inhalt NICHT anzeigen) ====="
find "$HOME" -maxdepth 5 -iname "*key*" -o -maxdepth 5 -iname "*.env" 2>/dev/null | grep -v smartcity-roboter | head -20
