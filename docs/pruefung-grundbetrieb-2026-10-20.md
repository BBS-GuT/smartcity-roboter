# Repositoryabgleich zum Grundbetrieb am 20 Oktober 2026

**Ergebnis:** Die Anwendung wurde seit dem 2. Oktober deutlich verbessert. Der vollständige Grundbetrieb ist weiterhin nicht erreicht. Größere, gezielte Arbeiten bleiben beim gemeinsamen Motorfreigabeweg, bei Sensorqualität und Fahrzeughülle, Kreuzungsnavigation, gemeinsamer Zustandsquelle, MQTT und Viergeräteintegration erforderlich. Die vorhandene Spurführung, Wahrnehmung, Kartierung, Diagnose und Bedienung bilden dafür eine nutzbare Basis.

Geprüft ist `main` auf **`b9f64424d92f64ed4f391a96b6c6718caae43bcd`**, letzter Commit vom 19.10.2026. Maßstab ist die [Zieldefinition Version 1.0](zieldefinition-grundbetrieb.md). Sie liegt inzwischen im Repository und stimmt inhaltlich mit der am 2. Oktober verwendeten Vorlage überein. Ihre technischen Vorschläge wurden als Vorschläge behandelt; verbindlich sind die fachlichen Anforderungen.

Der [Vorschlag für Zusammenarbeit und Weiterentwicklung](zusammenarbeit-und-entwicklung.md) ordnet die folgenden Lücken konkreten Arbeitspaketen und drei parallelen Entwicklungsbereichen zu.

## Fortschritte seit der letzten Prüfung

- Die Spurführung nutzt jetzt Odometrie und IMU, historische Aufnahmeposen, Kurvenvorausschau und ein verbessertes simuliertes Antriebsmodell. Die Suche bei Linienverlust wurde von drei auf 0,8 Sekunden verkürzt.
- Automatisches Blockade-Ausweichen ist standardmäßig abgeschaltet. Ein neuer Test prüft längeres Warten. Das schließt noch nicht alle autonomen Rückwärtsbewegungen aus.
- Einsatz-Sonderrechte sind aus der aktuellen Entscheidungslogik entfernt.
- Fehlgeschlagenes Wenden setzt inzwischen eine Fehlersperre. Im Übergang zum Fehler besteht noch ein einzelner falscher Freigabezyklus.
- Zebrastreifen- und Hindernisauswertung wurden verbessert; der Fahrweg der Querungsprüfung wird laufend erneuert.
- Messfahrtaufzeichnung, Wiederabspielen, Kalibrierdiagnose, Board-/Domainprüfung und Panelhinweise erleichtern die Fehlersuche.
- Das autonome Greifen wurde erweitert und ist jetzt standardmäßig freigegeben. Diese Entwicklung gehört laut Zieldefinition in einen getrennt freizugebenden Funktionsumfang.

Die vorhandenen Entwicklungsbranches enthalten keine zusätzlich einzuspielende Lösung: `claude/adoring-volta-olbga0`, `claude/eager-ptolemy-zqsd34` und `noah_und_sven` haben gegenüber dem geprüften `main` jeweils null eigene Commits. Die ersten beiden wurden bereits integriert. Ein erneutes breites Zusammenführen alter Branches ist kein nächstes Arbeitspaket.

## Abgleich aller Anforderungen

„Teilweise“ bezeichnet passende Softwarebausteine und keine Gerätefreigabe. Die Tabelle bewertet den untersuchten Code; reale Grenzwerte und die Geräteabnahme bleiben zusätzlich erforderlich.

