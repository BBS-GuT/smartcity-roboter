# Fahr-Gehirn

Ein eigener Modus, der **nur fährt**: der schwarzen Linie folgen, an Kreuzungen nach einem festen **Fahrplan**
abbiegen, vorher **blinken**, bei Hindernissen **anhalten und warten**. Kein Arm, kein Wegräumen, keine Karte, keine
KI-Zentrale. Es fährt endlos Runde um Runde, **misst** jede Kreuzung und jede Runde und **lernt** dabei die
Fahrparameter.

Der Grundbetrieb (Panel, `line_follower.py`, KI-Zentrale) bleibt unverändert. Beide dürfen nie gleichzeitig laufen
(zwei Fahrbefehle); das Fahr-Gehirn und der Linienfolger prüfen das beim Start gegenseitig.

## Dateien

| Datei | Aufgabe |
|---|---|
| `fahrgehirn/fahrgehirn.py` | ROS-Programm. Unterklasse des Linienfolgers: Linienerkennung, Lenkung, Linien-Gedächtnis und LiDAR-Notbremse sind **derselbe Code** |
| `fahrgehirn/gehirn.py` | Zustand (gestoppt/fährt/pausiert), Kreuzungen, Runden (ohne ROS, testbar) |
| `fahrgehirn/fahrplan.py` | Fahrplan: welche Richtung an welcher Kreuzung |
| `fahrgehirn/blinker.py` | Blinker-Schnittstelle `setze('links' / 'rechts' / 'aus')` und die Attrappe |
| `fahrgehirn/sicherheit.py` | feste Hindernis-Regel (wird nicht gelernt) |
| `fahrgehirn/messung.py` | Messen, Wertung, Diagnose, CSV-Protokolle |
| `fahrgehirn/lernen.py` | Lernverfahren, Grenzen, Speichern/Laden |
| `fahrgehirn/auswerten.py` | Auswertung: wird es besser, womit scheitert es? |
| `scripts/fahrgehirn_training.sh` | Start (endlos) |
| `scripts/fahrgehirn_zuruecksetzen.sh` | Gelerntes bewusst zurücksetzen |
| `sim/fahrgehirn_sim.py` | viele Runden im Simulator, mit Wahrheit zum Vergleich |
| `tests/test_fahrgehirn.py` | Softwaretests |

## Bedienung

1. Arm in **Fahrstellung** (die Kamera sitzt am Arm, sonst stimmt die Draufsicht nicht). Panel beenden oder dort nicht
   START drücken.
2. Roboter auf die Linie stellen, **vor die erste Kreuzung des Fahrplans**.
3. Start:

   ```bash
   scripts/fahrgehirn_training.sh -p fahrplan:="links, geradeaus, rechts" -p fahrplan_start:=0
   ```

   `fahrplan` = die Richtungen **einer Runde**, der Reihe nach, so wie die Strecke es erlaubt (nur `links`,
   `geradeaus`, `rechts`). Nach der letzten Kreuzung beginnt der Plan von vorn. Der Plan muss zur Strecke passen:
   Er sollte zurück zur ersten Kreuzung führen. Fester Plan statt Zufall: nur so kann man messen, ob eine Kreuzung
   geklappt hat.
   Dauerhaft eintragen geht in `config/lokal/roboter.yaml` unter `fahrgehirn:` → `ros__parameters:` → `fahrplan`.
   `fahrplan_start:=0` nur, wenn der Roboter wirklich vor der ersten Kreuzung steht. Ohne die Angabe macht er an der
   gespeicherten Plan-Position weiter.
4. **Not-Aus: `scripts/stopp.sh`** (beendet die Endlosschleife des Startskripts, das Fahr-Gehirn und den
   Linienfolger und schickt Stopp an die Motoren). Strg+C im Terminal beendet auch.

Stürzt das Fahr-Gehirn ab, startet das Skript es nach 5 s neu. Das Gelernte wird geladen, die angefangene Runde zählt
nicht.

### Schnittstelle nach außen (vorbereitet für Panel, KI-Zentrale, Arm-Gehirn)

