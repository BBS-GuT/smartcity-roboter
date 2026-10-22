# Automatische Merge-Freigabe nach Codex

Codex uebernimmt die Produktreviews. Seine native GitHub-Integration meldet
Befunde oder einen erfolgreichen Review. Fuer eine formale GitHub-Freigabe
uebertraegt der Workflow `Codex - Mergefreigabe` ein eindeutiges erfolgreiches
Ergebnis als eigene GitHub-App in `APPROVED`. Er fuehrt keine weitere
KI-Pruefung aus und merged keine Pull Requests.

## Voraussetzungen je Pull Request

- Offen, kein Draft und Zielbranch `main`.
- Ein echter Codex-Summary-Kommentar: Bot-ID, App und letzter Bearbeiter
  werden geprueft. Benutzerkommentare und ein Daumen reichen nicht.
- Code Review fuer exakt den aktuellen Commit: abgeschlossen, keine Befunde
  und keine ungeloesten Befunde. Die Selbsteinschaetzung des implementierenden
  Chats ersetzt diesen unabhaengigen nativen Code Review nicht.
- Ein zusaetzlicher Security Review ist dauerhaft optional. Sein fehlender,
  laufender, wartender, abgebrochener oder fehlgeschlagener Lauf blockiert
  allein nicht. Bekannte Befunde fuer den aktuellen Commit blockieren weiter;
  unbekannte oder fehlerhafte Statusformate werden weiterhin abgelehnt.
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

## Dauerhafter Arbeitsablauf (Entscheidung vom 21.10.2026)

Der normale Codex-Code-Review bleibt fuer jeden pruefbereiten PR und jeden
neuen Commit aktiv. Er prueft relevante Anforderungen, verbundene Komponenten,
Fehlerfaelle, Schnittstellen und Tests gemaess `AGENTS.md`. Nur konkrete Fehler
blockieren; Stilwuensche rechtfertigen keine kuerzere oder laengere Pflichtkette.
Die drei vorhandenen D1-Pflichtpruefungen bleiben unveraendert. Kleine fertige
PRs und gebuendelte Pushes vermeiden unnoetige Wiederholungen.

In den nativen Repository-Review-Einstellungen wird der allgemeine automatische
Security Review deaktiviert; gezielte Security Reviews bleiben bei Bedarf
moeglich. Insbesondere Zugangsdaten, Berechtigungen, CI-Ausfuehrung und externe
Erreichbarkeit brauchen eine gezielte Sicherheitsbetrachtung. Ein fehlgeschlagener
optionaler Scan ist kein bestandener Sicherheitsnachweis. Fuer einen bewusst
verpflichtenden Einzelfall unterstuetzt die Entscheidungsfunktion weiterhin
`require_security_review=True` (ein explizit aufzurufender strenger Modus).
Es gibt kein Ablaufdatum und keine automatische Rueckkehr zur bisherigen Regel.

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

Die installierte App `5409664` hat Contents **Read and write**, Pull requests
**Read and write** sowie Checks, Actions, Issues und Metadata **Read-only**.
Die Contents-Schreibberechtigung wurde ausdruecklich genehmigt und am
21.10.2026 fuer die Installation bestaetigt. Damit zaehlt die App als
schreibberechtigte Review-Autorin fuer die Pflichtfreigabe. Der konkrete
GitHub-Nachweis steht im Abschnitt zur Live-Abnahme; das erfolgreiche
Absenden eines `APPROVED`-Reviews allein belegt diese Anrechnung nicht.

Der tatsaechlich im Workflow ausgestellte App-Token bleibt ausdruecklich auf
`permission-contents: read` begrenzt. Diese Begrenzung in
`.github/workflows/codex-mergefreigabe.yml` bleibt erhalten. Die Anrechnung
der App-Freigabe mit Contents-Schreibrecht der Installation und weiterhin
lesendem Job-Token wurde am 21.10.2026 um 11:54 UTC nachgewiesen.

