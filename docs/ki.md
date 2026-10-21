# KI-Zentrale

## Aufbau

```
 Kamera ──► Kamera-KI (YOLO) ──┐
            + Ampelfarbe        │
            + Ersatz: LED, Form │
            + Zebrastreifen     │
            + Einfahrt verboten │
 LiDAR (Fahrschlauch) ─────────►├──► Entscheider ──► /ki/befehl ──► Linienfolger ──► Motoren
 Tiefenkamera (Bodenmodell) ───┘    (ki/entscheider.py)                (lenkt nach Linie, führt Manöver aus,
                                     + Abläufe (ki/ablaeufe.py)          eigene Notbremse)
                                         │
                                         └──► Arm (nur wenn freigegeben, nur im Stand, nur während der Fahrt)
```

- **ki/zentrale.py**: ROS-Programm. Wertet die Sinne aus und schickt 10× pro Sekunde einen Befehl mit Grund.
- **ki/entscheider.py**: Entscheidungslogik, ohne ROS testbar (`python3 tests/test_entscheider.py`).
- **ki/ablaeufe.py**: Abläufe aus mehreren Schritten: Zebrastreifen, Wenden, Wegräumen, Umschauen.
- **line_follower/line_follower.py**: lenkt nach der schwarzen Linie, fährt nur, wenn die KI es erlaubt, und führt deren Manöver aus. Manöver sind z. B. wenden oder zum Greifen ausrichten. Sie sind begrenzt: max. 0,10 m/s vor, 0,08 m/s seitwärts, 1,2 rad/s drehen.

## Wie entscheidet die KI? (wichtigstes zuerst)

| # | Situation | Entscheidung |
|---|---|---|
| 1 | LiDAR: etwas näher als **12 cm** | **STOPP sofort, ohne KI-Prüfung** (Eigenschutz) |
| 2 | kein LiDAR oder keine Kamerabilder | STOPP (wer nichts sieht, fährt nicht) |
| – | ein Ablauf läuft (Zebrastreifen, Wenden, Wegräumen, Umschauen) | der Ablauf bestimmt, 1 und 2 gelten trotzdem |
| 3 | LiDAR (**im Fahrschlauch**, näher als **45 cm**) und/oder Tiefenkamera (etwas ragt aus der Fahrbahn, näher als 35 cm) | **STOPP, Kamera schaut genau hin**, dann wegräumen oder warten (siehe unten) |
| 4 | Kamera-KI sieht Person/Auto/… im Weg | STOPP |
| 6 | Schild **"Einfahrt verboten"** (2 Bilder hintereinander) | **wenden**: auf der Stelle drehen, bis die Linie wieder genau vorne liegt (gemessen mit dem Lagesensor, mind. 150°) |
| 7 | **Zebrastreifen** näher als 33 cm | anhalten, Kamera nach **links**, dann nach **rechts** drehen (Arm), zurück. Sieht er eine **Spielfigur** in der Nähe (bis `zebra_figur_abstand` = 1 m ab Kamera; echte Menschen im Raum zählen nicht, siehe „Die Sinne“) oder steht etwas am Zebrastreifen (LiDAR, ±30 cm seitlich): warten und neu schauen. Sonst weiter. Ohne Arm-Freigabe: anhalten und geradeaus schauen |
| 8 | Ampel rot oder gelb | STOPP, bis **grün** erkannt wird. Ampel nicht mehr zu sehen ist KEINE Freigabe (Zieldefinition: Rot verschwindet nicht durch Timeout) |
| 9 | Stoppschild (nah, d. h. groß im Bild) | 3 s halten, dann weiter. Dasselbe Schild löst erst wieder aus, wenn es 2 s weg war |


**Wenden** (Einbahnstraße) bricht ab und der Roboter bleibt stehen, wenn der Lagesensor nach 2,5 s keine Drehung meldet (IMU fehlt, falsch eingebaut, Räder blockiert) oder nach 7 s nicht fertig ist. Weiter geht es erst nach STOPP und neuem START. So dreht er nicht endlos im Kreis.

