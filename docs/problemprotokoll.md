# Problem → Lösung: Protokoll

Was auf dem Roboter (RM02) schiefging, woran man es gesehen hat, was die Ursache war und was geändert wurde.
**Status** sagt ehrlich, wie weit es geprüft ist:

- **am Roboter bestätigt:** im echten Log gesehen, dass es jetzt geht
- **mit Aufnahme geprüft:** mit einer echten Messfahrt nachgerechnet (`kartograf/abspielen.py`)
- **nur Test:** automatischer Test ohne Roboter (`tests/`)
- **offen:** noch nicht gelöst

Neue Einträge oben anfügen. Logs: Panel → System → „Logs herunterladen“. Messfahrt: Panel → Karte → Aufnahme.

---


## 20.10.2026, Lauf 14:0x–14:27

### Greifen: mal zu fest (Greifer knackt), mal zu schwach (Würfel bleibt stehen)
- **Beleg:** `ki.log`: 15 Greifversuche, 2 Erfolge. Würfel 3 cm breit, 7 cm hoch. Die tatsächlich benutzte
  Korrektur wich beim Ausprobieren bis 3,5 cm von der gelernten ab (z. B. „-0.0 / +3.5“).
- **Ursache (vermutet):** Bei 8,5 cm Öffnung und 3 cm Würfel darf er höchstens ~2,75 cm danebenliegen. Weiter
  daneben trifft eine Backe die Kante: Würfel rutscht weg oder wird verkantet gequetscht. Dazu fuhr der Greifer
  immer mit voller Geschwindigkeit auf festen Wert 130.
- **Lösung:** Ausprobieren auf 40 % des Spielraums begrenzt. Greifer erst schnell anlegen, dann langsam
  zudrücken; Zielwert nach gemessener Breite (`config/arm.yaml`, Werte geschätzt).
- **Status:** nur Test. Am Roboter: knackt es noch → `greifer_druecken` kleiner; rutscht er → größer.

### „Zu nah für die Kamera“ statt Prüfblick
- **Beleg:** „Hindernis vorhin gesehen, jetzt nicht mehr (zu nah?) -> fahre etwas zurueck“, mehrmals
  „hinten nicht frei -> warte (wegnehmen, dann STOPP und START)“.
- **Lösung:** Prüfblick wieder da (war seit dem Umbau auf berechnete Armbewegungen weg), jetzt mit Messung
  (eigenes Kameramodell für die Pose). Siehe `docs/ki.md`.
- **Status:** nur Test. Kameramodell im Prüfblick aus nicht nachgemessenen Armmaßen gerechnet.

## 20.10.2026, Lauf 11:54–12:00 (mit PR #44; Logs + Messfahrt `smartcity_20261020_115423`)

### Karte: gelöst
- **Beleg (Messfahrt abgespielt):** Abgleich sicher **94 %** (vorher 19 %), Minute 1–7: 100/100/99/92/78/89/100 %,
  längste unsichere Zeit 7,8 s (vorher 176 s). Scan dreht ×0,98 / ×0,97 wie Lagesensor / Räder.
  Der Kartograf hat den Versatz von `/scan0` gegenüber `/scan1` selbst gelernt: **−26,6 cm / +18,5 cm, −0,2°**
  (passt zur eigenen Messung vom Lauf davor, ca. −23 / +13 cm).
- **Status:** am Roboter bestätigt (Panelbild: ein Raum, kein Doppelbild) + mit Aufnahme geprüft.

### Ursache der Hänger gefunden: Linienfolger braucht 200–500 % CPU
- **Beleg (`system.log`):** Sobald der Linienfolger läuft: dauerhaft ~200 %, alle paar Sekunden 6–10 s lang
  **~500 %** → CPU 100 %, Last 12–14. Ohne Linienfolger: CPU 30–55 %.
- **Beleg (Linienfolger-Log + Messfahrt):** „KI-Zentrale war 6,9 s still“, aber die KI meldet „Takt max 100 ms“ und
  der Kartograf hat in denselben Sekunden 50 KI-Befehle empfangen. Die KI hat also geliefert, der **Linienfolger** kam
  nicht dazu, sie zu lesen.
