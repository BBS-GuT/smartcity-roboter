# Geometrischer Kreuzungsfahrablauf: lokale Integration

`tests/test_kreuzung_fahrablauf.py` ergänzt die getrennten Prüfungen in
`test_kreuzung.py`, `test_line_follower.py` und `test_entscheider.py` um fünf
zusammenhängende Softwaresequenzen. Aufruf aus der Projektwurzel:

```sh
python tests/test_kreuzung_fahrablauf.py
```

## Tatsächlich verbundene Module

Synthetische Kamerabilder aus dem vorhandenen `test_kreuzung.bild_bei_pose`
gehen durch `LineFollower.on_image`, `LinienSucher.suche` und das reale
Liniengedächtnis. `Entscheider.update` verarbeitet synthetische Wahrnehmungen;
sein tatsächliches JSON-Ergebnis geht durch `LineFollower.on_ki` und
`steuern` bis zum `Twist`-Publisher. Die lokale LiDAR-Fusion bekommt zwei
LaserScan-Nachrichten mit der ausdrücklich synthetischen Geometrie aus
`tests/attrappen/lidar_testdaten.py`. Keine Produktdefaults werden freigegeben.
Nur der Zufallszug wird auf den linken sichtbaren Ast festgelegt; Erkennung,
Auswahlbindung, Lenkung und Schutzentscheidungen werden nicht nachgebaut.

| Sequenz | Nachweis am tatsächlichen Modulausgang |
|---|---|
| Wahl, begonnene Linksdrehung, LiDAR-Notbremse, Wiederaufnahme, Ausfahrt | Zunächst positive Vorwärtsfahrt und Drehkommando, dann alle drei Twist-Komponenten null; Wahl und Linie im Gedächtnis bleiben. Freier Scan ohne frisches Linienbild reicht nicht. Frische Eingaben nach bestehender Wartezeit ermöglichen Fahrt; nach gerichteter Ausfahrt wird die Wahl gelöscht und Linie weiter verfolgt. |
| Neue lokale LiDAR-Sperre vor KI-Verarbeitung | KI-Ergebnis bleibt ausdrücklich `fahren`; der Linienfolger veröffentlicht trotzdem null. Nach frischen freien Scans folgt derselbe Ast bis zur Linienfahrt. |
| Rot während begonnener Drehung, Signal verschwindet, Grün bei Hindernis | Zwei Rotbilder binden den Halt, auch nach sechs Sekunden ohne sichtbares Signal; Wahl bleibt erhalten. Grün hebt die Ampelbindung auf, aber nicht LiDAR-Halt und dessen bestehende Nachwartezeit. Erst danach Fahrt und gerichtete Ausfahrt. |
| Explizite START-Quittierung des Rot-Halts | Statusausfall und Wiederkehr quittieren nichts. START bei inaktiver Fahrt hebt Rot noch nicht auf; erst aktive Fahrt verarbeitet die explizite Quittierung. Danach gerichtete Ausfahrt. Dies prüft den vorhandenen KI-Vertrag, keinen Prozessneustart. |
| Panel-STOPP während Drehung | Echter `/api/stopp`-Handler ruft `PanelNode.stillstand` und `Prozesse.stopp` auf. SIGINT-Anforderung und Prozesswait werden beobachtet. Der echte `LineFollower.main`-Aufräumpfad sendet fünf Nullkommandos, beendet Executor/Node; das Panel sendet insgesamt zehn Nullkommandos. Neue Node hat weder alte Wahl noch alte Linie. |

## Explizite Grenzen und offene Produktverbindungen

- ROS-Publisher, Nachrichtenzustellung, Executor, HTTP-I/O und POSIX-Prozess-/
  Signaltransport sind lokal ersetzt. Der STOPP-Test stellt KeyboardInterrupt
  am Hauptloop zu; er startet/stoppt keinen Betriebssystemprozess. HighGUI-
  Fensterabbau wird für headless OpenCV ersetzt. Ein Gerät oder Motorboard
  wurde nicht angesprochen; Nullkommando ist kein gemessener Stillstand.
- Die Posen und Zeitfolge werden vorgegeben, nicht aus Befehlen physikalisch
  simuliert oder durch Odometrie/IMU gemessen. Geometrische Wahlauflösung ist
  kein unabhängiger Nachweis einer real geräumten Kreuzung. Spiegelungen und
  weitere Kreuzungsbilder bleiben im vorhandenen Geometrietest.
- Die Wahrnehmung wird direkt an den echten Entscheider übergeben. Kamera-KI,
  `ki/zentrale.py`, ROS-Transport und gemeinsame Sensorzeitzuordnung sind kein
  Bestandteil dieses Tests. Der lokale Bremsfall vor KI-Verarbeitung prüft
  ausdrücklich die zeitlich getrennten Verbraucher.
- `lib/b2_auswahl.py` ist weiterhin nicht an diesen normalen Fahrpfad
  angeschlossen. Bestätigte Produzenten für Knoten/eigene Zufahrt, gerichtete
  Erlaubnisse und positive Ein-/Ausfahrtnachweise fehlen. Die Tests belegen
  keine Erlaubnisprüfung nach GB-05/09 und ersetzen sie nicht durch Adapter.
- Der Entscheider erhält keine geometrische Querungsphase. Der Rot-Test
  dokumentiert deshalb den vorhandenen Halt auch während begonnenen Abbiegens;
  eine Trennung von Einfahrtsbindung und bereits begonnenem Räumen gemäß
  Zieldefinition 4.3 ist im normalen Pfad damit nicht nachgewiesen.
- Panel-STOPP beendet den Linienfolger. Die vorherige Wahl lebt nur noch im
  beendeten Objekt; ein neuer Prozess setzt sie nicht fort. Es gibt keinen
  belegten sicheren Asttransfer oder Wiederanlauf mitten in der Kreuzung.
  Der Test kopiert keine Wahl und erfindet keine automatische Quittierung.
- Bestehende Ampel-, Zebra-, Hindernis- und Armtests bleiben eigenständige
  Regressionen; diese Ergänzung verändert keine Fahrarchitektur und bietet
  keine vollständige Runde oder Geräteabnahme für RM01/RM02.
