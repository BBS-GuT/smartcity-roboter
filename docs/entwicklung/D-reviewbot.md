# Codex-PR-Reviewer: Einrichtung und Betrieb

**Stand: 21.10.2026. Repository: `BBS-GuT/smartcity-roboter`. Der Reviewer ist aktiv; die kurzen Projektregeln werden mit [PR #54](https://github.com/BBS-GuT/smartcity-roboter/pull/54) geliefert.**

Fachliche Orientierung ist die [Zieldefinition](../zieldefinition-grundbetrieb.md). Die [Review-Regeln](../../AGENTS.md#code-review-rules) verweisen darauf und beschreiben, wie Änderungen geprüft und Befunde begründet werden.

**Vorläufiger Hinweis:** Wegräumen gehört gemäß der bestätigten Entscheidung in [Issue #8](https://github.com/BBS-GuT/smartcity-roboter/issues/8) zum Grundbetrieb. Die älteren Ausschlüsse in der Zieldefinition werden noch angepasst. Maßgeblich sind die Schutzbedingungen des erlaubten Räumens, insbesondere STOPP, Personen-/Tier-/Fahrzeughalt und gültige Pflichtsensoren; die Funktion wird nicht pauschal ausgeschlossen. Die Funktionsentscheidung ersetzt keine Geräteabnahme.

## Review verwenden

In den [Codex-Review-Einstellungen](https://chatgpt.com/settings/code-review) wird das verbundene BBS-Repository ausgewählt. `Automatic review` steuert die Automatik; für Team-PRs gibt es `All PRs` beziehungsweise `Follow personal preferences`. Bei letzterer Auswahl wirken die persönlichen Einstellungen mit. `Review trigger` bestimmt die Auslösung. Die aktuell gewählten Optionen sind in der angemeldeten Oberfläche sichtbar.

Ein Review lässt sich im PR mit `@codex review` anfordern. Die Bot-Zusammenfassung nennt Status, geprüften Commit und Auslöser. Sie wird bei weiteren Reviews fortgeschrieben; das Ergebnis muss deshalb zur gewünschten Commit-SHA passen. Eine manuelle Anforderung belegt keinen automatischen Start.

Die [offizielle OpenAI-Dokumentation](https://learn.chatgpt.com/docs/third-party/github) beschreibt Einrichtung, Auslösung und `AGENTS.md`-Regeln. Bei ausbleibender Reaktion sind Repositoryzugriff, Automatik, persönliche Einstellungen, Auslöser und angezeigte Nutzungslimits die ersten Prüfpunkte.

## Belegter Stand

| Bereich | Nachweis vom 21.10.2026 |
| --- | --- |
| Automatisch bei neuem prüfbereitem PR | [PR #57](https://github.com/BBS-GuT/smartcity-roboter/pull/57#issuecomment-6311814166): `PR opened`, Commit `ca791ca`, um 10:42 MESZ abgeschlossen, ohne Befunde und ohne manuellen Aufruf. |
| Manuelle Anforderung | [Anforderung an PR #78](https://github.com/BBS-GuT/smartcity-roboter/pull/78#issuecomment-6312470288) vom 21.10.2026, 11:18 MESZ: mit `@codex review` ausgelöst. Die [fortgeschriebene Bot-Zusammenfassung](https://github.com/BBS-GuT/smartcity-roboter/pull/78#issuecomment-6312475473) nennt `Manual request` und jeweils den zuletzt geprüften Commit. Das belegt keine automatische Auslösung. |
| Draft → Ready und neuer Push | Für diese Ereignisse liegt hier kein gesonderter, eindeutig zugeordneter Automatiknachweis vor. |
| Erkennungsqualität der kurzen Regeln | Noch nicht systematisch mit einer Regelverletzung, einem zulässigen Gegenfall und einer unabhängigen harmlosen Änderung geprüft. Die beobachteten Reviews belegen keine vollständige Fehlererkennung. |

Eine zusätzliche Testserie oder Änderung von Einstellungen und Kontingenten ist nicht Bestandteil dieses Dokumentationspakets.

## Grenzen

Codex prüft den PR-Diff mit relevantem Repositorykontext. `AGENTS.md` gibt zusätzliche Orientierung. Laut aktueller OpenAI-Dokumentation konzentrieren sich veröffentlichte GitHub-Befunde auf P0/P1. Ein fehlender Befund bestätigt keine Fehlerfreiheit. CI, erforderliche Freigaben und Branchschutz gelten weiterhin; Softwaretests sind keine Geräteabnahme.

## Historische Nachweise

- Die ursprüngliche Regelfassung entstand im Quellrepository `davidheinrich73/smartcity-roboter`: [PR #84](https://github.com/davidheinrich73/smartcity-roboter/pull/84), Regelcommit [c275f635](https://github.com/davidheinrich73/smartcity-roboter/commit/c275f635b5601add9beb57404c84dd4e4575fefc), Basis `c404a9335dc1aabf3b0a509aadbc017c64cd57cb`. Die damalige Prüfung von 29 lokalen Links/Ankern und drei Regelgruppen betrifft diese ursprüngliche Fassung. Die damaligen Schutzangaben betrafen das [Quell-Ruleset 25474694](https://github.com/davidheinrich73/smartcity-roboter/rules/25474694), nicht das BBS-Repository.
- Der BBS-Einrichtungsnachweis vom **21.10.2026, 10:48 MESZ**, dokumentiert das [BBS-Ruleset 25533179](https://github.com/BBS-GuT/smartcity-roboter/rules/25533179): eine unabhängige Approval, Verwerfen alter Approvals, erledigte Reviewgespräche, aktuelle Basis, drei D1-Pflichtchecks, Force-Push-/Löschsperre und keine Bypass-Ausnahmen. Diese Einstellungen wurden bei der Vorbereitung von PR #54 am 21.10.2026 erneut über die GitHub-API bestätigt. Eine tatsächlich andere berechtigte Reviewperson muss vor Merge zustimmen; ein weiterer Agent unter dem Autorenkonto ist keine unabhängige Approval. Zusammenfassung und Korrekturauftrag: [Issue #68](https://github.com/BBS-GuT/smartcity-roboter/issues/68).
- Der erste erfolgreiche [BBS-CI-Lauf 39571559910](https://github.com/BBS-GuT/smartcity-roboter/actions/runs/39571559910) bestand alle drei D1-Checks und 21/21 Softwaretestskripte. Er prüfte einen PR-Mergestand; er ist weder ein eigener `main`-Push-Lauf noch die CI des endgültigen Heads von PR #54. Die Probe-PRs #56/#57 wurden ohne Merge geschlossen und ihre temporären Branches separat entfernt. Das aktivierte automatische Löschen nach Merge wurde damit nicht praktisch nachgewiesen.
