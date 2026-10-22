# MQTT-Broker: Betrieb und Prüfung

Stand: 22.10.2026. Der Projektbroker hat nach der letzten Mitteilung die Adresse
`10.0.40.100:1883`. Die folgenden Schritte beziehen sich auf den Fork
`BKoewenig/smartcity-roboter`, Branch `feat/mqtt-panel-telemetrie`.

## Wie die Verbindung funktioniert

Beim normalen Start des SmartCity-Panels startet die lesende MQTT-Bridge mit.
Sie versucht, sich beim Projektbroker anzumelden. Erst eine erfolgreiche
MQTT-Anmeldung zählt als Verbindung. Ist der Projektbroker nicht erreichbar oder
lehnt er die Anmeldung ab, nutzt die Bridge `127.0.0.1:1883` auf demselben
Roboter. Falls dort noch kein Broker läuft, startet sie einen lokalen
Testbroker. Alle 30 Sekunden prüft sie erneut, ob der Projektbroker erreichbar
ist, und wechselt dann automatisch zurück. Der Wechsel erzeugt keine
Fahrbefehle.

Der lokale Testbroker lauscht **nur auf dem jeweiligen Roboter**. Vier Roboter
können darüber weder Daten noch Karten austauschen. Dafür müssen alle vier zum
selben Projektbroker verbinden und eindeutige Roboter-IDs verwenden.

## Einmalige Einrichtung auf jedem Roboter

Die Desktop-Verknüpfung übernimmt keine Variablen aus einem SSH-Terminal.
Deshalb auf **jedem** Roboter die eigene lokale Datei
`~/.config/smartcity/mqtt.json` anlegen beziehungsweise eine alte Broker-IP
darin ersetzen. Beispiel ohne echte Zugangsdaten:

```json
{
  "MQTT_HOST": "10.0.40.100",
  "MQTT_PORT": 1883,
  "MQTT_USERNAME": "BENUTZERNAME_DES_BROKERS",
  "MQTT_PASSWORD": "PASSWORT_DES_BROKERS"
}
```

Die Datei ist privat zu halten (`chmod 600 ~/.config/smartcity/mqtt.json`).
Zugangsdaten gehören weder in Git noch in Screenshots oder Diagnoseausgaben.
Eine gesetzte Umgebungsvariable `MQTT_HOST` hat Vorrang vor dieser Datei; bei
Problemen auch sie auf die alte IP prüfen. Der Code verwendet `10.0.40.100`,
wenn kein Host konfiguriert ist.

Die Bridge kann nur Daten veröffentlichen, die das Panel wirklich empfängt.
Fehlt wie derzeit `/battery` der Publisher, bleibt die Akkuspannung unbekannt.
Das MQTT-System erfindet keinen Wert. Es nimmt keine Fahrbefehle entgegen.

## Zu Hause ohne Schulnetz

Von zu Hause ist `10.0.40.100` nur erreichbar, wenn dafür ein tatsächlich
eingerichteter Netzweg besteht. Ohne diesen Netzweg ist ein TCP-Timeout zu
erwarten; es sagt nichts über den Zustand des Brokers im Schulnetz aus. Auf dem
Roboter kann das Panel trotzdem mit dem lokalen Testbroker arbeiten. Die
anderen Roboter und die zentrale WebApp sehen diese lokalen Nachrichten nicht.

Die Implementierung lässt sich ohne Roboter und Schulnetz mit synthetischen
Daten prüfen:

```bash
python3 -m pip install -r mqtt/requirements-test.txt
python3 mqtt/integration_test.py
python3 mqtt/auth_integration_test.py
python3 mqtt/m1_integration_test.py
```

Diese Tests belegen die lokale Softwarefunktion, nicht die Erreichbarkeit oder
Freigabe des Projektbrokers.

## Im Schulnetz prüfen

Wenn Roboter und Broker wieder im Projektnetz sind, auf einem Rechner mit
Netzweg zu `10.0.40.100` und mit eigenen Broker-Zugangsdaten prüfen:

```bash
export MQTT_USERNAME='BENUTZERNAME_DES_BROKERS'
export MQTT_PASSWORD='PASSWORT_DES_BROKERS'
python3 mqtt/check_broker.py --host 10.0.40.100 --port 1883
```

Das Skript prüft TCP, MQTT-Anmeldung, Subscription, QoS-1-Bestätigung und den
Empfang einer synthetischen, nicht gespeicherten Nachricht über einen zweiten
Client. `PASS` für alle Schritte bestätigt genau diesen Testweg. Ein Fehler bei
TCP deutet auf Netzweg, Firewall oder Brokerdienst; eine abgelehnte Anmeldung
auf Zugangsdaten oder Brokerberechtigungen. Wenn TCP funktioniert, aber der
Nachrichtentest scheitert, auch die Topic-Rechte für
`smartcity/diagnostics/+/echo` prüfen.

Danach das Panel auf jedem Roboter öffnen und unter **MQTT Daten** kontrollieren,
ob als Ziel `project` und als Broker `connected` angezeigt werden. Die WebApp
muss sich mit demselben Projektbroker verbinden. Der jeweilige Roboter sendet
unter `smartcity/robots/<ROBOTER-ID>/...`; Beispiele der Topics und ihrer
Bedeutung stehen in [README.md](README.md). Die zentralen Karten-Topics stehen
in [docs/m1-mqtt.md](../docs/m1-mqtt.md).

Eine gemeinsame Karte darf erst veröffentlicht oder zum Fahren benutzt werden,
wenn feste gemeinsame Marker, überprüfte Koordinaten und Strecken-IDs vorhanden
sind. Die aktuelle M1-Implementierung bereitet den Datenaustausch vor; der
Projektbroker allein löst diese Voraussetzungen nicht.

