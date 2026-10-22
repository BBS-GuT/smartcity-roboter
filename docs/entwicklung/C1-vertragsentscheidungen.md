# C1: Gemeinsame Vertragsentscheidung und Folgeaufträge

Stand: 22.10.2026. **Fundamentsemantik für Auftrag 1 aus C angenommen;
implementierter Gesamtvertrag noch nicht angenommen.**
Verantwortlicher Mensch: Carsten; Rolle C: C1-Entscheidungs-Chat
(öffentlicher Datenvertrag, Version, JSON und Schemagrundlage); O: C1-Manager.
Refs [#3](https://github.com/BBS-GuT/smartcity-roboter/issues/3),
[#15](https://github.com/BBS-GuT/smartcity-roboter/issues/15),
[#16](https://github.com/BBS-GuT/smartcity-roboter/issues/16),
[#17](https://github.com/BBS-GuT/smartcity-roboter/issues/17),
[#18](https://github.com/BBS-GuT/smartcity-roboter/issues/18).

## Grundlage und Entscheidungsebene

Eigene Basis ist der tatsächliche C1-Sammelhead
`03430e462052c57a599f306948a2e488728c4db7`. Nur die vorliegende neue Datei
ist zugeteilt. Die Entwurfsdateien anderer Besitzer werden nicht bearbeitet.
Fachlich ausgewertet wurden folgende konkrete Lieferstände, keine Codepfade:

| Entwurf | Tatsächlicher Head beim Abgleich | Verwendung |
|---|---|---|
| [C1e / #130](https://github.com/BBS-GuT/smartcity-roboter/pull/130) | `ff4c0d78beee1eeae40fdd0597d0c32c0fc7e644` | Quellen-/Frame-/Datenidentität, historische Zuordnung, Frische |
| [C1f / #132](https://github.com/BBS-GuT/smartcity-roboter/pull/132) | `e1d6185e6878a304afa2681285be20342339e468` | Eigener Fahrwunsch, Zeitregression und exakte Nanosekundenvergleiche |
| [C1g / #131](https://github.com/BBS-GuT/smartcity-roboter/pull/131) | `3a8b81bc3e06eaceb77c3628aee874ee7d069197` | Im Sammelbranch enthaltene begrenzte B-Historie |
| [C1h / #128](https://github.com/BBS-GuT/smartcity-roboter/pull/128) | `46cd940b973fd55c92d9ccff75bcbf12ff26f097` | Im Sammelbranch enthaltener vorläufiger Räum-/Armentwurf |

Weitere Grundlage: [Zieldefinition v1.0](../zieldefinition-grundbetrieb.md)
§4–10, [gemeinsame Regeln](../auftraege/00-gemeinsame-regeln.md),
[Register](../auftraege/README.md), [C1-Auftrag](../auftraege/C-zustand-mqtt-und-panel.md),
[bestehender Vertragsentwurf](../schnittstellen-grundbetrieb.md),
Elternissue #3 und Teilissues #11–#18. #11–#14 liefern nacheinander
Altersprüfung, UTC-Kalenderprüfung, Quellenempfangszeit und auflösbare Messwertquellen.
Erst nach integrierter Lieferung von #14 beginnen die unten genannten Umsetzungen.
O gleicht spätere Heads von #130/#132 vor Annahme erneut ab; native Befunde
und ihre Korrektur bleiben beim jeweiligen Besitzer und nativen Reviewer.

Die folgenden Abschnitte trennen **R: festgelegte Anforderungen**, **V: konkrete
Vorschläge zur Annahme** und **N: noch erforderliche Entscheidungen/Nachweise**.
V1/V1a/V4 sind von Rolle C als Grundlage für Auftrag 1 angenommen;
V2/V3 bleiben Empfehlungen zur weiteren Abstimmung, keine Gesamtannahme.
Carsten hat A/B-Fachabgleiche unter O bestätigt: A-Chat
`01a162d4-e3bf-78d3-b661-335e65c4a4f4` liefert ausschließlich
`docs/entwicklung/C1-abgleich-A.md`, B-Chat
`01a162d4-f4ee-77f1-bb64-acff1646ed9e` ausschließlich
`docs/entwicklung/C1-abgleich-B.md`. O hat die ausdrückliche Annahme von
V1/V1a/V4 als erste Implementierungsgrundlage aus
[A / #145](https://github.com/BBS-GuT/smartcity-roboter/pull/145) und
[B / #147](https://github.com/BBS-GuT/smartcity-roboter/pull/147) übergeben;
damit wird keine weitergehende A-/B-Zustimmung behauptet.
Nach Umsetzung folgt eine zweite Annahme am konkreten
Gesamtcommit. O koordiniert beide Stufen; nativer Review bleibt unabhängig.
Die Rollen sind damit zugeteilt; die Gesamtannahme wird nicht vorweggenommen.
Teil-PRs gehen ausschließlich
gegen `feat/gb-c1-zustandsvertrag`; nur Gesamt-PR
[#134](https://github.com/BBS-GuT/smartcity-roboter/pull/134) geht nach main
und bleibt bis zur vollständigen Lieferung Draft.

## R: Bereits festgelegte Regeln

- GB-15–18 / A13–15: ein versionierter Zustand für Panel und MQTT;
  gleiche `(robot_id, boot_id, seq)` bedeutet gleichen fachlichen Inhalt.
  Gerätetrennung, Quellen-/Framezuordnung, Datenalter und Synchronisationsqualität
  bleiben sichtbar. Reconnect erzeugt keine Freigabe.
- GB-12–14 und #3: Messung, B-Wunsch, A-Ausgabe und abschließendes
  Freigabeergebnis bleiben getrennt. Fehlende Werte sind `null` mit Qualität,
  keine gültige Null; keine NaN-/Unendlichwerte. Der Datenvalidator prüft
  Konsistenz, er ermittelt weder Pflichtsensoren noch Motor-/Armfreigaben.
- #14: `source` ist ausschließlich ein registrierter `sensors`-Schlüssel;
  `source_id` bezeichnet die technische Quelle. Kein Alias-Fallback.
- #11–#13: lokale monotone Zeit für Alter; endliche nichtnegative Sekunden,
  keine Zukunftswerte als frisch. UTC-Kalender mit `Z`, 1–9 optionale
  Nachkommastellen, keine Schaltsekunden in dieser Fassung.
- GB-07 / A06: relevante eigene Fahrhistorie gehört zur Darstellung;
  Wunsch und ausgegebener Befehl beweisen keine abgeschlossene Fahrt.
- [#8](https://github.com/BBS-GuT/smartcity-roboter/issues/8): Wegräumen gehört
  ausdrücklich zum Grundbetrieb. Ziel-/Abnahmeharmonisierung und reale
  Schutz-/Gerätenachweise bleiben erforderlich. Keine zweite Zielfassung hier.

## V1: Gemeinsame Feld-, Identitäts- und Zeitbasis

Aus Rolle C für Auftrag 1 angenommen: Die folgende Basis gilt einheitlich für alle vier
Erweiterungen. Kennungen sind opake, nichtleere Texte, exakt verglichen;
Sequenzen sind ganze Zahlen ≥ 0, ohne Boolean und ohne Umlauf im selben Start.
Nur `robot_id` benutzt das bestehende Geräte-Vokabular RM01–RM04.

| Ebene / Felder | Identität und Zuordnung | Zeit / Neustart / Gültigkeit |
|---|---|---|
| Zustand: `robot_id`, `boot_id`, `seq` | `boot_id` ist **Cs Zustandsproduzentenstart**; `seq` steigt je neuem konsistentem Zustand ab 0. | `generated_mono_s` trägt `time_basis_id`; UTC `generated_at` und `time_sync` bleiben separat. C-Neustart ändert nur diese Zustandsidentität. |
| Gemeinsame Uhr: `time_basis_id` | Kennung der systemweiten lokalen Geräte-Uhreninstanz, einschließlich Uhrtyp, Ursprung und Suspendverhalten; keine Prozessstoppuhr. | Neu bei Geräteuhrreset/Uhrenraumwechsel, nicht allein bei A-/B-/C-/Sensorprozessstart. Gleiche Zeichenfolge ist ohne bestätigte Bindung kein Nachweis. |
| Ursprung: `producer_id`, `producer_boot_id` | Logischer fachlicher Produzent und dessen eigenständiger Start, gebunden an `robot_id`. Keine Gleichsetzung mit C-`boot_id`. | Kennung bei jedem Produzentenstart neu, niemals wiederverwenden; Zeitbasis darf dabei gleich bleiben. C übernimmt Ursprungsidentitäten unverändert. |
| Quelle: `sensors[source]` | Registrierung mit `source_id`, `producer_id`, `producer_boot_id`, `time_basis_id`; `frame_id` ist Aufnahmekennung, `coord_frame` bleibt räumlicher Bezug. | `captured_mono_s`, `received_mono_s` und Zustandserzeugung in derselben belegten Uhr. Sensorzeit nur nach nachgewiesener Abbildung. |
| Frame / Detail | Frame: `(robot_id, source, producer_id, producer_boot_id, frame_id)`; Daten: Frame plus `(channel, data_id)`. `source_id`, Zeitbasis, Aufnahmezeit und Format sind unveränderliche Metadaten. | Aufnahmealter statt Wiederempfangsalter. Detail-`state_boot_id` ist nur Ausgabekontext und entspricht äußerem `boot_id`; Zustandstupel trägt zusätzlich `seq`. Es gehört nicht zum Aufnahmeschlüssel. |
| Fahrwunsch: `motion.request` | `(robot_id, producer_id, producer_boot_id, request_seq)`; `request_id` nur Korrelation. Vollständige eigene Nachricht, auch ohne Zustand zuordenbar. | Eigene `generated_mono_s`, `valid_until_mono_s`, `time_basis_id`; identische Nachricht eingebettet und separat, keine Umschreibung durch C. |
| Historie: `route.history` | B-eigener Produzentenstart, `robot_id`/`map_version` aus Zustand; Eintragsschlüssel zusätzlich `entry_seq`. Unabhängig von Zustands- und Requestsequenz. | `confirmed_mono_s` ist Abschlussbestätigung, keine Aufnahmezeit; `time_basis_id` explizit am Puffer. Nur B-Neustart initialisiert den Puffer neu. |
| Räumvorgang / Armaktion | `clearing`: `producer_id`, `producer_boot_id`, `operation_id`; Objektbezug als `(robot_id, producer_id, producer_boot_id, object_id)` des Objektproduzenten. Armwunsch besitzt eigene `command_seq`. | Vorgangs-/Objektproduzent, Armwunschproduzent und Messquellen können verschiedene Starts besitzen. `started_mono_s`, `updated_mono_s` mit expliziter Zeitbasis; Messungen bewahren eigene Frame-/Zeitbezüge. |

Bei vergleichbaren Sensor-/Detailzeiten gilt
`0 <= captured_mono_s <= received_mono_s <= generated_mono_s`.
`age_s` ist die Differenz aus Zustandserzeugung und Aufnahme; bei fehlendem
Nachweis `null`. Ein nicht belegter Bezug ist `unknown`, ein widersprüchlicher
oder fremder Zeitbezug `invalid`. Alte Geräteuhrdaten bleiben identifizierbar,
sind im neuen Zeitkontext jedoch nicht frisch. UTC ersetzt diese Prüfung nicht.

Ein **reiner C-Neustart** erzeugt weder Sensoraufnahme noch Request,
Historieneintrag oder Räumvorgang neu. Er übernimmt die belegten Ursprungsdaten
unverändert; bis zur Übernahme sind sie fehlend, niemals erfunden gültig leer.
Bei Details darf nur der referenzierende Zustandskontext wechseln. Ein
Sensorneustart erzeugt einen neuen Frame-Namensraum, keinen neuen B-Start.

### V1a: Exakte Sekundenfelder durch den gesamten JSON-Pfad

Die Präzisierung aus #132 ist **aus C für Auftrag 1 angenommen**, noch nicht im
öffentlichen Vertrag umgesetzt. Vorschlag für 2.0: monotone Zeitpunkte,
Alters-/Dauerwerte und die zugehörigen lokalen Prüfparameter verwenden
einheitlich das Nanosekundenraster. Die `_s`-Felder bleiben JSON-**Zahlen in
Sekunden**, keine Strings und keine als Sekunden etikettierten Nanosekunden.
Wertebereich gemäß C1f: 0 bis `9223372036.854775807` s (= 2⁶³−1 ns).
Dies ist eine technische Darstellungsgrenze, keine Bewegungsfrist und kein
Versprechen einer Sensorauflösung von 1 ns. UTC-Felder behalten ihr eigenes
Format; sie dienen nicht dem lokalen Fristvergleich.

| Pfad | Konkreter umsetzbarer Vorschlag |
|---|---|
| Produzent / lokale Parameter | Bestätigte gemeinsame Uhr liefert Integer-ns, etwa über `time.monotonic_ns()` nach Nachweis des gemeinsamen Uhrenraums. Fristen durch Addition eines ausdrücklich vereinbarten Integer-ns-Budgets bilden; Überlauf ablehnen. Kein `time.monotonic()`-Float, kein `ns / 1e9` als Float. |
| Direkte Python-Bauwerte | Zeitfelder akzeptieren `int` als ganze **Sekunden** oder exakte `Decimal`-Sekunden; `bool`, Binärfloats und Zahlenstrings ablehnen. Ein expliziter Bauhelfer wandelt Integer-ns durch exakte Dezimalstellenbildung in `Decimal`-Sekunden um. `Decimal(float)` ist kein zulässiger Reparaturweg; direkte Dezimalliterale aus Text oder ns verwenden. |
| JSON-Lesen (`lade_json`) | Dezimal-/Exponententokens unmittelbar mit `parse_float=Decimal`, Ganzzahltokens als `int` lesen, Sonderzahlen weiter ablehnen. Erst anschließend feldbezogen Raster/Bereich prüfen und Zeiten in Integer-ns normalisieren. Vorheriges `json.loads` mit Standardfloat verliert den erforderlichen Beleg. |
| Rechnen / Vergleichen | Rasterprüfung und ns-Umwandlung exakt über Dezimalziffern/Exponent bzw. Ganzzahlarithmetik, ohne rundenden Decimal-Kontext. `now`, Bindung, letzte Erzeugung und Maximaldauer ebenfalls Integer-ns. Differenz, Ablauf und Zeitregression ausschließlich ganzzahlig; kein Epsilon/Nachrunden. |
| JSON-Schreiben (`als_json`) | `Decimal` feldtreu als unquotiertes JSON-Zahlentoken ausgeben; `int` unverändert als Sekundenzahl. Standard-`json.dumps` unterstützt diesen Decimal-Pfad bislang nicht. Eigene begrenzte Zahlenausgabe im bestehenden Modul vorsehen; keine Umwandlung in Float, kein `default=str`, kein nachträgliches Ersetzen von Text. Andere JSON-Typen weiterhin korrekt escapen. |
| Nichtzeitliche Zahlen / externe Leser | Der Leser liefert auch für andere Dezimalzahlen `Decimal`; deren Zahlenprüfung muss diesen endlichen Typ unterstützen, ohne SI-Bedeutung zu ändern. Endliche direkte Floats bleiben für Nichtzeitfelder möglich. Schema beschreibt Zahlen/Struktur; ein Leser mit Binärfloats kann die exakte Fristsemantik nicht garantieren und darf daraus keine lokale Verwendbarkeit ableiten. |

Für **alle** Decimal-Zahlen, auch in Nichtzeitfeldern, ist vor Arithmetik,
Raster-, Bereichs- oder Ordnungsvergleichen die Endlichkeit mittels
`is_finite()` zu prüfen. Direkte Bauwerte `Decimal("NaN")`, `Decimal("sNaN")`,
`Decimal("Infinity")` und `Decimal("-Infinity")` sind ungültig. Die Prüfung
darf weder durch naive Vergleiche `decimal.InvalidOperation` auslösen noch
Sonderwerte an die JSON-Ausgabe weiterreichen. `pruefe()` liefert dafür
Fehlertexte; die validierenden JSON-/Altersfunktionen melden den dokumentierten
`ValueError`, keine unkontrollierte Decimal-Ausnahme. JSON-`parse_constant`
allein deckt diesen direkten Python-Eingang nicht ab.

Damit sind Bau-, Lese-, Prüf- und Schreibpfad gemeinsam zu ändern. Ein isolierter
`parse_float`-Zusatz genügt nicht: Die heutige Zahlenprüfung akzeptiert nur
`int`/`float`, der Writer nutzt Standard-`json.dumps`, `alter_s` rechnet direkt
mit den Bauwerten. Diese Ausgangsbeschreibung ist Implementierungsplanung,
kein zusätzlicher manueller Code-Review. Die vorgeschlagene Lösung ist mit
Standardbibliothek darstellbar, verlangt aber gezielte Rundlauf-/Grenztests
und eine bewusste öffentliche Typänderung in 2.0. Auch `alter_s` muss exakte
Eingänge/Ergebnisse unterstützen, seine bisherigen Fehlerregeln bleiben bestehen.
Externes Schema allein ersetzt keine Prüfung ursprünglicher Zahlentokens.

Synthetische Akzeptanzfälle: `120.2`, `120.200000000` und `1.202e2` normalisieren
auf denselben Wert; `120.2000000001` ist unzulässig und wird nicht verkürzt.
`120.2 - 120.0` ergibt exakt 200000000 ns. Bei `now=120.2` ist die Frist
`120.2` bereits abgelaufen. Der Wertebereich endet exakt bei 2⁶³−1 ns;
ein weiteres ns ist ungültig. Der JSON-Rundlauf bewahrt Zahlen und Fristen.

## V2: Details und eigenständiger Fahrwunsch

**Details:** C1e-Schlüssel und Statusregeln aus #130 übernehmen. Ältere Frames
sind erlaubt: historisch belegte Registrierung statt Gleichheit mit dem
neuesten Sensorframe. Identisches Schlüssel-/Metadatenpaar ist ein Duplikat;
gleicher Schlüssel mit widersprüchlichen Metadaten ist ungültig. Ohne damaligen
Zuordnungsbeleg kein `valid`. Metadaten-/Payloadaufbewahrung bleibt begrenzt;
Verdrängung erlaubt keine Wiederverwendung einer Kennung. Grenze und konkrete
Kanal-Altersbudgets werden noch vereinbart. Ein alter brauchbarer Frame belegt
keine aktuelle Sensorverfügbarkeit. Farbe/Tiefe werden nicht aus gleichen
Textkennungen automatisch gepaart. Detailqualität bleibt von Transportzustand
und physischer Schutzwirkung getrennt.

**Fahrwunsch:** die 13 Felder aus C1f übernehmen, `contract_version` auf dieselbe
gemeinsame Version wie Zustands-`schema_version` festlegen. Kein eigenes
Versionsregime. `motion.request = null` bedeutet kein verfügbarer Wunsch.
Maximale Wunschdauer ist ein verpflichtender Prüfparameter, kein hier erfundener
Standardwert; C1 kann seine Semantik mit synthetisch vorgegebenem Budget prüfen.

| Eingang im bestätigten lokalen Kontext | Vorgeschlagene Datensemantik |
|---|---|
| Neuer Wunsch | Gerät, zugelassener Produzent, aktiver Start und Zeitbasis müssen gebunden sein; `generated <= now < valid_until`, `0 < valid_until - generated <= max_duration`. Keine Bindung durch erste Nachricht oder Topic. |
| Höhere `request_seq` im selben Start | Sequenz muss über dem gesonderten Anti-Replay-Höchststand liegen; Erzeugungszeit mindestens die des dort gespeicherten jüngsten ansonsten gültigen Eingangs. Gleichheit zulässig. Rücklauf wird verworfen, auch bei offener Frist. Angenommenen Wunsch und beobachteten Höchststand getrennt führen. |
| Gleiches Tupel, gleicher Inhalt | Duplikat; keine erneute Ausführung, Fristerneuerung oder neuer Manöverbeginn. |
| Gleiches Tupel, anderer Inhalt / Sequenz unter Anti-Replay-Höchststand | Widerspruch / Replay, verwerfen. Solche Eingänge verändern weder Vergleichswerte noch Fristen. |
| `now >= valid_until`, Eingang ansonsten vollständig gültig und identitätsgebunden | Nicht ausführen, aber neuen Anti-Replay-Höchststand samt Erzeugungszeit/Inhaltsbezug speichern. Ältere Wünsche sind damit überholt, auch wenn deren eigene Frist noch offen ist; es gibt keinen Rückfall auf sie. Annahmepaar des letzten ausgeführten/verwendbaren Wunsches bleibt als Diagnose erhalten. |
| Fremdes Gerät, unbestätigter Start/Uhrenbezug, Zukunft, ungültige Zahl | Nicht übernehmen; keine scheinbare Frische und kein impliziter Startwechsel. |
| Bestätigter B-Startwechsel | Alten Wunsch verwerfen/alten Start sperren; Vergleich im neuen Start neu beginnen. Wechsel selbst gibt keine Bewegung frei. |
| A-Neustart / verlorener Annahmekontext | Neu binden, Puffer verwerfen; erster Wunsch muss nach Bindung erzeugt sein (`generated > bind_mono_s`). C-Neustart allein verändert diese Bindung nicht. |

**Präzisierung gegenüber C1f zur Annahme:** Der Anti-Replay-Höchststand ist
das Paar aus höchster beobachteter ansonsten gültiger Sequenz und deren
Erzeugungszeit im bestätigten Kontext, ergänzt um den unveränderlichen
Inhaltsbezug für Duplikat-/Widerspruchserkennung. Er steigt sowohl bei frischen
als auch bei lediglich abgelaufenen Eingängen. Vorher müssen Struktur,
Gerät/Produzent/Start/Uhr, Bindungszeit, Zahlenraster, nicht zukünftige Erzeugung,
positive erlaubte Dauer und nicht rückläufige Erzeugungszeit geprüft sein.
Fremde, widersprüchliche, zukünftige, überlange oder zeitregressive Eingänge
dürfen diesen Stand nicht vergiften. Erst danach wird Frische geprüft.
Ein frischer neuer Wunsch aktualisiert zusätzlich das Annahmepaar und den
verwendbaren Wunsch; ein abgelaufener neuerer Eingang hinterlässt eine Sperre
gegen ältere Sequenzen und entfernt deren Verwendbarkeit. Identische Wiederholung
am Höchststand ändert nichts. Beide Vergleichspaare bleiben nach Fristende
erhalten und werden bei bestätigtem Kontextwechsel neu initialisiert.
Der Kontext besteht aus lokal bestätigtem Gerät, B-Produzent, B-Start und
Zeitbasis samt A-Bindung, **nicht** aus Cs äußerer `boot_id`. Ein reiner
C-Neustart erhält Annahmepaar und Anti-Replay-Höchststand einschließlich
Duplikatbezug unverändert; neue C-Zustandssequenz ist keine Neubindung.

Synthetischer Umordnungsfall bei `now=101` s, Budget 2 s: Nach angenommenem
Wunsch 8 (Erzeugung 100, Ablauf 102) trifft Wunsch 10 (100.4, 100.6) bereits
abgelaufen ein. Höchststand wird 10; Wunsch 8 ist überholt. Wunsch 9
(100.2, 101.5) bleibt trotz offener eigener Frist gesperrt. Erst ein neuer
ansonsten gültiger Wunsch über 10 mit nicht rückläufiger Erzeugungszeit kann
wieder verwendbar sein. Das ist Datensemantik, kein hier implementierter Haltweg.

Das sind darstellbare Zuordnungs-/Validierungsregeln. C1 liefert dafür eine
ROS-unabhängige Prüfung mit explizitem Kontext und gegebenem `now`, keine
laufende Empfangsschleife oder A-/B-Adapter. Ein formal gültiger Wunsch
überspringt weder STOPP noch Pflichtsensor-/Hüllen-/Verkehrsprüfung.

## V3: Begrenzte Historie und Räum-/Armdarstellung

**Historie:** #131 übernehmen: maximal **16** bestätigte gerichtete Abschlüsse
im Zustand, ältester zuerst. Diese Puffergröße ist ein Vorschlag, keine
Anforderung oder gemessene Größe. `section`, `node`, `approach_from`, `exit_to`
beziehen sich auf dieselbe `map_version`; ausgehender Abschnitt zählt noch
nicht als befahren. `entry_seq` lückenlos aufeinanderfolgend, Bestätigungszeiten nicht
abnehmend und nicht nach Zustandserzeugung. Kapazitätsverlust ist sichtbar
in `dropped_entries`, ohne Neunummerierung. Erfassungslücken sind davon getrennt.

Präzisierung zu C1g: In einem gültigen nichtleeren Puffer gilt für jedes
Indexelement `i` ab 0: `entries[i].entry_seq = dropped_entries + i`.
Die älteste Sequenz entspricht also exakt der Zahl ausschließlich wegen
Kapazität verworfener Einträge. Bei weniger als 16 Einträgen ist
`dropped_entries = 0`; bei positiver Verwerfungszahl sind genau 16 Einträge
vorhanden. Gültig leer hat immer Zähler 0. Andere Löschungen oder Lücken
werden als Erfassungslücke `invalid`, nicht als Kapazitätsverlust kaschiert.
Beispiele: `[0, 2]` ist ungültig; nach dem 17. Abschluss sind `[1, ..., 16]`
mit `dropped_entries=1` gültig, dieselbe Folge mit Zähler 0 nicht.

Initialisiert leer: `valid`, `entries=[]`, `dropped_entries=0`. Nicht verfügbar:
`missing`, Grund, Nutzwerte `null`; widersprüchlich/Erfassungslücke: `invalid`,
Grund, Nutzwerte `null`. B-Neustart setzt Puffer und Zähler neu; STOPP, TEST,
Reconnect oder C-Neustart nicht. Kartenwechsel verlangt in dieser Fassung
einen neuen Historienproduzentenstart; kein Umetikettieren alter Kennungen.
Optionale Abschlussbelege nutzen Detailreferenzen, keine erfundene Sensorquelle
für den B-Historienproduzenten. C1 prüft deklarierte Kartenbezüge/gegebenen
synthetischen Kartenkontext; B2 bestätigt später reale Karte und Abschlusskriterien.

**Räumen/Arm:** #128 auf folgende öffentliche Bereiche konkretisieren, ohne
neuen Betriebsmodus oder Bewegungsautomat. Neue Namen sind Vorschläge:

| Bereich | Darstellbarer Mindestinhalt und Grenze |
|---|---|
| `clearing` (B) | Vorgangsidentität gemäß V1, `phase`, `execution_status`, `result`, `abort_reason`, Objektbezug, Beginn/letzter Übergang, Qualität/Grund. Phasen und Ergebnisvokabular aus C1h; Abbruch braucht Grund, Pause ist kein Erfolg. |
| Objektbeobachtung / Schätzung | Letzte echte Quelle/Frame-/Detailreferenz, Klasse samt Qualität, Lage/Geometrie mit Koordinatenbezug; Odometriefortschreibung separat mit Herkunft und Unsicherheit. Schätzung erneuert keine Aufnahme. |
| `arm.request` / `arm.output` | Wunsch mit eigener Produzentenidentität, `command_seq`, Zeitbasis/Erzeugung/Ablauf, Vorgangs-/Objektbezug und Ziel; ausgegebener Auftrag und Empfangsbestätigung separat. C1f-Zuordnungs-/Duplikatregeln entsprechend, aber keine Fahrfreigabe daraus. |
| `arm.measured`, `camera_pose` | Wirkliche Stellung mit Quelle, Messungs-/Aufnahmekennung, Zeit, Einheit und Qualität; Koordinaten-/Kalibrierbezug explizit. Sollwert und Schätzung sind keine Bestätigung; fehlende Rückmeldung bleibt `null` mit Status. |
| Fahrt-/Armfreigabe | Getrennte vom jeweiligen Freigabebesitzer gelieferte Ergebnisse samt geprüfter Request-/Commandkennung und Prüfzeit. Nicht aus Phase, Klasse, Sollstellung oder `ki_darf_arm_bewegen` ableiten. A bleibt Besitzer der Fahrtfreigabe; Arm-Besitzer offen A/B. |
| `protection` | `policy_id`, `policy_version`, Nachweisreferenz; `status` und `reason` für den Schutzpolitikbezug. Getrennt dazu Sensorpflichtreferenz und tatsächlich gemeldete Sperren mit Wirkung auf Fahrt/Arm/beide, Quelle und Zeit. Fehlende Politik: `unknown` mit Grund, keine erfundene Freigabe. |

Die Schutzpolitik wird **referenziert und mit ihrem Nachweisstatus dargestellt**;
die Schemaannahme bescheinigt ihre physische Wirksamkeit nicht. C1 prüft
Feldtypen, Referenzen und widersprüchliche Angaben, keine erfolgreiche
Sensor-/Sicherheitsprüfung aus dem Vorhandensein einer Referenz.

### V3a: Zusammengeführter Datenanhang für Auftrag 5

**C-Spezifikation zur anschließenden ausdrücklichen Bestätigung durch A/B/O,
noch keine angenommene Auftrag-5-Implementierung.** Fachliche Quellen wurden
vor Bezug erneut abgefragt: A/#145 auf
`3d6d5e812e66e9975509ca0ddfd21c082c5717ab`, B/#147 auf
`deba190d7061a65c7e21625b7a21a57747643125`.
Dieser Anhang konkretisiert die obige Übersicht verbindlich für den Vorschlag.
Die über O nachgereichten nativen Präzisierungen zu A-Kommentar 4346582538
(begründeter Nullwunsch auch im Ergebnis) und B-Kommentar 4346589401
(kein fortbestehender Armwunsch bei Inaktivität) sind unten aufgenommen;
anschließend tatsächlich abgeglichene Korrekturheads: A
`69da13138a9d1215dced02b8ca6b00b9c783c617`, B
`1a1a3e8c22dd52b1adbcd031a482b25b37a720d1`. Deren konkrete ergänzte
Nullregeln sind fachlich gelesen; Zustimmung zu diesem neuen C-Anhang
wird daraus nicht abgeleitet.
Einzige Sperrwirkungsbelegung: **`effect=motion/arm/both`**. B-`scope=drive`
wird auf `effect=motion` vereinheitlicht; kein paralleles `scope`-Feld.
`domain=motion/arm` bezeichnet dagegen den Bereich einer Auswertung.

**Gemeinsame Typ-/Nullkonvention:** Alle in den folgenden Tabellen genannten
Felder sind Pflichtschlüssel; `null` ist nur in den ausdrücklich genannten
Fällen zulässig. `Q` bedeutet die beiden Felder `status` und `reason`:
Status aus `valid/unknown/invalid/stale/missing`, bei `valid` Grund `null`,
sonst nichtleerer Grundcode. `valid` bewertet den jeweiligen Datenbeleg,
nicht die Erlaubnis einer Bewegung. Bekannte Identitäten bleiben auch bei
schlechter Qualität erhalten; unbekannte Identitäten werden nicht erfunden.
Zeit-/Zahltypen folgen V1a, Zähler sind ganze Zahlen ≥ 0 ohne Boolean.
Zeiten werden nur bei belegter gleicher Uhr verglichen. Nicht verfügbare
Mess-/Schätzwerte sind `null`; nie eine gültige Nullstellung daraus bilden.

#### Vollständige Referenztypen

Jede Referenz wird als Objekt mit **allen** unten genannten Schlüsselanteilen
übertragen; keine Abkürzung auf die letzte ID. Das jeweilige Ziel muss im
gegebenen Datensatz bzw. explizit bereitgestellten historischen Kontext
auflösbar sein. Fehlender Nachweis ist `unknown`, ein Widerspruch `invalid`.
Verschiedene fachliche Rollen dürfen unabhängige Produzentenstarts besitzen.

| Typ | Vollständige Pflichtfelder / Ziel |
|---|---|
| `OperationRef` | `robot_id, producer_id, producer_boot_id, operation_id`: B-Räumvorgang. |
| `ObjectRef` | `robot_id, producer_id, producer_boot_id, object_id`: Objektproduzent, nicht automatisch der Vorgangsproduzent. |
| `FrameRef` | `robot_id, source, producer_id, producer_boot_id, frame_id`: registrierter Sensorframe nach V1/V2; technisches `source_id`, Aufnahmezeit/Uhr und `coord_frame` aus dessen unveränderlichem Registerbeleg. |
| `DetailRef` | Alle `FrameRef`-Felder plus `channel, data_id`; Format/Metadaten nach C1e. Optionaler Payloadabruf ersetzt keinen Quellenbeleg. |
| `ObservationRef` / `EstimateRef` | `robot_id, producer_id, producer_boot_id` plus `observation_seq` bzw. `estimate_seq`: eigene Interpretation/Schätzung, nicht Sensorframe oder C-Zustandssequenz. |
| `RequestRef` / `CommandRef` | `robot_id, producer_id, producer_boot_id` plus `request_seq` bzw. `command_seq`: B-Fahrwunsch oder Armwunsch. |
| `OutputRef` | `robot_id, producer_id, producer_boot_id, output_seq`: tatsächlich meldender Ausgabeproduzent; Referenzfeld ist durch `motion` oder `arm` typisiert. Sequenz je Ausgabedomäne/Produzentenstart ohne Wiederverwendung. |
| `EvaluationRef` | `robot_id, producer_id, producer_boot_id, domain, evaluation_seq`: Freigabebesitzer, `domain=motion/arm`, eigene Sequenz je Domäne/Start ohne Wiederverwendung. |
| `BlockRef` | `robot_id, producer_id, producer_boot_id, block_id`: Ursprung der gemeldeten Sperre; dieselbe Ursache kann in beiden Domänen erscheinen. |
| `EvidenceRef` | `robot_id, producer_id, producer_boot_id, evidence_seq`: bestätigender Nachweisproduzent mit eigenem Start und Sequenz. |

Opake Textkennungen werden nicht zerlegt. Alle gerätebezogenen Ziele gehören
zum äußeren `robot_id`. Derselbe Schlüssel mit geändertem Inhalt ist ein
Widerspruch; Wiederübertragung erzeugt kein neues Ereignis. Reiner C-Neustart
ändert keinen dieser Schlüssel. Eine Referenz auf einen alten Vorgang darf
als Diagnose bestehen, wird aber nicht zum Nachweis eines anderen Vorgangs.

#### B-Vorgang, Objekt, Beobachtung und Schätzung

| Objekt / Felder | Typ, Pflicht/null und Qualität |
|---|---|
| `clearing` Herkunft | `producer_id, producer_boot_id, time_basis_id`: Text oder bei tatsächlich unbekannter Bindung `null`; `Q`. Gerät aus Zustand; zusammen mit `operation_id` entsteht `OperationRef`. |
| Vorgang | `operation_id`: Text oder inaktiv/unbekannt `null`; `started_mono_s, updated_mono_s`: Sekunden oder ohne Vorgang `null`; aktiv gilt `started <= updated <= generated`. |
| Phase | `phase`: `inaktiv/anschauen/ausrichten/greifen/ablegen/nachpruefen/fahrstellung_bestaetigen/beendet`; bei nicht bekanntem Vorgang `null` zulässig. `execution_status`: `laufend/pausiert/beendet` oder bei unbekanntem Ablauf `null`. |
| Ergebnis / Gründe | `result`: `offen/erfolgreich/nicht_raeumbar/abgebrochen` oder unbekannt `null`. `abort_reason`: nichtleer genau bei Abbruch, sonst `null`. `result_reason`: nichtleer genau bei `nicht_raeumbar`, sonst `null`. Qualitäts-`reason` bleibt davon getrennt. |
| Unterbrechung | `interruption_reason, interrupted_mono_s`: nichtleerer Code und Zeit genau bei `pausiert`, sonst beide `null`. Pause erhält Phase/Objekt, Ergebnis `offen`; Beginn ≤ Unterbrechung ≤ letzter Übergang. Beispiele für Ursachen: `person_hold/stop/object_lost/sensor_unavailable/actuator_error/limit_unproven`; reine gemeldete Ursachen, keine Schutzentscheidung. |
| Beziehungen | `object_ref`: vollständige `ObjectRef` oder ohne/bei unbekanntem Objekt `null`; `observation, estimate`: folgende Objekte oder ohne zugeordnetes Objekt `null`. Ein aktiver Vorgang ohne belegtes Objekt darf nicht als vollständig `valid` gelten. |
| Erfolgsbelege | `verification_ref, travel_pose_ref`: jeweils Nachweislink `{ref: EvidenceRef oder null, status, reason}` oder bei keinem Erfolgsbeleg `null`. Erfolg verlangt beide Links `valid`, auflösbare `valid`-Nachweise mit demselben `operation_ref`, passenden Arten `verification/travel_pose` und `started <= confirmed <= updated <= generated` in belegter gemeinsamer Uhr. Sonst kein belegtes `erfolgreich`. |
| `observation` | `observation_ref, object_ref, frame_ref`: vollständige Schlüssel; `detail_ref`: passender `DetailRef` oder `null`; `time_basis_id, captured_mono_s, received_mono_s`: nachgewiesene Aufnahme-/Empfangszeiten oder unbekannt `null`; `class_value`: Text oder unbekannt `null`, daneben eigenes `class_status/class_reason`; `spatial` und `Q`. Die Beobachtung behält die echte Aufnahmezeit. |
| `estimate` | `estimate_ref, object_ref, observation_ref`: vollständige Schlüssel; `odometry_ref`: `FrameRef` oder unbelegt `null`; `time_basis_id, estimated_mono_s`: Uhr/Zeit oder unbekannt `null`; `spatial, uncertainty` und `Q`. `uncertainty` ist ein eigener Qualitäts-/Komponentenblock, bei fehlender Unsicherheit unbekannt, nie automatisch 0. `valid` verlangt belegte Herkunft und bekannte passende Unsicherheit. |
| `spatial` / `uncertainty` / Ziel-/Messkomponenten | Je `{coord_frame, calibration_version, values, status, reason}`. Bezüge Text oder unbekannt `null`; `values` bei `valid` nichtleere Map aus Komponentenname zu `{value: endliche Zahl, unit: m/rad/N/1}`, sonst `null`. Einheit muss zur im Quellen-/Kalibrierkontext deklarierten Komponente passen (etwa Raum m/rad, gemessene Kraft N); ohne Rückmeldung keine Kraft behaupten. Unsicherheiten nichtnegativ und mit denselben Einheiten wie die benannten Komponenten. Komponentenkennungen stammen aus dem expliziten Quellen-/Kalibrierkontext; keine Servo-/Achsen-/Geometriebelegung erfinden. Vorhandene Komponenten behaupten keine vollständige Schutzraumabdeckung. |
| Räumerfolgs-Nachweisdatensatz im gegebenen Kontext | `evidence_ref, operation_ref, kind, source_refs, time_basis_id, confirmed_mono_s` und `Q`; `kind=verification/travel_pose`; `source_refs` ist bei `valid` eine nichtleere Liste vollständiger `FrameRef`, sonst unbelegt `null`. Bestätigungen nachgewiesen, keine Erzeugung aus Timer/Befehl. Historische Nachweise bewahren ursprüngliche Qualität und Zuordnung. Politik-/Matrixnachweise haben denselben Referenzschlüsseltyp, aber eigene Arten `policy/sensor_requirements` im getrennten Nachweiskontext und sind keine Räumerfolgs-Nachweise. |

Objektwechsel beendet/abbricht den bisherigen Vorgang und erzeugt einen neuen
Schlüssel; keine Übernahme alter Griff-/Erfolgsbelege. B-Neustart setzt einen
Vorgang nicht automatisch fort. Wiederaufnahme nach Pause ist eine ausdrückliche
neue B-Entscheidung mit passenden getrennten Freigabeergebnissen; der Validator
prüft deklarierte Beziehungen, er führt keine Wiederaufnahme aus.

**Vollständige Nullbelegung bei belegter gültiger Inaktivität:**

| Felder in `clearing` | Belegung |
|---|---|
| `producer_id, producer_boot_id, time_basis_id` | Bekannte gebundene Kennungen, nicht `null`. |
| `status, reason, phase, execution_status, result` | `valid, null, inaktiv, beendet, offen`. |
| `operation_id, started_mono_s, updated_mono_s, object_ref` | Alle `null`. |
| `abort_reason, result_reason, interruption_reason, interrupted_mono_s` | Alle `null`. |
| `verification_ref, travel_pose_ref, observation, estimate` | Alle `null`. |

Bei gültiger Inaktivität ist zusätzlich **`arm.request=null`**: kein noch
frischer Wunsch zu einem früheren Vorgang bleibt aktuell verwendbar.
Ein als aktuell gelieferter alter Armwunsch ist dann ein Datenwiderspruch;
historische Wünsche dürfen nur mit ihrem alten Bezug als Diagnose bestehen.
Ein neuer Vorgang braucht eine neue `command_seq`, keine Reaktivierung des
vorherigen Wunsches. Diese Nullregel beweist weder Auftragsstornierung noch
mechanischen Stillstand und entfernt keine anderen unabhängigen Sperren.
Ohne Initialisierungs-/Bindungsbeleg `missing/unknown` mit Grund, niemals
erfundene gültige Inaktivität. Diese Wunschentwertung setzt **keine** unabhängig
gemeldeten Arm-/Kameramessungen, Ausgaben, Empfangsbestätigungen, Freigaben,
Sperrbilder oder Schutzpolitik zurück. Diese behalten ihre eigene Zuordnung;
Bezüge auf frühere Vorgänge sind als solche erkennbar, nicht aktueller Erfolg.

#### Armwunsch, wirkliche Ausgabe, Empfang und Messung

| Objekt | Pflichtfelder, Nullregeln und Qualitätsaussage |
|---|---|
| `arm.request` | Objekt oder kein verfügbarer Wunsch `null`. Objekt: `contract_version, robot_id, producer_id, producer_boot_id, command_seq, time_basis_id, generated_mono_s, valid_until_mono_s, operation_ref, object_ref, action, target`. Vollständige Herkunft und `CommandRef`; bekannte Vorgangs-/Objektbezüge für eine Räumaktion erforderlich. `action` nichtleerer fachlicher Code, `target` Komponentenblock oder bei zielwertfreier Aktion `null` mit ausdrücklich vereinbarter Aktionsbedeutung. `anschauen/ausrichten/greifen/ablegen/fahrstellung` sind Darstellungscodes, keine Gerätebefehle. Zuordnung, Frist, Duplikate, Rücklauf und Anti-Replay entsprechend V2; maximales Budget als gegebener Kontext, kein Default. |
| `motion.output` | Objekt oder bei fehlender Ausgabe `null`. `robot_id, producer_id, producer_boot_id, output_seq, time_basis_id, issued_mono_s, v_m_s, w_rad_s, request_ref, request_reason, evaluation_ref` und `Q`. Bei `valid` tatsächliche endliche SI-Ausgabe; sonst Werte `null`. `request_ref` vollständig oder eigenständiger Sicherheitshalt `null`; `request_reason` nichtleer genau bei Nullreferenz, sonst `null`. `evaluation_ref` bei bekannter zugeordneter Ausgabe verpflichtend. Keine Ausgabe aus Wunsch rekonstruieren. |
| `arm.output` | Objekt oder fehlend `null`. `robot_id, producer_id, producer_boot_id, output_seq, time_basis_id, issued_mono_s, action, target, command_ref, command_reason, operation_ref, object_ref, evaluation_ref` und `Q`. Tatsächlicher Ausgabebesitzer, nicht still der Freigabebesitzer; eigener `OutputRef`. `command_ref` vollständig oder eigenständiger Schutzauftrag `null`; `command_reason` nichtleer genau bei Nullreferenz, sonst `null`. Unbekannte Ausgabeaktion/-werte `null`. Vorgangs-/Objektbezug nur ohne entsprechenden Auftrag `null`. `evaluation_ref` bindet die Arm-Auswertung. Keine Aktion aus Wunsch/Phase ableiten. |
| `arm.ack` | Objekt oder keine Bestätigung `null`; `output_ref, time_basis_id, received_mono_s, status, reason`. Bei bestätigtem Empfang vollständiger `OutputRef` des tatsächlich empfangenen Armauftrags; bei belegter gemeinsamer Uhr `issued <= received <= generated`. Keine Bestätigung aus Sendeaufruf; Empfang ist weder Stellung noch Lastnachweis. |
| `arm.measured`, `arm.load`, `camera_pose` | Je Qualitätsblock `{status, reason, measurements}`; bei nicht verfügbaren Daten `measurements=null`. Bei `valid` nichtleere Liste unabhängiger Messdatensätze `{frame_ref, time_basis_id, captured_mono_s, received_mono_s, components, status, reason}`. `frame_ref` vollständig, Aufnahme/Empfang nach V1; `components` folgt obigem Komponentenblock. Last kann unbekannt sein; keine Last aus geschlossenem Greifer folgern. Kamera enthält eigenen Raum-/Kalibrierbezug; Armstellung allein bestätigt keine Kameraprojektion. |

#### Atomare Freigabe-/Ausgabe-/Sperrpakete nach A

Die öffentlichen Bereiche sind `motion.release`, `motion.blocks`,
`motion.output` sowie entsprechend `arm.release`, `arm.blocks`, `arm.output`.
Ein Paket gehört genau einer `domain`. Es wird vom Freigabebesitzer geliefert;
C erfindet keinen Besitzer und mischt keine jeweils neuesten Teilwerte.

| Teil | Pflichtfelder und Bindung |
|---|---|
| `motion.release` / `arm.release` | `owner_ref` = `{robot_id, producer_id, producer_boot_id}` oder unbekannt `null`; `decision_seq` eigene Sequenz oder unbekannt `null`; `evaluation_ref` vollständiger Schlüssel oder ohne Auswertung `null`; `time_basis_id, evaluated_mono_s`; `decision=allowed/blocked/unknown`; `request_ref, request_reason` bei motion bzw. `command_ref, command_reason` bei arm; `output_ref` voller Ausgabeschlüssel oder fehlend `null`; `output_reason` nichtleer genau bei fehlender Ausgabe, sonst `null`; `Q`. Wunschreferenz vollständig oder bei fehlendem Wunsch/eigenständigem Schutzauftrag `null`, zugehöriger Wunschgrund dann nichtleer, sonst `null`. Bei vorhandener Ausgabe müssen Referenz **und Wunschgrund** mit deren Belegung übereinstimmen; Qualitäts-`reason` ist davon getrennt. Nicht bekannte Zeit/Referenzfelder dürfen `null` sein; ein fehlender Besitzer verlangt `decision=unknown` und `Q=unknown/missing`, kein `allowed`. |
| Aktueller Verwendungsbezug | `motion.package_use`: Pflichtobjekt `{mode, reason, evaluation_ref}` außerhalb des unveränderlichen Auswertungspakets. `mode=current/historical/unknown`; bei `current` Grund `null`, sonst nichtleerer Grundcode. Vollständige Auswertungsreferenz muss auf das dargestellte Motion-Paket zeigen; unbekanntes Paket erlaubt `evaluation_ref=null` nur mit `mode=unknown` und Grund. Das Feld bewertet die Verwendung im konkreten äußeren Zustand, nicht rückwirkend die damals gemeldete Entscheidung. |
| `motion.blocks` / `arm.blocks` | `producer_id, producer_boot_id, seq, evaluation_ref, time_basis_id, evaluated_mono_s, entries, stop_latched, fault_latched` und `Q`. Sperrbildproduzent = Freigabebesitzer, eigene `seq`; Auswertungsreferenz identisch zum Ergebnis. Beide Latches sind `{value: bool oder null, status, reason}`. `entries` nur bei geliefertem gültigem vollständigem Bild Liste, sonst `null`. `[]` bedeutet nur dann keine gemeldete Sperre. Unbekannter Besitzer lässt Herkunft/Auswertung unbekannt, kein erfundenes leeres Bild. |
| Eintrag in `entries` | `block_ref, code, effect, frame_ref, time_basis_id, reported_mono_s, status, reason`. `block_ref` vollständige Herkunft; `code` nichtleer; `effect=motion/arm/both`; `frame_ref` vollständige Quelle oder bei Bedien-/Prozessursache bzw. unbelegtem Sensorbezug `null`. Berichtqualität getrennt von der Qualität seines Belegs; ein gültig gemeldeter Sensorfehler darf sich auf eine alte/fehlende Aufnahme beziehen. Fehlende Berichtzeit/Uhr bleibt unbekannt `null`. |
| `protection` | `{policy_id, policy_version, evidence_ref, status, reason}`; unbekannte Texte/Referenz `null`, `Q=unknown/missing` mit Grund. `evidence_ref` ist ein vollständiger `EvidenceRef` auf Politik-/Abnahmenachweis im getrennten gegebenen Kontext; diese Nachweisart ist kein Räumerfolgsbeleg. |
| `sensor_requirements` | Separater Qualitätsblock `{matrix_id, matrix_version, evidence_ref, status, reason}`; unbekannte Werte `null`; Nachweis ebenfalls getrennt von Räumerfolgsbelegen. Keine feste Quellen-/Grenzwertmatrix in C1 berechnen. |
| Bestehende Laufzeitprojektion | `runtime.evaluation_ref`: dieselbe vollständige aktuelle motion-Auswertung oder ohne belegtes aktuelles Paket `null`. `runtime.stop_latched/fault_latched` und die motion-bezogenen zusammenfassenden Gründe müssen genau deren aktuelles Sperrbild wiedergeben; kein drittes unabhängig zusammengesetztes Sperrbild und keine Projektion nur historischer Pakete als aktuelle Daten. Unbekannte Latches dürfen nicht als bestätigtes `false` erscheinen. `motor_enabled` bleibt grundsätzliche Bereitschaft, keine aus C berechnete konkrete Fahrt-/Armfreigabe. |

Für ein bekanntes Paket müssen Ergebnis, Sperrbild und vorhandene Ausgabe
**dieselbe vollständige `evaluation_ref`** tragen. Ergebnis-`owner_ref` stimmt
mit deren Produzentenanteilen überein; alle Paketzeiten gehören zur belegten
Uhr, `evaluated_mono_s <= issued_mono_s <= generated_mono_s` bei vorhandener
Ausgabe. `output_ref` zeigt exakt auf deren `OutputRef`, inklusive Ausgabestart
und Sequenz; Ausgabeproduzent darf vom Freigabebesitzer verschieden sein.
Wunschreferenz des Ergebnisses und der Ausgabe muss identisch sein.
Fehlende Ausgabe wird ausdrücklich im Ergebnis begründet; aus fehlender
Bestätigung wird kein ausgegebener Nullbefehl.

**Gesperrte Motion-Ausgabe:** Bei `motion.release.decision=blocked` verlangt
eine vorhandene als gültig/konsistent gemeldete endgültige Fahrtausgabe
**`v_m_s=0` und `w_rad_s=0`**, ohne Toleranz. Bereits eine einzelne von null
verschiedene Komponente ist ein Datenwiderspruch, auch bei passenden
Referenzen/Zeiten. Historische Kennzeichnung macht diese widersprüchliche
Kombination nicht zu einem konsistenten Paket. Bei fehlender Ausgabe bleiben
`motion.output=null`, `output_ref=null` und ein `output_reason` erhalten;
der Validator erzeugt keinen Nullbefehl und bestätigt keinen Stillstand.

**Fristbindung aktueller Erlaubnis:** Bei `package_use.mode=current` gilt:
Sobald `decision=allowed` oder eine vorhandene Fahrtausgabe von null
verschieden ist, ist ein vollständig auflösbarer `RequestRef` mit positiv bestätigtem
Bindungs-/Zeit-/Annahmekontext erforderlich. Die Verwendung darf nicht durch
einen Anti-Replay-Höchststand oder bestätigten Kontextwechsel überholt sein.
Alle Vergleiche erfolgen exakt nach V1a in belegter gemeinsamer Uhr:

`request.generated_mono_s <= evaluated_mono_s <= generated_mono_s < request.valid_until_mono_s`.

Bei vorhandener Ausgabe gilt zusätzlich
`evaluated_mono_s <= issued_mono_s <= generated_mono_s`; damit ist auch die
Ausgabe vor Ablauf. Eine aktuelle von null verschiedene Ausgabe verlangt
ein geliefertes `allowed`, keine unbekannte oder gesperrte Entscheidung.
An der Ablaufgrenze ist `current` bereits unzulässig. Fehlende Bindung,
Zeitbasis oder fehlender Fristnachweis erlauben keinen aktuellen
Verwendungsbezug: `mode=unknown` mit entsprechendem Grund statt Freigabe.
Das sind Beziehungen gelieferter Daten, keine Berechnung einer Motorfreigabe.

Ein früher erlaubtes Paket darf nach Ablauf unverändert als Diagnose mit
`package_use.mode=historical`, `reason=REQUEST_EXPIRED` und derselben
`evaluation_ref` erhalten bleiben. Es erscheint dann weder als aktuelle
Freigabe noch als aktuell ausgegebene Fahrbewegung, auch wenn seine historischen
Ausgabewerte ungleich null waren; keine Projektion in aktuelle Laufzeitfelder.
Die damalige Erlaubnis muss bereits zum Auswertungs-/Ausgabezeitpunkt einen
frischen Wunsch und passenden Kontext gehabt haben. Historisch etikettieren
repariert keine schon damals ungültige Erlaubnis. Alte Aufnahmen/Pakete werden
nicht umdatiert und Fristen nicht erneuert. Der Wechsel von `current` zu
`historical` gehört ausschließlich zum äußeren Verwendungsbezug; er ändert
nicht den unveränderlichen Inhalt einer `evaluation_ref` und braucht keinen
erfundenen neuen A-Auswertungsdatensatz. Eine tatsächlich neu gemeldete
Haltentscheidung benötigt dagegen ein neues atomares Paket.

Kontrollierte Nullwünsche für eigenständige aktuelle Halt-/Schutzpakete
bleiben nach der folgenden Regel zulässig. Ohne Wunsch darf daraus keine
aktuelle Fahrterlaubnis oder von null verschiedene Fahrtausgabe entstehen.
Ein `blocked`-Paket kann einen abgelaufenen Wunsch als Ablehnungsbezug nennen;
das behauptet keine erneute Verwendbarkeit dieses Wunsches.

**Kontrollierter Nullwunsch:** Vollständig belegter Sicherheitshalt ohne
Fahrwunsch: Ausgabe und Ergebnis jeweils `request_ref=null`, beide
`request_reason=NO_REQUEST`; vollständig belegter Armschutzauftrag ohne
Armwunsch entsprechend `command_ref=null`, beide
`command_reason=PROTECTIVE_ACTION_WITHOUT_REQUEST`. Ergebnis `blocked` und
Datenqualität `valid` sind dann vereinbar; reale Ausgabeidentität,
`output_ref` und atomare Auswertung bleiben verpflichtend. Ohne ausgegebenen
Armauftrag kann ein belegtes fehlendes Wunschangebot mit
`command_reason=NO_ARM_REQUEST` und gesondertem `output_reason` dargestellt
werden; es wird kein Schutzauftrag behauptet. Bloß verlorener/unbekannter
Wunschbezug ist dagegen `unknown` mit
`REQUEST_REFERENCE_UNKNOWN/COMMAND_REFERENCE_UNKNOWN`, kein belegter
Nullwunsch und kein `allowed`. Fehlender Pflichtschlüssel ist nie dasselbe
wie ein ausdrücklich belegter Nullwert. Der A-Begriff Schutzauftragsgrund
wird hier in eigene `request_reason/command_reason` gefasst, damit er nicht
mit Qualitäts-`reason=null` bei gültigen Daten kollidiert; diese konkrete
öffentliche Belegung ist von A/B noch zu bestätigen.

Jede Änderung an Ergebnis, Ausgabe, Sperrbild oder Verriegelungen verlangt
ein neues vollständiges Paket mit neuer `evaluation_seq`, auch bei gleichem
Wunsch. Gleiche Auswertungskennung mit geändertem Inhalt ist ungültig.
Fremde/mischende Teile machen die aktuelle Paketzuordnung `invalid`;
fehlende Teile/Belege `unknown/missing`. Unvollständige Pakete dürfen nicht
als aktuelle Freigabe erscheinen; alte vollständige Pakete bleiben Diagnose.
Ein von seinem Besitzer geliefertes `allowed` mit zugleich wirksamer gemeldeter
Sperre derselben Domäne ist ein Datenwiderspruch. `both` ist in beiden
Domänen wirksam, `motion` nur in motion und `arm` nur in arm. Derselbe
gemeinsame Grund erscheint mit gleicher `BlockRef` in beiden Paketen;
beide Pakete behalten ihre eigene `EvaluationRef`. STOPP-/Fehlerstatus und
aktive Gründe müssen innerhalb desselben Pakets konsistent sein.

Bei unbekanntem Armfreigabebesitzer bleibt `arm.release` als unbekanntes
Ergebnis mit unbekannter Besitzer-/Auswertungs-/Ausgabereferenz und Grund
darstellbar; eine bekannte `command_ref` bleibt erhalten. `arm.blocks` unbekannt mit
`entries=null` und unbekannten Latches. Ohne bekanntes Paket ist eine
zugehörige aktuelle Ausgabe unbekannt/fehlend; separat bekannte historische
Ausgaben/Messungen werden nicht gelöscht oder als neue Aktion umetikettiert.
Unbekannte Politik bleibt ebenfalls darstellbar; der Validator leitet daraus
weder Freigabe noch zusätzliche Sperren ab. Ein explizit gelieferter
Sicherheitshalt kann auch bei noch unbekannter Politik belegbar sein.

#### Vier knappe synthetische C1h-Darstellungen

Reine **tabellarische Projektionen** des Anhangs, keine v2-Fixtures oder
Gerätefreigaben. Alle Kennungen mit `demo-` und Zahlen sind erfunden;
Zeiten sind gleichuhrige illustrative Sekunden, keine Fristen/Grenzen.
Gemeinsames Gerät `RM02`, Zeitbasis `demo-clock`; Produzentenstarts sind
unabhängig. Die folgenden Kurzzeichen sind ausschließlich Lesemakros und
werden im späteren JSON stets als vollständige Referenzobjekte ausgegeben:

| Makro | Vollständig ausgeschriebener Schlüssel (Feldreihenfolge siehe Typ oben) |
|---|---|
| O / X | `OperationRef(RM02, demo-b, demo-b-start, demo-op)` / `ObjectRef(RM02, demo-objects, demo-objects-start, demo-object)` |
| F / D | `FrameRef(RM02, camera, demo-camera, demo-camera-start, demo-frame)` / `DetailRef(RM02, camera, demo-camera, demo-camera-start, demo-frame, demo-color, demo-data)` |
| Obs / Est | `ObservationRef(RM02, demo-objects, demo-objects-start, 1)` / `EstimateRef(RM02, demo-b, demo-b-start, 1)`; Est referenziert Obs und `FrameRef(RM02, odometry, demo-odom, demo-odom-start, demo-odom-frame)`. |
| Rn / Cn | `RequestRef(RM02, demo-b, demo-b-start, n)` / `CommandRef(RM02, demo-b-arm, demo-command-start, n)` |
| Mn / An | `EvaluationRef(RM02, demo-a, demo-a-start, motion, n)` / `EvaluationRef(RM02, demo-arm-check, demo-arm-check-start, arm, n)`; der fiktive Armbesitzer ist **keine** Rollenentscheidung für echte Geräte. |
| Un / Vn | `OutputRef(RM02, demo-motion-out, demo-motion-out-start, n)` / `OutputRef(RM02, demo-arm-out, demo-arm-out-start, n)` |
| P / T | `BlockRef(RM02, demo-actors, demo-actors-start, demo-person)` / `BlockRef(RM02, demo-quality, demo-quality-start, demo-depth-stale)` |
| EP / EM | `EvidenceRef(RM02, demo-policy, demo-policy-start, 1)` / `EvidenceRef(RM02, demo-matrix, demo-matrix-start, 1)`; rein hypothetische Politik-/Matrixbelege, keine Räumerfolgsbelege. |

In jeder Zeile sind die genannten bekannten Pakete vollständig und atomar
geliefert gedacht: Ergebnis und Sperrbild tragen Mn/An, die Ausgabe zusätzlich
Un/Vn; `output_ref` und Request-/Commandbezug stimmen überein. Alle übrigen
Pflichtfelder/Nullregeln gelten nach obigen Tabellen, werden hier zur Kürze
nicht wiederholt. `blocked` mit bestätigtem Fahr-Nullbefehl ist kein gemessener
Stillstand. Arm-`blocked` ohne neue Ausgabe hat `output_ref=null` und Grund.
Als aktuell bezeichnete Motion-Pakete besitzen `package_use.mode=current`
und den dazu benötigten gegebenen Kontext; insbesondere ist R11 im
synthetischen Ausrichtfall am Auswertungs- und Zustandszeitpunkt noch frisch.

| Fall / Vorgang | Beobachtung, Wunsch und tatsächliche Daten | Gelieferte Pakete, Sperren und Aussage |
|---|---|---|
| Anschauen, Zustand 10, Zeit 100 | O/X, `phase=anschauen`, `laufend/offen`; Obs mit F/D bei 99, Klasse unbekannt; C10 wünscht Blickstellung. Kamerapose `unknown`, Messwerte `null`. | M10: `blocked`, R10, U10 mit tatsächlicher Ausgabe 0/0. Arm-Besitzer unbekannt: Ergebnis `unknown`, keine An/Vn erfinden, Sperrbild `entries=null`. Politik-ID/-Version/Nachweis unbekannt mit Grund. Kein bestätigter Blick oder Griff. |
| Ausrichten, Zustand 11, Zeit 101 | Derselbe O/X und die unveränderte Obs-Aufnahmezeit 99; R11 verlangt gemeldete begrenzte Bewegung, `arm.request=null`, kein neuer Griff. Im Beispiel neue echte Arm-/Kameramessungen getrennt belegt; hypothetische `protection=(demo-policy, demo-v1, EP, valid)` und `sensor_requirements=(demo-matrix, demo-v1, EM, valid)`, jeweiliger Qualitätsgrund `null`. | M11: hypothetisch geliefert `allowed`, U11 mit tatsächlicher SI-Ausgabe; A11: `blocked`, `command_ref=null`, `command_reason=NO_ARM_REQUEST`, `output_ref=null`, `output_reason=blocked_no_output`. Variante: seitlicher Bereich unbelegt → **neues** M12 `blocked`, U12 mit 0/0 und gemeldeter Sperre `effect=motion`; nicht U12 mit altem Ergebnis M11 mischen. |
| Greifen, Zustand 12, Zeit 102 | O/X, `greifen`, `laufend/offen`; C12 ist Greifwunsch. Est führt Obs/F und eigenständige Odometriequelle, Schätzzeit 102, Unsicherheit `unknown`, Werte daher nicht gültig. Greiferstellung/Last `missing`, kein Griffnachweis. | M13: `blocked`, R12, U13 mit 0/0. A12: `blocked`, C12, `output_ref=null`, Grund `pose_feedback_missing`; keine V12 erfinden. Empfangsbestätigung fehlt. Ergebnis bleibt `offen`, Erfolgsbelege `null`. Phase/Wunsch erzeugen keine Armfreigabe. |
| Personenhalt, Zustand 13, Zeit 103 | Derselbe O/X, Phase `greifen` bleibt; `pausiert/offen`, `interruption_reason=person_hold`, Unterbrechungszeit 103. Letzte Beobachtung und unbekannte Last bleiben erhalten. | M14/A13: beide geliefert `blocked`; P und T mit `effect=both` in beiden Sperrbildern. U14 bestätigt nur Ausgabe 0/0; keine neue Armausgabe, Grund `blocked_no_output`. Verschwindet P, bleibt T; neuer Sperrstand verlangt neue vollständige Pakete. Zusätzlicher STOPP bleibt verriegelt. Armreaktion/Lasthalten physisch offen; keine automatische Rückfahrt. |

Die Ausrichtvariante ist ein eigener Alternativfall; ihre Auswertungen werden
nicht in die folgende Sequenz hineingemischt. Objekt-/Nachweisschlüssel bleiben
in allen vier Fällen unabhängig vom äußeren Zustand. Kein Beispiel setzt
erfolgreiches Räumen voraus; dafür wären die zwei getrennten bestätigten
Erfolgsbelege zu O erforderlich.

**Gezielte Konsistenz-/Fristgegenproben zu den nativen P1-Befunden:**
Unabhängige rein synthetische Tabellenfälle, sonst passende unveränderte
Schlüssel/Uhr/Kontexte; keine realen Grenzwerte. Ein Testwunsch wurde vor
100 erzeugt und läuft exakt bei 101 ab, das Testpaket wird bei 100 ausgewertet
und ausgegeben. Eine eventuell andere Zustandszeit steht in der Tabelle.

| Fall | Gelieferter Verwendungsbezug / Ausgabe | Erwartete Datenbewertung |
|---|---|---|
| `blocked`, Zustand 100 | `current`, tatsächliche Ausgabe `(0, 0)` | Positiv: konsistente Nullausgabe; kein gemessener Stillstand behauptet. |
| `blocked`, Zustand 100 | `current`, `(0.1, 0)` oder `(0, 0.2)` | Zwei negative Varianten: jeweils Datenwiderspruch, trotz passender Referenzen. |
| `allowed`, Zustand 100.5 | `current`, tatsächliche Ausgabe `(0.1, 0)` | Positiv bei belegtem Annahmekontext: Auswertung und Zustand vor Ablauf. |
| `allowed`, Zustand 101 bzw. 102 | `current`, dasselbe unveränderte Paket mit `(0.1, 0)` | Negativ an und nach Ablauf; keine aktuelle Freigabe/fahrende Ausgabe. |
| Dasselbe bei 100 erlaubte Paket, Zustand 102 | `historical`, `reason=REQUEST_EXPIRED`, gleiche Auswertungs-/Ausgabeschlüssel | Positiv ausschließlich historische Diagnose; keine aktuelle Laufzeitprojektion oder erneute Verwendung. |
| Erst bei 101 ausgewertetes `allowed` | Auch `historical` im Zustand 102 | Negativ als gültige Erlaubnis: Wunsch war bereits bei Auswertung abgelaufen. |
| Eigenständiger Halt ohne Wunsch | `current`, `blocked`, tatsächliche Ausgabe `(0, 0)`, beide `request_ref=null`, beide `request_reason=NO_REQUEST` | Positiv bei ansonsten vollständigem Paket; kein erfundener Frist-/Wunschbezug. |

## Abhängigkeit #8: begrenztes C1-Tor, offenes Schutztor

**Jetzt beschließbar:** Identitäts- und Zeitbezüge, Qualitäts-/Nullregeln,
Vorgang/Objekt/Framezuordnung, getrennte Wünsche/Ausgaben/Messungen/Freigaben,
Unterphase/Pause/Ergebnis/Abbruch und gleichzeitige Sperrgründe. Synthetische
Fälle Anschauen, Ausrichten, Greifen und Personenhalt aus C1h müssen vollständig
darstellbar sein. Mehrere Sperren verschwinden nicht gemeinsam, wenn nur eine
Ursache endet. Diese Datenstruktur hängt nicht von einer bereits vorhandenen
echten Greiferstellung oder freigegebenen Räumfahrt ab.

**C1 darf nicht entscheiden:** Akteurserkennung abschalten, Schutzraum oder
Pflichtquellen festsetzen, unbelegte Zeit-/Geometriegrenzen freigeben,
Odometriefortschreibung als Schutzersatz zulassen oder STOPP-/Lastverhalten
eines Arms erfinden. Der bisherige Schutzstand aus #8/gemeinsamen Regeln gilt
als Referenz; ein Personenhaltbeispiel bedeutet keine neue Eigentümerentscheidung.
[PR #126](https://github.com/BBS-GuT/smartcity-roboter/pull/126) behauptet auf Head
`ec3547924e0ed7d43814ea9b560863dcaf3e0e31` eine Eigentümerentscheidung zur
Akteursabschaltung. Das ist für diesen Auftrag **unbestätigt**, keine hier
übernommene Nutzeranweisung und kein Nachweis einer geänderten Schutzpolitik.

Die **Datenannahme** kann auf diesem begrenzten Umfang erfolgen, wenn sie den
offenen Politik-/Gerätestatus ausdrücklich mitführt. Die **Freigabe realer
Räum-/Armhandlungen** bleibt von aktualisiertem Ziel-/Abnahmecommit zu #8,
benanntem Freigabebesitzer, Pflichtmatrix, gemessenen Räumen/Grenzen,
STOPP-/Watchdog-/Stellungs-/Lastnachweisen abhängig. Unabhängiger
Überwegschwenk bleibt #70. C1 schließt weder #8 noch diese Abnahmen.

## V4: Gemeinsame Version und Migration

Aus Rolle C für Auftrag 1 angenommen: Version **2.0** für den noch nicht
implementiert angenommenen öffentlichen Vertrag:
neue Pflichtidentitäten, geänderte Uhrenbedeutung, eigenständiger Wunsch und
erweiterte geschlossene Strukturen sind inkompatibel mit Entwurf 1.0.
Kein stilles Erweitern unter gleicher Version. `contract_version` des
Fahr-/Armwunsches entspricht `schema_version` des einbettenden Zustands.

Nach #14 im Sammelbranch neue `schemas/grundbetrieb-v2.schema.json` anlegen;
das tatsächlich veröffentlichte historische v1-Schema aus `88a82d4`
erhalten bzw. wiederherstellen, nicht den um Pflichtfelder erweiterten
C1c/C1d-Zwischenstand weiterhin als v1 veröffentlichen.
Der Python-Vertrag und die aktiven sieben Zustandsfixtures werden auf 2.0
umgestellt; Version 1.0 und unbekannte Versionen werden dort ausdrücklich
abgelehnt. Kein Parallelbetrieb zweier aktueller Verträge und kein Adapter,
der unbekannte Herkunftskennungen, Fristen oder gültig leere Historie erfindet.
Altdaten bleiben alte Diagnosebelege, niemals automatisch aktuelle 2.0-Daten.

Alle Änderungen bleiben bis zum vollständigen Stand im Draft-Gesamt-PR.
Schema beschreibt die Struktur; Python prüft dokumentierte Beziehungen und
gegebenen Kontext. Keine unbehauptete Schema-/Python-Gleichwertigkeit für
zeit- oder registerabhängige Regeln. Tests benennen diese Grenze.
O hält vor C2 einen konkreten Annahmecommit mit Version, angenommenem Umfang,
Zustimmung der betroffenen Rollen und ausdrücklich offenen Gerätenachweisen
fest. Ein grüner Bot-/CI-Lauf ersetzt die fachliche Annahme nicht.

## Explizite Fundamentannahme aus Rolle C

**C nimmt V1/V1a/V4 einschließlich der bekannten nativen Präzisierungen als
erste Implementierungsgrundlage für Auftrag 1 an.** Das umfasst gemeinsame
Identitäten/Uhrenbedeutung, Version 2.0 und Migration, exakten Integer-ns-/
Decimal-Bau-/JSON-Pfad, Endlichkeitsprüfung in Zeit- und Nichtzeitfeldern
sowie den ausdrücklich erlaubten Test-Loader-/Zeit-Assertion-Umfang.
Es verbleibt aus C **keine blockierende Fundamententscheidung** für diesen
abgegrenzten Auftrag. Die Referenz dieser Annahme ist der Dokumentstand
`68c1cf594bd43c2d8f62eeeb1e3df4908e147d94` mit den in dieser Lieferung
ausdrücklich aktualisierten Annahmestatusangaben; der Liefercommit steht im PR.

O hat Auftrag 1 als [#149](https://github.com/BBS-GuT/smartcity-roboter/issues/149)
an einen eigenen alleinigen Produkt-/Schema-/Vertrags-Schreiber vergeben,
mit fertig getestetem C1d-Stack `43c40e3` als Ausgangspunkt (Managerübergabe).
Diese Vergabe gibt diesem C-Fachchat keine weiteren Dateien frei.
Vollständige V3-Feldbelegung für Auftrag 5,
reale Geräte-/Uhrbindungsnachweise, konkrete Schutzpolitik, Fristen und
Brokerwerte sind **keine Voraussetzung dieser Fundamentumsetzung**.
Fehlende reale Daten werden gemäß Vertrag ehrlich als unbekannt/fehlend
dargestellt; synthetische Prüfkontexte sind keine Gerätefreigabe.

Diese Annahme gilt der Semantik zur Umsetzung, nicht einem schon
implementierten Gesamtvertrag. Native Prüfung bleibt unabhängig; zweite
fachliche Annahme durch A/B/C/O erfolgt erst am tatsächlichen vollständigen
Gesamtcommit. V3 wird separat zusammengeführt: A-Bindung atomarer
Freigabe-/Ausgabe-/Sperrpakete und B-Unterbrechungs-/Ergebnis-/Nachweisfelder
sind dabei zu berücksichtigen; `effect`/`scope` werden nicht konkurrierend
als zwei öffentliche Belegungen umgesetzt.

## Sechs kleine Folgeaufträge nach #14

Auftrag 1 ist als #149 vergeben; die weiteren Aufträge bleiben gesondert
zuzuteilen. O benennt je Auftrag einen C-Dateibesitzer und stimmt
A/B-Details ab; **streng nacheinander**, da Bibliothek/Schema/Doku gemeinsam
sind. Grundlage ist jeweils der integrierte Vorgänger im Sammelbranch.
Alle Aufträge: Refs #3 und zugehöriges Entwurfsissue, ROS-unabhängig,
kein C2-Produzent, ROS-Adapter, Panelumbau, MQTT-Transport oder Aktorzugriff.

1. **Version/Zeitbasis/JSON-Pfad als Fundament (A/B laut O und C angenommen;
   Umsetzung vergeben als #149 auf C1d-Stack).**
   Dateien: `lib/grundbetrieb_vertrag.py` nur Version/Kopf/Quellenidentitäten
   und monotone Quellenaufnahme sowie Zahlenprüfung, exakter Bau-/JSON-Pfad
   und Altersrechnung nach V1a; neue `schemas/grundbetrieb-v2.schema.json`;
   `schemas/grundbetrieb-v1.schema.json` ausschließlich historische
   Wiederherstellung aus `88a82d4` gemäß aktuellem Auftrag #149;
   `docs/schnittstellen-grundbetrieb.md` nur Version/Kopf/Quellen;
   sieben bestehende `tests/fixtures/grundbetrieb/*.json`;
   **ausdrückliche Dateiübernahme für `tests/test_zustandsvertrag.py`:**
   Version/Schemapfad/Fixtureannahmen **und bestehende Test-Loader sowie alle
   betroffenen zeitbezogenen Bauwerte, Rechenoperationen und Assertions**.
   Den Fixturehelper und weitere Ladepfade auf exaktes Lesen umstellen;
   beim Prüfen gültiger Zustände `lade_json()` statt Standard-`json.load()`
   verwenden. Ausdrücklich `StartUndSequenz.test_alter_nach_monotoner_uhr`:
   Addition `+0.25` und erwarteten Alterswert auf `Decimal("0.25")` umstellen,
   ebenso weitere Float-Zeitliterale; Fehlererwartungen bleiben erhalten.
   neue `tests/test_c1_identitaet_zeitbasis.py`.
   Positive/negative Kontrollen: C-Neustart bei gleichem Sensorstart/Uhr,
   unabhängiger Sensorstart, falsche Uhr, fehlende Kennung, Quellenalias,
   Zukunft, v1/unknown-Version ablehnen. Keine Regression der #11–#14-Regeln.
   Falls deren neue Testfixtures angepasst werden müssen, O übernimmt gezielt
   `tests/test_c1_empfangszeit.py`/`tests/test_c1_quellen.py` für neue Pflichtfelder;
   Assertions nicht lockern. `tests/test_c1_alter.py` nur positive Zeitliterale/
   Ergebnisdarstellung auf exakte Bauwerte umstellen und Float-Ablehnung ergänzen;
   vorhandene negativen Zeitfälle beibehalten. In der neuen Testdatei zusätzlich
   Dezimal-/Exponententokens, Raster-/Bereichsgrenze, direkte Float-/Bool-Ablehnung,
   kein Fristgewinn durch Lesen/Schreiben und numerischen Decimal-Rundlauf
   prüfen. Zusätzlich alle vier nichtendlichen Decimal-Bauwerte aus V1a je
   einmal in einem Zeitfeld und einem Nichtzeitfeld prüfen (acht Negativfälle,
   etwa `generated_mono_s` und `motion.measured_v_m_s.value`). Erwartung:
   gezielter Validierungsfehler und verweigerte Ausgabe, kein
   `decimal.InvalidOperation`. Endliche passende Decimals bleiben als positive
   Kontrolle gültig; vorhandene NaN-/Unendlich-Floatfälle beibehalten.
   Keine neue Abhängigkeit oder pauschale Testumschreibung.
   Noch kein vollständiger 2.0-Annahmestand.
2. **Eindeutige Details (#15, C/O).**
   Dateien: dieselbe Bibliothek nur Details/gegebenes historisches Register;
   v2-Schema nur Detaildefinitionen; Vertragsdoku nur Details;
   neue `tests/test_c1_detailreferenzen.py`, neue
   `tests/fixtures/c1_details/*.json`; bestehende Zustandsfixtures nur enthaltene
   Detailreferenzen. Prüfen: älterer gültiger und alter Frame, fremde Quelle,
   widersprüchliche Metadaten, anderer Produzentenstart, fehlender historischer
   Beleg, Uhrwechsel, C-Neustart bewahrt Aufnahmeschlüssel. Grenzen explizit
   vorgegeben, kein laufender Payloadspeicher/Broker.
3. **Eigenständiger Fahrwunsch (#16, C mit A/B/O).**
   Bibliothek nur Requesttyp und kontextuelle Annahmeprüfung; v2-Schema mit
   wiederverwendeter Requestdefinition und separat adressierbarem Einstieg;
   Vertragsdoku nur Wunsch; bestehende Zustandsfixtures nur `motion.request`;
   neue `tests/test_c1_fahrwunsch.py`, `tests/fixtures/c1_requests/*.json`.
   Prüfen: eingebetteter/separater Wunsch identisch, Duplikat/Mutationsversuch,
   Replay, exakte ns-Maximaldauer und Fristgrenze über den öffentlichen
   JSON- und direkten Baupfad, Zukunft, falsches Gerät/Start/Uhr,
   A-Neubindung und Zeitregression trotz höherer Sequenz. Den Umordnungsfall
   8 → abgelaufene 10 → noch frische 9 sowie eine danach zulässige 11 prüfen;
   ansonsten ungültige hohe Sequenzen dürfen den Höchststand nicht erhöhen.
   **C-Neustart positiv/negativ:** Im Umordnungsfall nach beobachteter 10 nur
   äußeres C-`boot_id` wechseln und Zustands-`seq` bei 0 beginnen lassen;
   A-Bindung, B-Tupel, Uhr und Prüfzeit bleiben gleich. Wunsch 9 bleibt danach
   Replay, Höchststand/Erzeugungszeit/Inhaltsbezug bleiben unverändert.
   Wunsch 11 (Erzeugung 100.5, Ablauf 101.6, jetzt 101, Budget 2 s) ist
   danach als neuer Wunsch zuordenbar. Ergänzend bleibt eine identische
   Wiederholung eines noch frischen Wunsches über den C-Wechsel ein Duplikat,
   ohne Fristverlängerung oder neuen Manöverbeginn. Kein A-Neustart simulieren.
   Nach Ablauf bleiben Annahmepaar und Anti-Replay-Höchststand erhalten;
   lediglich abgelaufene, ansonsten gültige Eingänge erhöhen nur den Höchststand
   und sperren überholte Wünsche, niemals verlängern sie eine Frist.
   Kontext/Budget werden im Test übergeben; keine Motorentscheidung.
4. **Begrenzte Historie (#17, C mit B/O).**
   Bibliothek nur Historienvalidierung; v2-Schema/Doku nur `route.history`;
   bestehende Zustandsfixtures nur dieses Feld; neue
   `tests/test_c1_fahrhistorie.py`, `tests/fixtures/c1_history/*.json`.
   Prüfen: gültig leer versus fehlend, 16/17 Einträge, sichtbare Verwerfung,
   doppelte/rückläufige Sequenz/Zeit, Sequenzlücke `[0, 2]`, falsche Zuordnung
   älteste Sequenz/Verwerfungszahl, gültige Folge 1–16 mit Verwerfungszahl 1,
   fremde Karte/Uhr, B-Reset und reiner
   C-Neustart ohne neue Einträge. Gegebene synthetische Kartenreferenzen;
   keine Erzeugung bestätigter Fahrten oder B2-Wegwahl implementieren.
5. **Räum-/Armzustand als Daten (#18, C mit A/B/O).**
   Bibliothek, v2-Schema und Vertragsdoku nur V3-Bereiche; bestehende
   Zustandsfixtures nur neue Felder; neue `tests/test_c1_raeumzustand.py`,
   `tests/fixtures/c1_clearing/*.json`.
   Vorher den konkreten V3a-Datenanhang durch A/B/O bestätigen lassen;
   diese C-Spezifikation behauptet deren Zustimmung nicht.
   Prüfen: vier C1h-Fälle, Pause versus Abbruch, Objekt-/Framewechsel,
   fehlende Arm-/Kameramessung bleibt unbekannt, Schätzung keine Beobachtung,
   unbekannte Schutzpolitik darstellbar, gleichzeitige Sperren und getrennte
   Fahrt-/Armresultate, vollständige inaktive Nullbelegung und Erfolgsbezüge.
   Atomare Paketbindung positiv bei gleicher Requestkennung/neuer Auswertung;
   negativ gemischte evaluation_ref, fremder Ausgabestart/output_seq,
   unpassende output_ref, fremdes Sperrbild und scope/drive statt effect/motion.
   Zusätzlich `blocked` mit linearer oder drehender Nichtnullausgabe negativ;
   erlaubtes Paket bei 100/Wunschablauf 101 als `current` im Zustand 101/102
   negativ, als ausdrücklich `historical` im Zustand 102 positiv. Bei schon
   zur Auswertung abgelaufenem Wunsch keine gültige historische Erlaubnis.
   Historischer Verwendungsbezug verändert weder Paketidentität noch Frist;
   kontrollierter Nullwunsch-Halt und fehlende Ausgabe bleiben darstellbar.
   Unbekannter Armbesitzer bleibt unbekannt, beide Sperrwirkungen behalten
   ihre vollständigen Quellenbezüge. Keine Freigabe aus Phase ableiten; keine physische
   Pflichtmatrix erzwingen. Blockiert nur durch fehlende Datenentscheidung,
   nicht durch noch ausstehende echte Gerätefahrt.
6. **Gemeinsame Annahme/Fixtures (C/O, A/B beteiligen).**
   Dateien: `docs/schnittstellen-grundbetrieb.md` Annahme/Versionsübersicht,
   neue `tests/test_c1_annahme.py`; die sieben Zustandsfixtures nur für
   abschließende Konsistenz. Keine neue Produktfunktion.
   Alle aktiven synthetischen Fixtures gegen v2-Schema und Python prüfen,
   Request-Einstieg separat; v1/unknown-Version negativ; gleicher Zustand
   behält fachlichen Inhalt bei JSON-Rundlauf. Betroffene vorhandene
   Vertragstests und regulären D1-Runner ausführen, Fehler/Skips ehrlich nennen.
   O dokumentiert Annahmecommit und offene Nachweise; aktueller nativer
   Review/CI am Gesamt-Head erforderlich. Nur O koordiniert Integration.

Diese Dateiumfänge sind Vorschläge zur späteren ausdrücklichen Reservierung,
keine jetzige Schreibfreigabe. Gemeinsame Fixtureänderungen je Schritt nur
für dessen neue Felder; unbekannte reale Messwerte bleiben unbekannt.

## N: Tatsächlich noch erforderliche Fachentscheidungen für den Manager

1. **A/B/C/O:** V1/V1a/V4 sind als erste Implementierungsgrundlage angenommen
   (A/B laut O, C ausdrücklich oben); Auftrag 1 ist dadurch nicht mehr fachlich
   blockiert. V2/V3 und genaue Feld-/Codebelegung für spätere Aufträge weiter
   abstimmen; zustimmende Personen und späteren Gesamtannahmecommit benennen.
   A/B sind den oben
   benannten Fachchats, C diesem Chat und O dem C1-Manager zugeteilt.
   A-/B-Annahmebedingungen zunächst abgleichen; tatsächliche Zustimmung zum
   implementierten Gesamtcommit bleibt die gesonderte zweite Stufe.
2. **A/B/C:** zuständige Produzenten, Start-/Uhrbindung und deren Nachweisweg
   festlegen; gemeinsame Uhr samt Suspendverhalten und Sensoreigenzeit-Abbildung
   nachweisen. C1 definiert Felder, C2/A/B liefern später reale Bindung.
3. **A/B/O:** maximale Wunschdauer und Prüf-/Senderaten anhand Latenz/
   Haltverfahren festlegen. Kein Zahlenstandard aus synthetischen Beispielen.
4. **B/C/O:** 16er-Puffer, Kartenwechsel-/Lückenregel und Umfang im Zustand
   bestätigen; B liefert verbindliche Kartenkennungen und Abschlusskriterien.
   C/B/E mit Partnern: Detailformate, Paarung, Raten, Frischebudgets und
   Metadatenaufbewahrung vereinbaren; echte Brokerdaten bleiben separat.
5. **O mit Carsten/A/B, #8:** behauptete Akteursentscheidung aus #126 klären,
   Schutzpolitik und aktualisierten Ziel-/Abnahmecommit benennen. C1 benötigt
   die vereinbarte Darstellung eines offenen Politikstatus; reale Freigabe
   benötigt die tatsächlich bestätigte Politik.
6. **A/B/E:** Armfreigabebesitzer benennen; Pflichtquellen je Bewegung/Armphase,
   Odometriegrenzen, echte Stellungs-/Lastbelege, sichere Unterbrechung und
   Wiederaufnahme festlegen. Gemessene Hülle/Bewegungs-/Greif-/Ablageräume,
   Kalibrierung, harte Greifergrenze sowie STOPP-/Watchdognachweise bleiben
   Geräteaufgaben (#37/#38/#58/#75/#79). Diese Werte blockieren Gerätefreigabe,
   nicht die ehrliche Darstellung fehlender Nachweise im C1-Vertrag.

Die vorliegende Lieferung ändert ausschließlich Dokumentation. Dokument-/Link-
und gegebenenfalls JSON-Prüfung sind keine Software-, ROS-, Geräte- oder
Brokerabnahme. Native Codeprüfung übernimmt ausschließlich der native Reviewer.
