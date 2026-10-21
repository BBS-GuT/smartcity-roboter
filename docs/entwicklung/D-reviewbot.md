# Codex-PR-Reviewer: Einrichtung und Betrieb

**Stand: 21.10.2026. Status: Repositoryvorbereitung fertig, Aktivierung offen.**

Dieses Paket liefert die [Review-Regeln](../../AGENTS.md#code-review-rules) für `davidheinrich73/smartcity-roboter`. David verantwortet die GitHub-Freigabe und Aktivierung; die Orchestrierung koordiniert menschliches Review und Integration. Produktcode, CI und Schutzregeln werden mit diesem Paket nicht geändert.

Die [Zieldefinition](../zieldefinition-grundbetrieb.md) ist der fachliche Sollzustand. Der vorhandene [Zustandsvertrag](../schnittstellen-grundbetrieb.md) bezeichnet sich noch als Entwurf; Integration von Vertragsdateien allein bestätigt keine A/B/O-Übergabe. Offene Brokerdetails oder Gerätegrenzen werden hier nicht freigegeben.

## Was David noch machen muss

1. Mit dem vorhandenen ChatGPT-/Codex-Konto anmelden, das die Reviews betreiben soll. Verfügbarkeit von Code Review und dessen Kontingent/Abrechnung im Konto prüfen; Betreiber und Kostenzuordnung festhalten. Ein neuer persönlicher GitHub-Account ist nicht nötig. Reviews erscheinen unter der Integration; Entwickler behalten ihre eigenen Konten.
2. In Codex GitHub verbinden. David genehmigt als Repositoryeigentümer den angeforderten Zugriff bzw. die App-Installation. Berechtigungen lesen und, soweit angeboten, nur `davidheinrich73/smartcity-roboter` auswählen; bei bestehender Installation deren Auswahl prüfen. Keine Passwörter oder persönlichen Tokens im Team verteilen.
3. In den [Code-Review-Einstellungen](https://chatgpt.com/settings/code-review) das Repository wählen, unter `Review code` → `Automatic review` einschalten und für Team-PRs `All PRs` wählen. Persönliche Review-Präferenzen mitprüfen.
4. Bei `Review trigger` die tatsächlich angebotene Auslösung auswählen und wörtlich im Nachweis unten festhalten. Gewünscht sind neue prüfbereite PRs und erneute Reviews nach Pushes. Fehlende Optionen als Grenze dokumentieren; Draft-Verhalten erst nach Prüfung bestätigen.
5. Den Regel-PR durch eine fachkundige andere berechtigte Person prüfen und über die Orchestrierung integrieren lassen. Anschließend den isolierten Bot-Test aus dem nächsten Abschnitt durchführen. Zur Diagnose ist ein PR-Kommentar `@codex review` möglich; eine manuelle Reaktion belegt keine Automatik.
6. Den bestehenden [main-Schutz](#main-schutz-separat-prüfen) mit den Anforderungen aus [D1-ci-betrieb.md](D1-ci-betrieb.md#5-eigentümer-main-schutz-tatsächlich-einrichten) abgleichen, ergänzen und belegen. Die Botprüfung ersetzt die menschliche Freigabe nicht.

Die [offizielle OpenAI-Dokumentation](https://learn.chatgpt.com/docs/third-party/github) beschreibt Repositoryverbindung, Review-Einstellungen mit Push-/Adminberechtigung, Auslösung und AGENTS-Regeln. Konto, Installation und Trigger wurden in Davids Oberfläche noch nicht geprüft; die Anleitung ist kein Aktivierungsnachweis.

## Bot-Test nach Integration und Aktivierung

Nur synthetische Daten und einen ausdrücklich als **TEST – NICHT MERGEN** markierten Branch/PR verwenden. Der Teststand wird niemals auf einem Roboter ausgeführt. Die Änderungen an A-Dateien und einer harmlosen Dokumentationsdatei vorher über die Orchestrierung reservieren. Dies ist ein Folgeversuch, keine Erweiterung des Dateiumfangs dieses Regel-PRs.

Vor Beginn für jeden Fall Basis-SHA, genaue Diff-Stelle und Erwartung festhalten:

| Fall | Kleine Teständerung und Eingabe | Vorab erwartetes Review |
|---|---|---|
| Künstliche Sicherheitsverletzung | Im bestehenden Kamerazeit-/Freigabepfad eine ungültige Aufnahmezeit als aktuell/zulässig behandeln. Frische Bildankunft, ungültiger Aufnahmezeitstempel und ansonsten zulässiger Fahrwunsch müssen dadurch Bewegung erlauben können. Erreichbarkeit durch Quellprüfung oder reine Softwareprobe belegen. | Konkreter sicherheitsrelevanter Befund zur neu eingeführten Fahrt trotz ungültiger Pflichtdaten (GB-13/14, A11); im konkreten erreichbaren Fahrpfad voraussichtlich P1. |
| Zulässiger Gegenfall | Auf demselben Basisstand die Zeitprüfung erhalten und nur deren Diagnose präzisieren: ungültiger Zeitstempel führt weiterhin zu Halt, ein gültiger aktueller Zeitstempel wird weiterhin geprüft. Keine Schwellen lockern. | Kein Befund über eine aufgehobene Sensorprüfung. |
| Unabhängige harmlose Änderung | Auf demselben Basisstand ausschließlich einen Schreibfehler in einer unabhängigen Dokumentation berichtigen. | Kein Sicherheits-/Vertragsbefund allein wegen bestehender Soll-Lücken. |

Die drei Fälle getrennt vorlegen, damit eine Verletzung nicht die Gegenkontrollen verdeckt. Je Fall Review-Link, geprüfte Head-SHA, tatsächlichen Befund oder Ausbleiben, Fehlalarme und Bewertung notieren. Ein übersehener Fehler ist ein negatives Ergebnis und bleibt als Grenze sichtbar. Eine korrigierte Wiederholung ersetzt den ersten Versuch nicht.

Automatik zusätzlich mit getrennten Ereignissen prüfen:

| Ereignis | Durchführung ohne manuellen Review-Kommentar | Beleg / Status |
|---|---|---|
| Neuer PR | Einen Test-PR direkt prüfbereit öffnen. | Offen: Ereigniszeit, Head-SHA und automatisch entstandenen Review-Link erfassen. |
| Draft → Ready for review | Einen weiteren Test-PR als Draft öffnen; etwaiges Draft-Review erfassen, dann auf prüfbereit stellen. | Offen: beide Ereignisse, jeweilige SHA und Botreaktion erfassen. |
| Neuer Push | Nach abgeschlossenem Review eine kleine weitere Änderung auf den Testbranch pushen. | Offen: neue Head-SHA und zugehöriges erneutes Review erfassen. |
| Manuelle Diagnose | Nur getrennt bei Bedarf `@codex review` kommentieren. | Offen; belegt nur manuelle Auslösung. |

Pro Versuch ein Zeitfenster vorab festlegen und ohne Reaktion nur „innerhalb dieses Fensters kein Review“ melden. Vor einem manuellen Aufruf die automatische Beobachtung sichern. Ein Review einer älteren SHA bestätigt den neuen Push nicht. Alle Test-PRs anschließend schließen, niemals mergen. Erkennungsqualität und Triggerabdeckung getrennt bewerten; beides ist noch offen.

## Grenzen

Die offizielle Dokumentation beschreibt derzeit GitHub-Befunde mit Fokus auf P0/P1. Regeln müssen trotzdem angemessene Schweregrade verwenden; kleinere Fehler werden dadurch nicht automatisch veröffentlicht. KI-Erkennung ist nicht deterministisch. Ein fehlender Kommentar bedeutet keine Fehlerfreiheit, und AGENTS.md erzwingt keine Merge-Sperre. Tests, menschliche Freigaben und Branchregeln bleiben erforderlich. Der Reviewer erhält mit diesen Regeln keinen Reparatur-, Merge- oder Gerätefreigabeauftrag.

## Fehlerbehebung

Bei ausbleibendem Review zuerst Repositoryzuordnung, App-Zugriff, Review-Aktivierung, persönliche Präferenzen, gewählten Trigger und angezeigte Nutzungslimits kontrollieren. Danach gegebenenfalls manuell diagnostizieren und die geprüfte Commit-SHA vergleichen. Ein Berechtigungsfehler ist kein erfolgreiches Review. Keine Zugangsdaten in Diagnosebelegen veröffentlichen.

Bei Fehlalarmen Diff-Bezug, Grundbetriebsmodus, Freigabestand des Vertrags und zulässigen Gegenfall prüfen. Die betroffene Regel mit einem kleinen eigenen PR präzisieren und denselben positiven/negativen Kontrollsatz erneut bewerten. Keine Fachtests oder Gerätegrenzen lockern, um den Bot zufriedenzustellen.

## main-Schutz separat prüfen

GitHub-Abfrage am **21.10.2026**, Basis `c404a9335dc1aabf3b0a509aadbc017c64cd57cb`: `main` meldet `protected=true`. Das [Ruleset main](https://github.com/davidheinrich73/smartcity-roboter/rules/25474694) ist aktiv. Die effektiven Regeln enthalten PR-Pflicht mit einem Approval, Force-Push-Sperre (`non_fast_forward`) und die drei D1-Checks mit aktueller Basis (`strict_required_status_checks_policy=true`). Der klassische Schutz-Endpunkt liefert 404; das widerlegt das vorhandene Ruleset nicht.

Gegenüber dem vereinbarten D1-Ziel sind noch zu ergänzen bzw. zu belegen:

- Alte Approvals bei neuem Push verwerfen: aktuell `dismiss_stale_reviews_on_push=false`.
- Erledigte Reviewgespräche verlangen: aktuell `required_review_thread_resolution=false`.
- Löschen von `main` sperren: in den effektiven Regeln fehlt eine `deletion`-Regel.
- Bypass-Ausnahmen einschließlich Administratoren anhand des vollständigen Rulesets prüfen: Die Detailantwort an den Entwicklungszugang enthält keine Bypassliste und bestätigt damit keine Ausnahmefreiheit. Die Wirksamkeit zusätzlich an der gesperrten Mergeanzeige eines PRs ohne Voraussetzungen nachweisen. Keine destruktive Probe auf `main`.

Maßgebliche Checks: `D1 / Python-Syntax (3.10)`, `D1 / Shell-Syntax (bash)` und `D1 / Softwaretests (Ubuntu 22.04, Python 3.10)`, jeweils GitHub Actions. Bestehende Einstellungen gezielt ergänzen, keine Checks umbenennen. Der Entwicklungszugang `letsc4` hat `push=true`, `admin=false`, `maintain=false`; er hat dieses Ruleset nicht verändert. [#50](https://github.com/davidheinrich73/smartcity-roboter/issues/50) bleibt für den vollständigen Eigentümernachweis offen. Ein technisches KI-Review unter dem PR-Autorenkonto ist kein unabhängiges menschliches GitHub-Approval.

## Nachweise und Übergabe

| Punkt | Stand am 21.10.2026 |
|---|---|
| Arbeitsbasis | Frischer eigener Checkout von `origin/main`: `c404a9335dc1aabf3b0a509aadbc017c64cd57cb`; Branch `chore/gb-reviewregeln`. |
| Vorhandene Anweisungen | Vor dem Schreiben keine `AGENTS.md`/`AGENTS.override.md` im Checkout oder in den geprüften Elternverzeichnissen gefunden. Gemeinsame Regeln, D-Auftrag, Register, Zieldefinition und vorhandene Vertragsdateien gelesen. |
| Dateiumfang | Ausschließlich Root-`AGENTS.md` und dieses Dokument. Keine öffentlichen Schnittstellen oder Produkt-/CI-Dateien geändert. |
| Dokumentationsprüfung | 21.10.2026: 29 lokale Links/Anker, verwendete GB-/A-Kennungen, drei Regelgruppen, Dateiumfang, UTF-8 und Markdown geprüft; keine Fehler. `git diff --cached --check` fehlerfrei. Reguläre PR-CI folgt separat. Keine Produkt-Unit-Tests für Markdown hinzugefügt. |
| Regel-PR / Liefercommit | Link und exakter Head werden nach Erstellung hier ergänzt; bis dahin offen. |
| Regeln integriert | Offen: menschlicher fachlicher Gegencheck und Merge durch die Orchestrierung erforderlich. |
| Betreiber / Nutzung | Offen: bestehendes Codex-Konto, Verfügbarkeit, Kontingent/Abrechnung und Kostenzuordnung durch David bestätigen. Keine kostenlose Nutzung zugesagt. |
| GitHub-Verbindung freigegeben | Offen: ausführendes Konto, Datum, ausgewähltes Repository und bereinigten Installationsbeleg erfassen. |
| Automatik eingestellt | Offen: Repositoryoption, persönliche Präferenzen und exakten Wortlaut der Triggeroption(en) aus Davids Oberfläche erfassen. |
| Erkennungsqualität belegt | Offen: drei Fälle mit erwarteten/tatsächlichen Ergebnissen, Datum, Basis-/Head-SHA und Review-Links protokollieren. |
| Automatik belegt | Offen: neuer PR, Draft → Ready und Push jeweils separat dokumentieren; manuellen Diagnoseaufruf getrennt ausweisen. |
| Menschlicher main-Schutz belegt | Teilweise vorhanden; obige Lücken und vollständiger Wirksamkeitsnachweis aus #50 noch offen. |
| Geräte-/Broker-/ROS-Abnahme | Nicht ausgeführt; kein Bestandteil dieses Dokumentationspakets. |

Für jeden späteren Beleg Datum mit Zeitzone, ausführendes Konto, Commit und PR-/Review-/Konfigurationslink festhalten. Test-PRs müssen als geschlossen und ungemergt nachvollziehbar sein. Keine Tokens, Cookies oder personenbezogenen Kontodetails in Screenshots übernehmen.

Vorschlag an die Orchestrierung für [docs/auftraege/README.md](../auftraege/README.md), dort noch nicht eingetragen: **D Review-Regeln / Codex-PR-Reviewer** – reserviert `AGENTS.md`, `docs/entwicklung/D-reviewbot.md`; Repositoryvorbereitung fertig, Integration/Aktivierung/Abnahme offen; menschliches Review und Eigentümeraktivierung durch David, main-Schutz über #50. Kein automatischer Abschluss des Elternauftrags [#15](https://github.com/davidheinrich73/smartcity-roboter/issues/15).
