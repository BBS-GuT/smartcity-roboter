# C1e: Eindeutige Detailreferenzen – Entscheidungsentwurf

**Status:** Vorschlag für C/O, noch nicht akzeptiert und nicht implementiert.
Auftrag: [#15](https://github.com/BBS-GuT/smartcity-roboter/issues/15),
Elternvertrag [#3](https://github.com/BBS-GuT/smartcity-roboter/issues/3).
Grundlage: [Zustandsvertrag](../schnittstellen-grundbetrieb.md),
[Zieldefinition](../zieldefinition-grundbetrieb.md) §5 und §7 (GB-13, GB-15–18,
A13/A14). Dieser Entwurf schließt keine Fach- oder Geräteabnahme ab.

## Vorgeschlagene Felder und Identität

Die folgende Referenz erweitert künftig `details[]`. Ein separat geliefertes
Detail trägt dieselbe Referenz, damit es ohne den neuesten Zustand zuordenbar
bleibt. Die Feldnamen sind Entscheidungsvorschläge, keine Erweiterung von v1.0.

| Feld | Typ / Einheit | Vorgeschlagene Bedeutung und Geltungsbereich |
|---|---|---|
| `robot_id` | RM01–RM04 | Gerät der Aufnahme; muss zum konsumierten Zustand gehören. |
| `source` | nichtleerer Text | Ausschließlich registrierter Schlüssel unter `sensors`, z. B. `camera` oder `lidar_0`. Kein Topic, keine Aliasauflösung und kein Ersatz durch `source_id`. |
| `source_id` | nichtleerer Text | Technische Quelle des referenzierten Frames; muss der Registrierung für `source` zum Aufnahmezeitpunkt entsprechen. Änderungen der technischen Quelle erhalten einen neuen Produzentenstart. |
| `producer_id` | nichtleerer Text | Registrierter Aufnahmeproduzent der Quelle, unabhängig vom Zustandsaggregator. |
| `producer_boot_id` | nichtleerer Text | Eindeutig je Start dieses Produzenten. Neustart beginnt einen neuen Frame-/Daten-Namensraum, auch bei unverändertem Gerät. |
| `state_boot_id` | nichtleerer Text | `boot_id` des Zustands, der diese Referenz herausgibt. Kein Ersatz für `producer_boot_id`; ein Aggregatorneustart startet den Sensorproduzenten nicht zwangsläufig neu. |
| `frame_id` | nichtleerer Text | Unveränderliche Aufnahmekennung, eindeutig je Gerät, `source`, Produzent und Produzentenstart. Kein Koordinatenrahmen und keine Zustandssequenz. |
| `channel`, `data_id` | nichtleerer Text | Kanal und unveränderliche Datenkennung innerhalb des Frame-Namensraums; mehrere Formate/Ableitungen eines Frames dürfen eigene Datenkennungen tragen. |
| `format` | nichtleerer Text | Beschreibt die konkrete Darstellung; echte Formate, Auflösung und Raten sind noch abzustimmen. |
| `captured_at_s` | endliche Zahl ≥ 0 / Unix-s oder `null` | Aufnahmezeit in UTC; bei unbekanntem UTC-Bezug `null`. Synchronisationsqualität bleibt über den Zustandsvertrag sichtbar. Keine Ersatzzeit für lokale Frische. |
| `time_basis_id` | nichtleerer Text | Kennung der gemeinsamen lokalen monotonen Geräteuhr, neu bei deren Reset (z. B. Geräteboot). Unabhängig von Produzenten- und Zustandsstart. |
| `captured_mono_s` | endliche Zahl ≥ 0 / s oder `null` | Aufnahmezeit in dieser Geräteuhr; Sensoreigenzeit nur nach belegter Umrechnung. |
| `received_mono_s` | endliche Zahl ≥ 0 / s oder `null` | Empfang dieses Frames am Gerät, in derselben Uhr wie `captured_mono_s` und `generated_mono_s`. Erneuter Empfang verjüngt die Aufnahme nicht. |
| `status`, `reason`, `age_s` | bestehender Status; Text oder `null`; endliche Zahl ≥ 0 / s oder `null` | Bewertung im referenzierenden Zustand. `age_s = generated_mono_s - captured_mono_s` nur bei belegtem gleichem Gerät/Zeitbezug. Nicht-`valid` braucht einen Grund. |

Frame-Schlüssel: `(robot_id, source, producer_id, producer_boot_id, frame_id)`.
Daten-Schlüssel: Frame-Schlüssel plus `(channel, data_id)`. `source_id`, Aufnahmezeit,
Zeitbasis und Format sind unveränderliche Metadaten dazu: widersprüchliche
Metadaten bei gleichem Schlüssel sind `invalid`, identische Wiederholungen sind
Duplikate. Kennungen werden als undurchsichtiger Text behandelt; keine versteckten
Geräte-, Start- oder Zeitangaben daraus erraten. Verschiedene Quellen mit gleicher
`frame_id` gehören nicht automatisch zusammen (auch Farbe/Tiefe nicht).

## Zuordnung und Frische

1. Der Produzent führt eine eindeutige Registrierung von `source` zu technischer
   Quelle, Produzent und Start. Der Aggregator bewahrt die zu einem älteren Frame
   gehörenden Metadaten mit der Referenz auf; ein späteres `sensors[source].frame_id`
   überschreibt sie nicht. Historische Zuordnung braucht einen belegten damaligen
   Registereintrag. Fehlt dieser, bleibt sie `unknown`, niemals `valid`.
2. Fremdes Gerät, nicht registrierter `source`, widersprüchliche Quellen-/Frame-
   Metadaten oder nicht belegter Produzentenstart sind für den aktuellen Zustand
   nicht gültig. Historisch bekannte frühere Starts bleiben als solche zuordenbar;
   sie werden nicht still dem aktuellen Start zugeschlagen. `state_boot_id` muss
   zum herausgebenden Zustand passen; bei erneuter Referenzierung wird nur dieser
   Kontext erneuert, die Aufnahmeidentität bleibt erhalten.
3. Für lokale Frische muss dieselbe `time_basis_id` wie im Zustand belegt sein und
   `captured_mono_s <= received_mono_s <= generated_mono_s` gelten. Zukunftswerte,
   fremde Zeitbasis und unzulässige Zahlen sind `invalid` mit `age_s = null`.
   Fehlender Zeitnachweis ist `unknown`; UTC-Synchronisation allein repariert
   keinen monotonen Bezug. Aufnahmealter zählt, nicht Übertragungsalter.
4. Ein älterer Frame ist grundsätzlich erlaubt. Bei auflösbarer Identität,
   brauchbarer Aufnahme und passendem Zeitbezug ist er innerhalb der vereinbarten
   Kanal-Altersgrenze `valid`, darüber `stale`. Gleichheit mit dem neuesten
   `sensors[source].frame_id` ist keine Gültigkeitsbedingung. Ein aktueller
   Quellenfehler macht eine frühere brauchbare Aufnahme nicht rückwirkend falsch;
   sie belegt aber auch keine aktuelle Sensorverfügbarkeit.
5. `missing` bezeichnet fehlende Detaildaten (Zeitwerte/Alter `null`), `unknown`
   eine noch nicht belegte Zuordnung oder Frische, `invalid` einen Widerspruch oder
   unbrauchbare Aufnahme, `stale` eine zu alte sonst brauchbare Aufnahme. Identität
   und Fehlergrund bleiben auch bei nicht gültigen Details sichtbar. Nach Reset
   der Geräteuhr bleiben alte Frames historisch zuordenbar, für den aktuellen
   Zeitkontext aber `invalid`, nicht scheinbar frisch.

Panel und MQTT zeigen dieselbe Referenz und Bewertung aus demselben Zustand;
zusätzliches Transportalter ist getrennt sichtbar. Ein Empfänger ohne passenden
lokalen Uhrbezug darf keine eigenen monotonen Differenzen bilden. Eine spätere
Neubewertung erhält einen neuen Zustandsdatensatz; Payload und Aufnahmeidentität
bleiben unverändert. Diagnoseansichten dürfen alte Details gekennzeichnet zeigen,
sie ersetzen keine aktuellen Pflichtsensordaten und erzeugen keine Motorfreigabe.

## Vier synthetische Beispiele

Gemeinsamer hypothetischer Kontext: `robot_id = RM02`, Zustands-`boot_id = state-B`,
`generated_mono_s = 105.0`, Gerätezeitbasis `clock-1`. Registriert sind
`camera -> (rgb-test, camera-driver, camera-A)` und
`lidar_0 -> (scan-test, lidar-driver, lidar-A)` für technische Quelle, Produzent und
Produzentenstart. Neueste Frames: `rgb-12` und `scan-24`. Nur für diese Beispiele
gilt eine **frei erfundene** Altersgrenze von 1 s; sie ist keine Fachschwelle.
`example/rgb` und `example/scan` sind Formatplatzhalter. Die JSON-Ausschnitte sind
Entwurfsreferenzen, keine vom heutigen v1.0-Validator akzeptierten Fixtures.

**1. Kamera: älterer Frame bleibt eindeutig zuordenbar, ist aber alt.**
`rgb-10` ist historisch mit genau diesen Metadaten registriert; der neueste Frame
`rgb-12` wird nicht zum Ersatz. Aufnahmealter 2 s ergibt `stale`.

```json
{"robot_id":"RM02","source":"camera","source_id":"rgb-test","producer_id":"camera-driver","producer_boot_id":"camera-A","state_boot_id":"state-B","frame_id":"rgb-10","channel":"color","data_id":"color-10","format":"example/rgb","captured_at_s":1792653603.0,"time_basis_id":"clock-1","captured_mono_s":103.0,"received_mono_s":103.1,"status":"stale","reason":"age_limit_exceeded","age_s":2.0}
```

**2. LiDAR: auch ein nicht neuester Frame darf aktuell sein.**
`scan-23` ist mit den angegebenen Metadaten registriert; Alter 0,2 s liegt innerhalb
der Beispielgrenze, obwohl `sensors.lidar_0.frame_id = scan-24` ist.

```json
{"robot_id":"RM02","source":"lidar_0","source_id":"scan-test","producer_id":"lidar-driver","producer_boot_id":"lidar-A","state_boot_id":"state-B","frame_id":"scan-23","channel":"scan","data_id":"scan-data-23","format":"example/scan","captured_at_s":1792653604.8,"time_basis_id":"clock-1","captured_mono_s":104.8,"received_mono_s":104.9,"status":"valid","reason":null,"age_s":0.2}
```

**3. Fremde Quelle: die bekannte Kamera-Frame-ID genügt nicht.**
`foreign_camera` ist kein `sensors`-Schlüssel. Weder `rgb-10` noch die technische
Kennung lösen einen Alias auf; keine Zuordnung zur lokalen Kamera, `invalid`.

```json
{"robot_id":"RM02","source":"foreign_camera","source_id":"rgb-test","producer_id":"camera-driver","producer_boot_id":"camera-A","state_boot_id":"state-B","frame_id":"rgb-10","channel":"color","data_id":"color-10","format":"example/rgb","captured_at_s":1792653603.0,"time_basis_id":"clock-1","captured_mono_s":103.0,"received_mono_s":103.1,"status":"invalid","reason":"source_not_registered","age_s":null}
```

**4. Unpassende Zeitbasis: numerisch plausible Sekunden ergeben keine Frische.**
Ein historisch belegter Frame aus `camera-old` / `clock-old` gehört zum Gerät,
aber nicht zur aktuellen Geräteuhr. Seine Aufnahme bleibt identifizierbar;
`105.0 - 104.9` darf hier nicht gerechnet werden, `invalid` im aktuellen Kontext.

```json
{"robot_id":"RM02","source":"camera","source_id":"rgb-test","producer_id":"camera-driver","producer_boot_id":"camera-old","state_boot_id":"state-B","frame_id":"rgb-9","channel":"color","data_id":"color-9","format":"example/rgb","captured_at_s":1792650000.0,"time_basis_id":"clock-old","captured_mono_s":104.9,"received_mono_s":104.95,"status":"invalid","reason":"timebase_mismatch","age_s":null}
```

## Entscheidungen und Folgeabhängigkeiten

- C/O entscheiden Feldnamen, Schlüssel und Statusregeln dieses Vorschlags auf
  einem konkreten Vertragscommit. Die Unterscheidung von Produzentenstart,
  Zustandsstart und Gerätezeitbasis muss mit dem
  [Fahrwunschauftrag #16](https://github.com/BBS-GuT/smartcity-roboter/issues/16)
  gemeinsam bestätigt werden; dessen Entwurf wird hier nicht vorweggenommen.
- C/A/B legen Registrierung, historische Metadatenhaltung, Aufbewahrungsgrenzen
  und Nachweis der Abbildung von Sensoreigenzeit auf die Geräteuhr fest. Auch nach
  Verdrängung eines Payloads darf dessen Kennung nicht wiederverwendet werden;
  ohne Zuordnungsbeleg bleibt die Referenz ausdrücklich unbestätigt.
- C/B/E und Dashboard-/Brokerteam vereinbaren Kanalformate, Umfang, Rate,
  Frischegrenzen und gegebenenfalls Farb-/Tiefenpaarung. Dafür sind noch keine
  realen Mess- oder Brokerwerte belegt.
- [#14](https://github.com/BBS-GuT/smartcity-roboter/issues/14) liefert die
  `sensors`-Schlüsselregel;
  [#13](https://github.com/BBS-GuT/smartcity-roboter/issues/13) die monotone
  Quellenempfangszeit. Nach fachlicher Bestätigung erstellt O einen kleinen
  Implementierungsauftrag für Versionierung, Referenz-/Registerabbildung,
  Python, Schema und positive/negative Vertragstests. Dieser PR ändert nur diese
  Datei; keine Laufzeitfelder, Fixtures, Detailübertragung oder Brokeranbindung.
  Elternissue #3 bleibt offen.
