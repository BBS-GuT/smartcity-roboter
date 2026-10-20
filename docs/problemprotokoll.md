# Problem → Lösung: Protokoll

Was auf dem Roboter (RM02) schiefging, woran man es gesehen hat, was die Ursache war und was geändert wurde.
**Status** sagt ehrlich, wie weit es geprüft ist:

- **am Roboter bestätigt:** im echten Log gesehen, dass es jetzt geht
- **mit Aufnahme geprüft:** mit einer echten Messfahrt nachgerechnet (`kartograf/abspielen.py`)
- **nur Test:** automatischer Test ohne Roboter (`tests/`)
- **offen:** noch nicht gelöst

Neue Einträge oben anfügen. Logs: Panel → System → „Logs herunterladen“. Messfahrt: Panel → Karte → Aufnahme.

---

## 20.10.2026, Lauf 11:20–11:31 (Logs + Messfahrt `smartcity_20261020_112619`)

**Wichtig vorab:** Dieser Lauf lief **ohne** die Fixes aus PR #44 (nicht gemerged). Dass „Hindernis überfahren“ und
„Karte verdreht“ wieder auftraten, war also zu erwarten. Die Aufnahme hat aber die eigentlichen Ursachen gezeigt.

### Ganzer Rechner hängt immer wieder 1–2 s
- **Symptom:** Linienfolger: „KI-ZENTRALE ANTWORTET NICHT -> STOPP“ ständig. Wegräumen bricht ab.
- **Beleg (Messfahrt):** In 210 s kamen Lagesensor, Räder, beide LiDARs **und** KI-Befehle über 50-mal
  **gleichzeitig** 0,6–2,3 s lang nicht an. Auch die Zeitstempel der Sensoren selbst haben diese Lücken.
- **Ursache:** Nicht die KI allein, sondern der ganze Rechner (Überlast, Speicher/Swap, Speicherkarte oder
  Temperatur). Welches Programm, ist **noch nicht gemessen**.
- **Lösung:** `logs/system.log` (neu, `lib/systemlast.py`): alle 2 s CPU, IO-Warten, RAM/Swap, GPU, Temperatur und
  die 5 Programme mit der meisten Rechenzeit. „HING x s“, wenn der Rechner selbst hing.
  Entlastung aus PR #44 (eigener Thread für Entscheiden, Panelbild 3×/s, Karte-Kamera 1×/s).
- **Status:** offen. Nächster Lauf mit `system.log` zeigt den Schuldigen.

### Karte verdreht und doppelt
- **Symptom:** Raum doppelt und gegeneinander verdreht (Panelbilder 20.10.).
- **Beleg (Messfahrt abgespielt):** Abgleich sicher nur in Minute 1 (56 %), danach 0 %.
- **Ursache 1, Lücken:** Fehlt der Lagesensor länger als 0,25 s, wurde die Drehung dieser Zeit **verworfen**;
  bei den Rädern wurde ab 0,5 s die Strecke abgeschnitten. Test: 1,5 s Lücke = **45° und 16,5 cm verloren**.
  → Lösung: Räder-Position (läuft lückenlos weiter) für Strecke und, nach einer Lagesensor-Lücke, für die Drehung.
- **Ursache 2, Geister-Zimmer:** War die Position unsicher, wurde ein Scan trotzdem eingetragen, wenn er an der
  (falschen) Position zu < 30 % auf Bekanntes fiel („neues Gebiet“). Bei falscher Position ist das fast immer so.
  → Lösung: „neues Gebiet“ nur bis 1,5 s / 40 cm / 15° nach dem letzten sicheren Abgleich.
- **Ursache 3, falscher Haupt-LiDAR:** Der Abgleich hing an `/scan0`. Der dreht beim Scan-Abgleich nur ×0,8 so viel
  wie Räder und Lagesensor, `/scan1` ×1,0. Ausgemessen: `/scan0` sitzt ca. 23 cm hinter und 13 cm neben `/scan1`,
  die Karte rechnet aber jeden LiDAR in der Robotermitte.
  → Lösung: `haupt_lidar: '/scan1'` für den Kartografen (`config/roboter.yaml`).
  Abgespielt: sicher 72 % / 91 % statt 56 % / 0 % in Minute 1 / 2, Karte ohne Doppelbild.
