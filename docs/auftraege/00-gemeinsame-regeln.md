# Gemeinsame Regeln für Entwicklungsaufträge

Du bearbeitest einen abgegrenzten Entwicklungsauftrag für `BKoewenig/smartcity-roboter`. Lies zuerst deine Auftragsdatei, dieses Dokument, die [Zieldefinition](../zieldefinition-grundbetrieb.md) und die relevanten Befunde im [Prüfbericht](../pruefung-grundbetrieb-2026-10-20.md). Vorhandene `AGENTS.md` im tatsächlichen Checkout beachten.

## Arbeitskopie und Startbasis

- Eine eigene Arbeitskopie oder ein eigener Worktree pro Entwickler/aktivem Agent. Keinen Branchwechsel und keine Produktänderungen im Orchestrator-Checkout `C:\SmartCity\research\review-github-20261020` oder in der alten Arbeitskopie `C:\SmartCity\smartcity-roboter` vornehmen.
- `origin` muss auf das Team-Repository zeigen. Remote-Stand und sauberen Arbeitsbaum prüfen; bestehende Änderungen bewahren. Neue Produktbranches beginnen auf dem aktuellen `origin/main`. Den tatsächlich verwendeten Basiscommit im Bericht nennen.
- Die Aufträge liegen zunächst auf `origin/codex/grundbetrieb`; dortige Dokumente bei Bedarf mit `git show origin/codex/grundbetrieb:docs/auftraege/<datei>` lesen. Nicht ungeprüft den gesamten Planungsbranch oder andere Entwicklerbranches zusammenführen.
- Nur den ausdrücklich beauftragten ersten Liefergegenstand umsetzen. Folgeaufträge sind Planung und beginnen nach gesonderter Zuteilung. Ist der Hauptstand inzwischen weiter, zunächst prüfen, welche Befunde bereits behoben wurden.

## Dateigrenzen und Schnittstellen

Die [Reservierungstabelle](README.md) ist verbindlich für diese Aufträge. Benötigst du eine fremd reservierte Datei oder eine neue öffentliche Schnittstelle, beschreibe die benötigte Übergabe und führe unabhängige Arbeit weiter. Keine konkurrierenden Gesamtumbauten.

C besitzt den einzigen gemeinsamen öffentlichen Zustands-/Fahrwunschvertrag. A besitzt Motorfreigabe, STOPP-Sperre und deren verbindliches Ergebnis; B besitzt Fahrentscheidung und Navigation. Ein interner Sicherheitszustand bei A ist kein zweiter Telemetrievertrag. Neue Adapter verwenden erst einen gemeinsam akzeptierten Vertragscommit.

`config/roboter.yaml` wird durch A integriert. B/C liefern nötige Änderungen als Übergabe. D besitzt gemeinsame Attrappen und den Testrunner. Neue testspezifische Helfer können in der jeweils eigenen Prüfdatei liegen. Bestehende fehlerhafte Testannahmen dürfen fachlich begründet geändert werden; Tests nicht nur an den aktuellen Code anpassen.

## Grundbetriebsgrenzen

Spurtreue und Schutz des gesamten Aufbaus haben Vorrang. Blockade bedeutet anhalten und warten; kein ungeprüftes Ausweichen, Greifen oder Kameraschwenken. Fehlende oder ungültige Pflichtdaten führen zu Halt. Rot verschwindet nicht durch Timeout. Ein Fahrwunsch ist keine Motorfreigabe, ein ausgegebener Befehl keine gemessene Bewegung.

Keine MQTT-Fernfahrt, Sonderrechte oder neuen Greiffunktionen in diesen Paketen aktivieren. Keine Messwerte oder Geräteabnahmen erfinden. Noch offene Infrastrukturregeln, Kalibrierwerte und Ersatzverfahren als offen führen; sie dürfen keine Bewegungsfreigabe begründen.

## Tests und Laufzeit

- Relevante vorhandene Tests und neue zielbezogene Regressionstests ausführen. Referenz vor Auftragsbeginn: sechs Skripte, 167 ausgegebene Einzelprüfungen auf `b9f6442`; das ist kein immer gleich bleibender Sollzähler.
- Logiktests mit künstlichen Daten, vollständige ROS-Simulation und reale Geräteabnahme getrennt berichten. Die historischen Prüfprobes in `docs/pruefungen/` reproduzieren Fehler; ihr Exitcode 0 bestätigt keine bestandene Sicherheitsprüfung.
- Die vorhandene ROS-Simulation verwendet Domain 77, Port 8080 und feste temporäre Dateien. Bis D2 die Laufzeit isoliert, keine parallelen vorhandenen Simulationsläufe im gleichen Laufzeitumfeld starten. Worktrees allein lösen diese Kollisionen nicht.
- Reale Motor-/Armtests sind kein Bestandteil eines reinen Softwareauftrags. Keine Installation oder Fahrbefehle auf Geräten ausführen, solange das Paket kein ausdrücklich abgestimmtes Gerätetestfenster umfasst.
- Zugangsdaten bleiben außerhalb von Repository, PR und Logs. Für MQTT synthetische Testidentitäten verwenden; keine realen Gerätezustände überschreiben.

## Lieferung und Prüfung

Kleine verständliche Commits auf dem eigenen Aufgabenbranch, anschließend ein Draft-PR nach `main`. Nicht selbstständig nach `main` zusammenführen oder auf `main` pushen. Keine fremden Branches überschreiben und keinen gemeinsamen Stand ungeplant per Force-Push ersetzen.

Im PR und zum Abschluss im Entwicklungs-Chat dieses Übergabeformat verwenden:

```text
Auftrag / verantwortlicher Mensch:
Status: vorbereitet | in Arbeit | zur Prüfung | abhängig von ...
Basiscommit / Branch / Liefercommit / PR:
Geänderte und reservierte Dateien:
Behobenes Verhalten und zugehörige GB-/A-Kennungen:
Öffentliche Schnittstellen verändert: nein | genaue Änderung:
Ausgeführte Prüfungen und tatsächliche Ergebnisse:
Offene Fehler / Messwerte / Geräte- oder Partnerabnahmen:
Benötigte Übergabe und vorgeschlagener nächster Auftrag:
```

Die erste Lieferung braucht einen klaren Abschluss. Weitere Funktionen nicht aus Bequemlichkeit in denselben PR aufnehmen. Der Orchestrator prüft den Übergabestand und koordiniert die Folgestufe.