**Versperrter Weg:** Er hält an und wartet (Zieldefinition GB-04, Gegenverkehr regelt die Infrastruktur). Automatisches Ausweichen (zurück + wenden nach zufälliger Wartezeit) gibt es weiterhin, ist aber **aus** (`ausweichen: true` schaltet es ein).

**Werte ändern:** Alle Zahlen aus `ki/entscheider.py` (`STANDARD`) sind Einstellungen der KI-Zentrale. Man trägt sie in `config/lokal/roboter.yaml` unter `ki_zentrale:` → `ros__parameters:` ein, z. B. `zebra_halt: 0.30`, und startet die KI neu.

**Fahrschlauch:** Der Linienfolger meldet, wo die Linie vor dem Roboter verläuft. Die KI prüft nur den Streifen von **30 cm Breite** (`fahrschlauch_breite`, Roboterbreite + Rand, **nachmessen**) entlang dieser Linie. Dasselbe gilt für die Tiefenkamera. Früher war es ein gerader Kegel nach vorne. Dann hielt er in jeder Kurve vor Häusern am Rand, und in einer Kurve hielt die Tiefenkamera einen Fußgänger am Straßenrand für ein Hindernis.

**Warum hat die Notbremse unter 12 cm das letzte Wort und nicht die KI?** Die KI kennt nur 80 Dinge. Einen Schuh, ein Kabel oder einen Karton kennt sie nicht. Darum: ganz nah = sofort stopp.

## Hindernis wegräumen (ki/ablaeufe.py, `Wegraeumen`)

1. **Anhalten, anschauen:** mindestens 1 s **und** mindestens 5 neue KI-Bilder (höchstens 8 s). Ist die KI langsam, wartet er also länger, statt nach einem halben Blick zu entscheiden. Er misst mit der Tiefenkamera: wo, wie breit, wie hoch.
2. **Urteil:**
   - Kamera und LiDAR sehen nichts mehr → weiter (Fehlalarm).
   - Nur der LiDAR sieht etwas → LANGSAM, ab 20 cm STOPP. Ist es näher als 22 cm (zu nah für die Kamera), fährt er bis zu 10 cm zurück und schaut nochmal.
   - **„Nichts gesehen“ gilt nur, wenn er wirklich genug gesehen hat:** Kamen zu wenige KI-Bilder (KI überlastet) oder sah die Kamera es nur in einzelnen Bildern, schaut er nochmal hin. Hat die Kamera es vorhin gesehen und jetzt nicht mehr (meist: er ist nach dem Halt noch etwas gerollt und es liegt jetzt unter dem Blickfeld der Kamera), fährt er erst zurück, bis er wieder hinsehen kann. In der Simulation ist er vorher genau so über den Würfel gefahren.
   - Ein **Zebrastreifen**, den die Kamera während des Anschauens sieht, wird vorgemerkt und danach beachtet, auch wenn er dann zu nah für die Kamera ist. In der Simulation ist er vorher einmal über den Zebrastreifen gefahren, obwohl der Fußgänger noch da war.
   - Lebewesen, Fahrzeug, zu groß, am Rand, kurz nach einem Zebrastreifen, Arm ausgeschaltet, nur TEST → **warten**, bis der Weg frei ist. **Der Grund steht immer im Ereignis**, z. B. „raeume nicht weg: Arm fuer die KI ausgeschaltet (Panel -> Arm …)“.
