# Entwicklungsauftrag A Sicherheit und Motorfreigabe

**Empfänger:** Unser separater Entwicklungs-Chat. **Jetzt umzusetzen:** A1. **Branch:** `fix/gb-a1-sensorfreigabe`. **Zielbezug:** GB-12, GB-13, GB-14; A11/A12.

Du entwickelst am Team-Repository `https://github.com/BKoewenig/smartcity-roboter`. Dieser Chat ist der Umsetzungs-Chat für Bereich A. Der Chat „SmartCity – Orchestrierung Grundbetrieb“ koordiniert Aufgaben und Integration. Lies die [gemeinsamen Regeln](00-gemeinsame-regeln.md), das [Aufgabenregister](README.md), die Zieldefinition und den Prüfbericht. Die Unterlagen liegen zunächst auf `codex/grundbetrieb` in PR #11.

## Auftrag A1

Korrigiere zwei konkrete Freigabefehler im Linienfolger, ohne dessen öffentliche Nachrichtenformate umzubauen:

1. **Ungültige Aufnahmezeit darf keine frische Kamera erzeugen.** Der geprüfte Code setzt bei einem sehr alten, zukünftigen oder unbrauchbaren Stempel die Aufnahmezeit auf jetzt. Dadurch fährt die Entscheidung bei sechs Sekunden altem Bild, während sie bei 0,7 Sekunden altem Bild hält. Entferne diese Freigabe durch Ersatzzeit. Führe den ungültigen Zeitbezug als sichtbaren Haltgrund. Eine abweichende Zeitbasis braucht später ein ausdrücklich geprüftes Verfahren, keine stillschweigende Frischeannahme.
2. **Jeder Bewegungswunsch muss die Pflichtprüfungen passieren.** Die aktuelle Notbremsausnahme liefert Dreh-/Rückwärtsbefehle schon vor der Kameraprüfung und sogar bei vollständig fehlendem LiDAR. Fehlende erforderliche Wahrnehmung muss sämtliche Bewegungsrichtungen sperren. Kein Durchgriff eines Manövers vor diesen Prüfungen. Noch nicht vorhandene geprüfte Ersatz-/Rückwärtsverfahren werden nicht durch bloße Annahmen freigegeben.

Prüfe zuerst den tatsächlichen aktuellen Hauptstand; der Befund stammt aus `b9f6442`. Erhalte die vorhandene Aufnahmeposenkorrektur, Bewegungsrückmeldung und Regelung, soweit die Korrektur dies zulässt. Keine Reparatur durch Abschalten von `obstacle_check`, `ki_pflicht`, Altersprüfung oder durch Erhöhen der Grenzwerte.

## Dateien und Grenzen

Für A1 bearbeiten:

- `line_follower/line_follower.py`
- `tests/test_line_follower.py`
- neue `tests/test_sicherheitsfreigabe.py`, falls getrennte Regressionen sinnvoll sind
- optional `docs/entwicklung/A1-sensorfreigabe.md` als kurze Übergabe

`lib/lidar.py`, `scripts/env.sh`, `scripts/stopp.sh` und der spätere interne Motorweg sind zwar Bereich A zugeordnet, gehören aber noch nicht zum ersten A1-PR. Kein Umbau von `ki/*`, `line_follower/linie.py`, `panel/*`, gemeinsamen Attrappen, Vertrag oder CI. Melde notwendige Anschlüsse an B/C/D. Kein zweites gemeinsames Telemetrieschema einführen.

## Konkrete Bestehenskriterien

- Gültiges frisches Bild und gültige übrige Pflichtdaten erlauben die bisher zulässige normale Entscheidung als positive Kontrolle.
- Bildalter über der geltenden Grenze führt zum Halt. Prüfe die Grenze und insbesondere 0,7 Sekunden sowie mehr als fünf Sekunden; der ältere Fall darf nicht wieder frischer werden.
- Zukunftsstempel, fehlender/unbrauchbarer Stempel und fehlende Kamerabilder liefern einen sichtbaren sicheren Zustand.
- Frischer KI-Drehwunsch ohne Scans und Kamera liefert ausschließlich Nullbewegung. Gleiches gilt für Rückwärts- und Seitenwunsch ohne erforderliche Daten.
- Kritischer Abstand und fehlende Pflichtdaten können nicht durch die Manöverausnahme übergangen werden.
- Relevante bestehende Tests bleiben sinnvoll. Frühere Erwartungen wie „Drehen trotz fehlendem LiDAR“ anhand GB-13/14 korrigieren und die Änderung erklären; nicht nur den Test entfernen.
- Neue Tests rufen den tatsächlichen Entscheidungspfad auf. Keine reine Nachbildung der fehlerhaften Logik im Test.

Keine Hardwarefahrt in diesem Auftrag. Ein grüner Test bestätigt die Softwareentscheidung, nicht den gemessenen Motorstillstand. Berichte welche verbleibenden Fälle A1 noch nicht löst, insbesondere globale STOPP-Sperre, Scanqualität und Fahrzeughülle.

## Arbeitsweise und Lieferung

Arbeite in einer eigenen Kopie, beispielsweise `C:\SmartCity\entwicklung\gb-a1-sicherheit`. Prüfe einen bereits vorhandenen Ordner vor Wiederverwendung; keine fremden Änderungen zurücksetzen. Basis ist aktuelles `origin/main`, nicht die alte lokale Reparaturarbeitskopie.

Lieferung: kleiner Draft-PR nach `main`, Tests mit tatsächlichem Ergebnis, Liefercommit und Übergabebericht nach dem gemeinsamen Format. Kein Merge nach `main` durch diesen Entwicklungs-Chat. Keine Direktnachrichten an andere Chats als Ersatz für den Übergabebericht; der Orchestrator kann deinen Status und PR lesend abholen.

## Folgeauftrag A2 erst nach Zuteilung

Nach geprüftem A1 und akzeptiertem C1-Vertrag folgt ein eigener Auftrag für einen alleinigen finalen Motorpublisher, verriegelten STOPP/Fehlerhalt, gültige Fahrwünsche, Sensorpflichten je Zustand und klar getrennte Freigabeergebnisse. Dann Scanqualität einschließlich vollständig ungültiger Bereiche und Ausfall konfigurierter Quellen behandeln. A integriert den Motoranschluss im Linienfolger; C integriert Panelbedienung und Zustandsübernahme über die vereinbarte Schnittstelle.

Gemessene Sensortransformationen, Hülle und Bremsgrenzen kommen aus E. Fehlende Messwerte bleiben sperrend. Diese größeren Arbeiten nicht in A1 hineinziehen und nicht ohne akzeptierten gemeinsamen Vertrag beginnen.
