# Änderungen im Fork-Branch `feat/mqtt-panel-telemetrie`

Stand: 22.10.2026. Diese Übersicht beschreibt die zusätzlichen Funktionen gegenüber dem gemeinsamen Ausgangsstand mit `main`. Das Referenzrepository `BBS-GuT/smartcity-roboter` wurde nicht verändert.

## Desktop-Panel und WebApp-Daten

- Die Ansicht **MQTT Daten** zeigt erreichbaren Roboter, Zustand, soweit verfügbar Position, aktuelle Aufgabe, Richtung, Geschwindigkeit und Ereignisse. Fehlende oder veraltete Werte werden als unbekannt angezeigt.
- Das Panel liest die Boardspannung aus frischen `/battery`-Nachrichten und zeigt Volt mit drei Nachkommastellen. Eine ungefähre Prozentanzeige ist eine Schätzung aus der Spannung, keine separate Messung.
- Der lesende MQTT-Adapter veröffentlicht Panelstatus und verfügbare Sensorinformationen. Er nimmt keine Fahrbefehle entgegen und erhält keinen Motorzugang.
- Ein Live-Test und Diagnoseberichte prüfen Brokerverbindung, Topic-Fluss und Datenlücken.

## MQTT-Betrieb

- Der Desktop-Start aktiviert die Bridge. Sie versucht zuerst den konfigurierten Projektbroker; bei Ausfall verwendet sie einen lokalen, nur auf dem Roboter erreichbaren Testbroker und prüft regelmäßig die Rückkehr des Projektbrokers.
- Die aktuelle Standardadresse des Projektbrokers ist `10.0.40.100:1883`. Eine vorhandene lokale `MQTT_HOST`-Konfiguration hat Vorrang und muss bei einer alten Adresse angepasst werden.
- Die [Broker-Anleitung](../../mqtt/BROKER_ANLEITUNG.md) erklärt Einrichtung, lokalen Betrieb ohne Schulnetz und den späteren Verbindungstest im Projektnetz.
- Broker-Zugangsdaten können lokal in `~/.config/smartcity/mqtt.json` liegen. Sie werden nicht ins Repository geschrieben.
- Die Integrationstests decken unter anderem Authentifizierung, bestätigte Veröffentlichungen, Brokerneustart und Quellenverlust ab.

## M1: gemeinsame Karte und vier Roboter

- Ein versioniertes MQTT-Schema, Kartenmodule und Transportcode bereiten den Austausch lokaler Kartenbeiträge und Roboterpositionen vor.
- Konfigurierbare Startplätze können lokale Positionen für die Anzeige ungefähr auf den Spielfeldplan abbilden. Diese Positionen tragen ausdrücklich eine unsichere Qualitätskennzeichnung.
- Routenhinweise erkennen gemeldete Belegungskonflikte. Sie verändern keine lokalen Haltebedingungen oder Fahrfreigaben.
- Eine verlässliche Kartenfusion und gemeinsame Kollisionsvermeidung sind **noch nicht einsatzbereit**: feste gemeinsame Marker, geprüfte Lokalisierung, identische Strecken-IDs und ein für alle vier erreichbarer Projektbroker fehlen beziehungsweise sind nicht nachgewiesen. Der lokale Testbroker verbindet die vier Roboter nicht miteinander.

## Installation und Boarddiagnose

- Ein Installer sichert bestehende Dateien, installiert Panel- und MQTT-Komponenten und kann anschließend das Panel öffnen und eine frische Akkumessung prüfen.
- Der Micro-ROS-Agent-Wrapper startet mit stabilem seriellen Gerätenamen und ohne das Fast-DDS-Profil des Panels. Ein bereits aktiver Agent wird beim Panel-Update nicht unnötig neu gestartet.
- Diagnosebefehle sind zeitlich begrenzt und melden ausdrücklich, wenn `/battery` keinen Publisher oder keine frische Nachricht hat.
- Am 22.10.2026 blieb die reale Akkumessung trotz erfolgreicher Installation unbekannt: Ein zusätzlicher Terminal-Agent wurde entfernt, doch das Board legt weiterhin weder `/YB_Node` noch einen `/battery`-Publisher an. Die Software zeigt keinen alten Wert als aktuelle Messung.

## Weiterführende Details

- [MQTT-Konfiguration und Tests](../../mqtt/README.md)
- [M1-Status und Voraussetzungen](../m1-mqtt.md)
- [WebApp-Datenabgleich](../webapp-datenabgleich.md)
- [Roboterlogs und Akku-Befunde](../pruefungen/2026-10-22-roboterlogs.md)