| ID | Stand am 20.10.2026 | Wesentliche Restarbeit |
|---|---|---|
| GB-01 | Teilweise vorbereitet | Gemeinsame Anwendung vorhanden. Gleiche geprüfte Regelkarte, Gerätekonfiguration und gleichzeitiger Viergerätebetrieb fehlen als Freigabe. README nennt bisher RM02. |
| GB-02 | Verbessert, teilweise | Odometrie/IMU und Bildzeitkorrektur vorhanden. Verbindliche Spurgrenze mit Halt, begrenzte Unsicherheit und sichere Fugenüberbrückung fehlen; Suchrotation bleibt. |
| GB-03 | Wesentliche Lücke | Kein vollständiger gemessener Fahrzeug- und Schwenkbereich einschließlich Arm/Kamera als abschließende Freigabeprüfung. |
| GB-04 | Verbessert, weiterhin widersprüchlich | Standardausweichen ist aus. Die Hindernisprüfung kann trotzdem ohne Armfreigabe rückwärts fahren; Greifabläufe können zusätzliche Fahrbewegungen auslösen. |
| GB-05 | Fehlt | Gerichtete Straßenregelkarte, Knoten-/Zufahrtsbestimmung und erlaubte Ausgänge fehlen. Die geometrische Karte ersetzt diese Informationen nicht. |
| GB-06 | Fehlt | Kein ausgewählter zulässiger Kreuzungsarm mit Bindung bis zur bestätigten Ausfahrt. |
| GB-07 | Fehlt | Keine eigene Abschnittshistorie und abwechslungsreiche Auswahl zulässiger Straßen. |
| GB-08 | Widerspruch und Lücken | Eigene Ampel ist nicht einer Zufahrt zugeordnet. Verdecktes Rot wird weiterhin nach vier Sekunden aufgehoben; unbekannte Freigabe ist kein verbindlicher Einfahrthalt. |
| GB-09 | Teilweise mit Zielkonflikten | Detektoren für Schilder und Zebra vorhanden. Festgelegte Halteposition, tatsächlicher Stillstand, beide realen Überwege und zulässige Manöver fehlen. Automatisches Wenden/Armumschauen ist nicht durch einen Grundbetriebsmodus begrenzt. |
| GB-10 | Teilweise | Mehrbildige Hindernisprüfung und Warteverhalten verbessert. Gemessene Brems-/Latenzgrenzen und geschwindigkeitsabhängiger Folgeabstand fehlen. |
| GB-11 | Offen, externe Voraussetzung | Kein gemeinsam abgenommenes Gegenverkehrsverfahren einschließlich Einfahrten bei K4/K5. Das Abschalten des Ausweichens allein löst die Infrastrukturaufgabe nicht. |
| GB-12 | Teilweise | Mehr Bewegungssensorik genutzt. Pflichtquellen und Ausfallverhalten je Fahrzustand fehlen; ein beliebiger frischer Scan genügt, Odometrieausfall kann zum Befehlsersatz führen. |
| GB-13 | Nicht durchgängig erfüllt | Ungültige Scans können als frei gelten. Sehr alte/ungültige Bildzeitstempel können eine Frischeprüfung umgehen. Tiefenalter und Datenzuordnung sind nicht durchgängig geprüft. |
| GB-14 | Wesentliche Lücke | Mehrere unmittelbare Motorpublisher, keine gemeinsame bleibende STOPP-Sperre und Ausnahmen vor Pflichtprüfungen. Fremdprozessdiagnose verbessert die Anzeige, ersetzt die Sperre aber nicht. |
| GB-15 | Fehlt als gemeinsamer Vertrag | Panel setzt mehrere Teilzustände und Prozessflags zusammen. Gemeinsamer Zustand mit Geräte-/Startkennung, Sequenz, Schema/Versionen, Gültigkeit und Detailreferenzen fehlt. |
| GB-16 | Fehlt | Keine tatsächliche MQTT-Implementierung oder Brokerveröffentlichung; Kamera-, Tiefen- und Scandetails müssen ebenfalls vereinbart und zugeordnet bereitgestellt werden. |
| GB-17 | Teilweise vorbereitet | Manuelle ROS-Domainwahl und neue Diagnose vorhanden. Standard bleibt 30; vollständige Isolation, eindeutige Identität und Viergerätetest fehlen. |
| GB-18 | Fehlt für MQTT | Kein Publisher mit Verbindungszustand, Wiederverbindung, Frischeprüfung und Ausfalltests. Lokale Fahrt und STOPP müssen davon unabhängig bleiben. |

## Fehler mit hoher Priorität

### Bildzeitstempel können die Frischeprüfung umgehen

