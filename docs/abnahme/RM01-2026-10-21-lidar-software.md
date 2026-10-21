# RM01: versionsbezogene LiDAR-Softwarebefunde, 21.10.2026

**Belegübergabe [#59](https://github.com/BBS-GuT/smartcity-roboter/issues/59), Elternaufgabe [#58](https://github.com/BBS-GuT/smartcity-roboter/issues/58).** Untersucht wurde der auf RM01 installierte und mit BBS-main verglichene Commit **`d92e366907fd538c377c272250a0e2d75120b5e2`**. Dieses Paket dokumentiert Befunde und den bereits vorhandenen Offline-Entwurf. Es implementiert keinen Produktfix und nimmt kein Gerät ab.

Der Quellabgleich erfolgte auf UTF-8-Inhalt mit zu LF normalisierten Zeilenenden. [Quellen und SHA256](../pruefungen/lidar-20261021/quellen.json) enthalten das genaue Verfahren und zusätzlich SHA256 der unveränderten öffentlichen Git-Blobbytes. Die synthetischen Reproduktionen laden ausdrücklich diesen fixierten Commit, unabhängig davon, ob der aktuelle Arbeitsbranch inzwischen weiter ist.

## Datenbezug und Grenzen

Die ursprünglichen statischen Referenzmessungen fanden am 21.10.2026 an RM01 statt. Beide Sensoren lieferten Rohdaten. Mit dem verbesserten hohen Ziel ergaben die direkten Strahlmediane:

| Quelle/Aufstellung | Nutzerreferenz 50 cm | Nutzerreferenz 100 cm |
|---|---:|---:|
| Vorne rechts, `/scan1` | 49.8 cm | 100.2 cm |
| Hinten links, `/scan0` | 49.7 cm | 99.7 cm |

Dies sind Vergleiche mit der aufgestellten Nutzerreferenz einschließlich unbekannter Maß-/Aufstellunsicherheit, kein unabhängig nachgewiesener Millimetergenauigkeitswert. Es wurde kein pauschaler Distanzoffset gespeichert. Frühere ungeeignete Zielaufstellungen bleiben im Originalbestand erhalten.

Die spätere Analyse nutzte gespeicherte Daten **rein offline erneut**: vier endgültige Referenzaufstellungen mit 832 Scans. Sie ist keine neue physische Messung. Der vollständige Referenzbestand umfasst sieben Läufe mit 2,892 Scans und 1,446,000 Entfernungswerten einschließlich ungültiger Nullwerte. Große Originalpakete bleiben im bestehenden Geräteprüfbestand; Namen, SHA256 und Aufbewahrungsumfang stehen in [quellen.json](../pruefungen/lidar-20261021/quellen.json). Diese Übergabe veröffentlicht keine Rohaufnahme-, Geräteidentitäts- oder Zugriffsdaten.

Die verwendeten Werksmodell-Translationen sind ein nachvollziehbarer Rechenbezug, **keine unabhängige RM01-Einbauvermessung**. Der Modellhash ist dokumentiert; die ursprüngliche Geräte-URDF wird nicht mitkopiert. Die Quellen-/Einbaubestätigung bleibt [#66](https://github.com/BBS-GuT/smartcity-roboter/issues/66).

## Befunde und synthetische Gegenkontrollen

Alle folgenden Quellenzeilen beziehen sich auf den fixierten Commit. Die ausführbaren kleinen Reproduktionen und ihre Bedeutung stehen im [Paket-README](../pruefungen/lidar-20261021/README.md).

### 1. Ungültig/leere Messung wird zu „frei“ — #60

`lib/lidar.py:19–34` verwirft ungültige Werte und liefert bei keinem gültigen Punkt im Bereich `inf`. `punkte_xy:62–66` liefert dann keine Punkte, `fahrschlauch:107–108` kein Objekt. Die KI deutet dies in `ki/zentrale.py:373–388` als frei; `lidar_hinten:358–364` liefert bei leerem Streifen sogar den Ersatzwert 5 m. Die zusätzliche LiDAR-Haltprüfung in `line_follower/line_follower.py:240–254` sperrt einen frisch empfangenen Scan mit `inf` ebenfalls nicht.

Unter absichtlich gültigen übrigen Kamera-/Linien-/KI-Voraussetzungen reicht der Effekt bis zu `entscheide` und `steuern`: ausschließlich Nullwerte, NaN oder leere Scans erzeugen im historischen Code einen Nichtnullbefehl an den **lokalen nachgebauten Publisher**. Bei `drive=False` bleiben dessen Fahrpublikationen dagegen null. Die Kontrollen Gesamtausfall beider Empfangskanäle und gültiges Hindernis bei 10 cm führen zu Nullbefehlen.

Das belegt die Softwarewirkung, keine reale Motorbewegung, Bremszeit oder externe Hardwarefreigabe. Bei ausschließlich `+inf` bleibt zusätzlich die konkrete Treiberkodierung „kein Echo bis zur Reichweitengrenze“ zu klären; die Null-/NaN-/Leerdatenbefunde hängen davon nicht ab.

### 2. Ein frischer Kanal verdeckt fehlende/veraltete Quellen — #61

KI und Linienfolger prüfen hier, ob irgendein gespeicherter Scan frisch ist. Die Reproduktion lässt einen konfigurierten Kanal fehlen oder altern, während der andere frische gültige Daten enthält. Die betroffenen Methoden melden dann keinen eigenen Quellenfehler.

Welche Quellen pro tatsächlichem Fahr-/Manöverbereich zwingend benötigt werden, ist fachlich festzulegen. Daraus folgt keine Behauptung, dass immer beide Sensoren in jedem Zustand Pflicht sein müssen. Die spätere Sektor-/Abdeckungsaufgabe wird separat durch #58 koordiniert; eine hohe globale Gültigkeitsquote ersetzt nicht die relevante Bereichsabdeckung.

### 3. Frischer Empfang ersetzt Aufnahmefrische — #62

`ki/zentrale._scan:290–296` und `line_follower.on_scan:164–168` speichern `time.time()` beim Empfang. Die untersuchten Prüfwege validieren nicht den Aufnahmeheader. Ein gerade empfangener Scan mit 30 s altem Header wird deshalb wie ein frischer Scan behandelt. Bei vollständig altem Empfang reagiert die Gegenkontrolle dagegen.

Aufnahmezeit, monotone Empfangszeit, Fortschritt und Zeitbasis müssen getrennt bewertet werden. Reale Zeitgrenzen und die Bestätigung der Gerätezeitbasis bleiben offen.

### 4. Sensorursprünge fehlen im gemeinsamen Roboterbezug — #63/#64

`punkte_xy` berücksichtigt Winkel, jedoch keine Translation. Die KI verwendet die sensorlokalen Punkte direkt für Fahrbereich und Rückraum. Drei synthetische Beispiele zeigen mit dem dokumentierten Werksmodell eine falsche Innen-/Außenzuordnung. Beispielsweise wird ein Sensorpunkt (0.30, 0.20) m vorne rechts im Werksmodell zu Basis-(0.40766, 0.10922) m. Im angenommenen 30-cm-Streifen liegt er danach innerhalb statt außerhalb. Umgekehrte und hintere Beispiele dienen als Gegenkontrollen.

Die korrekte Rechenoperation ist `p_basis = R(yaw) * p_sensor + (x,y)`, genau einmal und mit geprüftem Quellen-/Framebezug. Dies ist von radialer Distanzkalibrierung zu unterscheiden. Eine bereits transformierte Quelle darf nicht nochmals verschoben werden. Hüllengeometrie und Werkswerte sind dadurch noch nicht am Gerät bestätigt.

### 5. Letzter Schutz folgt nicht dem konkreten Fahrvektor — #65

`on_scan:166–168` wählt vorne/hinten aus dem allgemeinen Parameter `direction`. `entscheide:345–363` führt diese Prüfung vor der Auswertung des KI-Manöverwunsches aus. Der spätere Wunsch kann aber rückwärts, seitwärts oder drehend sein.

Die synthetische Gegenprobe enthält vorn 3 m, hinten 10 cm Hindernis und einen frischen KI-Rückwärtswunsch von -0.05 m/s. Mit `direction=+1` erreicht dieser Wunsch die lokale Publisherattrappe; mit `direction=-1` sperrt die positive Schutzkontrolle korrekt. Nicht behauptet wird, dass die aktuelle KI unter identischen realen Bedingungen selbst diesen Wunsch erzeugt.

## Offline-Entwurf und Zuordnung der nächsten Aufgaben

Der [archivierte Entwurf](../pruefungen/lidar-20261021/prototyp.py) stammt aus der bereits abgeschlossenen lokalen Analyse. Er wird hier nicht als zweites Produktmodul integriert:

- Strahlgültigkeit erhalten und unbekannt von verwertbar trennen: [#60](https://github.com/BBS-GuT/smartcity-roboter/issues/60), spätere Sektoraufgabe unter #58.
- Explizite Pflichtquellen mit Fehlergründen prüfen: [#61](https://github.com/BBS-GuT/smartcity-roboter/issues/61).
- Empfang und Aufnahme getrennt validieren: [#62](https://github.com/BBS-GuT/smartcity-roboter/issues/62).
- Reine Rotation/Translation und Frameprüfung: [#63](https://github.com/BBS-GuT/smartcity-roboter/issues/63), anschließend Verbraucher [#64](https://github.com/BBS-GuT/smartcity-roboter/issues/64).
- Der finale konkrete Fahrvektor und die gesamte Fahrzeughülle sind **nicht im Prototyp integriert**: [#65](https://github.com/BBS-GuT/smartcity-roboter/issues/65).

Der Entwurf liefert nur Datenverwertbarkeit, weder Hindernisfreiheit noch Motorfreigabe. Seine strenge Demo-Regel „alle ausdrücklich kritischen Strahlen gültig“ und synthetischen Zeitlimits sind keine abgenommenen Geräteeinstellungen. 19 zielgerichtete Testmethoden prüfen den begrenzten Entwurf. Die historischen Fehlerbeobachtungen sind davon getrennt; sie sind keine erwünschten Produktregressionen.

Die spätere Integration verwendet den bestehenden C1-Quellen-/Zeit-/Zustandsbezug ([#13](https://github.com/BBS-GuT/smartcity-roboter/issues/13), [#14](https://github.com/BBS-GuT/smartcity-roboter/issues/14)); diese Übergabe ändert keinen öffentlichen Vertrag, kein Panel, MQTT oder Kartograf. Geometrie, Qualität und tatsächlicher Fahrwunsch müssen am Ende in einer gemeinsamen abschließenden Sperre zusammenwirken.

## Prüf- und Übergabestand

Historische Fehlerreproduktion, Entwurfstests und lokale Software-Gesamtprüfung werden im [README](../pruefungen/lidar-20261021/README.md) und dem zugehörigen Ergebnisnachweis getrennt ausgewiesen. Ein Exitcode 0 des historischen Werkzeugs bedeutet ausschließlich: **beschriebene Fehlersignatur am fixierten Stand reproduziert**. Ein Produktfix muss gesonderte Tests mit dem erwünschten Halt-/Unbekanntverhalten liefern.

Verantwortlich für diese Lieferung ist der Generalprüfchat im Auftrag der Orchestrierung, Dateigrenze ausschließlich dieser Bericht und `docs/pruefungen/lidar-20261021/`. Neue Arbeitskopie und eigener Dokumentationsbranch ab aktuellem BBS-main; bisherige lokale Belege bleiben unverändert. Keine Produkt-/Konfigurationsänderung, Installation, Roboterverbindung, ROS-Gesamtsimulation oder Geräte-/Brokerprüfung im Rahmen dieser Übergabe. A11/A12 und A01–A16-Gesamtabnahme bleiben offen; Gerätefortsetzung ist [#67](https://github.com/BBS-GuT/smartcity-roboter/issues/67). Eine fachliche Fremdfreigabe und Integration des Draft-PR stehen aus.
