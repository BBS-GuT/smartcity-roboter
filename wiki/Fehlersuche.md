# Fehlersuche

Erst nachsehen, ob das Problem schon bekannt ist: [Problemprotokoll](Problemprotokoll).

## Logs holen

Panel → System → „Logs herunterladen“ lädt alle Protokolle als `.tar.gz`.

- Sie liegen auf dem Roboter in `logs/` im Projektordner, je Programm der aktuelle und der vorige Lauf (`*.alt.log`).
- Im Archiv stehen pro Datei höchstens die letzten 1 MB, insgesamt höchstens 8 MB. Was fehlt oder gekürzt ist, steht in `logs/HINWEISE.txt`.
- `logs/system.log` zeigt alle 2 s Rechnerlast, IO-Warten, Speicher/Swap, GPU, Temperatur und die Programme mit der meisten Rechenzeit. „HING x s“ heißt: der ganze Rechner hing.
- Wichtige Einzellogs: `ki.log` (Entscheidungen, Wegräumen, Greifen), `karte.log` (Kartograf), Linienfolger-Log.

Simulation: Logs in `/tmp/sim_*.log` (Prüfen) bzw. `logs/*.log` (mit Panel).

## Typische Meldungen

| Meldung / Symptom | Bedeutung | Was tun |
|---|---|---|
| „KI-ZENTRALE ANTWORTET NICHT -> STOPP“ | Linienfolger bekommt keine KI-Befehle | `system.log` ansehen: hängt der ganze Rechner oder braucht ein Programm sehr viel CPU? Bildschirmfreigabe beenden, Panel im Laptop-Browser öffnen |
| „KAMERABILDER ZU ALT“ | Bilder älter als 0,6 s (ab 0,25 s halbes Tempo) | Rechenlast senken, siehe oben |
| „Rote Ampel nicht mehr zu sehen -> warte auf Gruen“ | Rot bleibt wirksam, bis Grün erkannt wird | Gewollt (Zieldefinition). Bewusst freigeben: STOPP, dann START |
| „hinten nicht frei -> warte (wegnehmen, dann STOPP und START)“ | Hindernis zu nah für die Kamera | Hindernis wegnehmen, dann STOPP und START |
| „raeume nicht weg: …“ | Arm darf/kann nicht. Grund steht dahinter | z. B. Panel → Arm → „KI darf den Arm bewegen“ |
| „Linie weg -> suche“, dann Stopp | Linie verloren, er dreht nur ca. 30° zur letzten Seite | Roboter zurück auf die Linie, Kamera-Einstellung prüfen |
| Karte dreht weg oder ist doppelt | Lokalisierung passt nicht | [Messfahrt aufzeichnen](Messfahrt-aufzeichnen) |
| Panel bleibt bei „KI startet …“ | KI-Modell lädt | 10–20 s warten, sonst `logs/ki.log` |
| Chromium öffnet kurz und schließt sich | Snap-Problem auf dem Jetson | [Panel-Browser auf dem Jetson](Panel-Browser-auf-dem-Jetson) |
| Programme sehen den Roboter nicht | Domain-ID passt nicht zum micro-ROS-Agent | [Roboter und Netz](Roboter-und-Netz) |

## Nützliche Befehle am Roboter

Vorher `source scripts/env.sh` (setzt ROS und die Domain-ID).

```bash
ros2 topic list                           # welche Kanäle gibt es?
ros2 topic hz /scan0                      # kommen Daten, wie oft?
ros2 topic echo /line_follower/status     # was der Linienfolger meldet (JSON)
ros2 topic info -v /cmd_vel               # wer sendet Fahrbefehle? Es darf nur einer sein
ros2 param set /line_follower kamera_neigung 35.0   # Einstellung im laufenden Betrieb ändern
```

## Einen Fehler melden

Neuen Eintrag im [Problemprotokoll](Problemprotokoll) (per PR in `docs/problemprotokoll.md`, am besten im selben PR wie der Fix) oder ein Issue mit: Gerät, Commit (`git rev-parse --short HEAD`), was erwartet war, was passiert ist, Uhrzeit, Logs bzw. Messfahrt.
