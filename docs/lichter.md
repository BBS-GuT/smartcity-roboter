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
3. Die Linie vor dem Roboter (Linien-Gedächtnis, ca. 80 cm voraus) knickt um mindestens `kurve_grad` (60°) ab.
   Er blinkt also **vor** der Ecke. Sanfte Kurven blinken nicht.

Danach blinkt er noch `nachlauf` s (1 s) weiter, insgesamt mindestens `mindest` s (2 s). Takt 1,5 Hz.
Einstellungen: Abschnitt `lichter:` in `config/roboter.yaml` (eigene Werte in `config/lokal/roboter.yaml`).

## Offen: echte LEDs am Roboter

Welches Topic die vordere LED-Leiste des Motorboards annimmt, ist **noch nicht geprüft**. Bis dahin leuchtet am
Roboter nichts, nur das Dashboard zeigt es an. Nachsehen: Panel → System → „Licht-Topics anzeigen“
(oder `ros2 topic list -t | grep -i -E 'light|led|rgb'`). Dann einen kleinen Treiber schreiben, der
`/lichter/zustand` liest und `leds` (Farben von links nach rechts, Anzahl `leds`, je Seite `blink_leds` für den
Blinker) ans Board gibt.
