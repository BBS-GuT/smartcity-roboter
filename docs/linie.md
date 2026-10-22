# Linienfolger

Dateien: `line_follower/line_follower.py` (ROS-Programm), `line_follower/linie.py` (Rechnung, ohne ROS testbar).

## Warum er die Kurven nicht mehr schneidet

Der alte Linienfolger hat nach der Lage der Linie **im Bild** gelenkt. Die Kamera schaut schräg nach unten. Dadurch täuscht die Perspektive: Eine Kurve sieht im Bild flacher aus, als sie ist. Und direkt vor bzw. unter dem Roboter sieht die Kamera gar nichts (die ersten ~25 cm). In engen Kurven hat er deshalb geschnitten und die Linie verloren.

Jetzt:

1. **Draufsicht**: Die untere Bildhälfte wird mit dem Kameramodell (Höhe, Neigung, Blickwinkel) in eine Ansicht von oben umgerechnet. Dort ist 1 Pixel = 4 mm, und die Linie liegt so, wie sie wirklich auf dem Boden liegt.
2. **Mittellinie**: Von den dunklen Flächen wird die genommen, die am besten zur bisherigen Linie passt (nicht die größte). Zebrastreifen und Kreuzungen stören dadurch weniger.
3. **Gedächtnis**: Die Linienpunkte (in Metern) werden gemerkt und mit der eigenen Bewegung mitgerechnet. So kennt der Roboter die Linie auch **unter sich** und auch in engen Kurven, wo die Kamera sie nicht sieht.
   - Die Punkte altern nur beim Fahren. Hält er mitten in der Kurve an (Ampel, Fußgänger), weiß er danach noch, wo sie ist.
   - Dreht die KI die Kamera (Arm), werden die Bilder nicht ins Gedächtnis übernommen.
4. **Lenken**: Krümmung der Linie am Roboter vorsteuern (wie stark die Kurve ist), dazu Richtung und seitlichen Abstand nachregeln. In Kurven wird er automatisch langsamer.

Simulation (Rundkurs mit Kurvenradius 25 cm): größte Abweichung **1,9–2,7 cm** bei 2–15 Bildern/s und 0,15–0,25 m/s. Vorher waren es 7,4 cm, und die Linie ging verloren. Mit 4° falscher Kameraneigung sind es ca. 4 cm.

## Verspätete Kamerabilder (wichtig auf dem echten Roboter)

Ist der Rechner ausgelastet, kommen Kamerabilder verspätet an. Früher hat der Linienfolger die Linie dort eingetragen, wo der Roboter beim **Auswerten** stand. Bei 0,3 s Verspätung und 0,15 m/s liegt sie dann 4,5 cm falsch, in Kurven auch noch verdreht. Er hat also nach einem alten Bild gelenkt.

Jetzt:
- **Aufnahmezeit**: Er trägt die Linie dort ein, wo er beim **Fotografieren** stand (Zeitstempel der Kamera).
- **Bild älter als 0,25 s**: halbes Tempo. **Älter als 0,6 s**: STOPP mit Meldung „KAMERABILDER ZU ALT“ (`bild_alter_langsam`, `bild_alter_max`).
- **Eigene Bewegung**: kommt aus Radzählern (`/odom_raw`) und Lagesensor (`/imu/data_raw`), nicht mehr aus den Fahrbefehlen. Vorher prüft er, ob die Messung zur Fahrtrichtung passt (falsches Vorzeichen → Fahrbefehle).
- Das Panel zeigt unter Sensoren das Bildalter und die Quelle der Bewegung.

Simulation mit 0,3 s Verspätung: Der alte Linienfolger war bis 5,1 cm daneben, der neue 1,8–3 cm.

**Linie weg:** Er dreht nur noch ca. 30° zur Seite, wo die Linie zuletzt war (`such_zeit` 0,8 s), dann STOPP. Vorher drehte er 3 s lang, das sieht aus wie im Kreis fahren und kann Aufbauten streifen.

## Schnell fahren ohne Pendeln (Oktober 2026)

