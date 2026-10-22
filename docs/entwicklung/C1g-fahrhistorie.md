# C1g: Begrenzte eigene Fahrhistorie – Vertragsvorschlag

**Status:** Entwurf für B/C/O; Entscheidung ausdrücklich ausstehend.
**Auftrag:** [#17](https://github.com/BBS-GuT/smartcity-roboter/issues/17),
Refs [#3](https://github.com/BBS-GuT/smartcity-roboter/issues/3).
Grundlage: [Zieldefinition](../zieldefinition-grundbetrieb.md) §3.2, §4.2,
§7–8 und A06/A13/A15 (GB-05–07, GB-15–18),
[bestehender C1-Vertrag](../schnittstellen-grundbetrieb.md).

Die geschlossene `route`-Struktur enthält bisher keine Fahrhistorie. Alle hier
genannten neuen Felder und Grenzen sind Vorschläge, keine gültige Erweiterung
des heutigen v1-Schemas. Dieser Entwurf ändert keine Laufzeitfelder, Navigation,
Zufallsauswahl, Schemas oder Fixtures und nimmt weder B2 noch #3 ab.

## Bedeutung und Erfassung

B erzeugt die Historie aus bestätigtem Navigationsfortschritt; C übernimmt sie
in denselben unveränderlichen Zustand für Panel und MQTT. Ein Eintrag beschreibt
einen **abgeschlossenen gerichteten Straßenabschnitt** und die anschließende
bestätigte Ausfahrt am Zielknoten. Abschnitt und Ausfahrt werden gemeinsam erst
nach bestätigtem Abschluss des dortigen Manövers eingetragen. Der erste oder
noch laufende Abschnitt bleibt bis dahin außerhalb der Historie.

| Vorgeschlagener Wert | Bedeutung und Gültigkeit |
|---|---|
| `section` | Kennung des tatsächlich befahrenen gerichteten Abschnitts aus `map_version`; Gegenrichtung ist ein anderer Abschnitt. Keine freie Ortsbeschreibung. |
| `node`, `approach_from` | Zielknoten des Abschnitts und dessen bestätigte Zufahrt vom vorherigen Knoten; zusammen mit Karte und Richtung eindeutig. |
| `exit_to` | Nach dem Manöver bestätigter nächster Knoten; keine bloß geplante `selected_exit`. Der ausgehende Abschnitt ist dadurch noch nicht vollständig befahren. |
| `entry_seq` | Ganze Zahl ab 0 pro Geräte-/Programmstart; pro bestätigtem Abschluss genau einmal erhöht, unabhängig von der Zustands-`seq`. |
| `confirmed_mono_s` | Endliche nichtnegative Sekunden der gleichen lokalen monotonen Uhr wie `generated_mono_s`; Zeitpunkt der Abschlussbestätigung, keine erfundene Aufnahmezeit. |

Kennungen müssen in derselben Karte auflösbar sein und eine erlaubte gerichtete
Verbindung bilden. Ein Fahrwunsch, ausgegebener Motorbefehl, Timerablauf oder
wiederholtes Kamerabild genügt nicht als Abschlussbeleg. Abgebrochene oder nur
vermutete Manöver erzeugen keinen Eintrag. Die aktuelle Wegwahl verbleibt in
`route`; die Historie erteilt keine Bewegungsfreigabe und ersetzt keine aktuelle
Orientierung. Welche Quellen B zur Bestätigung braucht, bleibt zu entscheiden.

## Reihenfolge, Zeit, Begrenzung und Neustart

Vorschlag: `route.history` enthält `status`, `reason`, `entries` und
`dropped_entries`. Maximal **16 Einträge**, ältester zuerst, neuester zuletzt;
kein unbegrenztes Journal und keine Vollständigkeitsbehauptung über eine Fahrt.
Bei Eintrag 17 fällt der älteste weg; `dropped_entries` zählt ausschließlich
diese Kapazitätsverwerfungen seit Start. `entry_seq` wird dabei nicht neu
nummeriert. Bestätigungen sind nach `entry_seq` streng aufsteigend, Zeiten
nicht abnehmend und höchstens `generated_mono_s`; gleiche Zeitwerte werden
durch `entry_seq` geordnet. Doppelte Zustandsübertragung fügt nichts hinzu.

Gerät, `boot_id` und `map_version` aus dem Zustandskopf gelten für alle Einträge;
eine Eintragskennung ist erst mit `(robot_id, boot_id, entry_seq)` eindeutig.
`seq` bezeichnet weiterhin den Zustand, nicht den Historieneintrag. UTC und
Synchronisationsstatus stammen aus dem Kopf; UTC ist keine Ersatzsortierung.
Monotone Werte verschiedener Starts oder Geräte werden nicht verglichen.
Ein alter bestätigter Eintrag ist vergangene Fahrt, kein aktueller Sensorframe;
ein alter Zustandsdatensatz bleibt insgesamt als alt erkennbar.

Bei jedem Programmneustart: neue `boot_id`, leerer Puffer, `entry_seq` beginnt
wieder bei 0 und `dropped_entries` bei 0. Kein Wiederladen vorheriger Fahrten
als aktuelle Historie. Erst nach erfolgreicher Initialisierung gilt der leere
Puffer als gültig. STOPP, TEST oder Broker-Reconnect allein setzen ihn nicht
zurück. Kartenwechsel innerhalb eines Starts wird in dieser Fassung nicht
unterstützt: Historie als `invalid` kennzeichnen, keine alten Kennungen unter
neuer Karte ausgeben; neuer Kartenstand erfordert einen neuen Programmstart.

| Zustand | Darstellung und Interpretation |
|---|---|
| Gültig leer | `status: valid`, `reason: null`, `entries: []`, `dropped_entries: 0`: Erfassung seit Start initialisiert, noch kein bestätigter Abschluss. Kein Nachweis bisheriger Stillstandszeit. |
| Gültig befüllt | `status: valid`, Einträge vorhanden, `dropped_entries` ≥ 0; begrenzter Ausschnitt aller bestätigten Abschlüsse seit Start. |
| Fehlend | `status: missing`, begründender `reason`, `entries: null`, `dropped_entries: null`: Erfassung nicht verfügbar/nicht initialisiert. Ein bei alten Vertragsversionen ganz fehlendes Objekt ist ebenfalls unbekannt, nie gültig leer. |
| Ungültig | `status: invalid`, begründender `reason`, `entries: null`, `dropped_entries: null`: etwa unpassender Karten-/Start-/Zeitbezug oder Erfassungslücke. Nicht stillschweigend als lückenlose leere Liste ausgeben. |

Kapazitätsverlust ist mit `dropped_entries` sichtbar und macht den verbleibenden
Ausschnitt nicht ungültig. Ein tatsächlicher Erfassungsausfall während des
Starts ist dagegen keine Kapazitätsverwerfung und darf nicht verdeckt werden.
Bei fehlender/ungültiger Historie entfällt eine daraus abgeleitete Bevorzugung;
das konkrete B-Verhalten und nötige Haltebedingungen beschließen B/A/O separat.

## Gemeinsame Zusammenfassung und eindeutig referenzierte Details

Vorschlag zur Entscheidung: Den begrenzten Ausschnitt samt Status, Grund und
Verwerfungszahl vollständig im gemeinsamen Zustand führen. Damit sehen Panel
und MQTT dieselbe für Wegwahl relevante Vergangenheit ohne Detailabruf.
Optionale Belege der Bestätigungen (Bild/Scan usw.) bleiben Details; keine
zusätzliche unbeschränkte Historie, Publikationsrate oder neues Topic festlegen.

Abhängigkeit [#15](https://github.com/BBS-GuT/smartcity-roboter/issues/15):
Eine spätere Belegreferenz verknüpft die Eintragskennung mit der dort
vereinbarten Detailkennung einschließlich Gerät, Start, registriertem
`sensors`-Quellschlüssel, `data_id`/`frame_id` und Aufnahmezeit. Weder Kanalname
noch nackte Frame-ID reicht. Der Historienproduzent ist keine erfundene
Sensorquelle. Ältere passende Belegframes dürfen erhalten bleiben, ohne mit dem
neuesten Sensorframe identisch zu sein; Aufnahmezeit des Belegs und monotone
Abschlussbestätigung bleiben getrennt. Fremder Start, fremde Quelle oder
unpassender Zeitbezug machen die Belegzuordnung ungültig. Fehlender Detailabruf
bleibt sichtbar und wird nicht in eine gültig leere Historie umgedeutet.
Die genaue Referenzstruktur wird erst mit C1e entschieden und implementiert.

## Zwei synthetische Beispiele

Nur illustrative Ausschnitte des vorgeschlagenen Zustands, keine v1-Fixtures
oder Geräte-/Fahrmessungen. RM01 ist eine synthetisch verwendete Vertrags-ID;
`demo-karte-v1` und Abschnittsnamen sind Platzhalter nach den vorgeschlagenen
Richtungen der Zieldefinition, keine bestätigte B2-Karte.

**1. Zwei bestätigte Abschlüsse:** K7 → K4 mit Ausfahrt nach K1, danach
K4 → K1 mit Ausfahrt nach K3. Der Abschnitt K1 → K3 ist noch nicht abgeschlossen.
Eine eventuell nächste Auswahl wird hier nicht als gefahren ausgegeben.

```json
{
  "robot_id": "RM01", "boot_id": "demo-start-a", "seq": 12,
  "map_version": "demo-karte-v1", "generated_mono_s": 120.0,
  "route": {"history": {
    "status": "valid", "reason": null, "dropped_entries": 0,
    "entries": [
      {"entry_seq": 0, "section": "demo-K7-K4", "node": "K4", "approach_from": "K7", "exit_to": "K1", "confirmed_mono_s": 40.0},
      {"entry_seq": 1, "section": "demo-K4-K1", "node": "K1", "approach_from": "K4", "exit_to": "K3", "confirmed_mono_s": 95.0}
    ]
  }}
}
```

**2. Neustart, erfolgreich initialisiert:** Keine Übernahme aus `demo-start-a`.
Der neue Start hat noch keinen bestätigten Abschluss; gültig leer ist bekannt.
Wäre die Initialisierung fehlgeschlagen, müssten stattdessen `missing`, ein
Grund und beide Nutzwerte `null` erscheinen, nicht die folgende gültige Liste.

```json
{
  "robot_id": "RM01", "boot_id": "demo-start-b", "seq": 0,
  "map_version": "demo-karte-v1", "generated_mono_s": 2.0,
  "route": {"history": {
    "status": "valid", "reason": null, "dropped_entries": 0, "entries": []
  }}
}
```

## Ausstehende Entscheidungen und Folgeauftrag

- **B:** Abschnitt-/Zufahrt-/Ausfahrtkennungen mit B2 festlegen, Bestätigungs-
  und Erfassungslückenkriterien sowie Historienbedarf der Wegwahl benennen.
- **B/C/O:** Umfang im gemeinsamen Zustand versus referenzierte Details,
  16-Eintrags-Grenze, Status-/Resetregeln und Kartenwechselregel bestätigen.
- **C/O mit #15:** Detailnamensraum, Referenzformat und Darstellung fehlender,
  alter oder ungültiger Belege abschließend vereinbaren.
- **O:** Akzeptierten Entwurfscommit dokumentieren und danach einen kleinen
  Implementierungsauftrag für Vertrag/Schema, B-Produzent und Verbraucher mit
  Versionsübergang und passenden Positiv-/Negativtests abgrenzen. Bis dahin
  bleiben Laufzeitabbildung, B2-Navigation und fachliche C1-Abnahme offen.
