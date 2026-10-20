# Vorschlag für Zusammenarbeit und Weiterentwicklung

**Stand 20.10.2026.** Für drei oder mehr aktive Entwickler empfiehlt sich eine Aufteilung in Betrieb/Sicherheit, Wahrnehmung/Navigation und Zustandsdaten/MQTT/Panel. Jede Aufgabe erhält einen verantwortlichen Menschen, einen eigenen Branch, vereinbarte Dateien und ein überprüfbares Ergebnis. Die gemeinsame Integration erfolgt über kleine Pull Requests.

Ausgangspunkt sind der [Repositoryabgleich](pruefung-grundbetrieb-2026-10-20.md) und die [Zieldefinition](zieldefinition-grundbetrieb.md). Diese Datei schlägt den Teamablauf und die nächsten Pakete vor. Die namentliche Besetzung und die noch offenen Infrastrukturregeln werden im Team festgelegt; vorhandene GitHub-Einstellungen werden durch diese Dokumentation nicht aktiviert.

## Drei parallele Entwicklungsbereiche

| Bereich | Verantwortung | Vorrangig eigene Dateien |
|---|---|---|
| **A Betrieb und Sicherheit** | Motorfreigabe, STOPP/Fehler, Pflichtsensoren, Zeit-/Befehlsprüfung, Spur-/Hüllengrenzen, Geräteprofile und Startquellen | `line_follower/line_follower.py`, `lib/lidar.py`, `scripts/*`, Geräteparameter; neue Betriebs-/Sicherheitsmodule |
| **B Wahrnehmung und Navigation** | Linienarme, Knoten/Zufahrt, erlaubte Route, Fahrhistorie, Abbiegen/Ausfahrt, zugeordnete Ampeln, Schilder und Überwege | `ki/*`, `erkennung/*`, `line_follower/linie.py`, Ampel-/Schildermodule, `lib/tiefe.py`, `lib/zebra.py`; neue Straßenkarten-/Navigationsmodule |
| **C Zustandsdaten und Anbindung** | Versionierter Zustandsvertrag, konsistente Zustandsbildung, MQTT, Detaildaten und Panel | Neue Zustands-/MQTT-Module und Vertragsdateien, `panel/*`, Broker-Testwerkzeuge |
| **Weitere Entwickler und Mitwirkende** | Abgeschlossene Test-/Simulatorfälle, Messfahrten, Kalibrierung, Geräteprotokolle, Aufnahmen und Dokumentation | Je Arbeitspaket ausdrücklich benannte Testdateien, Fixtures und Dokumente |

Kartografie und Replay (`kartograf/*`, `lib/karte.py`, `lib/kartierer.py`, `lib/aufnahme.py`) erhalten je Paket genau einen Besitzer. Die vorhandene Kartierung wird gezielt für Orientierung und Diagnose genutzt; zusätzliche Karten-/Armfunktionen laufen getrennt von der Grundbetriebsintegration.

Das sind Dateizuständigkeiten, keine starren Wissensgrenzen. Jeder Bereich hat eine Vertretung und lässt Änderungen prüfen. Insbesondere bleibt `ki/zentrale.py` ein Integrationspunkt von B, `line_follower/line_follower.py` von A und `panel/panel.py` von C. Benötigt ein anderer Bereich dort einen Anschluss, wird er als kleine Übergabe mit dem Besitzer integriert. Nicht mehrere offene Gesamtumbauten derselben Datei beginnen.

`config/roboter.yaml`, Datenverträge und Zieldefinition sind gemeinsame Schnittstellen. Für jede Änderung daran übernimmt genau ein Aufgabenbesitzer die Integration; betroffene Bereiche prüfen die Änderung vor ihrer Verwendung.

## Vor parallelem Umbau vier Schnittstellen festlegen

Die folgenden Verträge sollen kurz, versioniert und anhand synthetischer Beispiele prüfbar sein. Sie beschreiben fachliche Bedeutung und Gültigkeit; die endgültigen Feldnamen werden gemeinsam gewählt.