**Problem am echten Roboter:** Ab ca. 0,25 m/s schwankt er ständig links/rechts um die Linie (Pendeln) und bricht in Kurven fast aus. In der Simulation sah man das nicht, weil dort jeder Fahrbefehl **sofort** die Geschwindigkeit war und Radzähler/Lagesensor 50× pro Sekunde ohne Verspätung kamen.

### 1. Simulation wie in echt

`sim/antrieb.py` rechnet den Antrieb nach (Simulator **und** Messskript):

| Wert | `echt` | `schwer` | Bedeutung |
|---|---|---|---|
| `totzeit` | 0,05 s | 0,08 s | Befehl kommt erst so spät bei den Motoren an (USB, Board) |
| `traegheit` | 0,15 s | 0,25 s | Motoren brauchen so lange, bis sie das neue Tempo (zu 63 %) haben |
| `max_beschl` / `max_dreh_beschl` | 0,8 m/s² / 5 rad/s² | 0,5 / 3 | schneller kann er nicht beschleunigen |
| `schlupf` | 0,04 s | 0,07 s | Mecanum-Räder rutschen in Kurven nach außen: Rutschtempo = schlupf × Tempo × Drehrate. **Die Radzähler merken davon nichts** |
| `dreh_skala` | 0,95 | 0,90 | er dreht sich weniger als befohlen (Rollen rutschen). Der Lagesensor merkt es |

Dazu im Messskript: Kamera 15 Bilder/s, 0,1 s spät; **Radzähler und Lagesensor nur 10× pro Sekunde und 0,05 s spät** (so arbeitet vermutlich der Yahboom-Treiber). **Alle diese Werte sind geschätzt, nicht am Roboter gemessen.**

Simulator: `-p antrieb:=echt -p odom_hz:=10.0 -p kamera_hz:=15.0` (Standard bleibt `ideal`, 50 Hz, damit die bisherigen Prüfungen gleich bleiben). Prüfung: `SIM_ANTRIEB=echt SIM_TEMPO=0.35 scripts/simulation.sh pruefen`.

**Messen ohne ROS:** `python3 sim/linie_messen.py` fährt mit dem **echten** Linienfolger-Code eine Runde bei 0,15 / 0,25 / 0,35 m/s (je 3 Fahrten mit etwas anderer Startlage) mit simulierter Uhr. Das Ergebnis hängt nicht von der Rechnerauslastung ab. Optionen: `--antrieb ideal echt schwer`, `--mess_verz 0.15`, `--set vorhersage=0.2 selbst_einstellen=false` usw. (Erklärung der Spalten oben im Skript.)

Damit ließ sich das Pendeln nachstellen (alter Linienfolger, Antrieb `echt`, 0,35 m/s): Schwankung auf den Geraden ±3,7 cm mit 0,4 Hz, nach Kurven bis 13 cm daneben.

### 2. Was die Ursachen waren und was geändert ist

1. **Gedächtnis hinkt hinterher (Hauptursache fürs Pendeln).** Radzähler und Lagesensor melden die Bewegung spät (10×/s + Übertragung ≈ 0,1 s). Das Linien-Gedächtnis glaubt also, der Roboter stehe noch da, wo er vor 0,1 s war. Bei 0,35 m/s sind das 3,5 cm Weg, in der Kurve 0,1 s × 1 rad/s = 6° Drehung. Er lenkt deshalb zu spät zurück und schießt über die Linie hinaus → Pendeln, je schneller, desto schlimmer.
   **Neu: `vorhersage`.** Er rechnet seine Lage um diese Zeit mit den letzten Fahrbefehlen voraus und schaut die Linie dort an, wo er **jetzt** ist.
