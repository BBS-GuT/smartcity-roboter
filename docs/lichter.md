# Abblendlicht und Blinker

Rechnet das Panel (`lib/lichter.py`, 10x pro Sekunde) und sendet den Zustand auf `/lichter/zustand`
(`std_msgs/String`, JSON: `abblend`, `blinker` = `null`/`"links"`/`"rechts"`, `blink_an`, `grund`, `leds`).

## Bedienung (Dashboard, unter dem Tempo-Regler)

- **Abblendlicht**: Knopf in der Mitte schaltet an/aus. **START schaltet es vor dem Losfahren ein.** Wer es während
  der Fahrt ausschaltet, sieht den Hinweis „Fährt ohne Abblendlicht!“.
- **Blinker**: Pfeile links/rechts blinken grün, solange der Roboter blinkt. Darunter steht der Grund. Jedes An/Aus
  steht auch in den Ereignissen.

## Wann blinkt er?

1. Die KI meldet ausdrücklich `"blinker": "links"/"rechts"` im Befehl (Platz für die Wegwahl an den Kreuzungen K1–K8,
   **gibt es noch nicht**).
2. KI-Manöver mit Drehung (z. B. Wenden) in Drehrichtung. Rückwärtsfahren blinkt nicht.
3. Die Linie ca. 70–80 cm voraus zeigt um mindestens `kurve_grad` (60°) von der eigenen Fahrtrichtung weg.
   Er blinkt also **vor** der Ecke. Sanfte Kurven blinken nicht.

Die Linie zählt erst, wenn sie `bestaetigen` s (0,5 s) lang zur selben Seite abknickt; die Seite wechselt erst nach
`wechsel` s (1,5 s). Sonst blinkte er vor Kreuzungen hin und her (mehrere Linienäste, RM02 21.10.).
Danach blinkt er noch `nachlauf` s (1 s) weiter, insgesamt mindestens `mindest` s (2 s). Takt 1,5 Hz.
Einstellungen: Abschnitt `lichter:` in `config/roboter.yaml` (eigene Werte in `config/lokal/roboter.yaml`).

## LED-Leiste am Roboter

Das Panel schickt die Farben an `/rgb` (`std_msgs/ColorRGBA`, Empfänger ist das Board über den micro-ROS-Agent).
Feld `a` wählt die LED: `0` = alle, `1`–`8` = eine LED (gefunden auf RM02, `~/rgb_zuordnung.txt`), `r`/`g`/`b` = Farbe
0–255. Gesendet werden nur geänderte LEDs, alle 2 s einmal die ganze Leiste. Beim Beenden des Panels gehen die LEDs aus.

Auf RM02 sitzt LED 1 rechts (`links_zuerst: false`, 21.10. geprüft).
Von Hand ausprobieren (Panel vorher beenden):

```bash
ros2 topic pub --once /rgb std_msgs/msg/ColorRGBA "{r: 90.0, g: 90.0, b: 90.0, a: 0.0}"    # alle weiß
ros2 topic pub --once /rgb std_msgs/msg/ColorRGBA "{r: 255.0, g: 140.0, b: 0.0, a: 1.0}"   # LED 1 gelb
ros2 topic pub --once /rgb std_msgs/msg/ColorRGBA "{r: 0.0, g: 0.0, b: 0.0, a: 0.0}"       # alle aus
```

Achtung: Das Gamepad (`yahboom_joy_M3Pro.py`) schaltet mit seiner Lichttaste ebenfalls auf `/rgb` (Effekte, `a` ab 100).
Während der Fahrt nicht drücken.