| Vertrag | Mindestinhalt | Zuständigkeit |
|---|---|---|
| Sensor und Wahrnehmung | Gerät/Quelle, Aufnahmezeit, monotone Empfangszeit, Frame-/Messungskennung, Koordinatenbezug, Einheit, Qualität und Fehlergrund. Frei, ungültig, unbekannt und veraltet unterscheiden. Pflichtquellen je Fahrzustand festlegen. | A und B; C prüft Darstellbarkeit |
| Fahrwunsch und Freigabe | Start-/Sequenzkennung, Ablaufzeit, gewünschte Geschwindigkeit/Drehung, ausgewähltes Manöver und fachliche Haltegründe. B liefert Wünsche; A prüft abschließend STOPP, Fehler, Pflichtdaten, Hülle und Betriebszustand. Nur A besitzt den finalen Motorpublisher. | B liefert, A setzt durch |
| Gemeinsamer Zustand | Ein konsistenter Datensatz mit Geräte-/Startkennung, Sequenz, Versionen, Zeit, Gültigkeit, Route, Haltegründen, Motorfreigabe sowie getrennt Wunsch, endgültige Ausgabe und gemessene Bewegung. Bilder/Tiefe/Scans erhalten gemeinsame Referenzen. | C integriert mit A/B |
| Gerät und Abnahme | RM01–RM04, ROS-Domain und sämtliche Treiber, Software-/Regelkartenstand, gemessene Kalibrierung und Testprotokoll. MQTT-Vertrag einschließlich Brokerbestätigung und Detaildaten abstimmen. | A/C und Geräte-/Partnerteams |

Das Zustandsmodul gehört C. A liefert darin das verbindliche Freigabeergebnis und die Motorausgabe, B die Wahrnehmungs-/Navigationsentscheidung. Panel und MQTT konsumieren diesen Zustand. Sie erzeugen keine zweite fachliche Fahrentscheidung. Ein zweites separates Zustandsmodell für das Panel würde die bisherige Lücke fortsetzen.

Der Vertrag legt Typen, SI-Einheiten und Gültigkeitsregeln fest; nicht verfügbare Zahlen erscheinen als `null` mit Status statt als scheinbar gültige Null oder unendliche JSON-Zahl. Lokale Altersprüfung verwendet monotone Zeit, geräteübergreifender Zeitbezug erhält einen sichtbaren Synchronisationsstatus. Für GB-18 veröffentlicht C auch Brokerstatus und bestätigte Sequenz: begrenzte Warteschlangen, erkennbar veraltete Daten und ein frischer vollständiger Zustand nach Wiederverbindung, die niemals eine Motorfreigabe erzeugt.

## Arbeitsablauf für Menschen und Coding Agents

1. Vor Beginn ein Arbeitspaket mit Ziel, GB-/Abnahmebezug, Besitzer, betroffenen Dateien, Abhängigkeiten und Bestehenskriterium festhalten. Erst beginnen, wenn Schnittstellen und Dateien frei sind.
2. Für jedes Paket von aktuellem `main` einen kurzen Aufgabenbranch erstellen, beispielsweise `fix/gb-bildalter`, `feat/gb-motorfreigabe` oder `feat/gb-mqtt`. Ein Branch hat einen verantwortlichen Besitzer. Dieser Dokumentationsbranch `codex/grundbetrieb` soll kein dauerhafter Sammelbranch werden.
3. Früh einen Draft-PR öffnen, damit Arbeit und Dateiumfang sichtbar sind. Bei Überschneidungen vor der zweiten Änderung klären, welcher PR zuerst integriert wird und welche Übergabe nötig ist.
4. Eine fachlich zusammenhängende Änderung pro PR vorlegen. GB-Kennung, Verhalten vorher/nachher, Schnittstellenänderung und tatsächlich ausgeführte Prüfungen angeben. Unausgeführte Geräteprüfungen bleiben als offene Freigabe sichtbar.
5. Eine fachkundige andere Person prüft den PR. Motor-, Sensor- und Vertragsänderungen erhalten einen gemeinsamen Übergabetest der betroffenen Bereiche. Der Aufgabenbesitzer löst Konflikte im eigenen Branch, führt relevante Tests erneut aus und lässt den geänderten Stand prüfen.
6. Nach Review und Prüfungen integrieren. Danach aktualisieren andere ihre Branches. Bereits geteilte Branchhistorie nicht ungeplant umschreiben; im geteilten Branch kann `main` zusammengeführt werden. Kein Force-Push auf `main`.

