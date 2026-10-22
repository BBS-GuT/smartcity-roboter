# Entwicklungsauftrag D: Tests, CI und Repositoryregeln

**Datierter BBS-Betriebsnachweis: 21.10.2026, main `ac5355df5e14352d0fe4ce4cd9a1e67369e9aa42`.** D1-Basis, main-Schutz und formale Freigabe-App sind geliefert und abgenommen; der spätere Integrationsstand der Dokumentationsaufträge steht unten. Eine neue Testinfrastruktur oder eine zweite Schutzregel ist nicht zu beauftragen.

Schreibziel ist ausschließlich [BBS-GuT/smartcity-roboter](https://github.com/BBS-GuT/smartcity-roboter), `origin=https://github.com/BBS-GuT/smartcity-roboter.git`. Neue kleine Aufgaben beginnen in eigener Arbeitskopie auf einem zugeteilten Branch ab aktuellem `origin/main`.

Die aktuellen [gemeinsamen Regeln](00-gemeinsame-regeln.md), das [Register](README.md) und die [CI-Betriebsanleitung](../entwicklung/D1-ci-betrieb.md) sind verbindliche BBS-Dokumente. Darin ausdrücklich als historisch gekennzeichnete Quellangaben sind keine neuen Einrichtungsaufträge. Die Orchestrierung vergibt weiterhin Aufgaben und Dateireservierungen. Ein freies Dokument oder ein zusätzliches KI-Fenster ist keine Zuteilung.

## Gelieferter D1-Betrieb

[D1 #4](https://github.com/BBS-GuT/smartcity-roboter/issues/4) und [Repositoryschutz #28](https://github.com/BBS-GuT/smartcity-roboter/issues/28) sind abgeschlossen. `letsc4` ist inzwischen Repositoryadministrator und Organisationsinhaber von BBS-GuT. Die frühere fehlende Adminberechtigung ist keine aktuelle Blockade mehr.

Der vorhandene Runner `scripts/pruefen.py` führt `tests/test_*.py` dynamisch in getrennten Prozessen aus. Fehler, Timeouts, fehlende Abhängigkeiten und gemeldete Skips verhindern einen Gesamterfolg. Historische Fehlerprobes unter `docs/pruefungen/` zählen nicht als bestandene Regressionstests. Der lokale Aufruf bleibt:

```sh
python scripts/pruefen.py
```

Die getestete CI-Basis ist Ubuntu 22.04/Python 3.10 mit `requirements-test.txt`; Paketpins und Zeitlimits werden in diesem Dokumentationsauftrag nicht geändert. Die drei Pflichtchecks aus GitHub Actions, App-ID `15368`, heißen exakt:

- `D1 / Python-Syntax (3.10)`
- `D1 / Shell-Syntax (bash)`
- `D1 / Softwaretests (Ubuntu 22.04, Python 3.10)`

Datierte CI-Belege vom 21.10.2026 unterscheiden PR und main:

- [Erster BBS-PR-Lauf an PR #57](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39571559910): drei erfolgreiche Checks und 21/21 Skripte auf dem PR-Testmerge. Dieser Prüf-PR wurde ohne Merge geschlossen.
- [Historischer main-Pushlauf nach PR #83](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39579961109): drei erfolgreiche Pflichtchecks und 21/21 Skripte auf dem damaligen main `2e70550c88e30291c0db07619cff574a6ff1655b`.
- [Main-Pushlauf nach PR #102](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39597759051): erfolgreiche CI auf dem damaligen main `8ee57b6cec55b5d2f4eb0c8de04d814344e9bfe8`; dieser Beleg schreibt spätere main-Stände nicht automatisch fort.

Die Zahl 21 ist das Ergebnis dieser Stände, kein festes Soll. Neue Fachtests werden vom Runner mitentdeckt; sie dürfen nicht zur Erhaltung einer festen Zahl ausgelassen werden.

## Vorhandenen main-Schutz verwalten

Das aktive [Ruleset 25533179](https://github.com/BBS-GuT/smartcity-roboter/rules/25533179) verlangt PR, mindestens eine gültige Freigabe, Verwerfen alter Freigaben bei neuen Commits, erledigte Reviewgespräche und alle drei D1-Pflichtchecks mit aktueller main-Basis (`strict=true`). Force-Push und Löschen von main sind gesperrt; es gibt keine Bypass-Ausnahmen, auch nicht für Administratoren.

Codeowner-Freigaben sind im Ruleset aktiviert; `.github/CODEOWNERS` ist mit [PR #91](https://github.com/BBS-GuT/smartcity-roboter/pull/91) auf main integriert und schützt die dort aufgeführten Steuerungsdateien. `CODEOWNERS` ersetzt keine Dateireservierung. Gemergte Aufgabenbranches werden durch die aktivierte Repositoryoption automatisch gelöscht; die Löschsperre für main bleibt bestehen.

Der unabhängige native Codex-Code-Review läuft auf jedem Push und übernimmt die Produktreviews. Der zusätzliche Security Review ist dauerhaft optional und startet nicht mehr allgemein automatisch. Aktueller sauberer Code Review und Pflicht-CI bleiben erforderlich; fehlende oder laufende optionale Security Reviews allein blockieren nicht, bekannte aktuelle Befunde bleiben blockierend. Die separate formale Freigabe-App aus [#90](https://github.com/BBS-GuT/smartcity-roboter/issues/90)/[PR #91](https://github.com/BBS-GuT/smartcity-roboter/pull/91) ist eingerichtet; [#95](https://github.com/BBS-GuT/smartcity-roboter/issues/95) belegt ihre von GitHub angerechneten `APPROVED`-Reviews. Die Nachträge [#98 / PR #99](https://github.com/BBS-GuT/smartcity-roboter/pull/99) und [#100 / PR #102](https://github.com/BBS-GuT/smartcity-roboter/pull/102) sind integriert. Contents der Installation ist schreibend, der kurzlebige Job-Token bleibt Contents-lesend. Eine bloße Botmeldung ist kein formales Approval; die App überträgt nur einen sauberen nativen Review und erfolgreiche Pflicht-CI für den aktuellen Head. Steuerungsdateien brauchen weiterhin eine unabhängige menschliche Codeowner-Freigabe. Einzelheiten und datierte Abnahmebelege stehen in der [Freigabeanleitung](../entwicklung/codex-mergefreigabe.md). Auto-Merge ist nicht eingerichtet. Ein anderer KI-Chat unter demselben Autorenkonto ist keine unabhängige GitHub-Freigabe.

[PR #54](https://github.com/BBS-GuT/smartcity-roboter/pull/54) zu #68 ist auf der genannten Basis integriert: `AGENTS.md` und `docs/entwicklung/D-reviewbot.md` sind geliefert. Dieser Auftrag ist abgeschlossen und keine erneute Dateizuteilung.

Die ursprüngliche Lieferung dieses Dokuments zu [#93 / PR #94](https://github.com/BBS-GuT/smartcity-roboter/pull/94) erfolgte auf Branch `docs/gb-d1-auftragsstatus`. Sie ist integriert und abgeschlossen, keine erneute Zuteilung. Der begrenzte spätere Begleitdoku-Abgleich in PR #80 steht unten; er ändert keine Workflows, Tests oder Produktdateien.

## Integrierte Dokumentationsaufträge und laufender Abgleich

- [#69 / PR #92](https://github.com/BBS-GuT/smartcity-roboter/pull/92): Beitrags- und Betriebsanleitung integriert, Issue abgeschlossen. Dieser frühere Auftrag reserviert `CONTRIBUTING.md` und `docs/entwicklung/D1-ci-betrieb.md` nicht mehr.
- [#96 / PR #97](https://github.com/BBS-GuT/smartcity-roboter/pull/97): gemeinsame Regeln integriert und verbindlich, Issue abgeschlossen. Keine aktive Reservierung aus dieser Lieferung.
- [BBS-PR #80](https://github.com/BBS-GuT/smartcity-roboter/pull/80), Branch `docs/gb-bbs-auftragsabgleich`: laufender Register-/Begleitdoku-Abgleich der Orchestrierung für `docs/auftraege/README.md`, `docs/auftraege/L-lidar-qualitaet-und-geometrie.md`, `CONTRIBUTING.md` und diese D1-Auftragsdatei. Die erweiterte Dateiübernahme ist im PR dokumentiert; sie eröffnet die abgeschlossenen D-Aufträge nicht erneut. Der importierte Produkt-Merge `d92e366` gehört zum früheren Quellrepository und dessen gleich nummeriertem PR #80, nicht zu diesem BBS-PR.

Jede Lieferung nennt Basis, Head, genaue Dateien, tatsächliche CI und offene Abnahmen. Vor Merge müssen der aktuelle Codex-Review, CI und die erforderliche unabhängige Freigabe vorliegen. Kleine Folgefehler werden als eigene Aufgaben mit Dateigrenze vergeben. Produktmodule und fachliche Tests bleiben bei ihren zugeteilten Besitzern; keine Erwartungen oder Grenzwerte für einen grünen Lauf abschwächen.

D1-Softwareprüfungen greifen nicht auf Roboter oder Projektbroker zu. Sie ersetzen keine Fahr-, Sensor- oder Greifabnahme. Erlaubtes Grundbetriebsräumen bleibt Bestandteil der Fachaufträge; sein Zieldefinitionsabgleich und seine Schutzbedingungen gehören zu [#8](https://github.com/BBS-GuT/smartcity-roboter/issues/8).

## Historische Quellplanung vom 20.10.2026

Diese Bezüge dokumentieren das frühere Repository und sind keine aktuellen Schreibziele oder Einrichtungsaufträge:

- Die ursprünglichen Aufträge lagen auf `codex/grundbetrieb` im [Quell-PR #11](https://github.com/davidheinrich73/smartcity-roboter/pull/11).
- Der damalige Quellstand [d991765](https://github.com/davidheinrich73/smartcity-roboter/commit/d991765) war mit 13/13 Softwaretestskripten grün. Runner, getestete Paketumgebung, CI sowie Beitrags-/PR-/Aufgabenvorlagen waren die ursprünglichen D1-Liefergegenstände.
- Die damaligen Quellenissues [#15](https://github.com/davidheinrich73/smartcity-roboter/issues/15), [#50](https://github.com/davidheinrich73/smartcity-roboter/issues/50), [#68](https://github.com/davidheinrich73/smartcity-roboter/issues/68) und [#69](https://github.com/davidheinrich73/smartcity-roboter/issues/69) wurden im BBS-Repository zu #4, #28, #44 und #45. Die frühere Adminaktion und die alten Ergänzungen sind abgeschlossen.

Ein historisch vorgemerktes Folgepaket für parallele ROS-Simulationen braucht weiterhin eine eigene Zuteilung und getrennte Domains, Ports sowie Karten-, Log-, Lern- und temporäre Pfade. Bis dahin nur einen vorhandenen Simulationslauf im gleichen Laufzeitumfeld starten. Dieser Dokumentationsauftrag verändert `scripts/simulation.sh` und andere Startpfade nicht.