3. **Ablagestelle suchen (noch im Stand):** Bevor er losfährt, rechnet er die ganze Armbewegung schon einmal so, als stünde er in Greifweite. Ablagestellen: ein Gitter neben dem Fahrschlauch (17–25 cm seitlich, 2–26 cm vorne, beide Seiten, bevorzugt die Seite, auf der der LiDAR weniger sieht). Stellen, an denen der LiDAR schon etwas sieht, fallen weg. Ist keine erreichbar und frei → gar nicht erst heranfahren, warten (Ereignis „vor dem Heranfahren geprueft“). Mit Yahbooms Kinematik probiert er für jeden Punkt die Handneigungen 80°, 65° und 50°.
4. **In Greifweite fahren:** geregelt nach dem, was die Kamera misst (nicht nach der Zeit), bis die Vorderkante 33 cm (`greif_vor`) vor der Robotermitte liegt. Näher sieht die Kamera kleine Gegenstände nicht mehr sicher (RM02 21.10.: ab 31 cm in fast jedem Bild, bei 29 cm nur noch in jedem zweiten). Steht er schräg zur Straße (Kurve), dreht er sich **erst auf der Stelle gerade** und fährt danach heran. Rückwärts nur, wenn der LiDAR hinten frei meldet.
   - Wartet er wegen einer Person, zählt die Wartezeit nicht als „aus den Augen verloren“.
   - Verliert die Kamera es trotzdem kurz vor der Greifweite und blind greifen geht nicht (z. B. Straßenwinkel unbekannt): etwas zurück (bis 10 cm), nochmal hinschauen, neu anfahren. Höchstens zweimal, dann warten. Findet er es nach dem Zurückfahren nicht wieder, gilt der Weg **nicht** als frei.
5. **Planen:** Die KI rechnet die Servowinkel für jeden Schritt aus (inverse Kinematik = aus dem Zielpunkt die Servowinkel rückwärts ausrechnen). Mit Yahbooms Kinematik-Dienst, wenn er läuft, sonst mit der eigenen Rechnung (Maße aus Yahbooms URDF oder Standard). Dazu kommt die **gelernte Korrektur** (siehe unten). Reicht der Arm nicht hin, fährt er blind bis zu 15 cm näher heran (3 cm/s) und plant neu. Erreicht er es trotzdem nicht, wird nichts bewegt und er wartet.
   - **Zu nah für die Kamera?** Dann neigt er die Kamera nach unten (Pose `pruefblick`, ohne eigene Pose: Fahrstellung mit Servo 4 um 20° weiter nach unten) und misst es dort, statt zurückzufahren. Das Kameramodell für diese Pose wird aus den Kameramaßen der Fahrstellung und der Armgeometrie umgerechnet (`armlib.kamera_fuer_pose`). Die Kontrolle danach macht er ebenfalls im Prüfblick. Sieht er im Prüfblick nichts: Kamera zurück und wie bisher etwas zurückfahren (einmal je Wegräumen). Das Ereignis nennt dann, wie viel des Tiefenbilds gültig war und den nächsten Messwert (RM02 21.10.: Prüfblick sah nie etwas; so sieht man, ob die Tiefenkamera so nah überhaupt misst).
