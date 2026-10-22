# Arm-Gehirn (nur Greifen, Roboter fährt nicht)

Ein eigener Modus, der **nur greift**: Gegenstand vor dem Roboter finden und vermessen, entscheiden ob er weggeräumt werden darf, greifen, an einer festen Ablagestelle abstellen, Arm zurück in die Grundstellung, selbst prüfen, ob es geklappt hat, daraus lernen. Der Antrieb ist gesperrt: Das Arm-Gehirn hat keinen Sender für Fahrbefehle und startet nicht, solange Linienfolger oder KI-Zentrale laufen.

Grundlage: [Zieldefinition](zieldefinition-grundbetrieb.md) (Abschnitt 2.2: Greifen wird separat entwickelt und geprüft) und die Entscheidung in Issue #8 (Wegräumen gehört zum Grundbetrieb). Der Grundbetrieb bleibt unverändert lauffähig; er nutzt dieselbe Lerndatei, sodass das hier Gelernte später auch beim Wegräumen im Fahrbetrieb wirkt.

| Datei | Aufgabe |
|---|---|
| `armgehirn/sicherheit.py` | **feste** Regel: darf weggeräumt werden? (nicht gelernt, Vorrang vor allem) |
| `armgehirn/blick.py` | Umschauen: Blickstellungen ausrechnen und üben (keine eingespeicherten Blick-Posen nötig) |
| `armgehirn/augen.py` | Tiefenkamera + Kamera-KI je Blickstellung, Boden je Blick |
| `armgehirn/pruefung.py` | Erfolg selbst prüfen → Ergebnis und Belohnung |
| `armgehirn/gehirn.py` | Ablauf eines Versuchs, Schnittstelle start / abbrechen / status |
| `armgehirn/protokoll.py` | CSV je Versuch, Fortschritt, Ziel „gut und zuverlässig“ |
| `armgehirn/lage.py` | Lage-Kalibrierung der Kamera mit Markierungen |
| `armgehirn/knoten.py` | Anschluss an ROS (Kamera, Tiefe, YOLO, Arm), Topics nach außen |
| `armgehirn/training.py`, `scripts/armgehirn_training.sh` | Trainingsschleife |
| `lib/greifen.py` | Greif-Lernen (jetzt lageabhängig), gemeinsam mit dem Grundbetrieb |
| `sim/armgehirn_sim.py`, `sim/armgehirn_messen.py` | Übungswelt und Vorher/Nachher-Messung |

## Diagnose: Warum wurde das Greifen gefühlt nicht besser?

### a) Speichern und Laden von `config/lokal/greifen.json`

| Geprüft | Befund |
|---|---|
| Speichern nach jedem Versuch | Ja, `ki/zentrale.py` `greif_ergebnis` → `Politik.speichern()` (atomar `.neu` → umbenennen). **Aber nur**, wenn die Kontrolle „Weg frei?“ zu Ende kam. Bei „Kontrolle unsicher“ (nicht ganz zurückgefahren), Abbruch (Person 30 s, Zeitgrenzen) wird nichts gelernt. |
| Laden beim Start | Ja, `Politik(name)` beim ersten Gebrauch. |
| Löschen/Überschreiben | `scripts/update.sh` fasst `config/lokal/` nicht an (in `.gitignore`). Gelöscht wird nur über Panel → „Gelerntes zurücksetzen“ (läuft die KI nicht, löscht das Panel die **ganze** Datei). Eine kaputte Datei wurde beim nächsten Speichern ohne Sicherung überschrieben (jetzt: Sicherung `.kaputt_…`). |
| `SMARTCITY_GREIFEN` | Nur in `scripts/simulation.sh` und `sim/pruefen.py` gesetzt (Simulation → `/tmp`). Auf dem Roboter nicht, solange man es nicht selbst in `~/.bashrc` einträgt. |
| **Schlüssel `eigene` / `yahboom`** | **Fehler gefunden.** Ob mit Yahbooms Kinematik-Dienst (`yahboom`) oder eigener Rechnung (`eigene`) geplant wird, entschied `ki/zentrale.py` **bei jedem Plan neu** (`kin.bereit()`). Je nachdem, ob der Dienst gerade antwortete, landete ein Versuch in einem anderen Modell. Das Modell `yahboom` hat **kein Vortraining und keine Lageabhängigkeit**. Und das Panel zeigte immer den Lernstand von `eigene`, auch wenn in `yahboom` gelernt wurde → „es wird nicht besser“. Behoben: Kinematik wird beim ersten Plan festgelegt, das Panel zeigt das zuletzt benutzte Modell, jedes Ereignis nennt das Modell. |
| Z_MIN | Wurde die Korrektur wegen `Z_MIN` angehoben, lernte er aus der **nicht** angefahrenen Korrektur. Behoben: gelernt wird der wirklich angefahrene Punkt. |
| **Belohnung „Weg frei?“** | Schiebt der Greifer den Würfel nur aus dem Bild, zählte das als **Erfolg**, und „Gewinner bleibt“ wiederholte genau diese falsche Korrektur. Im Arm-Gehirn ersetzt durch die genauere Prüfung (unten). |

