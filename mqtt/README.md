# MQTT-Telemetrie aus dem bestehenden Panel

Dieser Adapter liest den Panelstatus und die lokalen Lese-Endpunkte für Farbkamera,
native Tiefe und beide LiDAR-Scans. Er empfängt keine Befehle und besitzt keinen
ROS-/Motorzugang. Der Status verwendet `panel-telemetry/1`, die Sensordetails
`panel-detail/1`. Beide Transporthüllen sind noch kein gemeinsamer
`grundbetrieb-v1`-Zustand. Ein Live-Test auf einem echten Roboter und dem
Projektbroker steht noch aus; dieser Stand ist **keine vollständige C2-/GB-16-Abnahme**.

## Roboter: installieren und starten

Im Projektordner (ROS/Panel bereits gestartet):

```bash
python3 -m pip install -r mqtt/requirements.txt
export MQTT_HOST=10.0.10.11  # geplante Projektadresse; bei Abweichung anpassen
export MQTT_PORT=1883
export SMARTCITY_ROBOT_ID=RM02
# Der dokumentierte Projektbroker verlangt Anmeldung; Werte lokal setzen:
export MQTT_USERNAME='DEIN_BENUTZER'
export MQTT_PASSWORD='DEIN_PASSWORT'
bash scripts/mqtt_bridge.sh
```

Beim gewohnten Start über `scripts/panel.sh` beziehungsweise das Desktop-Symbol
startet MQTT automatisch mit; falls `paho-mqtt` fehlt, installiert das Skript
die Abhängigkeit für diesen Benutzer. `SMARTCITY_MQTT=0 scripts/panel.sh`
schaltet MQTT ausdrücklich aus. Bei direktem Aufruf von `panel/panel.py`
ist weiterhin `SMARTCITY_MQTT=1` nötig. Die Bridge endet mit dem Panel.
Mit `MQTT_PYTHON` lässt sich der Pythonpfad einer eigenen Umgebung wählen.

Der Desktop-Start versucht zuerst den Projektbroker (Standard `10.0.10.11:1883`).
Erst eine erfolgreiche MQTT-Anmeldung zählt als Verbindung. Bei Ausfall nutzt
er `127.0.0.1:1883` auf dem Roboter; falls dort noch kein Broker läuft, startet
er einen auf die Loopback-Adresse begrenzten Testbroker. Alle 30 Sekunden prüft
er den Projektbroker erneut und wechselt nach erfolgreicher Anmeldung zurück.
Auf dem lokalen Broker gelten dieselben Robotertopics, er ist jedoch nur auf
dem Roboter erreichbar. Der Wechsel sendet keine Fahrbefehle.

Die Desktop-Verknüpfung übernimmt keine in einem SSH-Terminal gesetzten
Umgebungsvariablen. Brokeradresse und Zugang können lokal in
`~/.config/smartcity/mqtt.json` mit Dateirechten `0600` stehen, etwa:

```json
{"MQTT_HOST":"10.0.10.11","MQTT_PORT":1883,
 "MQTT_USERNAME":"BENUTZER","MQTT_PASSWORD":"PASSWORT"}
```

Ohne gültige Projektdaten bleibt die Bridge beim lokalen Testbroker. Im
Panelstatus kennzeichnet `mqtt.target` das aktuell verwendete Ziel (`project`
oder `local`), `mqtt.broker` die tatsächliche Verbindung und
`last_panel_ack_seq` die bestätigte Sequenz.

## Vom Windows-PC aus

PowerShell im Projektordner, Panel auf dem Roboter bereits geöffnet:

```powershell
py -m pip install -r mqtt/requirements.txt
$env:MQTT_USERNAME = 'DEIN_BENUTZER'
$env:MQTT_PASSWORD = 'DEIN_PASSWORT'
py mqtt/panel_bridge.py --host 10.0.10.11 --robot RM02 --panel http://ROBOTER-IP:8080
```

