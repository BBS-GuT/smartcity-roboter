# Entwicklungsauftrag B Fahrentscheidungen und Navigation

**Empfänger:** Weiterer Entwickler / eigener Entwicklungs-Chat. **Jetzt umzusetzen:** B1. **Branch:** `fix/gb-b1-verkehrshalt`. **Zielbezug:** GB-04, GB-08, GB-09, GB-13, GB-14; A03/A07/A08/A11/A12.

Du entwickelst am Team-Repository `https://github.com/BKoewenig/smartcity-roboter`. Lies die [gemeinsamen Regeln](00-gemeinsame-regeln.md), das [Register](README.md), Zieldefinition und aktuellen Prüfbericht. Der Orchestrator-Chat koordiniert Dateigrenzen und Übergaben. Die Aufträge liegen zunächst auf `codex/grundbetrieb` in PR #11. Starte einen eigenen Branch von aktuellem `origin/main`; dokumentiere den Basiscommit.

## Auftrag B1

1. **Rot-Halt bleibt ohne gültige Freigabe wirksam.** Entferne das Freigeben allein durch vier Sekunden Unsichtbarkeit. Bei Signalverlust oder unbekanntem Signal bleibt die bestehende Einfahrtsperre bestehen. Fremdes Grün darf später nicht die eigene Ampel ersetzen: Die vollständige Signal-/Zufahrtszuordnung ist ein Folgepaket, kein durch den Timeout-Fix bereits gelöstes Thema.
2. **Wende-Fehlerübergang hält sofort.** Der Aufruf, in dem das Wendemanöver fehlschlägt, darf nicht noch `fahren / Weg frei` zurückgeben. Die Fehlersperre wirkt im selben Zyklus und bleibt bestehen. Sensorwiederkehr oder neuer Verkehrszustand heben sie nicht auf. Die bewusste Wiederfreigabe wird anschließend mit dem Betriebsweg aus A2 abgestimmt.
3. **Hindernisprüfung bleibt im Grundbetrieb stehen.** Auch bei `ausweichen=false` und ausgeschaltetem Arm darf ein zu nahes, visuell nicht bestätigtes Hindernis keine selbstständige Rückwärts-Wahrnehmungsfahrt auslösen. Greifen, seitliches Ausrichten, automatische Annäherung und Kameraschwenken gehören nicht in den Grundbetriebsablauf. Begrenze diese Aktionen in der Entscheidungslogik und erhalte getrennte spätere Szenarien nachvollziehbar, ohne sie im Grundbetrieb freizugeben.

Der aktuelle Standard `ki_darf_arm_bewegen=true` ist mit den Grundbetriebsgrenzen abzugleichen. Der Softwareauftrag bestätigt keine reale Arm-Fahrstellung. Manuelle Diagnosefunktionen des Panels nicht ungeprüft löschen; benötigte Änderungen an der Bedienung als Übergabe an C melden. A bleibt für die abschließende Motorprüfung verantwortlich.

## Dateien und Grenzen

Für B1: `ki/entscheider.py`, `ki/ablaeufe.py`, zugehörige `tests/test_entscheider.py` und bei Bedarf eine neue eigene Testdatei. `config/arm.yaml` darf für eine begründete sichere Grundbetriebsvoreinstellung angepasst werden. Optional `docs/entwicklung/B1-verkehrshalt.md`.

Kein Umbau von `line_follower/line_follower.py`, `lib/lidar.py`, `panel/*`, gemeinsamen Vertragsdateien oder CI. Öffentliche ROS-/JSON-Formate in B1 bewahren. Benötigte gemeinsame Parameter über A integrieren; `config/roboter.yaml` nicht parallel ändern. Änderungen am reinen Linienfinder und neue Navigationsmodule erst in B2 getrennt behandeln.

## Konkrete Bestehenskriterien

- Bestätigtes Rot, danach für mehr als vier Sekunden unsichtbar: weiterhin Halt. Wiederholte neue Bilder ohne Signal erzeugen keine Freigabe.
- Ein Signalwechsel mit gleichzeitigem Hindernis löscht den Hindernishalt nicht. Mehrere Haltegründe bleiben getrennt wirksam.
- Wenden ohne gemessenen Fortschritt: bereits der Fehlerübergang liefert Halt, nicht erst der spätere Endzustand. Danach bleibt der Fehlerhalt bestehen.
- Blockiertes Fahrzeug mit `ausweichen=false`: kein Rückwärts-/Seiten-/Wendebefehl aus einer Wahrnehmungs- oder Greifheuristik, auch bei naher LiDAR-Meldung und fehlender visueller Bestätigung.
- Grundbetriebsentscheidungen erzeugen keine automatischen Greif-/Kameraschwenkaktionen. Getrennte Szenariotests dürfen eine unzulässige Grundbetriebsaktion nicht als Erfolg zählen.
- Passe bestehende gegenteilige Testannahmen mit GB-Begründung an; ergänze Tests für Übergänge und gleichzeitig bestehende Haltegründe. Bestehende zulässige Fahrt behält eine positive Kontrolle.

Lieferung: kleiner Draft-PR, zugeordnete Anforderungen, tatsächliche Softwaretests, verbleibende Einschränkungen und Übergabebericht. Keine Hardwarefahrt und kein eigenständiger Merge nach `main`.

## Folgeauftrag B2 erst nach Zuteilung

Entwickle anschließend die gerichtete Straßenkarte und reine Navigationslogik: Knoten/Zufahrt, erlaubte Ausfahrten, eigene Auswahlhistorie/Zufallszustand, festgehaltene Ausfahrt sowie Annäherung/Manöver/Ausfahrtbestätigung. Die Regelkarte ist eine eigene versionierte fachliche Karte und nicht einfach der bestehende Kartograf.

Alle in der Zieldefinition erlaubten Zufahrten/Ausgänge werden gezielt geprüft. Signalzuordnung und Haltelinien, Stoppschildstillstand, beide Überwege und Gegenverkehr brauchen Partnerdaten aus E. Keine Kennungen oder Infrastrukturfreigaben als reale Beobachtung erfinden. Reine Modelltests können vor ROS-Anbindung entstehen; öffentliche Adapter verwenden erst den akzeptierten C1-Vertragscommit und den Motorweg aus A.
