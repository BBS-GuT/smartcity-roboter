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

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[{ROBOT_ID}] Erfolgreich mit dem MQTT-Broker verbunden!")
        # Auf die Strecken-Topics aller anderen Roboter subscriben
        client.subscribe(TOPIC_SUBSCRIBE)
    else:
        print(f"Verbindung fehlgeschlagen, Fehlercode: {rc}")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        absender = payload.get("robot_id")
        
        # Ignorieren, wenn die Nachricht von einem selbst kommt
        if absender == ROBOT_ID:
            return
            
        print(f"[{ROBOT_ID}] Strecken-Info empfangen von {absender}: {payload}")
        # Hier greift später deine Logik zur lokalen Streckenabsprache / Kollisionsvermeidung
        
    except Exception as e:
        print(f"Fehler beim Verarbeiten der Nachricht: {e}")

# MQTT Client einrichten
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

# Falls Authentifizierung erforderlich ist (Broker-ACL / Benutzerdaten):
# client.username_pw_user("dein_benutzername", "dein_passwort")

# Verbindung herstellen
client.connect(BROKER_HOST, BROKER_PORT, 60)

# Netzwerk-Schleife im Hintergrund starten (hört permanent auf Nachrichten)
client.loop_start()

def sende_strecken_daten(ziel, strecken_knoten):
    """Sendet die eigene geplante Route an den Broker."""
    daten = {
        "robot_id": ROBOT_ID,
        "ziel": ziel,
        "pfad": strecken_knoten,
        "timestamp": time.time()
    }
    client.publish(TOPIC_PUBLISH, json.dumps(daten))
    print(f"[{ROBOT_ID}] Eigene Strecke veröffentlicht: {daten}")

if __name__ == "__main__":
    try:
        # Beispiel: Dem Roboter ein Ziel und Knoten zuweisen
        time.sleep(1) # Kurze Wartezeit zum Einrichten der Verbindung
        sende_strecken_daten(ziel="Station_B", strecken_knoten=["Node_1", "Node_2", "Node_3"])
        
        # Programm am Laufen halten, um Nachrichten zu empfangen
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("Programm wird beendet...")
        client.loop_stop()
        client.disconnect()