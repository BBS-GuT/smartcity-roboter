# LiDAR: Softwarestand und ausstehende Nachweise am 22.10.2026

Bezug: [#58](https://github.com/BBS-GuT/smartcity-roboter/issues/58) mit allen
Unteraufgaben. Schutzkorrektur #176 und Mess-/Ausfallvorbereitung #172 sind nach
erfolgreicher nativer Prüfung im Sammelbranch integriert; ihre Lieferung nach main
bleibt getrennt offen.
Es wird keine Gerätefreigabe behauptet. Geprüfte Ausgangsbasis ist main
`dc6acc25e490edc301a6464af8fe19e17339aa42` mit integriertem
[PR #170](https://github.com/BBS-GuT/smartcity-roboter/pull/170).

## Vorbereitete Unterlieferungen

| Lieferung | Exakter Kandidat | Prüfung / Integrationsgrenze |
|---|---|---|
| [#172: Mess- und Ausfallmatrix](https://github.com/BBS-GuT/smartcity-roboter/pull/172) | `daa8db47ba74c3248bcd0fb62a09494dd5c8abe9` | [Linux-CI 43/43](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39843961334), [nativer Review](https://github.com/BBS-GuT/smartcity-roboter/pull/172#issuecomment-6349216160) am exakten Head abgeschlossen ohne Befunde/offene Befunde. P2 zur gemeinsamen statt nur einzelnen Messlücke behoben, Thread gelöst. Im Sammelbranch integriert; keine Geräteabnahme. |
| [#176: fehlende Geometrie sperren und explizite Simulationsgeometrie](https://github.com/BBS-GuT/smartcity-roboter/pull/176) | `ac56051b438375ea63220120d4158837d2b690cb` | [Linux-CI 44/44](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39841340080/job/120042856186), alle Pflichtchecks erfolgreich. [Nativer Review am exakten Head abgeschlossen ohne Befunde](https://github.com/BBS-GuT/smartcity-roboter/pull/176#issuecomment-6349329512). Als `3d4684cb16a3652e3a05c90ff0cc6bdd10a39e2c` in den Sammelbranch integriert; kein main-Merge. |

Die Unter-PRs zielen auf `fix/gb-58-lidar`. Erst nach den geforderten tatsächlichen
Prüfergebnissen integrieren; für den abschließenden Haupt-PR zählen erneut dessen
eigener Head, aktuelle main-Basis, CI, nativer Review und angerechnete Fremdfreigabe.
Ein grüner Testlauf ersetzt keinen dieser Nachweise. Kein Reviewersatz durch den
implementierenden Chat und keine Umgehung der Schutzregeln.

Ein früherer nativer Review von #176 war wegen eines Nutzungslimits abgebrochen.
Der notwendige Simulationsnachtrag startete regulär eine neue Prüfung am obigen
Head; erst deren tatsächlich sauberes Ergebnis erlaubte die Unterintegration.
Die Dokumentation #172 wurde nach ihrem eigenen sauberen Abschluss zusammengeführt.

## Ergebnis des Softwareabgleichs

Die bereits geschlossenen Unteraufgaben #59/#60/#61/#62/#63/#65/#79/#156 und
die integrierte gemeinsame Abdeckung #169/#170 werden nicht erneut implementiert.
Bei gesetzter bestätigter Geometrie verwenden KI, Rückraum, Überweg und finaler
Haltpfad die gemeinsame Fusionssicht im Fahrzeugbezug. Panel-Sensoransicht und
Kartograf bleiben eigenständige Verbraucher und werden nicht still verschoben.

Die echte Restlücke zu #64 ist das vollständig fehlende Geometrieprofil: Auf der
Ausgangsbasis können gültige Fernscans trotz unbekannter Pose/Hülle weiter im
alten Sensorursprung freigeben. Zwei neue Regressionsfälle an beiden tatsächlichen
Verbrauchern schlagen dort in vier Kontrollen fehl (Produktdefault sowie zuvor
gesetzte, dann vollständig entfernte Geometrie).

Die Korrektur #176 sperrt diesen Fall im gemeinsamen Adapter. Ihre 22
Fusionsverbrauchertests prüfen auch partielle/falsche Geometrie, den tatsächlichen
Nullpublisher trotz Kamera-/KI-Freigabe und die drei #64-Gegenbeispiele für
Front/Seite/Heck bei 0/+90/-90/180 Grad an KI und finalem Haltpfad. Reine
Transformationsprüfungen erhalten Nullpose, `base_link` und radiale Abstände.
Positive Kontrollen verwenden ausdrücklich synthetische Pose/Hülle; keine
Gerätemaße stehen in den Produktdefaults. Qualitäts-, Pflichtkanal-, Headerzeit-,
Abdeckungs-, Richtungs- und Überwegprüfungen bleiben erhalten.

Der genehmigte Kompatibilitätsnachtrag übergibt auch dem Simulator ausdrücklich
seine bekannten synthetischen Sensorposen und seine Modellhülle einschließlich
Arm in Fahrstellung. Diese Daten kommen allein aus dem vorhandenen Modell und
werden nur beim ausdrücklichen Simulationsstart in Domain 77 ausgewählt.
Gerätewerte und Produktdefaults bleiben davon getrennt. Konfigurationstests,
Python-3.10- und Bash-Syntax sind bestanden; eine vollständige ROS-Simulation
wurde nicht ausgeführt.

## Verbleibende Geräte- und Informationsgrenzen

- #66: bestätigte horizontale Einzelmaße im privaten Prüfbestand sind keine
  vollständige xyz-/Orientierungs-/Unsicherheitsabnahme. Konfigurierte Winkel und
  `scan_einbau_quelle=gemessen` ersetzen keinen Messbeleg. Den tatsächlichen
  Sensorursprung, die äußerste Hülle und deren Bezug gezielt bestätigen.
- Kein gespeichertes Paar der 35 realen Scanpaare belegt freie Frontabdeckung.
  Ein äußerer Mindestreichweiten-/Blindbereich bleibt auch bei idealen Fernscans
  unbekannt; Nullwertursache und Hardwaredefekt sind damit nicht gleichgesetzt.
  Keine Hülle vergrößern und keine Schutzprüfung abschalten, um Fahrt zu erhalten.
- #67: installierten vollen SHA, Prozessneustart, effektive Konfiguration,
  Quellen/Frames und Zeitbezug vor der Prüfung tatsächlich erfassen. Je Fehlerfall
  Wunschvektor, endgültiges Kommando, realen Stillstand, Latenz/Restweg und
  Wiederanlauf getrennt messen. Ein Nullbefehl ist kein gemessener Halt.
- Vor bewegten Fällen müssen äußerer Prüfbereich, Beobachtung, STOPP,
  Reaktionsgrenzen und Isolation geklärt sein. Offene Voraussetzungen blockieren
  diese Fälle. RM02-Abnahmen werden nicht durch RM01-Ergebnisse abgeschlossen.

Die konkrete allgemeine [Matrix und Ergebnisvorlage](lidar-messung-und-ausfallpruefung.md)
trennt auch eine gemeinsame Messlücke von positiver komplementärer Abdeckung.
Die bestehende private Morgenanleitung wird zentral gepflegt; diese Datei ist
kein zweiter Installationsablauf. Für diese Lieferung gab es keinen Gerätezugriff,
kein Deployment und keinen Fahr-/Armversuch. #58/#64/#66/#67 bleiben offen.