- **Ursache (wahrscheinlich, noch nicht bewiesen):** Python kann höchstens ~100 % nutzen. 500 % kommen aus nativen
  Threads, typischerweise aus Mathe-Bibliotheken (OpenBLAS/OpenMP), die auf allen Kernen aktiv warten. Der Linienfolger
  rechnet bei jedem Bild SVD/polyfit (NumPy). Die Arbeit selbst ist klein (Liniensuche hier gemessen: ~2 ms pro Bild).
- **Lösung:** `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1` in Linienfolger, KI, Kartograf und
  Panel (die gestarteten Programme erben es), `cv2.setNumThreads(1)` in Linienfolger und Kartograf.
  `system.log` zeigt jetzt zusätzlich die Threads des stärksten Programms.
- **Zusätzlich:** `gnome-shell` + `gnome-remote-desktop-daemon` brauchen zusammen 50–130 %. Das ist der Fernzugriff auf den
  Bildschirm. Besser das Panel im Laptop-Browser öffnen (`http://<Roboter-IP>:8080`) und die Bildschirmfreigabe beenden.
- **Status:** offen bis zum nächsten Lauf (`system.log` muss Linienfolger deutlich unter 100 % zeigen).

### Hindernis wieder überfahren (trotz PR #44)
- **Beleg (`ki.log`):** „Hindernis gesehen: 27 cm“ → „fahre in Greifweite“ → 2,5 s später „aus den Augen verloren“ →
  „Weg frei“ → Notbremse 9 cm.
- **Ursache 1:** Die gemerkte Stelle galt ab 22 cm (`kamera_min_sicht`) als „für die Kamera sichtbar“. Die Kamera hat das
  Hindernis aber schon bei ~25 cm verloren. → Jetzt gilt „Kamera sieht nichts = frei“ nur, wenn der Roboter **nicht
  näher** dran ist als bei der letzten echten Sichtung (1 cm Spiel).
- **Ursache 2:** Die KI hat die gefahrene Strecke als Geschwindigkeit × Zeit gerechnet (Zeit auf 0,2 s begrenzt). Bei
  Hängern fehlte Strecke, er glaubte sich weiter weg. → Jetzt aus der Odometrie-Position.
- **Ursache 3:** Greifweite 25 cm lag im toten Winkel der Kamera: Heranfahren konnte nie gelingen. → `greif_vor` 28 cm.
  Danach fährt er wie vorgesehen blind näher, wenn der Arm nicht hinreicht.
- **Status:** nur Test (`test_entscheider.py`: Szenario „mit Radzähler“ schlägt auf dem Stand von PR #44 fehl).

### Rote Ampel: bleibt stehen, bis Grün erkannt wird
- **Ursache:** B1-Regel „Rot verschwindet nicht durch Timeout“ (#13). Sieht er Grün nicht (Ampel außer Sicht), stand er
  für immer, nur ein Neustart der KI half.
- **Lösung:** STOPP, dann START im Panel (bewusste Freigabe) hebt den Rot-Halt auf. Ein Statusausfall ohne START tut das
  nicht. Nach 4 s ohne sichtbare Ampel zeigt das Panel: „Rote Ampel nicht mehr zu sehen -> warte auf Gruen (oder STOPP,
  dann START)“.
- **Status:** nur Test.

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
- **Nachtrag Lauf 12:27–12:39:** wieder 4× „zur Seite (4 / ±18 / 18–20 cm)“, jedes Mal erst NACH dem Heranfahren.
  „Umschauen“ im Arm-Tab hilft dabei nicht: das ist das Umschauen für die Karte, nicht die Ablagesuche.
- **Ursache (vermutet):** Mit den eigenen Standardmaßen wären die alten Punkte erreichbar. Gerechnet hat aber
  Yahbooms Kinematik-Dienst: feste Handneigung 80° und eigenes Koordinatensystem (base_link), in das die
  Ablagepunkte nicht umgerechnet wurden.
- **Lösung:** 80 statt 8 Ablagestellen (Gitter), Ablagepunkte um denselben Versatz verschoben wie der Greifpunkt,
  Yahboom-IK mit 80°/65°/50°, vom LiDAR belegte Stellen fallen weg. Vor dem Heranfahren geprüft (Phase
  `vorpruefen`); ohne Ablagestelle fährt er gar nicht erst los.
- **Status:** nur Test. Am Roboter prüfen: Ereignis „Ablagestelle gefunden: … lege ab bei x / y cm“.

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
