# D1: CI betreiben und main-Schutz abschließen

**Repository-Wechsel am 21.10.2026:** Aktuelles Arbeitsrepository ist `BKoewenig/smartcity-roboter`. Die unten verlinkten Issues, PRs, CI-L?ufe und Rechteangaben dokumentieren das urspr?ngliche Repository; sie belegen keinen Status des neuen Repositorys. Siehe [Repository-Wechsel](repository-wechsel.md).

Diese Anleitung ist der verbindliche Ablauf für Beiträge, CI-Nachweise und die Eigentümeraktion [#50](https://github.com/davidheinrich73/smartcity-roboter/issues/50). Zuständigkeiten und Dateigrenzen stehen im [Auftragsregister](../auftraege/README.md); fachliche Fahrregeln werden hier nicht festgelegt.

**Geprüfter Stand 20.10.2026:** Ursprüngliche D1-Software und CI sind integriert. Der [main-Lauf 39407908409](https://github.com/davidheinrich73/smartcity-roboter/actions/runs/39407908409) auf `d9917652087aec4684c1bf6a20837879d6961b1d` ist vollständig grün: Ubuntu 22.04.5, Python 3.10.22, 13/13 Testskripte, Runner 8/8, Vertragsprüfung mit jsonschema 20/20, `pip check` erfolgreich, keine Fehler/Timeouts/Skips. Die Skriptzahl ist ein Ergebnis dieses Stands, kein festes Soll.

Die Orchestrierung meldet zum 20.10.2026, 12:17 Uhr Europe/Berlin: Workflow aktiv, `main` ungeschützt (`protected=false`), effektive Ruleset-Regeln und Rulesets leer. Der Entwicklungszugang `letsc4` hat `push=true`, aber `admin=false`/`maintain=false`. **Status dieses Bearbeitungsstands: ursprüngliche D1-Software integriert; Ergänzungen #68/#69 in Arbeit; #50 administrativ offen.** [#15](https://github.com/davidheinrich73/smartcity-roboter/issues/15) bleibt bis zum nachgewiesenen Gesamtabschluss einschließlich [#68](https://github.com/davidheinrich73/smartcity-roboter/issues/68)/[#69](https://github.com/davidheinrich73/smartcity-roboter/issues/69) offen. Die Orchestrierung schreibt den Status in diesen Issues fort; der Eigentümer prüft den dann aktuellen Regelzustand vor jeder Änderung neu.

## 1. Auslösung, Checks und Logs

Maßgeblich ist [.github/workflows/grundbetrieb-tests.yml](../../.github/workflows/grundbetrieb-tests.yml), Workflow **Grundbetrieb - Softwarepruefung**. Die Ergänzung aus [PR #70 / #68](https://github.com/davidheinrich73/smartcity-roboter/pull/70) macht den vollständigen PR-Ereignissatz ausdrücklich: `opened`, `synchronize`, `reopened`, `edited`, jeweils nur mit Zielbranch `main`. So startet auch der Zielwechsel eines bestehenden PRs nach `main` bei unverändertem Head einen neuen Lauf. PR-Quellbranches sind nicht eingeschränkt. Titel-/Beschreibungskorrekturen können ebenfalls `edited` auslösen.

Pushes starten den Workflow auf `main`, `chore/gb-*`, `fix/gb-*` und `test/gb-*`. Ein Push etwa auf `docs/*` allein startet ihn nicht; dessen PR nach `main` schon. Ein PR auf eine andere Zielbase ist kein main-PR. Es gibt keinen `workflow_dispatch`-, Zeitplan- oder Merge-Queue-Trigger.

| Exakter Checkname | Prüfung | Joblimit | Erfolgreicher main-Beleg |
|---|---|---|---|
| `D1 / Python-Syntax (3.10)` | Versionierte Pythondateien kompilieren, ohne ROS-/Produktimports | 5 min | [68 Dateien](https://github.com/davidheinrich73/smartcity-roboter/actions/runs/39407908409/job/118578241978) |
| `D1 / Shell-Syntax (bash)` | Versionierte Shellskripte mit `bash -n` | 5 min | [13 Skripte](https://github.com/davidheinrich73/smartcity-roboter/actions/runs/39407908409/job/118578242084) |
| `D1 / Softwaretests (Ubuntu 22.04, Python 3.10)` | Pflichtimporte, `pip check`, gemeinsamer Runner | 40 min | [13/13 Skripte](https://github.com/davidheinrich73/smartcity-roboter/actions/runs/39407908409/job/118578242205) |

Der Runner entdeckt alle eigenständig ausführbaren `tests/test_*.py` direkt unter `tests/`, führt sie alphabetisch in eigenen Prozessen mit Projektwurzel als Arbeitsverzeichnis aus und liefert bei Fehler, Timeout oder ausgewiesenen unittest-Skips einen Fehlercode. Auch kombinierte Skip-Zusammenfassungen werden erkannt; erwartete Fehler allein bleiben nach unittest-Regeln erfolgreich. Der Timeout beendet nur den eigenen Testprozessbaum. Historische Fehlerprobes unter `docs/pruefungen/` werden nicht als Regression ausgeführt.

CI erlaubt 120 s je Testskript und 600 s für `test_karte.py`. Der lokale Runnerstandard ohne Parameter ist 300 s; für einen vergleichbaren Lauf die unten angegebenen Parameter verwenden. Einzellogs und `umgebung.log` mit Plattform und `pip freeze` liegen im Workflow-Artefakt `d1-softwaretestlogs-<run_id>-<run_attempt>`, auch nach Testfehlern, für 14 Tage. Benötigte Abnahmebelege rechtzeitig sichern und mit Commit/Run/Versuch zuordnen. Fehlende Logs nach einem Installationsabbruch sind kein Testnachweis.

Workflowrechte bleiben `contents: read`; Checkout-Zugangsdaten werden nicht persistiert. Keine Projektbroker, privaten Schlüssel, Roboter- oder Hardwaredienste für diese Prüfungen verwenden. Checknamen bei Änderungen mit Eigentümer und Orchestrierung abstimmen, damit Pflichtchecks nicht auf alte Namen zeigen.

## 2. Lokal reproduzieren

Im eigenen Checkout ab geprüftem `origin/main` eine isolierte Umgebung verwenden. Unter Ubuntu 22.04 mit vorhandenem Python 3.10 aus der Projektwurzel:

```bash
python3.10 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-test.txt
python -m pip check
python --version
python -m pip freeze
python scripts/pruefen.py --timeout 120 --test-timeout test_karte.py=600 --log-dir .venv/d1-testlogs
```

Unter Windows mit vorhandenem Python 3.10 eine eigene Umgebung mit `py -3.10 -m venv .venv` anlegen; anschließend dieselben Befehle mit `.venv\Scripts\python.exe` statt `python` ausführen. Ein Windowslauf wird als Windowslauf berichtet; er bestätigt keine Ubuntu-Plattform. Ein beschreibbares eigenes `TEMP`/`TMP` verwenden, falls das Systemtempverzeichnis gesperrt ist. Die Beendigung eigener Testkinder muss im Laufzeitumfeld erlaubt sein; verweigerte Prozessbeendigung als Fehler untersuchen, nicht überspringen.

Die acht getesteten Pins aus [requirements-test.txt](../../requirements-test.txt) sind:

| Paket | Version | Paket | Version |
|---|---|---|---|
| numpy | 1.26.4 | opencv-python-headless | 4.10.0.84 |
| PyYAML | 6.0.2 | jsonschema | 4.23.0 |
| attrs | 24.2.0 | jsonschema-specifications | 2023.12.1 |
| referencing | 0.35.1 | rpds-py | 0.20.0 |

Ubuntu/CPython 3.10.22 ist im obigen main-Lauf tatsächlich geprüft; Windows/CPython 3.12.14 ist als früherer Gegencheck im [Umgebungsnachweis](D1-testumgebung.md) dokumentiert. CI wählt die Reihe `3.10` und protokolliert die tatsächliche Patchversion. Vor Paketänderungen Kompatibilität in einer isolierten Umgebung prüfen, danach Pflichtimporte, `pip check`, Schema-Prüfung und Gesamtlauf nachweisen. `jsonschema` ist Pflicht; kein fehlendes Paket oder wesentlicher Skip wird als Erfolg behandelt.

## 3. Einen roten Lauf untersuchen

1. Commit, Event, Run-ID, Versuch, betroffenen Job und den ersten fehlerhaften Schritt festhalten. Installations-, Syntax-, Fachtest- und Runnerfehler getrennt benennen; stdout/stderr und vorhandenes Artefakt sichern.
2. Bei Fachtestfehlern eine kleine Reproduktion und den zuständigen Besitzer bestimmen. Weder Fachschwellen lockern noch automatisch wiederholen, bis zufällig Grün entsteht. Fehler/Timeout/Skip bleiben sichtbar.
3. Bei Download-, Verbindungs- oder Hashfehlern das Paket des fehlgeschlagenen Versuchs nicht verwenden. Dateiname, Quelle, vollständige Größe sowie erwarteten und erhaltenen SHA256 vergleichen. Die Originalerwartung gegen die offizielle Paketmetadatenquelle prüfen; mit einem frischen vollständigen Download erneut regulär verifizieren. Keine Hashprüfung abschalten, keinen erhaltenen Fehlhash als neuen Sollwert übernehmen und kein Paket austauschen, nur um Grün zu erhalten. Wiederholte Abweichungen an die Orchestrierung geben; bis zur Klärung keine Abnahme.
4. Ist ein temporärer Downloadabbruch belegt, unter **Actions → betroffener Lauf → Re-run jobs → Re-run failed jobs** gezielt erneut ausführen; laufende Wiederholungen nicht doppelt starten. Alten Fehler, Grund und neuen Versuch verlinken. Danach müssen Installation, `pip check` und alle tatsächlich gestarteten Tests erfolgreich sein. Ein normaler fachlicher Fehler wird so nicht weggewischt. [GitHub: Wiederholungen](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs).

Beleg aus D1: Im [PR-Lauf 39402654038](https://github.com/davidheinrich73/smartcity-roboter/actions/runs/39402654038) brach ein OpenCV-Download bei etwa 19,3/49,9 MB an der Hashprüfung ab. Die vollständige Originaldatei hatte 49.858.781 Bytes und SHA256 `377d08a7e48a1405b5e84afcbe4798464ce7ee17081c1c23619c8b398ff18295`, bestätigt gegen [PyPI-Metadaten](https://pypi.org/pypi/opencv-python-headless/4.10.0.84/json). Die gezielte Wiederholung bestand mit unveränderten Pins und Originalprüfung; das war kein behobener Fachtestfehler.

## 4. PR-Erfolg und main-Erfolg belegen

Ein PR-Nachweis gehört zum konkreten PR-Head und seiner main-Basis. `pull_request` prüft mit dem bestehenden Checkout den synthetischen Mergestand `refs/pull/<Nummer>/merge`; deshalb Head-SHA, Basis-SHA und die tatsächlich ausgecheckte Run-/Merge-SHA festhalten. Vor Integration über die Eltern/Ahnen dieser ausgecheckten SHA bestätigen, dass die aktuelle main-SHA enthalten ist; allein die inzwischen aktualisierte Basisangabe der PR-API genügt nicht. Ein beliebiger erfolgreicher Branch-Push genügt ebenfalls nicht. Nach Änderungen am Head oder einer nötigen Aktualisierung auf main einen neuen passenden PR-Lauf abwarten. Eine Wiederholung verwendet SHA und Ref des ursprünglichen Ereignisses und prüft keine neuen Commits. [GitHub: PR-Mergestand](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request).

Für jede Integration dokumentiert die Orchestrierung PR, Head/Basis, erforderliche andere Reviewperson, erledigte Gespräche und die drei erfolgreichen aktuellen PR-Checklinks. Nach dem Merge folgt der separate `push`-Lauf auf der tatsächlichen main-Merge-SHA; auch dessen drei Ergebnisse, Testzahlen, Fehler/Skips und Paketversionen festhalten. Der oben verlinkte main-Lauf auf `d991765` ist ein solcher Integrationsnachweis. Er bestätigt weder spätere main-Commits noch eingerichteten Branchschutz.

## 5. Eigentümer: main-Schutz tatsächlich einrichten

Die folgenden Schritte führt der in [#50](https://github.com/davidheinrich73/smartcity-roboter/issues/50) zuständige Repositoryeigentümer mit passenden Regel-/Adminrechten aus. Der Entwicklungszugang kann dies nicht stellvertretend aktivieren. Bereits vorhandene Regeln zuerst lesen und gezielt bearbeiten; keine neu eingerichtete Regel ungeprüft ersetzen.

In `BKoewenig/smartcity-roboter`: **Settings → Branches → Add classic branch protection rule**, Branch name pattern **`main`**. Existiert bereits die zutreffende Regel, **Edit** verwenden. Dann setzen:

| GitHub-Einstellung | Verbindliche Auswahl |
|---|---|
| Require a pull request before merging | an |
| Require approvals | an, **1** fachkundige andere berechtigte Reviewperson |
| Dismiss stale pull request approvals when new commits are pushed | an |
| Require conversation resolution before merging | an |
| Require status checks to pass before merging | an; exakt die drei Checknamen aus Abschnitt 1, Quelle **GitHub Actions** |
| Require branches to be up to date before merging | **an**: aktuelle main-Basis und passende neue Checks verlangen |
| Allow specified actors to bypass required pull requests | aus; keine Bypass-Ausnahmen |
| Do not allow bypassing the above settings | **an**, damit Regeln auch Administratoren und Bypass-Rollen binden |
| Allow force pushes / Allow deletions | beide **aus** |

Mit **Create** bzw. **Save changes** speichern und die gespeicherte Regel erneut öffnen. [GitHub: Einrichtung](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule), [Wirkung der Einstellungen](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

Eine technische Prüfung durch einen anderen Agentenchat unter demselben PR-Autorenkonto `letsc4` ist kein unabhängiges GitHub-Approval. Erforderlich ist die Freigabe eines tatsächlich anderen berechtigten GitHub-Kontos durch eine fachkundige Reviewperson; auch eine administrative Integration darf die Regel nicht umgehen. CODEOWNERS und unbekannte Konten werden mit diesem Paket nicht eingerichtet.

Falls der Eigentümer stattdessen vorhandene Rulesets verwendet, müssen sie für `main` **Active** sein und dieselben Anforderungen ohne Bypass wirksam abbilden; reine Auswertung oder ein gespeicherter Entwurf genügt nicht. Die hier beschriebene klassische Klickfolge ist der konkrete Einrichtungsweg für den bislang ungeschützten Stand.

## 6. Belege und Abschluss von #50 / #15

In #50 legt der Eigentümer Datum mit Zeitzone, ausführendes berechtigtes Konto, Link zur gespeicherten Regel und einen bereinigten Screenshot oder lesbaren Konfigurationsexport ab. Keine Tokens, Cookies oder Zugangsdaten veröffentlichen. Der Beleg muss sämtliche Einstellungen aus Abschnitt 5 zeigen, einschließlich aller drei exakten Pflichtchecks, aktueller Basis und angewendeter Administratorregeln.

Bei klassischem Schutz bestätigt die gespeicherte Konfiguration aus `GET /repos/BKoewenig/smartcity-roboter/branches/main/protection` insbesondere: `required_approving_review_count=1`, `dismiss_stale_reviews=true`, `required_status_checks.strict=true` und die drei Checks, `required_conversation_resolution.enabled=true`, `enforce_admins.enabled=true`, keine PR-Bypass-Ausnahmen sowie `allow_force_pushes.enabled=false`/`allow_deletions.enabled=false`. Dazu `protected=true` für main festhalten. Bei Rulesets die aktive Zielauswahl und tatsächlich wirksamen main-Regeln belegen; leere Ruleset-Listen allein beurteilen keinen klassischen Branchschutz. Ein wegen fehlender Leserechte abgewiesener Abruf ist kein Wirksamkeitsnachweis. [GitHub: Schutzkonfiguration lesen](https://docs.github.com/en/rest/branches/branch-protection#get-branch-protection).

Am nächsten echten PR ohne die nötige andere Freigabe bzw. mit noch offenen Voraussetzungen die gesperrte Mergeanzeige belegen, ohne nach main zu integrieren. Danach auf aktueller Basis andere Freigabe, erledigte Gespräche und alle drei erfolgreichen Checks mit ihren SHA-/Run-Links nachweisen. Force-Push oder Löschen nicht am echten main ausprobieren; deren Sperre aus der wirksamen Konfiguration belegen.

Erst mit aktivem und belegtem Schutz kann die Orchestrierung #50 als erfüllt abgleichen. #15 wird erst geschlossen, wenn zusätzlich #68/#69 integriert sind und der aktuelle PR-/main-CI-Nachweis vorliegt. Solange diese Ergänzungen laufen, lautet die Übergabe **„Ursprüngliche D1-Software integriert; #68/#69 in Arbeit; #50 administrativ offen“**. Nach deren Integration bis zum Nachweis aus #50 lautet sie **„D1-Software fertig; #50 administrativ offen“**. Keine dieser Phasen ist pauschal „D1 vollständig erledigt“. D1 liefert Code/Dokumentation/PR-Belege; die Orchestrierung pflegt die Issues.

Grüne Softwarechecks sind keine Gerätefreigabe. ROS-Simulation, reale Bewegung, Brokerempfang und Viergerätebetrieb benötigen eigene Abnahmen. Dokumentierte [Praxisbefunde](../problemprotokoll.md) mit Gerätekennung, Softwarestand und Mess-/Logbezug bleiben in der fachlichen Bewertung zu berücksichtigen; historische Probes sind keine bestandenen Regressionen.
