# Geräteprüfung nach der A1 Sicherheitskorrektur

**Prüfauftrag:** Die Softwareänderung aus PR #17 am Referenzgerät auf echte Kamerazeitstempel, lokale Nullausgabe und tatsächliche Haltreaktion prüfen. Durchführung im abgestimmten betreuten Gerätefenster durch das Geräte-/Testteam. Dieser Prüfplan dokumentiert noch keine bestandene Prüfung und löst keine Fernfahrt aus.

PR #11 enthält Dokumentation und benötigt selbst keinen Fahrtest. PR #17 verändert die Freigabeentscheidung. Die Softwareregressionen ersetzen deshalb vor einer bewegten Gerätefreigabe nicht die folgenden realen Prüfungen. Zugeordnet: GB-12/13/14, A11 und A12 im begrenzten A1-Umfang.

## Prüfstand festhalten

| Feld | Eintrag vor Durchführung |
|---|---|
| Datum, Betreiber und beobachtende Person | offen |
| Gerät und bestätigte Identität | offen; zunächst ein Referenzgerät |
| Softwarecommit mit integriertem A1 | tatsächlichen installierten SHA eintragen |
| Geräte-/Konfigurations-/Kalibrierstand | offen |
| ROS-Domain aller lokalen Quellen und Programme | prüfen und dokumentieren |
| Aktive Motorpublisher und ausgeschlossene Fremdquellen | vollständig erfassen; kein paralleles Gamepad/Altprogramm |
| Laufende Alters-/Abstandsparameter und Zeitbasis | tatsächlich geladene Werte eintragen |
| Messverfahren und vorher festgelegte Reaktionsgrenzen | offen; keine angenommene Watchdogzeit übernehmen |

Zuerst ohne Fahrbewegung Zeitbasis und Quellen prüfen. Danach Motorreaktionen im geeigneten gesicherten Prüfstand prüfen, etwa mit frei laufenden Rädern bei sicher abgestütztem Gerät und festgelegter Armstellung. Erst nach diesen Prüfungen folgt eine beaufsichtigte kurze Bodenfahrt mit vorher freigegebener niedriger Geschwindigkeit auf freier Strecke. Kein Viergeräte- oder Greiftest als erster Nachweis.

## Fälle und Bestehenskriterien

| Fall | Aufbau und Beobachtung | Erwartung |
|---|---|---|
| Echte Kamerazeit | Aufnahmezeit der realen Kamera, Rechner-/ROS-Zeit und Datenalter vergleichen; mehrere Bilder und Rechnerlast betrachten | Nicht null, plausibel und zur verwendeten Zeitbasis passend. Eine unbekannte Zeitbasis erzeugt Halt statt Ersatzzeit. |
| Ungültige oder alte Aufnahme | Im isolierten kontrollierten Testaufbau fehlende/Null-/Zukunftsstempel sowie alte Aufnahmen einschließlich 0,7 und sechs Sekunden prüfen | Sichtbarer Haltgrund, Nullausgabe; sehr alte Aufnahmen werden nicht wieder scheinbar frisch. Testeinspeisung nicht in fremde Geräte-Domains richten. |
| Ausbleibende Kamerabilder | Tatsächlichen Bildstrom kontrolliert unterbrechen und lokale Entscheidung sowie Bewegung beobachten | Halt nach der geltenden Aktualitätsgrenze. Endlich alter Empfang darf nicht unbefristet Fahrt erlauben. |
| Fehlender oder veralteter LiDAR | Alle von der bestehenden Freigabe verwendeten Scandaten im isolierten Prüfaufbau kontrolliert ausbleiben oder veralten lassen; auch Dreh-/Rückwärtswunsch prüfen | Erforderliche Sicht fehlt: Nullbewegung auch für Manöver. Ausfall nur einer von mehreren Quellen und vollständig ungültige Scanbereiche bleiben als A2-Restarbeit gesondert zu bewerten. |
| Aktive Notbremse | Reales Hindernis im geprüften Erfassungsbereich; lokale Ausgabe und tatsächlichen Stillstand beobachten | Kritischer Abstand sperrt Vorwärts-, Seiten-, Dreh- und Rückwärtswünsche. Tatsächliche Hüllen-/Abstandsreserve bleibt zusätzlich zu vermessen. |
| Erholung nach Sensorhalt | Nach einem Sensorhalt wieder gültige frische Daten liefern | Nur nach erneuter vollständiger Prüfung eine zulässige Entscheidung. Keine Umdeutung ungültiger Daten in frei. Sensorhalt und bewusster Bedien-STOPP getrennt behandeln. |
| Bedienung und Senderausfall | TEST/START/STOPP sowie Abbruch des Fahrbefehlssenders im gesicherten Aufbau prüfen; Nullausgabe und Stillstand getrennt messen | TEST ohne Motorfreigabe; tatsächliche Haltreaktion und Zeit dokumentiert. Ein gesendeter Nullbefehl oder kommentierter Board-Watchdog ist kein Stillstandsnachweis. |

Für die Zeitmessung Sensor-/Aufnahmezeit, Entscheidung, endgültige Befehlsausgabe und beobachteten Stillstand getrennt erfassen. Nicht allein die Panelanzeige oder das Prozessende als Bewegungssignal verwenden. Jeder Fall bekommt Erwartung, tatsächliches Ergebnis, Messwert/Zeitraum und offenen Fehler.

## Freigabegrenze

A1 behebt zwei lokale Freigabefehler. Globale STOPP-Verriegelung, alleiniger Motorpublisher, vollständige Scanqualität/Pflichtmatrix, Fahrzeughülle und gemessene Brems-/Watchdoggrenzen bleiben offen. Ein erfolgreicher A1-Gerätetest ist deshalb eine Teilprüfung und keine Freigabe des vollständigen Grundbetriebs oder des Vierroboter-Dauerlaufs.

Wenn die echte Kamera keine passenden Zeitstempel liefert, bleibt die Fahrt gesperrt. Zuerst die Quelle/Zeitbasis klären; die Prüfung nicht zur Wiederherstellung der Fahrt abschalten. Bei nicht bestandenem Fall Softwarestand und Messung an den Orchestrator übergeben. Reale Protokolle gehören nach `docs/abnahme/`; die Zuständigkeiten aus [E](E-geraete-und-infrastruktur.md) bleiben bestehen.
