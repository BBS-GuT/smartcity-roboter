# A1 Sensorfreigabe

Auftrag / verantwortlicher Mensch: A1, GitHub #12; Koordination Carsten Haas.
Status: zur Prüfung (Draft-PR).
Basiscommit: `b9f64424d92f64ed4f391a96b6c6718caae43bcd`.
Branch: `fix/gb-a1-sensorfreigabe`.
Liefercommit und PR: siehe PR-Kopf und Übergabe im Entwicklungs-Chat.
Auftragsdokumente: `origin/codex/grundbetrieb`, zuletzt `0db42c2`; A1 und gemeinsame Regeln gegenüber `eb563d8` unverändert.

## Änderung und Anforderungsbezug

- GB-12/13, A11: Ungültige Aufnahmezeit (fehlend, unbrauchbar, Null, Zukunft oder mindestens fünf Sekunden alt) erhält keine Ersatzzeit. Sie sperrt die Entscheidung; ungültige Punkte gelangen nicht ins Liniengedächtnis. Der bestehende Status enthält weiterhin `zeitstempel_ok` und einen lesbaren Haltgrund.
- GB-13, A11: Gültige Aufnahmezeiten bleiben erhalten. Das Aufnahmealter wächst bis zur Entscheidung weiter; die bestehenden Grenzen 0,25/0,6 Sekunden bleiben unverändert. 0,7 und sechs Sekunden alte Bilder erlauben keine Bewegung.
- GB-13/14, A11/A12-Teilumfang: Keine Manöverrückgabe vor den Pflichtprüfungen. Fehlender/veralteter LiDAR und kritischer Abstand sperren auch Drehen und Rückwärtsfahrt. Kamera und KI werden vor erlaubten Manövern geprüft.
- Die frühere Testerwartung „Notbremse erlaubt Drehen“ widerspricht GB-14 und wurde in eine Prüfung vollständiger Nullbewegung geändert. Die Prüfung wurde erhalten und verschärft.
- Aufnahmezeit im Gedächtnis, gültige normale Fahrt, Langsamfahrt, Manöverbegrenzung, Suchrotation bei gültiger Wahrnehmung und Bewegungsrückmeldung bleiben erhalten.

Geänderte und reservierte Dateien: `line_follower/line_follower.py`, `tests/test_line_follower.py`, `tests/test_sicherheitsfreigabe.py`, dieses Dokument. Öffentliche Nachrichtenformate verändert: nein. Keine neuen Parameter, keine abgeschalteten Prüfungen.

## Prüfungen

Reine Softwaretests mit vorhandenen ROS-Attrappen; Python 3.12.14 aus dem gebündelten Runtime, zusätzliche Pakete aus `C:\SmartCity\research\review-deps-20261002`.

- `tests/test_sicherheitsfreigabe.py`: sieben Testmethoden einschließlich parametrisierter Zeit-/Manöverfälle bestanden. Echte `on_image`, `entscheide` und `steuern` ausgeführt; nur Bildsuche und Uhr deterministisch ersetzt. Nullbefehl und lesbarer Status am Publisher geprüft.
- `tests/test_line_follower.py`: 21 vorhandene Einzelprüfungen bestanden.
- `tests/test_ampel.py`: 17 Einzelprüfungen bestanden.
- `tests/test_entscheider.py`: 82 Einzelprüfungen bestanden.
- `tests/test_greifen.py`: 20 Einzelprüfungen bestanden. Erster Lauf durch gesperrtes Sandbox-Temp-Verzeichnis abgebrochen; Wiederholung mit TEMP/TMP unter `C:\SmartCity\entwicklung\a1-testtmp` bestanden.
- `tests/test_schilder.py`: fünf Einzelprüfungen bestanden.
- `git diff --check`: bestanden.

Aufruf: Python aus dem Runtime mit `PYTHONPATH=C:\SmartCity\research\review-deps-20261002`, jeweils `python tests/<skript>.py`; für temporäre Dateien obiges TEMP/TMP verwenden.

## Offene Grenzen und Übergaben

Keine ROS-Gesamtsimulation oder Gerätefahrt ausgeführt; kein Nachweis gemessenen Motorstillstands. A12 ist nur bezüglich Vorrang der lokalen Sperrgründe bearbeitet, nicht vollständig abgenommen.

Globale verriegelte STOPP-Sperre, alleiniger Motorpublisher, Scanqualität (einschließlich NaN/Inf und fehlender einzelner konfigurierter Quellen), Sensorpflichtmatrix, monotone Zeitbasis, Fahrzeughülle, Rückwärtsabdeckung, Bremsgrenzen und Watchdogmessung bleiben offen. Ein beliebiger frischer Scan genügt weiterhin der bisherigen LiDAR-Prüfung; A1 behauptet keine vollständige Sensorvalidierung.

Benötigte Übergabe: Orchestrator prüft und integriert A1. C liefert den einzigen akzeptierten C1-Vertrag, E gemessene Geometrie-/Latenz-/Bremswerte; D übernimmt gemeinsamen Runner und spätere Simulationsisolation. A2 erst nach eigener Zuteilung und akzeptiertem C1. Kein Folgeauftrag gestartet.
