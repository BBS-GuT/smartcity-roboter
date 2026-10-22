# B2: Kreuzungsnachweise und offene Geräteabnahme

Stand: 22.10.2026. Bezug: [#106](https://github.com/BBS-GuT/smartcity-roboter/issues/106),
GB-02/03/05/06/07/09/13 und A02/A04/A05/A06/A08. Diese Checkliste ist eine
Vorbereitung ohne Gerätezugriff. Kein Feld gilt ohne konkreten Istbeleg als bestanden.

## Software, Übergangsregel und Erlaubnis

Die auf main integrierte geometrische Astwahl aus PR #101 ist eine vorläufige
Übergangslösung. Sichtbare Winkeläste belegen weder den Knoten und die eigene
Zufahrt noch eine erlaubte Ausfahrt. Die historische Entscheidung aus #106,
erst beim Schild „Einfahrt verboten“ zu wenden, erfüllt GB-05/09 nicht.
Die normale Ampel-, Überweg-, Hindernis- und Räumlogik bleibt für den
betreuten Fahrablauf erforderlich; der separate Fahrmodus aus PR #168
ersetzt sie nicht.

Ein strikter Erlaubnisvertrag und sein reiner Auswahlautomat brauchen als
Laufzeitvoraussetzung bestätigte Quellen für:

- Geräte-/Start-/Zeitbezug und fortschreitende Beobachtungen;
- Knoten, eigene Zufahrt und einen eindeutig abgeschlossenen Anfahrtsbezug;
- freigegebene gerichtete Regelkarte, zugeordnete Beschilderung/Freigabe
  und die daraus erlaubten Ausfahrten;
- Zuordnung der geometrischen Äste zu diesen Ausfahrten;
- positive, zum ausgewählten Ausgang passende Ausfahrtbestätigung.

Auf Ausgangs-main `dc6acc25e490edc301a6464af8fe19e17339aa42` existiert kein
solcher produktiver Quellenpfad. `docs/infrastruktur/E1-verkehrsregeln.md`
ist ausdrücklich ein offener Konzeptentwurf. `lib/karte.py` verwaltet
Belegung und lokale Geometrie. `lib/grundbetrieb_vertrag.py` und
`lib/c1_fahrhistorie.py` prüfen übergebene Daten; sie erzeugen keine
Straßenfreigabe. Der Linienfolger verarbeitet Bild und Gedächtnispose,
der KI-Fahrbefehl Aktion/Faktor/Manöver. Daraus darf keine Erlaubnismenge
erfunden werden. Eine tatsächliche Erlaubnis-/FSM-Fahrintegration bleibt
bis zur belegten Quelle und anschließend geprüftem Adapter offen.

## Kopf jedes Geräteprotokolls

Gerät, Datum/Uhrzeit und Prüfer/STOPP-Bediener eintragen. Vollständigen installierten
Commit, Anwendungsneustart, effektive lokale Konfiguration, Kalibrierbeleg,
Armfahrstellung, Kamerahöhe und gemessene beziehungsweise geschätzte Neigung
festhalten. Strecke/Aufbau, Licht, Tempo, erlaubte erreichbare Ausfahrten und
Aufnahmen-/Logablage benennen. Freigabe-/STOPP-/Hindernisnachweis muss zum selben
Gerät und Stand passen; RM01-Werte nicht auf RM02 übertragen.

## #111: ausdrücklich RM02

[#111](https://github.com/BBS-GuT/smartcity-roboter/issues/111) bleibt bis zur
tatsächlichen RM02-Abnahme offen. Frühere RM02-Fahrberichte in
`docs/problemprotokoll.md` und synthetische Tests sind kein Nachweis dieser
Matrix auf dem neuen Stand. RM01-Ergebnisse werden unter #106 geführt.

Jeden Geometriefall zunächst stehend betrachten und Originalbild plus Draufsicht
sichern. Betreute langsame Fahrt erst nach den aktuellen Sensor-/Haltprüfungen.
Nicht vorhandene Fälle als „nicht geprüft“ kennzeichnen.

| Fall | Soll | Ist / Aufnahme / Log |
|---|---|---|
| Gerade, enger Bogen | keine zufällige Kreuzungswahl | offen |
| T von unten | ausschließlich links/rechts; über mehrere Anfahrten beide Seiten dokumentieren | offen |
| Seitliche T links und Spiegelung rechts | nur vorhandene Äste; kein erfundener Gegenast | offen |
| Pluskreuzung | vorhandene Äste richtig; gewählten Ast tatsächlich fahren | offen |
| Kurze Haltelinie und Überweg | keine Wahl durch Querbalken | offen |
| Breiter Querbalken bis Bildrand | Mehrdeutigkeit durch zusätzlichen realen Kontext klären; keine reine Bildfreigabe | offen |
| Echter Abzweig neben Überweg | echten Ast erhalten; Überwegregeln weiter beachten | offen |
| Halt nach erfolgter Wahl | gleiche Wahl nach Halt/Wiederanfahrt, kein neues Losen | offen |
| Wiederholte/gleiche Bilder und Erkennungslücke | keine neue Wahl; fehlende Sicht bestätigt keine Ausfahrt | offen |
| Links/rechts 90 Grad, danach neue Spur | gewählter Ast bis hinter den Knoten; Ausfahrt anhand Bildfolge und Bewegung belegen | offen |
| Mehrere getrennte Kreuzungsfolgen | genau eine neue Auswahl je tatsächlich neuer Anfahrt | offen |
| Bildverarbeitung | Laufzeit je Bild mit Gerät/Last/Anzahl protokollieren; ca. 1 ms aus #111 ist eine Erwartung, kein Messwert | offen |

Mindestens Originalkamerabild, Linien-/Draufsicht vor/am/hinter dem Knoten,
Aufnahmezeit, Astliste/Wahl und zugehörige Bewegungs-/Haltezustände sichern.
Eine Logwahl belegt nur die Softwareentscheidung. Durchfahren, Spurtreue und
vollständige Fahrzeughülle sind gesondert zu beobachten. Dieselben fehlenden
Pixel können bei einer breiten Haltelinie und einer Kreuzung identisch sein;
eine weitere Schwelle ersetzt dann keine neue Information.

## #77: enge Kurven zuerst korrelieren

[#77](https://github.com/BBS-GuT/smartcity-roboter/issues/77) beschreibt am RM02
vom 21.10.2026 Richtungswechsel von ungefähr -25 auf +27 Grad und kurzzeitige
Abweichungen bis +7,3 cm. Die Ursache ist eine Hypothese: `Gedaechtnis.lokal()`
ergänzt bei zu wenigen nahen Vorwärtspunkten weiter entfernte Punkte;
`Lenkung.berechne()` verwendet daraus Krümmung, Richtung und Querabweichung.
Das Vorhandensein dieses Codepfads beweist nicht, dass er das reale Ereignis
verursacht hat. Weniger `quer_beschl` würde das Tempo begrenzen, aber die
Ursache ebenfalls nicht nachweisen. Deshalb keine unbelegte Regleränderung.

Für ein tatsächliches Kurvenereignis gemeinsam sichern:

1. Bildfolge/Panel-Linienbild mit Aufnahmezeit und sichtbar beobachteter
   Kurvenrichtung sowie Seite des Verlassens der vorgesehenen Spur.
2. Gedächtnispunkte beziehungsweise vorhandenen reproduzierbaren Replay,
   lokale Krümmung/Quer-/Richtungswerte und Vorhersageparameter.
3. Ausgegebenes Vor-/Drehkommando, gemessene Odometrie-/IMU-Bewegung,
   Quellenfrische, Bildalter, KI-Haltgrund und zeitgleiche Systemlast.
4. Ausgangsergebnis auf dem installierten Commit reproduzieren. Erst danach
   genau eine begründete Änderung gegen dieselben Daten prüfen; Gerade,
   andere Kurvenrichtung und Halt/Wiederanfahrt als Gegenkontrollen erhalten.

Der Standard-Simulationskurs hat keine Kreuzungen. Grüne Simulation und
synthetische Parabeln bestätigen weder echte RM01-/RM02-Kamerageometrie noch
die Ursache von #77. Der Nachweis bleibt bis zur zugeordneten Aufnahme offen.

## Abbruch und zusammenhängende Fahrt

Sofort anhalten bei fehlender/alter Pflichtquelle, falschem Frame/Bezug,
unbekanntem benötigtem Schutzbereich, wechselnder Wahl, verlorener Spur,
ungeklärter Ausfahrt oder Gefahr einer Berührung durch die gesamte Hülle.
Keine Suche außerhalb des bestätigten Fahrbereichs und kein Erweitern von
Grenzen für einen erfolgreichen Versuch. Eingriff/Umsetzen protokollieren;
ein solcher Lauf ist keine vollständige selbstständige Runde.

Ein betreuter RM01-Kurs braucht vorher geklärte tatsächlich erreichbare Äste.
Nach bestandenen Einzelprüfungen zusammenhängend vom markierten Start zurück
fahren: Gerade/Kurven, notwendige Kreuzungen, eigene Ampel, Überweg,
Hindernishalt, kontrollierte Wiederanfahrt und Bedien-STOPP prüfen. Bestehendes
Wegräumen nur mit eigenem aktuellen Geräte-/Armnachweis abnehmen. Commit und
Konfiguration zwischen Wiederholungen unverändert lassen, Neustartprobe
gesondert dokumentieren. Das ist keine Vierroboter-/GB-01–18-Gesamtabnahme.

## Issuezuordnung

#76/#84 wurden durch PR #101 softwareseitig geschlossen; ihr damaliger
Liefergegenstand ersetzt weder die fehlenden Erlaubnisdaten aus #85/#86 noch
die Geräteprüfung. #112 trägt Erkennung und ihre Informationsgrenzen,
#77 die korrelierte Kurvenursache, #111 die RM02-Abnahme. #106 bleibt für die
gesamte Kreuzungs-/Fahrintegration und deren reale Nachweise offen. Kein
gemischtes Geräteissue wird allein durch einen Softwaremerge abgeschlossen.