Eine andere im Panel gemeldete Gerätekennung wird abgelehnt. Der PC benötigt
Netzzugriff auf Panel und Broker. Die Detail-Endpunkte sind auf `127.0.0.1`
beschränkt; für den Livebild- und Sensordatenstrom muss die Bridge deshalb auf
dem Roboter laufen. Der Start vom Windows-PC aus sendet nur den Panelstatus.
`--tls --port 8883 --ca PFAD` aktiviert TLS mit Zertifikatsprüfung; Port und
Zertifikate mit dem Brokerteam klären.

## Empfang prüfen

MQTT Explorer mit denselben Brokerdaten verbinden und abonnieren:

- `smartcity/robots/RM02/state`: vollständiger, unveränderter `grundbetrieb-v1`-Zustand,
  **nur wenn** ein gültiger und frischer Produzent ihn auf dem ROS-String-Topic
  `/grundbetrieb/zustand` veröffentlicht. Das Topic kann mit `SMARTCITY_STATE_TOPIC`
  angepasst werden. Ohne diesen Produzenten wird ein alter retained Zustand gelöscht;
  die Bridge erfindet keine Motor-, Sicherheits- oder Positionswerte.
- `smartcity/robots/RM02/info`: Fähigkeiten und Verfügbarkeit des gemeinsamen
  Zustands (`panel-info/1`, QoS 1, retained). Versionsfelder ohne verlässliche
  Quelle bleiben `null`.
- `smartcity/robots/RM02/events`: neue Panelereignisse ab Bridge-Start
  (`panel-event/1`, QoS 1, nicht retained). Bereits vorhandene Historie wird
  nicht erneut als neues Ereignis ausgegeben.
- `smartcity/robots/RM02/communication`: Brokerbestätigungen, Wiederverbindungen
  und verworfene Detailnachrichten (`panel-communication/1`, QoS 1, nicht retained).

- `smartcity/robots/RM02/panel/state`: Status, Akku, Sensorübersicht, KI, Linienfolger,
  Position/Kartenstatus, Ereignisse und Armstatus, soweit vom Panel verfügbar.
- `smartcity/robots/RM02/availability`: `online` erst nach bestätigter Statusübertragung,
  `offline` bei Panelausfall, regulärem Ende oder Last Will.
- `smartcity/robots/RM02/details/camera`: aktuelle Farbkamera als JPEG, standardmäßig
  bis 20 Bilder/s, maximal 640 Pixel breit und 256 KiB pro JPEG.
- `smartcity/robots/RM02/details/depth`: nativer Tiefenframe mit ROS-Encoding,
  Breite, Höhe, Zeilenschritt und Endianness; Rohbytes mit zlib komprimiert.
- `smartcity/robots/RM02/details/scan0` und `.../scan1`: native Winkel- und
  Distanzwerte beider konfigurierter LaserScans, soweit aktuell vorhanden.

Detailnachrichten sind JSON (`panel-detail/1`), QoS 0 und **nicht retained**.
`payload.data_b64` enthält beim Kamerakanal JPEG-Bytes als Base64 und beim
Tiefenkanal zlib-komprimierte Rohbytes als Base64. Zum Anzeigen `data_b64`
dekodieren; beim Tiefenkanal anschließend zlib entpacken und `encoding`,
`step`, `width`, `height` und `is_bigendian` beachten. `frame_key` unterscheidet
Frames, `frame_id` ist der ROS-Koordinatenrahmen, `captured_at` die ROS-Aufnahmezeit
(falls vorhanden), `observed_at` der Empfang im Panel. `state_ack_seq` bezieht
das Detail auf den zuletzt vom Broker bestätigten Panelstatus; es ist keine
Behauptung identischer Sensoraufnahmezeit. Fehlende oder alte Frames erzeugen
keine Platzhalterbilder auf MQTT.

