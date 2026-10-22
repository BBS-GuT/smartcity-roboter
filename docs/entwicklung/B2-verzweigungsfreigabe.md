# B2: Geometrie, Erlaubnis und festgehaltene Ausfahrt

Vertragsentwurf für [#85](https://github.com/BBS-GuT/smartcity-roboter/issues/85),
Stand 22.10.2026. Grundlage: GB-05/06/07/09/13, #86 und
[E1-Verkehrsregeln](../infrastruktur/E1-verkehrsregeln.md).
Keine Straßenkarte, reale Infrastrukturfreigabe oder öffentliche C1-/ROS-/MQTT-Nachricht.
Annahme durch die Orchestrierung und exakter Vertragscommit werden in #76/#85
verlinkt; erst diese Annahme erlaubt die Umsetzung von #86.

## Interner Eingabe- und Ergebnisvertrag

Der reine Automat erhält unveränderliche lokale Datensätze; ein vorgeschalteter
Verbraucher muss ihre Herkunft prüfen. Er bestimmt weder Knoten noch Signale aus
Bildern. Die gerichtete B2-Regelkarte mit bestätigten E1-Regeln bleibt fachliche
Autorität. Auf der Startbasis `dc6acc25` existiert noch keine implementierte,
freigegebene gerichtete Regelkarte und keine reale Knoten-/Zufahrtsbrücke.
`lib/karte.py` ist eine geometrische Belegungskarte und ersetzt diese nicht.

| Feld | Bedeutung und Gültigkeit |
|---|---|
| Bezug | Gerätekennung, eindeutige Startkennung, Quellen-/Belegkennung einschließlich Karten-/Regelversion, bestätigter Knoten, bestätigte eigene Zufahrt, eindeutige Anfahrtkennung. Alle sind nichtleere interne Kennungen; synthetische Kennungen nur im Test. |
| Beobachtung | Monoton steigende Sequenz, lokale monotone Aufnahmezeit und explizite Gültigkeitsdauer. Endliche Zeitwerte; Zukunft, überschrittene Gültigkeit, rückläufige Sequenz oder abweichender erwarteter Geräte-/Start-/Quellenbezug sperren. Duplikate erneuern keine Frische. |
| Geometrie | Menge stabil zugeordneter sichtbarer Ausgangskennungen, getrennt von Erlaubnis; nur bestätigte Verzweigung, kein Überwegquerbalken. Die Zuordnung Ausgang zu Bildast muss eindeutig sein. |
| Erlaubnis | `None` bedeutet unbekannt; sonst die für genau diesen Bezug bestätigte Menge nach Regelkarte und Beschilderung, auch leer zulässig. Einfahrtsfreigabe wird separat geprüft. Geometrie ist kein Erlaubnisbeleg. |
| Einfahrt | Separate aktuelle passende Signal-/Infrastrukturfreigabe und positiv bestätigtes Einfahrtereignis mit identischem Bezug und gewähltem Ausgang. Vor Einfahrt sperrt unbekannte/rote Freigabe. Das bestätigte Ereignis bindet die erteilte Räumfreigabe bis zum Abschluss. |
| Historie | Eigene lokale Besuchszähler je Quellen-/Kartenversion, Knoten, Zufahrt und Ausgang; nur bestätigte Abschlüsse zählen. Gültig leer ist bekannt; unbekannte/ungültige Historie wird als `historie_unbekannt` gehalten, nicht als leere Liste ersetzt. |
| Abschluss | Separates positiv bestätigtes Ereignis mit identischem Bezug, gewähltem Ausgang, neuer Sequenz und frischem Zeitbezug. Nachweis der tatsächlichen Ausfahrt/neuen Spur durch bestätigte Wahrnehmung und gemessenen Fortschritt; kein Timeout, Bildzähler oder Fahrbefehl als Ersatz. |
| Ergebnis | Lage `bereit`, `gewaehlt`, `raeumen`, `halt` oder `abgeschlossen`, festgehaltener Ausgang (gegebenenfalls trotz Halt) und konkreter Diagnosegrund. Ausschließlich interner Fahrwunschbezug, niemals Motorfreigabe. |

Der erwartete Geräte-/Start-/Quellenbezug wird bei Erzeugung des Automaten
explizit übergeben. Knoten/Zufahrt/Anfahrt müssen zusätzlich als bestätigt gelten.
Quelle unbekannt, Bezug ungültig, Beobachtung veraltet, Erlaubnis unbekannt,
zulässige Schnittmenge leer, gewählter Ausgang verloren/verboten und falscher
Abschluss sind unterscheidbare Haltgründe. Ein gültiges leeres Erlaubnisresultat
ist kein Transportfehler. Die Gültigkeitsdauer ist eine vom bestätigten
Produzenten gelieferte Grenze, kein hier erfundener Geräteparameter.

## Zustandsregeln

1. Nur bei gültigem bestätigtem Anfahrtsbezug wird aus
   `Geometrie ∩ Erlaubnis` gewählt. Ein Ausgang ist eindeutig; mehrere werden mit
   eigenem injizierbarem Zufallszustand aus stabil sortierter Menge gewichtet
   gewählt: Gewicht je Ausgang `1 / (1 + bestaetigte_Besuche)`.
   Alle erlaubten Ausgänge bleiben möglich, selten befahrene werden bevorzugt.
   Der Automat initialisiert seine eigene Historie beim bekannten neuen Start
   ausdrücklich gültig leer, ohne alte Besuche oder Persistenz zu behaupten.
   Nicht initialisierbare oder unpassend zugeordnete Historie hält.
   Identischer Seed und gleiche Eingabefolge ergeben dieselbe Auswahlfolge.
2. Pro Anfahrt höchstens ein Zufallszug. Gleiche Bilder, Duplikate, Erkennungslücken
   und Wiederkehr desselben Knotens lösen keine Neuwahl aus. Bei Erkennungslücke
   bleibt die Wahl gespeichert und die Fahrt hält. Ein fehlender gewählter Ast
   wird nicht durch einen anderen sichtbaren Ast ersetzt.
3. Entfällt seine Erlaubnis oder wird die Zuordnung ungültig, bleibt die Wahl
   gespeichert, mit Haltgrund. Wieder gültige Daten dürfen dieselbe Wahl
   bestätigen, niemals heimlich eine andere wählen. Ein anderer Anfahrtsbezug
   vor passendem Abschluss wird als Konflikt gehalten.
   Die Einfahrtsfreigabe ist davon getrennt: vor der Einfahrt sperrt Rot oder
   unbekanntes Signal. Erst das frische passende bestätigte Einfahrtereignis
   setzt die Lage `raeumen`; ein späterer Signalwechsel allein hält diese
   Querung nicht an und entfernt ihre gebundene Räumfreigabe nicht. Ohne
   positiven Einfahrtnachweis wird dieser Zustand niemals angenommen.
4. Nur ein frischer passender positiver Abschluss beendet die Bindung. Danach
   erzeugt der alte Anfahrtsbezug keine neue Wahl; erst eine neue bestätigte
   Anfahrt darf wählen, auch bei erneuter Fahrt durch denselben Knoten.
   Neustart löscht keine verlässlich rekonstruierbare Querung: ohne neue
   bestätigte Zuordnung gibt es keine Fortsetzungsfreigabe.
   Jeder passende Abschluss erhöht den eigenen Besuchszähler genau einmal;
   Duplikate, Auswahl und Einfahrt allein verändern die Historie nicht.
   Karten-/Quellenwechsel braucht einen neuen ausdrücklich initialisierten
   Automaten; keine stillschweigende Übernahme inkompatibler Besuchszähler.
5. STOPP, Hindernisse, fehlende Pflichtdaten und Armschutz bleiben
   im bestehenden Fahrweg übergeordnet. Sie löschen die Auswahl nicht.
   Rot sperrt die Einfahrt, nicht allein die bereits bestätigte Räumung.
   Ein Überweg allein erzeugt keine Auswahl; während gebundener Querung ist
   fehlende Verzweigungserkennung weiterhin kein Abschluss.

## Vier synthetische Beispiele

1. Testbezug `test-geraet/test-start/test-regel`, Knoten `test-X`, Zufahrt
   `test-S`, Anfahrt `test-1`: sichtbar `{A,B,C}`, erlaubt `{A,C}`. Wahl nur A
   oder C; Bildduplikat hält denselben Ausgang ohne weiteren Zufallszug.
2. Gleicher Bezug: sichtbar `{A,B}`, erlaubt `{A}`. B bleibt trotz Sichtbarkeit
   verboten. Wird A später verboten, Halt mit gespeicherter Wahl A, keine Wahl B.
3. Unbestätigter Knoten ergibt `bezug_ungueltig`; bestätigter Knoten mit
   Erlaubnis `None` ergibt `erlaubnis_unbekannt`; bestätigte leere Schnittmenge
   ergibt `keine_erlaubte_ausfahrt`. Alle halten ohne neue Wahl.
4. Auf Wahl A folgen Erkennungslücke und falscher Abschluss B: Halt, Bindung A
   bleibt. Frischer bestätigter Abschluss A beendet `test-1`. Dessen Duplikat
   wählt nicht neu; erst bestätigte Anfahrt `test-2` erlaubt eine weitere Wahl.

## Offene Freigabebrücke und Übergangsentscheidung

E1 #5 liefert bislang Konzeptdaten, keine bestätigten realen Marker, Zufahrten,
Signal-/Schild-/Überwegregeln oder Gegenverkehrsfreigaben. Diese Lücke bleibt
offen; weder die Konzepttabelle noch erkannte Astwinkel werden zu Erlaubnissen.
Ein späterer lokaler Adapter muss genau diese belegte Zuordnung und einen
positiven Ausfahrtnachweis liefern. Ohne ihn hält strikte B2-Wegwahl am Knoten.

Die dokumentierte Projektinhaberentscheidung in #106 und
[PR #101](https://github.com/BBS-GuT/smartcity-roboter/pull/101#discussion_r4336891445)
erhält vorläufig geometrische Zufallswahl ohne Einbahnfilter. Sie ist ausdrücklich
keine Erfüllung von GB-05/09. Die Orchestrierung hat für diese Lieferung
entschieden, die normale Übergangsfahrt zu erhalten und ohne echte Quelle
keinen Modusschalter oder Scheinadapter einzubauen. Tatsächliche Integration
bleibt datenblockiert unter #106. Der strikte Automat selbst kennt keine Freigabe
durch diese Übergangsregel und keine MQTT-Fernfahrbefehle.
