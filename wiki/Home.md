# SmartCity-Roboter Wiki

Anleitungen und Wissenssammlung für die Software der SmartCity-Roboter RM01–RM04 (Yahboom ROSMASTER M3 Pro, Jetson Orin, Ubuntu 22.04, ROS 2 Humble) der BBS Trier.

> **Wie dieses Wiki gepflegt wird:** Die Seiten liegen im Repository im Ordner [`wiki/`](https://github.com/BBS-GuT/smartcity-roboter/tree/main/wiki). Nach jedem Merge auf `main` kopiert ein GitHub-Workflow sie automatisch hierher. **Änderungen bitte per Pull Request in `wiki/` machen**, nicht im Browser: Direkte Änderungen im Wiki werden beim nächsten Abgleich überschrieben. Ausnahme: Das [Problemprotokoll](Problemprotokoll) kommt aus `docs/problemprotokoll.md`.

## Erste Schritte

| Ich will … | Seite |
|---|---|
| verstehen, worum es im Projekt geht (zum Vortragen) | [Projektüberblick](Projektueberblick) |
| die Software auf einen Roboter bringen | [Installation und Update](Installation-und-Update) |
| den Roboter fahren lassen | [Bedienung mit dem Panel](Bedienung-mit-dem-Panel) |
| einen Roboter vor der ersten Fahrt einstellen | [Erste Inbetriebnahme](Erste-Inbetriebnahme) |
| ohne Roboter arbeiten | [Simulation in der VM](Simulation-in-der-VM), [Testen ohne Roboter](Testen-ohne-Roboter) |
| am Code mitarbeiten | [Mitarbeiten mit Git](Mitarbeiten-mit-Git) |

## Wenn etwas nicht geht

- [Fehlersuche](Fehlersuche): Logs, typische Meldungen, erste Schritte
- [Problemprotokoll](Problemprotokoll): was am Roboter schon schiefging, Ursache und Lösung
- [Messfahrt aufzeichnen](Messfahrt-aufzeichnen): wenn die Karte nicht passt
- [Panel-Browser auf dem Jetson](Panel-Browser-auf-dem-Jetson): Chromium startet nicht

## Wissen

- [Roboter und Netz](Roboter-und-Netz): IP-Adressen, Domain-ID, mehrere Roboter
- [Eigenes Erkennungsmodell](Eigenes-Erkennungsmodell): YOLO neu exportieren oder selbst trainieren
- [Glossar](Glossar): Fachbegriffe kurz erklärt

## Was steht im Repository statt im Wiki?

Alles, was sich zusammen mit dem Code ändert oder verbindlich ist, bleibt versioniert im Repository:

| Datei | Inhalt |
|---|---|
| [`docs/zieldefinition-grundbetrieb.md`](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/zieldefinition-grundbetrieb.md) | verbindliches Ziel (GB-01 … GB-18, Abnahmen A01 … A16) |
| [`docs/schnittstellen-grundbetrieb.md`](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/schnittstellen-grundbetrieb.md) | Zustandsdatensatz für Panel und MQTT |
| [`docs/ki.md`](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/ki.md), [`docs/linie.md`](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/linie.md), [`docs/karte.md`](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/karte.md), [`docs/greifarm.md`](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/greifarm.md) | Technik und alle Einstellungen der Programme |
| [`CONTRIBUTING.md`](https://github.com/BBS-GuT/smartcity-roboter/blob/main/CONTRIBUTING.md), [`docs/auftraege/`](https://github.com/BBS-GuT/smartcity-roboter/tree/main/docs/auftraege), [`docs/entwicklung/`](https://github.com/BBS-GuT/smartcity-roboter/tree/main/docs/entwicklung) | Teamregeln, Aufträge, Dateizuständigkeiten, CI |
| [`docs/geraete/`](https://github.com/BBS-GuT/smartcity-roboter/tree/main/docs/geraete), [`docs/infrastruktur/`](https://github.com/BBS-GuT/smartcity-roboter/tree/main/docs/infrastruktur), [`docs/abnahme/`](https://github.com/BBS-GuT/smartcity-roboter/tree/main/docs/abnahme) | Geräteinventar, Messpläne, Abnahmen |