- **Ursache 4, Selbstkalibrierung:** lernte aus diesen Daten „Lagesensor misst 150 %“ (falsch). → aus (PR #44).
- **Status:** mit Aufnahme geprüft + Tests (`tests/test_kartenluecken.py`). Am Roboter noch nicht.
- **Offen:** Ab Minute 3 der Messfahrt findet er die Position nicht wieder. Odometrie meldet Stillstand, die
  Übereinstimmung fällt schlagartig. Vermutlich umgesetzt oder Leute direkt am Roboter. Die Karte wird dabei jetzt
  nicht mehr zerstört, die Wiederfindung (weite Suche) muss aber besser werden.

### LiDAR-Positionen für die Hinderniserkennung nicht eingemessen
- **Ursache:** KI und Linienfolger rechnen ebenfalls beide LiDARs in der Robotermitte. Bei ~25 cm Versatz stimmen
  Abstände zu Hindernissen (Notbremse 12 cm!) für mindestens einen LiDAR nicht.
- **Status:** offen, **sicherheitsrelevant**. Braucht eine Messung am Roboter: Wo genau sitzen beide LiDARs
  (x vor / y links der Robotermitte, in cm) und wohin zeigt jeweils 0°?

### Wegräumen: „keine erreichbare Ablagestelle“
- **Beleg:** `ki.log` mehrfach „zur Seite (4 / 18 / 19–20 cm)“: keine der 8 Ablagestellen erreichbar.
- **Status:** offen. Braucht Messung am Arm (welche Seitenpositionen erreicht er in Fahrstellung?).

---

## 20.10.2026, Lauf 10:53–11:03

### Hindernis überfahren
- **Symptom:** „Hindernis beim Heranfahren aus den Augen verloren“ → 1 s später „Weg ist wieder frei“ →
  Notbremse 10 cm / drüber.
- **Ursache:** Hindernis (5 cm hoch) zu nah für die Kamera und unter der LiDAR-Ebene: kein Sensor sah es mehr.
- **Lösung (PR #44):** Stelle merken (Abstand + Radzähler). Zu nah für die Kamera → Halt „wegnehmen, dann STOPP
  und START“. Erst vergessen, wenn die Kamera die Stelle frei sieht oder START kommt.
- **Status:** nur Test (`tests/test_entscheider.py`). Lauf 11:26 zeigt denselben Fehler noch, da #44 nicht drauf war.

### KI antwortet nicht
- **Lösung (PR #44):** Entscheiden in eigenem Thread, Panelbild 3×/s, Zebrastreifen ohne zweite Liniensuche,
  Diagnose (KI-Warnungen, Linienfolger: „KI war x s still“).
- **Status:** offen (siehe oben: ganzer Rechner hängt).

---

## 20.10.2026, Lauf ~09:30 (erste Logs)

### Kartograf stürzt bei jedem Start ab → „Neue Karte“ geht nicht
- **Beleg:** `karte.log`: `TypeError: 'NoneType' object is not iterable` in `Kalibrierung.__init__`.
- **Ursache:** Ungelernter LiDAR-Einbau wird als `null` gespeichert, beim Laden nicht akzeptiert.
- **Lösung (PR #22, #19):** laden mit Standardwert. „Neue Karte“ erst vorbereiten, aktuellen Stand sichern, eindeutige
  Sicherung, Panel meldet Erfolg nur bei Bestätigung genau dieses Auftrags.
- **Status:** am Roboter bestätigt (`karte.log` 11:26: „Neue Karte angefangen, alte gesichert …“).

### „Hindernis ist Person“, wartet ewig
- **Ursache:** Ein einziges Bild mit „Person“ (meist die Hand beim Hinlegen) reichte. Danach wartete er, bis der
  Weg frei war, also ewig.
- **Lösung (PR #22):** ab 2 Bildern. Nach 3 s ohne Person neu hinschauen.
- **Status:** am Roboter bestätigt (`ki.log` 11:27: „niemand mehr in Sicht -> schaue nochmal hin“).

### Wegräum-Sperre nach Abbruch
- **Lösung (PR #18 → korrigiert in PR #22, B1 #13):** nur ein ausdrücklicher START im Panel hebt sie auf. Ein kurzer
  Statusaussetzer zählt nicht als START.
- **Status:** am Roboter bestätigt (`ki.log`: „START quittiert: Fehler/Hindernis wird neu geprueft“).

### Rote Ampel nach 4 s „vergessen“ (B1 #13)
- **Lösung (PR #22):** Rot gilt bis Grün erkannt wird.
- **Status:** nur Test.

---

## 20.10.2026, morgens

### Keine Logs zum Auswerten
- **Ursache:** Logs lagen in `/tmp`, das beim Neustart geleert wird.
- **Lösung (PR #18, #20):** `logs/<programm>.log` + vorheriger Lauf `.alt.log`, Panel → System → „Logs herunterladen“,
  robust gegen Neustart während des Downloads.
- **Status:** am Roboter bestätigt (Logs kamen an).