2. **Die Verspätung misst er selbst (`selbst_einstellen`).** Während der Fahrt merkt er sich 15 s lang Lenkbefehle und die vom Lagesensor gemessene Drehung. Dann probiert er aus, mit welcher Totzeit und Trägheit ein einfaches Motor-Modell die Messung am besten nachmacht (in den Kurven, wenn genug gelenkt wird). Ergebnis:
   - `vorhersage` = gemessene Totzeit − `motor_totzeit` (0,1 s, geschätzt: die Verzögerung in den Motoren zählt nicht, die sieht das Gedächtnis ja richtig). Bis zur ersten Messung gilt der Startwert `vorhersage` (0,1 s).
   - **Drehfaktor**: Dreht er z. B. nur 95 % von dem, was befohlen ist, befiehlt er 1/0,95 mal so viel (begrenzt auf 0,8–1,2).
   - Zu sehen in `/line_follower/status`: `verzoegerung` (totzeit, traegheit, faktor, guete) und `vorhersage` (benutzter Wert).
3. **Lagesensor wird früher benutzt.** Vorher galt er erst nach 1 s Drehen mit > 0,2 rad/s als plausibel – in der ersten Kurve rechnete das Gedächtnis also mit den Fahrbefehlen (dreht zu viel, zu früh). Jetzt: 0,5 s mit > 0,1 rad/s.
4. **Vor der Kurve bremsen (`quer_beschl`).** Er schaut auf die Linie 45 cm voraus (Gedächtnis) und fährt höchstens so schnell, dass Tempo² × Krümmung ≤ 0,15 m/s² bleibt (25-cm-Kurve: 0,19 m/s). Er bremst damit **schon auf der Geraden** und nicht erst in der Kurve, und die Räder rutschen weniger. Bei 0,15 m/s ändert sich nichts (die Kurvenbremse ist dort schon langsamer).
5. **Zebrastreifen direkt nach der Kurve.** In der engen Kurve sieht die Kamera die Linie nicht. Danach lag die Erwartung etwas daneben, und ein Balken vom Zebrastreifen wurde für die Linie gehalten (bis 8 cm daneben). Jetzt gelten kleine Stücke (weniger als halb so groß wie das größte) als 5 cm weiter weg → die lange Linie gewinnt.
6. **Lücke nach der Kurve.** Sieht die Kamera die Linie erst wieder weiter vorne, überbrückt die Linien-Rechnung am Roboter die Lücke (vorher: keine Linie am Roboter → grobe Notlösung).

7. **Anhalten und Umschauen (Zebrastreifen).** Zwei Dinge können das Gedächtnis im Stand verfälschen:
   - Bilder, die mit noch gedrehter Kamera aufgenommen wurden, aber erst nach dem Zurückdrehen ankommen. Jetzt werden Bilder, die bis 0,5 s nach dem letzten „Kamera schaut weg“ der KI aufgenommen wurden, nicht ins Gedächtnis übernommen.
   - Der Nullpunktfehler des Lagesensors: Im Stand hat sich das Gedächtnis langsam verdreht (z. B. 11 s × 0,003 rad/s = 2°). Jetzt lernt er den Nullpunkt im Stand (keine Fahrbefehle) und zieht ihn ab.
   - Messung (`linie_messen.py` mit Halt bei s = 2,13 m für 11 s, Kamera schaut ±45°, Antrieb `echt`, 0,15 m/s): vorher bis 8,3 cm daneben, jetzt 3,4 cm.

**Ausprobiert und wieder verworfen (Messung zeigte keinen Vorteil):** schwächeres Nachregeln bei hohem Tempo (Verstärkung ~ 1/Tempo) und Vorausrechnen um die Motor-Trägheit (`vorhersage` 0,2 s, obwohl die Sensoren pünktlich sind: dann bis 12 cm daneben). Eine Seitwärtskomponente (Mecanum) wird beim Linienfolgen weiterhin **nicht** benutzt.

### 3. Messung (nur Simulation, `sim/linie_messen.py`, eine Runde, schlimmste von 3 Fahrten)

Kamera 15 Bilder/s + 0,1 s; Radzähler/Lagesensor 10/s + 0,05 s. „Gerade“ = ab 30 cm nach der Kurve, „Kurve“ = Kurve + 30 cm danach. Pendeln = Schwankung auf den Geraden.

