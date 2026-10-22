# Entwicklungsauftrag D Tests CI und Repositoryregeln

**Empfänger:** Zusätzlicher Entwickler oder ausdrücklich eingeplantes Paket eines der Bereiche A/B/C. **Jetzt umzusetzen:** D1. **Branch:** `chore/gb-d1-testinfrastruktur`.

Du entwickelst am Team-Repository `https://github.com/BKoewenig/smartcity-roboter`. Lies [gemeinsame Regeln](00-gemeinsame-regeln.md), [Register](README.md) und Entwicklungsplan. Die Aufträge liegen zunächst auf `codex/grundbetrieb` in PR #11. Ein eigener Checkout und Aufgabenbranch ab aktuellem `origin/main` sind erforderlich. Diese Aufgabe ist separat zu vergeben; sie ist nicht automatisch einer bereits ausgelasteten Person zusätzlich zugeordnet.

## Auftrag D1

**Geprüfter Status am 20.10.2026:** Ursprünglicher Runner, Testumgebung, CI und Beitragsvorlagen sind integriert; main `d991765` ist mit 13/13 Softwaretestskripten grün. Maßgeblich für den laufenden Betrieb ist die [CI-Betriebs- und Eigentümeranleitung](../entwicklung/D1-ci-betrieb.md). Status dieses Bearbeitungsstands: **Ergänzungen #68/#69 in Arbeit; #50 administrativ offen**. Fortschreibung und Gesamtabschluss erfolgen über #15; ein grüner Lauf bestätigt keinen aktiven main-Schutz oder Gerätebetrieb. Die folgende Beschreibung des Ausgangsstands bleibt als Auftragsgrundlage erhalten.

Mache die vorhandenen reinen Softwareprüfungen reproduzierbar und auf Pull Requests automatisch sichtbar. Der Ausgangsstand hat sechs einzelne Testskripte und keine GitHub-Actions-Workflows. Keine Fahrlogik, Testszenarioerwartungen oder fachlichen Grenzwerte ändern, um einen grünen Lauf herzustellen.

Liefergegenstände:

1. `scripts/pruefen.py` als gemeinsamer Runner. Er führt eigenständig ausführbare `tests/test_*.py` jeweils in einem eigenen Prozess aus, zeigt Einzelstatus, gibt bei Fehler/Timeout einen Fehlercode zurück und verschluckt keine fehlenden Abhängigkeiten. Neue Tests aus A/B/C werden mit erfasst. Historische Fehlerprobes unter `docs/pruefungen/` werden nicht als bestandene Regressionstests gezählt.
2. `requirements-test.txt` mit nachvollziehbarer, getesteter Umgebung. Ziel ist eine zur Gerätebasis passende Ubuntu-22.04-/Python-3.10-Prüfung. NumPy/OpenCV/PyYAML müssen gemeinsam kompatibel sein. ROS-/Hardwaretests nicht durch Scheinerfolge ersetzen. Änderungen mit C bei zusätzlichem Vertragsprüfbedarf abstimmen.
3. `.github/workflows/grundbetrieb-tests.yml`: auf Pull Requests und geeigneten Branch-Pushes Python-Syntax, Shellsyntax und die reinen Softwaretests ausführen. Eindeutige Checknamen, passende Zeitlimits und sichtbare Logs. Der Kartentest dauert wesentlich länger als die Logiktests. Minimale Rechte; kein Zugriff auf Roboter, Projektbroker oder private Schlüssel.
4. `CONTRIBUTING.md`, `.github/pull_request_template.md` und eine Arbeitspaketvorlage unter `.github/ISSUE_TEMPLATE/`. Vorlage nennt Besitzer, Dateireservierung, GB-/A-Bezug, Schnittstellen, Tests, offene Geräteprüfung und Übergabe.

