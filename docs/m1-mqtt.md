# M1 im Fork: MQTT und gemeinsame Karte

Stand 22.10.2026. Der Nutzer hat MQTT als Transport für die Umsetzung im Fork
gewählt. Die formale Freigabe durch Projektinhaber und Brokerteam sowie die Abnahme
mit mindestens zwei realen Robotern sind offen. Die vorhandene Zieldefinition
für den Grundbetrieb bleibt unverändert: Fremddaten geben keine Motorfreigabe,
ersetzen keine lokalen Sensoren und überschreiben keine lokalen Haltebedingungen.

## Nachrichtenvertrag (#115, #116)

`schemas/m1-v1.schema.json` beschreibt die Hülle `m1/1`. `lib/m1_protocol.py`
prüft zusätzlich Semantik, Zeitfenster, Topic-/Brokeridentität, Startkennung und
Sequenz. Empfänger müssen dem tatsächlich authentifizierten MQTT-Client eine
Roboterkennung zuordnen; das Feld `geraet` allein ist kein Identitätsbeweis.
ACL: ein Roboter darf nur unter seinem eigenen Teilbaum schreiben. Zugangsdaten
werden lokal gesetzt und nicht ins Repository geschrieben.

Vorgeschlagene Topics, vorbehaltlich Brokerteam:

- `smartcity/m1/robots/RM01/position`
- `smartcity/m1/robots/RM01/intention`
- `smartcity/m1/robots/RM01/map_state`
- `smartcity/map/shared/<map_id>/<version>/...` für unveränderliche Kartenartefakte
- `smartcity/map/shared/current` als retained Zeiger auf die letzte vollständige Version

Jede M1-Nachricht enthält `schema_version`, `geraet`, `start_id`, `seq`,
`erzeugt_utc`, `karten_bezug` und `kind`. Positionen benötigen geprüfte Qualität;
unbekannte Lage wird nicht als genaue Position verbreitet. Eine neue Startkennung
beendet die vorige; Duplikate, rückläufige Sequenzen, zu alte und zukünftige
Nachrichten werden verworfen. Die Empfängerlaufzeit muss nach einem eigenen
Neustart ebenfalls den frischen Zeitstempel prüfen.

## Kartenverarbeitung (#117, #118)

`lib/m1_local_map.py` liest die bestehende `karte.npz` ohne Pickle und begrenzt
den Export. `lib/m1_map.py` richtet zwei Karten nur über mindestens drei
eindeutig benannte, nicht kollineare gemeinsame Marker aus. Maximal zulässig sind
3 cm Restfehler und 1° geschätzte Winkelunsicherheit. Fehlen solche Marker oder
ist das Muster mehrdeutig, gibt es keine bestätigte gemeinsame Karte. Diese
Marker müssen erst mit dem Projektteam auf dem realen Spielfeld bestimmt werden;
die bisherigen KI-Marker haben keine eindeutigen gemeinsamen IDs.

Die Fusion nimmt nur verifizierte Karten mit belegter Überlappung an, mittelt
statische Belegung und Bodenfarben, überspringt als dynamisch markierte Zellen
und verwirft stark widersprüchliche Überlappung. Die Qualitätswerte enthalten
Überlappungszellen, Konfliktquote und abgedeckte Zellen. Bei den bestehenden
`karte.npz`-Dateien sind Personen/Hindernisse nicht zuverlässig pro Zelle
markiert; deshalb muss vor einem realen Zusammenführen die statische Filterung
des Kartografen nachgewiesen werden.

## Veröffentlichung und Streckenhinweise (#119, #120)

`mqtt/m1_map_transport.py` erzeugt `occupancy.png` und `map.json` mit
Auflösung, Ursprung, Version, Quellen und Qualität. Dateien werden in Pakete
von höchstens 32 KiB geteilt. Erst nachdem alle Daten und das Manifest per QoS 1
bestätigt sind, wird `current` retained aktualisiert. Ein separater Empfänger
muss Hashes, Versionsbezug und Alter vor der Anzeige prüfen. Nach fünf Minuten
gilt ein retained Zeiger ohne frische Veröffentlichung nicht mehr als aktuell.
Nur die neueste wartende
Karte bleibt im Speicher; Fehler sind als `last_error` sichtbar. Die älteren
unveränderlichen Versionen benötigen auf dem Projektbroker eine abgestimmte
Aufbewahrungsregel.

Ein manueller Export aus zwei bereits aufgenommenen Karten lässt sich nach
Festlegung eindeutiger Marker ausführen:

```bash
python3 mqtt/m1_publish_map.py --map-id spielfeld-2026 \
  --reference-markers referenzmarker.json \
  --source RM01 rm01/karte.npz rm01-marker.json \
  --source RM02 rm02/karte.npz rm02-marker.json \
  --host BROKER-IP
```

Die drei Markerdateien enthalten JSON-Objekte mit gleichen festen IDs und
Koordinaten in Metern, zum Beispiel `{"K1":[0,0],"K2":[1,0],"K3":[0,1]}`.
Die Referenz muss auf dem Spielfeld bestätigt sein. Ohne sie bricht der Export
ab. Der Empfänger kann Manifest, Hashes und Version mit `verify_package()`
prüfen. Ein automatischer Upload aus dem laufenden Kartografen ist noch nicht
angeschlossen, weil dafür eine Freigabe des Kartenstandes und der statischen
Filterung fehlt.

`lib/m1_routes.py` wählt ausschließlich aus lokal bereits erlaubten Ausfahrten.
Bei fehlenden, alten oder unpassenden MQTT-Daten gilt die ursprüngliche lokale
Wahl. Frisch belegte oder kürzlich besuchte Abschnitte werden nachrangig gewählt.
Bei Konflikt erhält die kleinere Roboterkennung Vorrang. Ein Anschluss
an die echte N1-Navigation ist noch nicht möglich, weil deren freigegebene
Ausfahrten und Abschnitts-IDs nicht als Schnittstelle vorliegen. Die Funktion
sendet selbst keine Fahr- oder Stoppsignale.

## Abnahme (#121)

Die Softwaretests prüfen Identität, Replays, Alter, Kartenabgleich, Fusion,
Exportreihenfolge und Fallback. Noch offen sind ein Test mit zwei echten
Robotern in getrennten ROS-Domänen, die Projektbroker-ACL, identische
Abschnitts-IDs, nachgewiesene statische Kartenfilterung sowie Messungen von
Abdeckung und Wandfehler auf dem Spielfeld. Der Offlinebetrieb muss am echten
Fahrstack geprüft werden, bevor Streckenhinweise dort angeschlossen werden.

Lokal geprüft mit `py -m unittest tests.test_m1` und
`python3 mqtt/m1_integration_test.py` in der MQTT-Testumgebung. Der zweite
Test startet einen lokalen Broker und zwei unabhängige MQTT-Clients, lädt
alle Kartenteile über MQTT und prüft Manifest und Hashes. Er
ersetzt keinen Test mit getrennten echten ROS-Domänen.