| Tempo | Antrieb | max vorher → nachher | Mittel | Gerade | Kurve | Pendeln | Lenkunruhe (rad/s) |
|---|---|---|---|---|---|---|---|
| 0,15 | ideal | 2,2 → 2,0 cm | 0,64 → 0,67 | 1,3 → 1,3 | 2,2 → 2,0 | 0,39 → 0,42 | 0,05 → 0,05 |
| 0,25 | ideal | 2,8 → 2,3 | 0,66 → 0,68 | 2,8 → 1,6 | 2,8 → 2,3 | 0,59 → 0,48 | 0,15 → 0,08 |
| 0,35 | ideal | 4,1 → 2,2 | 0,64 → 0,65 | 4,1 → 1,6 | 4,1 → 2,2 | 0,69 → 0,48 | 0,42 → 0,11 |
| 0,15 | echt | 8,2 → 3,6 | 1,12 → 0,68 | 8,0 → 1,5 | 8,2 → 3,6 | 1,17 → 0,42 | 0,12 → 0,07 |
| 0,25 | echt | 9,1 → 3,1 | 1,28 → 0,59 | 9,1 → 1,4 | 9,1 → 3,1 | 1,77 → 0,45 | 0,50 → 0,12 |
| 0,35 | echt | 13,0 → 3,7 | 3,14 → 0,57 | 12,7 → 1,4 | 13,0 → 3,7 | 3,74 → 0,41 | 0,98 → 0,17 |
| 0,15 | schwer | 8,5 → 3,9 | 1,15 → 0,67 | 8,4 → 1,3 | 8,5 → 3,9 | 1,17 → 0,32 | 0,14 → 0,07 |
| 0,25 | schwer | 9,0 → 4,3 | 1,97 → 0,74 | 9,0 → 1,1 | 8,8 → 4,3 | 2,32 → 0,32 | 0,73 → 0,12 |
| 0,35 | schwer | 11,7 → 10,8 | 3,37 → 1,04 | 11,7 → 10,8 | 11,6 → 9,9 | 3,97 → 0,87 | 0,96 → 0,23 |

Weitere Fälle (Antrieb `echt`, schlimmste von 3 Fahrten, vorher → nachher):

| Fall | 0,15 m/s max / Mittel | 0,35 m/s max / Mittel |
|---|---|---|
| wie die alte Simulation (ideal, Sensoren 50/s pünktlich) | 2,4 / 0,60 → 2,1 / 0,66 | 2,8 / 0,67 → 2,3 / 0,56 |
| Sensoren 0,15 s spät (stark ausgelastet) | 8,4 / 0,91 → 2,9 / 0,63 | 15 (2× Linie verloren) / 4,1 → 2,7 / 0,62 |
| Kamera sitzt wirklich 31 cm hoch, eingestellt 22 cm | 4,8 / 1,01 → 3,3 / 0,96 | 7,6 / 1,96 → 3,8 / 0,86 |
| Kamera wirklich 36° geneigt, eingestellt 32° | 6,9 / 1,14 → 5,4 / 0,98 | 14,7 / 2,98 → 6,1 / 1,01 |

Komplette ROS-Simulation nach dem Zusammenführen mit Arm und Karte (`main`): Die Linie war in 4 Läufen immer OK (größte Abweichung 2,9 / 1,1 / 0,8 / 2,4 cm). Ein Lauf war komplett grün. In den anderen blieb der Roboter am Zebrastreifen stehen („etwas am Zebrastreifen, 22–35 cm rechts“), obwohl der Fußgänger weg war. Grund: Die KI merkt sich die Linie voraus (`weg`) nur einmal beim Anhalten. Hält er direkt nach der engen Kurve, ist diese Linie im Gedächtnis noch bis ca. 10° verdreht (die Kamera sah sie in der Kurve nicht). Wenige Bilder später ist sie richtig, aber die KI prüft weiter den alten, falschen Bereich. Vorschlag für die KI (`ki/ablaeufe.py`): `weg` bei jedem Schritt neu nehmen.

