# E1 – Geometrie und Messplan

Stand 20.10.2026 · Entwurf v0.1 · Status **offen**, sofern nicht ausdrücklich anders bezeichnet. Keine Geräte- oder Bewegungsfreigabe.

Bezug: [Zieldefinition](../zieldefinition-grundbetrieb.md), GB-02/03/05/09, A02/A04/A08. Es liegen keine freigegebenen E1-Maße vor. Die geschätzte Kamerahöhe 22 cm aus Software ist kein Messwert.

## Messregister

Je konkreter Stelle und RM01–RM04 eine eigene Zeile anlegen; Wiederholungen und Extremwerte erhalten. Alle Felder sind erforderlich, auch bei einem offenen Ergebnis.

| Mess-ID / Ort | Größe / Wert / Einheit | Verfahren / Messmittel | Datum / Person | Gerät / Aufbauversion | Unsicherheit | Quelle / Status |
|---|---|---|---|---|---|---|
| GEO-01 / je Straßenabschnitt | nutzbare Breite; offen (mm) | quer zur Leitlinie, engste Stelle und beide Ränder | offen | Spielfeld offen | offen (mm) | offen |
| GEO-02 / jede Kurve | innerer/äußerer Rand, Linienradius; offen (mm) | Rasteraufnahme + Maßband, engste Kurven separat | offen | Spielfeld offen | offen (mm) | offen |
| GEO-03 / Linie und Plattenfuge | Linienbreite, Lücke, Versatz, Höhenstufe; offen (mm) | Lineal/Lehre und Detailfoto | offen | Spielfeld offen | offen (mm) | offen |
| GEO-04 / Überweg Z1 und Z2 | Grenzen, Balken, Querungsfläche; offen (mm) | Eckpunkte im Feldbezug messen | offen | Spielfeld offen | offen (mm) | offen |
| GEO-05 / jede Zufahrt | Haltelinie/Haltepunkt und Konfliktgrenze; offen (mm) | Abstand zur definierten Fahrzeugfront | offen | Spielfeld offen | offen (mm) | offen |
| GEO-06 / jedes Signal/Schild | Standort, Höhe, Orientierung; offen (mm/°) | Position und Blickrichtung mit Foto | offen | Spielfeld offen | offen (mm/°) | offen |
| GEO-07 / alle Engstellen | lichte Abstände und Höhe zu Aufbauten; offen (mm) | engsten Querschnitt vermessen | offen | Spielfeld offen | offen (mm) | offen |
| GEO-08 / je RM01–RM04 | Länge/Breite/Höhe, Armfahrstellung, Kamera und alle Überstände; offen (mm) | gesamte Hülle statisch aufnehmen, Armstellung dokumentieren | offen | Gerät/Aufbau offen | offen (mm) | offen |
| GEO-09 / je Sensor und Gerät | x/y/z, Roll/Nick/Gier, Sicht-/Scanebene; offen (mm/°) | definierte Referenzpunkte und Winkelmessung | offen | Kamera, Tiefe, beide LiDAR offen | offen (mm/°) | offen |
| GEO-10 / jede erlaubte Kurve | Hüllkurve und geometrische Reserve; offen (mm) | zunächst statische Schablone aus GEO-08, Fahrnachweis erst E2 | offen | Gerät + Feldversion offen | offen (mm) | offen |

## Durchführung ohne Fahrversuch

1. Spielfeldteam bestätigt Aufbauversion, feste Referenzecke, Achsen und Höhenebene. Vorschlag: Feld x/y auf der Matte und z nach oben; erst nach Bestätigung verbindlich. Übersichtsbild mit Maßstab und Knotenkennung erstellen.
2. Je Abschnitt und Zufahrt Messpunkte markieren, Nullpunkt/Verfahren dokumentieren. Messmittelauflösung, Anlegefehler und Wiederholstreuung erfassen; Unsicherheit nicht pauschal erfinden.
3. Gerätehülle im gesicherten Stillstand erfassen. Armfahrstellung physisch dokumentieren; keine Armbewegung beauftragt. Fahrzeugbezug samt Ursprung/Achsrichtungen erst bestätigen, dann Sensortransformationen zu diesem Bezug protokollieren.
4. Feld- und Fahrzeugmessung anhand derselben Aufbauversion geometrisch vergleichen. Reserven und Engstellen an A/B geben; keine Geschwindigkeits- oder Abstandsschwelle aus ungeprüfter Geometrie einsetzen.
5. Spielfeld-/Geräteteam zeichnet Messblatt und Fotos gegen; Status bleibt offen bis zum prüfbaren Nachweis. Änderungen an Arm, Kamera oder Feld erzeugen eine neue Version.

## Späterer E2-Auftrag – nicht ausgeführt

Bremsweg, STOPP-/Sensor-/Befehlslatenz und Board-Watchdog getrennt prüfen: Gerät/Commit/Karte/Konfiguration, Beobachter, wirksamer Stillsetzweg, Messmittel, Last/Akku, Ausgangsgeschwindigkeit, Wiederholungen, Unsicherheit und vorher vereinbarte Abbruch-/Bestehensgrenzen protokollieren. Sender-, Prozess- und Sensorfehler sowie tatsächlichen Stillstand nachweisen. Keine Zahlen oder Testfenster festgelegt; Zuteilung durch Orchestrator und A nötig.
