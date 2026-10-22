# C1l-Vorbereitung #153

Nur synthetische Eingaben und API-Plan, keine echte Karte oder Fahrt.
Basis der Vorbereitung: `3bccdab47615001b3cfdfccf756ee98ccadea37f`.
Gemeinsame Vertragsdateien bleiben bis zweiter Managerfreigabe unberührt.

## Vorgeschlagener API-Anschluss

`pruefe_historie(history, *, robot_id, map_version, time_basis_id,
generated_mono_s, kontext=None, vorher=None)` liefert eine Fehlerliste ohne
Mutation. Dieser Name und die Kontextbelegung sind ein konkreter Arbeitsplan,
noch keine akzeptierte öffentliche API. `pruefe`, `als_json` und `lade_json`
sollen später denselben optionalen `historie_kontext` und `vorher`-Bezug an die
Historienprüfung durchreichen. Keine abweichenden Python-/JSON-Gültigkeiten.
Die genaue Keyword-Integration wird nach #150/#152 an deren echten Stand
angepasst. Keine zweite JSON-/Zeitimplementierung: `zeit_ns` und
`sekunden_aus_ns` aus #149/#151 benutzen; derselbe exakte JSON-Pfad verarbeitet
auch `confirmed_mono_s`. Die Test-JSONs sind isolierte Teilobjekte und werden
nicht als gültige vollständige v2-Zustände ausgegeben.

## Expliziter Kontext

`context.json` enthält eine separat vom Kandidaten gelieferte synthetische
Produzentenbindung und gerichtete Karte. `binding` bindet Gerät, B-Produzent,
B-Historienstart und Geräte-Uhreninstanz; `initialized` bestätigt tatsächlich
initialisierte Erfassung. `map.sections` ordnet jede gerichtete Abschnitts-ID
einer Zufahrt, einem Zielknoten und dessen erlaubten Ausfahrten zu.
`confirmed_new_history_start` bestätigt ausdrücklich einen neuen B-Start;
bloße Änderung einer Zeichenkette im Kandidaten genügt nicht.

`vorher` ist ein expliziter vorheriger bestätigter Snapshot mit äußeren Geräte-,
Karten-, Uhren- und Erzeugungszeitwerten sowie `history`. Keine versteckte
globale Sammlung. Derselbe B-Start behält Eintragsidentitäten; ein reiner
C-Neustart ist kein Reset. Eine capture_gap bleibt im Vergleich invalid, bis
der Kontext einen neuen B-Historienstart bestätigt. Gegenproben verändern nur
den Kandidaten oder gezielt den extern gegebenen Kontext, niemals erzeugt der
Validator seine eigene Karte aus dem Kandidaten.

## Qualitätsbelegung im Plan

- valid: vollständige gebundene Identitäten, Grund null, Liste und Zähler;
  Sequenz für Index i exakt dropped_entries+i. Weniger als16 => Zähler0;
  positiver Zähler => genau16. Leer => Liste[] und Zähler0.
- missing: Grund vorhanden, entries/dropped_entries null; bekannte Herkunft
  bleibt erhalten, tatsächlich unbekannte Identitäten null.
- unknown: nicht belegter Kontext mit Grund, Nutzwerte null, bekannte Herkunft
  erhalten. Bloße Kennungstexte erlauben keinen valid-Anspruch.
- invalid: Widerspruch oder capture_gap/map_changed mit Grund, Nutzwerte null;
  ein ehrlicher Fehlerzustand ist ein zulässiger Datensatz. Der Validator
  lehnt dagegen die widersprüchliche Behauptung valid ab.

## Nach Freigabe noch anzuschließende Gesamtprüfungen

Die vorbereiteten Historienfälle prüfen Leer/Fehlend/Unknown, zwei Abschnitte,
16/17, Sequenz-/Zählerfehler, Zeittypen/Raster/Grenze, Ursprung/Uhr/Karte,
Erfassungslücke, bestätigten Reset, Karten-/Uhrwechsel und Herkunftserhalt.

Auf dem bestätigten Nachfolger von #149/#150/#152 zusätzlich echte vollständige
v2-Zustände über alle drei öffentlichen Einstiege prüfen: nur C-boot_id ändern
ohne neue Einträge; STOPP/TEST/Reconnect erhalten den B-Puffer; identische
Python-/JSON-Kontextentscheidung; Dezimal-/Exponententokens und Roundtrip ohne
Floatgewinn; Schema positiv/negativ ohne verdeckte Skips. Optionale Belege nur
mit den dann tatsächlich gelieferten Detailreferenzen aus #150: älterer
passender Beleg zulässig, fehlender Abruf löscht keine Fahrt, widersprüchliche
Referenz darf keinen gesicherten Abschluss vortäuschen. Keine Referenzstruktur
vorweg erfinden und keine bestehenden Tests/Fixtures bis Freigabe ändern.

Vorbereitungsstatus: Die Fixturekontrollen sind getrennt ausführbar. Die
Vertragstests bleiben ohne implementierte API sichtbar rot, ohne Skip oder
ExpectedFailure. Dies ist kein prüfbereiter Implementierungs-PR und kein
Annahmenachweis. Nach dieser Übergabe auf zweite Managerfreigabe warten.

Tatsächlich ausgeführt: Windows/PowerShell7.6.5, eigene lokale venv mit
CPython3.14.7 ohne zusätzliche Pakete. Die normale venv-Erstellung scheiterte
bei ensurepip; `venv --without-pip` gelang und genügt für diese reinen
Standardbibliothektests. Drei Fixturekontrollen bestanden, keine Skips.
Eine gezielte Positivkontrolle gegen die fehlende API scheiterte erwartbar mit
`C1l-API noch nicht implementiert/freigegeben`; kein grüner Produktnachweis.
