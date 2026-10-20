# D1: Umgebung der reinen Softwaretests

Die Testpakete in [requirements-test.txt](../../requirements-test.txt) gehören in eine eigene virtuelle Umgebung. Sie ersetzen keine ROS-Installation auf Geräten. Zielplattform der CI ist Ubuntu 22.04 mit CPython 3.10; die genaue Patchversion wird im Lauf protokolliert.

## Installation und Aufruf

Aus der Projektwurzel unter Ubuntu 22.04:

```bash
python3.10 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-test.txt
python -m pip check
python scripts/pruefen.py --test-timeout test_karte.py=600
```

Unter Windows eine eigene Umgebung mit `python -m venv .venv` anlegen und `.venv\Scripts\python.exe` statt `python` verwenden. Falls das Systemtempverzeichnis gesperrt ist, `TEMP` und `TMP` vor dem Test auf ein eigenes beschreibbares Verzeichnis setzen. Nicht den Runner oder Fachtests für eine Sandbox umdeuten.

Der gemeinsame Runner kommt aus [#35](https://github.com/davidheinrich73/smartcity-roboter/issues/35) / [PR #41](https://github.com/davidheinrich73/smartcity-roboter/pull/41). Solange er nicht integriert ist, diesen Abhängigkeitsstand ausdrücklich nennen. Einzelprüfung des Vertrags: `python tests/test_zustandsvertrag.py -v`. Die portable Windows-Logprüfung benötigt [PR #40](https://github.com/davidheinrich73/smartcity-roboter/pull/40).

## Versionen und Prüfgrenzen

| Paket | Festgelegte Version | Zweck |
|---|---|---|
| NumPy | 1.26.4 | Gemeinsame numerische Basis mit OpenCV 4.10 |
| opencv-python-headless | 4.10.0.84 | Bildverarbeitung ohne GUI-Abhängigkeit |
| PyYAML | 6.0.2 | Konfigurationsdateien |
| jsonschema | 4.23.0 | Tatsächliche Prüfung des Vertrags gegen JSON Schema |
| attrs | 24.2.0 | jsonschema-Abhängigkeit |
| jsonschema-specifications | 2023.12.1 | jsonschema-Abhängigkeit |
| referencing | 0.35.1 | jsonschema-Abhängigkeit |
| rpds-py | 0.20.0 | jsonschema-Abhängigkeit |

NumPy bleibt bewusst in der mit OpenCV gemeinsam geprüften 1.x-Reihe. Bei Paketänderungen Installation, `pip check`, Vertragsprüfung und Gesamtlauf wiederholen. Keine produktiven Grenzwerte für Paketkompatibilität verändern.

Fehlendes `jsonschema` darf keinen grünen D1-Lauf ergeben: Der Runner meldet von unittest ausgewiesene Skips als unvollständig; CI importiert alle vier direkten Pakete vor dem Testlauf und protokolliert `pip freeze`. In der Vertragsprüfung müssen `test_schema_selbst_gueltig` und die Schema-Prüfungen der Fixtures tatsächlich laufen.

Tests benutzen teilweise [ROS-Attrappen](../../tests/attrappen/LIESMICH.txt) und künstliche Sensordaten. Auch `test_karte.py` ist ein reiner Softwaretest der Karten-/Weltberechnung. Die vollständige ROS-Simulation, Brokerempfang, Motorbewegung und Geräteabnahme sind separate Prüfungen. Ein grüner Lauf bestätigt keine vollständige fachliche Sicherheitsabnahme; C1-Vertragsreview und offene Fachissues bleiben unabhängig.

## Tatsächlich geprüft am 20.10.2026

- Basis `5309b20854e81a217996da8ebb903feebaa7f8eb`, eigener D1-Checkout.
- Windows / CPython 3.12.14, isolierte venv, pip 25.0.1: alle acht obigen Pakete installiert; `pip check` ohne Konflikt. Keine globale Installation.
- `python tests/test_zustandsvertrag.py -v`: 20 Methoden bestanden, 0 Fehler, 0 Skips; `test_schema_selbst_gueltig` ausdrücklich ausgeführt.
- Kombinierter Windowslauf auf `df3d5d6` mit den D1a/b/c-Lieferungen: 11/11 Skripte bestanden; 176 ausgegebene Einzelprüfungen plus 48 unittest-Methoden, 0 Fehler/Timeouts/Skips. Kartentest: 87,44 s. Diese Zähler beschreiben den geprüften Stand und sind keine feste Sollanzahl.
- Keine ROS-Gesamtsimulation und keine reale Geräte-/Brokerprüfung ausgeführt.

## Tatsächlicher Linux-/CI-Nachweis

Ubuntu 22.04 steht lokal nicht zur Verfügung (kein WSL). Stattdessen wurde die Zielumgebung tatsächlich in [PR #43](https://github.com/davidheinrich73/smartcity-roboter/pull/43) ausgeführt: Ubuntu 22.04.5 LTS, CPython **3.10.22**, isolierte venv, genau die acht oben festgelegten Paketversionen. `pip check` und der Pflichtimport von NumPy, OpenCV, PyYAML und jsonschema waren erfolgreich.

Der [erfolgreiche Push-Lauf auf `6aff086`](https://github.com/davidheinrich73/smartcity-roboter/actions/runs/39399805111) prüft die Basis `df3d5d6cbd79b98829a69efd79086c70ae441235` samt D1a/b/c und Workflow. Ergebnis: 11/11 Skripte bestanden, 0 Fehler/Timeouts/Skips; Vertragsprüfung 20/20 Methoden mit installiertem jsonschema. Kartentest: 36,64 s. Der Runner prüft sich mit temporären künstlichen Skripten einschließlich Fehler, fehlendem Paket, Skip und Timeout; er startet keine ROS-Simulation.

Nachgewiesene erfolgreiche Checknamen:

- [D1 / Python-Syntax (3.10)](https://github.com/davidheinrich73/smartcity-roboter/actions/runs/39399805111/job/118551404292): 65 versionierte Pythondateien ohne ROS-Import kompiliert.
- [D1 / Shell-Syntax (bash)](https://github.com/davidheinrich73/smartcity-roboter/actions/runs/39399805111/job/118551404903): 13 versionierte Shellskripte mit `bash -n` geprüft.
- [D1 / Softwaretests (Ubuntu 22.04, Python 3.10)](https://github.com/davidheinrich73/smartcity-roboter/actions/runs/39399805111/job/118551404840): vollständiger Softwarelauf; Einzellogs und `pip freeze` als Actions-Artefakt, Aufbewahrung 14 Tage.

Der erste Workflowversuch auf `dbde502` wurde vor Jobstart wegen eines unzulässigen Ausdruckskontexts abgewiesen. Auf `6aff086` ist dies korrigiert und mit actionlint 1.7.12 sowie dem obigen echten Lauf geprüft. Historische Fehlerprobes sind nicht als Regression ausgeführt worden. Offene Fachissues und C1-Vertragsreview bleiben von den grünen Infrastrukturchecks unberührt.

Repositoryeigentümer müssen die gewünschten `main`-Regeln separat einrichten und bestätigen: PR-Review durch mindestens eine andere fachkundige Person, erledigte Gespräche, diese tatsächlich erfolgreichen Checks sowie gesperrte Force-Pushes/Löschungen. Diese Lieferung behauptet keine eingerichteten Regeln oder CODEOWNERS.
