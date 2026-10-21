# D1: CI und main-Schutz im BBS-Repository betreiben

Diese Anleitung gilt für `BBS-GuT/smartcity-roboter`. Zuständigkeiten und Dateigrenzen stehen im [Auftragsregister](../auftraege/README.md); fachliche Fahrregeln werden hier nicht festgelegt.

**Migrationshinweis:** Das Register wird in [PR #80](https://github.com/BBS-GuT/smartcity-roboter/pull/80) abgeglichen. Der [historische D1-Auftrag](../auftraege/D-tests-ci-und-repository.md) und noch verbliebene Altangaben im Register beschreiben die frühere Quellplanung zu Repositoryziel, fehlenden Adminrechten und offenem main-Schutz. Diese Betriebsangaben sind historische Herkunft. Für Repository, Rechte, CI und Schutz ist der folgende datierte BBS-Betriebsstand maßgeblich. Aktuelle Zuständigkeiten, Dateireservierungen und Abhängigkeiten vor Arbeitsbeginn anhand der BBS-Issues mit der Orchestrierung abgleichen.

**Geprüfter Stand 21.10.2026:** D1-Software, CI und main-Schutz sind eingerichtet. Die BBS-Aufträge [#4](https://github.com/BBS-GuT/smartcity-roboter/issues/4), [#28](https://github.com/BBS-GuT/smartcity-roboter/issues/28), [#44](https://github.com/BBS-GuT/smartcity-roboter/issues/44) und [#45](https://github.com/BBS-GuT/smartcity-roboter/issues/45) sind geschlossen. Das aktive [Ruleset 25533179](https://github.com/BBS-GuT/smartcity-roboter/rules/25533179) verwalten und prüfen; keine zusätzliche klassische Schutzregel anlegen. `letsc4` besitzt inzwischen Repository-Adminrechte und die Organisationsinhaberrolle für BBS-GuT. Frühere Aussagen über fehlende Rechte und ungeschütztes main betreffen das Quellrepository vom 20.10.2026, siehe Abschnitt 6.

**Dokumentierter BBS-main-Nachweis, 21.10.2026:** Der echte `push`-Lauf auf main `8ee57b6cec55b5d2f4eb0c8de04d814344e9bfe8` nach Integration von [PR #102](https://github.com/BBS-GuT/smartcity-roboter/pull/102) ist [vollständig grün](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39597759051): Ubuntu 22.04, Python 3.10, **21/21 Softwaretestskripte**, keine Fehler oder unvollständigen Tests, zusätzlich **42/42 Tests der Freigaberegeln**. Diese Zahlen belegen diesen Commit, kein festes Soll und keinen späteren Commit. Frühere BBS-main-Läufe bleiben in Abschnitt 4 als historische Integrationsnachweise erhalten.

## 1. Auslösung, Checks und Logs

Maßgeblich ist [.github/workflows/grundbetrieb-tests.yml](../../.github/workflows/grundbetrieb-tests.yml), Workflow **Grundbetrieb - Softwarepruefung**. PRs mit Zielbranch `main` lösen ihn für `opened`, `synchronize`, `reopened` und `edited` aus. Auch ein Zielwechsel eines bestehenden PRs nach `main` bei unverändertem Head erzeugt dadurch einen neuen Lauf; Titel-/Beschreibungskorrekturen können ebenfalls `edited` auslösen. PR-Quellbranches sind nicht eingeschränkt.

Pushes starten den Workflow auf `main`, `chore/gb-*`, `fix/gb-*` und `test/gb-*`. Ein Push etwa auf `docs/*` allein startet ihn nicht; dessen PR nach `main` schon. Für diesen D1-Workflow gibt es keinen `workflow_dispatch`-, Zeitplan- oder Merge-Queue-Trigger.

| Exakter Pflichtcheck | Prüfung | Joblimit | BBS-main-Beleg auf `8ee57b6` |
|---|---|---|---|
| `D1 / Python-Syntax (3.10)` | Versionierte Pythondateien kompilieren, ohne ROS-/Produktimports | 5 min | [Erfolgreicher Job](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39597759051/job/119214220288) |
| `D1 / Shell-Syntax (bash)` | Versionierte Shellskripte mit `bash -n` | 5 min | [Erfolgreicher Job](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39597759051/job/119214220270) |
| `D1 / Softwaretests (Ubuntu 22.04, Python 3.10)` | Pflichtimporte, `pip check`, gemeinsamer Runner | 40 min | [21/21 Skripte](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39597759051/job/119214220463) |

Alle drei Pflichtchecks sind im Ruleset an **GitHub Actions, App-ID 15368** gebunden. Zusätzliche Checks ersetzen sie nicht. Namen oder Quellen nur mit der Orchestrierung und den berechtigten Eigentümern ändern, damit Pflichtchecks nicht auf alte Namen zeigen.

Seit PR #91 prüft der zusätzliche Job `Codex / Freigaberegeln` die Freigabelogik ohne GitHub-Zugriff; auf dem dokumentierten main-Stand bestanden [42 Tests](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39597759051/job/119214219853). Er gehört nicht zu den drei Pflichtchecks des Rulesets und belegt keine zählende App-Freigabe.

Der Runner entdeckt eigenständig ausführbare `tests/test_*.py` direkt unter `tests/`, führt sie alphabetisch in eigenen Prozessen mit Projektwurzel als Arbeitsverzeichnis aus und liefert bei Fehler, Timeout oder ausgewiesenen unittest-Skips einen Fehlercode. Auch kombinierte Skip-Zusammenfassungen werden erkannt; erwartete Fehler allein bleiben nach unittest-Regeln erfolgreich. Der Timeout beendet nur den eigenen Testprozessbaum. Historische Fehlerprobes unter `docs/pruefungen/` werden nicht als Regression ausgeführt.

CI erlaubt **120 s je Testskript und 600 s für `test_karte.py`**. Der lokale Runnerstandard ohne Parameter ist 300 s; für einen vergleichbaren Lauf die Parameter aus Abschnitt 2 verwenden. Einzellogs und `umgebung.log` mit Plattform und `pip freeze` liegen im Artefakt `d1-softwaretestlogs-<run_id>-<run_attempt>`, auch nach Testfehlern, für 14 Tage. Benötigte Belege rechtzeitig sichern und Commit, Run und Versuch zuordnen. Fehlende Logs nach einem Installationsabbruch sind kein Testnachweis.

Die D1-Workflowrechte bleiben `contents: read`; Checkout-Zugangsdaten werden nicht persistiert. Keine Projektbroker, privaten Schlüssel oder Roboter-/Hardwaredienste für diese Prüfungen verwenden.

## 2. Lokal reproduzieren

Im eigenen Checkout muss `origin` auf `https://github.com/BBS-GuT/smartcity-roboter.git` zeigen. Ab tatsächlich aktuellem `origin/main` eine isolierte Umgebung verwenden. Unter Ubuntu 22.04 mit vorhandenem Python 3.10 aus der Projektwurzel:

```bash
python3.10 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-test.txt
python -m pip check
python --version
python -m pip freeze
python scripts/pruefen.py --timeout 120 --test-timeout test_karte.py=600 --log-dir .venv/d1-testlogs
```

Unter Windows mit vorhandenem Python 3.10 eine eigene Umgebung mit `py -3.10 -m venv .venv` anlegen; anschließend dieselben Befehle mit `.venv\Scripts\python.exe` statt `python` ausführen. Ein Windowslauf bestätigt keine Ubuntu-Plattform. Ein beschreibbares eigenes `TEMP`/`TMP` verwenden, falls das Systemtempverzeichnis gesperrt ist. Verweigerte Beendigung eigener Testkinder als Fehler untersuchen, nicht überspringen.

Die acht getesteten Pins aus [requirements-test.txt](../../requirements-test.txt) bleiben:

| Paket | Version | Paket | Version |
|---|---|---|---|
| numpy | 1.26.4 | opencv-python-headless | 4.10.0.84 |
| PyYAML | 6.0.2 | jsonschema | 4.23.0 |
| attrs | 24.2.0 | jsonschema-specifications | 2023.12.1 |
| referencing | 0.35.1 | rpds-py | 0.20.0 |

CI wählt die Reihe `3.10` und protokolliert die tatsächliche Patchversion. Der frühere BBS-main-Lauf auf `2e70550` verwendete CPython 3.10.22; ein früherer Windows-/CPython-3.12.14-Gegencheck steht im [Umgebungsnachweis](D1-testumgebung.md). Für einen anderen Commit die Patchversion aus dessen eigenem Lauf übernehmen. Vor Paketänderungen Kompatibilität isoliert prüfen, danach Pflichtimporte, `pip check`, Schema-Prüfung und Gesamtlauf nachweisen. `jsonschema` ist Pflicht; fehlende Pakete oder wesentliche Skips gelten nicht als Erfolg.

## 3. Einen roten Lauf untersuchen

1. Commit, Event, Run-ID, Versuch, Job und ersten fehlerhaften Schritt festhalten. Installations-, Syntax-, Fachtest- und Runnerfehler unterscheiden; stdout/stderr und vorhandenes Artefakt sichern.
2. Bei Fachtestfehlern eine kleine Reproduktion und den zuständigen Besitzer bestimmen. Keine Fachschwellen lockern und nicht wiederholen, bis zufällig Grün entsteht. Fehler, Timeouts und Skips bleiben sichtbar.
3. Bei Download-, Verbindungs- oder Hashfehlern das Paket des fehlgeschlagenen Versuchs nicht verwenden. Dateiname, Quelle, vollständige Größe sowie erwarteten und erhaltenen SHA256 vergleichen. Die Originalerwartung gegen offizielle Paketmetadaten prüfen; mit einem frischen vollständigen Download erneut regulär verifizieren. Keine Hashprüfung abschalten, keinen Fehlhash zum Sollwert machen und kein Paket nur für Grün austauschen. Wiederholte Abweichungen an die Orchestrierung geben; bis zur Klärung keine Abnahme.
4. Nur bei belegtem vorübergehendem Downloadabbruch unter **Actions → betroffener Lauf → Re-run jobs → Re-run failed jobs** gezielt wiederholen. Keine doppelten Wiederholungen starten. Alten Fehler, Grund und neuen Versuch verlinken; Installation, `pip check` und alle gestarteten Tests müssen bestehen. [GitHub: Wiederholungen](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs).

Das historische OpenCV-Downloadbeispiel mit unveränderten Pins und Originalprüfung bleibt in Abschnitt 6 erhalten.

## 4. PR-Erfolg, Schutzprobe und main-Erfolg belegen

Ein PR-Nachweis gehört zum konkreten Head und seiner main-Basis. `pull_request` prüft mit dem bestehenden Checkout den synthetischen Mergestand `refs/pull/<Nummer>/merge`; deshalb Head-SHA, Basis-SHA und tatsächlich ausgecheckte Run-/Merge-SHA festhalten. Vor Integration anhand der Ahnen dieser ausgecheckten SHA bestätigen, dass die aktuelle main-SHA enthalten ist; eine inzwischen aktualisierte Basisangabe der PR-API oder ein erfolgreicher Branch-Push genügt nicht. Nach Head- oder Basisänderung den passenden neuen PR-Lauf abwarten. Eine Wiederholung prüft SHA und Ref des ursprünglichen Ereignisses, keine neuen Commits. [GitHub: PR-Mergestand](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request).

Die erste BBS-Schutzprobe verwendete den inzwischen ohne Merge geschlossenen [PR #57](https://github.com/BBS-GuT/smartcity-roboter/pull/57): Head `ca791ca1cf07e21cab89d7269dbf3bc93ec7fbe3`, Basis `d92e366907fd538c377c272250a0e2d75120b5e2`, ausgecheckter Testmerge `025afdc`. [Run 39571559910](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39571559910) bestand alle drei Checks und **21/21 Skripte**. Das ist ein **PR-Mergestand**, kein main-Push-Nachweis. Der normale Mergeversuch als Admin `letsc4` wurde nach grüner CI mit HTTP 405 und `At least 1 approving review is required by reviewers with write access.` abgewiesen. main blieb unverändert; die Probe wurde geschlossen und ihr Branch entfernt. Die bereinigten Belege stehen in [#28](https://github.com/BBS-GuT/smartcity-roboter/issues/28).

Der frühere erfolgreiche [BBS-main-Pushlauf 39579961109](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39579961109) auf `2e70550c88e30291c0db07619cff574a6ff1655b` nach [PR #83](https://github.com/BBS-GuT/smartcity-roboter/pull/83) ist ein **historischer Integrationsnachweis**: Ubuntu 22.04.5, Python 3.10.22, 21/21 Skripte. Er deckt die späteren Produktänderungen aus PR #78 nicht ab.

Der ebenfalls historische [Pushlauf 39589008257](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39589008257) auf `1c07fe4fdd509532359450dc11de3fb6666a1215` nach PR #78 bestand 21/21 Skripte. Der historische [Pushlauf 39593670942](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39593670942) auf `e37bd96` nach PR #91 bestand 21/21 Skripte und 37 Freigaberegeltests. Den späteren Nachweis auf `8ee57b6` nach PR #102 mit seinen eigenen Joblinks dokumentiert Abschnitt 1. PR-Nachweis und main-Push-Nachweise getrennt berichten. Für jede spätere Integration erneut PR-Head/Basis, aktuelle Pflichtchecks, Freigabe und erledigte Gespräche festhalten; nach Merge den separaten `push`-Lauf auf der tatsächlichen main-Merge-SHA samt Testzahlen, Fehlern/Skips und Paketversionen belegen. Ein alter grüner Lauf bestätigt keinen späteren Commit.

## 5. Bestehendes main-Ruleset verwalten

Berechtigte Eigentümer öffnen **Settings → Rules → Rulesets → main: PR, Review und D1-CI**, [Ruleset 25533179](https://github.com/BBS-GuT/smartcity-roboter/rules/25533179). Die aktuelle Konfiguration zuerst lesen und gezielt bearbeiten. Keine zweite klassische Regel und kein Ersatz-Ruleset anlegen.

| Aktive Anforderung | Belegter Zustand am 21.10.2026 |
|---|---|
| Geltung | `Active`, Branch `refs/heads/main` |
| Integration | Pull Request und mindestens **eine Approval einer anderen berechtigten GitHub-Identität** |
| Neue Commits | Alte Approvals verwerfen (`dismiss_stale_reviews_on_push=true`) |
| Gespräche | Alle Review-Threads erledigt (`required_review_thread_resolution=true`) |
| Pflichtchecks | Exakt die drei Namen aus Abschnitt 1, jeweils GitHub Actions / App-ID 15368 |
| Aktualität | Strikte aktuelle main-Basis (`strict_required_status_checks_policy=true`) |
| Bypass | Leere Liste, auch keine Admin-Ausnahme |
| main erhalten | Force-Push- und Löschsperre (`non_fast_forward`, `deletion`) |
| Codeowner-Regel | Eingeschaltet; [.github/CODEOWNERS](../../.github/CODEOWNERS) seit dem Merge von PR #91 auf main `e37bd96` vorhanden und für die zugeordneten Steuerungsdateien wirksam |
| Gemergte PR-Branches | Automatische Löschung an (`delete_branch_on_merge=true`) |

Die Löschsperre betrifft `main`; die automatische Löschung betrifft gemergte Entwicklungsbranches. Das sind getrennte Einstellungen. `allow_auto_merge=false`: Es erfolgt kein automatischer Merge.

Zur Prüfung Datum, berechtigtes Konto und bereinigten Konfigurationsexport oder Screenshot sichern. `GET /repos/BBS-GuT/smartcity-roboter/rulesets/25533179` liest das Ruleset; `GET /repos/BBS-GuT/smartcity-roboter/rules/branches/main` die tatsächlich wirksamen Regeln. Die Bypass-Liste ist nur mit passenden Schreibrechten am Ruleset sichtbar; fehlende Sichtbarkeit ist keine nachgewiesen leere Liste. Ein HTTP 403 belegt keine fehlende oder unwirksame Regel. Keine Tokens oder Cookies veröffentlichen. [GitHub: Regeln lesen](https://docs.github.com/en/rest/repos/rules).

Codex übernimmt die Produktreviews; die Orchestrierung koordiniert anhand des Bot-Ergebnisses und der CI. Native Kommentare allein sind kein formales GitHub-`Approve`. Die separate Freigabe-App ist installiert ([#90, abgeschlossen](https://github.com/BBS-GuT/smartcity-roboter/issues/90)); ihr Workflow und die Codeowner-Datei sind seit [PR #91](https://github.com/BBS-GuT/smartcity-roboter/pull/91) auf main integriert. Die praktische Abnahme [#95](https://github.com/BBS-GuT/smartcity-roboter/issues/95) ist abgeschlossen. Der [erste Workflow-Nachweis](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39593905480) erzeugte zunächst sichtbare, noch nicht angerechnete `APPROVED`-Reviews. Nach genehmigter Contents-Schreibberechtigung der Installation bei weiterhin Contents-lesendem Job-Token bestätigte der Abgleich am 21.10.2026, 13:54 MESZ `authorCanPushToRepository=true` und `reviewDecision=APPROVED`, unter anderem für den [App-Review in PR #97](https://github.com/BBS-GuT/smartcity-roboter/pull/97#pullrequestreview-5599108669) auf Head `a00cce67e2e14c51ecad240c775247e063a0f607`. Die Nachträge [PR #99](https://github.com/BBS-GuT/smartcity-roboter/pull/99) und [PR #102](https://github.com/BBS-GuT/smartcity-roboter/pull/102) sind integriert; Einrichtung und [Freigabeanleitung](codex-mergefreigabe.md) sind nachgezogen. Der Workflow prüft nun auch die Anrechenbarkeit. Für jeden neuen Head weiterhin dessen eigene CI, nativen Code-/Security-Review, erledigte Threads und tatsächlich zählende Freigabe abgleichen; der datierte Einrichtungsnachweis allein erklärt keinen späteren PR für mergebereit. Für die in `CODEOWNERS` genannten Steuerungsdateien ist bereits jetzt eine unabhängige berechtigte Codeowner-Freigabe erforderlich. Ein zweiter KI-Chat unter demselben PR-Autorenkonto erfüllt keine unabhängige Approval; Adminrechte heben die Regel nicht auf.

D1-Infrastruktur und Eigentümerauftrag sind bereits abgeschlossen; #69 aktualisiert deren Dokumentation. Issue-Abschlüsse erfolgen durch die Orchestrierung anhand der jeweiligen Liefer- und Abnahmebelege. Grüne Softwarechecks sind keine Gerätefreigabe: ROS-Simulation, reale Bewegung, Brokerempfang und Viergerätebetrieb benötigen eigene Abnahmen. [Praxisbefunde](../problemprotokoll.md) mit Gerätekennung, Softwarestand und Mess-/Logbezug berücksichtigen; historische Probes sind keine bestandenen Regressionen.

## 6. Historische Herkunft aus dem Quellrepository

Die folgenden Links gehören ausdrücklich zu `davidheinrich73/smartcity-roboter`, nicht zum aktuellen BBS-Betrieb. Sie bleiben als Herkunft erhalten:

- Am 20.10.2026 meldete der dortige Entwicklungszugang `letsc4` noch `admin=false`/`maintain=false`; main war zum damaligen Verwaltungsabgleich ungeschützt. Die frühere Anleitung zur Neueinrichtung einer klassischen Branchschutzregel bezog sich auf diesen Zustand und wird für BBS nicht erneut ausgeführt.
- [Quell-main-Lauf 39407908409](https://github.com/davidheinrich73/smartcity-roboter/actions/runs/39407908409) auf `d9917652087aec4684c1bf6a20837879d6961b1d`: Ubuntu 22.04.5, Python 3.10.22, 13/13 Skripte, Runner 8/8, jsonschema-Vertragsprüfung 20/20, `pip check` erfolgreich. Zugehörige Jobs: [Python, 68 Dateien](https://github.com/davidheinrich73/smartcity-roboter/actions/runs/39407908409/job/118578241978), [Shell, 13 Skripte](https://github.com/davidheinrich73/smartcity-roboter/actions/runs/39407908409/job/118578242084), [Softwaretests, 13/13](https://github.com/davidheinrich73/smartcity-roboter/actions/runs/39407908409/job/118578242205). Das belegt weder spätere Commits noch BBS-Einstellungen.
- [Quell-PR #70](https://github.com/davidheinrich73/smartcity-roboter/pull/70) ergänzte den PR-Ereignissatz für den Zielbranchwechsel.
- Im [Quell-PR-Lauf 39402654038](https://github.com/davidheinrich73/smartcity-roboter/actions/runs/39402654038) brach ein OpenCV-Download bei etwa 19,3/49,9 MB an der Hashprüfung ab. Die vollständige Originaldatei hatte 49.858.781 Bytes und SHA256 `377d08a7e48a1405b5e84afcbe4798464ce7ee17081c1c23619c8b398ff18295`, bestätigt gegen [PyPI-Metadaten](https://pypi.org/pypi/opencv-python-headless/4.10.0.84/json). Die gezielte Wiederholung bestand mit unveränderten Pins und Originalprüfung; das war kein behobener Fachtestfehler.

| Historischer Quellauftrag | Aktueller BBS-Auftrag |
|---|---|
| [#50: main-Schutz](https://github.com/davidheinrich73/smartcity-roboter/issues/50) | [#28, abgeschlossen](https://github.com/BBS-GuT/smartcity-roboter/issues/28) |
| [#15: D1-Gesamtpaket](https://github.com/davidheinrich73/smartcity-roboter/issues/15) | [#4, abgeschlossen](https://github.com/BBS-GuT/smartcity-roboter/issues/4) |
| [#68: PR-Ereignissatz](https://github.com/davidheinrich73/smartcity-roboter/issues/68) | [#44, abgeschlossen](https://github.com/BBS-GuT/smartcity-roboter/issues/44) |
| [#69: ursprüngliche Betriebsanleitung](https://github.com/davidheinrich73/smartcity-roboter/issues/69) | [#45, abgeschlossen](https://github.com/BBS-GuT/smartcity-roboter/issues/45) |

Das aktuelle BBS-Issue [#69](https://github.com/BBS-GuT/smartcity-roboter/issues/69) ist eine neue Dokumentationskorrektur und nicht das historische Quell-Issue derselben Nummer.
