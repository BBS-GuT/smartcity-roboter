# WebApp: Datenabgleich und offene Quellen

Stand: 22.10.2026. Grundlage: Wunschliste von Team WebApp im Chat und lesender
Abruf der RM04-Testansicht. Keine vollständige Geräteabnahme. Die Testansicht
nutzt einen lokalen Broker auf dem Roboter, nicht den Projektbroker.

| Wunsch | Stand | Noch nötig |
|---|---|---|
| Must: alle Roboter, erreichbar | Bridge unterstützt Geräte-ID; Testansicht nur RM04 | Gemeinsamer Brokerzugang und Empfang für alle Geräte |
| Must: Betriebszustand | Gemeinsamer `grundbetrieb-v1`-Transport vorhanden, RM04 liefert ihn derzeit nicht | Zustandsproduzent aus Sicherheits- und Navigationsteilen |
| Must: Spielfeldposition, falls bekannt | Unbekannt; keine bestätigte Zuordnung | Lokalisierung und verifizierte Zuordnung zum Spielfeld |
| Must: Akku | Spannungsfeld und Suche nach Akku-Topics vorhanden, aktuell ohne Messwert | Boardverbindung und frische Spannungsquelle |
| Nice: Auftrag / Ziel | Keine Quelle, Werte bleiben null | Auftragsquelle und abgestimmte Felder |
| Nice: Richtung / Geschwindigkeit | Vertrag hat Richtung und gemessene Geschwindigkeit, aktuell keine Werte | Zustandsquelle und Odometrie |
| Nice: Route der letzten Minuten | Bis 300 lokale Kartenpunkte, maximal fünf Minuten | Frische Kartenpose; für Spielfeldroute zusätzlich Koordinatenzuordnung |
| Nice: Ereignisse | Panelereignisse über MQTT vorhanden | Fachliche Ereignisse Start/Ankunft/Rot/Blockade aus ihren Erzeugern |
| Dashboardbefehle | Keine Befehlsfunktion in der Empfangsansicht | Wie vorgeschlagen rein lesend belassen |

## Geräte und Transport

Im Projekt sind RM01–RM04 dokumentiert; ihre vollständige physische Inventur ist
offen. Die Bridge nimmt `--robot` entgegen, die temporäre Liveprüfung ist auf RM04
begrenzt. Der Test liest die Kennung aus `~/roboter_name`; diese Datei bleibt bei
Neustarts erhalten, eine korrekte physische Zuordnung muss vor Ort bestätigt werden.
Der aktuelle Zugang ist ein Jetson/Linux-Rechner mit ROS 2 und einer Python-MQTT-
Bridge. Die MQTT-Verbindung entsteht in der Bridge, nicht unmittelbar im Motorboard.
Weitere IDs sind technisch möglich; Anzahl und Registrierung sind organisatorisch offen.

Basis: `smartcity/robots/<ID>/`. `panel/state` überträgt JSON mit `robot_id`,
`boot_id`, `seq`, `received_at`, `payload`. Die Bridge sendet standardmäßig etwa
einmal pro Sekunde auch bei unverändertem Inhalt. `availability` enthält retained
`online` bzw. `offline`, QoS 1; MQTT-Last-Will ist `offline`, Keepalive 15 Sekunden.
Online bestätigt Panelabruf und Brokerzustellung, keine fehlerfreie Hardware.
Die Testansicht wertet fehlende Panelnachrichten nach fünf Sekunden als veraltet.
Ein Ausfall unterscheidet nicht sicher zwischen Ausschalten und Netzverlust.
Ein feststeckender Roboter benötigt zusätzlich Bewegungsrückmeldung und Fachlogik.

## Werte und Gültigkeit

| Wert | Typ / Einheit | Versand / Status |
|---|---|---|
| `payload.akku` | Zahl in V oder null | Mit Panelstatus; aktuell null |
| `payload.akku_prozent` | Zahl 0–100 oder null | Mit Panelstatus; aktuell null |
| `diagnostics.battery_v` | Messwertobjekt, V | Im gültigen gemeinsamen Zustand; aktuell fehlt die Quelle |
| `runtime.state` | Zustandsenum | Im gemeinsamen Zustand; aktuell fehlt die Quelle |
| `motion.measured_v_m_s` | Messwertobjekt, m/s | Im gemeinsamen Zustand; aktuell fehlt die Quelle |
| `route.direction` | Text oder null | Im gemeinsamen Zustand; aktuell fehlt die Quelle |
| `test/dashboard` | JSON, Must-/Nice-Zusammenfassung | Etwa 1 Hz, nur temporärer Testvertrag |
| `events` | JSON mit Panelereignissen | Bei neuen Ereignissen, nicht retained |

