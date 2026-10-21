# Automatische Merge-Freigabe nach Codex

Codex uebernimmt die Produktreviews. Seine native GitHub-Integration meldet
Befunde oder einen erfolgreichen Review. Fuer eine formale GitHub-Freigabe
uebertraegt der Workflow `Codex - Mergefreigabe` ein eindeutiges erfolgreiches
Ergebnis als eigene GitHub-App in `APPROVED`. Er fuehrt keine weitere
KI-Pruefung aus und merged keine Pull Requests. Die neue `AGENTS.md` wird
separat in PR #54 eingerichtet und hier nicht bearbeitet.

## Voraussetzungen je Pull Request

- Offen, kein Draft und Zielbranch `main`.
- Ein echter Codex-Summary-Kommentar: Bot-ID, App und letzter Bearbeiter
  werden geprueft. Benutzerkommentare und ein Daumen reichen nicht.
- Code Review fuer exakt den aktuellen Commit: abgeschlossen, keine Befunde
  und keine ungeloesten Befunde. Ein aktueller zusaetzlicher Security Review
  muss ebenfalls sauber abgeschlossen sein.
- Alle drei vorgeschriebenen D1-Pruefungen fuer diesen Commit erfolgreich.
- Keine offenen Review-Threads und keine noch gueltige Aenderungsanforderung.
- Keine Aenderung an `.github/`, `AGENTS.md`, `CODEOWNERS` oder
  `docs/entwicklung/D-reviewbot.md`. Solche Steuerungsdateien brauchen weiter
  eine unabhaengige Freigabe durch Carsten oder David.

Die Freigabe nennt den Commit. Neue Commits verwerfen alte Freigaben ueber
die Branchregel. Bei nachtraeglich ungueltigem Ergebnis nimmt der Workflow
nur seine eigenen Freigaben zurueck. Er verwirft keine fremden Reviews und
loest keine fremden Threads auf. Bestehende native Aenderungsanforderungen
werden nicht durch einen weiteren sauberen Bot-Kommentar aufgehoben.

Der Workflow liest PR-Metadaten per API und fuehrt ausschliesslich eigene
Skripte vom Defaultbranch aus. Bot-Kommentare und abgeschlossene D1-Laeufe
loesen ihn aus; ein periodischer Abgleich faengt verpasste Events ab.
Das interne Kommentarformat ist keine zugesicherte oeffentliche Codex-API:
Ein unbekanntes oder geaendertes Format sperrt die automatische Freigabe.

## Warum eine eigene App

Der allgemeine Actions-Schalter `Allow GitHub Actions to create and approve
pull requests` bleibt **aus**. Andernfalls koennte ein Workflow auf einem
beliebigen Entwicklungsbranch einen anderen PR freigeben. CODEOWNERS allein
verhindert die Ausfuehrung solcher Branch-Workflows nicht.

Die eigene App hat nur Lesezugriff auf Contents, Checks, Actions und Issues sowie
Schreibzugriff auf Pull Requests. Ihr Schluessel liegt ausschliesslich in
der Environment `codex-mergefreigabe`, fuer die nur der Branch `main`
zugelassen ist. Der normale `GITHUB_TOKEN` bleibt im Freigabeworkflow lesend.
Ein neuer App-Token gilt nur fuer dieses Repository und wird nach dem Job
wieder widerrufen. Persoenliche Zugriffstoken gehoeren nicht in diesen Ablauf.

## Einmalige Aktivierung

1. Diesen Einrichtungs-PR nach gruenen Pruefungen und unabhaengiger Freigabe
   integrieren. Im vorhandenen `main`-Ruleset ist Codeowner-Freigabe bereits
   eingeschaltet. Eine Freigabe, das Verwerfen alter Freigaben, offene Threads
   und die drei D1-Pflichtpruefungen bleiben Pflicht. Keine Bypass-Ausnahme.
2. Eine Person mit passenden Organisationsrechten registriert unter
   [BBS-GuT: neue GitHub-App](https://github.com/organizations/BBS-GuT/settings/apps/new)
   eine private App, zum Beispiel `BBS-GuT Codex Freigabe`. Homepage ist dieses
   Repository, Webhook ausschalten, keine Benutzerrechte und keine Events.
   Repository permissions: Contents **Read-only**, Checks **Read-only**, Actions **Read-only**,
   Issues **Read-only**, Pull requests **Read and write**; Metadata bleibt
   automatisch lesend. Die Vorlage liegt unter
   `.github/codex-approval-app-manifest.json`.
3. Die App nur fuer `BBS-GuT/smartcity-roboter` installieren und einen privaten
   Schluessel erzeugen. Unter Settings > Environments > `codex-mergefreigabe`
   die numerische App-ID als Environment-Variable
   `BBS_CODEX_APPROVAL_APP_ID` und den PEM-Inhalt als Environment-Secret
   `BBS_CODEX_APPROVAL_APP_PRIVATE_KEY` hinterlegen. Kein Repository-Secret
   verwenden, keinen Schluessel im Chat oder Repository speichern.
4. Den Workflow einmal manuell auf `main` starten. Ein sauberer Produkt-PR
   erhaelt eine formale App-Freigabe. Ein PR an den Steuerungsdateien bleibt
   fuer eine Person reserviert. Den Nachweis im Einrichtungs-PR dokumentieren.

Ohne die App-Konfiguration meldet der Workflow den noch fehlenden Schritt
und gibt keinen PR frei. Der Schluessel wird erst mit erfolgreicher App-
Registrierung erzeugt; die Registrierung und Installation lassen sich nicht
mit dem vorhandenen Repository-Token ersetzen.

Trockenlauf mit einem Lesetoken, ohne Freigaben oder sonstige Schreibzugriffe:

```sh
GH_TOKEN=... python3 .github/scripts/codex_approve.py --pr 80
```

## Bedeutung fuer den Roboter

Eine App-Freigabe und gruene CI erlauben die Softwareintegration. Fahr-,
LiDAR-, Brems- und Greifverhalten brauchen weiterhin die im jeweiligen Issue
festgelegten Geraetetests vor einer entsprechenden Freigabe am Roboter.

## Quellen

- [Codex-Code-Review und AGENTS.md](https://learn.chatgpt.com/docs/third-party/github)
- [GitHub: Workflow-Berechtigungen](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#how-permissions-are-calculated-for-a-workflow-job)
- [GitHub: Branchbeschraenkung fuer Environment-Secrets](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments#deployment-branches-and-tags)
- [Offizielle Action fuer kurzlebige App-Token](https://github.com/actions/create-github-app-token)
