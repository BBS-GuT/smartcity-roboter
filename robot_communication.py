"""Austausch und lokale Auswertung geplanter Routen per MQTT.

Der Import öffnet keine Netzwerkverbindung. MQTT startet erst mit ``starte()``.
Der Fahrplaner muss ``warte_auf_freigabe()`` vor der Fahrt abfragen; diese
Klasse steuert selbst keine Motoren.
"""
import json
import math
import os
from pathlib import Path
import threading
import time

TOPIC_ROOT = 'smartcity/robots'


def _robot_id():
    konfiguriert = os.environ.get('SMARTCITY_ROBOT_ID')
    if konfiguriert:
        return konfiguriert
    try:
        return (Path.home() / 'roboter_name').read_text(encoding='utf-8').strip() or 'RM01'
    except OSError:
        return 'RM01'


def _pfad(value):
    return isinstance(value, list) and all(isinstance(knoten, str) and knoten for knoten in value)


def _zeit(value):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and value >= 0)


class StreckenKoordinator:
    """Veröffentlicht Routen und stellt eine explizit abfragbare Fahrfreigabe bereit."""

    def __init__(self, robot_id=None, broker_host=None, broker_port=None, client=None):
        self.robot_id = robot_id or _robot_id()
        if not isinstance(self.robot_id, str) or not self.robot_id:
            raise ValueError('robot_id muss nicht leer sein')
        self.broker_host = broker_host or os.environ.get('SMARTCITY_MQTT_BROKER_HOST')
        port = broker_port if broker_port is not None else os.environ.get('SMARTCITY_MQTT_BROKER_PORT', '1883')
        try:
            self.broker_port = int(port)
        except (TypeError, ValueError) as error:
            raise ValueError('broker_port muss eine ganze Zahl sein') from error
        if not 1 <= self.broker_port <= 65535:
            raise ValueError('broker_port muss zwischen 1 und 65535 liegen')

        self.client = client
        self.connected = False
        self.eigner_pfad = []
        self.eigner_timestamp = None
        self.fremde_routen = {}
        self.blockiert_von = set()
        self._lock = threading.RLock()
        self._freigabe = threading.Event()

    @property
    def topic_publish(self):
        return f'{TOPIC_ROOT}/{self.robot_id}/strecke'

    @property
    def topic_subscribe(self):
        return f'{TOPIC_ROOT}/+/strecke'

    def _aktualisiere_freigabe(self):
        if self.connected and self.eigner_pfad and not self.blockiert_von:
            self._freigabe.set()
        else:
            self._freigabe.clear()

    def setze_eigene_route(self, strecken_knoten, timestamp=None):
        if not _pfad(strecken_knoten):
            raise ValueError('strecken_knoten muss eine Liste nichtleerer Knotennamen sein')
        timestamp = time.time() if timestamp is None else timestamp
        if not _zeit(timestamp):
            raise ValueError('timestamp muss eine endliche, nichtnegative Zahl sein')
        with self._lock:
            self.eigner_pfad = list(strecken_knoten)
            self.eigner_timestamp = timestamp
            self._bewerte_routen()

    def _bewerte_routen(self):
        blockiert = set()
        eigene_knoten = set(self.eigner_pfad)
        for absender, route in self.fremde_routen.items():
            if (eigene_knoten.intersection(route['pfad'])
                    and (route['timestamp'], absender) < (self.eigner_timestamp, self.robot_id)):
                blockiert.add(absender)
        self.blockiert_von = blockiert
        self._aktualisiere_freigabe()

    def verarbeite_nachricht(self, payload):
        if not isinstance(payload, dict):
            return 'ungueltig'
        absender = payload.get('robot_id')
        route = payload.get('pfad')
        timestamp = payload.get('timestamp')
        if absender == self.robot_id:
            return 'eigene'
        if not isinstance(absender, str) or not absender or not _pfad(route) or not _zeit(timestamp):
            return 'ungueltig'
        with self._lock:
            self.fremde_routen[absender] = {'pfad': list(route), 'timestamp': timestamp}
            self._bewerte_routen()
            if absender in self.blockiert_von:
                return 'warten'
            return 'vorrang' if set(self.eigner_pfad).intersection(route) else 'frei'

    def on_connect(self, client, userdata, flags, reason_code, properties):
        self.connected = int(reason_code) == 0
        with self._lock:
            self._aktualisiere_freigabe()
        if self.connected:
            client.subscribe(self.topic_subscribe)

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        with self._lock:
            self.connected = False
            self._aktualisiere_freigabe()

    def on_message(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode('utf-8'))
        except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
            return 'ungueltig'
        return self.verarbeite_nachricht(payload)

    def sende_strecken_daten(self, ziel, strecken_knoten):
        if self.client is None:
            raise RuntimeError('MQTT ist nicht gestartet')
        self.setze_eigene_route(strecken_knoten)
        daten = {'robot_id': self.robot_id, 'ziel': ziel, 'pfad': self.eigner_pfad,
                 'timestamp': self.eigner_timestamp}
        return self.client.publish(self.topic_publish, json.dumps(daten))

    def starte(self):
        if not self.broker_host:
            raise RuntimeError('SMARTCITY_MQTT_BROKER_HOST muss konfiguriert sein')
        if self.client is None:
            import paho.mqtt.client as mqtt
            self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                                      client_id=self.robot_id)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.connect(self.broker_host, self.broker_port, 60)
        self.client.loop_start()
        return self.client

    def warte_auf_freigabe(self, timeout=None):
        """Gibt erst nach Brokerverbindung, eigener Route und konfliktfreier Route frei."""
        return self._freigabe.wait(timeout)

    def stoppe(self):
        if self.client is not None:
            self.client.loop_stop()
            self.client.disconnect()
        with self._lock:
            self.connected = False
            self._aktualisiere_freigabe()


def main():
    koordinator = StreckenKoordinator()
    try:
        koordinator.starte()
        time.sleep(1)
        koordinator.sende_strecken_daten('Station_B', ['Node_1', 'Node_2', 'Node_3'])
        while not koordinator.warte_auf_freigabe(timeout=1):
            print(f'[{koordinator.robot_id}] Keine MQTT-Fahrfreigabe; warte.')
    except KeyboardInterrupt:
        print('Programm wird beendet...')
    finally:
        koordinator.stoppe()


if __name__ == '__main__':
    main()