Messwertobjekte benötigen `status=valid` und einen endlichen Zahlenwert. null bedeutet
unbekannt, niemals Nullbewegung oder leerer Akku. Prozentwerte aus Spannung sind
eine Schätzung anhand 10,5–12,6 V und keine gemessene Restkapazität. Eine feste
Genauigkeit ist nicht nachgewiesen. Der offizielle gemeinsame Vertrag steht in
[schnittstellen-grundbetrieb.md](schnittstellen-grundbetrieb.md).

Die Prozessflags des Testpanels beweisen weder Stillstand noch Motorfreigabe.
Ohne gemeinsamen Zustand bleibt der fachliche Zustand unbekannt. Der vorhandene
Vertrag kennt u. a. GESTOPPT, TEST, BEREIT, SPURFOLGEN, VERKEHRSHALT und FEHLER.
Rot und Hindernis müssen durch die zugehörigen Haltegründe erklärt werden.
Laden wird ohne bestätigte Ladequelle nicht behauptet.

## Position

Das Zielsystem der WebApp ist 1954 × 2000 Planeinheiten, Ursprung links oben,
x nach rechts, y nach unten. Eine lokale SLAM-Pose in Metern ist damit nicht
automatisch kompatibel. Transformation, Maßstab, Orientierung und Referenzpunkte
sind noch nicht bestätigt. Keine erfundene Position oder Genauigkeit ausgeben.
Auch eine bekannte Straßenstrecke oder letzte Markierung wäre darstellbar;
deren belastbare Erkennung und Zuordnung zum Plan sind derzeit nicht nachgewiesen.

## Aktueller Gerätebefund und Einspielen

RM04 lieferte Kamera mit rund 8,5 FPS und Tiefenbilder. Akku, IMU, Odometrie und
beide LiDARs lieferten keine frischen Daten. Das Panel meldete laufenden micro-ROS-
Agent ohne angemeldetes Motorboard. Das ist eine Diagnose, kein Nachweis der
genauen Fehlerursache. Boardversorgung, Verbindung und ROS-Konfiguration vor Ort
prüfen; danach Telemetrie erneut abrufen. Keine Fahrt zum Prüfen erforderlich.

Die Änderungen liegen zunächst auf dem Entwicklungs-PC. SSH-Anmeldung war nicht
möglich. Bei laufendem Dateiserver auf 10.0.12.100 kann am Jetson aktualisiert werden:

```bash
curl -fsS http://10.0.12.100:8765/update_robot_live_test.py | python3 -
```

Der Updater startet den eigenen Stillstandstest neu und gibt eine neue Browser-URL
aus. Es werden keine Dashboardbefehle oder Fahrfreigaben ergänzt.

## Nachtrag: Desktop-Panel auf RM04

Die Ansicht „MQTT Daten“ ist im normalen Desktop-Panel integriert und auf RM04
installiert. Sie zeigt lokale Telemetrie und separat die MQTT-Zustellbestätigung.
Testreferenzen werden dort nicht als Messwerte angezeigt. Spannung hat drei
Nachkommastellen; „Akku erneut messen“ wartet bis zu fünf Sekunden auf eine neue
Nachricht des laufenden Akku-Sensors. Das ist kein eigener Hardware-Messbefehl.

Direkter Zugriff auf 10.0.12.107 wurde hergestellt. Der lokale Broker auf Port 1883
bestand Anmeldung, QoS-1-Bestätigung und unabhängigen Empfang. Das Desktop-Panel
läuft auf Port 8080 mit `--kein-netz`, ohne `--autostart`, und nutzt diesen lokalen
Testbroker. Die Desktopansicht wurde mit `?ansicht=mqtt` geöffnet. Die ursprüngliche
Desktop-Verknüpfung bleibt erhalten.

Vor dem Panelwechsel wurde eine reale Akkuspannung von etwa 12,734 V beobachtet.
Nach dem Wechsel kamen keine frischen Boarddaten mehr an. Der Agent besaß noch
eine Bindung an die alte Adresse 192.168.8.88; der Dienst
`m3pro-microros.service` wurde neu gestartet. Anschließend meldete sich das Board
noch nicht wieder am seriellen Agenten an. Ein erneuter Akkuabruf blieb ohne
Messwert. Physischer Board-Reset und erneute Prüfung stehen aus; die frühere
Spannung ist kein aktueller Messwert.

Anschließend wurde auf Nutzerwunsch auch der USB-Serielladapter gezielt per
`usbreset 001/007` zurückgesetzt (CP2104, VID/PID 10c4:ea60, Seriennummer
02E0E7F1). Der Agent war dabei gestoppt und wurde danach erneut gestartet.
Der USB-Reset meldete Erfolg; ein frischer Akkuabruf blieb trotzdem ohne
Messwert. Das ist kein nachgewiesener Reset des Mikrocontrollers selbst.
