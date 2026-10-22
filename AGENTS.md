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

- Der native Codex-Code-Review ist die unabhängige zweite Prüfung vor
  dem Merge. Eine Selbsteinschätzung des implementierenden Chats ersetzt
  ihn nicht. Prüfe den aktuellen Diff und die betroffenen Aufrufpfade,
  Schnittstellen, Fehlerfälle und Regressionen; reine Stilwünsche sind
  keine blockierenden Fehler. Fehlende Tests für einen konkreten Fehlerfall
  dürfen als Befund benannt werden. Zeitdruck reduziert die Prüftiefe nicht.

- Ein zusätzlicher Security Review ist keine allgemeine Merge-Pflicht.
  Bei Änderungen an Zugangsdaten, Berechtigungen, CI-Ausführung oder
  externer Erreichbarkeit prüfe die Sicherheitsfolgen gezielt und fordere
  bei Bedarf einen separaten Security Review an. Bekannte konkrete Befunde
  bleiben zu beheben; laufende optionale Scans allein blockieren nicht.

## Offener Abgleich

Wegräumen gehört gemäß der bestätigten Entscheidung in Issue #8
zum Grundbetrieb. Die älteren Ausschlüsse in der Zieldefinition
werden noch angepasst. Prüfe die Schutzbedingungen des Räumens;
beanstande die Funktion nicht pauschal.