6. **Ausführen:** Greifer auf → über das Hindernis → runter → Greifer schnell anlegen → langsam zudrücken (Wert nach gemessener Breite, eingemessen im Panel, siehe [greifarm.md](greifarm.md#greifkraft-wie-fest-drückt-der-greifer-zu)) → anheben → zur Ablagestelle (siehe 3.) → absetzen → loslassen → Fahrstellung. Höchstens 60° pro Sekunde je Servo. Ist er näher herangefahren, fährt er danach wieder so weit zurück.
7. **Prüfen:** Kamera wieder nach vorne, mindestens 1,5 s und 5 Bilder. Sieht sie im Weg noch etwas → Fehlversuch (wird gelernt), nächster Versuch (ab 1.). Nach 4 Versuchen aufgeben und warten.
   - **Nur nahe Personen, Tiere und Fahrzeuge zählen** (Entscheidung Projektinhaber 21.10.): Die Zentrale misst mit der Tiefenkamera, wie weit das von der Kamera-KI gefundene Ding weg ist (nahe Werte im Kasten, `lib/tiefe.py` `abstand_im_kasten`). Weiter als `akteur_nah` (Standard 1 m ab Kamera) zählt beim Wegräumen nicht – Zuschauer im Hintergrund halten ihn nicht auf. Ist die Tiefe im Kasten unsicher (weniger als 70 % messbar, z. B. näher, als die Tiefenkamera messen kann) oder gehört das Tiefenbild zeitlich nicht zum Farbbild (mehr als 0,15 s auseinander), zählt es als nah.
   - Taucht während des Wegräumens eine nahe Person, ein Tier oder ein Fahrzeug auf (in jeder Phase, in der sich Arm oder Roboter bewegen oder gleich bewegen würden: Ablagestelle suchen, heranfahren, Prüfblick, planen, greifen, zurückfahren, Kontrolle), halten Arm und Roboter **still** (der Greifer bleibt, wie er ist). Erst wenn 2 s niemand mehr zu sehen ist, macht er weiter. Nach 30 s gibt er auf. Auch die Rückkehr des Arms in die Fahrstellung danach wartet, bis 2 s niemand mehr zu sehen war.
   - Wird das Wegräumen abgebrochen (STOPP, Statusausfall, Arm ausgeschaltet, Notbremse zu lange), merkt er sich, wo die Kamera das Hindernis zuletzt gesehen hat. Fehlende neue Treffer gelten nicht als „frei“.
   - Wird „KI darf den Arm bewegen“ während des Greifens ausgeschaltet, bricht er ab und fährt den Arm zurück in die Fahrstellung, bevor er weiterfährt.
   - Das blinde Heranfahren und Zurückfahren misst die Strecke mit den Radzählern, nicht mit der Zeit. Verliert die Kamera es beim Heranfahren kurz, rechnet er ebenfalls mit den Radzählern weiter (nicht über die Greifweite hinaus). Sonst „Weg ist frei (geprüft)“ → Erfolg, weiter.
8. **Lernen:** Das Ergebnis aus 7. ist die Belohnung für das Greif-Lernen (`lib/greifen.py`). Ereignis z. B. „Greifversuch 7: Erfolg, Erfolgsquote 86 % (letzte 7)“. Wie das Lernen funktioniert, wie man im Simulator vortrainiert und was es gebracht hat: [greifarm.md](greifarm.md#greifen-lernen-libgreifenpy).

**Sicherheit:** Die KI darf den Arm standardmäßig bewegen (`ki_darf_arm_bewegen: true`), aber nur, wenn das Fahrprogramm **fährt** (START) und der Roboter steht. Im TEST und nach STOPP bewegt sie den Arm nie, ein laufender Ablauf wird abgebrochen, beim nächsten START fährt der Arm zuerst in die Fahrstellung. Taucht während des Greifens eine Person, ein Tier oder ein Fahrzeug auf → Abbruch, Arm zurück. Notbremse → Pause, nach 5 s Abbruch. Ausschalten: Panel → Arm (gilt nach ca. 2 s, ohne Neustart).

## Die Sinne

- **Kamera-KI**: YOLO. Mit Grafikkarte (Jetson): über Ultralytics/TensorRT, z. B. Yahbooms `~/ultralytics/ultralytics/yolo11n.engine` (sucht selbst, `erkennung/yolo.py`). Ohne: `models/yolov8n.onnx` auf dem Prozessor. Im Panel steht, was läuft (z. B. „TensorRT (Grafikkarte)“). 80 Dinge aus dem COCO-Datensatz, u. a. Person, Auto, Bus, Fahrrad, Hund, Ampel, Stoppschild. **Benutzt werden nur `ki_klassen`** (Standard: Person, Teddy, Ampel, Stoppschild – in der SmartCity gibt es nur Spielfiguren, Ampeln, Stopp- und Einbahnschilder; Vogel, Auto, Stuhl usw. waren Fehlerkennungen oder Dinge neben dem Spielfeld). Für jede Person schätzt die Zentrale die echte Größe (Kastenhöhe × Abstand): bis `figur_max_hoehe` (30 cm) = Spielfigur, größer oder am oberen Bildrand abgeschnitten = echter Mensch (`lib/tiefe.py`, `spielfigur`). Findet sie eine **Ampel**, schaut sie im Kasten nach, welche Lampe leuchtet.
- **Ersatz, wenn die KI nichts findet**:
  - LED-Erkennung für die winzigen SmartCity-Ampeln (`line_follower/ampel.py`, einstellbar im Panel → System → „Ampel einstellen“),
  - Achteck-Form für Stoppschilder (`line_follower/schilder.py`).
- **Einfahrt verboten**: roter Kreis mit waagrechtem weißem Balken (`schilder.finde_einfahrt_verboten`).
- **Zebrastreifen**: In der Draufsicht des Linienfolgers sind mindestens 4 gleich breite, parallele Balken nebeneinander (`lib/zebra.py`).
- **LiDAR**: nächster Punkt im Fahrschlauch (`lib/lidar.py`). Richtung "vorne" je LiDAR im Panel einstellbar.
- **Tiefenkamera**: Für jeden Bildpunkt wird die Höhe über dem Boden ausgerechnet. Den Boden lernt sie, solange der Weg frei ist (`lib/tiefe.py`). Erkennt auch den 4,5 cm hohen Würfel.
- **Wohin schaut die Kamera?** Die KI hört `/arm6_joints` mit (KI, Panel und Gamepad senden dorthin). Steht der Arm nicht in der Fahrstellung, werden Draufsicht, Zebrastreifen und Tiefe nicht ausgewertet. Linienfolger und Kartograf bekommen das ebenfalls mitgeteilt.

## Getestet (in der VM, nicht auf dem Roboter)

- Entscheidungslogik: `tests/test_entscheider.py`.
- Greif-Lernen, URDF lesen, Übungswelt: `tests/test_greifen.py`.
- Komplette Simulation mit ROS 2 Humble (`scripts/simulation.sh pruefen`), alles bestanden:
  - Ampel, Zebrastreifen mit Fußgänger,
  - Würfel anschauen, Armbewegung berechnen, wegräumen, Weg prüfen, Greifversuch lernen (simulierter Arm absichtlich etwas anders gebaut als geplant),
  - Stoppschild, Einbahnstraße (gewendet bei ca. 160°),
  - Karte.

## Grenzen (ehrlich)

- Das Modell wurde mit **echten Fotos** trainiert. Spielfiguren und Spielzeugautos erkennt es nur teilweise oder gar nicht. In der Simulation hielt es eine gezeichnete Fläche einmal kurz für eine Katze. Für die SmartCity braucht man wahrscheinlich ein **eigenes Modell** (Vorgehen: [Eigenes Erkennungsmodell](https://github.com/BBS-GuT/smartcity-roboter/wiki/Eigenes-Erkennungsmodell)).
- Zebrastreifen-, Einbahn- und Würfelerkennung sind nur mit **gezeichneten** Bildern getestet. Echte Schilder können anders aussehen (Größe, Farbe, Licht).
- Die Rechenzeit auf dem Jetson ist noch nicht gemessen. Das Panel zeigt sie an ("ms/Bild").

## Modell austauschen, Yahbooms eigene KI

Standardmodell neu exportieren, eigenes Modell für die SmartCity trainieren und was Yahbooms „KI-Großmodell“ kann: Wiki-Seite [Eigenes Erkennungsmodell](https://github.com/BBS-GuT/smartcity-roboter/wiki/Eigenes-Erkennungsmodell). Auf dem Roboter läuft das ONNX-Modell mit **onnxruntime** (`installieren.sh` bietet die Installation an). **API-Schlüssel nie ins Repository!**

Lizenz: YOLOv8 von Ultralytics steht unter AGPL-3.0.