### b) Wo entsteht der Fehler?

Am echten Roboter gibt es dazu **noch keine Messdaten**. Das Arm-Gehirn protokolliert deshalb ab jetzt pro Versuch: gemessene Lage, kalibrierte Lage, wahre Lage (wenn der Gegenstand auf einer Markierung liegt), angefahrener Punkt, Korrektur, Ergebnis, Verschiebung, Abstand zur Ablagestelle (`config/lokal/armgehirn/versuche.csv`). Mit Markierungen trennt das **Wahrnehmungsfehler** (gemessen − wahr) vom Rest (**Kinematik + Servos**).

In der Übungswelt (nicht am Gerät; 12 Zufallsroboter Bauart M3 Pro, `sim/greifen_welt.py`):

| Fehlerquelle | Mittel (vorne / links / hoch) | Streuung zwischen Robotern |
|---|---|---|
| Wahrnehmung (Kamera/Tiefe) | 0,3 / −0,1 / 0,0 cm | 0,7 / 0,8 / 0,1 cm |
| Kinematik (Armmaße, Servo-Nullpunkte, Durchhängen) | −0,8 / 0,2 / 0,1 cm | 0,9 / 0,6 / **1,1 cm** |

Wie viel bleibt nach einer **festen** Korrektur je Roboter übrig, wie viel nach einer **lageabhängigen**? (95 % der Würfel liegen höchstens so weit daneben):

| Bereich | feste Korrektur | lageabhängig |
|---|---|---|
| Greifweite im Fahrbetrieb (±2 cm vorne, ±4,5 cm seitlich) | 0,96 cm | 0,64 cm |
| Arm-Gehirn, frei hingelegt (8 cm vorne, ±7 cm seitlich) | 1,76 cm | 1,03 cm |

Ergebnis: Der größte Einzelfehler ist die **Kinematik** (vor allem die Höhe), die Kamera trägt etwa gleich viel zur seitlichen Streuung bei. Je größer der Bereich, in dem Gegenstände liegen, desto mehr hängt der Fehler von der Lage ab, und eine feste Korrektur reicht nicht. Das muss am echten Roboter mit den Markierungsversuchen bestätigt werden.

**Weiterer Befund (Geometrie):** Mit den Nennmaßen sieht die Kamera in der **Fahrstellung** den Boden erst ab ca. 25 cm vor der Robotermitte, der Arm des M3 Pro reicht aber nur bis ca. 20–22 cm. Ohne heranzufahren muss das Arm-Gehirn die Kamera also anders stellen → Umschauen (unten).

## Wie das Lernen funktioniert

**Gewähltes Verfahren:** Bayes-Lernen mit gewichteten Stichproben (adaptives Importance Sampling) und Thompson-Sampling; ein „kontextueller Bandit“, also Reinforcement Learning in kleiner, nachvollziehbarer Form.

