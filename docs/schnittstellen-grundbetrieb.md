# Schnittstelle Grundbetrieb: gemeinsamer Datenvertrag v2.0

**Auftrag:** C1 ([#14](https://github.com/davidheinrich73/smartcity-roboter/issues/14)). **Bezug:** [Zieldefinition](zieldefinition-grundbetrieb.md) §5–7, GB-12 bis GB-18.
**Status:** Integrierter 2.0-Lieferkandidat fuer [C1 #3](https://github.com/BBS-GuT/smartcity-roboter/issues/3), gemeinsam ueber [PR #134](https://github.com/BBS-GuT/smartcity-roboter/pull/134). Details, eigenstaendiger Fahrwunsch, Historie sowie Raeum-/Arm- und Schutzdaten sind im Modell, Schema und ROS-unabhaengigen Python-Pfad enthalten. Native Abschlusspruefung, CI und die A/B/C/O-Gesamtannahme am konkreten Liefercommit werden vor Freigabe getrennt dokumentiert; synthetische Softwaretests ersetzen keine reale Geraeteabnahme.

Ein Roboter erzeugt **einen** Zustandsdatensatz. Panel und MQTT lesen genau diesen Datensatz. Das Panel leitet daraus keine eigene Fahrentscheidung und keinen eigenen Haltegrund ab.

| Datei | Inhalt |
|---|---|
| `lib/grundbetrieb_vertrag.py` | Prüfung (Struktur + fachliche Regeln R1–R11), strenges JSON, Startkennung/Sequenz, Vergleich, Datenalter. Nur Python-Standardbibliothek, kein ROS. |
| `schemas/grundbetrieb-v2.schema.json` | Aktives JSON-Schema (Draft 2020-12) der **Struktur** für externe Leser (z. B. Dashboard). Die Regeln R1–R11 stehen nur in der Python-Prüfung. |
| `tests/fixtures/grundbetrieb/*.json` | Synthetische Beispiele, **keine** Messwerte eines Geräts. |
| `tests/test_zustandsvertrag.py` | Tests ohne ROS, Roboter und Broker. Schemafälle benötigen `jsonschema`; eine ausgelassene Schemaprüfung ist kein vollständiger Nachweis. |

## Grundregeln

- **Einheiten:** SI. Die Einheit steht im Feldnamen: `_m` Meter, `_s` Sekunden, `_m_s` m/s, `_rad` rad, `_rad_s` rad/s, `_hz` Hz, `_v` Volt.
- **Nicht verfügbar** ist `null` mit Status. Eine fehlende oder unbekannte Messung wird nie zu einer gültigen `0`. `NaN` und Unendlich sind verboten (R1).
- **Status** jeder Quelle und jedes Messwerts:

  | Status | Bedeutung |
  |---|---|
  | `valid` | gemessen, aktuell, plausibel |
  | `unknown` | noch nicht bestimmbar (z. B. Orientierung vor dem ersten Knoten) |
  | `invalid` | Messung da, aber unbrauchbar (z. B. Zeitbezug passt nicht) |
  | `stale` | Messung da, aber zu alt |
  | `missing` | keine Messung |

  „Frei“ ist **kein** Status. Ein nachgewiesen freier Fahrbereich ist `obstacles.corridor = "free"` mit gültiger Quelle. Unbekannt ist `"unknown"`.
- **Messwert-Objekt** `{value, status, source}`: Bei `status = valid` ist `value` eine Zahl und `source` ein nicht leerer, registrierter Schlüssel unter `sensors`, sonst ist `value` `null` (R2). Eine angegebene Quelle muss auch bei nicht verfügbarem Messwert ein registrierter Schlüssel sein; `source = null` bleibt dann erlaubt. Der Befehl ersetzt keine Messung.
- **Identität:** `robot_id` (RM01–RM04) + `boot_id` (Cs Zustandsproduzentenstart) + `seq` (ab 0 pro C-Start). Eine Sequenz gilt nur zusammen mit Gerät und C-Start. Ein C-Neustart ist keine Fortsetzung (`vergleiche()` → `anderer_start`), erzeugt aber keine neue Sensoraufnahme. Quellen bewahren ihren eigenständigen `producer_id`/`producer_boot_id` und Uhrenbezug.
- **Zeit:** `generated_at` ist UTC im Format `YYYY-MM-DDTHH:MM:SS[.Bruchteil]Z` (RFC 3339, nur abschließendes `Z`, ASCII-Ziffern). Kalenderdatum einschließlich Schaltjahr muss gültig sein (Jahr 0001–9999); Stunden 00–23, Minuten und Sekunden 00–59. Optional sind 1–9 Nachkommastellen erlaubt, Schaltsekunden nicht. `generated_mono_s` gehört zur expliziten lokalen Geräte-Uhreninstanz `time_basis_id` für lokale Altersprüfung (`alter_s()`). Sie ist keine pro Prozess auf null gesetzte Stoppuhr. `time_sync.status` zeigt, ob `generated_at` mit anderen Geräten vergleichbar ist. `unsynced` bleibt sichtbar.
- **Änderung** eines Betriebs- oder Kommunikationszustands = neuer Datensatz mit neuer `seq`.
- **Version:** `schema_version` = `"2.0"`. Neue Pflichtfelder, entfernte Felder oder neue Aufzählungswerte (z. B. Haltegründe) erhöhen die Version.

## Felder

### Kopf

| Feld | Typ | Bedeutung |
|---|---|---|
| `schema_version` | `"2.0"` | aktiver Fundamentstand; 1.0/unbekannt werden abgelehnt |
| `robot_id` | `RM01`…`RM04` | Gerät |
| `boot_id` | Text ≥ 8 | eindeutig pro C-Zustandsproduzentenstart, getrennt von Sensorstart/Uhr |
| `seq` | ganze Zahl ≥ 0 | Sequenz in diesem Start |
| `generated_at` | Text UTC | Erzeugungszeit (Wanduhr) |
| `generated_mono_s` | exakte Sekundenzahl | monotone Erzeugung in `time_basis_id` |
| `time_basis_id` | nichtleerer Text | systemweite lokale Uhreninstanz: Uhrtyp, Ursprung und Suspendverhalten; Wechsel bei Uhrreset/Uhrenraumwechsel, nicht allein bei Prozessstart |
| `time_sync` | `{status: synced\|unsynced\|unknown, source}` | Zeitsynchronisation |
| `software_version`, `map_version`, `config_version` | Text oder `null` | Commit, Straßenkarte, Gerätekonfiguration |

### `runtime` – Betrieb (Produzent: A, Freigabeergebnis)

| Feld | Typ | Bedeutung |
|---|---|---|
| `mode` | `"GRUNDBETRIEB"` | andere Modi (Szenarien) sind nicht Teil von v2 |
| `state` | `GESTOPPT`, `TEST`, `BEREIT`, `SPURFOLGEN`, `KREUZUNG_ANNAEHERN`, `VERKEHRSHALT`, `MANOEVER`, `AUSFAHRT_BESTAETIGEN`, `FEHLER` | Betriebszustand (Zieldefinition §6) |
| `motor_enabled` | bool | Motorweg grundsätzlich freigegeben |
| `stop_latched` | bool oder `null` | Projektion des aktuellen gemeldeten Sperrbildes; ohne aktuellen Beleg `null` |
| `fault_latched` | bool oder `null` | Projektion der aktuellen Fehlersperre; ohne aktuellen Beleg `null` |
| `hold_reasons` | Liste, eindeutig | **alle** wirksamen Haltegründe, getrennt (z. B. `RED_LIGHT` und `FRONT_BLOCKED` gleichzeitig) |
| `faults` | Liste Text | Fehlerbeschreibungen |
| `evaluation_ref` | vollstaendige Auswertungsreferenz oder `null` | Identitaet des aktuellen Motion-Pakets; kein Bezug auf nur historische Pakete |

Haltegründe: `STOP_LATCHED`, `FAULT`, `TEST_MODE`, `NO_REQUEST`, `RED_LIGHT`, `YELLOW_LIGHT`, `SIGNAL_UNKNOWN`, `STOP_SIGN`, `CROSSING_OCCUPIED`, `FRONT_BLOCKED`, `DISTANCE_LOCK`, `SENSOR_MISSING`, `SENSOR_STALE`, `SENSOR_INVALID`, `LINE_LOST`, `LOCALIZATION_UNKNOWN`, `MANEUVER_FAILED`.

### `motion` – Bewegung

| Feld | Typ | Produzent | Bedeutung |
|---|---|---|---|
| `request` | Objekt oder `null` | B → A | Eigenstaendiger vollstaendiger 13-Feld-Fahrwunsch nach nachfolgendem Gesamtmodell; eingebettet unveraendert. **Keine** Motorfreigabe. |
| `output` | Ausgabeobjekt oder `null` | Ausgabebesitzer | Werte `v_m_s, w_rad_s`, Ausgabe-/Wunsch-/Auswertungsreferenzen, Zeit und Qualitaet; fehlende Ausgabe erzeugt keinen Nullbefehl |
| `release`, `blocks`, `package_use` | getrennte Pflichtobjekte | Freigabebesitzer / C-Verwendungsbezug | Atomare Entscheidung und Sperrbild; aktueller, historischer oder unbekannter Verwendungsbezug |
| `measured_v_m_s`, `measured_w_rad_s` | Messwert | A (Sensoren) | tatsächlich gemessene Bewegung, eigene Quelle |
| `odometry_distance_m`, `heading_rad` | Messwert | A/B | Odometrie und Orientierung |

Ein ausgegebener Befehl ist kein Nachweis einer Bewegung. `output` und `measured_*` sind deshalb getrennt.

### `lane`, `route`, `traffic` – Wahrnehmung und Navigation (Produzent: B)

| Feld | Bedeutung |
|---|---|
| `lane.status`, `lane.offset_m`, `lane.heading_error_rad` | Spur: Abweichung quer (m, + = links) und Kurs (rad), nur bei `valid` mit Wert |
| `route.section`, `node`, `approach_from`, `direction` | Abschnitt, Knoten, Zufahrt, Fahrtrichtung (Kennungen aus der Straßenkarte B2) |
| `route.allowed_exits`, `selected_exit` | erlaubte und gewählte Ausfahrt (gewählt ∈ erlaubt, R9) |
| `route.maneuver`, `maneuver_progress` | laufendes Manöver, Fortschritt 0–1 |
| `route.localization_status`, `localization_quality` | Orientierungssicherheit (Qualität 0–1, keine Zentimeterortung) |
| `route.history` | Begrenzte bestaetigte B-Fahrhistorie; fehlend/unbekannt ist keine gueltige leere Liste |
| `traffic.signal_id`, `signal`, `signal_status`, `signal_confidence` | **eigene** zugeordnete Ampel und Signal (`red`, `yellow`, `green`, `off`, `unknown`) |
| `traffic.signs[]` | `{type, status, confidence}` |
| `traffic.crossings[]` | Überwege `{id, occupancy: free\|occupied\|unknown, status}` |

### `obstacles` – Hindernisse (Produzent: A/B)

| Feld | Bedeutung |
|---|---|
| `corridor` | benötigter Fahrbereich `free` / `occupied` / `unknown` |
| `front_clearance_m` | Messwert: freier Abstand zur **Fahrzeugaußenkante** (nicht zum Sensor) |
| `unknown_areas` | gibt es nicht einsehbare Bereiche im Fahrbereich? (`null` = nicht bestimmt) |
| `distance_locks` | aktive Abstandssperren |
| `objects[]` | `{class, distance_m, lateral_m, in_corridor, source, frame_id}`; `class = null` = gemessen, aber nicht erkannt. Bleibt trotzdem wirksam. |

### `sensors` – Quellen

Messwert-`source` verweist ausschließlich auf einen Schlüssel dieses Objekts, z. B. `odometry` oder `board`. `source_id` bezeichnet die technische Quelle (z. B. `odom_raw`); es gibt keine Alias- oder Fallbackauflösung. Die synthetischen Akkubeispiele registrieren deshalb ausdrücklich `sensors.board`. Diese Beispielquelle ist kein Nachweis einer realen Boardmessung.

Objekt *Name → Quelle*, z. B. `camera`, `depth`, `lidar_0`, `imu`, `odometry`. Jede Quelle hat folgende Pflichtschlüssel:

| Feld | Typ / Bedeutung |
|---|---|
| `source_id` | nichtleerer Text, technische Quelle; kein Referenzalias |
| `producer_id`, `producer_boot_id` | nichtleerer Text oder `null`; logischer Ursprungsproduzent und sein eigenständiger Start, gebunden an das äußere `robot_id` |
| `time_basis_id` | nichtleerer Text oder `null`; Uhreninstanz der monotonen Aufnahmezeit |
| `captured_at_s` | endliche nichtnegative Unix-Sekundenzahl oder `null`, getrennte UTC-Aufnahmezeit; kein Ersatz für lokale Uhrenbindung |
| `captured_mono_s` | exakte lokale Sekundenzahl oder `null`, tatsächliche Aufnahme; Sensoreigenzeit nur nach bestätigter Abbildung |
| `received_mono_s` | exakte lokale Sekundenzahl oder `null`, lokaler Empfang in der Uhr des Zustandskopfs, auch bei fremder Aufnahmeuhr |
| `age_s` | exakte Dauer oder `null`, Erzeugung minus Aufnahme, niemals minus Wiederempfang |
| `status`, `reason` | Qualität und Grund; Nicht-`valid` braucht einen Grund |
| `rate_hz`, `frame_id`, `coord_frame` | endliche nichtnegative Messrate, Aufnahmekennung, räumlicher Bezug; jeweils Wert oder `null` |

Bei `valid` sind alle drei Ursprungs-/Uhrkennungen und alle vier Zeitwerte erforderlich. Die Aufnahmeuhr muss zur Kopfzeitbasis passen. Für deklarierte gleiche Uhr gilt exakt `0 <= captured_mono_s <= received_mono_s <= generated_mono_s` und `age_s = generated_mono_s - captured_mono_s`. Jeder vorhandene Empfang liegt höchstens bei Zustandserzeugung, unabhängig vom Quellenstatus. `stale`, `invalid` und `unknown` dürfen einen bekannten früheren Empfang behalten oder `null` führen. Bei `missing` (nie empfangen) sind alle vier Aufnahme-/Empfangs-/Altersfelder `null`; bekannte Herkunft darf erhalten bleiben, unbekannte bleibt ehrlich `null`. Bei fehlender Aufnahmezeit ist das Alter `null`.

Ein fehlender Zeitbasisnachweis ist `unknown`, ein fremder oder widersprüchlicher Aufnahmeuhrbezug `invalid`; beide sind niemals `valid`. Ohne vergleichbare deklarierte Aufnahmeuhr ist `age_s = null`. Bekannte fremde Aufnahmezeiten können als Diagnose erhalten bleiben, werden aber nicht mit der lokalen Erzeugung verglichen. UTC wird nicht zur Frischeberechnung herangezogen. Reiner C-Neustart oder Wiederempfang ändert weder Ursprungsstart noch Aufnahmezeit/Frame und erneuert keine Messung. Ein Sensorneustart erzeugt einen eigenen neuen Aufnahmenamensraum; die Geräteuhr kann gleich bleiben.

**Geltungsgrenze:** `pruefe()` prüft statische deklarierte Konsistenz. Gleiche Kennungstexte beweisen keine physische Bindung, keinen gemeinsamen Ursprung und keine Farbbild-/Tiefenpaarung. Reale Produzenten müssen die Bindung an Gerät, Sensorstart und gemeinsame Uhr einschließlich Suspendverhalten separat bestätigen. C-`boot_id`, Sensorstart und `time_basis_id` sind getrennte Identitäten; sie werden weder voneinander abgeleitet noch pauschal gleichgesetzt. Die synthetischen Fixtures sind kein solcher Nachweis. Fehlende Herkunft darf nicht erfunden werden.

### Öffentlicher Python-/JSON-Zeitpfad (Standardbibliothek, Python ≥ 3.10)

Monotone Zeiten, Alter und lokale Zeitparameter verwenden exakt das Nanosekundenraster im Bereich `0..9223372036854775807` ns (= `0..9223372036.854775807` s). Das ist eine technische Darstellungsgrenze, keine Bewegungsfrist oder zugesagte Messauflösung. Erfasst wird Integer-ns aus einer bestätigten gemeinsamen Uhr, etwa `time.monotonic_ns()`. Kein `time.monotonic()`-Float oder `ns / 1e9` als Bauweg.

| Öffentliche Funktion | Einheiten, Ergebnis und Fehler |
|---|---|
| `sekunden_aus_ns(nanosekunden)` | Integer-ns → exakte `Decimal`-Sekunden; ausschließlich `int`, keine bool; Bereich wie oben; sonst `ValueError` |
| `zeit_ns(sekunden)` | `int` als ganze Sekunden oder exakte `Decimal`-Sekunden → Integer-ns; Raster/Bereich/Endlichkeit exakt prüfen, sonst `ValueError` |
| `alter_s(d, jetzt_mono_s)` | Erzeugung und jetzt in bestätigter gleicher Uhr; genaue Differenz als `Decimal`-Sekunden; ungültige Zeit oder Erzeugung nach jetzt → `ValueError`. Die Funktion erhält den Uhrnachweis vom Aufrufer. |
| `pruefe(d)` | Fehlerliste, einschließlich Zeit-/Zahl-/Identitätsregeln; kein Schema- oder ROS-Paket nötig |
| `lade_json(text)` | validiert; Dezimal-/Exponententokens direkt als `Decimal`, Ganzzahltokens als `int`, keine Floatvorstufe; ungültig → `ValueError` |
| `als_json(d)` | validiert und schreibt Decimal-Werte feldtreu als unquotierte JSON-Zahlen; korrekte String-/bool-/null-/Listen-/Objektausgabe; ungültig → `ValueError` |

Zeitfelder `generated_mono_s`, `sensors.*.captured_mono_s`, `received_mono_s`, `age_s`, `motion.request.valid_until_mono_s`, `diagnostics.events[].mono_s`, `communication.last_broker_ack_mono_s` und die Zeithelper lehnen direkte Floats, bool und Zahlenstrings ab. `null` bleibt ausschließlich dort möglich, wo es dokumentiert ist; fehlende Pflichtschlüssel sind Fehler. `int(1)` bedeutet eine Sekunde, `sekunden_aus_ns(1)` eine Nanosekunde. Exakte Decimal-Literale aus Text verwenden, niemals `Decimal(float)` als Reparaturweg. Alle Raster-/Bereichs-/Differenzrechnungen laufen unabhängig vom Decimal-Kontext über Ziffern/Exponent und Integer-ns, ohne Epsilon, Nachrunden oder Fristgewinn.

JSON-Felder bleiben **Zahlen in Sekunden**. `120.2`, `120.200000000` und `1.202e2` haben denselben Wert; `120.2000000001` ist unzulässig. `120.2 - 120.0` ergibt exakt `0.20` s. Der Writer verwendet weder `default=str`, Floatkonvertierung noch Textersetzung. Nichtzeitliche Zahlen akzeptieren endliche `Decimal` und weiterhin endliche direkte Floats; deren erneutes Lesen liefert bei Dezimaltokens `Decimal` mit dem übertragenen Zahlenwert, keine Zusage binärer Float-Objektgleichheit. Auch UTC-Unixfelder bleiben separat und erzeugen keine lokale Frist. `NaN`, `sNaN`, ±Infinity werden in Zeit- und Nichtzeitfeldern vor jedem Vergleich abgelehnt, ohne `decimal.InvalidOperation`.

Das aktive v2-Schema beschreibt Struktur/Zahlenbereiche; exaktes Raster, Endlichkeit, Statusbezug, Aufnahmereihenfolge und Alter prüft Python. Binärfloat-Leser können die exakte Fristsemantik nicht garantieren. `schemas/grundbetrieb-v1.schema.json` bleibt bytegleich zum veröffentlichten Altstand `88a82d46023a1e53b7bda78a7f66063872c225c3`, vor `received_mono_s`. Er ist ausschließlich historisch; Python und alle sieben aktiven Fixtures verwenden 2.0 und lehnen 1.0/unbekannte Versionen ab. Kein automatischer Migrationsadapter erfindet fehlende Pflichtdaten.

### `diagnostics`

`battery_v` (Messwert), `board_status`, `warnings[]`, `events[]` (`event_id`, `mono_s`, `kind`: `info`/`stop`/`drive`/`warning`/`fault`, `text`).

### `communication` (Produzent: C2)

| Feld | Bedeutung |
|---|---|
| `broker` | `connected` / `disconnected` / `unknown` / `disabled` |
| `last_publish_requested_seq` | zuletzt **angeforderte** Veröffentlichung (lokaler Publish-Aufruf) |
| `last_broker_ack_seq`, `last_broker_ack_mono_s` | zuletzt **vom Broker bestätigte** Sequenz (z. B. PUBACK bei QoS 1). Beide gibt es nur zusammen. |
| `reconnects`, `dropped_messages`, `last_error` | Wiederverbindungen, verworfene Nachrichten, letzter Fehler |

Angefordert ≠ vom Broker bestätigt ≠ extern empfangen. Externer Empfang ist ein Abnahmenachweis außerhalb des Datensatzes.

### `details` – Detaildaten

Die noch unveröffentlichte 2.0-Erweiterung aus [#150](https://github.com/BBS-GuT/smartcity-roboter/issues/150)
implementiert die Detailreferenz und eine **explizit kontextuelle** Prüfung.
Sie liefert keinen Payloadspeicher, Bildtransport oder Adapter und nimmt den
Gesamtvertrag nicht abschließend an. Format, Auflösung, Rate und reale
Altersbudgets bleiben mit E/Broker-/Dashboardteam zu vereinbaren.

Alle folgenden Schlüssel sind in jedem `details[]`-Eintrag vorhanden:

| Felder | Typ und Bedeutung |
|---|---|
| `robot_id`, `state_boot_id` | Nichtleere Texte, entsprechen äußerem `robot_id` / `boot_id`. `state_boot_id` ist nur Cs aktueller Ausgabekontext. |
| `channel` | Nichtleerer Kanaltext; kein festgelegtes Topic oder Transportformat. |
| `source` | Registrierter Schlüssel unter `sensors`, niemals technische `source_id` oder Alias. Bei unbekannter Herkunft `null`. |
| `source_id` | Technische Quelle der damaligen Aufnahme, nicht zwingend die heutige technische Quelle des Schlüssels. |
| `producer_id`, `producer_boot_id` | Aufnahmeproduzent und sein eigener Start; unabhängig von C-Start und Uhreninstanz. |
| `frame_id` | Opake Aufnahmekennung; `coord_frame` bleibt räumlicher Bezug und ersetzt sie nicht. |
| `data_id`, `format` | Opake Datenkennung und Format dieser Darstellung; mehrere Datenkennungen je Frame sind möglich. |
| `time_basis_id` | Uhreninstanz der Aufnahme, gegen bestätigte Geräteuhr des Kontexts zu prüfen. |
| `captured_at_s` | Endliche nichtnegative Unix-Sekunden oder `null`; UTC bleibt separat. |
| `captured_mono_s`, `received_mono_s`, `age_s` | Exakte nichtnegative Sekunden im gemeinsamen ns-Raster/Bereich oder `null`; gemeinsame Helper `zeit_ns()` / `sekunden_aus_ns()`. Empfang meint den ursprünglichen lokalen Frameempfang, kein neuer Transportversuch. |
| `status`, `reason` | Bestehender Qualitätsstatus; `valid` verlangt `reason = null`, jeder andere Status einen nichtleeren Grund. |

Frame-Schlüssel: `(robot_id, source, producer_id, producer_boot_id, frame_id)`.
Daten-Schlüssel: Frame-Schlüssel plus `(channel, data_id)`. Technische Quelle,
Format, UTC-Aufnahmezeit, Uhreninstanz und monotone Aufnahme-/ursprüngliche
Empfangszeit bleiben bei derselben Datenkennung unverändert. Identische
Wiederholungen sind Duplikate; widersprüchliche Metadaten derselben Kennung werden
abgelehnt. Verschiedene Darstellungen desselben Frames dürfen verschiedene Formate
haben; gemeinsame Aufnahme-/Quellenmetadaten bleiben identisch. C-Neustart ändert
nur `state_boot_id` und den äußeren Zustandskontext, niemals die Aufnahmeidentität.
Bei zulässigen endlichen UTC-Floats wird der übertragene dezimale JSON-Zahlenwert
verglichen, nicht dessen interne Binärdarstellung; lokale Zeitfloats bleiben verboten.

**Null-/Qualitätsregeln:** `valid` und `stale` benötigen alle Identitäts-, Format-
und Zeitfelder einschließlich passendem Alter. Bei `unknown` / `invalid` dürfen
unbekannte Quellen-, Produzenten-, Frame-, Daten-, Format- und Zeitfelder `null`
sein; Bekanntes bleibt erhalten, `age_s` ist `null`. `missing` erhält ebenfalls
bekannte Herkunft einschließlich `source_id`, Produzentenstart und Uhrenkennung;
`frame_id`, `data_id`, `format`, beide Aufnahmezeiten, Empfang und Alter sind
`null`. Kein erfundener fehlender Frame. `robot_id`, `state_boot_id` und `channel`
bleiben immer erforderlich. Ein vorhandener `source` muss auch in Diagnosen ein
registrierter Schlüssel sein. Falsche Herkunft kann separat bewertet werden,
ist aber keine gültige lokale Detailreferenz. Ein als `invalid` deklariertes
unbrauchbares Detail wird durch passende Identität/Frische nicht repariert.

### Öffentlicher Detailkontext und strikte Einstiege

`pruefe_detailreferenz(detail, *, zustand, detail_kontext=None)` bewertet ohne
Mutation von Kandidat, Zustand oder Kontext. `zustand` enthält mindestens
`robot_id`, `boot_id`, `time_basis_id`, `generated_mono_s` und `sensors`.
Die Antwort ist `{status, reason, age_s, context}`. `context` nennt die tatsächlich
benutzte Bindung (`context_id`, `robot_id`, `state_boot_id`, `time_basis_id`), nach
Auflösung zusätzlich `registration`, `frame_key`, `data_key` und das verwendete
`age_budget_s`. Fehlender Kontext ergibt ein leeres Kontextobjekt; keine erfundene
Bindung. Diese Prüfung ist keine vollständige Zustands-Strukturprüfung.

Der Aufrufer liefert **unabhängig vom zu prüfenden Kandidaten** genau diese
Kontextschlüssel; es gibt keinen Standardkontext und keine globale Registrierung:

| Kontextschlüssel | Inhalt |
|---|---|
| `context_id` | Nichtleere Kennung des gegebenen Nachweiskontexts. Kein automatischer Vertrauensbeweis durch einen Text. |
| `robot_id`, `state_boot_id`, `time_basis_id` | Explizit bestätigte Geräte-/C-Start-/Uhrbindung, muss zum betrachteten Zustand passen. |
| `registrations` | Liste historischer Einträge mit genau `robot_id`, `source`, `source_id`, `producer_id`, `producer_boot_id`, `time_basis_id`; alle nichtleere Texte. Frühere Produzentenstarts dürfen enthalten sein. |
| `records` | Liste unabhängig bekannter Datenreferenzen mit genau allen Frame-/Datenschlüsselfeldern plus `source_id`, `format`, `captured_at_s`, `time_basis_id`, `captured_mono_s`, `received_mono_s`. Alle Metadaten vorhanden; keine Status-/Alters-/C-Startfelder. |
| `age_budgets_s` | Kanal → explizites exaktes Altersbudget in Sekunden, im selben ns-Raster/Bereich; keine Floats, bool oder Standardfrist. Fehlende Kanäle sind erlaubt, bestätigen aber keine Frische. |

Die Listen sind gegebene historische Belege, kein laufender Speicher. Der Prüfer
fügt nichts hinzu und verschiebt keine Startbindung. Widersprüchliche doppelte
Registereinträge werden abgelehnt, statt den ersten passenden Eintrag auszuwählen.
Verdrängte/verlorene Metadaten dürfen nicht aus Kandidaten rekonstruiert werden;
Kennungen dürfen nicht wiederverwendet werden. Aufbewahrung und reale Uhrenbindung
einschließlich Sensorzeitabbildung bleiben gesondert zu belegen.

Für ein vollständiges Detail gilt: damaligen Registereintrag auflösen, unveränderte
Metadaten vergleichen, gemeinsame Uhr bestätigen, dann exakt
`captured_mono_s <= received_mono_s <= generated_mono_s` prüfen. Aufnahmealter
entsteht aus ganzzahligen ns-Differenzen, unabhängig vom Decimal-Kontext.
Innerhalb des gegebenen Kanalbudgets einschließlich Gleichheit ist die Aufnahme
`valid`, darüber `stale`. **Keine Gleichheit zum neuesten Sensorframe**: Ein
historisch belegter älterer Frame kann gültig bleiben, auch bei inzwischen neuem
Sensorproduzentenstart oder aktuellem Quellenfehler. Er beweist keine aktuelle
Sensorverfügbarkeit. Wiederempfang und UTC-Synchronisation verjüngen nichts.

Ohne Kontext: `unknown/detail_context_unknown`. Ohne damaligen Framebeleg:
`unknown/historical_record_unknown`. Ohne bestätigten Start oder Uhrnachweis:
`unknown` mit entsprechendem Grund und ohne Alter. Ohne Kanalbudget:
`unknown/age_budget_unknown`, ebenfalls ohne Alter. Fremdes Gerät/Quelle, falscher
C-Kontext, Uhrwechsel, Zukunft, Metadatenwiderspruch oder ungültige Zahl sind
`invalid`. Unvollständige oder widersprüchliche explizite Kontexte ergeben
`invalid/detail_context_invalid`. Fehlende Daten mit ehrlichen Nullfeldern bleiben
`missing`; Diagnose ist keine aktuelle Schutzinformation.

Die aktiven Einstiege heißen jetzt einheitlich
`pruefe(d, *, detail_kontext=None)`, `als_json(d, *, detail_kontext=None)` und
`lade_json(text, *, detail_kontext=None)`. Sie reichen denselben gegebenen Kontext
weiter. Behauptetes `valid` oder `stale` muss mit der kontextuellen Bewertung und
dem exakten Alter übereinstimmen; sonst Fehlerliste bzw. `ValueError`. Auch ein
strukturell/schemaformal korrektes `valid` wird ohne Kontext **nicht** vollständig
gültig akzeptiert. Ehrliche `unknown`-/`missing`-/`invalid`-Diagnosen bleiben ohne
erfundene Registrierung schreib-/lesbar. Die Zustandsfixtures zeigen deshalb die
bekannten Detailmetadaten als `unknown/detail_context_unknown`, Alter `null`.

Synthetische unabhängige Register, Bindungen, Budgets und sechs Kandidaten stehen
unter `tests/fixtures/c1_details/`. Deren Tests prüfen zusätzlich den aktiven
Python-/JSON-Pfad und das v2-Schema. Schema beschreibt nur Struktur und Nullregeln;
es beweist weder Registrierung noch reale Frische. Die kontextuelle Antwort und
ihre externen Belege sind kein zweiter Zustand und erzeugen keine Motorfreigabe.

## Integriertes C1-Gesamtmodell und explizite Kontexte

Die vollstaendigen Pflichtschluessel, Nulltypen und Strukturgrenzen stehen im aktiven
[v2-Schema](../schemas/grundbetrieb-v2.schema.json). Alle Referenzen enthalten
`robot_id, producer_id, producer_boot_id` und die jeweilige fachliche Kennung oder
Sequenz. Auswertungen ergaenzen `domain`; Sensorframes ergaenzen `source, frame_id`,
Details ausserdem `channel, data_id`. C-Start, Sensorstart, B-Start und Uhreninstanz
sind getrennt. Bekannte Herkunft bleibt erhalten, unbekannte wird nicht erzeugt.

### Eigenstaendiger Fahrwunsch und Datenannahme

`motion.request` ist `null` oder exakt derselbe Datensatz wie der eigenstaendige
Fahrwunsch: `contract_version, robot_id, producer_id, producer_boot_id, request_seq,
request_id, time_basis_id, generated_mono_s, valid_until_mono_s, v_m_s, w_rad_s,
maneuver, hold_reasons`. Beide Darstellungen nutzen `$defs/fahrwunsch`. Strukturell gelten inklusive
Grenzen `-1 <= v_m_s <= 1` und `-10 <= w_rad_s <= 10` (m/s bzw. rad/s);
ein konkreter Freigabeweg kann engere konfigurierte Grenzen verlangen. Ein eingebetteter
Wunsch muss zum aeusseren Geraet gehoeren; `request_id` ist opak und ersetzt keine Identitaet.

`pruefe_fahrwunsch`, `fahrwunsch_als_json` und `lade_fahrwunsch_json` sind zustandslos.
`FahrwunschAnnahme` erhaelt ausdruecklich `robot_id, producer_id, producer_boot_id,
time_basis_id, bind_mono_s, max_duration_s`. Erst `annehmen` / `annehmen_json`
schreiben Annahme- und getrennten Anti-Replay-Hoechststand fort. Erzeugung muss
nach der bestaetigten Bindung liegen; es gilt `generated <= jetzt < valid_until`,
positive Dauer und gegebenes Maximalbudget, jeweils exakt in Integer-ns.
Ein korrekt gebundener bereits abgelaufener hoeherer Wunsch entwertet aeltere
Wunschsequenzen (8 / abgelaufen 10 / frisch 9 wird abgewiesen / 11 kann folgen).
Fehlerhafte hohe Kennungen vergiften keinen Hoechststand. Duplikate erneuern keine
Frist, Erzeugungszeiten laufen nicht zurueck. Nur eine ausdrueckliche Neubindung
setzt B-/A-Kontext zurueck; ein C-Neustart tut dies nicht. Rueckgaben sind Kopien.

### Begrenzte bestaetigte Fahrhistorie

`route.history` enthaelt `producer_id, producer_boot_id, time_basis_id, status,
reason, entries, dropped_entries`. Ein Eintrag besteht aus `section, node,
approach_from, exit_to, entry_seq, confirmed_mono_s`. Maximal 16 Eintraege,
`entries[i].entry_seq = dropped_entries + i`; vor voller Kapazitaet ist der
Verlustzaehler 0. `valid` braucht bestaetigte B-Bindung/Initialisierung und die
explizite gerichtete Karte. Unbekannt/fehlend besitzt `entries=null` und
`dropped_entries=null`, niemals eine erfundene gueltige leere Liste.

`pruefe_historie` erhaelt den gegebenen Karten-/Bindungskontext und optional einen
bestaetigten vorherigen Snapshot. Eine Erfassungsluecke bleibt `invalid/capture_gap`
bis zu einem ausdruecklich bestaetigten neuen B-Historienstart. STOPP, TEST,
Reconnect oder C-Neustart setzen nichts zurueck; ein Kartenwechsel braucht einen
neuen Historienstart. Der Validator erzeugt selbst keine Fahrt oder Historie.

### Atomare Motion-/Arm-Pakete und Raeumvorgang

`motion` und `arm` besitzen `release, blocks, output, package_use`. `release`
meldet Besitzer, Entscheidung, Wunsch-/Commandbezug, Ausgabereferenz und Auswertungszeit;
`blocks` meldet dasselbe vollstaendige Auswertungspaket mit unabhaengigen
STOPP-/Fehlerlatches und einzelnen Sperren (`effect=motion/arm/both`). Vorhandene
Ausgabe und Sperrbild muessen exakt zur `evaluation_ref` des Ergebnisses passen.
Ein gleicher Auswertungsschluessel mit geaendertem Inhalt ist ein Widerspruch.
Wunsch, gemeldete Ausgabe, Empfangsbestaetigung und wirkliche Messung bleiben getrennt.

`package_use.mode=current/historical/unknown` bewertet die Verwendung im aeusseren
Zustand. Endgueltige Motion-Ausgaben halten ebenfalls die inklusiven Strukturgrenzen
`v_m_s` von -1 bis 1 und `w_rad_s` von -10 bis 10 ein. Ein aktuelles
wunschgebundenes Paket muss den vollstaendigen aufgeloesten Wunsch in
`motion.request` bzw. `arm.request` enthalten; der externe Kontext ersetzt
diese fuer beide Leser benoetigten Daten nicht. Historische Diagnose und
eigenstaendige belegte Nullwunsch-Haltpakete bleiben darstellbar.
Aktuelle Erlaubnis oder fahrende Ausgabe braucht einen explizit bestaetigten
aktuellen Annahmebezug; Wunsch/Command muss bereits bei der Auswertung und noch bei
Zustandserzeugung frisch sein. Bei vorhandener Ausgabe gilt zusaetzlich
`evaluated <= issued <= generated < valid_until`. Eine erlaubte Entscheidung ohne
Ausgabe bleibt darstellbar; ohne Ausgabe wird keine `issued_mono_s` erfunden.
Historische Pakete werden nicht umdatiert oder in aktuelle Laufzeitwerte projiziert.
Ohne aktuelles Paket sind `runtime.evaluation_ref` und beide Laufzeitlatches `null`.

`blocked` verlangt bei vorhandener Motion-Ausgabe exakt `v_m_s=w_rad_s=0`.
Bei gesperrtem Arm ist eine commandgebundene Ausgabe verboten. Ein unabhaengiger
Schutzauftrag kann mit `command_ref=null` und in Ausgabe/Ergebnis identischem
`command_reason=PROTECTIVE_ACTION_WITHOUT_REQUEST` gemeldet werden; ein unbekannter
Wunsch ist kein belegter Nullwunsch. Ohne Ausgabe bleibt deren Referenz `null` mit Grund.

`arm` ergaenzt den eigenstaendigen Armwunsch mit Sequenz/Frist, `ack` als wirkliche
Empfangsbestaetigung und `measured/load` als quellbelegte Messbloecke. `camera_pose`
bleibt ein eigener Messblock. Komponenten tragen Raum-, Kalibrier-, Einheits- und
Qualitaetsbezug; ohne gegebenen Komponenten-/Quellenkontext keine gueltige Stellung,
Kraft oder Unsicherheit. Zielwerte sind keine Messwerte. Ein aeusserlich `valid` gemeldeter Messblock
braucht mindestens einen gueltigen Messdatensatz; eine ausschliesslich
ungueltige oder fehlende Liste darf keine gueltige Stellung oder Last behaupten.

`clearing` meldet B-Vorgangsidentitaet, Phase, Ausfuehrungsstatus, Ergebnis, Abbruch-
und Unterbrechungsgruende/-zeiten, Objektbezug, Beobachtung, Schaetzung und getrennte
Verifikations-/Fahrstellungsbelege. Aktiv gilt `started <= updated <= generated`.
Eine Pause behaelt das offene Ergebnis und braucht Grund/Zeit. Abschliessende
Ergebnisse erfordern `execution_status=beendet`; umgekehrt braucht ein beendeter
aktiver Vorgang ein abschliessendes Ergebnis. Einzige Ausnahme ist belegte
Inaktivitaet mit `phase=inaktiv, execution_status=beendet, result=offen` und
vollstaendiger Nullbelegung aller Vorgangs-/Objekt-/Erfolgsfelder sowie `arm.request=null`.
Erfolg braucht passende bestaetigte Verifikations- und Fahrstellungsnachweise
desselben Vorgangs, nicht Timer oder gesendete Befehle. Objektwechsel braucht einen
neuen Vorgang. `protection` und `sensor_requirements` referenzieren getrennte
Politik-/Matrixnachweise; unbekannte Politik und unbekannter Armbesitzer bleiben darstellbar.

### Oeffentliche Gesamtpruefung

`pruefe`, `lade_json` und `als_json` reichen die expliziten Schluesselparameter
`detail_kontext`, `historie_kontext`, `vorherige_historie`, `raeum_kontext` an die
Teilpruefer weiter. `vorherige_historie` ist ein bestaetigter Snapshot mit Geraet,
Karte, Uhr, Erzeugungszeit und `history`. `raeum_kontext` ist ein `RaeumKontext`
mit gegebenen Registern, Bindungen, Einheiten und aktuellem Annahmebezug. Diese
Kontexte kommen vom Aufrufer, niemals aus dem zu bestaetigenden Kandidaten.
Fehlender Kontext bestaetigt keine aktuelle Erlaubnis, gueltige aktive Historie
oder gueltigen Quellenbeleg. Ehrliche `unknown/missing` bleiben darstellbar.
Die drei statischen Einstiege veraendern weder Kontexte noch Annahme-/Replaystand.
Doppelte JSON-Schluessel werden auch bei eingebetteten Wuenschen zurueckgewiesen.

Die sieben Gesamtbeispiele haben einen gesonderten synthetischen Annahmekontext
unter `tests/fixtures/c1_context/grundbetrieb.json`. Die Teilbeispiele und die
Gesamtpruefung `tests/test_c1_gesamtvertrag.py` bilden vier Raeumfaelle, Ausfall,
TEST, Fahrt, parallele Haltgruende und Reconnect ohne neue Freigabe ab.

## Fachliche Regeln (prüft `pruefe()`)

| Regel | Inhalt |
|---|---|
| R1 | Kein `NaN`/Unendlich. `als_json()`/`lade_json()` lehnen es ab. |
| R2 | Messwert/Spur: `valid` ⇔ Wert vorhanden. Gültige Messwerte brauchen einen auflösbaren `sensors`-Schlüssel als `source`; jede angegebene Messwertquelle verwendet diesen Namensraum. Unbekannt wird nie zur gültigen Null. |
| R3 | STOPP-/Fehlersperre, `GESTOPPT`, `TEST`, `FEHLER` → `motor_enabled = false` und `output = 0`. TEST darf einen Fahrwunsch zeigen. |
| R4 | `output ≠ 0` nur mit `motor_enabled` und in `SPURFOLGEN`, `KREUZUNG_ANNAEHERN`, `MANOEVER`, `AUSFAHRT_BESTAETIGEN`. |
| R5 | `VERKEHRSHALT` → mindestens ein Haltegrund und `output = 0`. |
| R6 | bestätigt ≤ angefordert ≤ `seq`. `disconnected` braucht `last_error`. |
| R7 | Quelle `valid` braucht vollständige Herkunft, gleiche deklarierte Uhr, Aufnahme/Empfang/Erzeugung in Reihenfolge und exaktes Aufnahmealter. `missing` hat keine Zeit. Nicht-`valid` braucht einen Grund. |
| R8 | `stop_latched` → `STOP_LATCHED` in den Haltegründen. `FEHLER` → `fault_latched`. Fehlersperre → mindestens ein Fehlertext. |
| R9 | `selected_exit` ∈ `allowed_exits`. |
| R10 | `corridor = free` und ein Objekt `in_corridor` widersprechen sich. |
| R11 | `signal_status = valid` mit `signal = unknown` widerspricht sich. |

## MQTT (Vorschlag aus Zieldefinition §7.4, noch abzustimmen)

`smartcity/robots/<RM0x>/state` (dieser Datensatz, QoS 1, retained), `…/availability`, `…/info`, `…/events`, `…/details/...`. Empfänger prüfen Gerät, Startkennung, Sequenz und Alter. Ein retained Zustand ist nicht automatisch aktuell. Eine Wiederverbindung ändert weder `stop_latched` noch `motor_enabled` (Beispiel `broker_wiederverbunden.json`). Broker, Topics und Raten liefert E. Nichts davon ist hier als vereinbart angenommen.

## Für A/B zu prüfende Adapterentscheidungen

1. **A:** Wer setzt `runtime.state`? Vorschlag: der Motorfreigabeweg (A2) aus Bedienung + Fahrwunsch + Pflichtsensoren. Der heutige Linienfolger kennt nur `drive` true/false und KI-`aktion`.
2. **A:** `motor_enabled` vs. `output`: Heute gibt es keinen getrennten Freigabeweg. Bis A2 wäre `motor_enabled` = „START gedrückt und keine Sperre“.
3. **B:** Abbildung der heutigen KI-Gründe (`ki/entscheider.py`, Freitext) auf `hold_reasons`. Die Codes oben sind ein Vorschlag. Fehlende Codes führen zu einer neuen Schemaversion.
4. **B:** `route.*` und `traffic.signal_id` bleiben `null`/`unknown`, bis die Straßenkarte B2 und die Ampelzuordnung (E) existieren.
5. **A/B:** `measured_v_m_s`: Gibt es eine echte Geschwindigkeitsmessung (Radzähler)? Sonst bleibt sie `missing`. Der Befehl wird nicht als Messung ausgegeben.
6. **A/B:** `front_clearance_m` zur Fahrzeugaußenkante braucht die gemessene Fahrzeughülle und LiDAR-Einbaulage (E1-Messung).
7. **C2:** `communication.*` füllt der MQTT-Publisher. `last_broker_ack_*` erst nach echter Brokerbestätigung.

Offen (nicht erfunden): Brokeradresse, Topics, Raten, Bildformate und -auflösung, Ampel-/Knotenkennungen, Fahrzeughülle.
