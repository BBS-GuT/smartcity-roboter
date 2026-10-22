#!/usr/bin/env python3
# Objekterkennung mit einem YOLO-Modell. Ohne ROS.
#   Mit Grafikkarte (Jetson: PyTorch mit CUDA + Ultralytics sind vorinstalliert): YoloGpu,
#     am schnellsten mit einer TensorRT-Datei (.engine), z. B. ~/ultralytics/ultralytics/yolo11n.engine
#   Ohne Grafikkarte: Yolo (ONNX-Datei ueber onnxruntime oder OpenCV, nur Prozessor)
# Beide liefern dasselbe Ergebnis (Liste von Kaesten), die KI-Zentrale merkt keinen Unterschied.
#
# YOLO = "You Only Look Once", ein neuronales Netz, das in einem Bild Objekte
# findet (Kasten + Name + Sicherheit). Das Standardmodell kennt 80 Dinge
# (COCO-Datensatz), u. a. Person, Auto, Bus, Fahrrad, Ampel, Stoppschild.
# Achtung: Es wurde mit ECHTEN Fotos trainiert. Spielzeugautos und
# Spielfiguren erkennt es nur teilweise -> spaeter eigenes Modell trainieren.
import cv2
import numpy as np

# Namen der 80 COCO-Klassen (Reihenfolge ist fest im Modell)
COCO = ['Person', 'Fahrrad', 'Auto', 'Motorrad', 'Flugzeug', 'Bus', 'Zug', 'LKW', 'Boot', 'Ampel',
        'Hydrant', 'Stoppschild', 'Parkuhr', 'Bank', 'Vogel', 'Katze', 'Hund', 'Pferd', 'Schaf', 'Kuh',
        'Elefant', 'Baer', 'Zebra', 'Giraffe', 'Rucksack', 'Schirm', 'Handtasche', 'Krawatte', 'Koffer',
        'Frisbee', 'Ski', 'Snowboard', 'Ball', 'Drachen', 'Baseballschlaeger', 'Baseballhandschuh',
        'Skateboard', 'Surfbrett', 'Tennisschlaeger', 'Flasche', 'Weinglas', 'Tasse', 'Gabel', 'Messer',
        'Loeffel', 'Schuessel', 'Banane', 'Apfel', 'Sandwich', 'Orange', 'Brokkoli', 'Karotte', 'Hotdog',
        'Pizza', 'Donut', 'Kuchen', 'Stuhl', 'Sofa', 'Topfpflanze', 'Bett', 'Esstisch', 'Toilette',
        'Fernseher', 'Laptop', 'Maus', 'Fernbedienung', 'Tastatur', 'Handy', 'Mikrowelle', 'Ofen',
        'Toaster', 'Spuele', 'Kuehlschrank', 'Buch', 'Uhr', 'Vase', 'Schere', 'Teddy', 'Foehn',
        'Zahnbuerste']


class Yolo:
    def __init__(self, modell, groesse=320, namen=None, kerne=2):
        """modell: Pfad zur .onnx-Datei, groesse: Bildgroesse beim Export (imgsz).
        kerne: so viele Prozessorkerne darf die KI benutzen. Mehr = schneller, aber dann
        bleibt fuer Linienfolger und Panel zu wenig uebrig (Roboter ruckelt)."""
        self.groesse = groesse
        self.namen = namen or COCO
        # Weg 1: onnxruntime (funktioniert mit jeder OpenCV-Version, evtl. mit Grafikkarte)
        # Weg 2: OpenCV dnn (braucht OpenCV >= 4.7, Ubuntu 22.04 hat nur 4.5 -> geht dort NICHT)
        try:
            import onnxruntime as ort
            wunsch = ['TensorrtExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider']
            da = ort.get_available_providers()
            opt = ort.SessionOptions()
            opt.intra_op_num_threads = kerne
            opt.inter_op_num_threads = 1
            self.sess = ort.InferenceSession(modell, sess_options=opt, providers=[p for p in wunsch if p in da])
            self.eingang = self.sess.get_inputs()[0].name
            self.backend = 'onnxruntime ' + self.sess.get_providers()[0].replace('ExecutionProvider', '')
            self.net = None
        except ImportError:
            self.sess = None
            cv2.setNumThreads(kerne)
            self.net = cv2.dnn.readNetFromONNX(modell)
            self.backend = 'OpenCV CPU'
            try:
                if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                    self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
                    self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
                    self.backend = 'OpenCV CUDA'
            except Exception:
                pass

    def _rechne(self, blob):
        if self.sess is not None:
            return self.sess.run(None, {self.eingang: blob})[0]
        self.net.setInput(blob)
        return self.net.forward()

    def erkenne(self, img, min_sicher=0.4, nms=0.45):
        """Rueckgabe: Liste von dicts {name, klasse, sicher, box: (x, y, b, h)} in Bildpixeln."""
        h, w = img.shape[:2]
        blob = cv2.dnn.blobFromImage(img, 1 / 255.0, (self.groesse, self.groesse), swapRB=True, crop=False)
        out = self._rechne(blob)          # Form (1, 4 + Klassen, N)
        zeilen = out[0].T                 # -> (N, 4 + Klassen): cx, cy, b, h, Wert je Klasse
        werte = zeilen[:, 4:]
        klassen = werte.argmax(axis=1)
        sicher = werte[np.arange(len(werte)), klassen]
        gut = sicher >= min_sicher
        zeilen, klassen, sicher = zeilen[gut], klassen[gut], sicher[gut]
        fx, fy = w / self.groesse, h / self.groesse
        boxen = [[float((cx - bw / 2) * fx), float((cy - bh / 2) * fy), float(bw * fx), float(bh * fy)]
                 for cx, cy, bw, bh in zeilen[:, :4]]
        # NMS: ueberlappende Kaesten fuer dasselbe Objekt zusammenfassen
        behalten = cv2.dnn.NMSBoxes(boxen, sicher.tolist(), min_sicher, nms) if boxen else []
        ergebnis = []
        for i in np.array(behalten).flatten():
            x, y, bw, bh = boxen[i]
            k = int(klassen[i])
            ergebnis.append({'name': self.namen[k] if k < len(self.namen) else str(k), 'klasse': k,
                             'sicher': round(float(sicher[i]), 2),
                             'box': (int(x), int(y), int(bw), int(bh))})
        return ergebnis


