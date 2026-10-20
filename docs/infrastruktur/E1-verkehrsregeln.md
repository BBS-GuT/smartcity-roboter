# E1 – Signale, Schilder und Gegenverkehr

Stand 20.10.2026 · Entwurf v0.1 · Status **offen**, sofern nicht ausdrücklich anders bezeichnet. Keine Geräte- oder Bewegungsfreigabe.

Quelle: Zieldefinition v1.0, Abschnitte 3 und 4.3. GB-05/08/09/11, A04/A07/A08/A10. Die folgenden Zufahrten sind **Konzept**, aus den dortigen Richtungspfeilen abgeleitet; reale Zufahrten, Montage und Regeln sind nicht bestätigt. Keine Tabelle ist eine freigegebene Straßenkarte.

Versionierung: v0.1 am 20.10.2026; nächste Version braucht Aufbau-ID, bestätigende Rollen/Personen, Datum und Änderungsbeleg. Bei abweichendem Aufbau neue Zufahrtzeilen ergänzen; keine stillschweigende Konzeptübernahme.

| Knoten | Konzept-Zufahrt aus | Konzept-Ausgänge (keine Manöverfreigabe) | Reale Zufahrt-ID / eigene Ampel / Haltelinie | Erlaubtes Manöver / Gelb / Ausfall | Beleg / Status |
|---|---|---|---|---|---|
| K1 | K2 | K3 | offen | offen / offen / offen | Konzept; reale Festlegung offen |
| K1 | K4 | K3 | offen | offen / offen / offen | Konzept; reale Festlegung offen |
| K2 | K6 | K1, K5 | offen | offen / offen / offen | Konzept; reale Festlegung offen |
| K3 | K1 | K7, K4 | offen | offen / offen / offen | Konzept; reale Festlegung offen |
| K3 | K4 | K7 | offen | offen / offen / offen | Konzept; reale Festlegung offen |
| K4 | K3 | K1, K5 | offen | offen / offen / offen | Konzept; reale Festlegung offen |
| K4 | K5 | K1, K3 | offen | offen / offen / offen | Konzept; reale Festlegung offen |
| K4 | K7 | K1, K3, K5 | offen | offen / offen / offen | Konzept; reale Festlegung offen |
| K5 | K4 | K8, K6 | offen | offen / offen / offen | Konzept; reale Festlegung offen |
| K5 | K6 | K8, K4 | offen | offen / offen / offen | Konzept; reale Festlegung offen |
| K5 | K2 | K8, K4, K6 | offen | offen / offen / offen | Konzept; reale Festlegung offen |
| K6 | K5 | K2 | offen | offen / offen / offen | Konzept; reale Festlegung offen |
| K6 | K8 | K2, K5 | offen | offen / offen / offen | Konzept; reale Festlegung offen |
| K7 | K3 | K8, K4 | offen | offen / offen / offen | Konzept; reale Festlegung offen |
| K8 | K7 | K6 | offen | offen / offen / offen | Konzept; reale Festlegung offen |
| K8 | K5 | K6 | offen | offen / offen / offen | Konzept; reale Festlegung offen |

U-Turns sind hier nicht als Konzept-Ausgänge aufgenommen. Signalwechsel beim bereits begonnenen Räumen von Einfahrtsfreigabe unterscheiden; STOPP/Hindernis- und Fehlerhalt bleiben wirksam. Verdecktes Rot oder unbekannte Freigabe erlaubt laut Zieldefinition keine Einfahrt. Konkrete Gelb-/Ausfallregel durch Ampelteam bestätigen lassen.

| Schild-ID / Art | Reale Lage / Zufahrt | Bedeutung / Halt / Wiederanfahrt / Wiedererkennung | Foto, Version, Datum / Partnerbestätigung | Status |
|---|---|---|---|---|
| Tatsächliche Schildliste offen | offen | offen; Stoppschild braucht tatsächlichen Stillstand und definierte Wartebedingung | offen | offen |

Weitere Zeilen je eingebautem Schild anlegen, auch Einbahn-/Vorfahrt-/Richtungsvorgaben; keine Detektorklasse als Beleg für Montage verwenden.

| Überweg | Tatsächlicher Ort / Querungsgrenzen | Figuren-/Objektregel / Annäherung / Freigabe | Beleg / Partner / Status |
|---|---|---|---|
| Z1 (vorläufige Kennung) | offen | offen | Spielfeld-/Ampelteam; offen |
| Z2 (vorläufige Kennung) | offen | offen | Spielfeld-/Ampelteam; offen |

Z1/Z2 sind noch auf einem Aufbauplan zu verorten. Querbalken sind keine zufälligen Kreuzungsoptionen. Geschwindigkeit und Beobachtungsgrenzen bleiben bis zu Messung/Festlegung offen.

## Offene Partnerentscheidung Gegenverkehr K3–K4–K5–K6

Vorschlag zur Abstimmung, nicht vereinbart: Konfliktbereich und sämtliche Einfahrten einschließlich K4 aus K7 und K5 aus K2 kartieren; eine Richtung erst freigeben, wenn die tatsächliche Räumung des zugehörigen Bereichs positiv nachgewiesen ist. Ganze Querstraße oder getrennte Abschnitte sind eine offene Partnerentscheidung. Benötigt werden Belegungs-/Räumungsquelle, sichere Zuordnung, Fehlererkennung und Verantwortlichkeit. Unbekannte Belegung, Ausfall, Stillstand oder Rückstau darf keine gegensätzliche Einfahrt freischalten. Keine ungeprüfte feste Durchfahrtszeit als Freigabenachweis.

Gemeinsamer späterer A10-Testplan: beide Richtungen und alle Einbieger, langsame Durchfahrt, Stillstand im Bereich, Rückstau an Ausfahrt, fehlerhafte/alte Belegung und Wiederanlauf prüfen. Erwartung: keine konfliktierende Freigabe bis bestätigter Räumung; Roboter wartet auf eigener Linie. Tatsächliche Freigaben, Belegungszustände und Räumzeitpunkte synchron protokollieren. Grenzen und Testfenster erst mit A/Orchestrator festlegen; hier keine Fahrt.

Kurze Klärungsliste für Ampel-/Spielfeldteam (über Carsten):

1. Welcher Aufbauplan und welche realen Zufahrt-/Signal-/Schildkennungen gelten, wer bestätigt sie?
2. Welche Manöver, Haltelinien, Gelb-/Ausfall- und beiden Überwegregeln gelten je Zufahrt?
3. Welcher Bereich wird verriegelt, wie wird seine Räumung einschließlich K4/K5, Stillstand und Rückstau nachgewiesen?
