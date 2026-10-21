# Gemeinsame Regeln für Entwicklungsaufträge

**BBS-Stand vom 21.10.2026.** Schreibziel ist ausschließlich [BBS-GuT/smartcity-roboter](https://github.com/BBS-GuT/smartcity-roboter). Maßgeblich sind der aktuelle kleine BBS-Issueumfang und die bestätigte Dateiübernahme durch die Orchestrierung. Alte A–E-Auftragsvorlagen erteilen keinen neuen Auftrag.

Lies den zugeteilten Issue, diese Regeln, die [Zieldefinition](../zieldefinition-grundbetrieb.md) und vorhandene `AGENTS.md` im tatsächlichen Checkout. Der Ziel-/Abnahmeabgleich für das erlaubte Wegräumen bleibt in [#8](https://github.com/BBS-GuT/smartcity-roboter/issues/8) offen; die bestätigte Fachentscheidung steht unten. Der [Prüfbericht vom 20.10.2026](../pruefung-grundbetrieb-2026-10-20.md) enthält historische Ausgangsbefunde und ersetzt keine aktuelle Abnahme.

## Arbeitskopie, Startbasis und kleine Aufgaben

- Eine eigene Arbeitskopie oder ein eigener Worktree pro aktivem Entwickler oder Agent. Bestehende Änderungen bewahren; fremde Arbeitskopien und den Orchestrator-Checkout nicht umschalten oder für Produktänderungen verwenden.
- `origin` zeigt auf `https://github.com/BBS-GuT/smartcity-roboter.git`. Neue Aufgabenbranches beginnen auf aktuellem `origin/main`; tatsächlichen Basiscommit und späteren Liefercommit berichten. Keine alten Planungs- oder Entwicklerbranches ungeprüft zusammenführen.
- Eine Aufgabe hat ein konkretes Ergebnis, wenige ausdrücklich erlaubte Dateien und einen nachvollziehbaren Prüfweg. Nur den zugeteilten Liefergegenstand umsetzen. Weitere Probleme als eigene kleine Issues mit beobachtetem Fehler, Sollverhalten und Dateigrenze melden.
- Ist `main` inzwischen weiter, zuerst die noch offenen Punkte abgleichen. Eine historische Befundliste ist kein Beleg, dass der Fehler auf aktuellem `main` fortbesteht. Folgeaufträge beginnen nach gesonderter Zuteilung.

## Dateigrenzen und Schnittstellen

Pro Datei arbeitet genau ein aktiver Besitzer. Die bestätigte Reservierung im BBS-Issue und die Orchestrierung gelten; die [Registerübersicht](README.md) unterstützt den Abgleich. Ältere Bereichszuordnungen oder Dateilisten in Vorlagen vergeben keine fremden Dateien zusätzlich.

Benötigst du eine reservierte Datei oder eine neue öffentliche Schnittstelle, beschreibe die Übergabe und arbeite an unabhängigen Teilen weiter. Gemeinsame Produktdateien werden nacheinander auf dem bestätigten Integrationsstand bearbeitet; keine konkurrierenden Gesamtumbauten.

Den gemeinsamen Zustands-/Fahrwunschvertrag nicht duplizieren. Ein interner Sicherheitszustand ist kein zweiter Telemetrievertrag. Neue Adapter brauchen einen gemeinsam akzeptierten Vertragscommit. Änderungen an `config/roboter.yaml`, gemeinsamen Attrappen, Runner und Fachtests benötigen ebenfalls eine ausdrückliche Dateiübernahme. Keine Testannahmen nur an den momentanen Code anpassen oder Grenzwerte für grüne Tests lockern.

## Grundbetriebsgrenzen

Das bestehende **Wegräumen gehört nach ausdrücklicher Entscheidung des Projektinhabers zum Grundbetrieb**. Zieldefinition und erweiterte Abnahme werden über [#8](https://github.com/BBS-GuT/smartcity-roboter/issues/8) angeglichen. Diese Entscheidung ist keine neue Bewegungsfreigabe und kein Nachweis einer bereits bestandenen Geräteprüfung.

Spurtreue und Schutz des gesamten Aufbaus haben Vorrang. STOPP, Personen-/Tier-/Fahrzeughalt, rote Ampel, fehlende Pflichtdaten und Sensorunsicherheit bleiben sperrend, auch während des Räumablaufs. Rot endet nicht durch Timeout. Ein Fahrwunsch ist keine Motorfreigabe, ein ausgegebener Befehl keine gemessene Bewegung. Bei nicht belegten Schutzvoraussetzungen anhalten und warten.

Keine freie Umfahrung, MQTT-Fernfahrt, Sonderrechte oder zusätzlichen Greiffunktionen aus diesem Dokument ableiten. Erlaubtes Räumen erlaubt auch keinen davon unabhängigen Kameraschwenk am Überweg. Gemessene Bewegungs-/Greifbereiche, Kalibrierwerte und erforderliche Geräteabnahmen bleiben getrennte Nachweise; fehlende Werte oder Ersatzverfahren dürfen keine Freigabe begründen.

## Tests und Laufzeit

- Relevante bestehende Prüfungen und bei Verhaltensänderungen zielbezogene Regressionstests ausführen. Für reine Dokumentationskorrekturen genügen passende Markdown-/Linkprüfungen und die reguläre CI; keine künstlichen Softwaretests hinzufügen.
- Historischer main-Beleg vom 21.10.2026 nach PR #78: [Run 39589008257](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39589008257) auf `1c07fe4fdd509532359450dc11de3fb6666a1215`, drei Pflichtchecks erfolgreich und tatsächlich 21/21 Skripte. Testanzahlen sind Ergebnisse eines konkreten Stands, kein starres Soll.
- Main-Beleg zum Abschlussstand vom 21.10.2026 nach PR #102: [Run 39597759051](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39597759051) auf `8ee57b6cec55b5d2f4eb0c8de04d814344e9bfe8`, drei D1-Pflichtchecks erfolgreich. Auch dieser Beleg gilt nur für den genannten Commit; für eine neue Lieferung zählt deren aktuelle CI.
- Reine Softwareprüfung mit künstlichen Daten, vollständige ROS-Simulation und reale Geräteabnahme getrennt berichten. Historische Fehlerprobes in `docs/pruefungen/` reproduzieren Befunde; ihr Exitcode 0 bestätigt keine bestandene Sicherheitsprüfung.
- Parallele Simulationen benötigen getrennte Domains, Ports und Karten-, Log-, Lern- und temporäre Pfade. Ohne bestätigte Trennung keine parallelen vorhandenen Simulationsläufe im gleichen Laufzeitumfeld starten; Worktrees allein isolieren diese Ressourcen nicht.
- Reale Motor-/Armtests und Installationen auf Robotern gehören nur in ein ausdrücklich abgestimmtes Gerätetestfenster. Ein reiner Softwareauftrag erteilt dafür keinen Auftrag.
- Zugangsdaten bleiben außerhalb von Repository, PR und Logs. Für MQTT synthetische Testidentitäten verwenden; keine realen Gerätezustände überschreiben.

## Automatischer Review und formale Freigabe

Der native Codex-Reviewer ist im BBS-Repository für alle PRs aktiviert. Bei prüfbereiten PRs läuft Code Review automatisch beim Öffnen und bei jedem neuen Push; Security Review läuft zusammen mit Code Review. Entwürfe als Draft kennzeichnen, zur Übergabe prüfbereit machen und den tatsächlichen Bot-Status des aktuellen Liefercommits prüfen.

Code-Reviews übernimmt der native Reviewer. Die Orchestrierung und ihre Entwicklungsagenten führen keine eigenen Code-Reviews durch. Sie koordinieren Dateibesitz, Abhängigkeiten, CI- und Botstatus sowie die Integration. Automatische Befunde innerhalb des beauftragten Umfangs beheben; zusätzliche Dateibesitzer oder neue Probleme über kleine Folgeaufträge koordinieren.

Das aktive [main-Ruleset 25533179](https://github.com/BBS-GuT/smartcity-roboter/rules/25533179) verlangt eine formale GitHub-Freigabe, aktuelle main-Basis, erledigte Reviewgespräche und die drei unveränderten D1-Pflichtchecks von GitHub Actions, App-ID `15368`:

- `D1 / Python-Syntax (3.10)`
- `D1 / Shell-Syntax (bash)`
- `D1 / Softwaretests (Ubuntu 22.04, Python 3.10)`

Alte Freigaben verfallen bei neuen Commits. Force-Push und Löschen von main sind gesperrt; keine Bypass-Ausnahmen oder Schutzabsenkung zum Abschluss eines Auftrags. Ein weiterer Chat unter demselben PR-Autorenkonto ist kein unabhängiges GitHub-Approval.

Die Codeowner-Regel und die Steuerdatei-Zuordnung aus [PR #91](https://github.com/BBS-GuT/smartcity-roboter/pull/91) sind integriert. Steuerdateien brauchen die vorgesehene unabhängige Codeowner-Freigabe und werden nicht durch die App selbst freigegeben. Die separate Freigabe-App `5409664` arbeitet; Installation [#90](https://github.com/BBS-GuT/smartcity-roboter/issues/90) und die echte, von GitHub angerechnete `APPROVED`-Abnahme [#95](https://github.com/BBS-GuT/smartcity-roboter/issues/95) sind am 21.10.2026 abgeschlossen. Die Installation hat Contents-Schreibrecht, der kurzlebige Job-Token bleibt Contents-lesend; die Environment ist auf `main` beschränkt. Für diesen Abschluss ist keine weitere App-, Ruleset- oder Secret-Konfiguration erforderlich. Schlüssel bleiben außerhalb des Repositorys. Eine native Botmeldung allein ist kein formales Approval; für jede neue Lieferung müssen CI, Code Review und die angerechnete App-Freigabe zum aktuellen Head passen. Ein für diesen Head vorhandener Security Review muss ebenfalls sauber abgeschlossen sein; fehlende oder ältere Security-Ergebnisse sperren die derzeitige Freigabebrücke nicht. Details und datierte Nachweise stehen im [Freigabebetrieb](../entwicklung/codex-mergefreigabe.md). Auto-Merge wird nicht aktiviert.

## Lieferung und Übergabe

Kleine verständliche Commits auf dem eigenen Aufgabenbranch und ein eigener PR nach BBS-`main`. Keine fremden Branches überschreiben, keinen Force-Push auf gemeinsame Stände und keinen eigenständigen Merge durch den Entwickler. Ein vorbereiteter PR oder ein grüner Testlauf ist noch keine Integration oder Geräteabnahme.

Im PR und zur Übergabe dieses Format verwenden:

```text
BBS-Issue / verantwortlicher Mensch / bestätigte Dateiübernahme:
Status: vorbereitet | in Arbeit | zur Prüfung | abhängig von ...
Basiscommit / Branch / Liefercommit / PR:
Geänderte und reservierte Dateien:
Behobenes Verhalten und zugehörige GB-/A-Kennungen:
Öffentliche Schnittstellen verändert: nein | genaue Änderung:
Prüfungen, tatsächliche Ergebnisse und aktuelle CI-/Botbelege:
Offene Fehler / Messwerte / Geräte- oder Partnerabnahmen:
Benötigte Übergabe und nächster kleiner Auftrag:
```

Die erste Lieferung braucht einen klaren Abschluss. Keine weiteren Funktionen beiläufig aufnehmen. Issues erst nach tatsächlicher Integration als geliefert einordnen; offene Geräte- und Partnerabnahmen bleiben bis zu ihrem eigenen Nachweis offen.

## Historische Quellplanung

Die frühere Planung auf `codex/grundbetrieb` im [Quell-PR #11](https://github.com/davidheinrich73/smartcity-roboter/pull/11) gehört zum alten Repository und ist kein verbindlicher Startbranch für neue BBS-Aufgaben. Die ursprünglichen A–E-Pakete bleiben Vorlagen, keine zusätzliche Beauftragung.

Der damalige Prüfstand [b9f6442](https://github.com/davidheinrich73/smartcity-roboter/commit/b9f6442) umfasste sechs Skripte mit 167 ausgegebenen Einzelprüfungen. Das ist eine historische Ausgangsreferenz; weder sechs/167 noch die im Beleg nach PR #78 ausgeführten 21 Skripte sind ein dauerhaftes Testsoll.
