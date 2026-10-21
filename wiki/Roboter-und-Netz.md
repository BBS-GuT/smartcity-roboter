# Roboter und Netz

Schnellübersicht für den Alltag. Das verbindliche Geräteinventar (Bereich E, mit Beleg und Datum) liegt im Repository unter [`docs/geraete/`](https://github.com/BBS-GuT/smartcity-roboter/tree/main/docs/geraete). Was dort als „offen“ steht, ist nicht geprüft, auch wenn es hier steht.

| Roboter | IP | Zustand | Bemerkung |
|---|---|---|---|
| RM01 | ? | ? | noch nicht geprüft |
| RM02 | 10.0.12.62 (Schulnetz), früher 192.168.8.88 | fährt, Linie + Ampel laufen | Referenz-Roboter, Akku 12,5 V am 01.10. |
| RM03 | 192.168.8.88 | fährt | ein Rad schwächer, keine Sensordaten; alter Code von früheren Teams im Home-Ordner |
| RM04 | ? | ? | noch nicht geprüft |

Alle: Benutzer `jetson`, Domain-ID 30, micro-ROS-Agent startet automatisch.

## Welcher Roboter ist es?

Alle heißen `yahboom`. `scripts/installieren.sh` fragt einmal nach dem Namen und speichert ihn in `~/roboter_name`. Panel → System → „Systemcheck“ zeigt ihn an, dazu die MAC-Adressen (bei jedem Gerät anders). Die IP-Adresse ist **keine** Geräteidentität, sie ändert sich mit dem Netz (VLAN).

| Roboter | MAC WLAN | MAC LAN |
|---|---|---|
| RM01 | ? | ? |
| RM02 | ? | ? |
| RM03 | ? | ? |
| RM04 | ? | ? |

Bitte gemessene MACs zusätzlich in `docs/geraete/RM0x.md` eintragen (per PR), dort mit Datum und prüfender Person.

## Mehrere Roboter gleichzeitig (Domain-ID)

**Kurz erklärt:** Die ROS-Domain-ID ist eine Kanalnummer. Alle ROS-Programme mit derselben Nummer im selben Netz hören sich gegenseitig, egal auf welchem Rechner sie laufen.

Alle Roboter nutzen ab Werk ROS-Domain-ID 30. Dann hört jeder Roboter die Fahrbefehle der anderen mit. **Deshalb nie zwei Roboter mit derselben Domain-ID gleichzeitig einschalten.**

Für gleichzeitiges Fahren braucht jeder Roboter eine eigene Nummer (z. B. RM01 = 31, RM02 = 32 ...):

1. Unsere Programme: `echo 32 > ~/ros_domain_id` (wird von `scripts/env.sh` gelesen).
2. Yahboom-Teil (micro-ROS-Agent, Autostart) muss **dieselbe** Nummer bekommen. Das ist eine Änderung an Yahboom-/Systemeinstellungen: nur nach Absprache mit der Lehrkraft, vorher sichern.

Stimmen die Nummern nicht überein, sieht unser Programm den Roboter nicht mehr (keine Sensoren, keine Motoren). Das Panel meldet das im Systemcheck.

Die Simulation nutzt Domain 77, damit sie nie einen echten Roboter steuert ([Simulation in der VM](Simulation-in-der-VM)).

## Roboter blockieren sich gegenseitig

Im Verkehr erkennen sich die Roboter gegenseitig als Hindernis (LiDAR). Laut Zieldefinition (GB-04) hält ein blockierter Roboter an und **wartet**. Das automatische Ausweichen (zufällige Wartezeit 12–25 s, dann zurück und wenden) gibt es im Code noch, es ist aber standardmäßig **aus** (`ausweichen: false`, siehe [`docs/ki.md`](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/ki.md)). Gegenverkehr auf der Querstraße muss die Infrastruktur (Ampeln) regeln.