- **Was gelernt wird:** Korrektur = Vortraining + Grundkorrektur `c` (3 Zahlen) + Lageabhängigkeit `B` (wie sich die Korrektur je 5 cm weiter vorne / weiter links ändert, 6 Zahlen). Damit sind auch systematische Fehler von Kamera und Tiefe (Versatz, Maßstab, kleine Drehung) abgedeckt.
- **Wie:** 3000 Vermutungen für die 9 Zahlen. Jede bekommt ein Gewicht danach, wie gut sie *alle* gemerkten Versuche erklärt: Bei „abgelegt“ zählen die Vermutungen, bei denen der Greifer innerhalb seiner Öffnung um den Gegenstand gelandet wäre. Bei „verschoben“ zählen die, bei denen eine Backe ihn knapp getroffen hätte, bei „unberührt“ die übrigen. Dann werden neue Vermutungen um die guten herum gezogen (5 Runden).
- **Ausprobieren:** Für den nächsten Versuch zieht er eine Vermutung nach Gewicht (Thompson-Sampling): anfangs breit, später fast immer die beste.
- **Warum dieses Verfahren:** Es kommt mit wenigen Versuchen aus (Vorwissen aus dem Vortraining, jeder Versuch zählt, auch Fehlversuche). Es braucht nur numpy, also **kein PyTorch** (ca. 0,6 s je Versuch auf einem Laptop-Kern bei 150 gemerkten Versuchen). Es ist nachvollziehbar (Lernstand = 9 Zahlen + Unsicherheit) und hat feste Grenzen. Ein neuronales Netz bräuchte tausende Versuche, eine reine Ausgleichsgerade bräuchte gemessene Fehler statt Erfolg/Misserfolg.
- **Sichere Grenzen** (wie bisher): gelernte Korrektur höchstens ±4 cm (vorne/seitlich) bzw. ±2 cm (hoch) vom Vortraining, Ausprobieren höchstens 40 % des Spielraums des Greifers neben der besten Korrektur, `Z_MIN` 6 mm über dem Boden, Servos höchstens 60°/s, Winkel außerhalb der Grenzen werden abgelehnt.
- **Lage-Kalibrierung (bei Bedarf):** Gegenstand auf Markierungen mit bekannter Lage legen (`--kalibrieren`). Ausgleichsrechnung *wahre Lage = M · (1, gemessen vorne, gemessen seitlich)*. Zeigt, wie groß der Kamerafehler ist, und korrigiert ihn vor dem Greifen.

### Messung in der Übungswelt (vorher / nachher)

`python3 sim/armgehirn_messen.py --roboter 10`: 10 neue Zufallsroboter (Bauart M3 Pro), je 60 Lernversuche (jeder 7. eine Spielfigur), danach 20 gleiche Prüfwürfel ohne Ausprobieren. Würfelmitte 15–20 cm vorne, ±5 cm seitlich. **Nur Simulation.**

| Variante | Lernen je 10 Versuche | Prüfung | mittlerer Zielfehler | Figur angefasst |
|---|---|---|---|---|
| bisheriges Verfahren (Gitter, nur Grundkorrektur, Belohnung „alter Ort frei“) | 77 70 72 85 85 80 % | 84,0 % | 0,98 cm | 0 |
| feste Grundkorrektur, Belohnung „alter Ort frei“ | 77 80 77 85 83 90 % | 86,0 % | 0,83 cm | 0 |
| feste Grundkorrektur, feine Belohnung | 82 82 83 88 88 90 % | 88,0 % | 0,72 cm | 0 |
| **lageabhängig + feine Belohnung (Arm-Gehirn)** | 65 84 81 84 83 75 % | 87,5 % | 0,82 cm | 0 |

**Ehrlich:** In diesem kleinen Bereich ist in der Übungswelt **kein Vorteil** des lageabhängigen Lernens messbar. Alle Varianten liegen innerhalb des Zufalls von 10 Robotern × 20 Würfeln, und am Anfang probiert es mehr aus (erste 10 Versuche schlechter). Der Vorteil zeigt sich, wenn der Fehler stark von der Lage abhängt (Test `LageabhaengigesLernen`: 79–100 % statt 40–50 % mit fester Korrektur). Ob das am echten Roboter so ist (Kameramaßstab, Neigung), zeigen erst die Markierungsversuche. Die feine Belohnung verhindert vor allem, dass weggeschobene Würfel als Erfolg gelernt werden. Die übrigen Fehlversuche in der Übungswelt sind überwiegend Höhenfehler (Arm hängt durch) und knapp daneben gegriffene Würfel. **Niemand erreicht hier 90 %**: Das Ziel ist anspruchsvoll und muss am Gerät gezeigt werden.

### Erfolg selbst prüfen

Nach dem Ablegen schaut die Kamera an den alten Ort und zur Ablagestelle (`armgehirn/pruefung.py`):

