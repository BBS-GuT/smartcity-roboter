# Roboterlogs und lokale Korrekturen vom 22.10.2026

Arbeitsstand im Fork `BKoewenig/smartcity-roboter`, Branch
`feat/mqtt-panel-telemetrie`. Das Referenzrepository
`BBS-GuT/smartcity-roboter` und sein `main` wurden ausschließlich gelesen.
Auf Nutzerwunsch wurden anschließend alle SSH-Versuche beendet. Die hier
beschriebenen letzten Korrekturen sind lokal; sie wurden noch nicht am Gerät erprobt.

## Tatsächlich gesicherte Daten

Das vollständige Archiv wurde schließlich mit SCP im alten Übertragungsmodus
heruntergeladen: 2.029.030 Bytes, 40 Dateien, entpackt 32.213.661 Bytes.
Es enthält Panel-, Kamera-, MQTT- und Akku-Probeprotokolle sowie den aktuellen
Kernel- und Agent-Journalstand. Lokaler Speicherort:
`logs/robot-diagnostics/complete/`; Archiv und Dateiliste mit SHA-256 stehen
nebenan. Dieser Ordner ist von Git ausgeschlossen. Rohlogs und lokale
Gerätesicherungen werden nicht in den Fork übernommen.

Das vorherige Bootjournal fehlt: Die entsprechende Datei enthält lediglich
`no persistent journal was found`. Manche Dateien sammeln mehrere Testläufe.
Historische Fehlermeldungen dürfen deshalb nicht als aktueller Einzelprozessfehler
interpretiert werden. Die Uhr wurde beim Boot mehrfach korrigiert; frühe
Kernel-Zeitstempel sind keine verlässlichen Echtzeiten.

## Belegte Befunde

| Bereich | Beleg | Bewertung |
|---|---|---|
| Akku vor dem Eingriff | Probe-JSON: 12,730806350708008 V, `/battery`, `std_msgs/msg/Float32`, Aufnahme am 22.10.2026 um 08:58:10 Europe/Berlin | Echte Messung funktionierte; kein aktueller Messwert |
| Board nach Nutzer-Neustart | Agent legt Client, Session, Participant, fünf Datawriter und fünf Datareader an | UART, Baudrate und XRCE-Kommunikation funktionieren grundsätzlich wieder |
| Aktueller Akkuempfang | Ein RELIABLE-Publisher auf `/battery` wird entdeckt; zwölf Sekunden Empfang mit Best-effort-QoS liefern keinen Wert | Fehlender Samplefluss; Best-effort-Subscriber ist mit RELIABLE-Publisher kompatibel |
| Agent-Implementierung | `ldd`: `librmw_fastrtps_shared_cpp`, `libfastrtps.so.2.6`, Micro XRCE-DDS 2.4 | Der Agent nutzt Fast DDS; die Environmentvariable für Cyclone beweist keine andere Agent-Implementierung |
| Agent-Startskript | Altes Skript prüft früh `/YB_Node`, manipuliert den ROS-Daemon und beendet Agenten mit SIGKILL | Fehleranfällige Kopplung an DDS-Discovery; stabiler Dienststart ersetzt diese Schleife |
| Akku-Probe | `FileNotFoundError` beim Ersetzen derselben temporären Datei; außerdem mehrfaches ROS-Shutdown | Überlappende Schreiber und fehlerhaftes Aufräumen sind konkrete Softwarefehler |
| Kamerapfad | Tausende `uvc_open`-Fehler, Gerätesperrfehler, wiederholte Orbbec-USB-Disconnects; später wieder laufende Streams | Intermittierende Kamera-/USB-Störung, kein Beweis eines Akkudefekts |
| Netzwerk | Wiederholte SSH-/HTTP-Abbrüche; NetworkManager verbindet das WLAN neu und bezieht `.107` | Separates Verbindungsproblem; dessen genaue Ursache ist nicht bestimmt |
| Ressourcen | Moderate CPU-/RAM-Last, kein Swapdruck, etwa 57–59 °C; kein OOM-/Unterspannungsnachweis im Kernel | Keine belegte Ressourcen- oder Unterspannungsursache |

