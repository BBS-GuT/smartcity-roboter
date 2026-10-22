import paho.mqtt.client as mqtt
import json
import time

# --- Konfiguration ---
BROKER_HOST = "192.168.1.100"  # IP des Projektbrokers (anpassen)
BROKER_PORT = 1883
ROBOT_ID = "RM01"              # Eigene Roboter-ID (z. B. RM01, RM02, etc.)

# Topics gemäß Projektvorgabe (ACL-konform getrennt)
TOPIC_PUBLISH = f"smartcity/robots/{ROBOT_ID}/strecke"
TOPIC_SUBSCRIBE = "smartcity/robots/+/strecke"  # Wildcard (+) um alle anderen Roboter zu hören

# Eigener geplanter Pfad und Timestamp (für M1f Auswahllogik)
eigner_timestamp = time.time()
eigner_pfad = ["Node_1", "Node_2", "Node_3"]

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[{ROBOT_ID}] Erfolgreich mit dem MQTT-Broker verbunden!")
        client.subscribe(TOPIC_SUBSCRIBE)
    else:
        print(f"Verbindung fehlgeschlagen, Fehlercode: {rc}")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        absender = payload.get("robot_id")
        fremder_pfad = payload.get("pfad", [])
        fremder_timestamp = payload.get("timestamp", 0)
        
        # Eigene Nachricht ignorieren
        if absender == ROBOT_ID:
            return
            
        print(f"[{ROBOT_ID}] Strecken-Info empfangen von {absender}")
        
        # --- M1f AUSWAHLLOGIK (Konflikterkennung & Vorrang) ---
        gemeinsame_knoten = set(eigner_pfad).intersection(set(fremder_pfad))
        if gemeinsame_knoten:
            print(f"[{ROBOT_ID}] Konflikt erkannt auf Knoten: {gemeinsame_knoten}")
            
            # Prioritätsregel: Ältester Timestamp gewinnt, bei Gleichstand entscheidet die Roboter-ID
            if fremder_timestamp < eigner_timestamp or (fremder_timestamp == eigner_timestamp and absender < ROBOT_ID):
                print(f"[{ROBOT_ID}] Roboter {absender} hat Vorrang. Wir warten.")
            else:
                print(f"[{ROBOT_ID}] Wir haben Vorrang. Fahrt fort.")
                
    except Exception as e:
        print(f"Fehler bei der Auswahllogik: {e}")

# MQTT Client einrichten
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER_HOST, BROKER_PORT, 60)
client.loop_start()

def sende_strecken_daten(ziel, strecken_knoten):
    """Sendet die eigene geplante Route an den Broker."""
    daten = {
        "robot_id": ROBOT_ID,
        "ziel": ziel,
        "pfad": strecken_knoten,
        "timestamp": eigner_timestamp
    }
    client.publish(TOPIC_PUBLISH, json.dumps(daten))
    print(f"[{ROBOT_ID}] Eigene Strecke veröffentlicht: {daten}")

if __name__ == "__main__":
    try:
        time.sleep(1)
        sende_strecken_daten(ziel="Station_B", strecken_knoten=eigner_pfad)
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("Programm wird beendet...")
        client.loop_stop()
        client.disconnect()