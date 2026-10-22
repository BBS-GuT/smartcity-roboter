# Schnittstelle Grundbetrieb: Zustandsdatensatz v1.0

**Auftrag:** C1 ([#14](https://github.com/davidheinrich73/smartcity-roboter/issues/14)). **Bezug:** [Zieldefinition](zieldefinition-grundbetrieb.md) §5–7, GB-12 bis GB-18.
**Status:** Entwurf zur fachlichen Prüfung durch A/B/O. Erst ein akzeptierter Commit ist verbindlich (siehe [Register](auftraege/README.md)).

Ein Roboter erzeugt **einen** Zustandsdatensatz. Panel und MQTT lesen genau diesen Datensatz. Das Panel leitet daraus keine eigene Fahrentscheidung und keinen eigenen Haltegrund ab.

| Datei | Inhalt |
|---|---|
| `lib/grundbetrieb_vertrag.py` | Prüfung (Struktur + fachliche Regeln R1–R11), strenges JSON, Startkennung/Sequenz, Vergleich, Datenalter. Nur Python-Standardbibliothek, kein ROS. |
| `schemas/grundbetrieb-v1.schema.json` | JSON-Schema (Draft 2020-12) der **Struktur** für externe Leser (z. B. Dashboard). Die Regeln R1–R11 stehen nur in der Python-Prüfung. |
| `tests/fixtures/grundbetrieb/*.json` | Synthetische Beispiele, **keine** Messwerte eines Geräts. |
| `tests/test_zustandsvertrag.py` | Tests ohne ROS, Roboter und Broker. Nutzt `jsonschema`, falls installiert. |

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
- **Identität:** `robot_id` (RM01–RM04) + `boot_id` (neu bei jedem Programmstart) + `seq` (ab 0 pro Start). Eine Sequenz gilt nur zusammen mit Gerät und Start. Ein Neustart ist nie eine Fortsetzung (`vergleiche()` → `anderer_start`).
- **Zeit:** `generated_at` ist UTC im Format `YYYY-MM-DDTHH:MM:SS[.Bruchteil]Z` (RFC 3339, nur abschließendes `Z`, ASCII-Ziffern). Kalenderdatum einschließlich Schaltjahr muss gültig sein (Jahr 0001–9999); Stunden 00–23, Minuten und Sekunden 00–59. Optional sind 1–9 Nachkommastellen erlaubt, Schaltsekunden nicht. `generated_mono_s` ist die monotone Uhr des Starts für lokale Altersprüfung (`alter_s()`). `time_sync.status` zeigt, ob `generated_at` mit anderen Geräten vergleichbar ist. `unsynced` bleibt sichtbar.
- **Änderung** eines Betriebs- oder Kommunikationszustands = neuer Datensatz mit neuer `seq`.
- **Version:** `schema_version` = `"1.0"`. Neue Pflichtfelder, entfernte Felder oder neue Aufzählungswerte (z. B. Haltegründe) erhöhen die Version.

## Felder

### Kopf

| Feld | Typ | Bedeutung |
|---|---|---|
| `schema_version` | `"1.0"` | Vertragsversion |
| `robot_id` | `RM01`…`RM04` | Gerät |
| `boot_id` | Text ≥ 8 | eindeutig pro Programmstart |
| `seq` | ganze Zahl ≥ 0 | Sequenz in diesem Start |
| `generated_at` | Text UTC | Erzeugungszeit (Wanduhr) |
| `generated_mono_s` | Zahl ≥ 0 | Erzeugungszeit (monoton, nur innerhalb des Starts vergleichbar) |
| `time_sync` | `{status: synced\|unsynced\|unknown, source}` | Zeitsynchronisation |
| `software_version`, `map_version`, `config_version` | Text oder `null` | Commit, Straßenkarte, Gerätekonfiguration |

### `runtime` – Betrieb (Produzent: A, Freigabeergebnis)

| Feld | Typ | Bedeutung |
|---|---|---|
| `mode` | `"GRUNDBETRIEB"` | andere Modi (Szenarien) sind nicht Teil von v1 |
| `state` | `GESTOPPT`, `TEST`, `BEREIT`, `SPURFOLGEN`, `KREUZUNG_ANNAEHERN`, `VERKEHRSHALT`, `MANOEVER`, `AUSFAHRT_BESTAETIGEN`, `FEHLER` | Betriebszustand (Zieldefinition §6) |
| `motor_enabled` | bool | Motorweg grundsätzlich freigegeben |
| `stop_latched` | bool | bleibende Bedien-STOPP-Sperre |
| `fault_latched` | bool | bleibende Fehlersperre |
| `hold_reasons` | Liste, eindeutig | **alle** wirksamen Haltegründe, getrennt (z. B. `RED_LIGHT` und `FRONT_BLOCKED` gleichzeitig) |
| `faults` | Liste Text | Fehlerbeschreibungen |

Haltegründe v1: `STOP_LATCHED`, `FAULT`, `TEST_MODE`, `NO_REQUEST`, `RED_LIGHT`, `YELLOW_LIGHT`, `SIGNAL_UNKNOWN`, `STOP_SIGN`, `CROSSING_OCCUPIED`, `FRONT_BLOCKED`, `DISTANCE_LOCK`, `SENSOR_MISSING`, `SENSOR_STALE`, `SENSOR_INVALID`, `LINE_LOST`, `LOCALIZATION_UNKNOWN`, `MANEUVER_FAILED`.

### `motion` – Bewegung

| Feld | Typ | Produzent | Bedeutung |
|---|---|---|---|
| `request` | Objekt oder `null` | B → A | Fahrwunsch: `request_id`, `valid_until_mono_s`, `v_m_s`, `w_rad_s`, `maneuver`, `hold_reasons`. **Keine** Motorfreigabe. |
| `output` | `{v_m_s, w_rad_s}` | A | endgültig an den Motor ausgegeben |
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

Objekt *Name → Quelle*, z. B. `camera`, `depth`, `lidar_0`, `lidar_1`, `imu`, `odometry`. Jede Quelle: `source_id`, `status`, `reason`, `captured_at_s` (Aufnahmezeit, Unix-s), `age_s`, `rate_hz`, `frame_id` (Frame-/Messungskennung), `coord_frame` (Koordinatenbezug).

Zusätzlich ist `received_mono_s` ein **Pflichtschlüssel**: endliche, nicht negative Zahl in Sekunden oder `null`. Der Produzent erfasst ihn beim lokalen Empfang mit derselben Geräte-`time.monotonic()`-Basis wie `generated_mono_s`. Es ist kein pro Prozess auf null gesetzter Zähler und keine Rückrechnung aus UTC, `captured_at_s` oder `age_s`. Vergleiche gelten nur bei derselben bestätigten lokalen Zeitbasis.

Bei `valid` ist eine Empfangszeit erforderlich, die kleiner oder gleich `generated_mono_s` ist. Bei `missing` (nie empfangen) steht `null`. `stale`, `invalid` und `unknown` dürfen den realen früheren Empfang behalten oder bei nicht verfügbarem Empfangszeitpunkt `null` führen. Für **jeden** Status sind zukünftige Empfangszeiten, negative Zahlen, boolesche Werte, `NaN` und Unendlich unzulässig. Das Schema prüft die Feldstruktur; Endlichkeit, Statusbezug und Vergleich mit der Erzeugungszeit prüft Python. Alle Fixturezeiten sind synthetisch und belegen keine Gerätezeitbasis.

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

Liste `{channel, data_id, format, captured_at_s, frame_id, status}`. Damit sind Bild-, Tiefen- und Scandaten (Panelansichten) über `frame_id` dem Zustand und den Quellen zuordenbar. Format, Auflösung und Rate der Detailkanäle sind **noch nicht vereinbart** (E/Broker-/Dashboardteam). Die Beispiele zeigen nur die Zuordnung.

## Fachliche Regeln (prüft `pruefe()`)

| Regel | Inhalt |
|---|---|
| R1 | Kein `NaN`/Unendlich. `als_json()`/`lade_json()` lehnen es ab. |
| R2 | Messwert/Spur: `valid` ⇔ Wert vorhanden. Gültige Messwerte brauchen einen auflösbaren `sensors`-Schlüssel als `source`; jede angegebene Messwertquelle verwendet diesen Namensraum. Unbekannt wird nie zur gültigen Null. |
| R3 | STOPP-/Fehlersperre, `GESTOPPT`, `TEST`, `FEHLER` → `motor_enabled = false` und `output = 0`. TEST darf einen Fahrwunsch zeigen. |
| R4 | `output ≠ 0` nur mit `motor_enabled` und in `SPURFOLGEN`, `KREUZUNG_ANNAEHERN`, `MANOEVER`, `AUSFAHRT_BESTAETIGEN`. |
| R5 | `VERKEHRSHALT` → mindestens ein Haltegrund und `output = 0`. |
| R6 | bestätigt ≤ angefordert ≤ `seq`. `disconnected` braucht `last_error`. |
| R7 | Quelle `valid` braucht Aufnahmezeit und Alter. `missing` hat keine Zeit. Nicht-`valid` braucht einen Grund. |
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
