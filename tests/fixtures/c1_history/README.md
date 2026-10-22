# C1l-Modullieferung #153

Nur synthetische Eingaben, keine echte Karte oder Fahrt.
Basis der Vorbereitung: `3bccdab47615001b3cfdfccf756ee98ccadea37f`.
Fundamentbasis #151 `1a90143f98c0d78c7bb7b944e5facb8a6b285de1` wurde normal
übernommen. Eigene Implementierung ausschließlich `lib/c1_fahrhistorie.py`;
gemeinsame Vertragsdateien bleiben bis Adapterfreigabe unberührt.

## Implementierter Moduleinstieg und geplanter Fassadenanschluss

`pruefe_historie(history, *, robot_id, map_version, time_basis_id,
generated_mono_s, kontext=None, vorher=None)` liefert eine Fehlerliste ohne
Mutation. Modul und Kontextbelegung bilden die begrenzte Modullieferung,
noch keinen integrierten Gesamtvertrag. `pruefe`, `als_json` und `lade_json`
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

Der Aufrufer behält den letzten bestätigten B-Snapshot auch während fehlender
C-Übernahme und ersetzt ihn nicht durch einen C-Zustand ohne B-Nutzdaten.
Bekannte Erfassungslücken können zusätzlich über `binding.capture_gap=true`
übergeben werden; sie erlauben ausschließlich invalid/capture_gap im selben
Start. Ohne vorherigen Snapshot oder übergebene Lückeninformation kann eine
zustandslose Funktion keine vergangene Erfassungslücke erkennen. Ein expliziter
neuer Historienstart wird im Vergleich zunächst mit leerem Puffer bestätigt;
spätere Abschlüsse vergleichen gegen diesen neuen bestätigten Snapshot.

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

Der frühere reine Vorbereitungsstatus und seine rote API-Probe stehen unten
als Vorher-Nachweis. Jetzt existiert das eigenständige Modul; Fassaden-, Schema-
und Gesamtfixtureintegration bleiben ausdrücklich offen bis Adapterfreigabe.

Schemaübergabe: `c1_fahrhistorie.SCHEMA_DEFS` ist ein JSON-fähiges Dictionary
mit `c1History` und `c1HistoryEntry`. Beide unverändert nach `$defs` übernehmen,
`route.history` referenziert `#/$defs/c1History`. Statische Pflicht-/Null-/Status-
und Kapazitätsregeln sind enthalten; Sequenzgleichung, ns-Exaktheit und externe
Karten-/Start-/Uhrenbindung bleiben ausdrücklich Python-Kontextregeln.

Tatsächlich ausgeführt: Windows/PowerShell7.6.5, eigene lokale venv mit
CPython3.14.7 ohne zusätzliche Pakete. Die normale venv-Erstellung scheiterte
bei ensurepip; `venv --without-pip` gelang und genügt für diese reinen
Standardbibliothektests. Drei Fixturekontrollen bestanden, keine Skips.
Eine gezielte Positivkontrolle gegen die fehlende API scheiterte erwartbar mit
`C1l-API noch nicht implementiert/freigegeben`; kein grüner Produktnachweis.

Modullieferung: 32 eigene Tests einschließlich zwei wirklicher
Draft-2020-12-Schemaprüfungen bestanden; vollständige vorhandene C1-Sammlung
91 Tests und bestehende Vertragssuite20 Tests bestanden, insgesamt111 ohne
Skips. Ausgeführt mit bereits vorhandener Testumgebung
`C:/SmartCity/entwicklung/c1i-testenv/Scripts/python.exe -B`, keine Pakete
installiert und keine fremden Test-/Produktdateien geändert. Die anfängliche
eigene reine Standardbibliothekumgebung hatte bei der zusätzlichen alten
Empfangszeitsuite einen ausgewiesenen Schema-Skip; dieser ist durch die
abschließende vollständige Prüfung mit installiertem jsonschema ersetzt.
Keine ROS-/Geräteprüfung oder native Codeprüfung durch den Entwickler.