| Topic | Inhalt |
|---|---|
| `/fahrgehirn/kommando` (String) | `start`, `stopp`, `pause`, `weiter`, `fahrplan <nr>` (Roboter umgesetzt, nächste Kreuzung = Plan-Nr.) |
| `/fahrgehirn/zustand` (String, JSON, 2×/s) | `zustand`, `fahrplan`, `fahrplan_index`, `naechste_richtung`, `blinker`, `kreuzung_aktiv`, `parameter`, `phase`, `versuch`, `halt`, `hilfe_noetig` … |
| `/fahrgehirn/blinker` (String) | `links` / `rechts` / `aus` bei jeder Änderung |
| `/fahrgehirn/antwort` (String) | Antwort auf ein Kommando |

`pause` hält an und behält alles (Runde, offene Kreuzung, Fahrplan). Nach 0,5 s Stopp-Befehlen sendet das Fahr-Gehirn
**keine** Fahrbefehle mehr: `/cmd_vel` ist frei, z. B. für ein Arm-Gehirn, das ein Hindernis wegräumt. `weiter` fährt
genau dort weiter. Das Umschalten zwischen den Gehirnen selbst ist **noch nicht** gebaut.

Beispiel: `ros2 topic pub --once /fahrgehirn/kommando std_msgs/msg/String "{data: pause}"`

## Sicherheit (fest, nicht gelernt)

Reihenfolge in jedem Fahrbefehl (20× pro Sekunde), das Erste gewinnt:

1. **Hindernis-Regel** (`fahrgehirn/sicherheit.py`): Etwas im Fahrschlauch (30 cm breiter Streifen entlang der Linie)
   näher als **30 cm** (LiDAR) oder Tiefenkamera meldet Hindernis → **STOPP**. LiDAR/Tiefenkamera fehlt, ist zu alt
   oder misst den Fahrweg nicht → ebenfalls STOPP. Weiter erst, wenn der Weg **1 s ununterbrochen** frei war.
   Nie wegräumen, nie den Arm bewegen.
   **Beim Abbiegen** gilt als Fahrschlauch der geplante Weg: bis zum geschätzten Abzweig, dann genau 90° in die
   gewählte Richtung, nur bis er eingelenkt hat (danach wieder die Linie aus dem Gedächtnis). Grund (Simulator): An
   einem T mittelt das Linien-Gedächtnis beide Arme zu „geradeaus“; ein Haus 22 cm hinter der Kreuzung lag dann
   scheinbar im Weg, der Abstand flackerte um die 30 cm, und er stand für immer. Erste Versuche mit der geschätzten
   Astrichtung (schwankt bis 35°) und dem Pfad auch nach dem Einlenken führten ebenfalls zu Dauerhalten vor Häusern
   neben der Straße. **Annahme: rechtwinklige Kreuzungen** (am Brett prüfen). Steht er länger als 60 s vor einem
   Hindernis, meldet er `hilfe_noetig` und wartet weiter.
2. Zustand: pausiert/gestoppt → steht.
3. Linienfolger mit seiner eigenen **LiDAR-Notbremse (12 cm)**, Kamera-Prüfungen (Bilder zu alt → Stopp).

`halt_abstand` und `frei_warten` lassen sich als ROS-Parameter einstellen, aber nicht unter 20 cm bzw. 0,5 s. Das
Lernen kennt diese Werte nicht und kann sie nicht ändern (Test: `test_lernen_aendert_keine_sicherheitswerte`).
Das Fahr-Gehirn hört nicht auf die KI-Zentrale (`ki_pflicht` aus), also auch nicht auf deren Halt für Ampel,
Zebrastreifen, Schilder. **Darum nur auf einer Trainingsstrecke ohne Verkehr fahren.**

## Blinker

Beim ersten Sehen einer Kreuzung schaltet es den Blinker in die Fahrplan-Richtung (`links`/`rechts`, geradeaus: aus),
nach dem Durchfahren wieder aus. Gemessen wird, wie viele Sekunden **vor** dem Einlenken er geblinkt hat
(`blink_vorlauf_s` in `kreuzungen.csv`).

Die Lichttechnik (Fork `smartcity-roboter-lichter-2`, `lib/lichter.py`) ist noch nicht in `main`. Darum gibt es nur die
schmale Schnittstelle `Blinker.setze(richtung)` mit einer **Attrappe**, die ins Log schreibt, und das Topic
`/fahrgehirn/blinker`. Später: eine Klasse mit derselben Funktion `setze()` an die Lichter hängen, oder die Lichter
lesen das Topic (deren `lichter.py` versteht schon `{'blinker': 'links'}`). Das Fahr-Gehirn ändert sich dafür nicht.

