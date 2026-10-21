# L: LiDAR-Qualität und gemeinsamer Roboterbezug

**Elternauftrag:** [#58](https://github.com/BBS-GuT/smartcity-roboter/issues/58), BBS-Repository. **Prüfstand 21.10.2026:** `d92e366907fd538c377c272250a0e2d75120b5e2`, auch für RM01 bestätigt. Jeder Entwicklungsauftrag startet trotzdem am dann aktuellen BBS-`origin/main` und nennt seinen genauen Basiscommit.

RM01-Befunde und reine Gegenproben zeigen getrennte Lücken bei ungültigen Scans, Pflichtquellen, Aufnahmezeit, Sensor-/Roboterkoordinaten und der tatsächlich angeforderten Fahrtrichtung. Die vorhandenen radialen Referenzen begründen keine pauschale Distanzkorrektur und keinen nachgewiesenen Treiberfehler. Werksmodellwerte sind Test-/Modellquellen, keine bestätigte Einbaukalibrierung.

## Kleine Aufträge

Jedes Issue enthält seinen begrenzten Fehlerfall, erlaubte Dateien und positive/negative Kontrollen. Je Lieferung ein kleiner PR; nicht alle Zeilen als einen Gesamtumbau übernehmen.

| Issue | Liefergegenstand | Reihenfolge / Grenze |
|---|---|---|
| [#59 L0a](https://github.com/BBS-GuT/smartcity-roboter/issues/59) | Bereinigte RM01-Berichte, Commit-/Konfigurationsbezug und vorhandenen Offline-Prototyp nachvollziehbar sichern | Generalprüfchat liefert Belege/Entwurf; kein Produktfix und keine Gerätefreigabe |
| [#60 L1](https://github.com/BBS-GuT/smartcity-roboter/issues/60) | Vollständig ungültige/leere Scans in KI und finalem Haltpfad als unbekannt statt frei behandeln | **Erster Produktfix.** Gemeinsame Qualitätsentscheidung und kleine Verbraucheränderungen; Geometrie und Uhren hier nicht umbauen |
| [#61 L2](https://github.com/BBS-GuT/smartcity-roboter/issues/61) | Fehlenden/veralteten Pflichtkanal trotz frischem zweiten Kanal sperren | Nach #60; Pflichtquellen explizit festhalten, optional und erforderlich unterscheiden |
| [#62 L3](https://github.com/BBS-GuT/smartcity-roboter/issues/62) | Alten Aufnahmeheader trotz frischem Empfang zurückweisen | Nach #60/#61 und Dateifreigabe; passende ROS-Uhrdomäne und monotones Empfangsalter getrennt prüfen |
| [#63 L4](https://github.com/BBS-GuT/smartcity-roboter/issues/63) | Reine quellenbezogene Sensor-zu-Roboter-Transformation samt Frame-/Poseprüfung | Nur nach Freigabe derselben `lib/lidar.py`; synthetische Posen testen, Messfreigabe #66 getrennt |
| [#64 L5](https://github.com/BBS-GuT/smartcity-roboter/issues/64) | Gemeinsamen Roboterbezug einmal pro Quelle vor Hindernis-/Rückwärts-/Haltprüfung anwenden | Nach #60/#61/#62/#63/#65/#79 und bestätigter Pose #66; Panelansicht und Kartograf-Kalibrierung nicht still global verschieben |
| [#65 L6](https://github.com/BBS-GuT/smartcity-roboter/issues/65) | Finalen Schutz aus tatsächlich ausgegebenem Fahrvektor ableiten, auch bei Rückwärts-Manöver | Nach #60/#61/#62; nacheinander in `line_follower.py`, kein neuer öffentlicher Fahrwunschvertrag |
| [#79 L7](https://github.com/BBS-GuT/smartcity-roboter/issues/79) | Unbekannten Fahrbereich trotz gültiger seitlicher Punkte sperren | Nach den Qualitäts-/Zeitfixes, mit dem tatsächlichen Fahrvektor aus #65; keine willkürliche globale Gültigkeitsquote |
| [#66 E1-L](https://github.com/BBS-GuT/smartcity-roboter/issues/66) | RM01-Quellen, Frames, Einbaupose und Messunsicherheit bestätigen | Gerätebelege unter E1 #5; RM02 bleibt eigenständig #37 |
| [#67 E2-L](https://github.com/BBS-GuT/smartcity-roboter/issues/67) | Korrigierten installierten Stand mit Fehlerfällen und gültiger Wiederkehr abnehmen | Nach erforderlichen Fixes und #66; erst statisch, reale Halt-/Reaktions-/Wiederfreigabeprüfung als eigene abgestimmte Etappe |

## Wer schreibt wo?

O bestätigt vor Beginn einen Besitzer, ein Issue, einen Branch und die erlaubten Dateien. `lib/lidar.py`, `ki/zentrale.py` und `line_follower/line_follower.py` haben **jeweils nur einen aktiven Schreibauftrag**. Keine parallelen Vollüberarbeitungen. Die nächste Änderung beginnt nach geprüfter Übergabe auf dem aktualisierten BBS-main beziehungsweise einem von O ausdrücklich vereinbarten Lieferstand. Damit stimmen A-Sicherheitsweg und B-Entscheidungspfad weiterhin überein.

[PR #78](https://github.com/BBS-GuT/smartcity-roboter/pull/78) ist in BBS-`main` integriert und begründet keine aktive Dateisperre mehr. Der erste Produktfix #60 beginnt am aktuellen `origin/main` einschließlich dieses Lieferstands. O prüft vor Übernahme ausschließlich tatsächlich neue aktive Schreibaufträge für `ki/zentrale.py`; nur bei einer solchen laufenden Bearbeitung ist eine zusätzliche Dateiübergabe nötig. Unabhängige Tests, reine Entwürfe und die Dokumentationsaufgabe #59 sind weiter parallel vorbereitbar.

Der Chat **„SmartCity – Generalprüfung am Roboter“** sammelt Geräte-/Versionsbelege, bereitet Offline-Entwürfe vor und führt abgestimmte Geräteetappen durch. Seine noch nicht integrierten Entwürfe sind weder Produktlieferung noch Abnahme. Für Produktfixes werden separate Entwicklungsarbeitskopien verwendet; vorhandenen Entwurf einmal zuordnen, keinen zweiten konkurrierenden Fix starten. Gemeinsame Attrappen/Runner bleiben bei D. Änderungen an `config/roboter.yaml` mit A abstimmen; reale lokale Kalibrierwerte nicht ungeprüft veröffentlichen.

## Lieferung und Freigabe

Code-Reviews übernimmt nach der aktuellen Nutzerentscheidung der automatische Codex-Reviewer. Die Orchestrierung koordiniert Issues, Dateibesitzer, Abhängigkeiten und die Übergabe der automatischen Ergebnisse; sie führt keine zusätzlichen eigenen Code-Reviews durch. Die formale fremde GitHub-Freigabe aus dem main-Ruleset bleibt bestehen.

Fehlerfall und zulässigen Gegenfall im gemeinsamen Runner nachweisen: ungültig ist nicht frei; gültige freie Daten, echtes nahes Hindernis und gültige Rückkehr bleiben unterscheidbar. Nur lokale ROS-/Publisherattrappen für Softwareproben benutzen. Keine Fachschwellen für grüne Tests lockern. Head, Basis, CI und tatsächlich verwendete Quellen-/Uhr-/Frameannahmen im PR nennen. Aktuelle Pflichtchecks und fremde Freigabe bleiben erforderlich.

Geräteprüfung bestätigt zuerst installierten Commit und Konfiguration. Methodenrückgaben belegen keinen realen Stillstand. Fahr-/Armversuche benötigen ihre eigene abgestimmte Testetappe; A11/A12 bleiben bis zur tatsächlichen Abnahme offen. [#34](https://github.com/BBS-GuT/smartcity-roboter/issues/34) zur Kartenkalibrierung und [#37](https://github.com/BBS-GuT/smartcity-roboter/issues/37) zur RM02-Messung werden nicht aus RM01-Belegen geschlossen. C1-Quellenregeln (#13/#14) berücksichtigen, ohne den kleinen internen Schutzfix auf die gesamte C1-Integration warten zu lassen.

Die vollständige Zielharmonisierung bleibt bei [#8](https://github.com/BBS-GuT/smartcity-roboter/issues/8). Dieser L-Auftrag erweitert keine Räumfunktionen oder öffentlichen Nachrichtenformate und erteilt keine allgemeine Fahrfreigabe.