# Hier sucht die KI-Zentrale ein Modell fuer die Grafikkarte (erstes vorhandenes gilt).
# .engine = TensorRT, auf DIESEM Jetson gebaut (Yahboom liefert yolo11n.engine mit), .pt = PyTorch-Modell.
GPU_MODELLE = ['models/yolo_gpu.engine', '~/ultralytics/ultralytics/yolo11n.engine', 'models/yolo_gpu.pt',
               '~/ultralytics/ultralytics/yolo11n.pt']


def gpu_modell_suchen(repo, wunsch=''):
    """Pfad zu einem Modell fuer die Grafikkarte oder None."""
    import os
    for p in ([wunsch] if wunsch else []) + GPU_MODELLE:
        p = os.path.expanduser(p if os.path.isabs(os.path.expanduser(p)) else os.path.join(repo, p))
        if os.path.exists(p):
            return p
    return None


class YoloGpu:
    """YOLO ueber Ultralytics auf der Grafikkarte (CUDA). Gleiche Schnittstelle wie Yolo.
    Wirft beim Start einen Fehler, wenn keine Grafikkarte da ist (dann nimmt die Zentrale Yolo)."""

    def __init__(self, modell, groesse=320, namen=None):
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError('PyTorch sieht keine Grafikkarte (CUDA)')
        from ultralytics import YOLO
        self.modell = YOLO(modell, task='detect')
        self.engine = modell.endswith('.engine')
        self.groesse = groesse
        self.namen = namen or COCO
        # einmal rechnen lassen: der erste Durchlauf dauert lange (Grafikkarte wird vorbereitet)
        self.erkenne(np.zeros((480, 640, 3), np.uint8), 0.5)
        self.backend = ('TensorRT' if self.engine else 'PyTorch CUDA') + ' (Grafikkarte)'

    def erkenne(self, img, min_sicher=0.4, nms=0.45):
        # .engine hat eine feste Bildgroesse (beim Bauen festgelegt) -> nicht vorgeben
        extra = {} if self.engine else {'imgsz': self.groesse, 'half': True}
        r = self.modell.predict(img, conf=min_sicher, iou=nms, device=0, verbose=False, **extra)[0]
        b = r.boxes
        if b is None or len(b) == 0:
            return []
        ergebnis = []
        for (x0, y0, x1, y1), s, k in zip(b.xyxy.cpu().numpy(), b.conf.cpu().numpy(), b.cls.cpu().numpy()):
            k = int(k)
            ergebnis.append({'name': self.namen[k] if k < len(self.namen) else str(k), 'klasse': k,
                             'sicher': round(float(s), 2),
                             'box': (int(x0), int(y0), int(x1 - x0), int(y1 - y0))})
        return ergebnis


def zeichne(view, objekte):
    for o in objekte:
        x, y, bw, bh = o['box']
        farbe = (0, 0, 255) if o.get('im_weg') else (0, 255, 0)
        cv2.rectangle(view, (x, y), (x + bw, y + bh), farbe, 2)
        cv2.putText(view, f"{o['name']} {o['sicher']:.2f}", (x, max(12, y - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, farbe, 2)