## Messen: was, wie, wo

Zuerst messen, dann lernen. Alles landet in `logs/fahrgehirn/` (bleibt über Neustarts, ist im Panel-Download
„Logs herunterladen“ enthalten):

**`kreuzungen.csv`**, eine Zeile je Kreuzung:

| Spalte | Bedeutung |
|---|---|
| `gewuenscht` | Richtung laut Fahrplan |
| `erkannt` | Kreuzung gesehen (False = nie erkannt) |
| `aeste_grad`, `gewaehlt` | welche Äste er sah und welchen er nahm |
| `gefahren`, `drehung_grad` | wie weit er sich bis 70 cm nach der Wahl gedreht hat (Lagesensor/Radzähler): über +45° = links, unter −45° = rechts |
| `ergebnis` | `ok`, `nicht_erkannt`, `richtung_fehlt` (Ast war nicht da), `falsch_abgebogen`, `linie_verloren` |
| `unsauber` | geklappt, aber dabei mehr als 4 cm neben der Linie (eigene Schätzung) |
| `max_abw_cm`, `linie_weg`, `blink_vorlauf_s`, `dauer_s`, `tempo`, `kandidat` | wie es lief, mit welchen Parametern |
| `hinweis` | z. B. warum „nicht erkannt“ (vermutet aus der Strecke, übersprungen beim Umsetzen) |

**`runden.csv`**, eine Zeile je Runde (= Fahrplan einmal durch): Kreuzungen ok/gesamt und je Fehlerart, Linienverluste,
mittlere/größte Abweichung von der Linienmitte, **Pendeln** (wie weit er auf Geraden hin und her schwankt), Lenkunruhe,
Tempo, Zeit, Sicherheits-Halte (`halte_sicherheit`: Hindernis oder Sensor unbekannt, auch beim Start), **Wertung**,
Parameter. `gewertet = False`: Runde mitten im Fahrplan begonnen (Neustart)
oder gestoppt, zählt nicht zum Lernen.

**`fortschritt.csv`**, eine Zeile je **10 gewertete Runden**: Erfolgsquote Abbiegen, mittlere Abweichung, Pendeln,
Linienverluste je Runde, Tempo, Wertung, Hauptproblem.

**Wertung einer Runde** (höchstens 100): 50 × Anteil geklappter Kreuzungen + 25 × Linienhaltung (0 cm = voll, ab 3 cm
mittlere Abweichung = 0) + 10 × Ruhe (kein Pendeln = voll, ab 2 cm = 0) + 15 × Tempo (0,25 m/s = voll) − 15 je
Linienverlust.

**Diagnose** („womit scheitert er?“): Für die letzten Runden wird ausgerechnet, wie viele Punkte jede Fehlerart kostet:
Kreuzung nicht erkannt, falsch abgebogen, Linie verloren, Pendeln, Abweichung, zu langsam. Die teuerste ist das
Hauptproblem, und nur daran wird als Nächstes gedreht.

### Grenzen der Messung auf dem Roboter (ehrlich)

- Die Abweichung von der Linie ist die **eigene Schätzung** des Roboters (Linien-Gedächtnis), kein Maßband. Im
  Simulator stimmt sie gut; an scharfen 90°-Ecken überschätzt sie (deshalb oft `unsauber`, obwohl er in Wahrheit unter
  4 cm blieb).
- „Kreuzung nicht erkannt“: Auf dem Roboter gibt es keine Wahrheit. Er vermutet es, wenn er viel weiter gefahren ist
  als sonst bis zu dieser Kreuzung (mehr als 1,6 × die übliche Strecke, nach mind. 3 Messungen). Fährt er dabei auf
  eine andere Strecke, passt der Fahrplan nicht mehr: dann anhalten (`pause`), Roboter umsetzen und
  `fahrplan <nr>` schicken (übersprungene Kreuzungen zählen als `nicht_erkannt`).
- Linie verloren und Suche vorbei: Er bleibt stehen (fährt nie blind) und meldet nach 10 s `hilfe_noetig` im Zustand
  und im Log. Wieder auf die Linie setzen genügt, dann fährt er allein weiter.
- Die gefahrene Richtung kommt aus der eigenen Drehung (Lagesensor/Radzähler). Folgt nach der Kreuzung innerhalb von
  70 cm eine Kurve, zählt die mit. Dann `messweg` kleiner stellen.

