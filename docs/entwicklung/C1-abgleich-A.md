# C1: Fachlicher Datenabgleich A – Fahrfreigabe und Sicherheit

Stand: 22.10.2026. Verantwortlicher Mensch: Carsten; zugewiesene Fachrolle A
unter C1-Management. Refs [#3](https://github.com/BBS-GuT/smartcity-roboter/issues/3)
und [#134](https://github.com/BBS-GuT/smartcity-roboter/pull/134).
**Erste Phase: Annahme einer Entscheidungsgrundlage mit engen Ergänzungen.**
Dies ist keine menschliche Zustimmung anderer Rollen, keine Annahme eines
implementierten Gesamtvertrags und keine Gerätefreigabe. Codeprüfung bleibt
beim nativen Reviewer; hier wurden keine Anwendungscode-/PR-Diffs geprüft.

## Konkreter Bezug und Aussagegrenze

Eigene Basis: `e8863f6998391c9a3d9cc30af2711eb4d7c86a51`, tatsächlicher
`origin/feat/gb-c1-zustandsvertrag` beim Klonen. Branch `docs/c1-abgleich-a`;
exklusiv nur diese neue Datei. Andere Dateien bleiben bei ihren Besitzern.

| Fachliche Quelle | Gelesener Lieferhead / Einordnung |
|---|---|
| [Entscheidungsvorlage #142](https://github.com/BBS-GuT/smartcity-roboter/blob/f42202799396e5b71f378909eaf3a5863ef1e93f/docs/entwicklung/C1-vertragsentscheidungen.md) | `f42202799396e5b71f378909eaf3a5863ef1e93f`; V1–V4 einschließlich V1a und Anti-Replay-Ergänzung sind Grundlage dieses Abgleichs. |
| [C1e #130](https://github.com/BBS-GuT/smartcity-roboter/blob/ff4c0d78beee1eeae40fdd0597d0c32c0fc7e644/docs/entwicklung/C1e-detailreferenzen.md) | `ff4c0d78beee1eeae40fdd0597d0c32c0fc7e644`; offen, beim Start nicht im Sammelbranch. |
| [C1f #132](https://github.com/BBS-GuT/smartcity-roboter/blob/e1d6185e6878a304afa2681285be20342339e468/docs/entwicklung/C1f-fahrwunsch-identitaet.md) | `e1d6185e6878a304afa2681285be20342339e468`; als Entwurf im Sammelbranch, keine Laufzeitannahme. |
| [C1g](C1g-fahrhistorie.md) / [#131](https://github.com/BBS-GuT/smartcity-roboter/pull/131) | `3a8b81bc3e06eaceb77c3628aee874ee7d069197`; als Entwurf im Sammelbranch. |
| [C1h](C1h-raeumzustand.md) / [#128](https://github.com/BBS-GuT/smartcity-roboter/pull/128) | `46cd940b973fd55c92d9ccff75bcbf12ff26f097`; als vorläufiger Entwurf im Sammelbranch. |

Gelesen: AGENTS/CONTRIBUTING, [gemeinsame Regeln](../auftraege/00-gemeinsame-regeln.md),
[Register](../auftraege/README.md), [C1-Auftrag](../auftraege/C-zustand-mqtt-und-panel.md),
Entwicklungsplan, [Zieldefinition](../zieldefinition-grundbetrieb.md) v1.0/02.10.2026,
bestehende Vertragsdokumentation sowie aktuelle Issues #3, #8 und #11–#18.
GB-12–18 und A11–15 sind Prüfbezüge; A02/A03/A06 sind ergänzende Bezüge,
keine hier bestandenen Abnahmen. Die bestätigte Räumerlaubnis aus #8 gilt;
die alten Ausschlüsse in §2.2/§4.1/A03 benötigen weiterhin Zielharmonisierung.

## V1/V1a: Identitäten, Quellen und exakter Zeitpfad

Aus A-Sicht zur Implementierung angenommen: Zustandsidentität
`(robot_id, boot_id, seq)` gehört C; Ursprungsdaten führen unabhängig
`producer_id`/`producer_boot_id`. Die belegte lokale Geräteuhr führt
`time_basis_id`, einschließlich Ursprung, Uhrtyp und Suspendverhalten.
Ein Prozessstart ändert die Uhreninstanz nicht automatisch. Reiner C-Neustart
übernimmt unveränderte Sensor-, Request-, Historien- und Vorgangsidentitäten;
bis dahin `missing`, keine neue Aufnahme und keine erfundene leere Historie.
Das verhindert scheinbar neue Herkunft oder Frische nach Aggregatorneustart.

`source` ist ausschließlich ein registrierter `sensors`-Schlüssel; technische
Quelle `source_id`, Framekennung und räumlicher `coord_frame` sind verschieden.
Für belegte vergleichbare Zeiten gilt
`0 <= captured_mono_s <= received_mono_s <= generated_mono_s`.
Alter entsteht aus Aufnahme, nicht erneutem Empfang. Fehlender Nachweis ist
`unknown`, fehlende Messung `missing`, widersprüchlicher Bezug `invalid`,
belegt zu alte brauchbare Aufnahme `stale`. Nutzwerte bleiben bei fehlender
Messung `null`; gemessene Null erfordert echte Quelle und Qualität.
Eine Quelle im Register ist noch kein Nachweis ihrer Schutzwirkung.

Ich nehme den bewussten inkompatiblen Zeitpfad aus V1a an: JSON-Zahlen in
Sekunden, Raster 1 ns, Bereich 0…9223372036854775807 ns. Integer-ns aus
belegter lokaler Uhr; direkte Bauwerte `int`-Sekunden oder exakte
`Decimal`-Sekunden, keine Zeit-Floats/Booleans/Strings. JSON-Dezimal- und
Exponententokens vor Floatkonvertierung exakt lesen, Raster/Bereich ohne
rundenden Decimal-Kontext prüfen, integer-ns vergleichen und Decimal wieder
als Zahl schreiben. Kein Epsilon oder Fristaufschlag; kein `Decimal(float)`.
Schema allein oder ein externer Floatleser beweist diese Semantik nicht.
UTC bleibt Kalender-/Synchronisationsangabe, keine lokale Fristuhr.

Enge Ergänzung für Umsetzung: Jede kontextuelle Prüfantwort muss neben
Status/Grund den benutzten Geräte-/Produzentenstart-/Uhrkontext benennen.
Ein nicht belegter Uhrbezug darf auch bei gleichen Kennungstexten kein
berechnetes Alter liefern. Reale Uhr-/Sensorzeitabbildung wird später belegt;
C1 prüft jetzt explizit gegebenen Kontext und synthetische Parameter.

## V2: Datenannahme von Wunsch und Details

Die 13 C1f-Felder und der vollständige Requestschlüssel werden angenommen;
`request_id` ist nur Korrelation. Separater und eingebetteter Wunsch haben
denselben fachlichen Inhalt. `motion.request=null` bedeutet kein verfügbarer
Wunsch. Die kontextuelle Datenannahme liefert Verwendbarkeit und Diagnose,
keine Motorfreigabe, keinen laufenden Empfangsprozess und keine Aktoraktion.

Die V2-Regeln sind konkret genug: nur ausdrücklich gebundener Produzent/Start/
Gerät/Uhr; keine Bindung durch erste Nachricht. Integer-ns-Bedingungen
`generated <= now < valid_until` und `0 < duration <= max_duration`.
Höhere Sequenz verlangt nicht rückläufige Erzeugungszeit. Gleicher Schlüssel
und gleicher Inhalt ist Duplikat ohne Ausführung/Fristerneuerung; anderer
Inhalt ist Widerspruch. Replay/ungültiger Kontext verändert Vergleichswerte
nicht. A-Neubindung verlangt `generated > bind_mono_s`; C-Neustart löst sie
nicht aus. Nach bestätigtem B-Startwechsel bleibt der alte Start gesperrt.

Insbesondere nehme ich die Präzisierung von #142 an: Annahmepaar und
Anti-Replay-Höchststand mit Erzeugungszeit/Inhaltsbezug sind getrennt.
Ein ansonsten gültiger abgelaufener höherer Eingang erhöht nur den Höchststand
und entzieht älteren Wünschen die Verwendbarkeit; kein Rückfall nach Ablauf.
Fremde, zukünftige, überlange, widersprüchliche oder zeitregressive Eingänge
vergiften ihn nicht. Beide Paare bleiben nach Ablauf erhalten. Bei fehlendem
Kontext/Budget lautet das Ergebnis unbekannt/nicht verwendbar mit Grund,
keine erfundene Standardfrist. Das ist keine Anweisung, physische Haltreaktion
im Datenvalidator auszuführen.

Ältere Details bleiben bei belegter damaliger Registrierung und unveränderten
Metadaten zuordenbar; kein Zwang zum neuesten Frame. Wiederempfang verjüngt
nicht, verdrängte Metadaten werden nicht rekonstruiert. Ein historisch gültiges
Detail beweist keinen aktuell gesunden Pflichtsensor. Die genaue lokale
Aufbewahrungsgrenze und das Altersbudget sind Eingabeparameter, keine hier
festgelegte reale Rate. Das genügt für Darstellung ohne Brokerbetrieb.

## V3: Enge Ergänzungen vor den Datenimplementierungen

Die Begrenzung auf 16 bestätigte Historienabschlüsse ist aus A-Sicht als
Darstellungspuffer tragfähig: keine Fortschrittsmessung aus Befehlen, sichtbare
Kapazitätsverwerfung, Erfassungslücke getrennt, B-Reset statt C-Reset.
Kartenkennungen/Abschlusskriterien und die fachliche Pufferannahme bleiben B/O.
Ich nehme die Trennung von Räumphase, Pause, Ergebnis und Abbruchgrund an;
ein gesendeter Griff oder Timerablauf belegt keinen Erfolg.

Die Grenzen der Vorlage sind richtig. Vor Auftrag 5 sind folgende konkrete
Feld-/Regelergänzungen gemeinsam mit B/C/O festzuhalten. Namen sind Vorschläge
für denselben Vertrag 2.0, keine bereits eingeführte Schnittstelle:

| Bereich | A-Vorgabe zur darstellbaren Bedeutung |
|---|---|
| `motion.request` | B-Wunsch mit vollständigem Requestschlüssel und eigener Frist; weder Ausgabe noch Messung. |
| `motion.output` | Von A tatsächlich ausgegebene SI-Bewegung mit A-`producer_id`/`producer_boot_id`, `output_seq`, `time_basis_id`, `issued_mono_s`, Status/Grund, `request_ref` und verpflichtender `evaluation_ref` gemäß Regel unten. `request_ref` ist der vollständige Requestschlüssel oder `null` bei eigenständigem Sicherheitshalt mit Grund. Keine Ausgabe aus Wunsch rekonstruieren. Fehlende Ausgabe bleibt unbekannt/null; bestätigter Nullbefehl beweist keinen Stillstand. |
| `motion.measured` | Wirkliche Messung mit Quellen-/Frame-/Aufnahme-/Empfangsbezug, m/s und rad/s, Qualität/Grund; nicht vom ausgegebenen Sollwert befüllen. |
| `arm.output` | Tatsächlich vom Armausgabebesitzer weitergereichter Auftrag: `robot_id`, dessen `producer_id`/`producer_boot_id`, eigene ganzzahlige `output_seq` ≥ 0 ohne Wiederverwendung im selben Start, `time_basis_id`, `issued_mono_s`, Status/Grund, tatsächlich ausgegebene Aktion/Zielwerte mit Einheit/Koordinatenbezug, vollständige `command_ref` und verpflichtende `evaluation_ref` für `domain=arm`. Ausgabeschlüssel ist `(robot_id, producer_id, producer_boot_id, output_seq)`; `arm.release.output_ref` muss genau diesen Schlüssel referenzieren. `command_ref` bezeichnet `(robot_id, producer_id, producer_boot_id, command_seq)` des Armwunschproduzenten; bei eigenständigem Schutzauftrag null mit Grund. Ausgabebesitzer und Freigabebesitzer dürfen verschieden sein und behalten ihre eigenen Starts; die gemeinsame `evaluation_ref` gehört dem Freigabebesitzer. Fehlende Ausgabe bleibt unbekannt/null mit Grund. Empfangsbestätigung separat mit diesem Ausgabeschlüssel referenzieren; weder Ausgabe noch Empfang beweisen erreichte Stellung oder gehaltene Last. |
| `motion.release` / `arm.release` | Jeweils geliefertes abschließendes Ergebnis `decision=allowed/blocked/unknown`, Qualität/Grund, eigener Besitzerstart und `decision_seq`, Prüfzeit/Uhr, vollständige `request_ref` bzw. `command_ref` oder kontrolliert null gemäß Schutzauftragsregel unten, sowie verpflichtende `evaluation_ref`. `output_ref` bezeichnet genau die zugehörige Ausgabe mit Gerät/Besitzerstart/Ausgabesequenz, bei fehlender Ausgabe ausdrücklich null mit Grund. Grundsätzliche Motorbereitschaft getrennt halten. Fehlender Besitzer/Nachweis bedeutet `unknown`, nie `allowed`. Historische Ergebnisse bleiben als solche referenzierbar; ein Resultat zu anderem Request darf nicht als aktuelles angezeigt werden. |
| Sperren / Betriebszustand | Geliefertes vollständiges Sperrbild je Auswertung mit verpflichtender `evaluation_ref`, `status`, `reason`, Besitzerstart, `seq`, `time_basis_id`, `evaluated_mono_s`; `blocks[]` mit stabiler `block_id`, `code`, Quelle/Produzent, Zeit/Qualität und `effect=motion/arm/both`. Leere Liste bedeutet nur bei ausdrücklich gültigem vollständigem Bild keine gemeldete Sperre. Unvollständiges/fehlendes Bild bleibt unbekannt, nicht leere Freigabe. |
| STOPP / Fehler | `stop_latched` und `fault_latched` als gelieferte bool/null-Angaben mit Qualität und Grund; aktive Ursachen bleiben zusätzlich in `blocks`. Bestätigter Reset mit Besitzer-/Zeitbezug ist von Wiederkehr frischer Daten getrennt. Ein Zustandswechsel, Grün, Timer oder Reconnect löscht keine Verriegelung. |
| `protection` / Sensorpflicht | Politik-ID/-Version, Pflichtmatrixreferenz und Nachweisreferenz jeweils mit Status/Grund; unbekannte Referenzen dürfen null sein. Fehlender Politiknachweis ist darstellbar. Kein `allowed` aus bloß vorhandener Referenz, Phase, Klasse oder `ki_darf_arm_bewegen` ableiten. |
| Arm/Kamera/Objekt | C1h-Vokabular für Phase/Ausführung/Ergebnis, eigene Vorgangs-/Objektidentitäten; Wunsch, Ausgabe, Empfangsbestätigung, echte Stellung/Last und Kamerapose getrennt. Letzte Beobachtung behält Frame/Zeit; Odometrieschätzung führt eigene Herkunft/Unsicherheit und erneuert diese Aufnahme nicht. Fehlende Messung bleibt null mit Qualität, keine angenommene Fahr-/Nullstellung. |

**Atomare Auswertung:** `evaluation_ref` ist das vollständige Tupel
`(robot_id, producer_id, producer_boot_id, domain, evaluation_seq)` des
Freigabebesitzers; `domain` ist `motion` oder `arm`, Sequenz steigt pro
Besitzerstart und Bereich ohne Wiederverwendung. Jede neue Auswertung bindet
genau ein Ergebnis, das dabei verwendete vollständige Sperrbild einschließlich
STOPP-/Fehlerstatus und die zugehörige Ausgabe (oder explizit fehlende Ausgabe).
Alle führen dieselbe Auswertungsreferenz; die Ergebnis-`output_ref` muss auf
genau diese Ausgabe zeigen. Änderung der Ausgabe oder der bewerteten Sperren
verlangt eine neue vollständige Auswertung, auch bei unverändertem Request.
Identische Auswertungskennung mit geändertem Inhalt ist ein Widerspruch.
C übernimmt das Paket atomar und kombiniert keine separat neuesten Teilwerte.
Fehlt ein erforderlicher Teil/Bezug, bleibt das aktuelle Ergebnis unbekannt;
eine nach folgender Regel ausdrücklich belegte Nullreferenz ist kein fehlender
Bezug. Ältere vollständige
Pakete dürfen nur als historische Diagnose erscheinen. Ohne bekannten
Armbesitzer bleibt das Armpaket unbekannt/null statt einer erfundenen Kennung.
Fahrt- und Armpakete besitzen eigene Auswertungen; ein vom jeweiligen Besitzer
bewerteter gemeinsamer Sperrgrund bleibt in beiden mit seinem Quellenbezug
sichtbar. Ein zusammenfassendes Sperrdisplay ersetzt diese beiden Pakete nicht.

**Schutzauftrag ohne Wunsch:** Bei nachweislich eigenständigem Sicherheitshalt
ohne Fahrwunsch führen sowohl `motion.output.request_ref` als auch
`motion.release.request_ref` ausdrücklich null und `reason=NO_REQUEST`.
Analog führen eigenständige Armschutzaufträge ohne Armwunsch sowohl
`arm.output.command_ref` als auch `arm.release.command_ref` als null mit
`reason=PROTECTIVE_ACTION_WITHOUT_REQUEST`. Die Gründe sind hier vorgeschlagene
Daten-Codes, keine neue Schutzpolitik. Ausgabe und Ergebnis müssen in derselben
Auswertung denselben Wunschbezug und für diesen Nullfall denselben Grund tragen.
`evaluation_ref`, reale Ausgabeidentität und deren `output_ref` bleiben dabei
verpflichtend; nur der nicht existierende Wunsch wird nicht referenziert.
So kann ein vollständig belegtes `blocked`-Ergebnis mit gültiger Datenqualität
und tatsächlich ausgegebenem Schutzauftrag vorliegen, ohne erfundenen Wunsch
und ohne allein wegen dessen Abwesenheit `unknown` zu werden. Ist dagegen nur
der Bezug unbekannt oder verloren, ist dies kein belegter Schutzauftrag:
`unknown` mit Grund für den fehlenden Nachweis, keine Ersatzkennung und keine
Umdeutung als `NO_REQUEST`. Ein fehlender Referenzschlüssel ist nie dasselbe
wie der vorgeschriebene explizite Nullwert. Das tatsächliche sichere Verhalten
liefert weiterhin der zuständige Freigabe-/Ausgabeweg.

Synthetische Dokumentfälle, jeweils mit sonst vollständig passendem atomarem
Paket, bekanntem Besitzer und tatsächlich gelieferter Ausgabeidentität:

| Fall | Ausgabe / Ergebnis | Datenbewertung |
|---|---|---|
| Kein Fahrwunsch, Sicherheitshalt | Beide `request_ref=null`, beide `reason=NO_REQUEST`, Ergebnis `blocked`; Ausgabe v=0 m/s, w=0 rad/s | Vollständig darstellbar mit gültiger Datenqualität; kein gemessener Stillstand behauptet. |
| Kein Armwunsch, eigenständiger Schutzauftrag | Beide `command_ref=null`, beide `reason=PROTECTIVE_ACTION_WITHOUT_REQUEST`, Ergebnis `blocked`; Ausgabe ist ein hypothetisch vom Besitzer gelieferter Schutzauftrag | Vollständig darstellbar; keine Festlegung einer physischen Armreaktion oder Lastbestätigung. |
| Ausgabe ohne Wunsch, Ergebnis verweist auf alten Wunsch | Ausgabe null, Ergebnis vollständige frühere Wunschreferenz | Widersprüchliches Paket trotz gleicher Auswertungskennung; nicht als aktuelles vollständiges Ergebnis übernehmen. |
| Nullbezug ohne belegten Grund oder mit verschiedenen Gründen | Beide Referenzen null, Grund fehlt oder passt zwischen Ausgabe/Ergebnis nicht | Kein kontrollierter Schutzauftragsfall; unbekannten Bezug ehrlich zeigen, keine vollständige gültige Auswertung behaupten. |

Referenzen müssen zum Gerät, Besitzerstart und jeweiligen Schlüssel passen;
Ausgabe- und Prüfzeit sind keine Sensoraufnahmezeiten. Vergleiche zwischen
Zeitfeldern nur bei belegter gemeinsamer Uhr. Das vollständige Sperrbild ist
eine Behauptung des liefernden Freigabebesitzers; C1 kann Typen, Referenzen und
deklarierte Widersprüche prüfen, nicht Vollständigkeit aus Sensoren berechnen.
`allowed` bei gemeldeter wirksamer Sperre desselben Ergebnisses ist ein
Datenwiderspruch. Keine zusätzlichen Sperren aus einer eigenen Pflichtmatrix
ermitteln. Verschwindet Personenhalt, bleiben alte Tiefe, STOPP und Fehler
unabhängig sichtbar. Welche Armreaktion STOPP physisch bewirkt, bleibt offen.

## V4 und die sechs Folgeaufträge

Version 2.0 wird aus A-Sicht als bewusster öffentlicher Bruch angenommen:
gemeinsame Zustands-/Wunschversion, historisches v1-Schema, aktive v2-Daten;
v1/unknown nicht still migrieren. Unbekannte Herkunft, Zeit und Historie dürfen
nicht zu erfundenen gültigen 2.0-Werten werden. Die Umsetzung folgt #14 und
erfolgt mit exklusiver Dateireservierung streng nacheinander.

| Auftrag aus #142 | Fachliche A-Annahme und erforderlicher Nachweis der späteren Lieferung |
|---|---|
| 1 Fundament | V1/V1a/V4 einschließlich exakter Bau-/Lese-/Schreibpfade und Altersrechnung annehmen. Positiv C-Neustart ohne neue Ursprungsdaten; negativ falsche Uhr, Alias, Float/Bool, Raster/Bereich, Zukunft und v1. #11–#14 dürfen nicht verloren gehen. |
| 2 Details | Historischen Registerkontext und getrenntes Aufnahme-/Transportalter annehmen. Älteren gültigen Frame erhalten; fremde Quelle/Uhr und fehlenden historischen Beleg erkennen. Parameter explizit, kein Broker erforderlich. |
| 3 Fahrwunsch | V2 einschließlich separatem Höchststand annehmen. Fall 8 → abgelaufene 10 → frische 9 muss 9 sperren; zulässige 11 darf folgen. 1 ns vor Ablauf verwendbar, Gleichheit abgelaufen; direkte und JSON-Wege gleich. Datenannahme löst keinen Halt-/Motoradapter aus. |
| 4 Historie | Aus A-Sicht Datenabgrenzung annehmen; B/O entscheidet Karten-/Abschlusssemantik und 16er-Puffer. Gültig leer versus missing, 16/17, Lücken, B-Reset und C-Neustart zeigen; keine Fahrt aus Wünschen erfinden. |
| 5 Räumen/Arm | Nur nach gemeinsamer Feld-/Codeannahme der obigen Ergänzungen. Vier C1h-Fälle, gleichzeitige Sperren, getrennte Fahrt-/Armresultate, unbekannter Besitzer/Politik, fehlende Messung und Pause/Abbruch darstellen. Positiv vollständiges neues Auswertungspaket bei gleicher Requestkennung; negativ neue Ausgabe plus altes Ergebnis oder fremdes Sperrbild trotz gleicher Requestkennung. Keine physische Sensorpflichtmatrix implementieren. |
| 6 Gesamtannahme | Vollständige aktive Fixtures, separater Request-Einstieg, Schema und Python-Beziehungen samt JSON-Rundlauf und funktionalen Positiv-/Negativnachweisen vorlegen. Danach bewertet A separat den konkreten Gesamt-Liefercommit; dieser Abgleich nimmt ihn nicht vorweg. |

## Präzise Rückgabe an den Manager

Jetzt entscheidbar sind die genannten Datenregeln, einschließlich Darstellung
unbekannter Politik und unbekannter Armfreigabe. Enges Datentor vor Auftrag 5:
B/C/O müssen Feld-/Codebelegung und Referenzform der Tabelle bestätigen oder
konkret ändern. Ein fehlender realer Armfreigabebesitzer blockiert die ehrliche
`unknown`-Darstellung nicht; vor echtem Betrieb muss O mit A/B einen benennen.

Echte offene Entscheidungen/Nachweise: O/Carsten klären die in #126 behauptete
Akteursabschaltung und den aktualisierten Ziel-/Abnahmecommit zu #8; hier wird
keine solche Zustimmung übernommen. A/B/O legen reale Wunschhöchstdauer,
Sende-/Prüfraten und Bindungsnachweis fest; A/B/C/E belegen Uhrenraum samt
Suspendverhalten und Sensorzeitabbildung. A/B/E bestimmen Pflichtquellen je
Raum/Bewegung, zulässige Odometriefortschreibung, Stellungs-/Lastbelege und
sichere Unterbrechung/Wiederaufnahme. Gemessene Hülle, Rück-/Seiten-/Greif- und
Ablageräume, Kalibrierung, harte Greifergrenze sowie STOPP-/Watchdog-/Haltnachweise
bleiben Geräteabnahmen (#37/#38/#58/#75/#79). Ohne sie keine reale Freigabe.
Brokeradresse, Topics, Formate/Raten und externer Empfang bleiben C2/Partnerabnahme.
Keine dieser unbekannten realen Größen wird für bloße C1-Darstellung erfunden.

## Tatsächliche Dokumentprüfung

Windows, PowerShell 7.6.5, Git 2.55.0.windows.4, eigene Arbeitskopie:
6/6 relative Markdownziele mit Test-Path bestätigt,
Quell-PR-Heads und Issues über GitHub gelesen; kein JSON-Codeblock in dieser
Datei. Exakte Dezimal-/Integer-ns-Dokumentrechnung erfolgreich: Differenz
200000000 ns, 1 ns vor Ablauf, Ablaufgleichheit und Umordnung 8/10/9/11.
Dies ist kein bestandener Validator. `git diff --check` und
`git diff --cached --check` erfolgreich; genau eine neue erlaubte Datei.
Keine künstlichen Softwaretests, Pakete, ROS-, Geräte-/Brokerprüfung oder
Roboteraktion. Nativer Review und aktueller CI-Status gehören separat zur
PR-Übergabe; keine formale manuelle Review oder eigene Mergeaktion.

Nativer P2-Befund auf Vorgänger `bb17895563e86bff28832906b1eb5b6c435b438c`
([Auswertungsbindung](https://github.com/BBS-GuT/smartcity-roboter/pull/145#discussion_r4346477654)):
Ausgabe, Freigabe und Sperrbild waren nicht atomar verknüpft. Obige gemeinsame
Auswertungsreferenz und die konkreten Positiv-/Negativfälle ergänzen genau diese
Datenregel. Dies ist eine Dokumentkorrektur, keine implementierte Funktion.

Nativer Folgebefund auf `5667c7744a844687886fa57d7659fb14dc157f3d`
([Arm-Ausgabeidentität](https://github.com/BBS-GuT/smartcity-roboter/pull/145#discussion_r4346519293)):
Die ergänzte `arm.output`-Definition macht den zuvor nur vorausgesetzten
Ausgabeschlüssel und dessen Bindung an `arm.release.output_ref`, Armwunsch und
atomare Auswertung explizit. Dokumentarische Gegenkontrolle: Bei gleichem
Armwunsch darf eine Ausgabe aus anderem Ausgabestart oder mit anderer
`output_seq` die referenzierte Ausgabe nicht ersetzen; ein anderes
`evaluation_ref` verbindet auch bei identischem Ausgabeschlüssel kein passendes
Paket. Ein vollständig passendes Paket bewahrt die getrennte Empfangs-/
Stellungs-/Lastqualität. Keine JSON-Beispiele oder Runtimeänderung ergänzt;
6/6 lokale Links und beide Diffchecks erneut erfolgreich.

Nativer Folgebefund auf `3d6d5e812e66e9975509ca0ddfd21c082c5717ab`
([Nullbezüge im Ergebnis](https://github.com/BBS-GuT/smartcity-roboter/pull/145#discussion_r4346582538))
vollständig gelesen: Die Ergebnisregel verlangte stets eine Wunschreferenz,
obwohl die Ausgabe eigenständige Schutzaufträge ohne Wunsch erlaubte.
Die kontrollierte Nullregel und vier obige Dokumentfälle schließen diesen
Widerspruch; die atomare Bindung bleibt erhalten. Dokumentkontrolle mit
synthetischen Null-/Referenz-/Grundvarianten und lokale Link-/Diffprüfung
erfolgreich; keine implementierte Validatorprüfung oder Runtimeänderung.
