# Lichter (F1)

Abblendlicht, Blinker links/rechts, Warnblinker und Blaulicht für die vordere LED-Leiste. Issue [#24](https://github.com/davidheinrich73/smartcity-roboter/issues/24).

## Stand

| Teil | Stand |
|---|---|
| Lichtlogik `lib/lichtlogik.py` | fertig, Softwaretests `tests/test_lichter.py` |
| ROS-Programm `lichter/lichter.py` | fertig, veröffentlicht `/lichter/zustand` |
| Echte LED-Leiste ansteuern | **offen**: Topic und Nachrichtentyp der Yahboom-Platine unbekannt |
| LED-Anzahl und Reihenfolge links/rechts | **nicht am Roboter geprüft** (Annahme: 14 LEDs, Index 0 = links) |
| Blinker beim Abbiegen an Kreuzungen | **offen**: Abbiegen gibt es noch nicht (B2). Bis dahin blinkt nur bei KI-Manövern |
| Blaulicht automatisch beim RTW-Einsatz | **offen**: RTW-Einsatz ist vorerst entfernt. Bis dahin nur per Kommando |

## Verhalten

- **Abblendlicht:** weiß in der Mitte der Leiste, an, solange `lichter/lichter.py` läuft.
- **Blinker:** gelb an den äußeren LEDs, 1,5 Hz (StVZO/ECE R6: 90 ± 30 Takte pro Minute). Automatisch, wenn die KI ein Manöver mit Drehung (ab 0,15 rad/s) oder Querfahrt (ab 0,03 m/s) fährt, z. B. Wenden oder Ausweichen. Richtung nach ROS: Drehung gegen den Uhrzeigersinn bzw. Querfahrt nach links = links. Kleine Lenkkorrekturen des Linienfolgers lösen keinen Blinker aus. Nach dem Manöver 1 s Nachlauf. Ein KI-Befehl älter als 0,6 s gilt als ausgefallen, der Blinker geht dann aus.
- **Warnblinker:** beide Seiten, nur per Kommando.
- **Blaulicht:** blau, Mitte der Leiste, linke und rechte Hälfte abwechselnd mit 2,5 Hz. Ersetzt in der Zeit das Abblendlicht. Blinker bleibt sichtbar.
- Ein Handbefehl für den Blinker hat Vorrang vor der KI, bis `blinker aus`.

Die Lichtsteuerung liest nur. Sie sendet keine Fahr- oder Armbefehle und hat keinen Einfluss auf die Motorfreigabe.

## Ausprobieren

```bash
source scripts/env.sh
python3 lichter/lichter.py &
ros2 topic echo /lichter/zustand
ros2 topic pub --once /lichter/kommando std_msgs/msg/String "data: 'blaulicht an'"
```

Kommandos: `abblendlicht an|aus`, `blinker links|rechts|aus`, `warnblinker an|aus`, `blaulicht an|aus`.

## Einstellungen

`config/lichter.yaml`, eigene Werte eines Roboters in `config/lokal/lichter.yaml` (gleicher Aufbau, nicht im Repository).

## Nächster Schritt am Roboter (nur lesen)

Bevor die echte Leiste angesteuert wird, muss am stillstehenden Roboter feststehen, wie die Platine die LEDs annimmt. Nur lesende Befehle:

```bash
ros2 topic list -t | grep -i -E "rgb|light|led|beep|buzzer"
ros2 topic info -v <gefundenes Topic>
grep -rn -i -E "rgb|light" ~/yahboomcar_ws/src/*/*/yahboom_joy_M3Pro.py
```

Ergebnis (Topic, Typ, Subscriber, Bedeutung der Werte) hier eintragen. Erst danach einen Ausgang in `lichter/lichter.py` ergänzen. Kann die Platine nur fertige Effekte statt einzelner LEDs, ist das Konzept „Blinker an den äußeren LEDs“ dort nicht umsetzbar und muss angepasst werden.
