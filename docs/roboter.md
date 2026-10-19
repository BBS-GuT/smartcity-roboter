# Roboter-Übersicht

| Roboter | IP | Zustand | Bemerkung |
|---|---|---|---|
| RM01 | ? | ? | noch nicht geprüft |
| RM02 | 10.0.12.62 (Schulnetz), früher 192.168.8.88 | fährt, Linie + Ampel laufen | Referenz-Roboter, Akku 12,5 V am 01.10. |
| RM03 | 192.168.8.88 | fährt | ein Rad schwächer, keine Sensordaten; alter Code von früheren Teams im Home-Ordner |
| RM04 | ? | ? | noch nicht geprüft |

Alle: Benutzer `jetson`, Domain-ID 30, micro-ROS-Agent startet automatisch.

Welcher Roboter ist es? Alle heißen `yahboom`. `scripts/installieren.sh` fragt einmal nach dem Namen und speichert ihn in `~/roboter_name`. Panel → System → „Systemcheck“ zeigt ihn an, dazu die MAC-Adressen (bei jedem Gerät anders), bitte hier eintragen.

| Roboter | MAC WLAN | MAC LAN |
|---|---|---|
| RM01 | ? | ? |
| RM02 | ? | ? |
| RM03 | ? | ? |
| RM04 | ? | ? |

## Mehrere Roboter gleichzeitig

Alle Roboter nutzen ab Werk ROS-Domain-ID 30. Dann hört jeder Roboter die Fahrbefehle der anderen mit. **Deshalb nie zwei Roboter mit derselben Domain-ID gleichzeitig einschalten.**

Für gleichzeitiges Fahren braucht jeder Roboter eine eigene Nummer (z. B. RM01 = 31, RM02 = 32 ...):
1. Unsere Programme: `echo 32 > ~/ros_domain_id` (wird von `scripts/env.sh` gelesen).
2. Yahboom-Teil (micro-ROS-Agent, Autostart) muss **dieselbe** Nummer bekommen. Das ist eine Änderung an Yahboom-/Systemeinstellungen: nur nach Absprache mit der Lehrkraft, vorher sichern.

Im Verkehr erkennen sich die Roboter gegenseitig als Hindernis (LiDAR). Stehen zwei voreinander, wartet jeder eine zufällige Zeit (12–25 s), dann fährt einer etwas zurück und wendet. So blockieren sie sich nicht dauerhaft.
