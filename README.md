# SmartCity 2026 – Autonomes Fahren

Software für den Yahboom ROSMASTER M3 Pro (Jetson Orin, Ubuntu 22.04, ROS 2 Humble) in der SmartCity der BBS Trier.
**Bisher nur auf RM02 programmiert und getestet.**

Der Roboter folgt der schwarzen Linie. Eine **KI** beachtet Ampeln, Stoppschilder, Zebrastreifen, Einbahnstraßen und Hindernisse und räumt Hindernisse mit dem Greifarm weg. Ein **Kartograf** baut bei jeder Fahrt eine 2D- und 3D-Karte. Bedient wird alles über das **Panel**.

📖 **Anleitungen, Fehlersuche und Glossar: [Wiki](https://github.com/BBS-GuT/smartcity-roboter/wiki)** · Zum Vortragen: [Projektüberblick](https://github.com/BBS-GuT/smartcity-roboter/wiki/Projektueberblick)

![Dashboard](docs/bilder/panel_dashboard.jpg)

## Schnellstart

```bash
cd ~
git clone https://github.com/BBS-GuT/smartcity-roboter.git
cd ~/smartcity-roboter
scripts/installieren.sh          # am Bildschirm des Roboters, nicht über SSH
```

Vor der ersten Fahrt die Einrichtungsschritte 1–5 der [Ersten Inbetriebnahme](https://github.com/BBS-GuT/smartcity-roboter/wiki/Erste-Inbetriebnahme) abschließen; für den dortigen Kalibrier-TEST gilt der eigene Vorabcheck. Vor jedem Fahrversuch den [vollständigen Check des Startprotokolls](https://github.com/BBS-GuT/smartcity-roboter/wiki/Startprotokoll#check-vor-einem-fahrversuch) abarbeiten: Vorbereitungen vor dem Einschalten beachten, dann im Dock **SmartCity Panel** öffnen und den Check vor **TEST** zur Fahrvorbereitung und bewusstem **START** abschließen. **STOPP** steht auf jeder Seite oben rechts. Not-Aus von außen: `scripts/stopp.sh`.

| Thema | Wiki-Seite |
|---|---|
| Installieren, Update, alten Klon umstellen | [Installation und Update](https://github.com/BBS-GuT/smartcity-roboter/wiki/Installation-und-Update) |
| Vor der ersten Fahrt einstellen (LiDAR, Arm, Kamera, Ampel) | [Erste Inbetriebnahme](https://github.com/BBS-GuT/smartcity-roboter/wiki/Erste-Inbetriebnahme) |
| Panel, Laptop-Zugriff, Logs | [Bedienung mit dem Panel](https://github.com/BBS-GuT/smartcity-roboter/wiki/Bedienung-mit-dem-Panel) |
| Simulation in einer VM | [Simulation in der VM](https://github.com/BBS-GuT/smartcity-roboter/wiki/Simulation-in-der-VM) |
| Etwas geht nicht | [Fehlersuche](https://github.com/BBS-GuT/smartcity-roboter/wiki/Fehlersuche), [Problemprotokoll](docs/problemprotokoll.md) |

## Was steckt wo?

| Ordner | Inhalt |
|---|---|
| `line_follower/` | Linienfolger (Draufsicht, Linien-Gedächtnis, Lenkung), Ampel- und Schilderkennung |
| `ki/`, `erkennung/` | KI-Zentrale, Entscheidungsregeln, Abläufe, YOLO |
| `kartograf/` | Karte 2D/3D, Messfahrt abspielen |
| `lib/` | gemeinsame Rechnungen ohne ROS (Karte, LiDAR, Tiefe, Arm, Greifen, Zustandsvertrag) |
| `panel/` | Bedienoberfläche (Webseite) |
| `sim/` | Simulation ohne Roboter |
| `scripts/` | Start- und Hilfsskripte (Panel, Simulation, Update, Not-Aus, Testrunner) |
| `config/` | Standardeinstellungen; eigene Werte in `config/lokal/` (nicht im Repository) |
| `schemas/` | JSON-Schema des Zustandsdatensatzes |
| `tests/` | Softwaretests ohne ROS und Roboter |
| `docs/` | Technik, Ziele und Teamregeln (siehe unten) |
| `wiki/` | Quelle des [Wikis](https://github.com/BBS-GuT/smartcity-roboter/wiki), wird nach jedem Merge auf `main` automatisch übertragen |

## Dokumentation im Repository

| Datei | Inhalt |
|---|---|
| [Zieldefinition](docs/zieldefinition-grundbetrieb.md) | verbindliches Ziel des Grundbetriebs (GB-01 … GB-18, Abnahmen A01 … A16) |
| [Schnittstelle Grundbetrieb](docs/schnittstellen-grundbetrieb.md) | gemeinsamer Zustandsdatensatz für Panel und MQTT (Entwurf) |
| [KI](docs/ki.md), [Linie](docs/linie.md), [Karte](docs/karte.md), [Greifarm](docs/greifarm.md) | wie die Programme arbeiten, alle Einstellungen |
| [Fahr-Gehirn](docs/fahrgehirn.md) | eigener Trainingsmodus: nur fahren, Kreuzungen nach Fahrplan, messen und Fahrparameter lernen |
| [CONTRIBUTING](CONTRIBUTING.md), [Aufträge](docs/auftraege/README.md), [Entwicklungsplan](docs/zusammenarbeit-und-entwicklung.md) | Mitarbeit, Dateizuständigkeiten, Arbeitspakete |
| [CI-Betrieb](docs/entwicklung/D1-ci-betrieb.md) | automatische Prüfungen und `main`-Schutz |
| [Geräte](docs/geraete/), [Infrastruktur](docs/infrastruktur/), [Abnahme](docs/abnahme/) | Inventar, Messpläne, Nachweise |
| [Prüfbericht 20.10.2026](docs/pruefung-grundbetrieb-2026-10-20.md), [Prüfnachweise](docs/pruefungen/) | Abgleich des Codes mit der Zieldefinition (historisch) |

## Testen ohne Roboter

```bash
python3 -m venv .venv && . .venv/bin/activate
python -m pip install -r requirements-test.txt
python scripts/pruefen.py --test-timeout test_karte.py=600   # alle Softwaretests
python3 tests/panel_demo.py                                    # Panel mit Beispieldaten, http://localhost:8099
scripts/simulation.sh pruefen                                  # komplette ROS-Simulation (Ubuntu 22.04 + ROS 2)
python3 sim/fahrgehirn_sim.py --runden 30                      # Fahr-Gehirn: viele Runden mit Kreuzungen (ohne ROS)
```

Die Softwaretests laufen bei jedem Pull Request automatisch (GitHub Actions). Grüne Tests sind **keine** Fahrfreigabe.

## Stand

**Offen (gehört laut Zieldefinition zum Grundbetrieb):**
- Kreuzungen und Abbiegen nach Stadtplan (K1–K8), Wegwahl
- gemeinsamer Motorfreigabeweg mit bleibender STOPP-Sperre
- gemeinsamer Zustand und MQTT für die Leitzentrale
- alle vier Roboter gleichzeitig: dafür braucht jeder eine eigene Domain-ID ([Roboter und Netz](https://github.com/BBS-GuT/smartcity-roboter/wiki/Roboter-und-Netz))

**Später:** Abblendlicht und Blinker (in Arbeit), RTW-Einsatz (Sonderrechte), Einsatzaufträge über MQTT.

**Bekannte Fehler / ungeprüft** (Details im [Problemprotokoll](docs/problemprotokoll.md)):
- **LiDAR-Einbau:** Die beiden LiDARs sitzen ca. 25 cm versetzt, Hinderniserkennung und Notbremse rechnen beide in der Robotermitte. Vermessung offen, **sicherheitsrelevant**.
- **Greifarm:** Am 20.10. auf RM02 erste Versuche, 2 Erfolge in 15. Greifkraft nur geschätzt, bis der Greifer im Panel eingemessen ist.
- **Kamerahöhe:** Laut Robotermodell ca. 31 cm in Fahrstellung, eingestellt sind 22 cm. Bitte nachmessen (betrifft Linie, Karte, Tiefe).
- **Rechenlast:** Hänger von 1–2 s (Linienfolger bis 500 % CPU). Gegenmaßnahme eingebaut, am Roboter noch nicht bestätigt.
- **Linienfolger:** Pendeln bei höherem Tempo ist in der Simulation behoben, am Roboter ungeprüft.
- Die Objekterkennung ist teilweise fehlerhaft, Ampeln werden noch nicht sauber erkannt.

Die Karte passt seit 20.10. auf RM02 (Haupt-LiDAR `/scan1`). Alles Neue ist zuerst in der Simulation getestet. Gerätetests auf RM02 laufen.