Komplette ROS-Simulation vor dem Zusammenführen (`sim/pruefen.py`, mit KI, Kartograf, Arm):
- Standard (Antrieb `ideal`, 0,15 m/s): alle Prüfungen grün, größte Abweichung 2,6 cm, Mittel 0,6 cm (ein erster Lauf bei stark ausgelastetem Rechner hat das Schild „Einfahrt verboten“ übersehen; Linie trotzdem 2,9 cm / 0,6 cm).
- `SIM_ANTRIEB=echt SIM_TEMPO=0.35`: Linie OK (größte Abweichung 3,2 cm, Mittel 0,7 cm, nie verloren). **Aber:** Bei 0,35 m/s fährt er auf den Holzwürfel auf, und Stoppschild/Einbahnstraße klappen nicht mehr. Das liegt an der KI (erkennt/stoppt zu spät für dieses Tempo), nicht an der Linie. Für die Aufgaben mit Hindernis und Schildern also weiter langsam fahren.

Was das heißt:
- Bei 0,35 m/s pendelt er in der Simulation nicht mehr (Geraden ≤ 1,6 cm, Schwankung ±0,4 cm statt ±3,7 cm).
- Die größten Abweichungen sind jetzt **am Ende der engen Kurven** (3–4 cm): Dort sieht die Kamera die Linie nicht, und Rutschen/Radzähler-Fehler sammeln sich im Gedächtnis. Mit dem Antrieb `schwer` (viel Rutschen) war es in 1 von 3 Fahrten bei 0,35 m/s nach der ersten Kurve trotzdem 10,8 cm. Das ist noch offen.
- Bei 0,15 m/s ist er mindestens so gut wie vorher.
- **Alles nur in der Simulation geprüft.** Wie spät Motoren und Sensoren am echten Roboter wirklich sind, ist nicht gemessen. Die Selbstmessung (`verzoegerung` im Status) zeigt es.

### 4. Am Roboter ausprobieren

1. Mit 0,15 m/s ein paar Runden fahren, dann in `/line_follower/status` schauen: `verzoegerung` sollte nach den ersten Kurven einen Wert haben (z. B. `totzeit` 0,15–0,3 s, `faktor` 0,85–1,0, `guete` > 0,7). `ros2 topic echo /line_follower/status`.
2. Tempo langsam erhöhen (Panel-Regler). Pendelt er noch: `vorhersage` von Hand größer setzen (`ros2 param set /line_follower selbst_einstellen false`, dann `vorhersage 0.15` / `0.2`). Zu groß ist weniger schlimm als zu klein. Wird es schlechter: kleiner.
3. Bricht er in Kurven aus: `quer_beschl` kleiner (0,1).
4. **Kamera-Höhe prüfen:** `linie_breite` im Status = wie breit die Linie in der Draufsicht aussieht. In der Simulation (Linie 2,5 cm, Kamera richtig eingestellt) sind es ca. 3,2 cm. Ist die Kamera in Wirklichkeit höher als eingestellt, wird die Linie schmaler (31 statt 22 cm: ca. 2,4 cm). Nur ein grober Hinweis – besser nachmessen.

| Name | Standard | Bedeutung |
|---|---|---|
| `vorhersage` | 0.1 | so viele s rechnet er seine Lage voraus (Startwert, mit `selbst_einstellen` gemessen). 0 = aus |
| `selbst_einstellen` | true | Verzögerung und Drehfaktor während der Fahrt selbst messen und benutzen |
| `motor_totzeit` | 0.1 | so viel von der gemessenen Verzögerung steckt in USB + Motorboard (geschätzt), wird abgezogen |
| `quer_beschl` | 0.15 | höchstens so viel Fliehkraft (m/s²); bremst schon vor der Kurve. 0 = aus |

## Kamera nachmessen (wichtig!)