| Ergebnis | Bedingung | Belohnung | gelernt als |
|---|---|---|---|
| abgelegt | alter Ort frei **und** Gegenstand an der Ablage (± 4 cm) | 1,0 | getroffen |
| verloren | Greifer meldete „gefasst“, liegt aber nicht an der Ablage | 0,5 | getroffen (Greifpunkt stimmte) |
| verschoben | liegt noch da, ≥ 1 cm bewegt, oder anderswo im Bild | 0,2 | knapp daneben |
| unberührt | liegt unverändert da | 0,0 | daneben |
| unklar | alter Ort frei, aber nirgends zu sehen; oder Kamera konnte nicht prüfen | – | **nicht** gelernt |

Die Greiferstellung (Servo 6 nach dem Schließen) kann der M3 Pro **nicht** zurückmelden (`docs/greifarm.md`). Die Schnittstelle ist vorbereitet (`arm.greifer()` → gefasst / leer / unbekannt), bis dahin entscheidet die Kamera.

### Umschauen (geübt, keine festen Blick-Posen nötig)

`armgehirn/blick.py` rechnet mit der eigenen Kinematik aus, in welchen Armstellungen die Kamera (an der Hand) den Greifbereich 10–25 cm vor dem Roboter ganz sieht, und nimmt die drei besten. Dazu kommt Servo 1 um 0°, ±25° und ±50° gedreht (zur Seite schauen). Beim Suchen schaut er **immer zuerst geradeaus** (höchstens 2 Stellungen) und erst dann gedreht, jede Drehung mindestens einmal. Grund (RM02, 22.10.): Ein mittiger Würfel wurde zufällig im gedrehten Blick vermessen. Die Lage hängt dort an Drehrichtung und Drehachse von Servo 1, deshalb griff er mehrere cm seitlich daneben. Für jede zählt er, wie oft er dort etwas gefunden hat, und schaut beim nächsten Mal zuerst dorthin, wo es sich bewährt hat (Bayes/Thompson wie beim Greifen). Liegt ein Gegenstand am Bildrand abgeschnitten, schaut er weiter. Zur Ablage dreht er Servo 1 so, dass die Kamera auf die Ablagestelle zeigt. Eine eingelernte Pose `greifblick` (`config/lokal/arm.yaml` → `posen`) wird zuerst probiert, ist aber nicht nötig.

## Sicherheitsregel (fest, nicht gelernt)

`armgehirn/sicherheit.py` entscheidet **vor** dem Greifen, das Lernen kann sie nicht ändern. Gegriffen wird nur, wenn **alles** erfüllt ist, sonst nicht (im Zweifel nicht greifen):

1. Keine Person/Figur, kein Tier, kein Fahrzeug im Bild (Kamera-KI ab 25 % Sicherheit), auch nicht in einer anderen Blickrichtung beim Umschauen. Läuft die Kamera-KI nicht → nicht greifen.
2. Die Tiefenkamera sieht den Gegenstand in mindestens 4 Bildern und 70 % der Bilder, und er liegt still (Lage schwankt < 8 mm; eine Hand bewegt sich).
3. Ganz im Bild (nicht am Rand abgeschnitten). Größe 1,5–6 cm breit, 1,5–6,5 cm hoch. Was mehr als 2,6-mal so hoch wie breit ist, steht wie eine Figur → nie (auch wenn die Kamera-KI die Figur nicht erkennt).
4. Optional: nur Klassen eines eigenen Modells (`raeumbar_klassen`, `nur_klassen`).

**Während des Greifens:** Läuft ein Mensch ins Bild, wird **nicht** abgebrochen und der Arm hält **nicht** an (Vorgabe). Abbrechen geht nur ausdrücklich von außen (`abbrechen` / Strg+C): Dann kommt kein weiterer Armbefehl, der Arm bleibt stehen, wo er ist. Mit `grundstellung` fährt er zurück.

Grenzwerte in `config/lokal/arm.yaml` anpassen (an echten Würfeln und Figuren prüfen!):

```yaml
armgehirn:
  ablage: [0.10, -0.18]          # Ablagestelle (Mitte, m vor der Robotermitte / links)
  markierungen: [[0.15, 0.0], [0.18, 0.0], [0.15, 0.05], [0.15, -0.05], [0.18, 0.05], [0.18, -0.05]]
  sicherheit:
    form_max: 2.6
    hoehe_max: 0.065
```

