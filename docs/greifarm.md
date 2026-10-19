# Greifarm

## Auf RM02 geprüft

- `/arm6_joints` gibt es, Typ `arm_msgs/msg/ArmJoints` mit `joint1`–`joint6` und `time` (alles `int16`). Subscriber = Motorboard (über den micro-ROS-Agent). Prüfen: Panel → Arm → „Arm-Topics anzeigen“ (nur lesen).
- Die Gamepad-Steuerung (`yahboomcar_ctrl/yahboom_joy_M3Pro.py`, startet automatisch) sendet ebenfalls auf `/arm6_joints` und `/arm_joint`. **Gamepad und Panel nicht gleichzeitig am Arm benutzen.**
- Startstellung der Gamepad-Steuerung: **90, 120, 10, 20, 90, 0**. Damit lief unser Linienfolger → in `config/arm.yaml` als `fahrstellung` (Greifer 30 statt 0).
- Yahbooms eigener Linienfolger (`largemodel_arm/follow_line.py`): **90, 90, 12, 20, 90, 0** → als `yahboom_linie`. Achtung: Dort wird Servo 1 als `180 - Wert` geschickt (bei 90 egal).
- Beim Greifer waren „zugreifen“ und „öffnen“ vertauscht (siehe unten, jetzt nach Yahboom eingestellt).

## Was in Yahbooms Unterlagen steht