Die Kamerarate lässt sich mit `--camera-hz 1` verringern oder mit
`--camera-hz 0` abschalten (Bereich 0–20). Tiefe und Scans werden höchstens
einmal pro Statusrunde angefragt, standardmäßig etwa einmal pro Sekunde.
Detaildaten haben keine Wiederholungswarteschlange und werden nach einem Ausfall
nicht nachgeliefert. Bandbreite und Broker-Paketgrenzen müssen im echten Netz
mit dem Brokerteam gemessen und abgestimmt werden.

`MQTT PUBACK seq=...` im Terminal bestätigt die QoS-1-Brokerbestätigung.
Ein separater Abonnent muss zusätzlich den tatsächlichen Empfang prüfen.
`received_at` ist der Abrufzeitpunkt, **kein Sensoraufnahmezeitpunkt**. Panelwerte
behalten ihre vorhandenen Alters-/Gültigkeitsangaben. `null` bleibt unbekannt;
NaN/Infinity werden zu null. QoS 1 kann Duplikate liefern: Geräte-ID, boot_id und seq
verwenden. Retained Zustände können alt sein; Empfänger müssen Datenalter selbst
überwachen, auch wenn availability noch online ist.

Standard: eine Statusabfrage pro Sekunde (maximal 1 MiB HTTP-Antwort) und bis zu
20 Bildabfragen pro Sekunde. Detailantworten sind auf 3 MiB begrenzt.
Fehler führen zum Neuaufbau des Clients mit neuen frischen Daten;
kein Offline-Archiv und kein historischer Rückstau. Die neue Startkennung kennzeichnet
diesen Neuaufbau. Panel und lokale Fahrt laufen unabhängig von der Bridge.
Die Erzeugung des offiziellen gemeinsamen Zustands aus den A/B-Komponenten,
der abgestimmte externe Detailvertrag sowie der Vierrobotertest bleiben Folgearbeit.

Das Panel nimmt den gemeinsamen Zustand nur als frisches, schema- und fachlich
gültiges JSON an; `/api/grundbetrieb` gibt ihn ausschließlich lokal und höchstens
zwei Sekunden nach seiner Erzeugung aus. Der Bridge-Empfänger prüft erneut.
Im Panel-Statusfeld `mqtt` steht die lokale Verbindungsdiagnose aus
`logs/mqtt-status.json` (bei `SMARTCITY_MQTT=1`). Diese Bestätigung bezieht sich
auf den Transport. Die eigentliche Zustandserzeugung aus den Komponenten A/B
und ihre Erprobung auf dem Roboter stehen noch aus.

## Softwaretest

```bash
python3 tests/test_mqtt_panel.py
python3 tests/test_telemetry_detail.py
```

Realer Projektbroker und ROS-/Gerätelauf müssen separat geprüft werden.

### Broker gezielt prüfen, ohne Roboterzugriff

```powershell
python -m venv .venv-mqtt
.\.venv-mqtt\Scripts\python.exe -m pip install -r mqtt/requirements-test.txt
.\.venv-mqtt\Scripts\python.exe mqtt/check_broker.py --host 10.0.10.11 --port 1883
```

Der Test prüft zuerst TCP, dann MQTT-Anmeldung (mit `MQTT_USERNAME` und
`MQTT_PASSWORD`, falls gesetzt; sonst anonym), SUBACK, QoS-1-PUBACK und den
identischen Empfang über einen zweiten Client. Er sendet ausschließlich synthetische,
nicht retained Nachrichten auf `smartcity/diagnostics/<zufällige UUID>/echo`.
Der Broker muss diesen Diagnosebereich zum Lesen und Schreiben erlauben.
Es werden weder Panel noch ROS oder Roboterprozesse gestartet. Exitcode 0 bedeutet
Erfolg, 1 TCP-Fehler, 2 MQTT-/Übertragungsfehler. Bei TCP-Fehlern sind Anmeldung und
Übertragung noch nicht geprüft.

