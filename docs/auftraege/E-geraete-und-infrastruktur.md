# Auftrag E Geräte Aufbau und Partnerfestlegungen

**Empfänger:** Geräte-/Testteam, Spielfeldteam, Ampelteam und Netzwerk-/Brokerteam. **Jetzt zu liefern:** E1, Inventar und konkrete offene Festlegungen. **Branch für Dokumentation:** `docs/gb-e1-geraete-infrastruktur`.

Grundlage ist die [Zieldefinition](../zieldefinition-grundbetrieb.md), insbesondere Abschnitte 3, 5, 8–10. Lies [gemeinsame Regeln](00-gemeinsame-regeln.md) und [Register](README.md). E1 erhebt und dokumentiert die Voraussetzungen für Entwicklung und spätere Abnahme. Es ist noch kein Auftrag, neue Software auf allen Robotern zu installieren oder autonome Fahrt/Armbewegung zu starten.

## E1a Geräteinventar RM01 bis RM04

Für jedes Gerät eine getrennte Datei `docs/geraete/RM01.md` bis `RM04.md` anlegen beziehungsweise vorhandene geprüfte Angaben ergänzen:

- Eindeutige Zuordnung Gerätename, MAC, Netz und physisches Gerät; keine Identität nur aus dem allgemeinen Hostnamen `yahboom` ableiten.
- Installierter Softwarecommit, Konfigurations-/Kalibrierstand und verwendete Kartenstände mit Datum und prüfender Person.
- ROS-Domain sämtlicher relevanter Treiber, micro-ROS-Agent, Kamera, eigener Programme und Panel. Vorhandene automatische Startquellen und alle Publisher auf `/cmd_vel` dokumentieren.
- Tatsächlich ankommende Daten je Quelle: Topic/Typ, Rate, Aufnahmezeit/Zeitsprung, gültige Werte, Ausfälle und Zuordnung zum eigenen Gerät. Ein Topicname allein ist kein gültiger Sensorstrom.
- Akku-/Board-/Motorstatus sowie bekannte Defekte und ungeprüfte Quellen. Ersatzverfahren oder abgeschaltete Pflichtprüfungen nicht stillschweigend als normalen Zustand ausweisen.

Lesende Inventur und vorhandene sichere Aufnahmen können sofort erfolgen. Keine Zugangsdaten in diese Dateien schreiben. Netzadresse ist Betriebsinformation, kein Ersatz für Geräteidentität. Quellen, Datum und Beobachtungsgrenze angeben.

## E1b Spielfeld und Fahrzeuggeometrie

Unter `docs/infrastruktur/` reale Maße und einen Prüfplan dokumentieren: Straßenbreiten, engste Kurven, Linien/Fuge, beide Überwege, Haltepositionen, Signal-/Schildstandorte und lichte Abstände zu Aufbauten. Vollständige Fahrzeughülle einschließlich Arm in Fahrstellung, Kamera und herausragender Teile berücksichtigen.

Kamera-/LiDAR-Lage und Koordinatenbezug messen beziehungsweise als offen kennzeichnen. Bildmaßangaben und öffentliche Robotermodelle sind keine eigene Vermessung. Die in der Software geschätzten 22 cm Kamerahöhe dürfen nicht als bestätigter Wert übernommen werden. Neue Aufnahmen nur mit eindeutiger Geräte-/Aufbauzuordnung ablegen.

Lieferung: tabellarische Messwerte mit Einheit, Messverfahren, Datum, Gerät/Aufbau, Unsicherheit und Freigabestatus. Noch fehlende Brems-/Latenz-/Watchdogmessungen als E2-Testplan vorbereiten, nicht schätzen.

## E1c Ampeln Schilder und Gegenverkehr

Das Ampel-/Spielfeldteam liefert für jede Zufahrt die eigene Signalzuordnung, Haltelinie, erlaubten Manöver, Gelb-/Ausfallregel und Schildbedeutung. Beide Zebrastreifen erhalten einen definierten zu prüfenden Querungsbereich und eine Verhaltensregel für Figuren/Objekte.

Für die gemeinsame Zweirichtungsstrecke ein abgestimmtes Verfahren dokumentieren, das gegensätzliche Einfahrt bis zur tatsächlichen Räumung verhindert. Einbieger bei K4/K5, Stillstand, Rückstau und langsame Fahrt berücksichtigen. Eine ungeprüfte feste Freigabezeit ersetzt den Räumungsnachweis nicht. Der Roboter löst Blockade nicht durch eigenständiges Verlassen der Linie.

Lieferung: versionierte Regel-/Zuordnungstabellen und ein gemeinsamer Gegenverkehrstestplan. Offene Partnerentscheidungen benennen; keine vermeintliche Freigabe erfinden. B nutzt diese Angaben für Straßenkarte/Navigation, A für sichere Bewegungsgrenzen.

## E1d Broker und Datenzugang

Das Netzwerk-/Brokerteam klärt mit C: erreichbarer Test-/Projektbroker, Port und Transport, Zugang über einen sicheren getrennten Kanal, erlaubte Topicstruktur, eindeutige Clientkennungen, Raten/Größen und Detaildatenformate. Für Kamera, Tiefe und Scans muss ein vereinbarter externer Zugriff mit Datenkennung möglich sein. Die Topic-/QoS-Beispiele der Zieldefinition bleiben Vorschläge bis zur Abstimmung.

Lieferung: Zugangsdokumentation ohne Geheimnisse im Repository sowie ein Plan für externes Abonnieren, Brokerunterbrechung, veraltete Daten und Wiederverbindung. Reconnect darf keine Motorfreigabe erzeugen. Hierdurch werden keine MQTT-Fernfahrbefehle freigegeben.

## Dateien Grenzen und Übergabe

E bearbeitet `docs/geraete/*`, `docs/infrastruktur/*`, `docs/abnahme/*` und ausdrücklich freigegebene Messdaten. Keine Produktionskonfiguration auf Geräten oder im Repository ändern; notwendige Parameter an A und Datenvertragsfragen an C geben. Änderungen an Zieldefinition, Aufgabenregister und Quellverweisen werden mit O abgestimmt.

Jede Information kennzeichnet „beobachtet/gemessen“, „vereinbart“ oder „offen“. Lieferung als kleiner Dokumentations-PR und Übergabebericht nach gemeinsamem Format. Zu offene Punkten eine zuständige Rolle und den benötigten Nachweis nennen; keine ungeklärte Aufgabe durch einen beliebigen Standardwert schließen.

## Folgeauftrag E2 erst nach Zuteilung

Nach geprüftem Softwarestand und abgestimmtem betreutem Testfenster reale Prüfungen durchführen: tatsächlicher STOPP und Sender-/Prozessausfall, Watchdog, Bremsweg/Latenz, Spur/Hülle/Fuge, blockierter Fahrweg und zulässige Manöver. Danach Signale/Überwege/Nachfahren, Zweigerätebetrieb und Infrastrukturverfahren, schließlich Viergerätezuordnung und Dauerlauf gemäß A01–A16.

Vor jedem Lauf Gerät, Betreiber, Software-/Regelkarten-/Konfigurationsstand und erwartetes Ergebnis festhalten. Ergebnisse sind tatsächliche Beobachtungen, keine Schlussfolgerung allein aus einem gesendeten Nullbefehl oder einem grünen Softwaretest. Nach einem Update beginnt für den neuen Stand ein neues nachvollziehbares Protokoll.
