# LiDAR: Softwarestand und ausstehende Nachweise am 22.10.2026

Bezug: [#58](https://github.com/BBS-GuT/smartcity-roboter/issues/58) mit allen
Unteraufgaben. Diese Statuslieferung integriert keine ungeprüfte Schutzsoftware
und behauptet keine Gerätefreigabe. Geprüfte Ausgangsbasis ist main
`dc6acc25e490edc301a6464af8fe19e17339aa42` mit integriertem
[PR #170](https://github.com/BBS-GuT/smartcity-roboter/pull/170).

## Vorbereitete Unterlieferungen

| Lieferung | Exakter Kandidat | Prüfung / Integrationsgrenze |
|---|---|---|
| [#172: Mess- und Ausfallmatrix](https://github.com/BBS-GuT/smartcity-roboter/pull/172) | `a3c81259d69990183ca4eb20f6d9eae9774b243f` | Linux-CI 43/43; [nativer Review](https://github.com/BBS-GuT/smartcity-roboter/pull/172#issuecomment-6349216160) beim Statusabgleich noch laufend. Noch nicht integriert. |
| [#176: fehlende Geometrie sperren](https://github.com/BBS-GuT/smartcity-roboter/pull/176) | `b5a608e019ddbab57ad3a5f716876056ae0524db` | Lokaler Windows-Gesamtlauf 42/43, ausschließlich bekannter Prozessnamenfall in `test_systemlast.py`; alle betroffenen Prüfungen bestanden. [Linux-CI](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39839393132) separat am Head prüfen. [Nativer Review abgebrochen wegen Nutzungslimit](https://github.com/BBS-GuT/smartcity-roboter/pull/176#issuecomment-6349330384), daher noch nicht integrierbar. |

Die Unter-PRs zielen auf `fix/gb-58-lidar`. Erst nach den geforderten tatsächlichen
Prüfergebnissen integrieren; für den abschließenden Haupt-PR zählen erneut dessen
eigener Head, aktuelle main-Basis, CI, nativer Review und angerechnete Fremdfreigabe.
Ein grüner Testlauf ersetzt keinen dieser Nachweise. Kein Reviewersatz durch den
implementierenden Chat und keine Umgehung der Schutzregeln.

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

Kandidat #176 sperrt diesen Fall im gemeinsamen Adapter. Seine 22
Fusionsverbrauchertests prüfen auch partielle/falsche Geometrie, den tatsächlichen
Nullpublisher trotz Kamera-/KI-Freigabe und die drei #64-Gegenbeispiele für
Front/Seite/Heck bei 0/+90/-90/180 Grad an KI und finalem Haltpfad. Reine
Transformationsprüfungen erhalten Nullpose, `base_link` und radiale Abstände.
Positive Kontrollen verwenden ausdrücklich synthetische Pose/Hülle; keine
Gerätemaße stehen in den Produktdefaults. Qualitäts-, Pflichtkanal-, Headerzeit-,
Abdeckungs-, Richtungs- und Überwegprüfungen bleiben erhalten.

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

Die konkrete allgemeine Matrix und Ergebnisvorlage stehen in Unter-PR #172.
Die bestehende private Morgenanleitung wird zentral gepflegt; diese Datei ist
kein zweiter Installationsablauf. Für diese Lieferung gab es keinen Gerätezugriff,
kein Deployment und keinen Fahr-/Armversuch. #58/#64/#66/#67 bleiben offen.