Dieser Ablauf folgt dem branchbasierten [GitHub Flow](https://docs.github.com/en/get-started/using-github/github-flow). Er benötigt keinen zusätzlichen dauerhaften `develop`-Branch. Eine größere Integration wird über klar voneinander abhängige kleine PRs aufgebaut.

Auf demselben Rechner bekommt jeder aktive Agent eine eigene Arbeitskopie oder einen eigenen Git-Worktree. Mehrere Agents schreiben nicht im selben Verzeichnis und wechseln dort nicht gegenseitig Branches. Der menschliche Paketbesitzer prüft die zusammengeführten Änderungen; die Anzahl paralleler Agents ersetzt keine Dateizuständigkeit.

Auch die Laufzeit braucht Trennung: `scripts/simulation.sh` verwendet derzeit Domain 77, Port 8080 sowie feste temporäre Arm-/Lerndateien. Worktrees isolieren diese Ressourcen nicht. Deshalb auf demselben Rechner zunächst nur eine dieser Simulationen gleichzeitig betreiben. Für echte parallele Simulationsläufe müssen Domain, Port, Karten-, Log-, Lern- und temporäre Dateipfade je Lauf reserviert und parametrisiert werden; Domains dürfen sich auch im gemeinsamen Netz nicht mit Geräten oder anderen Läufen überlagern.

Reale Gerätetests erhalten ebenfalls einen zugeordneten Betreiber und ein Zeitfenster pro Gerät. Ein zweiter Entwickler startet dort keinen parallelen Fahrprozess. MQTT-Tests verwenden getrennte Testidentitäten, Clientkennungen und abgestimmte Testtopics, damit sie reale Telemetrie nicht überschreiben.

## GitHub als gemeinsames Prüftor einrichten

Die Abfrage am 20.10. zeigt: `main` ungeschützt, keine Regelsätze, keine Actions-Workflows, keine offenen Aufgaben/PRs. Der Zugang `letsc4` darf schreiben, besitzt aber keine Administrationsrechte.

Der Repository-Eigentümer sollte für `main` eine Regel einrichten: Änderungen über Pull Requests, mindestens eine zustimmende Prüfung einer anderen Person, erledigte Reviewgespräche, erfolgreiche erforderliche Checks sowie gesperrtes Löschen/Force-Push. Die Regeln sollten auch bei administrativer Integration beachtet werden. Erforderliche CI-Checks werden erst ausgewählt, nachdem sie mit stabilen eindeutigen Namen existieren und erfolgreich gelaufen sind. Technische Optionen beschreibt GitHub unter [geschützte Branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

Eine `CODEOWNERS`-Datei kann die zuständigen Prüfer automatisch zuordnen. Dafür pro Pfad einen Hauptverantwortlichen und eine Vertretung mit Schreibrechten eintragen, sobald die GitHub-Konten feststehen. Sie sperrt keine Dateien und verhindert keine gleichzeitigen Änderungen; die Aufgabenreservierung bleibt erforderlich. Verbindliche Codeowner-Freigaben brauchen zusätzlich passende Branchregeln. Quelle: [GitHub Code Owners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners).

Als nächste versionierte Hilfen genügen eine kurze Beitragsanleitung, ein PR-Formular und eine Arbeitspaketvorlage. Ein Paket sollte enthalten:

```text
Ziel und zugehörige GB-/A-Kennungen:
Verantwortlicher Mensch und Prüfer:
Reservierte Dateien und Schnittstellen:
Abhängige Pakete und ausgeschlossener Umfang:
Erwartetes Verhalten und Bestehenskriterium:
Ausgeführte Softwareprüfungen mit Commit:
Benötigte Geräteprüfung und tatsächliches Ergebnis:
```

Ein gemeinsamer Testaufruf soll alle vorhandenen sechs Skripte ausführen und bei einem Fehler fehlschlagen. Der Kartentest braucht deutlich mehr Zeit als die kurzen Logiktests; getrennte CI-Jobs oder passende Zeitlimits verhindern verdeckte Auslassungen. Für die Jetsons ist zusätzlich eine reproduzierbare Umgebung passend zu Ubuntu 22.04, Python 3.10 und ROS 2 Humble erforderlich. Die Windows-Prüfung dieses Berichts ersetzt diese Umgebung nicht.

Automatische Checks umfassen zunächst Syntax und Softwaretests mit künstlichen Daten. Danach kommen zielkonforme Regressionstests, Aufnahmen und vollständige ROS-Simulation hinzu. Szenariotests für Greifen/Umkehr werden getrennt ausgewiesen. Gerätefahrt, Bremsweg, Watchdog und externer Brokerempfang bleiben eigene Abnahmen. Ein grüner CI-Lauf ist kein Fahrfreigabenachweis.

## Die nächsten Arbeitspakete

Die Kennungen sind Vorschläge für neue Aufgaben, noch keine angelegten GitHub-Issues oder zugesagten Termine.

| Paket | Verantwortungsbereich | Ergebnis und Abhängigkeiten | Prüfbezug |
|---|---|---|---|
| **AP00 Zusammenarbeit und Verträge** | A/B/C gemeinsam, ein benannter Integrator | Rollen und Dateien besetzen; Schnittstellen und Grundbetriebsgrenzen festlegen; Testaufruf/CI, PR-/Aufgabenvorlagen und Eigentümerregel vorbereiten. Zieldefinitionsbilder und Quellverweise reparieren. Vor Beginn großer paralleler Umbauten. | Grundlage aller Abnahmen |
| **AP01 Akute Fehler und Grundbetriebsmodus** | A für Bild-/Motorpfad, B für Entscheider/Abläufe | Ungültige Bildzeit verhindert Fahrt; kein Manöver vor Pflichtprüfung; Wende-Fehlerübergang sofort sicher; Rot bleibt ohne passende Freigabe wirksam. Greifen, Armumschauen, Rückwärts-Wahrnehmung und Suchrotation nur im separat freigegebenen Umfang. Jede Korrektur mit passendem Regressionstest. | A01, A03, A05, A07, A11, A12 |
| **AP02 Betriebsmodell und Motorfreigabe** | A; Übergabe an B/C | Ein finaler Publisher, verriegelter STOPP/Fehler, Pflichtsensor-/Befehlsprüfung, kontrollierte Fremdquellen. Fahrzeughülle, Sensortransformationen, Geschwindigkeits-/Abstandsgrenzen messen und durchsetzen. Baut auf AP00 auf; nicht durch einzelne AP01-Patches ersetzen. | A01–A03, A05, A09, A11, A12 |
| **AP03 Gemeinsamer Zustand und MQTT** | C; A/B liefern festgelegte Daten | Zustand bereits im Stillstand/TEST bilden, Panel daran anbinden, tatsächlichen nicht blockierenden Publisher und zugeordnete Detailkanäle entwickeln. GB-18: Verbindungsstatus, bestätigte Sequenz, begrenzte Warteschlange und frischer Zustand nach Wiederverbindung ohne Motorfreigabe. Brokervertrag und Zeitbasis mit Partnerteam klären. Nach AP00 parallel zur Navigation; keine Motoranbindung für Fernbefehle im Grundbetrieb. | A13, A14 |
| **AP04 Straßenkarte und Kreuzungsnavigation** | B; Aufbau-/Infrastrukturteam liefert Festlegungen | Gerichtete Karte, sichere Knoten/Zufahrt, erlaubte Ausgänge, Historie, Auswahlbindung, Abbiegen und Ausfahrtbestätigung. A setzt jede Bewegung durch. Alle erlaubten Zufahrt-/Ausfahrtkombinationen gezielt prüfen. | A02, A04–A08 |
| **AP05 Zwei Geräte und Infrastruktur** | A/B/C mit Partnerteams | Gemeinsamer geprüfter Stand auf zwei getrennten Geräten; Nachfahren, eigene/fremde Ampel und beide Überwege prüfen. Gegenverkehr einschließlich K4/K5 und tatsächlicher Räumung gemeinsam abnehmen. AP02–AP04 und reale Aufbauverträge vorausgesetzt. | A07–A10, A13–A15 |
| **AP06 Viergerätefreigabe und Dauerlauf** | Geräte-/Testteam, technische Besitzer beheben Fehler | RM01–RM04 mit identischem geprüftem Software-/Regelkartenstand, individuellen Kalibrierungen und isolierten Identitäten. Unterbrechungen, STOPP und Dauerlauf gemäß festgelegten Grenzen nachweisen. | A01–A16, alle Pflichtprüfungen |

Viergerätebetrieb und MQTT sind Bestandteile der vollständigen Zielabnahme. Eine kurze Einzelfahrt ist ein sinnvoller Meilenstein, aber keine Umdefinition des Grundbetriebs. Greiflernen, Einsatzaufträge und weitere Sonderfunktionen werden separat weitergeführt, solange sie die Grundbetriebsintegration nicht ersetzen oder unkontrolliert verändern.

## Konkreter Start mit mindestens drei Entwicklern

Zuerst gemeinsam die Dateizuständigkeiten und die vier Schnittstellen aus AP00 festlegen. Danach können drei überschaubare Einstiege parallel laufen:

- **A:** Bildzeit-/Pflichtdatenfehler in `line_follower/line_follower.py` mit sicheren Fehlerzuständen korrigieren; Vorbereitung des alleinigen Motorwegs beginnen.
- **B:** Wende-Fehlerübergang und Rot-Halt in `ki/entscheider.py` korrigieren; Grundbetriebsgrenzen für `ki/ablaeufe.py` festlegen und anschließend das gerichtete Straßenmodell entwickeln.
- **C:** Zustandsvertrag und synthetische Beispieldaten erstellen; Panel und MQTT zunächst im Stillstand anbinden. Änderungen an Motor-/KI-Integrationsdateien über A beziehungsweise B übernehmen lassen.

Weitere Personen übernehmen klar begrenzte Testpakete, beispielsweise fremdes Grün, verlorene Linie, ungültige Tiefe, zwei Überwege, Messfahrt-Replay oder Geräte-/Domaininventar. Auch ein kleines Testpaket bekommt einen eigenen Besitzer und Branch. So kann die Parallelität steigen, ohne die drei Integrationsdateien gleichzeitig umzubauen.

## Integration und Geräteauslieferung

Einmal je Arbeitstag kurz abgleichen: aktive Pakete, reservierte Dateien, Schnittstellenänderungen, Reihenfolge der nächsten PRs und benötigte Gerätezeit. Konflikte nicht erst beim abschließenden Großmerge entdecken.

`main` bezeichnet den integrierten Entwicklungsstand. Ein auf dem Gerät zu prüfender Kandidat wird zusätzlich an einen konkreten Commit oder später ein Freigabetag gebunden. Nicht während eines Abnahmelaufs per ungebundenem `git pull` aktualisieren. Pro Gerät sind Software-, Regelkarten- und Konfigurationsstand sowie Kalibrierung im Protokoll festzuhalten; lokale Zugangsdaten und Kalibrierdateien bleiben außerhalb des Repositorys.

Nach einer bestandenen Geräteprüfung wird genau dieser Stand für die nächsten Geräte verwendet. Fehler erhalten einen reproduzierbaren Fall mit Commit, Gerät, Erwartung, Ergebnis und geeigneter Aufnahme. Der neue Replaypfad hilft dabei, ohne alle Entwickler gleichzeitig am selben Roboter arbeiten zu lassen.
