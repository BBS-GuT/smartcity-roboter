# Entwicklungsauftrag D: Tests, CI und Repositoryregeln

**BBS-Betriebsstand: 21.10.2026.** D1-Basis und main-Schutz sind geliefert; die offenen Dokumentations- und Freigabeaufgaben stehen unten. Eine neue Testinfrastruktur oder eine zweite Schutzregel ist nicht zu beauftragen.

Schreibziel ist ausschließlich [BBS-GuT/smartcity-roboter](https://github.com/BBS-GuT/smartcity-roboter), `origin=https://github.com/BBS-GuT/smartcity-roboter.git`. Neue kleine Aufgaben beginnen in eigener Arbeitskopie auf einem zugeteilten Branch ab aktuellem `origin/main`.

Für Repositoryadresse, Rechte und CI gilt dieser datierte BBS-Stand. Abweichende ältere Angaben in [gemeinsamen Regeln](00-gemeinsame-regeln.md), [Register](README.md) und [CI-Betriebsanleitung](../entwicklung/D1-ci-betrieb.md) sind insoweit historische Quellplanung; ihre Aktualisierung läuft über die unten genannten PRs. Die Orchestrierung vergibt weiterhin Aufgaben und Dateireservierungen. Ein freies Dokument oder ein zusätzliches KI-Fenster ist keine Zuteilung.

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

Belege unterscheiden PR und main:

- [Erster BBS-PR-Lauf an PR #57](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39571559910): drei erfolgreiche Checks und 21/21 Skripte auf dem PR-Testmerge. Dieser Prüf-PR wurde ohne Merge geschlossen.
- [Echter main-Pushlauf nach PR #83](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39579961109): drei erfolgreiche Checks und 21/21 Skripte auf main `2e70550c88e30291c0db07619cff574a6ff1655b`.

Die Zahl 21 ist das Ergebnis dieser Stände, kein festes Soll. Neue Fachtests werden vom Runner mitentdeckt; sie dürfen nicht zur Erhaltung einer festen Zahl ausgelassen werden.

## Vorhandenen main-Schutz verwalten

Das aktive [Ruleset 25533179](https://github.com/BBS-GuT/smartcity-roboter/rules/25533179) verlangt PR, mindestens eine gültige Freigabe, Verwerfen alter Freigaben bei neuen Commits, erledigte Reviewgespräche und alle drei D1-Pflichtchecks mit aktueller main-Basis (`strict=true`). Force-Push und Löschen von main sind gesperrt; es gibt keine Bypass-Ausnahmen, auch nicht für Administratoren.

Codeowner-Freigaben sind im Ruleset aktiviert. Die zugehörige `CODEOWNERS`-Datei ist noch Bestandteil von [PR #91](https://github.com/BBS-GuT/smartcity-roboter/pull/91) und damit auf dem genannten main-Stand noch nicht wirksam. `CODEOWNERS` ersetzt keine Dateireservierung. Gemergte Aufgabenbranches werden durch die aktivierte Repositoryoption automatisch gelöscht; die Löschsperre für main bleibt bestehen.

Automatische native Codex-Reviews sind eingerichtet. Eine Botmeldung ersetzt derzeit kein formales GitHub-Approval. Die separate formale Freigabe-App aus [#90](https://github.com/BBS-GuT/smartcity-roboter/issues/90)/[PR #91](https://github.com/BBS-GuT/smartcity-roboter/pull/91) bleibt bis Einrichtung, Integration und eigenem Funktionsnachweis offen. Auto-Merge ist nicht eingerichtet. Ein anderer KI-Chat unter demselben Autorenkonto ist keine unabhängige GitHub-Freigabe.

## Noch offene kleine Aufträge und Dateibesitz

- [#68 / PR #54](https://github.com/BBS-GuT/smartcity-roboter/pull/54): Reviewer-Chat besitzt ausschließlich `AGENTS.md` und `docs/entwicklung/D-reviewbot.md`.
- [#69 / PR #92](https://github.com/BBS-GuT/smartcity-roboter/pull/92): aktuelle Beitrags- und Betriebsanleitung, ausschließlich `CONTRIBUTING.md` und `docs/entwicklung/D1-ci-betrieb.md`.
- [PR #80](https://github.com/BBS-GuT/smartcity-roboter/pull/80): die Orchestrierung hält das Auftragsregister in `docs/auftraege/README.md` aktuell.
- [#93](https://github.com/BBS-GuT/smartcity-roboter/issues/93): ausschließlich dieses Auftragsdokument auf Branch `docs/gb-d1-auftragsstatus` korrigieren. Keine Workflows, Tests oder Produktdateien mitändern.
- [#90 / PR #91](https://github.com/BBS-GuT/smartcity-roboter/pull/91): separate App-Einrichtung und formale Freigabebrücke; kein erneuter D1-Grundaufbau.

Jede Lieferung nennt Basis, Head, genaue Dateien, tatsächliche CI und offene Abnahmen. Vor Merge müssen der aktuelle Codex-Review, CI und die erforderliche unabhängige Freigabe vorliegen. Kleine Folgefehler werden als eigene Aufgaben mit Dateigrenze vergeben. Produktmodule und fachliche Tests bleiben bei ihren zugeteilten Besitzern; keine Erwartungen oder Grenzwerte für einen grünen Lauf abschwächen.

D1-Softwareprüfungen greifen nicht auf Roboter oder Projektbroker zu. Sie ersetzen keine Fahr-, Sensor- oder Greifabnahme. Erlaubtes Grundbetriebsräumen bleibt Bestandteil der Fachaufträge; sein Zieldefinitionsabgleich und seine Schutzbedingungen gehören zu [#8](https://github.com/BBS-GuT/smartcity-roboter/issues/8).

## Historische Quellplanung vom 20.10.2026

Diese Bezüge dokumentieren das frühere Repository und sind keine aktuellen Schreibziele oder Einrichtungsaufträge:

- Die ursprünglichen Aufträge lagen auf `codex/grundbetrieb` im [Quell-PR #11](https://github.com/davidheinrich73/smartcity-roboter/pull/11).
- Der damalige Quellstand [d991765](https://github.com/davidheinrich73/smartcity-roboter/commit/d991765) war mit 13/13 Softwaretestskripten grün. Runner, getestete Paketumgebung, CI sowie Beitrags-/PR-/Aufgabenvorlagen waren die ursprünglichen D1-Liefergegenstände.
- Die damaligen Quellenissues [#15](https://github.com/davidheinrich73/smartcity-roboter/issues/15), [#50](https://github.com/davidheinrich73/smartcity-roboter/issues/50), [#68](https://github.com/davidheinrich73/smartcity-roboter/issues/68) und [#69](https://github.com/davidheinrich73/smartcity-roboter/issues/69) wurden im BBS-Repository zu #4, #28, #44 und #45. Die frühere Adminaktion und die alten Ergänzungen sind abgeschlossen.

Ein historisch vorgemerktes Folgepaket für parallele ROS-Simulationen braucht weiterhin eine eigene Zuteilung und getrennte Domains, Ports sowie Karten-, Log-, Lern- und temporäre Pfade. Bis dahin nur einen vorhandenen Simulationslauf im gleichen Laufzeitumfeld starten. Dieser Dokumentationsauftrag verändert `scripts/simulation.sh` und andere Startpfade nicht.