## Lernen

**In einem Satz:** Er behält immer den besten bekannten Parametersatz (Champion), probiert gezielt **eine** kleine
Änderung an dem Parameter aus, der zum größten Fehler passt, und behält sie nur, wenn die Runden damit messbar besser
waren.

1. **Champion** = beste bekannte Einstellung. Er fährt Kontrollrunden.
2. **Diagnose** sagt, was am meisten Punkte kostet (z. B. „Kreuzung nicht erkannt“). Zu jeder Fehlerart gehören die
   Parameter, die daran etwas ändern (z. B. für „nicht erkannt“: `ast_min`, `threshold`, `kreuzung_tempo`, `speed`).
   Einer davon wird um einen Schritt verändert → **Herausforderer**. Immer nur einer, damit klar ist, was gewirkt hat.
3. Der Herausforderer fährt **2 Runden**. Ist seine mittlere Wertung mindestens **0,5 Punkte** besser als die der
   letzten Champion-Runden: neuer Champion. Sonst bleibt der alte.
4. Schrittweite: nach Erfolg ×1,5, nach Misserfolg ×0,6 und nächstes Mal in die andere Richtung. So tastet er sich ans
   Optimum heran.
5. Danach 1 Kontrollrunde mit dem Champion (misst ihn unter gleichen Bedingungen nach: Akku, Licht), dann der nächste
   Versuch.

**Warum dieses Verfahren** und nicht ein Bandit wie beim Greifen (`lib/greifen.py`)? Beim Greifen gibt es 3 Werte und
ein klares Treffer/Daneben. Hier sind es 7 Parameter, und eine Runde liefert viele Messwerte. Ein Gitter über 7
Parameter hätte Millionen Kombinationen; ein Parameter nach dem anderen braucht wenige Runden, jede Änderung steht
nachvollziehbar im Protokoll, und es bleibt immer innerhalb der Grenzen.

**Gelernte Parameter und Grenzen** (`fahrgehirn/lernen.py`, `PARAMETER`; beim Laden wird immer begrenzt, auch wenn
jemand die Datei von Hand ändert):

| Parameter | Start | Grenzen | wirkt auf |
|---|---|---|---|
| `speed` | 0,15 | 0,10–0,25 m/s | Grundtempo |
| `kreuzung_tempo` | 0,7 | 0,3–1,0 | Tempo-Faktor von „Kreuzung gesehen“ bis „durchfahren“ (mehr Bilder pro cm beim Abbiegen) |
| `regel_abstand` | 44 | 20–80 | Lenkverstärkung seitlicher Abstand |
| `regel_richtung` | 13 | 6–22 | Lenkverstärkung Richtung (dämpft Pendeln) |
| `quer_beschl` | 0,15 | 0,08–0,25 m/s² | Vorausschau-Bremse vor/in Kurven |
| `ast_min` | 0,05 | 0,03–0,10 m | Schwelle der Kreuzungserkennung (Astlänge) |
| `threshold` | 70 | 45–100 | Helligkeitsschwelle Linie/Kreuzung |

Nicht gelernt: `vorausschau` (wird nur als Notlösung benutzt, wenn unter dem Roboter noch keine Linie bekannt ist, wirkt
im Normalbetrieb also kaum), `vorhersage` (misst der Linienfolger schon selbst, `selbst_einstellen`), alles zur
Sicherheit. Einen „Abbiegewinkel“ gibt es nicht als Parameter: Er folgt dem gewählten Ast; der Zeitpunkt hängt am
Tempo an der Kreuzung (`kreuzung_tempo`) und an der Erkennung (`ast_min`, `threshold`).

### Wo gespeichert

`config/lokal/fahrgehirn.json` (nicht im Repository, `git pull`/`scripts/update.sh` lassen es in Ruhe). Inhalt:
Champion, laufender Versuch, Wertungen, Schrittweiten, Protokoll der letzten 200 Versuche, Fahrplan-Position, typische
Strecken zwischen den Kreuzungen.

- Gespeichert wird **nach jeder Kreuzung und jeder Runde**, **atomar**: erst `fahrgehirn.json.neu` ganz schreiben, dann
  umbenennen. Bei Stromausfall bleibt die alte Datei ganz.