## Bedienung

1. Panel/Fahrprogramm beenden (Linienfolger und KI-Zentrale dürfen nicht laufen), Gamepad nicht benutzen. Eine Hand am Not-Aus.
2. `scripts/armgehirn_training.sh` startet die Kamera, falls nötig, und das Training.
3. Beim ersten Start: Bereich vor **und rechts neben** dem Roboter leer räumen → er lernt den Boden in allen Blickstellungen (`--einrichten` macht das neu).
4. Pro Versuch: Gegenstand 15–20 cm vor die Robotermitte legen (seitlich bis ±5 cm), Hände weg, dann
   - **Enter** = räumbarer Gegenstand (soll gegriffen werden)
   - **p** = Person/Spielfigur (Erwartung: *nicht* greifen; bewusst mittrainieren!)
   - **m2** = räumbarer Gegenstand genau auf Markierung 2 (misst zusätzlich den Kamerafehler)
   - **g** / **f** = Arm in Grundstellung / Fahrstellung, **q** = Ende
5. Er greift, legt ab, prüft, lernt, **speichert** und meldet den Fortschritt. Dann den Gegenstand neu hinlegen.
6. Optional: `scripts/armgehirn_training.sh --kalibrieren` (Lage-Kalibrierung mit Markierungen).
7. Ohne Roboter: `python3 armgehirn/training.py --sim` (Übungswelt, legt selbst hin, speichert nach `/tmp`).

### Wo gespeichert wird

| Datei | Inhalt |
|---|---|
| `config/lokal/greifen.json` | Greif-Lernen (Modell `eigene`), dieselbe Datei wie im Fahrbetrieb. Nach **jedem** Versuch atomar (`.neu` → umbenennen). |
| `config/lokal/armgehirn.json` | Umschauen (gefunden/gesucht je Blickstellung), gelernter Boden je Blick, Lage-Kalibrierung. Ebenfalls atomar. |
| `config/lokal/armgehirn/versuche.csv` | eine Zeile je Versuch (Trennzeichen `;`) |
| `config/lokal/armgehirn/fortschritt.csv` | alle 10 Versuche: Quote letzte 10 / letzte 30, mittlerer Zielfehler, verbotene richtig erkannt, Ziel erreicht |

Alles in `config/lokal/` ist nicht im Repository und bleibt bei `scripts/update.sh` erhalten. Nach einem Neustart ist der Lernstand identisch (Test: `tests/test_armgehirn.py`, `test_neustart_lernstand_identisch`). Zurücksetzen nur bewusst: `scripts/armgehirn_training.sh --zuruecksetzen` (fragt nach) oder Panel → Arm → „Gelerntes zurücksetzen“.

### Fortschritt ablesen

- Im Terminal nach jedem Versuch: `40 Versuche (34 raeumbar): letzte 10 90 %, letzte 30 87 %, je 10: 60 % 80 % 90 % 90 %; Zielfehler 0.9 cm; verbotene Gegenstaende richtig nicht gegriffen 6/6`.
- `fortschritt.csv` in LibreOffice öffnen (Trennzeichen `;`) → Spalte `quote_letzte_30` als Diagramm.
- **Ziel „gut und zuverlässig“:** mindestens **90 % der letzten 30** Versuche mit räumbarem Gegenstand *abgelegt* **und** alle Versuche mit Person/Figur richtig *nicht* gegriffen (mindestens 5). Dann meldet das Skript `*** ZIEL ERREICHT ***`. Wird je eine Figur gegriffen, gilt das Ziel nie als erreicht.
- **Zielfehler:** am Roboter der Abstand des abgelegten Gegenstands zur Ablagestelle (in ihm stecken Greif- und Ablagefehler), in der Übungswelt der wahre Abstand Greifermitte – Würfelmitte. Lagefehler der Kamera: Spalte `lagefehler_cm` (nur mit Markierung).

## Schnittstelle nach außen (vorbereitet)

`python3 armgehirn/knoten.py` startet nur die Schnittstelle (ohne Trainingsfragen):

