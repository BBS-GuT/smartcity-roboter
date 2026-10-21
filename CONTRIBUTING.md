# Kleine, prüfbare Beiträge

Beginne mit einem kleinen Issue: ein verständliches Problem, ein Ziel und ein prüfbares Bestehenskriterium. Nenne Elternissue, verantwortliche Person, erlaubte Dateien, Fehlerbeispiel und Abhängigkeiten. Große Aufgaben aufteilen; offene Architektur-/Vertragsentscheidungen als Abhängigkeit an die Orchestrierung geben.

Lies [gemeinsame Regeln](docs/auftraege/00-gemeinsame-regeln.md), [Auftragsregister mit Dateireservierungen](docs/auftraege/README.md), [Entwicklungsplan](docs/zusammenarbeit-und-entwicklung.md) und [Zieldefinition](docs/zieldefinition-grundbetrieb.md). Prüfe deren Stand gegen aktuelle Issues und akzeptierte Übergaben. Vorhandene `AGENTS.md` beachten. Offene Pull Requests und Drafts ansehen, bevor du Dateien änderst, an denen schon jemand arbeitet. Fremd reservierte Dateien oder neue öffentliche Schnittstellen zuerst über die Orchestrierung abstimmen.

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

Runner und Testumgebung sind integriert. Die verbindliche [CI-Betriebs- und Eigentümeranleitung](docs/entwicklung/D1-ci-betrieb.md) beschreibt Aufruf, Checknamen, PR-/main-Nachweise, Downloadfehler und den noch offenen main-Schutz aus #50. Fehlende Dateien oder Pakete sind kein bestandener Test. Der Runner entdeckt `tests/test_*.py`; Fehler, Timeouts und ausgewiesene unittest-Skips verhindern Gesamterfolg. Relevante positive und negative Kontrollen ergänzen. Keine Fachschwellen verändern, um Tests grün zu machen.

Erstelle kleine Commits und einen Draft-PR nach `main`. Verlinke das kleine Issue und das Elternissue; schließe ein Elternpaket erst mit dessen vollständigem Nachweis. Benenne die betroffenen GB-/A-Kennungen oder begründe, weshalb ein reiner Infrastrukturbeitrag keinen fachlichen Anspruch abnimmt. Keine Zugangsdaten, echten Brokeridentitäten oder lokalen Gerätekonfigurationen veröffentlichen.

Anleitungen und Wissenssammlung gehören ins [Wiki](https://github.com/BBS-GuT/smartcity-roboter/wiki). Es wird aus dem Ordner `wiki/` erzeugt; Änderungen daran laufen wie Code per PR und werden nach dem Merge automatisch übertragen. Technik, die sich mit dem Code ändert, bleibt in `docs/`.

Der Übergabebericht enthält Besitzer, Status, Basis-/Liefercommit, Branch/PR, geänderte und reservierte Dateien, Schnittstellenänderungen sowie tatsächlich ausgeführte Befehle, Plattform, Paketversionen, Testzahlen, Fehler und Skips. Softwaretests, ROS-Simulation und reale Geräte-/Brokerabnahme getrennt ausweisen; nicht ausgeführte Prüfungen offen nennen. Historische Fehlerprobes sind kein bestandener Regressionstest. Offene Fehler als kleine Folgeaufträge mit Reproduktion an die Orchestrierung geben.

Die Orchestrierung koordiniert Review, Abhängigkeiten und Integration. Kein eigener Merge nach `main`, kein Überschreiben fremder Branches. Branchschutz und CODEOWNERS werden erst nach Einrichtung durch berechtigte Eigentümer als aktiv berichtet; konkrete erfolgreiche CI-Checks verlinken.
