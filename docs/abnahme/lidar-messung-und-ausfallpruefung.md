# LiDAR: Messbezug und versionsbezogene Ausfallprüfung

Stand: 22.10.2026. **Vorbereitete Prüfdokumentation; keine Gerätefreigabe.**
Bezug: [#66](https://github.com/BBS-GuT/smartcity-roboter/issues/66),
[#67](https://github.com/BBS-GuT/smartcity-roboter/issues/67), Elternissue
[#58](https://github.com/BBS-GuT/smartcity-roboter/issues/58).
Diese beiden offenen Issues haben beim Abgleich weder Kommentare noch Unterissues.
Die Vorlage unterstützt GB-03/04/12/13/14 und Teilnachweise A03/A11/A12 aus der
[Zieldefinition](../zieldefinition-grundbetrieb.md); sie schließt diese nicht ab.

## Versions- und Beleggrenzen

Softwarebasis dieser Vorbereitung ist
`dc6acc25e490edc301a6464af8fe19e17339aa42` (Integration von
[PR #170](https://github.com/BBS-GuT/smartcity-roboter/pull/170)).
Dieser Commit ist **kein Nachweis des installierten Gerätestands**. Den vollen
installierten SHA und die tatsächlich neu gestarteten Prozesse vor jeder Prüfung
festhalten. Nach Software-, Konfigurations-, Montage- oder Armstellungsänderung
betroffene Fälle auf dem neuen Stand wiederholen; alte Ergebnisse erhalten.

| Belegklasse | Aussage und Grenze |
|---|---|
| Historische RM01-Referenzprobe | Der [Bericht vom 21.10.](RM01-2026-10-21-lidar-software.md) belegt radiale Zielmessungen am dort fixierten Stand. Aufstellunsicherheit bleibt unbekannt; dies bestätigt keine vollständige Einbaupose. |
| Integrierte Software | PR #170 enthält gemeinsame Abdeckung im Fahrzeugbezug und synthetische Regressionen. Aktuelle CI und nativer Review gehören jeweils zu ihrem exakten SHA. Sie messen keine Motorreaktion. |
| Private RM01-Messbelege vom 22.10. | Bestätigte horizontale Sensorpositionen und Hüllengrenzen liegen im privaten Prüfbestand. Einzelwerte, Geräte-/Netzdaten und lokale Rohdaten bleiben dort. Vollständiges z, Orientierung und Unsicherheit werden dadurch nicht pauschal bestätigt. |
| 35 gespeicherte reale Scanpaare | Offline erneut ausgewertet; **keines gibt den Frontschutz frei**. Das ist keine neue Geräteprobe und kein Beweis eines Hardwaredefekts. Unbekannter äußerer Nahbereich bleibt sperrend. |
| RM02-Praxisberichte | [Problemprotokoll](../problemprotokoll.md): niedrige Hindernisse unterhalb der LiDAR-Ebene, überfahrene Hindernisse und zeitliche Verarbeitungslücken sind gezielte Prüfanlässe. RM02-Mess-/Replaywerte und dortige Softwaretests gelten nicht als RM01-Pose oder RM01-Haltabnahme. |

[#169](https://github.com/BBS-GuT/smartcity-roboter/issues/169) ist durch PR #170
softwareseitig integriert und geschlossen. Keine zweite Implementierung nötig.
Die [gemeinsame Abdeckung](../lidar-gemeinsame-abdeckung.md) beschreibt die
Parameter und die verbleibenden physikalischen Grenzen. Die im offenen
[PR #168](https://github.com/BBS-GuT/smartcity-roboter/pull/168) beschriebenen
Fahr-Gehirn-Simulatorergebnisse betreffen einen separaten Modus und sind kein
realer Haltbeleg für den normalen Fahrablauf.

**Software-Nachtrag zur Basis:** Der #58-Orchestrator hat auf obiger
Basis mit ideal gültigen Vollscans reproduziert, dass vollständig fehlende
Geometrie in beiden Verbrauchern auf den bisherigen Sensorursprungs-Pfad
zurückfällt, auch nach Entfernen aller Geometrieangaben. Die Korrektur aus
[PR #176](https://github.com/BBS-GuT/smartcity-roboter/pull/176), geprüft am Head
`ac56051b438375ea63220120d4158837d2b690cb`, ist inzwischen im Sammelbranch
`fix/gb-58-lidar` integriert. Vor Geräteprüfung die Korrektur im tatsächlich
installierten SHA bestätigen. Fehlende Pose/Hülle muss halten; die ursprüngliche
Basis erfüllt S07 noch nicht vollständig. Auch dieser Softwarestand ist keine
Gerätefreigabe.

## #66: Messung, Annahme und offene Größen getrennt führen

Privat je Quelle ein Messblatt mit Datum, Prüfer, Geräteidentität, physischer
Sensorzuordnung, Topic, tatsächlichem `header.frame_id`, Messmittel und Skizze
führen. Der Fahrzeugursprung muss physisch wiederauffindbar sein: x vorwärts,
y links, z aufwärts, Längen in Metern. „Robotermitte“ allein legt weder Höhe noch
Messpunkt hinreichend fest. Sensorursprung ist das Mess-/Drehzentrum, nicht eine
beliebige Gehäusekante. Fahrstellung und äußerste bewegte Hülle einschließlich
Sensoren, Rädern, Kamera und Arm festhalten.

| Größe je Quelle | Belegstatus dieser Vorbereitung | Erforderlicher privater Nachtrag |
|---|---|---|
| Physischer Sensor ↔ Topic/Frame | Bisherige Zuordnung aus Prüfbestand; vor Verwendung am tatsächlichen Stand bestätigen | Eindeutige Zuordnungsprobe mit bekanntem Ziel; keine bloße Topic-Namensannahme |
| x/y und horizontale Hüllengrenzen | Lokale bestätigte Messwerte vorhanden, hier bewusst nicht veröffentlicht | Messblatt referenzieren; Frontkante gegen vorderes Sensorzentrum gezielt auf Konsistenz prüfen |
| z beider Sensoren | Vollständiger unabhängiger Nachweis offen | Höhe der Messebene relativ zum definierten Ursprung und Boden messen |
| Orientierung, 0° und Drehsinn | Vollständiger bestätigter Nachweis offen; konfigurierte Winkel sind kein Messbeleg | Ziele vor/links/rechts zuordnen; Vorzeichen, yaw sowie roll/pitch bzw. Ebenenneigung mit Methode und Unsicherheit bestätigen |
| Unsicherheit aller Maße/Winkel | Vollständiger Nachweis offen | Auflösung, Messpunkt-/Aufstellfehler, Wiederholmessungen und verwendete Unsicherheitsgrenze je Größe nennen |
| Abdeckung außerhalb der Hülle | Frontfreigabe nicht belegt | Äußeren Nahbereich, diagonale Ecken, Blindsektoren, Nullwerte und Mindestreichweite gezielt prüfen |

Werks-URDF, aus Scanabgleich gelernter relativer Versatz, Schätzung und direkte
Messung erhalten getrennte Quellenkennzeichen. Unbekannt bleibt „offen“, niemals
0 mit vermeintlicher Genauigkeit. Ein gesetztes `scan_einbau_quelle=gemessen`
ersetzt keinen Messbeleg. Auf RM02 gefundene Versätze nicht auf RM01 übertragen.

Der aktuelle planare Produktvertrag verwendet x/y und **genau eine** Drehung:
`p_basis = R(-scan_front_deg) * p_sensor + (x,y)`.
`scan_front_deg` bezeichnet den Sensorwinkel der Robotervorderrichtung; es ist
nicht zusätzlich als positive yaw-Drehung einzusetzen. Schon in `base_link`
gelieferte Scans verlangen Nulltranslation und `scan_front_deg=0`.
z/roll/pitch und Messunsicherheit sind in diesem Parametervertrag keine eigenen
Kalibrierfelder. Sie bleiben trotzdem erforderliche Mess-/Eignungsnachweise;
eine geneigte oder ungeklärte Messebene darf nicht still als horizontal gelten.
Die Konfiguration bestätigt weder Unsicherheitsmargen noch vertikale Abdeckung.

Synthetisches Beispiel, **keine Gerätemaße**: Ein Sensor an einer Hüllkante mit
positiver Mindestreichweite kann unmittelbar außerhalb der Hülle einen blinden
Streifen haben. Liegt derselbe Ort im Blindsektor der zweiten Quelle, belegen
auch zwei gültige Fernscans dort keinen Freiraum. Keine Hülle vergrößern, keine
Null-/Inf-Werte als frei behandeln und keine Pflichtquelle entfernen, um diese
Lücke zu umgehen. Eine verbleibende äußere Blindzone erfordert eine nachgewiesene
Montage-/Sensorlösung.

## #67: Prüfkopf für jeden tatsächlichen Stand

Diese Vorlage führt keine Installation oder Geräteaktion aus. Die vorhandene
private Morgenanleitung bleibt der Einstieg für das Geräteteam; diese Datei ist
das allgemeine Nachweisschema, kein zweiter Installationsablauf.

Vor der statischen Etappe prüfen: #60–#65 und #79 am verwendeten Stand integriert,
aktuelle CI und nativer Review zugeordnet, #66 für den tatsächlich verwendeten
Bezug ausreichend bestätigt. Fehlende Voraussetzungen explizit als blockiert
eintragen. Vor einem bewegten Teilversuch zusätzlich gesicherten Aufbau,
Beobachter/Bediener, Isolation fremder Fahrpublisher, STOPP-Möglichkeit,
zulässige Geschwindigkeit, Haltweg und Reaktionsgrenzen ausdrücklich festlegen.
Offene Grenzen erlauben keinen bewegten Versuch.

| Feld im privaten Prüfkopf | Eintrag vor Durchführung |
|---|---|
| Identität / Datum / Prüfer / Beobachter | offen |
| Installierter voller SHA / sauberer Baum / Prozessneustart | offen; SHA aus installiertem Checkout, Prozessbezug getrennt bestätigen |
| Effektive lokale Konfiguration und Kalibrierbeleg | offen; Version/Hash und Overrides von KI/Linienfolger einschließlich Pflichtquellen, Frames, Winkel, Hülle, Schutzschalter |
| Zeitbezug | offen; ROS-Uhr, monotone Empfangszeit, Synchronisation und Messunsicherheit; keinen gemeinsamen Uhrbezug voraussetzen |
| Aufbau / Fahrstellung / Zielkörper | offen; Abmessungen, Höhe, Material, Lage und Abstand zur äußeren Hülle |
| Grenzen / Wiederholungen / Abbruchbedingungen | offen; vor bewegter Etappe verbindlich festlegen |
| Aufzeichnung | offen; Scans/Frames/Header, Haltegrund, Fahrwunsch, endgültiger Ausgang und unabhängige Bewegungsbeobachtung zeitlich zuordnen |

## Konkrete Ausfallmatrix

Alle Zeilen sind **vorbereitet/offen**, nicht durchgeführt. Pro Zeile und
Wiederholung den Prüfkopf samt installiertem SHA referenzieren und das unten
definierte Ergebnisblatt ausfüllen. Quelle A/B sind Platzhalter für die beiden
privat bestätigten Pflichtquellen. Bei einzelnen Quellenfehlern die jeweils andere
Quelle gültig/frisch halten, um den Pflichtkanalfehler isoliert zu prüfen.
Gültig/frisch bedeutet dabei nicht, dass diese Quelle jede benötigte Zelle frei
misst. Für Abdeckungsfälle zählt das gemeinsame Messfeld: Eine von einer Quelle
gemessene freie Zelle kann die Blindzone der anderen abdecken; beide Pflichtkanäle
müssen weiterhin gültig/frisch sein. Statische Fehlerfälle nur im isolierten
Prüfaufbau ohne Fahr-/Armbefehle erzeugen; keinen Test-Publisher an einen aktiven
Motorweg anschließen. Eine Ausgangsmessung in einem getrennten Softwareaufbau
als solche kennzeichnen.

| ID / Etappe | Fehler oder Kontrolle | Erwartete Bewertung / endgültige Fahrkommandoausgabe |
|---|---|---|
| S01 statisch | Beide Quellen frisch, korrekt zugeordnet, belegter freier Prüfbereich | Kein LiDAR-Fehler; allein dadurch kein Fahrbefehl und keine Motorfreigabe |
| S02 statisch | Quelle A vollständig 0, NaN, Inf oder leer; dann separat B | Unverwertbar/unbekannt; bei einem später gesondert geprüften Fahrwunsch Nullvektor |
| S03 statisch | A fehlt seit Start; separat B; danach beide | Pflichtquelle fehlt, Halt; gültiger anderer Kanal ersetzt sie nicht |
| S04 statisch | A empfängt nicht mehr; separat B; andere Quelle bleibt frisch | Nach effektiver Altersgrenze unbekannt/Halt; Zeitpunkt des letzten gültigen Empfangs aufzeichnen |
| S05 statisch | Frisch empfangen, Header alt, null, zukünftig; jeweils A/B | Aufnahme ungültig/alt, Halt trotz frischem Empfang |
| S06 statisch | Doppelte bzw. rückläufige Header; Uhrsprung | Keine künstliche Frische; gültigen Fortschritt und Ablauf der bisherigen Aufnahme getrennt beobachten |
| S07 statisch | Falscher/leerer Frame, unbekannte/widersprüchliche Pose oder Quellenliste | Kein geometrischer Freiraumnachweis; Halt statt Ersatzpose |
| S08 statisch, negative Kontrolle | Beide Kanäle frisch/gültig mit gültigen Punkten neben dem Fahrbereich; dieselbe benötigte Zelle im Fahrbereich bzw. äußeren Nahbereich wird von keiner Quelle gemessen | Gemeinsame Abdeckungslücke bleibt unbekannt und hält; globale Gültigkeitsquote reicht nicht |
| S08+ statisch, positive Gegenkontrolle | Beide Kanäle frisch/gültig; eine Quelle ist für dieselbe benötigte Zelle blind, die zweite misst diese Zelle vollständig frei; übriger benötigter Bereich ebenfalls gemeinsam frei gemessen | Keine zusätzliche Abdeckungssperre wegen der Blindzone der einzelnen Quelle; übrige Schutz- und Freigabebedingungen bleiben erforderlich |
| S09 statisch | Bekanntes Ziel vor/hinter der Hülle innerhalb und außerhalb des relevanten Bereichs | Transformation/Seite korrekt; innen Hindernishalt, außerhalb kein falscher Hindernisbeleg; übrige Freigabebedingungen weiter nötig |
| S10 statisch | Ziel bei Seitwärtsfahrt/Drehung/Abbiegebogen an äußerer Ecke | Gesamte überstrichene Hülle prüfen; kritischer Treffer oder Lücke hält den betreffenden Vektor |
| S11 statisch | Fehler entfernt, gültige frische Daten kehren zurück | Datenfehler darf erst nach vollständiger erneuter Prüfung entfallen; keine START-/STOPP-Sperre allein dadurch lösen |
| M01 gesondert bewegt | Langsame Vorwärts-/Rückwärtsfahrt, bekanntes Ziel im geprüften Bereich | Endgültig `(vx,vy,wz)=(0,0,0)` bei Schutzfall; realen Stillstand und Restweg separat messen |
| M02 gesondert bewegt | Jeweils einzelner Pflichtkanal fällt aus/altert; beide aus | Nullvektor nach Fehlererkennung; reale Haltlatenz einschließlich Ausfallerkennung messen |
| M03 gesondert bewegt | Seitwärts-/Dreh-/Kurvenwunsch gegen Ziel/Ecke | Konkreter Vektor gesperrt; kein Vorwärtssektor als Ersatz; tatsächliche Translation und Drehung enden |
| M04 gesondert bewegt | Niedriges Ziel unter LiDAR-Ebene / außerhalb Kamerasicht | Gesamten verfügbaren Schutz prüfen; Ausbleiben eines LiDAR-Treffers ist keine Freigabe. Fehlender Nachweis blockiert betroffenen Betrieb |
| M05 gesondert bewegt | Bedien-STOPP; separat Fahrprozess-/Senderausfall | Tatsächlicher Halt, Board-/Watchdogwirkung separat erfassen; fehlende Nullpublikation bei Prozessausfall ausdrücklich protokollieren |
| M06 gesondert bewegt | Ziel entfernt bzw. Sensor kehrt zurück, danach STOPP-Fall | Kein Wiederanlauf allein durch Timer/Grün/Sensorwiederkehr nach STOPP; erst bewusster Start und neue vollständige Schutzprüfung |

Die derzeitigen Software-Altersgrenzen (siehe [LiDAR-Modul](../../lib/lidar.py))
sind Konfigurations-/Implementierungswerte, **keine gemessene sichere Haltlatenz**.
Für statische Fälle bleibt die reale Haltzeit „nicht gemessen“; sie darf weder aus
einem Nullbefehl noch aus einer erfolgreichen Publisherattrappe abgeleitet werden.
Ein Datenfehler kann nach gültiger Rückkehr entfallen; ob der installierte Stand
dabei unzulässig erneut fährt, muss im Wiederanlauffall tatsächlich geprüft werden.

### Statische Etappe mit `scripts/lidar_standpruefung.py`

Das Werkzeug führt durch die statischen Fälle, liest nur `/line_follower/status`
und `/ki/befehl` und schreibt den versionsbezogenen Bericht
`docs/abnahme/<Gerät>-lidar-halt-<Datum>.md`. Frühere Berichte werden nie
überschrieben; Rohdaten landen privat in `config/lokal/lidar_standpruefung/`.
Es sendet keine Fahr-, Arm- oder Parameterbefehle.

```bash
# Linienfolger im TESTMODUS (Panel -> TEST) und KI laufen, "KI darf den Arm bewegen" AUS
source scripts/env.sh
python3 scripts/lidar_standpruefung.py --geraet RM01 --pruefer "Name" --beobachter "Name"
```

Läuft der Linienfolger mit `drive=true` oder darf die KI den Arm bewegen, bricht
das Werkzeug ab. Je Fall bewertet es nach einer Einschwingzeit von 2 s, ob der
LiDAR-Haltegrund **durchgehend** vorliegt (bzw. fehlt), ob der rechnerische Befehl
dabei 0 ist und ob der Grund die erwartete Quelle oder Ursache nennt. Die Zeit bis
zum ersten Halt zählt ab der Bestätigung durch die prüfende Person und enthält die
Bedienzeit. Sie ist **keine** Motor-Haltzeit.

| Abgedeckt | Fälle im Werkzeug |
|---|---|
| S01, S02, S03, S04, S07, S08, S09, S11 | S01, S02a/b, S03, S04a/b, S07, S08, S09a–d, S11a–c |

Nicht abgedeckt, im Bericht also nicht enthalten, bleiben offen:

- **S05/S06** (alter, zukünftiger oder rückläufiger Header): Sie brauchen einen
  isolierten Test-Publisher ohne Motorweg; am Gerät gesondert planen.
- **S08+** (positive komplementäre Abdeckung): braucht eine gezielte Abschattung
  nur eines Sensors.
- **S10** (Seitwärts/Drehung): Im Testmodus wird nur der Bereich der eingestellten
  Fahrtrichtung geprüft.
- **M01–M06**: stehen immer als „nicht durchgeführt“ im Bericht.

Ein Fall, der sich am Gerät nicht herstellen lässt, wird mit `s Grund` als
„blockiert“ eingetragen und nicht geschätzt.

## Ergebnisblatt je Fall und Wiederholung

| Nachweisfeld | Auszufüllender Inhalt |
|---|---|
| Fall-ID / Datum / installierter SHA / Prüfkopf | offen |
| Soll / Ist Sensorzustand und Haltegrund | offen; Fehlerbeginn und letzte gültige Aufnahme/Empfang getrennt |
| Gewünschter Fahrvektor | offen; vx/vy in m/s, wz in rad/s, Quelle und Zeitpunkt |
| Endgültige ausgegebene Kommandos | offen; gemessener Ausgang mit Zeitbezug, alle drei Komponenten, konkurrierende Sender; kein KI-Wunsch als Ausgang ausgeben |
| Tatsächlicher Halt | nicht gemessen; unabhängige Methode, Stillstandskriterium, Translation/Drehung und verbleibender Abstand |
| Latenzen / Weg | nicht gemessen; Fehlerbeginn → Erkennung → erster Nullbefehl → realer Stillstand; Restweg und Zeitunsicherheit je Messung |
| Wiederanlauf | nicht geprüft; Rückkehr gültiger Daten, Freigabezustand, bewusster START falls nötig, tatsächlicher Anlauf und erneute Hindernisprobe |
| Ergebnis / Beleg | offen; bestanden / nicht bestanden / blockiert, private Beleg-ID und verantwortliche Person |

Unterschiedliche Uhren nur mit dokumentierter Zuordnung und Unsicherheit
verrechnen. Bei Prozessausfall kann der erste Nullbefehl fehlen: dann „keiner
beobachtet“ eintragen und Hardware-Halt getrennt messen. Messgrenze statt erfundener
Nullzeit angeben. Ohne ausreichende Zeitauflösung keine präzise Latenz behaupten.

Abbrechen und bewegte Folgefälle sperren bei Bewegung trotz STOPP/TEST,
Nichtnullausgang trotz bestätigtem Schutzfall, fehlendem tatsächlichem Halt,
überschrittener vereinbarter Grenze, unklarem Frame/Zeitbezug, äußerer Blindzone,
Kontakt oder unkontrolliertem Wiederanlauf. Ursache, Rücksprung und Wiederholbedarf
protokollieren; Schutz nicht zur Fortsetzung abschalten.

Öffentlich nur bereinigte allgemeine Ergebnisse mit Software-SHA, Fall-ID,
Status und synthetischer Reproduktion ergänzen. Lokale Einzelmesswerte,
Rohaufnahmen sowie Geräte-/Netz-/Zugriffsdaten bleiben privat. #66/#67 bleiben
bis zum vollständigen tatsächlichen Nachweis und seiner Lieferung offen; RM02
und #37/#41/#42 sowie die A01–A16-Gesamtabnahme werden dadurch nicht abgeschlossen.
