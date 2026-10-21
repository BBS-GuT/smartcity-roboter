# Testen ohne Roboter

Es gibt drei Stufen. Jede ersetzt **nicht** die nächste:

1. **Softwaretests** mit künstlichen Daten (ohne ROS): schnell, laufen auch auf GitHub bei jedem Pull Request.
2. **ROS-Simulation**: alle Programme laufen wie auf dem Roboter, der Simulator ersetzt die Hardware. Siehe [Simulation in der VM](Simulation-in-der-VM).
3. **Echter Roboter**: nur das zählt für eine Abnahme.

## Softwaretests

**Kurz erklärt:** Eine virtuelle Umgebung (`venv`) ist ein eigener Python-Ordner nur für dieses Projekt. So bekommen die Tests genau die getesteten Paketversionen, ohne das System-Python zu verändern.

Aus der Projektwurzel (Linux, Python 3.10 wie auf dem Jetson):

```bash
python3 -m venv .venv
. .venv/bin/activate                   # Windows/PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-test.txt
python -m pip check
python scripts/pruefen.py --test-timeout test_karte.py=600
```

`scripts/pruefen.py` findet alle `tests/test_*.py` und führt jedes in einem eigenen Prozess aus. Grün ist es nur, wenn **alle** bestehen: Fehler, Timeout oder übersprungene Tests (Skip) gelten als nicht bestanden. Der Kartentest dauert deutlich länger als die anderen.

Einzelne Tests direkt:

```bash
python3 tests/test_entscheider.py      # Regeln der KI
python3 tests/test_karte.py            # Karte
python3 tests/test_line_follower.py    # Linienfolger
```

Viele Tests nutzen nachgebaute ROS-Module aus `tests/attrappen/`. Sie werden nur in Tests benutzt, nie auf dem Roboter.

## Panel ohne Roboter ansehen

```bash
python3 tests/panel_demo.py            # Panel mit Beispieldaten, http://localhost:8099
```

## Automatische Prüfung auf GitHub (CI)

**Kurz erklärt:** CI (Continuous Integration) heißt, dass GitHub bei jedem Pull Request die Tests automatisch auf einem frischen Ubuntu-Rechner laufen lässt. Ein PR kann erst nach `main`, wenn die drei Checks grün sind:

- `D1 / Python-Syntax (3.10)`
- `D1 / Shell-Syntax (bash)`
- `D1 / Softwaretests (Ubuntu 22.04, Python 3.10)`

Was bei einem roten Lauf zu tun ist: [`docs/entwicklung/D1-ci-betrieb.md`](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/entwicklung/D1-ci-betrieb.md). **Grüne Checks sind keine Fahrfreigabe.**
