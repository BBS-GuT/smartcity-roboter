# Aufträge für den Grundbetrieb

**Koordination:** Chat „Orchestrierung“. Hier werden Aufgaben geteilt, Dateien reserviert, Übergaben protokolliert und Integrationen geplant. Produktcode entsteht in getrennten Entwicklungs-Chats und Arbeitskopien.

**Reviewzuständigkeit seit 21.10.2026:** Code-Reviews übernimmt der automatische Codex-Reviewer. Der Orchestrator führt keine eigenen Code-Reviews durch und beauftragt dafür keine Unteragenten. Er darf Review-/CI-Status für Issuefortschritt und Integrationskoordination auswerten. Die im main-Ruleset verlangte Freigabe durch eine andere berechtigte GitHub-Person bleibt erforderlich; die Botreaktion allein ersetzt diese formale Freigabe nicht.

**Stand 21.10.2026:** Kanonisches Team-Repository ist [BBS-GuT/smartcity-roboter](https://github.com/BBS-GuT/smartcity-roboter), geprüfter `main`-Commit `d92e366907fd538c377c272250a0e2d75120b5e2`. Neue Arbeit beginnt am dann aktuellen BBS-`origin/main`; Basis und Dateigrenze im Auftrag nennen. Issue- und PR-Nummern in diesem Register beziehen sich auf BBS. Das frühere Repository `davidheinrich73/smartcity-roboter` bleibt Quelle historischer Belege.

Zuerst [gemeinsame Regeln](00-gemeinsame-regeln.md), Auftragsdatei und tatsächlichen Issue-Stand lesen. Die [Zieldefinition](../zieldefinition-grundbetrieb.md) beschreibt den Sollzustand. **Bestätigte Fachentscheidung:** Wegräumen gehört zum Grundbetrieb; der Abgleich der älteren Zieldefinition und zugehöriger Regeln bleibt in [#8](https://github.com/BBS-GuT/smartcity-roboter/issues/8) offen. Dieses Register ersetzt diesen Abgleich nicht.

## Aktuelle Aufträge

| Auftrag | Zuständigkeit | Stand und nächster Schritt |
|---|---|---|
| **O** | Orchestrierung | Aktiv: kleine Issues, Dateibesitzer, Abhängigkeiten, Review und Integration koordinieren. |
| **[A1 Sicherheit](A-sicherheit-und-motorfreigabe.md)** | Separater Entwicklungs-Chat; Geräteprüfung getrennt | Softwareauftrag [#1](https://github.com/BBS-GuT/smartcity-roboter/issues/1) abgeschlossen. [Geräteprüfung](A1-geraetetest.md) und offene A11/A12-Nachweise bleiben erforderlich; LiDAR-Restarbeit läuft unter #58. |
| **[B1 Fahrentscheidungen](B-verkehr-und-navigation.md)** | Zugewiesener B-Entwickler | Elternissue [#2](https://github.com/BBS-GuT/smartcity-roboter/issues/2) offen. Rest: Zielabgleich [#8](https://github.com/BBS-GuT/smartcity-roboter/issues/8), begrenzter Arm-Kameraschwenk [#70](https://github.com/BBS-GuT/smartcity-roboter/issues/70) und reale Abnahme. |
| **[C1 Zustandsvertrag](C-zustand-mqtt-und-panel.md)** | Zugewiesener C-Entwickler; A/B/O für Übergaben | [#3](https://github.com/BBS-GuT/smartcity-roboter/issues/3) offen. Vertrags-/Quellenregeln und Verbraucherübergaben am tatsächlichen Lieferstand prüfen; vorhandene Dokumente allein bestätigen keine akzeptierte Gesamtübergabe. |
| **[D1 Testinfrastruktur](D-tests-ci-und-repository.md)** | D1-Entwicklungs-Chat; Orchestrierung für Abgleich | [#4](https://github.com/BBS-GuT/smartcity-roboter/issues/4) und Schutzauftrag [#28](https://github.com/BBS-GuT/smartcity-roboter/issues/28) abgeschlossen; BBS-Belege unten. Alte Beitrags-/CI-Anleitung separat über [#69](https://github.com/BBS-GuT/smartcity-roboter/issues/69) aktualisieren. |
| **[E1 Geräte und Infrastruktur](E-geraete-und-infrastruktur.md)** | Geräte-, Spielfeld-, Ampel- und Brokerteams | [#5](https://github.com/BBS-GuT/smartcity-roboter/issues/5) offen. RM01-LiDAR-Pose über #66 bestätigen; RM02-Messung bleibt eigenständig in [#37](https://github.com/BBS-GuT/smartcity-roboter/issues/37). Keine Gerätefreigabe aus Softwaretests ableiten. |
| **[L LiDAR-Qualität und Geometrie](L-lidar-qualitaet-und-geometrie.md)** | Je Teilschritt ein von O bestätigter Dateibesitzer; Generalprüfung für Belege/Geräteetappen | [#58](https://github.com/BBS-GuT/smartcity-roboter/issues/58) offen. Kleine Aufgaben #59–#67 und [#79](https://github.com/BBS-GuT/smartcity-roboter/issues/79); erster Produktfix #60. Gemeinsame Produktdateien nacheinander bearbeiten. |
| **D Review-Regeln** | Bestehender Entwicklungs-Chat für PR #54 | [PR #54](https://github.com/BBS-GuT/smartcity-roboter/pull/54) bleibt Draft: Räumverbot korrigieren, BBS-Betriebsstand ergänzen und Branch aktualisieren; kleiner Auftrag [#68](https://github.com/BBS-GuT/smartcity-roboter/issues/68). |
| **F1 Lichtlogik** | Bestehender Lieferautor; Hardwareteam für späteren Ausgang | Elternissue [#9](https://github.com/BBS-GuT/smartcity-roboter/issues/9) offen. [PR #55](https://github.com/BBS-GuT/smartcity-roboter/pull/55) bleibt Draft bis Blinkerfix [#53](https://github.com/BBS-GuT/smartcity-roboter/issues/53), aktueller BBS-CI und fremder Freigabe; reale LED-Ansteuerung nicht enthalten. |
| **B1.3 RM02-Praxis** | David als Autor; Orchestrierung für Review und Übergabe | [PR #78](https://github.com/BBS-GuT/smartcity-roboter/pull/78) und kleine Praxis-Issues #71–#77 sind neu hinzugekommen. Softwarelieferung, offene Diagnose und reale Nachprüfung getrennt halten. Die betroffenen B-Dateien und `ki/zentrale.py` vor einer weiteren LiDAR-/B1d-Änderung übergeben. |

Ein offener Auftrag hat erst nach bestätigter Übernahme einen aktiven Besitzer. Neue Helfer beginnen mit einem kleinen Issue und dessen erlaubten Dateien; sie übernehmen keine bereits reservierten Produktdateien parallel.

**BBS-Betriebsnachweis vom 21.10.:** [Codex-Review an PR #57](https://github.com/BBS-GuT/smartcity-roboter/pull/57#issuecomment-6311814166) automatisch beim Öffnen abgeschlossen, ohne manuellen Review-Aufruf. [CI-Lauf 39571559910](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39571559910) bestätigt alle drei D1-Checks und 21/21 Skripte auf dem PR-Mergestand mit Basis `d92e366`; er ist kein eigener BBS-main-push-Nachweis. [Aktives main-Ruleset 25533179](https://github.com/BBS-GuT/smartcity-roboter/rules/25533179) verlangt fremde Freigabe, aktuelle Basis, erledigte Gespräche und die drei GitHub-Actions-Checks, verwirft alte Approvals und sperrt Force-Push/Löschen ohne Bypass. Der Testmerge blieb trotz grüner CI wegen fehlender fremder Approval gesperrt. Gemergte PR-Branches werden automatisch gelöscht; die ungemergten Prüf-PRs #56/#57 wurden geschlossen und ihre Prüfbranches separat entfernt. Details: #4/#28. Draft→Ready- und Push-Reviewtrigger wurden nicht gesondert abgenommen.

**Historischer A1-Beleg vom 20.10.:** [Quell-PR #17](https://github.com/davidheinrich73/smartcity-roboter/pull/17) integrierte die damalige Softwarekorrektur (`0c7e8b3`); sieben Testskripte, 58 Python-Dateien und 13 Shellskripte bestanden am kombinierten Stand. [Maschinelle Zusammenfassung](../pruefungen/2026-10-20-integration.json). Keine ROS-Gesamtsimulation oder reale Geräteprüfung. Der Ausgangsstand `b9f6442` und [Quell-Planungs-PR #11](https://github.com/davidheinrich73/smartcity-roboter/pull/11) bleiben historische Nachweise.

## Dateireservierungen

| Bereich | Produkt- und Vertragsdateien | Tests und Dokumentation |
|---|---|---|
| **A** | `line_follower/line_follower.py`, `lib/lidar.py`, interne Motorfreigabemodule, `scripts/env.sh`, `scripts/stopp.sh`; Integrationsbesitzer für `config/roboter.yaml` | Sicherheits-/Linienfolgertests, `docs/entwicklung/A*.md` |
| **B** | `ki/*`, `erkennung/*`, `line_follower/linie.py`, `line_follower/ampel.py`, `line_follower/schilder.py`, `lib/tiefe.py`, `lib/zebra.py`, `config/arm.yaml`, reine Navigation | Entscheidungs-/Verkehrstests, `docs/entwicklung/B*.md` |
| **C** | Gemeinsamer Vertrag, `schemas/grundbetrieb-v1.schema.json`, `lib/grundbetrieb_vertrag.py`, Zustands-/MQTT-Module, `panel/*`, `scripts/panel.sh` | Zustands-/MQTT-/Paneltests, `docs/entwicklung/C*.md` |
| **D** | `.github/*`, `CONTRIBUTING.md`, `requirements-test.txt`, `scripts/pruefen.py`, `tests/attrappen/*`; Simulation erst im eigenen D2-Paket | Infrastrukturtests, `docs/entwicklung/D*.md` |
| **E** | `docs/geraete/*`, `docs/abnahme/*`, `docs/infrastruktur/*`, freigegebene Messdaten | Geräte-/Partnerprotokolle mit Commit, Identität und Gültigkeit |
| **O** | `docs/auftraege/*`, Aufgabenstatus und Koordinationsberichte | Übergaben, Integrationsentscheidungen und Folgeaufträge |

**Befristete L-Übergabe:** Für #60–#65 und #79 koordiniert O die übergreifenden Änderungen an `lib/lidar.py`, `ki/zentrale.py` und `line_follower/line_follower.py` mit A/B. PR #78 überschneidet sich bei `ki/zentrale.py`; #70 und PR #78 teilen außerdem B-Entscheidungsdateien. Diese Arbeiten beginnen nicht parallel ohne ausdrückliche Dateiübergabe. Pro betroffener Datei darf genau ein aktiver Schreibauftrag bestehen; die Übergabe zum nächsten Issue erfolgt nach geprüftem Lieferstand. Die allgemeine A/B-Zuständigkeit entfällt dadurch nicht. Einzelheiten stehen im L-Auftrag. Gemeinsame Attrappen und Runner bleiben bei D; kein Auftrag reserviert pauschal alle Tests.

## Start, Übergaben und Integration

Unabhängige Belege, Messpläne und getrennte Tests können parallel vorbereitet werden. Gemeinsame Produktdateien werden nach Issue und Besitzer nacheinander geliefert. Für C1 bleibt die dokumentierte A/B/O-Annahme des tatsächlichen Vertragscommits Voraussetzung neuer Vertragsadapter; vorhandene Dateien oder ein ungemergter Entwurf ersetzen sie nicht.

| Folgestufe | Voraussetzung |
|---|---|
| A2 Gemeinsamer Motorweg und Sensorqualität | Geprüfte A1-/LiDAR-Lieferungen, akzeptierte nötige C1-Übergaben; unbekannte Gerätegrenzen geben keine Bewegung frei |
| B2 Straßenmodell und Navigation | B1-Reste und Karten-/Zufahrtsregeln geklärt; ROS-Adapter auf akzeptiertem C1 |
| C2 Zustand, Panel und MQTT | Akzeptierter C1-Stand, vereinbarte A/B-Ergebnisse und bestätigte Brokerdetails |
| D2 Parallele Simulation | Eigenes Paket für Domain, Ports und sämtliche Laufzeitpfade, abgestimmt mit A/C |
| E2 Bewegte Geräteabnahme | Geprüfter installierter Commit, Konfiguration und abgestimmtes betreutes Testfenster; LiDAR zunächst statisch gemäß #67 |

Die Orchestrierung hält Besitzer, Basis-/Liefercommit, Branch/PR, Dateigrenze und nächste Abhängigkeit fest. Entwickler liefern kleine PRs mit tatsächlichen Testergebnissen. Vor Merge sind aktueller BBS-Stand, grüne Pflichtchecks, erledigte Gespräche und eine andere berechtigte Freigabe erforderlich; danach folgt der separate main-Lauf. Softwaretest, ROS-Simulation und Geräteabnahme werden getrennt berichtet.

Ergebnisse anderer Chats werden lesend abgeholt oder durch Carsten eingebracht. Direkte Chat-/Teamnachrichten benötigen Nutzerautorisierung. Kein Entwickler startet ungeplant alle Folgestufen oder schreibt auf fremden Arbeitskopien.
