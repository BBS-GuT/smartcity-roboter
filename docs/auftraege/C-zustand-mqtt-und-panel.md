# Entwicklungsauftrag C Zustandsvertrag MQTT und Panel

**Empfänger:** Weiterer Entwickler / eigener Entwicklungs-Chat. **Jetzt umzusetzen:** C1. **Branch:** `feat/gb-c1-zustandsvertrag`. **Zielbezug:** GB-12 bis GB-18; insbesondere A13/A14.

Du entwickelst am Team-Repository `https://github.com/davidheinrich73/smartcity-roboter`. Lies [gemeinsame Regeln](00-gemeinsame-regeln.md), [Register](README.md), Zieldefinition §5–8 und Prüfbericht. Die Aufträge liegen zunächst auf `codex/grundbetrieb` in PR #11. Arbeite in einer eigenen Kopie ab aktuellem `origin/main`. Du bist Integrationsbesitzer des einzigen gemeinsamen öffentlichen Zustands-/Fahrwunschvertrags.

## Auftrag C1

Liefere einen kleinen tatsächlich prüfbaren Vertrag als Grundlage der parallelen Entwicklung. In C1 noch keinen Gesamtumbau von Panel/KI/Motorweg und keinen Publisher-Platzhalter als erfülltes MQTT-Ziel ausgeben.

Erstelle:

- `docs/schnittstellen-grundbetrieb.md` mit Feldern, Typen, SI-Einheiten, Bedeutung, Gültigkeit, Versionierung und Produzent/Konsument;
- `schemas/grundbetrieb-v1.schema.json` für den gemeinsamen Zustandsdatensatz;
- `lib/grundbetrieb_vertrag.py` mit kleinen ROS-unabhängigen öffentlichen Datentypen beziehungsweise Bau-/Validierungsfunktionen und strenger JSON-Ausgabe;
- synthetische Beispiele unter `tests/fixtures/grundbetrieb/` und eigenständig ausführbare `tests/test_zustandsvertrag.py`.

## Zu definierende Übergaben

1. **Sensorqualität:** Geräte-/Quellenidentität, Aufnahmezeit, monotone Empfangszeit, Frame-/Messungskennung, Koordinatenbezug, Gültigkeit und Grund. Frei, unbekannt, ungültig, veraltet und fehlend sind fachlich verschieden.
2. **Fahrwunsch B → A:** Identität, Start-/Sequenzbezug, Gültigkeitsfrist, gewünschte Bewegung, gewähltes Manöver und fachliche Haltegründe. Ein Fahrwunsch enthält keine eigenständige endgültige Motorfreigabe.
3. **Freigabeergebnis A → Zustand:** Betriebszustand, bleibende STOPP-/Fehlersperre, alle wirksamen Gründe und endgültig ausgegebene Bewegung. Tatsächlich gemessene Bewegung mit eigener Quelle/Gültigkeit separat führen.
4. **Navigation/Wahrnehmung B → Zustand:** Abschnitt, Knoten/Zufahrt, Orientierungssicherheit, erlaubte/gewählte Ausfahrt, Manöverfortschritt, Spurqualität, eigene Signal-ID/Erkennung, Schilder/Überwege und Hindernisse.
5. **Zustand → Panel und MQTT:** Geräte-ID RM01–RM04, Startkennung, Sequenz, Schema-/Software-/Karten-/Konfigurationsversion, Erzeugungszeit/Synchronisationsstatus, Betriebs-/Sensor-/Kommunikationsdaten sowie eindeutig zugeordnete Bild-, Tiefen- und Scandetails.

Version und Startkennung gehören zur Interpretation jeder Sequenz. Änderungen von Betriebs-/Kommunikationszuständen benötigen einen neuen konsistenten Datensatz. Lokal ist monotone Altersprüfung vorgesehen; eine nicht synchronisierte geräteübergreifende Uhr wird sichtbar. Nicht verfügbare Zahlen sind `null` mit Status; JSON darf kein `NaN` oder Unendlich enthalten.