Eine falsch eingestellte Kamera verzerrt die Draufsicht. In der Simulation (Tabelle oben): 31 cm statt 22 cm Höhe → bis 3,8 cm daneben, 4° mehr Neigung → bis 6 cm. Ein öffentliches Modell des M3 Pro (URDF) spricht für ca. 31 cm Höhe in Fahrstellung – unbedingt nachmessen.

Die Werte sind **geschätzt**. Messen, wenn der Arm in der **Fahrstellung** steht:

| Name | Standard | Bedeutung |
|---|---|---|
| `kamera_hoehe` | 0.22 | Höhe der Kameralinse über dem Boden (m) |
| `kamera_neigung` | 32.0 | wie weit die Kamera nach unten schaut (Grad, 0 = waagrecht). **Am wichtigsten** |
| `kamera_fov` | 70.0 | waagrechter Blickwinkel (Grad, Datenblatt der Kamera) |
| `kamera_x` | 0.12 | wie weit die Kamera vor der Robotermitte sitzt (m) |

Eintragen in `config/lokal/roboter.yaml` (Datei anlegen, gilt für Linienfolger, KI und Kartograf):

```yaml
/**:
  ros__parameters:
    kamera_hoehe: 0.21
    kamera_neigung: 35.0
```

**Neigung prüfen:** Panel → TEST, Roboter gerade auf eine gerade Linie stellen. In der Draufsicht (kleines Bild rechts oben) muss die Linie **senkrecht** und **gleich breit** erscheinen. Wird sie nach oben breiter, ist die Neigung zu klein. Wird sie schmaler, ist sie zu groß. Im laufenden Betrieb ändern: `ros2 param set /line_follower kamera_neigung 35.0` (`ros2 param set` = Einstellung eines laufenden Programms ändern).

## Weitere Einstellungen

In `config/lokal/roboter.yaml` unter `line_follower:` → `ros__parameters:` eintragen (gilt ab dem nächsten START) oder im laufenden Betrieb `ros2 param set /line_follower name wert`.

| Name | Standard | Bedeutung |
|---|---|---|
| `speed` | 0.15 | m/s auf gerader Strecke (Panel-Regler) |
| `threshold` | 70 | dunkler als das = Linie (0 schwarz – 255 weiß) |
| `zeilen_oben` | 0.5 | Linie nur in der unteren Bildhälfte suchen |
| `linie_max_breite` | 0.06 | dunkle Fläche breiter als 6 cm = keine Linie |
| `kurven_bremse` | 0.15 | wie stark er in Kurven langsamer wird |
| `regel_abstand` / `regel_richtung` | 44 / 13 | wie kräftig er zur Linie zurücklenkt. Schlingert er, beide etwas kleiner |
| `max_turn` | 1.5 | höchste Drehgeschwindigkeit (rad/s) |
| `such_zeit` / `such_dreh` | 0.8 / 0.7 | Linie weg: so lange (s) mit dieser Drehgeschwindigkeit (rad/s) zur letzten Seite drehen (ca. 30°), danach Stopp |
| `notbremse_dist` | 0.12 | eigene LiDAR-Notbremse (m), unabhängig von der KI |
| `obstacle_check` | true | Notbremse an/aus (RM03 hat kein LiDAR → `false`) |
| `ki_pflicht` | true | ohne KI-Zentrale nicht fahren |
| `abbiegen` | true | an Kreuzungen zufällig einen Ast wählen (siehe unten). `false` = wie bisher |
| `ast_min` | 0.05 | ein Ast muss mindestens so lang zu sehen sein (m), sonst zählt er nicht als Ausfahrt. Kurz, weil die Kamera nur ca. 20 cm Boden sieht |

## Kreuzungsgeometrie und Auswahl

Ziel (Zieldefinition 4.2): An Verzweigungen wählt er selbst einen erlaubten Ausgang, damit nicht immer dieselbe Runde gefahren wird. `LinienSucher.aeste` liefert ausschließlich sichtbare geometrische Äste. Das bestätigt weder Knoten/Zufahrt noch verkehrsrechtlich erlaubte Ausfahrten (GB-05/09). Die bisherige Zufallswahl allein erfüllt diese Anforderungen nicht; unbekannte Erlaubnis darf keine Einfahrt begründen.

