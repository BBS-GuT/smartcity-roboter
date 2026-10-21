# Erste Inbetriebnahme

Checkliste, bevor ein Roboter zum ersten Mal fährt. Reihenfolge einhalten. Alle Einstellungen landen in `config/lokal/` (nicht im Repository, bleibt bei Updates erhalten). Was bei einem Wert „geschätzt“ steht, ist **nicht** am Roboter gemessen.

## 1. Roboter erkennen

- [ ] Panel → System → „Systemcheck“: Roboter-Name, Netz, Software-Version und micro-ROS-Agent prüfen.
- [ ] Panel → Sensoren: Kamera, Tiefe, beide LiDAR (`/scan0`, `/scan1`), Odometrie und Lagesensor liefern Daten mit Messrate. Ein Topic, das nur existiert, ist kein Datenstrom.
- [ ] Läuft noch ein anderer Roboter mit derselben Domain-ID? Dann einen ausschalten ([Roboter und Netz](Roboter-und-Netz)).

## 2. LiDAR „vorne“

- [ ] Panel → LiDAR: Gegenstand vor die Kamera-Seite stellen, mit den Pfeilen drehen, bis er oben im Bild erscheint, **Speichern**.
- Wichtig für die Notbremse (12 cm). Die genaue Einbaulage beider LiDARs ist noch nicht vermessen; der Versatz von ca. 25 cm zwischen ihnen ist für die Hinderniserkennung **offen und sicherheitsrelevant** (siehe [Problemprotokoll](Problemprotokoll)).

## 3. Arm in Fahrstellung

Die Kamera sitzt am Arm. Ohne richtige Fahrstellung stimmt die Draufsicht nicht.

- [ ] Panel → Arm: Fahrstellung prüfen (voreingestellt: Startstellung der Gamepad-Steuerung **90, 120, 10, 20, 90, Greifer 30**). Bei Bedarf neu einlernen.
- [ ] Greifer auf / zu prüfen. Ist es vertauscht, in `config/lokal/arm.yaml` `greifer_auf: 130` und `greifer_zu: 30` eintragen.
- [ ] Greifer einmessen (Panel → Arm → „Greifer einmessen“), sonst ist die Greifkraft nur geschätzt.
- Details und alle weiteren Schritte zum Greifen: [`docs/greifarm.md`](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/greifarm.md#vor-dem-ersten-echten-versuch-in-dieser-reihenfolge).

## 4. Kamera nachmessen

Eingestellt sind geschätzte Werte (`kamera_hoehe` 0,22 m, `kamera_neigung` 32°). Ein öffentliches Robotermodell spricht eher für ca. 31 cm Höhe. Eine falsche Neigung verzerrt Linie, Karte und Tiefe.

- [ ] Mit dem Arm in Fahrstellung Höhe der Linse über dem Boden messen.
- [ ] In `config/lokal/roboter.yaml` eintragen:
  ```yaml
  /**:
    ros__parameters:
      kamera_hoehe: 0.21
      kamera_neigung: 35.0
  ```
- [ ] Neigung prüfen: Panel → TEST, Roboter gerade auf eine gerade Linie stellen. In der Draufsicht muss die Linie **senkrecht und gleich breit** sein. Nach oben breiter = Neigung zu klein, schmaler = zu groß.
- Details: [`docs/linie.md`](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/linie.md#kamera-nachmessen-wichtig).

## 5. Ampel-Farben

- [ ] Panel → System → „Ampel einstellen“: LED-Farben der SmartCity-Ampeln einlernen.

## 6. Erste Fahrt

- [ ] Panel → **TEST**: Entscheidungen und Gründe im Dashboard ansehen, ohne dass er fährt.
- [ ] **START** mit 0,15 m/s auf freier Strecke, eine Hand am STOPP.
- [ ] Bei Auffälligkeiten: Logs herunterladen und im [Problemprotokoll](Problemprotokoll) nachsehen. Bei Kartenproblemen: [Messfahrt aufzeichnen](Messfahrt-aufzeichnen).

Gemessene Werte (Maße, Kalibrierung) bitte zusätzlich mit Datum und Person in `docs/geraete/RM0x.md` festhalten (per PR). Nur so werden sie für die Abnahme verwendbar.