Ein Bild mit 0,7 Sekunden Aufnahmealter führt zum Halt. Ein sechs Sekunden altes oder um eine Sekunde zukünftiges Bild bekommt dagegen ersatzweise die aktuelle Aufnahmezeit und kann 0,15 m/s Fahrwunsch ergeben. Der Status `zeitstempel_ok=false` verhindert dies nicht. Ungültige Zeitbezüge müssen als ungültiger Sensorzustand wirken. Quellen: [Zeitstempelfallback](https://github.com/davidheinrich73/smartcity-roboter/blob/b9f64424d92f64ed4f391a96b6c6718caae43bcd/line_follower/line_follower.py#L252), [Altersprüfung](https://github.com/davidheinrich73/smartcity-roboter/blob/b9f64424d92f64ed4f391a96b6c6718caae43bcd/line_follower/line_follower.py#L329).

### Ungültige LiDAR-Daten und fehlende Quellen bleiben unzureichend getrennt

Ein vollständig mit `NaN` belegter Scan kann nach Filterung `inf` und anschließend 0,15 m/s Fahrwunsch ergeben. Auch nur einer von zwei konfigurierten Scans reicht derzeit. Welche Quellen zwingend erforderlich sind, muss die Sensorpflichtmatrix festlegen; der Code erzwingt eine solche Matrix noch nicht. „Frei“, „ungültig“, „veraltet“ und „nicht abgedeckt“ benötigen getrennte Zustände. Quellen: [LiDAR-Filter](https://github.com/davidheinrich73/smartcity-roboter/blob/b9f64424d92f64ed4f391a96b6c6718caae43bcd/lib/lidar.py#L13), [Scanprüfung](https://github.com/davidheinrich73/smartcity-roboter/blob/b9f64424d92f64ed4f391a96b6c6718caae43bcd/line_follower/line_follower.py#L230).

### Manöver umgehen erforderliche Sicht und STOPP ist nicht global

Ein frischer KI-Drehwunsch kann ohne Scans und ohne Kamerabilder einen Drehbefehl von 0,8 rad/s ergeben. Die entsprechende Rückgabe liegt vor weiteren Pflichtprüfungen. Panel-STOPP sendet endlich viele Nullbefehle und beendet nur registrierte eigene Fahrprozesse; ein fremder Motorpublisher erhält dadurch keine bleibende Sperre. Die neue Warnung vor fremden Linienfolgern verhindert einen Doppelstart, behebt diesen STOPP-Pfad aber nicht. Quellen: [Manöverausnahme](https://github.com/davidheinrich73/smartcity-roboter/blob/b9f64424d92f64ed4f391a96b6c6718caae43bcd/line_follower/line_follower.py#L321), [Panel-STOPP](https://github.com/davidheinrich73/smartcity-roboter/blob/b9f64424d92f64ed4f391a96b6c6718caae43bcd/panel/panel.py#L529).

### Wendeabbruch erzeugt im Fehlerübergang noch eine Freigabe

Der neue Fehlerhalt ist grundsätzlich sinnvoll. Im Aufruf, der den Fehler setzt, kann der Entscheider aber noch `fahren / Weg frei` liefern. Erst der folgende Aufruf hält an. Der bestehende Test betrachtet einen späteren Endzustand. Der Fehlerübergang selbst muss sofort einen sicheren Befehl liefern. Quellen: [Ablaufende im Entscheider](https://github.com/davidheinrich73/smartcity-roboter/blob/b9f64424d92f64ed4f391a96b6c6718caae43bcd/ki/entscheider.py#L303), [Fehlersperre setzen](https://github.com/davidheinrich73/smartcity-roboter/blob/b9f64424d92f64ed4f391a96b6c6718caae43bcd/ki/entscheider.py#L431).

### Grundbetrieb ist nicht zuverlässig von Greifabläufen getrennt

Trotz `ausweichen=false` und `arm_erlaubt=false` kann ein LiDAR-Hindernis in 15 cm Abstand ohne visuelle Bestätigung einen Rückwärtswunsch von −0,05 m/s auslösen. Das ist eine autonome Wahrnehmungsbewegung statt durchgängigem Halt/Warten; die Probe misst keinen tatsächlichen Linienverlust. Mit Armfreigabe sind zudem seitliches Ausrichten, Annäherung und Greifen aktiv. `ki_darf_arm_bewegen` steht jetzt standardmäßig auf `true`. Ein verbindlicher Grundbetriebsmodus muss zulässige Aktionen zentral begrenzen. Quellen: [Rückwärtsentscheidung](https://github.com/davidheinrich73/smartcity-roboter/blob/b9f64424d92f64ed4f391a96b6c6718caae43bcd/ki/ablaeufe.py#L450), [Armstandard](https://github.com/davidheinrich73/smartcity-roboter/blob/b9f64424d92f64ed4f391a96b6c6718caae43bcd/config/arm.yaml#L15).

### Verkehrsregeln und Fahrzeughülle brauchen verbindliche Freigaben

Verdecktes Rot wird nach vier Sekunden weiter aufgehoben; Signal-ID und Zufahrt fehlen. Stoppschildzeit beginnt weiterhin bei Sichtung statt bestätigtem Stillstand. Wenden kann bei 215 Grad ohne bestätigte Linie erfolgreich enden. Die verbleibende Suchrotation, alte Linienerinnerung, unbegrenzt wiederverwendete Tiefe und pauschale Fahrwegbreite ersetzen keine geprüfte Fahrzeughülle. Quellen: [Ampel-/Schildlogik](https://github.com/davidheinrich73/smartcity-roboter/blob/b9f64424d92f64ed4f391a96b6c6718caae43bcd/ki/entscheider.py#L251), [Wendeabschluss](https://github.com/davidheinrich73/smartcity-roboter/blob/b9f64424d92f64ed4f391a96b6c6718caae43bcd/ki/ablaeufe.py#L193), [Suchrotation](https://github.com/davidheinrich73/smartcity-roboter/blob/b9f64424d92f64ed4f391a96b6c6718caae43bcd/line_follower/linie.py#L431).

Die eigene Dokumentation berichtet bei 0,35 m/s in der Simulation von Auffahren auf einen Würfel und zu später Schildreaktion. Der Panelregler erlaubt bis 0,4 m/s, der Tempoeingang bis 0,5 m/s. Das belegt die Notwendigkeit einer aus gemessenen Latenzen und Bremswegen abgeleiteten Freigabegrenze; es begründet noch keinen bestimmten sicheren Gerätewert. Quelle: [dokumentierte Simulationsbefunde](https://github.com/davidheinrich73/smartcity-roboter/blob/b9f64424d92f64ed4f391a96b6c6718caae43bcd/docs/linie.md#L103).

## Fehlende Funktionsblöcke und Integrationsbedarf

Die neue Kartierung einschließlich Selbstkalibrierung und Replay ist wertvoll für Orientierung und Diagnose. Es fehlen weiterhin die gerichtete Straßenregelkarte, Knoten/Zufahrt, zulässige Ausgänge, eigene Fahrhistorie, Auswahlbindung, Abbiegen und bestätigte Ausfahrt. Diese Navigationsschicht muss ausdrücklich entwickelt werden.

MQTT ist weiter nur als offene Aufgabe dokumentiert. Vor dem Publisher braucht es den gemeinsamen Zustand. Das Panel kombiniert derzeit unabhängige ROS-Teilmeldungen, lokale Dateien und Prozessflags. Im TEST kann es eine hypothetische Geschwindigkeit als m/s anzeigen; Fahrwunsch, endgültige Ausgabe und gemessene Bewegung sind nicht getrennt. Ein bloßes Weiterreichen von `/api/status` erfüllt deshalb den geforderten Vertrag nicht. Quellen: [Panelstatus](https://github.com/davidheinrich73/smartcity-roboter/blob/b9f64424d92f64ed4f391a96b6c6718caae43bcd/panel/panel.py#L686), [Dashboardzustand](https://github.com/davidheinrich73/smartcity-roboter/blob/b9f64424d92f64ed4f391a96b6c6718caae43bcd/panel/index.html#L900), [Fahrwerte im TEST](https://github.com/davidheinrich73/smartcity-roboter/blob/b9f64424d92f64ed4f391a96b6c6718caae43bcd/line_follower/line_follower.py#L372).

Für vier Geräte sind ROS-Isolation sämtlicher Treiber/Programme, Identität, geprüfte Software und Regelkarte sowie Kalibrierung verbindlich zu machen. Die neue Domain-/Boarddiagnose hilft dabei. Ein gemeinsames `git pull` und individuell fortgeschriebene Belegungskarten bilden noch keine gemeinsame Gerätefreigabe. Gegenverkehr und Brokervertrag bleiben Partneraufgaben mit gemeinsamer Abnahme.

Die Zieldefinition verweist außerdem auf nicht vorhandene Dateien: Abbildungen unter `docs/abbildungen/` sowie ältere Prüf-, RM04-, Schnittstellen- und Teamunterlagen. Diese Quellen sollten wiederhergestellt oder durch gültige Verweise ersetzt werden. README/Projektbeschreibung ordnen den Viergerätebetrieb teilweise weiter unter „später“ ein; für die vollständige Abnahme gehört er bereits zum Grundbetrieb.

## Ausgeführte Prüfungen

Alle 98 versionierten Dateien des Hauptstands wurden inventarisiert; Quellbereiche, Konfiguration, Skripte, Dokumentation, Tests und Branchhistorie wurden auf Zielbezug geprüft.

| Vorhandenes Testskript | Ergebnis | Ausgegebene Einzelprüfungen |
|---|---|---:|
| `tests/test_ampel.py` | Bestanden | 17 |
| `tests/test_entscheider.py` | Bestanden | 82 |
| `tests/test_greifen.py` | Bestanden | 20 |
| `tests/test_karte.py` | Bestanden | 22 |
| `tests/test_line_follower.py` | Bestanden | 21 |
| `tests/test_schilder.py` | Bestanden | 5 |
| **Gesamt** | **6 Skripte bestanden** | **167** |

Zusätzlich: 56 Python-Dateien syntaktisch fehlerfrei; 13 Shellskripte mit `bash -n` fehlerfrei. Umgebung: Windows, Python 3.12.14, NumPy 2.3.5, OpenCV 5.0.0 und PyYAML 6.0.3. Der Kartentest dauerte etwa 79 Sekunden. Die [maschinelle Zusammenfassung](pruefungen/2026-10-20-softwaretests.json) hält den geprüften Commit und die Ergebnisse fest.

Die [gezielten Prüfprobes](pruefungen/2026-10-20-probes.json) reproduzieren acht Abweichungsfälle und eine positive Kontrolle. Sie verwenden unveränderte Methoden mit ROS-Attrappen und kontrollierter Uhr. Nur für die drei Bildzeitprüfungen wird die Linienerkennung deterministisch ersetzt; Bilderkennungsqualität und reale Motorbewegung sind damit nicht geprüft. Das [Prüfskript](pruefungen/2026-10-20-probes.py) dokumentiert Methode und Quellhashes. Sein Exitcode 0 bedeutet Reproduktion der Beobachtungen und keine bestandene Sicherheitsabnahme.

Zum Wiederholen am unveränderten Prüfstand:

```bash
git worktree add ../smartcity-pruefung b9f64424d92f64ed4f391a96b6c6718caae43bcd
python3 docs/pruefungen/2026-10-20-probes.py --repo ../smartcity-pruefung --output /tmp/smartcity-probes.json
```

Die sechs Testskripte prüfen heutiges Verhalten, teilweise einschließlich Rot-Timeout, Armumschauen, Greifen und Wenden. Ihre grünen Ergebnisse sind daher keine vollständige Zielabnahme. Die ROS-Simulation bildet weiter einen Rundkurs mit einem Überweg statt des vollständigen Netzes mit acht Knoten und beiden Überwegen ab. ROS-Simulation, reale Gerätefahrt, Watchdogmessung, Brokerempfang und Viergeräteabnahme wurden in dieser Prüfung nicht ausgeführt.

## Zusammenarbeit im aktuellen Repository

Die GitHub-Abfrage am 20.10. bestätigt Schreibrechte für `letsc4`, aber keine Administrationsrechte. `main` wird ungeschützt gemeldet, Repository-Regelsätze sind leer, und GitHub Actions meldet null Workflows. Zum Abrufzeitpunkt bestanden keine offenen Pull Requests und keine offenen Issues. Versionierte Regeln für Beiträge, Dateizuständigkeiten, PR-/Aufgabenvorlagen und einen gemeinsamen Testaufruf fehlen.

Die Historie enthält Pull Requests und zusätzliche unmittelbare Änderungen beziehungsweise Worktree-Merges. Daraus lässt sich kein Urteil über einzelne Personen ableiten. Für drei oder mehr aktive Entwickler fehlen aber erkennbare gemeinsame Arbeitspakete, reservierte Integrationsdateien und ein automatisches Prüftor.

Die nächste sinnvolle Entwicklung ist deshalb: erst Verantwortungsbereiche und Schnittstellen festlegen, dann Sicherheitsbasis, Navigation und Datenanbindung parallel in kleinen Paketen aufbauen. Der [Entwicklungsplan](zusammenarbeit-und-entwicklung.md) enthält Dateigrenzen, Abhängigkeiten und Abnahmekriterien. Die vorliegenden Änderungen ergänzen Dokumentation und Prüfnachweise; sie reparieren den Fahrbetrieb noch nicht.