So geht es (`line_follower/linie.py`, `LinienSucher.aeste`):

1. Von der eigenen Linie aus misst er die Strecke **entlang** der dunklen Fläche (nicht Luftlinie, in 16-mm-Schritten).
2. Teilt sich die Fläche in mindestens zwei Äste, die jeweils mindestens `ast_min` lang zu sehen sind **und aus dem Kamerabild hinauslaufen**, ist das eine Kreuzung. Ein enger Bogen (U) teilt sich so nie. Äste, die zum Roboter zurückzeigen, zählen nicht (von dort kommt er). Ein Querbalken, der im Bild endet (Haltelinie, Markierung), ist keine Ausfahrt. Grenze: Reicht ein Querbalken bis an den seitlichen Bildrand (z. B. Haltelinie ab ca. 20 cm je Seite), hält er ihn für eine Ausfahrt; mit Unschärfe im Kamerabild teils schon ab ca. 18 cm (auch vor RM02 22.10. so). Der Bildrand ist nur am fernen Ende 2 Pixel breit. Maße der realen Haltelinien sind noch offen (E1); nach dem Ausmessen am Brett prüfen. Sieht er im selben Bild einen Zebrastreifen, wählt er nicht (dessen Begrenzungen sind keine Abzweigung, Zieldefinition 4.3).
3. Beim ersten Sehen wählt er **zufällig** einen Ast. Die Wahl merkt er sich als Richtung im Raum (mit der eigenen Drehung aus dem Linien-Gedächtnis). So bleibt es derselbe Ast, auch wenn er sich beim Abbiegen im Bild dreht.
4. Nur Stamm + gewählter Ast kommen ins Linien-Gedächtnis, der Linienfolger fährt also dorthin.
5. Nach mehr als 15 gültigen Bildern ohne Kreuzung und mindestens 20 cm Abstand zur letzten Sichtung wird neu gewählt, sofern die gemessene Richtung zum gewählten Ast passt (45° Toleranz wie bei der Astzuordnung). Im Stand bleibt die Wahl erhalten. Ohne Positionsangabe entfällt die Streckenprüfung; fehlende/ungültige Richtung bestätigt kein Einlenken.

Im Log steht z. B. `Kreuzung: Aeste [-90, 90] Grad -> zufaellig gewaehlt: links (+90 Grad)`. Rechenzeit: ca. 1 ms je Kamerabild.

**Grenzen (ungetestet am Roboter):**
- Die Kamera sieht nur ca. 25–47 cm vor dem Roboter. Die Kreuzung wird erst in diesem Bereich erkannt.
- Er weiß nicht, welche Ausfahrt erlaubt ist. Fährt er in eine Einbahnstraße und sieht das Schild „Einfahrt verboten“, wendet er wie bisher.
- Querbalken, die die Leitlinie berühren und **über den Bildrand hinaus** reichen (und kein Zebrastreifen sind), sähen weiterhin aus wie eine Kreuzung.
- Erlaubte Ausfahrten (Einbahnstraßen) kennt er noch nicht, siehe oben.
- Ob er eine 90°-Abzweigung sauber fährt, ist nur mit gezeichneten Bildern geprüft (`tests/test_kreuzung.py`).

### Softwarebeleg zu #112 und offene Informationsgrenze

`python tests/test_kreuzung.py` prüft zusätzlich Pluskreuzungen und seitliche T-Einmündungen samt Spiegelung mit den Standardkamerawerten sowie einer synthetischen Kamera auf 31 cm Höhe und mit 28° Neigung. Plus muss drei Ausgänge liefern, seitliches T genau Geradeaus und den jeweiligen Seitenast. Jeder Ausgang wird deterministisch ausgewählt; die zurückgegebenen Bodenpunkte müssen auf dem gewählten Ast bleiben. Das sind angenommene Bildgeometrien, keine gemessene Kalibrierung oder Geräteabnahme. Die Fälle bestehen bereits auf Basis `dc6acc25e490edc301a6464af8fe19e17339aa42`.