- Beim Start wird sie geladen. Prozess beenden und neu starten → Werte und Lernstand sind identisch (Test
  `test_prozess_neu_starten_behaelt_lernstand` startet dafür wirklich einen zweiten Python-Prozess).
- Unlesbare Datei: wird nach `.kaputt` verschoben (nicht überschrieben), er startet mit den Startwerten.
- **Zurücksetzen nur bewusst:** `scripts/fahrgehirn_zuruecksetzen.sh` (fragt nach, legt Sicherungen von Lernstand und
  Protokollen an). Automatisch passiert das nie.
- Nur messen, nichts ändern: `-p lernen:=false`.

## Fortschritt ablesen

```bash
python3 fahrgehirn/auswerten.py
```

zeigt je 10 Runden Erfolgsquote Abbiegen, Abweichung, Pendeln, Linienverluste, Tempo, Wertung und Hauptproblem, dazu die
Ergebnisse je Kreuzung im Fahrplan und die letzten Lernversuche mit „ANGENOMMEN/verworfen“. Besser wird es, wenn
`Abbiegen` und `Wertung` steigen und `Abw. cm`, `Pendeln`, `Linie weg` sinken. Im Log (`logs/fahrgehirn/fahrgehirn.log`)
steht alle 10 Runden eine Zeile `FORTSCHRITT bis Runde …`. Die CSV-Dateien lassen sich auch in LibreOffice Calc öffnen.

## Simulator

```bash
python3 sim/fahrgehirn_sim.py --runden 40           # mit Lernen
python3 sim/fahrgehirn_sim.py --runden 20 --nicht_lernen   # Vergleich: feste Startwerte
python3 sim/fahrgehirn_sim.py --runden 3 --hindernis       # Figur steht im Weg: Stopp, warten, weiter
```

Ohne ROS, mit simulierter Uhr und dem echten Fahr-Gehirn-Code (wie `sim/linie_messen.py`). Welt: Rechteck 2,2 × 1,4 m
mit Mittelsteg = zwei T-Kreuzungen, Fahrplan `links, rechts, geradeaus, geradeaus, rechts, links` (ca. 16 m je
Runde). Der Simulator misst **selbst** (Wahrheit) und vergleicht mit der Selbstmessung des Fahr-Gehirns. Kommt der
Roboter vom Weg ab, setzt ihn ein „Helfer“ hinter die Kreuzung und schickt `fahrplan <nr>`.
Antrieb, Sensorverzögerungen und Kamera sind **geschätzt** (siehe `docs/linie.md`), nicht am Roboter gemessen.

### Ergebnisse (Simulator, 22.10.2026, nur Software, Antrieb `echt`)

| Lauf | Runden | Abbiegen je 10 Runden (Selbstmessung) | Wertung je 10 Runden | Pendeln cm | Wahrheit |
|---|---|---|---|---|---|
| fest (Startwerte, kein Lernen) | 15 | 100 % / 100 % (5 Runden) | 83,7 / 84,0 | 0,64 / 0,54 | 89/89 Kreuzungen richtig, Abweichung Ø 0,76 cm, 95 % < 2,4 cm |
| Lernen ab Startwerten | 30 | 100 / 100 / 100 % | 83,6 / 82,0 / 83,0 | 0,59 / 1,18 / 0,55 | 179/179 richtig, Ø 0,79 cm, 95 % < 2,5 cm |
| Lernen ab verstimmten Werten (`speed=0.25 regel_richtung=6 regel_abstand=80 kreuzung_tempo=1.0`) | 30 | 95 / 100 / 100 % | **78,0 / 83,6 / 83,0** | **1,72 / 1,32 / 1,35** | 173/179 richtig (6× vom Weg / festgehalten), Ø 0,86 cm |

Was das heißt (ehrlich):

- **Mit den Startwerten** klappen im Simulator alle Kreuzungen; das Lernen findet nichts Besseres und verwirft fast
  alle Versuche (das ist richtig so). Ein Versuch (`quer_beschl` 0,15 → 0,138) wurde angenommen, obwohl der Unterschied
  im Rauschen liegt: Die Wertung einer Runde streut um ca. ±1,5 Punkte, die Schwelle ist 0,5. Auf dem Roboter (mehr
  Streuung) eher `RUNDEN_JE_VERSUCH = 3` oder `VORSPRUNG = 1.5` nehmen.
