# Gemeinsame LiDAR-Abdeckung

## Fehler und Verhalten

Zwei komplementäre Teilscans können gemeinsam einen Fahrbereich messen, obwohl
keiner den gesamten Bereich allein sieht. Die gemeinsame räumliche Prüfung ist
von der Pflichtquellenprüfung getrennt: **jede konfigurierte Quelle muss weiterhin
frische, gültige Messungen mit passender Aufnahmezeit liefern**.

Bei bestätigter Geometrie werden Messpunkte und freie Bereiche genau einmal in
`base_link` umgerechnet. Die KI prüft den geplanten Fahrbereich, der finale
Linienfolger-Haltpfad die äußere Fahrzeugfläche in der tatsächlichen Bewegungsrichtung.
Drehung prüft den gesamten umschriebenen Kreis. Die Überwegprüfung benutzt denselben
räumlichen Bezug. Panel-Sensoransicht und Kartograf werden nicht mitverschoben.
Diagonale Fahrt schließt die äußere überstrichene Ecke ein. Nach der Berechnung
wird das Alter genau der ausgewerteten Messungen erneut geprüft.

Ungültige Messwerte, Teilscan-Blindsektoren und der Raum hinter einem Treffer
werden nicht aufgefüllt. Eine Fläche wird in vollständige Zellen zerlegt; ein
ungültiger Strahl durch das Zellinnere kann sich nicht zwischen gültigen Ecken
verstecken. Jede Zelle muss vollständig von mindestens einer gültigen Quelle
gemessen sein. Die eigene Fahrzeugfläche wird ausgespart. Ein echtes Hindernis
im äußeren Schutzbereich hat Vorrang vor einer unbekannten Abdeckung.
Der frühere Nahkegel zum Ausblenden vermuteter eigener Teile entfällt in diesem
Pfad: Außerhalb der bestätigten Fahrzeugfläche zählt der ganze Fahrkorridor.
Die Vorschau reicht um die Fahrzeugfront über den Pfad der Fahrzeugmitte hinaus.
Die Rückraumprüfung liefert nur die tatsächlich belegte freie Strecke bis zur
ersten unbekannten Zelle oder zum ersten Treffer; ein entferntes Hindernis löscht
den davor gemessenen kurzen Rückweg nicht.

## Geräteeigene Parameter

Die folgenden Werte gehören nach Vermessung und Quellenbestätigung in die lokale
Gerätekonfiguration. Das Produkt enthält **keine** angenommene Gerätepose.

| Parameter | Inhalt |
|---|---|
| `scan_topics` | Liste aller Pflichtquellen |
| `scan_frames` | Erwarteter `header.frame_id`, in derselben Reihenfolge |
| `scan_front_deg` | Sensorwinkel, unter dem der Sensor die Robotervorderrichtung sieht; Drehung nur hier |
| `scan_einbau_xy` | `[x0, y0, x1, y1, ...]` in Metern, x vorne, y links |
| `scan_einbau_quelle` | Je Quelle `gemessen`; `werksmodell` allein gibt keine Fahrt frei |
| `fahrzeug_grenzen` | Vier **positive** Abstände von der Fahrzeugmitte: `[vorne, hinten, links, rechts]` in Metern |

Die Fahrzeuggrenzen müssen die ganze aktuelle Fahrstellung einschließlich Rädern,
Sensoren, Arm und Kamera einschließen. Ein bereits in `base_link` gelieferter Scan
braucht einen Nullversatz und `scan_front_deg=0`. Ein Sensorursprung außerhalb der
angegebenen Fahrzeugfläche ist ein Konfigurationsfehler. Ohne Geometrieangaben
bleibt die bisherige konservative Prüfung erhalten; teilweise oder widersprüchlich
gesetzte Angaben halten. Keine Einzelquelle oder Schutzfunktion entfernen, um
eine Konfiguration zum Fahren zu bringen.

Nach geänderten Geometrie-/Fahrzeugwerten Anwendungen neu starten. Während eines
Parameterwechsels dürfen keine Messfelder mit verschiedenen Bezugsrahmen zusammen
freigeben. Ein sehr großer oder leerer Prüfbereich gilt als unbekannt, nicht als frei.

## Was auch die Korrektur nicht als frei behandelt

Ein konstruktiv blinder Nahbereich außerhalb der Fahrzeugfläche bleibt unbekannt,
wenn ihn auch der zweite Sensor nicht misst. Die Korrektur garantiert daher keine
Fahrt allein aufgrund einer eingetragenen Geometrie. Das bloße Ausbleiben eines
Treffers ist kein Freiraumnachweis. Unbestätigte Treiberkodierungen wie `inf` werden
nicht als Freiraum interpretiert. Zielmessung, Softwaretest und Gerätefreigabe sind
verschiedene Nachweise.
Insbesondere kann ein Sensor direkt an einer Fahrzeugkante einen blinden Bereich
außerhalb der Hülle innerhalb seines `range_min` hinterlassen. Auch ideale, gültige
Fernmessungen schließen diese Lücke nicht. Die Fahrzeughülle darf deswegen nicht
größer eingetragen werden als tatsächlich gemessen.

## Standtest vor dem Fahrversuch

1. Installierten Commit, sauberen Arbeitsbaum und tatsächlich neu gestartete
   Anwendungsprozesse dokumentieren; richtige Quellen/Frames/Geometrie bestätigen.
2. Im Stillstand frische Daten beider LiDARs und gültige Aufnahmezeiten prüfen.
   Unbekannte Zeit-/Geometrie-/Restabdeckungsgründe zuerst klären.
3. Einen bekannten freien Prüfbereich sowie ein reales Hindernis in der
   vorgesehenen Fahrtrichtung prüfen. Das Hindernis muss weiterhin halten.
4. Fehlende bzw. veraltete Pflichtquelle und falschen Frame in Softwaregegenproben
   prüfen; Softwaretests veröffentlichen keinerlei Aktuatorbefehle.
5. Erst nach geklärtem Standcheck den separat betreuten Fahrversuch durchführen.

Bezug: #169, #64, #66 und #79. Ein Software-PR ersetzt keine reale Geräteabnahme.