Quelle: [Yahboom ROSMASTER M3 Pro, Kursunterlagen](https://github.com/YahboomTechnology/ROSMASTER-M3PRO) (Kapitel „Robotic Arm and 3D Space Gripping“, „Configuration and Operation Guide“).

| Was | Wert |
|---|---|
| Alle Servos | `/arm6_joints` (`arm_msgs/msg/ArmJoints`): `joint1`…`joint6` in ganzen Grad, `time` in ms |
| Ein Servo | `/arm_joint` (`arm_msgs/msg/ArmJoint`): `id`, `joint`, `time` |
| Winkel | Servo **90** = Glied zeigt gerade nach oben. Alle auf 90 = Arm senkrecht |
| Greifer (Servo 6) | **30 = offen**, 120–130 = zugegriffen, 180 = ganz zu (größer = fester). Eine andere Yahboom-Anleitung sagt das Gegenteil → **am Roboter prüfen** |
| Kinematik | Dienst `/get_kinemarics` (`arm_interface/srv/ArmKinemarics`), Programm `ros2 run arm_kin kin_srv`. Rechnet mit dem echten Robotermodell (URDF): Zielpunkt → Servowinkel (`ik`) und Servowinkel → Punkt (`fk`) |
| Kamera | sitzt am Arm-Ende („eye-in-hand“). Umrechnung Kamerapunkt → Arm mit einer festen Matrix und der Vorwärtsrechnung |
| Kalibrierung | 1. Mittelstellung (`calibrate_arm.py`), 2. Versatz mit einem 4-cm-Würfel (`arm_offset`) → `~/yahboomcar_ws/src/arm_kin/param/offset_value.yaml` |

**Vorsicht bei Servo 1:** Yahboom schickt Servo 1 als `180 - joint1` aus der Kinematik. Das übernimmt unser Code genauso.

## Hindernis wegräumen: so rechnet die KI die Armbewegung aus

Es gibt **keine eingelernten Greif-Posen** mehr. Die KI misst das Hindernis und rechnet aus, wie die Servos stehen müssen (Ablauf: [ki.md](ki.md), „Hindernis wegräumen“).

1. Die Tiefenkamera liefert, wo das Hindernis im Bild ist (Bildpunkt) und wie weit weg (Tiefe).
2. **Echter Roboter:** Yahbooms Kinematik-Dienst rechnet daraus den Punkt im Arm-System (wie in Yahbooms `grasp_desktop.py`: Kamerapunkt → Arm-Ende → `base_link`, plus Versatz aus `offset_value.yaml`). Dann fragt die KI für jeden Schritt (über dem Hindernis, unten, angehoben, an der Ablagestelle) die Servowinkel ab.
3. **Simulation:** eigene, einfache Rechnung (`lib/arm.py`, `Kinematik`) mit ausgedachten Maßen aus `sim/arm_sim.yaml`. Der Simulator rechnet aus den Servowinkeln nach, wo der Greifer wirklich ist. Daneben gegriffen = nicht gegriffen.
4. Erreicht der Arm einen Punkt nicht, bewegt sich nichts. Der Roboter wartet.

Die eigene Rechnung benutzt die KI auf dem echten Roboter **nicht**, die Maße sind nur geschätzt. Ausnahme: `eigene_kinematik: true` in `config/lokal/arm.yaml`, und nur, wenn die Maße unter `geometrie:` nachgemessen sind.

## Vor dem ersten echten Versuch (in dieser Reihenfolge)

1. **Greifer prüfen:** Panel → Arm → „Greifer auf“ / „Greifer zu“. Ist es falsch herum, in `config/lokal/arm.yaml` eintragen:
   ```yaml
   greifer_auf: 130
   greifer_zu: 30
   ```
2. **Yahbooms Arm-Kalibrierung** machen (Mittelstellung und Versatz, siehe oben). Ohne sie greift die Kinematik daneben.
3. **Kinematik prüfen:** Panel → Arm → „Kinematik prüfen“. Das bewegt nichts. Es zeigt, wo laut Yahboom-Modell das Arm-Ende in der Fahrstellung ist, und rechnet einen Testpunkt 22 cm vor dem Roboter. Kommt „nicht installiert“ oder „antwortet nicht“, räumt die KI nichts weg, sie hält nur an und wartet.
4. **„KI darf den Arm bewegen“** einschalten (Panel → Arm), KI neu starten (Panel → System).
5. Ersten Versuch mit kleinem Tempo machen, eine Hand am STOPP. Würfel mittig auf die Linie legen.

**Ungeprüft auf dem Roboter:** Der Kinematik-Dienst, die Umrechnung Kamerapunkt → Arm und die Greifer-Werte sind aus Yahbooms Unterlagen übernommen, aber noch nie auf unserem Roboter gelaufen. Der LiDAR könnte den Arm sehen, wenn er vorne bis zum Boden greift. Dann greift die Notbremse (unter 12 cm), und der Ablauf wartet, bis sie vorbei ist.

## Im Panel (Seite "Arm")

- 6 Schieberegler, "Pose anfahren", Greifer auf/zu, Dauer der Bewegung.
- Gesperrt, solange das Fahrprogramm läuft (die Kamera sitzt am Arm).
- Werte außerhalb der Bereiche werden abgelehnt, nicht gekürzt.
- **Posen einlernen**: Regler einstellen, mit "Pose anfahren" prüfen, dann den passenden Knopf drücken. Gespeichert wird in `config/lokal/arm.yaml`. Die Datei ist nicht im Repository, bleibt also bei Updates erhalten. Standardwerte stehen in `config/arm.yaml`. Danach die KI neu starten (System).

| Pose | Wofür | Hinweis |
|---|---|---|
| **fahrstellung** | Linienfolgen. **Als Erstes!** | Startstellung der Gamepad-Steuerung ist voreingestellt. Kameramaße danach nachmessen (`docs/linie.md`) |
| blick_links / blick_rechts | Zebrastreifen und Karte: umschauen | ohne eigene Pose: Fahrstellung mit Servo 1 um ±45° gedreht. **Richtung ungeprüft**: zeigt "links" nach rechts, beide neu einlernen |

Alle Werte aus `ki/entscheider.py` (`STANDARD`) lassen sich einstellen, z. B. `greif_vor` (wie weit vor der Robotermitte er zum Greifen hält). Eintragen in `config/lokal/roboter.yaml`:

```yaml
ki_zentrale:
  ros__parameters:
    greif_vor: 0.24
```

Danach die KI neu starten.
