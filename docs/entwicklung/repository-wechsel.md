# Arbeitsrepository seit 21.10.2026

Aktuelles Repository: https://github.com/BKoewenig/smartcity-roboter

Die vorhandene lokale Arbeitskopie wurde weiterverwendet. Ihr Ordnername
`smartcity-ben` ist unabhängig vom Repositorynamen und kann bestehen bleiben.
`origin` verwendet für Abruf und Push die neue URL:

```bash
git remote set-url origin https://github.com/BKoewenig/smartcity-roboter.git
git fetch --prune origin
git remote -v
```

Bei der Umstellung zeigte das neue `main` auf
`d92e366907fd538c377c272250a0e2d75120b5e2`, identisch zum vorhandenen lokalen
`main`. Der lokale Branch `feat/mqtt-panel-telemetrie` auf `faa9f63` sowie alle
nicht committeten MQTT-Änderungen bleiben erhalten. Der MQTT-Branch existierte
zum Prüfzeitpunkt im neuen Repository noch nicht; seine veraltete
Upstream-Verknüpfung wurde entfernt. Es wurde nichts gepusht oder gemergt.
Ein später ausdrücklich beauftragter Push kann die neue Upstream-Verknüpfung
mit `git push -u origin feat/mqtt-panel-telemetrie` anlegen.

## Dokumentation und Herkunft

Clone-Anleitungen, aktuelle Repository-Vorgaben und die Zielangaben der
CI-Verwaltungsanleitung beziehen sich auf das neue Repository. Bestehende
Issue-/PR-Nummern, CI-Lauf-Links und datierte Prüfbelege verweisen weiterhin auf
ihre ursprüngliche Quelle `davidheinrich73/smartcity-roboter`. Diese Belege und
die damaligen Rollen, Berechtigungen und Branchschutzangaben sind keine
Bestätigung des Zustands im neuen Repository. Alte Auftrags- und Branchangaben
vor ihrer erneuten Verwendung dort prüfen.

Die `$id` in `schemas/grundbetrieb-v1.schema.json` bleibt die Kennung des
bestehenden Vertrags. Der Repository-Wechsel allein erzeugt keine neue
Schema-Version. MQTT-Brokeradresse, Topics und Roboterkennungen hängen ebenfalls
nicht vom Git-Repositorynamen ab.

Die virtuelle Umgebung `.venv-mqtt` und der sichere Diagnoseaufruf bleiben nutzbar:

```powershell
.\.venv-mqtt\Scripts\python.exe mqtt/check_broker.py
```

Der Repository-Wechsel erfordert weder einen Panelstart noch einen Roboterlauf.
