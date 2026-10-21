# Hinweise für Agents

Fachliche Grundlage ist die Zieldefinition:
[Grundbetrieb](docs/zieldefinition-grundbetrieb.md).

## Code Review Rules

- Lies die für die Änderung relevanten Abschnitte der Zieldefinition.
  Prüfe auch Auswirkungen auf zusammenhängende Komponenten.
  Unterscheide Anforderungen, Vorschläge und offene Festlegungen.

- Melde konkrete Fehler, die der PR verursacht oder verschärft.
  Ein einzelner PR muss nicht die gesamte Zieldefinition umsetzen.

- Begründe Befunde kurz auf Deutsch: betroffene Codezeile,
  konkreter Auslöser und fehlerhafte Wirkung.
  Konzentriere dich auf Funktion und Sicherheit.

- Prüfe bei verändertem Verhalten die passenden Tests.
  Unterscheide bestandene Softwaretests und reale Geräteabnahme.

## Offener Abgleich

Wegräumen gehört gemäß der bestätigten Entscheidung in Issue #8
zum Grundbetrieb. Die älteren Ausschlüsse in der Zieldefinition
werden noch angepasst. Prüfe die Schutzbedingungen des Räumens;
beanstande die Funktion nicht pauschal.