Bei Timeout zuerst Projektnetz/WLAN, VLAN-Routing, Firewall und VPN prüfen.
`Find-NetRoute -RemoteIPAddress 10.0.10.11` zeigt unter Windows die gewählte Route.
Ein Timeout allein unterscheidet nicht zwischen fehlendem Netzpfad, Paketfilter
und ausgefallenem Broker. Zugangsdaten nicht ins Repository oder in Logs schreiben.

Zusätzlicher echter lokaler Brokertest (synthetisches Panel, unabhängiger MQTT-Leser,
Panelausfall/-wiederkehr und Brokerneustart; kein Projektnetz nötig):

```bash
python3 -m pip install -r mqtt/requirements-test.txt
python3 mqtt/integration_test.py
python3 mqtt/auth_integration_test.py
```

`integration_test.py` prüft zusätzlich mehrere aufeinanderfolgende JPEG-Nachrichten,
einen entpackbaren nativen Tiefenframe und beide Scans bei einem unabhängigen
MQTT-Empfänger. Der HTTP-Server liefert dazu ausschließlich synthetische Daten.
Mit `--load-seconds 60` misst derselbe Test eine Minute lang empfangene Bilder,
Bildrate und Datenmenge. Er vergleicht alle empfangenen JPEG-Bytes mit der Quelle.
Die eingestellten 20 fps sind eine Obergrenze, keine garantierte Bildrate.

Zum Anschauen der synthetischen Nachrichten im Browser, ebenfalls nur lokal:

```powershell
.\.venv-mqtt\Scripts\python.exe mqtt/local_demo.py
```

Das Skript startet einen Broker, ein künstliches Panel, die echte Bridge und einen
unabhängigen MQTT-Leser auf `127.0.0.1`. Die ausgegebene Browseradresse zeigt
Testbild, empfangene Bildrate, Status, `info`, Ereignisse und Diagnosen. Mit
Strg+C wird die Demo beendet. Sie hat keinen Kontakt zum Roboter oder Projektbroker.

Der zusätzliche Anmeldetest verwendet einen lokalen Broker mit zufälligen
Testzugangsdaten: gültige Anmeldung samt unabhängiger Übertragung, falsches
Passwort, fehlende Anmeldung sowie Anmeldung/PUBACK und geordnetes Ende der
Telemetrie-Bridge. Er benötigt dieselben Testabhängigkeiten.
Ein zweiter angemeldeter Client vergleicht mindestens drei vollständige
Telemetrie-Payloads mit der synthetischen Quelle (Akku, null-Wert, Scanwerte,
Position und Ereignistext) und prüft Geräte-/Startkennung, Sequenz, ACK-Bezug
sowie den Empfang von online und offline. Es werden keine echten Roboter benötigt.

## Projektunterlagen vom 21.10.2026

Die bereitgestellte Brokerdokumentation nennt `172.16.3.29` als alte temporäre
Schulnetzadresse und `10.0.10.11:1883` als Ziel im Projektnetz (VLAN 10).
MQTT verlangt Anmeldung; TLS ist laut Dokumentation nicht eingerichtet.
Der Nutzer bestätigt das 10er Projektnetz als künftigen Standort; die genaue
Laufzeitadresse und der aktive Brokerdienst sind noch zu bestätigen. Der Code
verwendet `10.0.10.11` als geplanten Standard und erlaubt eine abweichende IP
mit `MQTT_HOST` oder `--host`. Für einen Test im Projektnetz:

```powershell
.\.venv-mqtt\Scripts\python.exe mqtt/check_broker.py --host 10.0.10.11
```

`MQTT_USERNAME` und `MQTT_PASSWORD` zuvor lokal mit den bereitgestellten Daten
setzen. Der Robotikanschluss liegt laut Netzwerkübergabe in VLAN 12,
`10.0.12.0/24`, Gateway `10.0.12.1`; die Firewall muss den jeweiligen
MQTT-Teilnehmer zum bestätigten Broker auf TCP 1883 zulassen. Ein erreichbares
Gateway bestätigt noch keine Verbindung zum Broker. Dokumentierte Haus-Aktor-
Topics werden für diese Diagnose nicht verwendet.
