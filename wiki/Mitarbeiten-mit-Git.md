# Mitarbeiten mit Git

Einstieg für neue Teammitglieder. Die **verbindlichen Regeln** stehen in [`CONTRIBUTING.md`](https://github.com/BBS-GuT/smartcity-roboter/blob/main/CONTRIBUTING.md) und den [gemeinsamen Regeln](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/auftraege/00-gemeinsame-regeln.md). Diese Seite erklärt nur das Handwerk.

## Begriffe

| Begriff | Bedeutung |
|---|---|
| **Repository** | Projektordner mit der ganzen Änderungsgeschichte. Unseres: `BBS-GuT/smartcity-roboter`. |
| **Commit** | Eine gespeicherte Änderung mit Beschreibung (bei uns auf Deutsch). |
| **Branch** | Eigener Entwicklungszweig. `main` ist der gemeinsame Stand. |
| **Pull Request (PR)** | Bitte, einen Branch nach `main` zu übernehmen. Dort wird geprüft und diskutiert. |
| **Draft-PR** | PR im Entwurf: zeigt, woran man arbeitet, ist aber noch nicht zur Übernahme bereit. |
| **Merge** | Einen Branch in einen anderen übernehmen. |

## Ablauf

```bash
git clone https://github.com/BBS-GuT/smartcity-roboter.git
cd smartcity-roboter
git fetch origin
git switch -c fix/gb-mein-thema origin/main   # eigener Branch vom aktuellen main
# ... ändern ...
git status                                    # was ist geändert?
git add <dateien>
git commit -m "Linienfolger: Bildalter als Haltegrund anzeigen"
git push -u origin fix/gb-mein-thema
```

Dann auf GitHub einen **Draft-PR nach `main`** öffnen. Die Vorlage fragt nach Problem, Dateien, Tests und offenen Prüfungen.

## Regeln in Kürze

- **Vorher schauen, wer woran arbeitet:** offene Pull Requests und Drafts auf GitHub sowie das [Auftragsregister](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/auftraege/README.md) mit den Dateireservierungen. Keine Datei umbauen, an der gerade ein anderer PR arbeitet, ohne Absprache.
- Ein Thema pro PR, kleine Commits.
- `main` ist geschützt: Übernahme nur per PR, mit grünen Checks und Freigabe einer **anderen** Person. Kein Force-Push auf `main`.
- Vor dem PR die Tests laufen lassen ([Testen ohne Roboter](Testen-ohne-Roboter)). Tests nicht abschwächen, um grün zu werden.
- **Keine Passwörter, Tokens oder Brokerzugänge** ins Repository, in PRs oder Logs.
- Eigene Einstellungen eines Roboters gehören nach `config/lokal/`, nicht ins Repository.

## Branch-Namen

| Präfix | Wofür | CI bei Push? |
|---|---|---|
| `fix/gb-…` | Fehler beheben | ja |
| `feat/gb-…` | neue Funktion | nur über den PR |
| `chore/gb-…`, `test/gb-…` | Infrastruktur, Tests | ja |
| `docs/…` | Dokumentation | nur über den PR |

## Wiki bearbeiten

Das Wiki wird aus dem Ordner `wiki/` im Repository erzeugt. Also: Datei in `wiki/` ändern oder neu anlegen, per PR nach `main`. Nach dem Merge aktualisiert der Workflow „Wiki abgleichen“ das Wiki. Seitenname = Dateiname ohne `.md`, Bindestriche werden im Wiki als Leerzeichen angezeigt. Links zwischen Wiki-Seiten schreibt man ohne `.md`: `[Glossar](Glossar)`. Das Problemprotokoll ist die Ausnahme: Es liegt in `docs/problemprotokoll.md` und wird von dort ins Wiki kopiert.
