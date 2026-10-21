# Kleine, prüfbare Beiträge

Beginne mit einem kleinen Issue: ein verständliches Problem, ein Ziel und ein prüfbares Bestehenskriterium. Nenne Elternissue, verantwortliche Person, erlaubte Dateien, Fehlerbeispiel und Abhängigkeiten. Große Aufgaben aufteilen; offene Architektur-/Vertragsentscheidungen als Abhängigkeit an die Orchestrierung geben.

Lies [gemeinsame Regeln](docs/auftraege/00-gemeinsame-regeln.md), [Auftragsregister mit Dateireservierungen](docs/auftraege/README.md), [Entwicklungsplan](docs/zusammenarbeit-und-entwicklung.md) und [Zieldefinition](docs/zieldefinition-grundbetrieb.md). Prüfe deren Stand gegen aktuelle Issues und akzeptierte Übergaben. Vorhandene `AGENTS.md` beachten. Offene Pull Requests und Drafts ansehen, bevor du Dateien änderst, an denen schon jemand arbeitet. Fremd reservierte Dateien oder neue öffentliche Schnittstellen zuerst über die Orchestrierung abstimmen.

**Migrationsstand 21.10.2026:** Das Register wird in [PR #80](https://github.com/BBS-GuT/smartcity-roboter/pull/80) abgeglichen. Der [historische D1-Auftrag](docs/auftraege/D-tests-ci-und-repository.md) und noch verbliebene Altangaben im Register beschreiben die Quellplanung: ein altes Repositoryziel, fehlende Adminrechte und offenen main-Schutz. Diese Betriebsangaben sind historische Herkunft. Für Repository, Rechte, CI und Schutz gilt der datierte BBS-Stand der [CI-Betriebsanleitung](docs/entwicklung/D1-ci-betrieb.md) und das unten genannte BBS-`origin`. Dateibesitz und Abhängigkeiten vor der Arbeit anhand der aktuellen BBS-Issues mit der Orchestrierung abgleichen.

## Eigene Arbeitskopie

Vorhandene Änderungen prüfen und bewahren. Verwende einen eigenen Checkout oder Worktree; wechsle keine Branches in fremden Arbeitskopien. Im eigenen Checkout:

```bash
git status --short
git remote -v
git fetch origin
git switch -c <aufgabenbranch> origin/main
git rev-parse HEAD
```

`origin` muss auf `BBS-GuT/smartcity-roboter` zeigen (ältere Klone zeigen noch auf `davidheinrich73/smartcity-roboter`: `git remote set-url origin https://github.com/BBS-GuT/smartcity-roboter.git`). Notiere den Basiscommit und die Dateigrenze. Neue Arbeit beginnt am tatsächlich aktuellen `origin/main`; prüfe inzwischen gelieferte Lösungen, bevor du etwas ersetzt.

## Prüfen und liefern

Für reine Softwaretests mit `python -m venv .venv` eine eigene Umgebung anlegen. Unter Linux mit `. .venv/bin/activate`, unter Windows/PowerShell mit `.\.venv\Scripts\Activate.ps1` aktivieren. Dann aus der Projektwurzel:

```bash
python -m pip install -r requirements-test.txt
python -m pip check
python scripts/pruefen.py --test-timeout test_karte.py=600
```

Runner, Testumgebung und BBS-main-Schutz sind eingerichtet. Die verbindliche [CI-Betriebsanleitung](docs/entwicklung/D1-ci-betrieb.md) beschreibt Aufruf, exakte Checknamen, BBS-PR-/main-Nachweise zum dokumentierten Stand, Downloadfehler und das bestehende [main-Ruleset](https://github.com/BBS-GuT/smartcity-roboter/rules/25533179). Die Infrastrukturaufträge [#4](https://github.com/BBS-GuT/smartcity-roboter/issues/4) und [#28](https://github.com/BBS-GuT/smartcity-roboter/issues/28) sind abgeschlossen. Fehlende Dateien oder Pakete sind kein bestandener Test. Der Runner entdeckt `tests/test_*.py`; Fehler, Timeouts und ausgewiesene unittest-Skips verhindern Gesamterfolg. Relevante positive und negative Kontrollen ergänzen. Keine Fachschwellen verändern, um Tests grün zu machen.

Erstelle kleine Commits und einen Draft-PR nach `main`. Kennzeichne den fertigen PR als bereit zur Prüfung, damit der automatische Codex-Reviewer ihn prüfen kann. Nach weiteren Commits muss sein Ergebnis den aktuellen Head abdecken; ein älterer Review genügt nicht. Verlinke das kleine Issue und das Elternissue; schließe ein Elternpaket erst mit dessen vollständigem Nachweis. Benenne die betroffenen GB-/A-Kennungen oder begründe, weshalb ein reiner Infrastrukturbeitrag keinen fachlichen Anspruch abnimmt. Keine Zugangsdaten, echten Brokeridentitäten oder lokalen Gerätekonfigurationen veröffentlichen.

Anleitungen und Wissenssammlung gehören ins [Wiki](https://github.com/BBS-GuT/smartcity-roboter/wiki). Es wird aus dem Ordner `wiki/` erzeugt; Änderungen daran laufen wie Code per PR und werden nach dem Merge automatisch übertragen. Technik, die sich mit dem Code ändert, bleibt in `docs/`.

Der Übergabebericht enthält Besitzer, Status, Basis-/Liefercommit, Branch/PR, geänderte und reservierte Dateien, Schnittstellenänderungen sowie tatsächlich ausgeführte Befehle, Plattform, Paketversionen, Testzahlen, Fehler und Skips. Softwaretests, ROS-Simulation und reale Geräte-/Brokerabnahme getrennt ausweisen; nicht ausgeführte Prüfungen offen nennen. Historische Fehlerprobes sind kein bestandener Regressionstest. Offene Fehler als kleine Folgeaufträge mit Reproduktion an die Orchestrierung geben.

Codex übernimmt die Produktreviews. Die Orchestrierung gleicht Bot-Ergebnis und CI ab und koordiniert Abhängigkeiten, Dateibesitz und Integration. Kein eigener Merge nach `main`, kein Überschreiben fremder Branches. Der aktive Branchschutz verlangt eine unabhängige GitHub-Freigabe und die drei aktuellen D1-Pflichtchecks; gemergte PR-Branches werden automatisch gelöscht. Zum Abgleich vom 21.10.2026 ist die Codeowner-Regel eingeschaltet, die `CODEOWNERS`-Datei aber erst in [PR #91](https://github.com/BBS-GuT/smartcity-roboter/pull/91) vorbereitet. Auch die dort geplante formale App-Freigabe ist erst nach Einrichtung und Funktionsnachweis aktiv; ein Codex-Kommentar allein ist kein formales `Approve`. Konkrete erfolgreiche CI-Checks und Freigaben verlinken; erforderliche Geräteabnahmen bleiben getrennt.