**Risikodelta:** Der private App-Schluessel kann nach der Rechteerweiterung auch
Contents-Schreibtoken ausstellen. Ein nur lesender Job-Token begrenzt den
aktuellen Workflow, nicht die grundsaetzliche Macht dieses Schluessels. Die
Erweiterung wurde deshalb ausdruecklich vom Nutzer genehmigt. Weitere
Rechteerweiterungen brauchen eine eigene Zustimmung. Admin-, Workflows-Schreibrechte und
Bypass-Ausnahmen werden nicht angefordert; der allgemeine Actions-Freigabeschalter
bleibt aus.

Der Schluessel liegt ausschliesslich in der Environment `codex-mergefreigabe`,
fuer die nur der Branch `main` zugelassen ist. Der normale `GITHUB_TOKEN` bleibt
im Freigabeworkflow lesend. Ein neuer App-Token gilt nur fuer dieses Repository
und wird nach dem Job wieder widerrufen. Persoenliche Zugriffstoken gehoeren
nicht in diesen Ablauf.

## Einmalige Aktivierung

1. Diesen Einrichtungs-PR nach gruenen Pruefungen und unabhaengiger Freigabe
   integrieren. Im vorhandenen `main`-Ruleset ist Codeowner-Freigabe bereits
   eingeschaltet. Eine Freigabe, das Verwerfen alter Freigaben, offene Threads
   und die drei D1-Pflichtpruefungen bleiben Pflicht. Keine Bypass-Ausnahme.