Der Test `test_querbalken_am_bildrand_ist_bildgleich_mit_plus` zeichnet eine durchgehende Leitlinie mit einer 80 cm langen Querlinie und vergleicht sie mit einer Pluskreuzung mit 100 cm Querlinie (jeweils 2,5 cm Strichbreite, bei 36 cm Abstand). Beide Querlinien reichen über beide seitlichen Kamerabildränder; die erzeugten Kamerabilder sind **bytegleich**. Die bestehende Erkennung meldet in beiden Fällen drei geometrische Äste. Dieser Test sichert die Informationsgrenze und behauptet ausdrücklich keine erfolgreiche Haltelinienunterdrückung.

Eine Regel, die dieses Querbalkenbild allein anhand der Pixel verwirft, müsste auch das identische Plusbild verwerfen. Ein längerer sichtbarer Balken ist deshalb kein allgemeines Unterscheidungsmerkmal. #112 bleibt für die geforderte allgemeine Querbalkenkorrektur offen. Benötigt werden unterscheidbare, bestätigte Markierungsmerkmale oder ein bestätigter Knoten-/Zufahrts- und Markierungsbezug; deren Gültigkeit und Ausfallverhalten müssen vor einer Freigabe geklärt sein. Reale Bilder, Maße, Licht, Kamerafahrstellung und die Bedeutung der Markierung sind am Aufbau zu sichern. Geometrische Äste allein dürfen keine Verkehrserlaubnis erzeugen.

Die bestehenden Negativkontrollen (Gerade, enger U-Bogen, im Bild endende Haltelinie, Zebrastreifenbegrenzung) bleiben erhalten. Die Simulatorrunde enthält keine Kreuzungen und ersetzt diese Kontrollen nicht. #111 bleibt die offene Geräteprüfung auf **RM02**; ein späterer RM01-Test ist kein Ersatz.

### Gewählter Ast im nahen Kamerablindbereich (#106)

Eine synthetische Annäherungsfolge mit Seitenast bei 36 cm reproduziert einen eigenen Fehler: Nach 12 cm Vorfahrt liegt der Abzweig bei 24 cm und verschwindet unter dem Kamerabild. Die ungewählte Gerade bleibt sichtbar und wurde zuvor als neue Linie bis 58,2 cm im ursprünglichen Koordinatensystem ins Gedächtnis übernommen. Dadurch kann der Seitenast trotz gespeicherter Wahl verdrängt werden. Die Kontrolle verwendet den echten `Gedaechtnis.hinzufuegen`-Pfad und beide Spiegelungen; auf dem Ausgangscode schlägt sie fehl.

Solange die gemessene Richtung noch nicht zur Wahl passt, werden nun allein sichtbare Linien mit widersprechender Hauptachse verworfen. Das ergibt keine neuen Bodenpunkte; das vorhandene Gedächtnis und dessen Alterung bleiben wirksam. Eine passende Querlinie bleibt beobachtbar; nach tatsächlichem Einlenken funktioniert die normale gerade Linie wieder. Weder viele Bilder noch bloßer Wegfortschritt dürfen eine noch nicht eingeschlagene Seitenwahl löschen. Unbekannte Richtung bestätigt kein Einlenken. Die Änderung erteilt keine Fahrfreigabe, verlängert keine Speicherfrist und ersetzt keine geprüfte Ausfahrtserkennung oder reale 90°-Fahrt. Keine Reglerparameter wurden geändert und PR #168 wurde nicht übernommen.

## Was er an die KI meldet

`/line_follower/status` (JSON): unter anderem `linie_quer`/`linie_kurs` (Lage der Linie am Roboter) und `weg`. `weg` ist die Linie vor dem Roboter als Punktliste. Daraus macht die KI den **Fahrschlauch**: Nur was entlang der Linie liegt, gilt als Hindernis. Häuser neben einer Kurve stören deshalb nicht mehr.