Der Runner soll auch lokal nutzbar sein. Syntaxprüfung muss ROS-Dateien ohne ROS-Import parsen können. Läuft ein Test im CI-System anders als beim dokumentierten Windows-Prüfstand, die konkrete Abweichung untersuchen und melden; produktive Fachmodule nur über ihren Besitzer ändern lassen.

## Dateien und Grenzen

D besitzt die oben genannten Infrastrukturdateien und gemeinsame `tests/attrappen/*`. Bestehende Attrappen nur bei tatsächlichem Bedarf erweitern und mit betroffenen Testbesitzern abstimmen. Die fachlichen Tests gehören A/B/C; keine pauschalen Änderungen an allen Tests.

`scripts/env.sh`, `scripts/stopp.sh` und `config/roboter.yaml` gehören A, `scripts/panel.sh` gehört C. `scripts/simulation.sh` wird in D1 nicht geändert. Keine Produktdateien oder den gemeinsamen Zustandsvertrag umbauen. Optional `docs/entwicklung/D1-tests.md` mit tatsächlich reproduzierter Umgebung und Checknamen.

## Konkrete Bestehenskriterien

- Ein einziger dokumentierter Aufruf führt alle vorhandenen reinen Testskripte aus und meldet einen Gesamterfolg nur bei vollständigem Erfolg.
- Fehler und Timeout werden zuverlässig als Fehler gemeldet. Ein fehlendes Paket führt nicht zu stillem Überspringen.
- Die Tests laufen im CI mit dokumentierten Versionen; nicht verfügbare ROS-/Geräteprüfungen sind als separate Prüfungen erkennbar.
- PR-Checks erscheinen mit stabilen eindeutigen Namen und genügend Diagnose. Der Entwurf fordert noch keinen erforderlichen Check, der nie gelaufen ist.
- Vorlagen bilden Aufgabenbesitzer, Dateigrenzen und tatsächliche Ergebnisse ab. Keine unbekannten GitHub-Konten in `CODEOWNERS` erfinden.

Lieferung: kleiner Draft-PR mit Runner/CI/Vorlagen, getesteter Umgebung, tatsächlichem Checklauf und Übergabebericht. D1 kann unabhängig von C1 anfangen. Keine globale Systeminstallation auf Robotern und kein eigenständiger Merge nach `main`.

## Konkreter Zusatzauftrag an den Repositoryeigentümer

Sobald die CI-Checknamen tatsächlich existieren und erfolgreich gelaufen sind, für `main` PR-Prüfung mit mindestens einer fachkundigen anderen berechtigten GitHub-Reviewperson, verfallenden alten Freigaben, erledigten Gesprächen und den drei passenden erfolgreichen Checks einrichten. Required Checks müssen eine **aktuelle main-Basis** verlangen (`Require branches to be up to date before merging` / `strict=true`). Force-Push und Löschen sperren; Regeln auch für Administratoren ohne Bypass anwenden. Konkrete Einrichtung und Abnahmebelege für #50/#15 stehen in der [Betriebsanleitung](../entwicklung/D1-ci-betrieb.md).

Codeowner können anschließend mit echten GitHub-Konten und einer Vertretung pro Bereich eingerichtet werden. `CODEOWNERS` reserviert keine Dateien. Der gespeicherte Zugang `letsc4` hat Schreib-, aber keine Administrationsrechte; dieses Einstellen der Regeln muss ein berechtigter Eigentümer übernehmen. Die Bestätigung der tatsächlich aktivierten Regeln gehört in die Übergabe.

## Folgeauftrag D2 erst nach Zuteilung

Parallele ROS-Simulationen müssen getrennte Domains, Ports, Karten-, Log-, Lern- und temporäre Pfade erhalten. Dafür ein eigenes Paket zu `scripts/simulation.sh` und nötigen Parametern abstimmen. Bis dahin nur einen vorhandenen Simulationslauf im gleichen Laufzeitumfeld starten. D1 wird nicht um einen ungeprüften Umbau aller Startpfade erweitert.
