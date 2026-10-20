# Aufträge für den Grundbetrieb

**Koordination:** Chat „SmartCity – Orchestrierung Grundbetrieb“. Hier werden Aufgaben geschnitten, Dateien reserviert, Schnittstellen geprüft und Integrationen geplant. Produktcode entsteht in getrennten Entwicklungs-Chats und Arbeitskopien.

**Basis am 20.10.2026:** `main` auf `b9f64424d92f64ed4f391a96b6c6718caae43bcd`. Vor jedem Start Remote-Stand prüfen. Diese Aufträge liegen zunächst auf `codex/grundbetrieb` in PR #11; der Dokumentationsbranch ist kein gemeinsamer Produktbranch. Maßgeblich bleibt die [Zieldefinition](../zieldefinition-grundbetrieb.md).

Jede Auftragsdatei ist als Startnachricht für einen Entwicklungs-Chat verwendbar. Zuerst die [gemeinsamen Regeln](00-gemeinsame-regeln.md) lesen. Die folgenden Dateireservierungen konkretisieren und ersetzen die gröbere Ordneraufteilung im bisherigen Entwicklungsvorschlag.

## Jetzt vorbereitete Aufträge

| Auftrag | Empfänger | Erster Liefergegenstand | Status und GitHub-Aufgabe |
|---|---|---|---|
| **O** | Dieser Orchestrator-Chat | Aufgabenregister, Übergaben, fachliches Review und Integrationsreihenfolge | Aktiv; keine Produktentwicklung hier |
| **[A1 Sicherheit](A-sicherheit-und-motorfreigabe.md)** | Unser separater Entwicklungs-Chat, Konto `letsc4` | Sichere Bildzeit-/Pflichtprüfung im Linienfolger mit Regressionstests | Software geprüft und [PR #17](https://github.com/davidheinrich73/smartcity-roboter/pull/17) nach `main` gemergt (`0c7e8b3`); [Geräteprüfung](A1-geraetetest.md) offen; Auftrag [#12](https://github.com/davidheinrich73/smartcity-roboter/issues/12) |
| **[B1 Fahrentscheidungen](B-verkehr-und-navigation.md)** | Weiterer Entwickler / Entwicklungs-Chat | Rot-Halt, sicherer Wende-Fehlerübergang und Grenzen autonomer Hindernisaktionen | Vergabefertig, parallel zu A1; [#13](https://github.com/davidheinrich73/smartcity-roboter/issues/13) |
| **[C1 Zustandsvertrag](C-zustand-mqtt-und-panel.md)** | Weiterer Entwickler / Entwicklungs-Chat | Ein gemeinsamer prüfbarer Vertrag mit Beispielen und Typen | Vergabefertig, priorisierte Schnittstellenlieferung; [#14](https://github.com/davidheinrich73/smartcity-roboter/issues/14) |
| **[D1 Testinfrastruktur](D-tests-ci-und-repository.md)** | Weiterer Entwickler oder anschließend ausdrücklich zugeordneter Bereich | Ein Testaufruf, CI und Beitragsvorlagen | Vergabefertig, bei nur drei Entwicklern separat einplanen; [#15](https://github.com/davidheinrich73/smartcity-roboter/issues/15) |
| **[E1 Geräte und Infrastruktur](E-geraete-und-infrastruktur.md)** | Geräte-, Spielfeld-, Ampel- und Brokerteams | Geräteinventar, Mess-/Regelplan und Partnerfestlegungen | Erhebung bereit zur Vergabe, kein autonomer Fahrauftrag; [#16](https://github.com/davidheinrich73/smartcity-roboter/issues/16) |

Namentliche Empfänger für B–E sind noch nicht eingesetzt. „Vergabefertig“ bedeutet nicht, dass bereits jemand daran arbeitet. Erst nach Übernahme wird ein Auftrag als aktiv geführt. Weitere Aufträge werden hier ergänzt; neue Personen beginnen nicht ungeplant in bereits reservierten Dateien.

**A1-Integrationsnachweis vom 20.10.:** Unabhängiges Quellreview ohne Blocker; am kombinierten Stand alle sieben Softwaretestskripte bestanden (167 ausgegebene Einzelprüfungen und sieben neue unittest-Methoden), 58 Python-Dateien und 13 Shellskripte syntaktisch fehlerfrei. [Maschinelle Zusammenfassung](../pruefungen/2026-10-20-integration.json). Keine ROS-Gesamtsimulation oder reale Geräteprüfung. Die historische Repositoryprüfung auf `b9f6442` bleibt unverändert als Ausgangsnachweis erhalten.

## Exakte Dateireservierungen

| Bereich | Produkt- und Vertragsdateien | Zugehörige Tests und Dokumentation |
|---|---|---|
| **A** | `line_follower/line_follower.py`, `lib/lidar.py`, spätere interne Betriebs-/Motorfreigabemodule, `scripts/env.sh`, `scripts/stopp.sh`; Integrationsbesitzer für `config/roboter.yaml` | `tests/test_line_follower.py`, neue `tests/test_sicherheitsfreigabe.py` und `tests/test_lidar_sicherheit.py`, `docs/entwicklung/A*.md` |
| **B** | `ki/*`, `erkennung/*`, `line_follower/linie.py`, `line_follower/ampel.py`, `line_follower/schilder.py`, `lib/tiefe.py`, `lib/zebra.py`, `config/arm.yaml`; spätere reine Straßenkarten-/Navigationsmodule | `tests/test_entscheider.py`, `tests/test_ampel.py`, `tests/test_schilder.py`, neue Navigationstests, `docs/entwicklung/B*.md` |
| **C** | Gemeinsamer Vertrag und öffentliche Datentypen in `docs/schnittstellen-grundbetrieb.md`, `schemas/grundbetrieb-v1.schema.json`, `lib/grundbetrieb_vertrag.py`; spätere Zustands-/MQTT-Module, `panel/*`, `scripts/panel.sh`, Broker-Konfigurationsvorlage | `tests/panel_demo.py`, neue Zustands-/MQTT-/Paneltests, `docs/entwicklung/C*.md` |
| **D** | `.github/*`, `CONTRIBUTING.md`, `requirements-test.txt`, neuer gemeinsamer Runner `scripts/pruefen.py`, `tests/attrappen/*`; `scripts/simulation.sh` erst in späterem separatem Paket D2 | Infrastrukturtests und `docs/entwicklung/D*.md` |
| **E** | `docs/geraete/*`, `docs/abnahme/*`, `docs/infrastruktur/*`, freigegebene Messdaten | Geräte-/Aufbau-/Brokerprotokolle mit Commit, Identität und Gültigkeit |
| **O** | `docs/auftraege/*`, Aufgabenstatus, Prüfreports und Planungsbranch | Integrationsentscheidungen und dokumentierte Folgeaufträge |

Kartograf, Replay, Greiflernen und bestehende Kartentests werden durch diese Aufträge zunächst nicht umgebaut. Gemeinsame Attrappen gehören D; A/B/C verwenden bei Bedarf eigene lokale Testhilfen in ihren Prüfdateien und melden notwendige Erweiterungen an. Kein Bereich reserviert pauschal alle Skripte, Konfigurationen oder Tests.

## Start und Übergaben

**Sofort unabhängig:** A1 korrigiert den Linienfolgerpfad, B1 die Entscheidungslogik, C1 entwickelt den Vertrag, D1 automatisiert die bestehenden Prüfungen, E1 erhebt Geräte-/Partnerdaten. A1/B1 verändern zunächst keine öffentlichen Nachrichtenformate.

**Danach:** C1 wird fachlich durch A/B/O geprüft. Erst ein dokumentierter akzeptierter Vertragscommit schaltet neue Vertragsadapter, Motorfreigabeintegration A2, Zustand/MQTT C2 und ROS-Navigationsintegration B2 frei. Reine Straßenmodelllogik kann B zuvor getrennt vorbereiten. Ein ungemergter Vertragsentwurf wird nicht stillschweigend zur verbindlichen Abhängigkeit.

| Folgeauftrag | Freigabebedingung |
|---|---|
| A2 Gemeinsamer Motorweg und Sensorqualität | A1 geprüft; C1 akzeptiert; unbekannte Gerätegrenzen bewirken weiterhin Halt |
| B2 Straßenmodell und Navigation | B1 geprüft; Karten-/Zufahrtsregeln geklärt; ROS-Adapter auf akzeptiertem C1 |
| C2 Zustand, Panel und MQTT | C1 akzeptiert; A/B liefern vereinbarte Ergebnisse; Brokerdetails für Projektabnahme bestätigt |
| D2 Parallele Simulationsläufe | Eigenes Paket für Domain, Ports und sämtliche Laufzeitpfade, abgestimmt mit A/C |
| E2 Bewegte Geräteabnahmen | Geprüfter Softwarestand und abgestimmtes betreutes Testfenster; Messgrenzen/STOPP/Isolation geklärt |

## Auftrag des Orchestrators

Der Orchestrator hält Besitzer, Branch, Basiscommit, reservierte Dateien, Status, PR und nächste Abhängigkeit je Auftrag fest. Er prüft Ergebnisse gegen die Zieldefinition, koordiniert Änderungen über Dateigrenzen und bereitet die gemeinsame Integration vor. Umsetzung, Review und Geräteabnahme werden getrennt ausgewiesen.

Entwickler berichten in ihrem Entwicklungs-Chat und PR. Ergebnisse anderer Chats werden hier lesend abgeholt oder von Carsten mit PR-Link/Übergabebericht eingebracht. Direkte Nachrichten zwischen Chats oder an Teammitglieder erfolgen nur bei entsprechender Nutzerautorisierung.

Nach akzeptiertem PR aktualisiert der Orchestrator das Register und erteilt das nächste abgegrenzte Paket. Ein Entwickler startet nicht selbstständig alle beschriebenen Folgestufen.