Der Kernel meldet auch GPT-Prüfsummenabweichung und EXT4-Recovery nach unsauberem
Abschluss. Eine Kausalität zum Akku ist nicht nachgewiesen. Es wurde keine
Partitions- oder Dateisystemreparatur durchgeführt.

## Korrektur der früheren Diagnose

Die Aussage „Board antwortet gar nicht“ gilt nach dem Neustart nicht mehr:
Session und DDS-Writer sind vorhanden. Häufige `session re-established` und
ein Client-Key-Wechsel sind auffällig, beweisen allein aber weder einen
Hardwaredefekt noch einen Firmware-Reset. Ebenso ist die alte IP-Bindung ein
Diagnosehinweis, kein abschließend bewiesener Ursprung des Ausfalls.

Die beim absichtlichen USB-Port-Stromzyklus erzeugten CP210x-Fehler und der
unmittelbare `errno 5` waren Folgefehler dieses Eingriffs. Spätere erfolgreiche
Portöffnungen dürfen nicht mit diesem vorübergehenden Rebind-Fehler verwechselt werden.

## Live-Nachprüfung nach der Installation

Der Nutzer startete um 08:27 den micro-ROS-Agenten über den Installer neu. Der
Agent wurde aktiv und öffnete die serielle Schnittstelle. Um 08:28:20 meldete
sich der Board-Client `0x45033032` an; später folgten erneut Sitzungen. Im
aktuellen Journal fehlen jedoch nach diesem Neustart `create_participant` und
`create_datawriter`. Der ROS-Test in Domain 30 sah für `/battery` **0 Publisher**
und nach 15 Sekunden keine Nachricht (`echo_exit=124`). Panel und Agent verwenden
beide Domain 30; eine Domänenabweichung erklärt diesen konkreten Ausfall nicht.

Damit ist der Agent-Prozess allein kein Nachweis für eine funktionsfähige
Board-Brücke. Beim früheren kompletten Roboterstart wurden die Entities erzeugt.
Ein Software-Neustart des Roboters wird als Wiederherstellung geprüft. Ob
danach auch neue Batteriesamples fließen, ist noch offen; die frühere
Phase mit vorhandenem Publisher, aber ohne Sample darf nicht übergangen werden.

## Lokale Änderungen

- Der Agent-Wrapper übernimmt nicht länger das Projektprofil für Fast-DDS-
  Kamera-/Panelverkehr. Er nutzt die erforderlichen ROS-/Yahboom-/Agent-Setups,
  eine stabile Gerätekennung und begrenztes Warten. Ein eigenes Agentprofil
  kann explizit angegeben werden. Ob das den fehlenden Samplefluss am Gerät
  beseitigt, muss erst kontrolliert getestet werden.
- Die Akku-Probe schreibt über eindeutige temporäre Dateien. Ein fehlerhafter
  Datensatz ersetzt keinen gültigen vorherigen Datensatz.
- Doppeltes ROS-Shutdown wird vermieden. SIGTERM/SIGHUP führen beim Livetest
  durch das Aufräumen; ein Prozesslock verhindert parallele neue Livetests.
- Die Desktopansicht bleibt auf reale bzw. explizit unbekannte Angaben begrenzt.
  Spannungen werden mit drei Nachkommastellen angezeigt.

## Lokale Prüfung und Grenzen

Tests prüfen parallele Akku-Schreiber, ungültige Messwerte, Messalter, isolierte
Agent-Umgebung und fehlendes serielles Gerät ohne ROS oder Roboterzugriff.
Die lokalen MQTT-Integrationstests verwenden einen echten Testbroker und
unabhängigen Empfänger mit synthetischen Daten. Sie prüfen auch Authentifizierung,
PUBACK, Kamera-/Tiefen-/Scandaten, Quellenverlust und Brokerneustart.

Diese Softwaretests ersetzen keine reale Akkumessung. SIGTERM-/SIGHUP-Aufräumen
und der Linux-Prozesslock benötigen zusätzlich einen Linux-Lauf; ein erzwungenes
Windows-Testprozessende belegt kein geordnetes Linux-Shutdown.