- **Von verstimmten Werten aus** wird es messbar besser: Es erhöht die Dämpfung (`regel_richtung` 6 → 11) und senkt
  `regel_abstand` (80 → 65), Pendeln sinkt von 1,7 auf 1,3 cm, Wertung von 78 auf 83. Nach 30 Runden ist es aber
  **noch nicht** so gut wie die Startwerte (Pendeln 0,55 cm), und im dritten Block stagniert es. Schneller fahren
  verwirft es: Auf dieser Strecke bremsen Kurven und Kreuzungen, mehr Grundtempo bringt kaum Zeit und mehr Abweichung.
- **Selbstmessung** (nur Roboter-Sensoren) und Wahrheit stimmten bei 179/179 bzw. 176/179 Kreuzungen überein. Die 3
  Abweichungen: Er bog richtig ab und hielt danach wegen eines Hauses dicht neben der Strecke (Simulator zählt das als
  Fehlschlag, das Fahr-Gehirn als geklappte Kreuzung).
- `unsauber` (Selbstmessung > 4 cm an der Kreuzung) steht bei fast jedem Abbiegen, obwohl die Wahrheit an den
  Kreuzungen meist 3–5 cm zeigt: An scharfen 90°-Ecken überschätzt die eigene Messung.
- **Hindernis** (`--hindernis`, 2 Runden): Figur 60 cm vor ihm auf die Linie gestellt, er hielt 28 cm davor (Mitte
  bis Figur), fuhr 1,2 s nach dem Wegnehmen weiter, 0 Berührungen.
- Gefundene und behobene Fehler durch die Messung: Abbiegen von einer durchgehenden Linie (0/4 → 100 %,
  `abbiegen_halten`), Dauerhalt vor einem Haus hinter einem T (Fahrschlauch an Kreuzungen), „geradeaus“-Ast bei +35°
  geschätzt (fälschlich `richtung_fehlt`), Absturz der Pendel-Rechnung bei kurzen Geraden.
- Rechenzeit: ca. 1 min je Runde (ein Kern). Lernen braucht viele Runden: je Versuch 3 Runden (2 Herausforderer + 1
  Kontrolle), also ca. 10 Versuche je 30 Runden.

## Was die Softwaretests belegen und was nicht

**Belegt (ohne Roboter, `tests/test_fahrgehirn.py`):** Speichern/Laden identisch und atomar, echter Neustart in einem
zweiten Prozess behält Lernstand und Fahrwerte, Grenzen auch bei handgeänderter Datei, Ausprobieren bleibt immer in den
Grenzen, Hindernis-Stopp hat Vorrang (auch vor offener Kreuzung, KI-Manöver, Panel-Tempo) und wartet `frei_warten`,
ohne LiDAR/Tiefenkamera kein Fahren, Haus hinter einem T stoppt beim Abbiegen nicht (geradeaus schon), Lernen ändert
keine Sicherheitswerte, Fahrplan statt Zufall (Zufall wird nicht
gefragt), Grundbetrieb ohne Fahrplan weiter zufällig, Blinker vor dem Einlenken (und über das Topic), Pause gibt
`/cmd_vel` frei, Runden/Fortschritt/Diagnose, Neustart mitten im Plan wird nicht gewertet, `hilfe_noetig` nach 10 s
ohne Linie.

**Erst die Abnahme am Roboter zeigt:**

- ob Kreuzungen auf dem echten Brett erkannt und sauber gefahren werden (Kamera-Einstellung, Licht, echte Kreuzungsform,
  Haltelinien) und ob `abbiegen_halten` dort hilft;
- ob die Selbstmessung (Drehung, Abweichung, „nicht erkannt“-Vermutung) zur Wirklichkeit passt: einige Runden
  beobachten und mit `kreuzungen.csv` vergleichen;
- ob der Hindernis-Stopp mit den echten LiDARs/der Tiefenkamera rechtzeitig hält (Figur, Holzwürfel unter der
  LiDAR-Ebene!) und erst nach freiem Weg weiterfährt;
- ob `scripts/stopp.sh` das laufende Training sofort beendet (Schleife + Programm) und der Roboter steht;
- ob ein Neustart des Roboters/Programms den Lernstand behält (`python3 fahrgehirn/auswerten.py --lernstand` vorher und
  nachher vergleichen);
- ob es über viele Runden wirklich besser wird (`fortschritt.csv`), oder ob Akku/Licht/Rutschen das Lernen stören.