2. Eine Person mit passenden Organisationsrechten registriert unter
   [BBS-GuT: neue GitHub-App](https://github.com/organizations/BBS-GuT/settings/apps/new)
   eine private App, zum Beispiel `BBS-GuT Codex Freigabe`. Homepage ist dieses
   Repository, Webhook ausschalten, keine Benutzerrechte und keine Events.
   Repository permissions: Contents **Read and write**, Checks **Read-only**, Actions **Read-only**,
   Issues **Read-only**, Pull requests **Read and write**; Metadata bleibt
   automatisch lesend. Die Vorlage liegt unter
   `.github/codex-approval-app-manifest.json`.
3. Die App nur fuer `BBS-GuT/smartcity-roboter` installieren und einen privaten
   Schluessel erzeugen. Unter Settings > Environments > `codex-mergefreigabe`
   die numerische App-ID als Environment-Variable
   `BBS_CODEX_APPROVAL_APP_ID` und den PEM-Inhalt als Environment-Secret
   `BBS_CODEX_APPROVAL_APP_PRIVATE_KEY` hinterlegen. Kein Repository-Secret
   verwenden, keinen Schluessel im Chat oder Repository speichern.
4. Bei einer vorhandenen Installation die neue Contents-Berechtigung in den
   App-Einstellungen anfordern und durch die zustaendige Person fuer die
   Installation bestaetigen lassen. Ein Manifest-Commit oder erneuter
   Workflowstart aendert keine bereits genehmigte Installation. Vor dieser
   ausdruecklichen Freigabe keine Rechte aendern.
5. Den Workflow auf `main` starten und die untenstehende Live-Abnahme
   dokumentieren. Fuer die hier beschriebene Installation wurde die Anrechnung
   bereits erfolgreich nachgewiesen.

Ohne die App-Konfiguration meldet der Workflow den noch fehlenden Schritt
und gibt keinen PR frei. Der Schluessel wird erst mit erfolgreicher App-
Registrierung erzeugt; die Registrierung und Installation lassen sich nicht
mit dem vorhandenen Repository-Token ersetzen.

Trockenlauf mit einem Lesetoken, ohne Freigaben oder sonstige Schreibzugriffe:

```sh
GH_TOKEN=... python3 .github/scripts/codex_approve.py --pr 80
```

## Live-Abnahme der angerechneten Freigabe

Vor der Erweiterung hatte die Installation Contents-Lesezugriff: App-Reviews
waren zwar `APPROVED`, GitHub meldete aber `authorCanPushToRepository: false`
und `reviewDecision: REVIEW_REQUIRED`.

Am 21.10.2026 um 11:54 UTC war nach genehmigter Erweiterung der Installation
auf Contents-Schreibrecht bei unveraendert lesendem Job-Token nachgewiesen:

- [App-Freigabe von PR #97](https://github.com/BBS-GuT/smartcity-roboter/pull/97#pullrequestreview-5599108669)
  fuer exakt `a00cce67e2e14c51ecad240c775247e063a0f607`: Review `APPROVED`,
  `authorCanPushToRepository: true` und PR-Status `reviewDecision: APPROVED`.
- Auch PR #80 hatte `reviewDecision: APPROVED`. Der Freigabeworkflow auf
  `main` war im [Lauf 39593905480](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39593905480)
  erfolgreich; seine App-Token-Konfiguration blieb bei `permission-contents: read`.
- PR #54 hatte weiterhin `reviewDecision: REVIEW_REQUIRED` und keinen
  App-Review. Der Schutz der Steuerungsdateien bleibt erhalten.

PR #80 und #97 waren beim Nachweis noch `BEHIND`. Die angerechnete Freigabe
hebt diese native Sperre nicht auf; vor dem Merge bleibt die Aktualisierung
auf den aktuellen `main` erforderlich. Die folgenden Kriterien gelten auch
bei spaeteren Aenderungen der Einrichtung:

- Einen aktuellen Produkt-PR ohne Steuerungsdateien mit `main` abgleichen.
  Fuer exakt seinen aktuellen Head muessen nativer Codex-Code-Review und
  Pflicht-CI sauber abgeschlossen sein. Ein optionaler Security Review darf
  noch laufen; bekannte aktuelle Befunde bleiben blockierend.
- Der App-Review fuer exakt diesen Head muss `APPROVED` sein und in GraphQL
  `authorCanPushToRepository: true` melden. Zusaetzlich muss derselbe PR
  `reviewDecision: APPROVED` melden. Ein Review-Kommentar oder das erfolgreiche
  Absenden des Reviews reicht als Abnahme nicht.
- Den aktuellen Head, die App-Review-URL, die GraphQL-Werte und CI-Belege im
  Einrichtungsissue dokumentieren. Rueckstaendige Branches, offene Threads oder
  andere native Sperren werden nicht durch eine Rechteaenderung aufgehoben.
- PR #54 mit Steuerungsdateien bleibt von der automatischen Freigabe
  ausgeschlossen; die unabhaengige Codeowner-Freigabe bleibt erforderlich.
  Ein Draft-Status allein beweist den Schutz der Steuerungsdateien nicht.

Bei spaeteren Aenderungen an der Installation oder am Workflow ist die
Anrechnung erneut anhand dieser GitHub-Werte zu belegen. Den Job-Token nicht
stillschweigend auf Schreibzugriff erweitern und keine Schutzregel abschwaechen.

## Bedeutung fuer den Roboter

Eine von den Branchregeln angerechnete App-Freigabe und gruene CI erlauben die Softwareintegration. Fahr-,
LiDAR-, Brems- und Greifverhalten brauchen weiterhin die im jeweiligen Issue
festgelegten Geraetetests vor einer entsprechenden Freigabe am Roboter.

## Quellen

- [Codex-Code-Review und AGENTS.md](https://learn.chatgpt.com/docs/third-party/github)
- [GitHub: Workflow-Berechtigungen](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#how-permissions-are-calculated-for-a-workflow-job)
- [GitHub: Branchbeschraenkung fuer Environment-Secrets](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments#deployment-branches-and-tags)
- [Offizielle Action fuer kurzlebige App-Token](https://github.com/actions/create-github-app-token)
- [GitHub: erforderliche Freigaben von schreibberechtigten Reviewern](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#require-a-pull-request-before-merging)
- [GitHub: ein Review erstellen erfordert Pull-Requests-Schreibrecht](https://docs.github.com/en/rest/pulls/reviews#create-a-review-for-a-pull-request)
- [GitHub: zusaetzliche App-Rechte bestaetigen](https://docs.github.com/en/apps/using-github-apps/approving-updated-permissions-for-a-github-app)