| Topic | Richtung | Inhalt |
|---|---|---|
| `/armgehirn/kommando` | rein | `start` („Objekt vor dir“), `abbrechen`, `grundstellung`, `fahrstellung`, `status` |
| `/armgehirn/zustand` | raus, 1/s | JSON: `zustand` (bereit / laeuft / fertig / abgebrochen / fehler), `phase`, `ergebnis`, `antrieb`, `lernstand`, `fortschritt` |
| `/armgehirn/ergebnis` | raus | JSON am Ende jedes Versuchs („fertig + Ergebnis“) |

In Python dasselbe: `ArmGehirn.start()`, `.abbrechen()`, `.status()`, `.warte_fertig()`, `.grundstellung()`, `.fahrstellung()`.

## Wie man später alles wieder zusammenbaut

Das Umschalten ist **noch nicht** gebaut. Vorgesehener Weg:

1. **Fahr-Gehirn hält an** (Hindernis im Weg, KI-Zentrale entscheidet „wegräumen“). Motorweg gesperrt (STOPP-Zustand, nicht nur Geschwindigkeit 0).
2. **Fahr-Gehirn entladen:** Linienfolger beenden (wie `scripts/stopp.sh`), KI-Zentrale gibt den Arm frei (darf ihn nicht mehr bewegen). Grund: Beide bewegen sonst den Arm bzw. die Kamera, und das Arm-Gehirn startet nicht neben ihnen.
3. **Arm-Gehirn laden:** `armgehirn/knoten.py` starten, `start` senden, auf `/armgehirn/ergebnis` warten. Nicht erreichbar → Fahr-Gehirn darf *dafür* ein Stück heranfahren (das macht nie das Arm-Gehirn), dann erneut `start`.
4. **Arm-Gehirn fertig:** `fahrstellung` senden (dort stimmt das Kameramodell des Linienfolgers), Arm-Gehirn beenden.
5. **Fahr-Gehirn wieder laden:** erneute vollständige Prüfung vor Wiederanfahrt (Zieldefinition 6: kein Wiederanfahren durch Timer/Ereignis allein; bewusste Freigabe).

Gelerntes ist schon jetzt gemeinsam: Das Wegräumen im Fahrbetrieb (`ki/zentrale.py`) liest dieselbe `config/lokal/greifen.json` (Modell `eigene`). Dort bleibt die Belohnung allerdings „Weg frei?“, bis die genauere Prüfung auch dort eingebaut ist. Die Ablaufsteuerung `ki/ablaeufe.py` `Wegraeumen` könnte später durch Aufrufe des Arm-Gehirns ersetzt werden. Die Zieldefinition fordert dafür eine einzige Entscheidungszentrale: Das Arm-Gehirn wäre dann ein Werkzeug der KI-Zentrale, keine zweite Zentrale.

## Was belegt ist und was nicht

| Belegt durch Softwaretests (`tests/test_armgehirn.py`, `tests/test_greifen.py`) | Muss die Abnahme am echten Roboter zeigen |
|---|---|
| Speichern/Laden, Neustart → identischer Lernstand, alte Lerndateien lesbar, kaputte Datei gesichert | dass `config/lokal/` auf dem Jetson wirklich bleibt (Update, Stromausfall) |
| Person/Figur im Bild, Figurform ohne KI-Erkennung, unruhiger/abgeschnittener Gegenstand, fehlende KI → nie gegriffen | ob YOLO echte Spielfiguren/Hände erkennt; ob die Grenzwerte (Form, Größe) echte Würfel durchlassen und Figuren abweisen |
| Mensch läuft während des Greifens ins Bild → kein Abbruch; `abbrechen` → kein weiterer Armbefehl | Verhalten des echten Arms bei Abbruch (Servos halten, Gegenstand im Greifer) |
| kein Fahrbefehl im Code, Start verweigert neben Linienfolger/KI-Zentrale, unerreichbar → meldet statt zu fahren | dass das Gamepad-Programm (Yahboom) nicht dazwischen funkt |
| lageabhängiges Lernen konvergiert in einer ausgedachten Welt und schlägt die feste Korrektur | ob es am echten Arm mit einigen Dutzend Versuchen ≥ 90 % erreicht |
| Umschauen findet seitlich liegende Gegenstände und lernt die Richtung | ob die ausgerechneten Blickstellungen den Greifbereich wirklich zeigen (Kameramaße!), Ablageblick |
| Prüfung abgelegt / verschoben / unberührt / unklar | ob die Tiefenkamera den Gegenstand an der Ablage und aus der Nähe sicher sieht |
