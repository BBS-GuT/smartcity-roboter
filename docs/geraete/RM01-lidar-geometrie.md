# RM01 – LiDAR-Quellen und Einbaupose

Bezug: [#66 E1-L](https://github.com/BBS-GuT/smartcity-roboter/issues/66), Elternissue
[#58](https://github.com/BBS-GuT/smartcity-roboter/issues/58), Verwendung in
[#64 L5](https://github.com/BBS-GuT/smartcity-roboter/issues/64), Abnahme
[#67 E2-L](https://github.com/BBS-GuT/smartcity-roboter/issues/67).

**Stand: Messblatt vorbereitet, Messung offen.** Kein Wert in Abschnitt 4 ist bisher am
RM01 gemessen. Solange dort „offen“ steht, bleibt die Einbaupose unbekannt und der
Roboter hält (gewollt, siehe [gemeinsame Abdeckung](../lidar-gemeinsame-abdeckung.md)).
Keine Werte auf andere Roboter übertragen; RM02 bleibt [#37](https://github.com/BBS-GuT/smartcity-roboter/issues/37).

## 1. Was bisher bekannt ist – nach Belegklasse getrennt

| Belegklasse | Inhalt | Darf als Einbaupose dienen? |
|---|---|---|
| Werksmodell (M3Pro.urdf, Modell-SHA256 `6001d4747d0ed68826a2bacad0891aec531fb9217351c2ffff72114909825acf`, [historische Geometrie](../pruefungen/lidar-20261021/historische_geometrie.py)) | `laser0_frame` x −0,11617 / y +0,09156 / z 0,1253 m; `laser1_frame` x +0,10766 / y −0,09078 / z 0,1253 m; rpy jeweils 0 | **Nein.** Nur Rechen- und Testbezug (`werksmodell`). |
| Bisherige Zuordnung aus dem Prüfbestand ([Bericht 21.10.](../abnahme/RM01-2026-10-21-lidar-software.md)) | `/scan1` vorne rechts, `/scan0` hinten links | **Nein.** Topicnamen und frühere Notizen ersetzen keine Zuordnungsprobe. |
| Radiale Referenzmessung 21.10. | 50/100-cm-Ziele: 49,8/100,2 cm (`/scan1`), 49,7/99,7 cm (`/scan0`) | **Nein.** Bestätigt die Entfernungsmessung, nicht die Lage im Fahrzeug. |
| Private horizontale Einzelmaße 22.10. | Liegen laut [Nachtstand](../abnahme/lidar-nachtstand-2026-10-22.md) im privaten Prüfbestand | Nur zusammen mit den fehlenden Größen aus Abschnitt 4. Bei der Messung als `sensoren:` (Maßband) zum Abgleich eintragen. |
| Relative Schätzung aus dem Scanabgleich | Für RM01 keine. Die Angabe „23 cm hinter, 13 cm neben“ in `config/roboter.yaml` stammt von **RM02**. | **Nein.** |

## 2. Bezug vor der Messung festlegen

- **Ursprung `base_link`:** einen am Gerät wiederauffindbaren Punkt wählen und
  markieren (Foto). Empfehlung: wie im Werks-URDF die Mitte zwischen den Rädern in
  der Draufsicht, Höhe Boden. Einbaupose, Fahrzeuggrenzen und Kamera beziehen sich alle
  auf denselben Punkt.
- **Achsen:** x vorne, y links, z oben, Meter. Winkel gegen den Uhrzeigersinn positiv.
- **Sensorursprung:** das Dreh- und Messzentrum des LiDARs, nicht eine Gehäusekante
  (Datenblatt oder Markierung am Gehäuse).
- **Fahrstellung:** Arm in Fahrstellung, alle Anbauteile wie im Betrieb.

## 3. Messablauf

Alles läuft am stehenden Roboter. Das Werkzeug `scripts/lidar_einmessen.py` liest nur
LaserScans und sendet **keine** Fahr- oder Armbefehle. Rohaufnahmen landen in
`config/lokal/lidar_einmessung/`; dieser Ordner wird nicht ins Repository übernommen.

1. **Stand festhalten:** Fahrprogramme beenden (`scripts/stopp.sh`), nur die
   LiDAR-Treiber laufen lassen. Installierten Commit notieren (`git rev-parse HEAD`,
   `git status --short`). Das Werkzeug speichert beides in jeder Aufnahme mit.
2. **Hintergrund aufnehmen:** Niemand steht in Sensorsicht. Dann:
   `source scripts/env.sh && python3 scripts/lidar_einmessen.py aufnehmen hintergrund`
3. **Standcheck:** `python3 scripts/lidar_einmessen.py standcheck config/lokal/lidar_einmessung/hintergrund.json`
   Damit sind die offenen Fragen aus #58 je Quelle beantwortet: tatsächlicher
   `header.frame_id`, Zeitstempelalter (≤ 1 s, nicht in der Zukunft), Sektoren ohne
   Messung (eigener Aufbau?), Werte genau auf `range_max` oder `inf` und Treffer
   näher als 12 cm. Die Hinweise ins Messblatt übernehmen.
4. **Zuordnung Sensor ↔ Topic:** Eine Hand oder Kiste etwa 5–10 cm vor **einen**
   physischen Sensor halten und `aufnehmen zuordnung_vorne_rechts` starten. Im
   Standcheck dieser Aufnahme darf, im Vergleich zum Hintergrund, nur der zugehörige
   Kanal neue nahe Treffer zeigen.
   Danach den anderen Sensor prüfen. Melden beide Treiber denselben Frame, muss ein
   Treiber-Frame umbenannt werden, sonst hält der Roboter (#64).
5. **Zielstäbe:** Einen dünnen senkrechten Stab (z. B. Rundholz 20 mm, höher als die
   Messebene) nacheinander an mindestens **vier** Stellen aufstellen. Die Stellen
   liegen 0,3–1,0 m vom Roboter entfernt, rund um ihn verteilt und nicht auf einer
   Linie. Möglichst jede Stelle sollte für beide Sensoren sichtbar sein. Die Stabmitte
   per Maßband und Winkel vom markierten Ursprung messen (x, y, Unsicherheit notieren).
   Nach dem Aufstellen aus der Sensorsicht treten, dann `aufnehmen ziel1` usw.
6. **Maßband-Abgleich:** Die Sensormitten unabhängig mit dem Maßband messen. Stimmen
   Zielmessung und Maßband nicht überein, meldet das Werkzeug einen Widerspruch
   (z. B. vertauschte Topics).
7. **Auswerten** (auch am Laptop, ohne ROS): Messdatei
   `config/lokal/lidar_einmessung/messung.yaml` anlegen und
   `python3 scripts/lidar_einmessen.py auswerten config/lokal/lidar_einmessung/messung.yaml` starten.

   ```yaml
   geraet: RM01
   datum: JJJJ-MM-TT
   pruefer: Name
   bezug: "Mitte zwischen den Raedern, Boden; Markierung siehe Foto"
   hintergrund: hintergrund.json
   ziel_durchmesser: 0.020      # m
   ziel_unsicherheit: 0.005     # m je Achse (Massband + Aufstellung)
   ziele:
     - {aufnahme: ziel1.json, x: 0.60, y: 0.05}
     - {aufnahme: ziel2.json, x: 0.35, y: 0.45}
     - {aufnahme: ziel3.json, x: -0.50, y: -0.30}
     - {aufnahme: ziel4.json, x: 0.10, y: -0.55}
   sensoren:                    # optional, Massband
     /scan0: {x: -0.11, y: 0.09, unsicherheit: 0.01}
     /scan1: {x: 0.11, y: -0.09, unsicherheit: 0.01}
   ```
   Die Zahlen oben sind **Beispiele**, keine RM01-Werte. Ausgegeben werden je Quelle
   x, y und `scan_front_deg` mit erweiterter Unsicherheit (k = 2), RMS und größtes
   Residuum, die Jackknife-Spanne (Ziel einzeln weggelassen) und der Maßband-Abgleich.
   Nur ohne Probleme folgt ein Vorschlag für `config/lokal/roboter.yaml`. Mehrdeutige
   Aufnahmen (z. B. Person noch im Bild) werden verworfen und nicht geraten.
8. **Höhe z:** Höhe der Messebene über dem Boden = Höhe der Sensormitte (Maßband und
   Datenblatt). Dieser Wert ist nicht Teil des planaren Vertrags, entscheidet aber,
   welche niedrigen Hindernisse unsichtbar bleiben (siehe M04 in der
   [Ausfallmatrix](../abnahme/lidar-messung-und-ausfallpruefung.md)).
9. **Neigung der Messebene:** Eine flache Kiste in 0,3 m und in 1,5 m Abstand vor den
   Sensor stellen und ihre Höhe mit untergelegten Brettchen in 5-mm-Schritten
   erhöhen, bis der Standcheck sie erkennt. Unterscheiden sich die Erkennungshöhen
   h₁ und h₂, ist die Ebene geneigt: Neigung ≈ atan((h₂ − h₁) / 1,2 m). Eine
   ungeklärte Neigung bleibt „offen“ und gilt nicht als waagrecht.
10. **Fahrzeuggrenzen:** Die äußersten Punkte der ganzen Fahrstellung (Räder,
    Sensoren, Kamera, Arm) als positive Abstände vom Ursprung messen:
    `[vorne, hinten, links, rechts]`. Beide Sensorursprünge müssen darin liegen.

## 4. Messblatt RM01

Pro Messung einen neuen Block anlegen; alte Ergebnisse nicht überschreiben.
Rohaufnahmen bleiben privat und werden hier nur mit Namen genannt.

| Kopf | Eintrag |
|---|---|
| Gerät / physische Kennzeichnung | RM01 / offen |
| Datum, prüfende Person, beobachtende Person | offen |
| Installierter Commit, sauberer Baum | offen |
| Ursprung `base_link` (Beschreibung, Foto) | offen |
| Fahrstellung (Arm, Anbauteile) | offen |
| Messmittel (Maßband, Winkel, Stab-Ø) | offen |

| Größe je Quelle | Quelle A | Quelle B |
|---|---|---|
| Physischer Ort (z. B. vorne rechts) | offen | offen |
| Topic | offen | offen |
| `header.frame_id` (Standcheck) | offen | offen |
| Zuordnungsprobe (Aufnahme, Ergebnis) | offen | offen |
| x / U (m) | offen | offen |
| y / U (m) | offen | offen |
| z der Messebene / U (m) | offen | offen |
| `scan_front_deg` / U (Grad) | offen | offen |
| Neigung der Messebene / U (Grad) | offen | offen |
| Maßband-Abgleich x/y | offen | offen |
| Standcheck-Hinweise (Blindsektoren, `range_max`, `inf`, Zeit, nahe Treffer) | offen | offen |
| Belegklasse | offen (Ziel: gemessen) | offen (Ziel: gemessen) |

| Fahrzeug | Eintrag |
|---|---|
| `fahrzeug_grenzen` [vorne, hinten, links, rechts] / U (m) | offen |
| Äußerer Blindbereich, den kein Sensor misst | offen |

## 5. Übertrag in den Produktvertrag

Der planare Vertrag aus [#63](https://github.com/BBS-GuT/smartcity-roboter/issues/63)
rechnet `p_basis = R(−scan_front_deg) · p_sensor + (x, y)`, also **genau eine** Drehung
und eine Verschiebung. `scan_front_deg` ist der Sensorwinkel, unter dem der Sensor die
Robotervorderrichtung sieht. Sieht ein Sensor vorne bei seinen +90°, steht dort 90.
Das Werkzeug gibt die Werte in genau dieser Form aus. Für den Übertrag:

1. Werte erst eintragen, wenn Abschnitt 4 vollständig ist (Datum, Person,
   Unsicherheit).
2. In `config/lokal/roboter.yaml` setzen: `scan_frames`, `scan_front_deg`,
   `scan_einbau_xy`, `scan_einbau_quelle: ['gemessen', 'gemessen']` und
   `fahrzeug_grenzen`. Nicht in `config/roboter.yaml` (gilt für alle Roboter).
3. Programme neu starten. Liefert ein Treiber schon `base_link`, gilt Nullversatz und
   `scan_front_deg = 0`. Jede Quelle und jeder Frame darf nur einmal vorkommen.
4. Danach folgt die statische Etappe aus #67. Grüne Softwaretests oder ein gesetztes
   `gemessen` sind keine Fahrfreigabe.

## 6. Grenzen

- z, Neigung und Unsicherheit sind keine Felder des planaren Produktvertrags. Sie
  bleiben trotzdem Pflichtnachweise für die Eignung.
- Die Zielmessung prüft die Lage in der Messebene. Sie ersetzt nicht die Prüfung des
  äußeren Nahbereichs: Ein Sensor an der Fahrzeugkante kann innerhalb seines
  `range_min` blind sein. Diese Lücke bleibt sperrend, bis eine Montage- oder
  Sensorlösung nachgewiesen ist.
- Das Werkzeug ist mit synthetischen Scans aus bekannter Pose getestet
  (`tests/test_lidar_einmessen.py`). Am echten RM01 ist es noch nicht gelaufen.
