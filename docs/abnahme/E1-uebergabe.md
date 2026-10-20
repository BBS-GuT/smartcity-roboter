# E1 – Nachweisstand und Übergabe

Stand 20.10.2026 · Entwurf v0.1 · Status **offen**, sofern nicht ausdrücklich anders bezeichnet. Keine Geräte- oder Bewegungsfreigabe.

Auftrag E1 / verantwortlicher Mensch: Carsten Haas (Koordination); ausführende Geräte-/Spielfeld-/Ampel-/Brokerpartner namentlich offen. Refs [#16](https://github.com/davidheinrich73/smartcity-roboter/issues/16). Status: vorbereiteter Teilstand, Erhebung und Partnerbestätigung ausstehend.

Basiscommit: `ca6d49d56cf9e034280c88df6780ee62e50dcbc9`, beim Klonen von origin/main am 20.10.2026 geprüft. Issue #16 am selben Tag aktuell gelesen (offen). Branch: `docs/gb-e1-geraete-infrastruktur`. Liefercommit und PR im Git-/PR-Nachweis; kein Abschluss von #16.

## Dateibesitz und Quellen

Bearbeitet: [RM02](../geraete/RM02.md), [RM03](../geraete/RM03.md), [RM04](../geraete/RM04.md), [Messplan](../infrastruktur/E1-messplan.md), [Verkehrsregeln](../infrastruktur/E1-verkehrsregeln.md), [Brokerzugang](../infrastruktur/E1-broker-datenzugang.md) und diese Übergabe.

Reserviert im Generalprüfchat: docs/geraete/RM01.md und docs/abnahme/generalpruefung-matrix.md. Keine konkurrierende RM01-Datei angelegt. Keine Produkt-/Konfigurations-/Auftragsdatei verändert. Keine AGENTS.md im Checkout oder bei der vorangehenden Workspace-Suche gefunden.

Quellen: E-Auftrag, gemeinsame Regeln/Register und Zieldefinition v1.0; historisches roboter.md; Repository-Prüfbericht 20.10.2026. Private Koordinations-/Reconciliationdateien unter C:\SmartCity\research am 20.10.2026 nur gelesen. Sie sind keine neuen Hardwaremessungen.

## Gesamtübersicht RM01–RM04 (kein Geräteprotokoll)

| Gerät | Nachweisstand am 20.10.2026 | Grenze / nächster Nachweis | Zuständige Rolle |
|---|---|---|---|
| RM01 | Beobachtet: reservierte uncommittete Notizen des Generalprüfchats in C:\SmartCity\pruefung\generalpruefung, gelesen etwa 10:38 Europe/Berlin. Carstens physische Zuordnung dort vorläufig dokumentiert. | MAC-Abgleich, vollständige Prozesse/Domains, Sensorbelege, installierter Stand und Abnahme offen. Keine Übernahme als freigegebenes Geräteinventar. | Generalprüfchat / Carsten / Orchestrator |
| RM02 | Historische Hinweise in roboter.md; kein aktueller E1-Gerätebeleg. | Alle aktuellen Identitäts-, Installations-, Laufzeit- und Sensorfelder offen. | Geräteteam / Carsten |
| RM03 | Historische Hinweise auf Rad-/Sensorproblem; aktuell ungeprüft. | Defektzustand und vollständige Inventur bestätigen. | Geräteteam / Carsten |
| RM04 | Kein aktueller Gerätebeleg. Historischer Zieldefinitionslink docs/rm04.md auf Basis nicht vorhanden. | Identität und vollständige Inventur; historischen Nachweis bei Bedarf durch O nachreichen. | Geräteteam / Orchestrator |

RM01-Notizen melden übertragenen Quellstand 834b71d, keine Installation/Startbestätigung. Domain 30 ist dort nur für Sitzung/untersuchte Joystickprozesse berichtet, nicht für sämtliche Komponenten. Momentaufnahmen sind keine Vollständigkeitsnachweise. Hier keine eigene SSH-Sitzung, Befragung zu laufenden RM01-Themen oder Geräteaktion.

## Offene Punkte und benötigte Übergaben

| Teil | Benötigter Nachweis / Entscheidung | Zuständige Rolle / Abhängigkeit |
|---|---|---|
| E1a | Physische Identität/MAC/Netz; installierter SHA samt Änderungen, Karten-/Konfigurations-/Kalibrierprüfsummen; sämtliche Startquellen/Domains/Motorpublisher; sichere Sensoraufnahmen mit Typ/Rate/Zeiten/Gültigkeit/Gerätezuordnung | Geräteteam; RM01 ausschließlich Generalprüfchat, Commitübergabe durch O |
| E1b | Bestätigter Feldbezug und Aufbauversion; vollständige Messblätter samt Einheit/Verfahren/Datum/Unsicherheit; Hülle und Sensorextrinsik je Gerät | Spielfeld-/Geräteteam; Parameterübergabe an A/B |
| E1c | Reale Zufahrten, Ampeln, Haltelinien, Schildliste und Z1/Z2; schriftliche Regeln; Gegenverkehrsbereich, Räumungsnachweis und Störfallverfahren inkl. K4/K5 | Ampel-/Spielfeldteam; O koordiniert, B übernimmt bestätigte Regelkarte |
| E1d | Broker/Transport/Port, sicherer Credentialbezug, Client-/Gerätekennungen, Datenformate/Frames/Raten/Größen, lesender Testzugang | Carsten + Brokerteam + C; C1 #14 weiterhin offen |

Gezielte RM01-Übergabefragen an O: Welcher prüfbare Commit liefert das inventarisierte Gerät und die Generalprüfmatrix? Welche physische MAC-Zuordnung und vollständigen Treiber-/Agent-/Motorquellen sind danach belegt? Welche Sensoraufnahmen enthalten Zeitbezug und Quellenidentität? Den laufenden USB-/Joystickbefund erst aus dieser Übergabe übernehmen.

An A: gemessene Hülle/Sensorlagen, Pflichtquellen und Alters-/Stoppgrenzen benötigen eine spätere bestätigte Übergabe. An B: bestätigte Zufahrts-/Regel-/Räumungskarte fehlt. An C: Broker- und Detaildatenfelder abstimmen; E1 setzt keinen eigenen öffentlichen Vertrag.

Historischer Softwarebefund vor PR #22 laut O-Review vom 20.10.2026 (aktueller Abgleich im Nachtrag unten): #13 Statuswiederkehr kann Wegräum-Sperre löschen und Armwunsch erzeugen; #19 Kartenreload/Reset und falsche Bestätigung; #20 Logrotation/Download. A1-Softwarefix ist erhalten, reale Abnahme fehlt. Nur Voraussetzungen dokumentiert, keine Fehlerbehebung und keine Bewegungsfreigabe aus Softwaretests. E2 braucht gesonderten Auftrag, geprüften Stand und betreutes Testfenster.

## Dokumentenprüfung und nächster Schritt

Relative Links der neuen Dateien, Tabellenbreiten, Datum-/Einheitenfelder, Status-/Quellenkennzeichnung, Dateigrenzen und Geheimnisfreiheit werden vor Lieferung geprüft; Ergebnis im PR. Keine Motor-, Arm-, Simulations- oder Produkttests für diesen Dokumentationsstand.

Nächster Schritt: Carsten liefert vorhandene Spielfeldmaße/Regelunterlagen und zuständige Partnerrollen; kompakte Frage im E1-Chat gestellt. Danach Messregister und reale Zuordnung gezielt ergänzen. O bestätigt die RM01-Commitübergabe und die Zuständigkeiten für die offenen Partnerentscheidungen. Keine Nachrichten an andere Chats oder Partner gesendet.

## Ergänzung aus Carstens Rückmeldung am 20.10.2026

Beobachtet (Nutzerangabe im E1-Chat): Spielfeld ungefähr 240 × 220 cm; Verfahren, Unsicherheit, Aufbau-ID und Messbestätigung offen. Vereinbart als Zuständigkeitsgrenze: Spielfeld/Ampeln werden von außen gesteuert, von Carsten als externe Steuerung mit MQTT berichtet; konkrete Anbindung/Zuständigkeit offen; verantwortliche Person/Team und konkretes Infrastrukturverfahren weiterhin offen. In Messplan und Verkehrsregeln aufgenommen.

Liefernachweis: Draft-PR [#23](https://github.com/davidheinrich73/smartcity-roboter/pull/23), erster Commit b7de4382e6532881fb7647a43c6a6b773c839096; Ergänzung im Folgecommit. Relative Links und Tabellenspalten aller sieben Dateien geprüft: keine Fehler; git-Diffprüfung fehlerfrei. Keine Geheimnisse aufgenommen. Nächster Informationsblock: vorhandener Aufbau-/Ampelplan oder Kontaktrolle für die externe Infrastruktursteuerung; noch keine zusätzliche Befragung gestartet.


## Software- und Umfangsnachtrag 20.10.2026, 11:02 Europe/Berlin

Beobachtet: origin/main nach erneutem Fetch auf `5309b20854e81a217996da8ebb903feebaa7f8eb` (Merge PR #22). Die Arbeitsbasis dieses E1-Branches bleibt der oben genannte ca6d49d; kein fremder Produktstand wurde in den Dokumentationsbranch übernommen. GitHub-Status bei der lesenden Abfrage: #19/#20 geschlossen, #13/#14 offen.

Berichtet durch Orchestrator-Review zu PR #23 am 20.10.2026: Kartenwechsel einschließlich Bestätigung (#19), Logdownload (#20) sowie bisherige B1-Statuswiederkehr-, Rot- und Wendefehler sind auf dem neuen Stand technisch nachgeprüft behoben. Dies ersetzt die oben historischen Fehlerhinweise als aktuellen Softwarestatus; keine eigene erneute Produktprüfung durch E1. Hardwareprüfungen und reale Abnahmen fehlen weiterhin.

C1 #14 ist wegen verbliebener Vertragslücken wieder geöffnet; kein akzeptierter Vertragscommit. Broker-/Detaildatenabstimmung bleibt davon abhängig.

Vereinbart laut übermittelter neuer Nutzerentscheidung: Wegräumen gehört ausdrücklich zum Grundbetrieb. Zieldefinition und Abnahmeumfang werden laut Carsten andernorts erweitert; E1 bearbeitet diese Dateien nicht parallel. Bestätigter Sicherheitsrest laut Orchestrator: Personen stoppen die Räumphasen `abstand` / `zurueck` noch nicht; ein separater kleiner Folgeauftrag wird angelegt (Kennung hier noch offen). Korrekturbeleg und anschließende reale Prüfung bleiben Voraussetzungen; keine Räum-/Arm-/Fahrfreigabe aus diesem Nachtrag. Geräteinventare und Messwerte bleiben unverändert offen.

Quelle dieses Nachtrags: Orchestrator-Nachricht in diesem E1-Chat; Remote-/Issue-Status zusätzlich lesend geprüft. Dokumentenprüfung nach Redaktion: relative Links und Tabellenspalten unverändert gültig, Git-Diffprüfung fehlerfrei. Keine Geräteaktion und kein Produktcode geändert.
