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
den alten v1-Schemaentwurf als ausdrücklich historischen Stand erhalten.
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

O kann Auftrag 1 nach dem fertig integrierten #14-Stand mit eigener enger
Dateireservierung vergeben. Vollständige V3-Feldbelegung für Auftrag 5,
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

Noch nicht vergeben. O benennt je Auftrag einen C-Dateibesitzer und stimmt
A/B-Details ab; **streng nacheinander**, da Bibliothek/Schema/Doku gemeinsam
sind. Grundlage ist jeweils der integrierte Vorgänger im Sammelbranch.
Alle Aufträge: Refs #3 und zugehöriges Entwurfsissue, ROS-unabhängig,
kein C2-Produzent, ROS-Adapter, Panelumbau, MQTT-Transport oder Aktorzugriff.

1. **Version/Zeitbasis/JSON-Pfad als Fundament (A/B laut O und C angenommen;
   O vergibt nach #14).**
   Dateien: `lib/grundbetrieb_vertrag.py` nur Version/Kopf/Quellenidentitäten
   und monotone Quellenaufnahme sowie Zahlenprüfung, exakter Bau-/JSON-Pfad
   und Altersrechnung nach V1a; neue `schemas/grundbetrieb-v2.schema.json`;
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
   Vorher genaue Feld-/Codebelegung von V3 durch A/B/C/O annehmen.
   Prüfen: vier C1h-Fälle, Pause versus Abbruch, Objekt-/Framewechsel,
   fehlende Arm-/Kameramessung bleibt unbekannt, Schätzung keine Beobachtung,
   unbekannte Schutzpolitik darstellbar, gleichzeitige Sperren und getrennte
   Fahrt-/Armresultate. Keine Freigabe aus Phase ableiten; keine physische
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
