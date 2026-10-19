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

## Kamera nachmessen (wichtig!)

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
| `such_zeit` / `such_dreh` | 3.0 / 0.7 | Linie weg: so lange (s) drehend suchen, danach Stopp |
| `notbremse_dist` | 0.12 | eigene LiDAR-Notbremse (m), unabhängig von der KI |
| `obstacle_check` | true | Notbremse an/aus (RM03 hat kein LiDAR → `false`) |
| `ki_pflicht` | true | ohne KI-Zentrale nicht fahren |

## Was er an die KI meldet

`/line_follower/status` (JSON): unter anderem `linie_quer`/`linie_kurs` (Lage der Linie am Roboter) und `weg`. `weg` ist die Linie vor dem Roboter als Punktliste. Daraus macht die KI den **Fahrschlauch**: Nur was entlang der Linie liegt, gilt als Hindernis. Häuser neben einer Kurve stören deshalb nicht mehr.