Brokerverbindung, angeforderte Veröffentlichung, tatsächlich bestätigte Sequenz und externer Empfang sind verschiedene Nachweise. Detailreferenzen enthalten Daten-/Framekennung, Format und Zeitbezug. Aus dem Vertrag dürfen keine ausschließlich im Panel verfügbaren fachlichen Quellen herausfallen. Noch offene Bildformate/Raten oder Brokerdaten nicht als vereinbart erfinden.

## Konkrete Beispiele und Bestehenskriterien

- Beispiele für Stillstand, TEST, Fahrt, gleichzeitig Rot plus Hindernis, ungültige/alte Sensorquelle sowie Brokerunterbrechung/Wiederverbindung.
- TEST kann einen Fahrwunsch zeigen, endgültige Motorausgabe und gemessene Bewegung bleiben eigenständig. Eine unbekannte Messung wird nicht zu gültiger Null.
- Neustart mit neuer Startkennung lässt eine neue Sequenz beginnen, ohne alte Daten als fortlaufend aktuell zu interpretieren. Daten verschiedener Geräte bleiben getrennt.
- Ungültige numerische Werte und strukturell unvollständige Pflichtdaten werden erkannt. Versions-/Einheiten-/Gültigkeitsregeln sind testbar.
- Panel und MQTT können dasselbe unveränderliche Zustandsobjekt mit identischer Geräte-/Start-/Sequenzkennung lesen. Keine zweite fachliche Entscheidung im Panel.
- Beispiel Brokerwiederverbindung: frischer Zustand, sichtbare ältere bestätigte Sequenz, unveränderte STOPP-Sperre und keine neue Motorfreigabe.
- Tests sind ohne ROS, Roboter und Projektbroker ausführbar. Abhängigkeiten minimal halten und mit D abstimmen; globale Requirements gehören nicht C.

Lieferung: Draft-PR mit Vertrag, Beispielen und Tests sowie einer kurzen Liste der von A/B zu prüfenden Adapterentscheidungen. C1 wird nach fachlichem Review als konkreter akzeptierter Commit festgehalten. Vorher keinen parallelen zweiten Vertrag akzeptieren und A/B nicht von einer nur privaten ungemergten Schnittstelle abhängig machen.

## Dateien und Grenzen

In C1 ausschließlich die genannten neuen Vertrags-/Beispiel-/Testdateien bearbeiten; optional `docs/entwicklung/C1-vertrag.md`. Noch keine Änderungen an `panel/*`, `ki/*`, `line_follower/*`, Geräteprofilen oder fremden Tests. Dadurch kann C1 parallel zu den A1/B1-Korrekturen entstehen.

## Folgeauftrag C2 erst nach Zuteilung

Auf akzeptiertem C1 den gemeinsamen Zustand bilden, Panel auf dessen Werte umstellen und tatsächliche nicht blockierende MQTT-Veröffentlichung entwickeln. A/B liefern ihre Adapter in ihren Dateien. Panel-START/TEST/STOPP wird mit A gemeinsam angebunden; C erzeugt keinen konkurrierenden finalen Motorpublisher.

MQTT braucht eindeutige Client-/Geräteidentität, begrenzte Warteschlangen, erkennbare Fehler und verworfene Daten, Brokerbestätigung, Frischeerkennung und frischen vollständigen Zustand nach Wiederverbindung. Lokale Steuerung und Panel bleiben bei Brokerausfall nutzbar; Reconnect verändert keine Motorfreigabe. Vereinbarte Detaildaten werden extern dekodiert und denselben Framekennungen zugeordnet. Projektbrokerdaten liefert E separat; ein lokaler Testbroker ist ein Softwaretest und keine Projektbrokerabnahme. MQTT-Fernfahrbefehle bleiben außerhalb des Grundbetriebs.
