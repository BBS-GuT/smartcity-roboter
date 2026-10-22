# C1: Fachlicher Abgleich B – Entscheidung und Navigation

Stand: 22.10.2026. Verantwortlicher Mensch: Carsten; Ausarbeitung durch den
beauftragten B-Fachchat unter dem C1-Manager. Refs
[#3](https://github.com/BBS-GuT/smartcity-roboter/issues/3),
[#134](https://github.com/BBS-GuT/smartcity-roboter/pull/134).
**Erste fachliche Entscheidung zur Implementierungsgrundlage, keine Annahme
eines implementierten Gesamtvertrags und keine Zustimmung anderer Rollen.**

## Konkrete Bezugsstände und Umfang

Eigene Basis: `e8863f6998391c9a3d9cc30af2711eb4d7c86a51`, tatsächlicher
`origin/feat/gb-c1-zustandsvertrag` beim Klonen. Eigener Branch
`docs/c1-abgleich-b`, eigene Arbeitskopie
`C:\SmartCity\entwicklung\bbs-c1-abgleich-b-20261022`.
Exklusiv zugeteilt und geändert: nur diese neue Datei.

| Fachlicher Bezug | Am 22.10. erneut abgefragter Head | Status beim Abgleich |
|---|---|---|
| [Entscheidungsvorlage #142](https://github.com/BBS-GuT/smartcity-roboter/blob/f42202799396e5b71f378909eaf3a5863ef1e93f/docs/entwicklung/C1-vertragsentscheidungen.md) | `f42202799396e5b71f378909eaf3a5863ef1e93f` | Offen; V1–V4 einschließlich V1a und sechs Folgeaufträge |
| [C1e #130](https://github.com/BBS-GuT/smartcity-roboter/blob/ff4c0d78beee1eeae40fdd0597d0c32c0fc7e644/docs/entwicklung/C1e-detailreferenzen.md) | `ff4c0d78beee1eeae40fdd0597d0c32c0fc7e644` | Offen, nicht übernommen |
| [C1f #132](https://github.com/BBS-GuT/smartcity-roboter/pull/132) | `e1d6185e6878a304afa2681285be20342339e468` | Als Entwurf im Sammelbranch integriert |
| [C1g #131](https://github.com/BBS-GuT/smartcity-roboter/pull/131) | `3a8b81bc3e06eaceb77c3628aee874ee7d069197` | Als Entwurf im Sammelbranch integriert |
| [C1h #128](https://github.com/BBS-GuT/smartcity-roboter/pull/128) | `46cd940b973fd55c92d9ccff75bcbf12ff26f097` | Als Entwurf im Sammelbranch integriert |

Gelesen: AGENTS/CONTRIBUTING, [gemeinsame Regeln](../auftraege/00-gemeinsame-regeln.md),
[Register](../auftraege/README.md), [C1-Auftrag](../auftraege/C-zustand-mqtt-und-panel.md),
[Entwicklungsplan](../zusammenarbeit-und-entwicklung.md),
[Zieldefinition v1.0](../zieldefinition-grundbetrieb.md), #3, #11–#18 und
[#8](https://github.com/BBS-GuT/smartcity-roboter/issues/8).
Bezüge: GB-05–07, GB-12–18, A06/A11–15; keine Abnahme dieser Anforderungen.
Die aktuellen Vorgaben zu Sammelbranch und nur einem main-PR ersetzen die
historischen main-Startanweisungen. #134 ist auf obigem Sammelhead weiter Draft.

## V1/V1a und V4: B nimmt Herkunft, Zeitpfad und Version an

B nimmt die getrennten Identitäten aus V1 an: Cs `boot_id`/`seq` beschreiben
Zustandsausgaben; B liefert eigene `producer_id`, `producer_boot_id` und
Request-/Historiensequenzen. Sensor-, Objekt- und Armproduzenten dürfen andere
Starts haben. Gleiche Textkennungen allein beweisen keine bestätigte Bindung.
Damit bleibt ein Wunsch auch ohne Zustand zuordenbar und ein C-Neustart
erzeugt keine neuen Ursprungsdaten. Bis C den B-Inhalt erneut übernommen hat,
ist er fehlend; C darf weder gültig leere Historie noch neue Beobachtung erfinden.

B nimmt V1a ausdrücklich als inkompatiblen öffentlichen Vorschlag an:
JSON-Zahlen in Sekunden auf dem exakten ns-Raster, Bereich
0 bis 9223372036.854775807 s; direkter Bau mit Integer-Sekunden oder exakten
Decimal-Sekunden, ns-Bauhelfer, JSON-Lesen ohne vorgeschaltete Floatkonvertierung,
exaktes Schreiben numerischer Tokens und ganzzahlige Fristvergleiche.
Bool, direkte Zeitfloats, Rundung und Epsilon sind ausgeschlossen.
Das Raster behauptet keine reale Sensorauflösung. Eine Frist ist bei
`now == valid_until_mono_s` abgelaufen; C-Ausgabe und Wiederempfang verlängern sie
nicht. UTC und Synchronisationsqualität bleiben eigenständig; Uhrtyp, Ursprung,
Suspendverhalten und reale Sensorzeitabbildung sind nachzuweisen.

B nimmt dafür gemeinsame Version **2.0**, neues v2-Schema und Ablehnung von
v1/unbekannten Versionen im aktiven Pfad an. Wunsch-`contract_version` entspricht
Zustands-`schema_version`. Altdaten erhalten keine erfundene Herkunft, Frist
oder Historie durch Migration. Schema prüft Struktur; bestätigte Bindung,
historisches Register und gegebenes `now` erfordern kontextuelle Prüfung.
Diese Zustimmung ersetzt weder C/A/O-Entscheidung noch funktionalen Nachweis.

## V2: Fahrwunsch und historischer Detailbezug

B nimmt die 13 C1f-Felder an: `contract_version`, `robot_id`, `producer_id`,
`producer_boot_id`, `request_seq`, `request_id`, `time_basis_id`,
`generated_mono_s`, `valid_until_mono_s`, `v_m_s`, `w_rad_s`, `maneuver`,
`hold_reasons`. `motion.request = null` bedeutet kein verfügbarer Wunsch.
Separater und eingebetteter Wunsch haben identischen Inhalt. Neue Wünsche
erhöhen `request_seq`, Lücken sind zulässig, Umlauf oder Reset im selben Start
nicht. `request_id` liefert keine versteckte Herkunft. Ein wiederholter Wunsch
startet kein Manöver neu; die ausgewählte Ausfahrt bleibt B-seitig bis zur
bestätigten Beendigung gebunden, unabhängig von neuen Zustandsframes.

V2s separater Anti-Replay-Höchststand wird ausdrücklich angenommen: eine
ansonsten gültige, gebundene, aber abgelaufene höhere Sequenz überholt ältere
Wünsche. Beispiel aus #142: 8 → abgelaufene 10 → noch frische 9 lässt 9 gesperrt.
Ungültige hohe Sequenzen vergiften den Höchststand nicht. Erzeugungszeiten dürfen
bei höherer Sequenz nicht zurücklaufen. Duplikate ändern weder Inhalt noch Frist;
gleicher Schlüssel mit anderem Inhalt ist ein Widerspruch. Nach Ablauf bleiben
Höchststand und Annahmepaar erhalten. A-Neustart/verlorener Annahmekontext verlangt
neue Bindung und anschließend erzeugten Wunsch (`generated > bind_mono_s`).
Bestätigter B-Startwechsel sperrt den alten Start; C-Neustart ändert diese
Zuordnung nicht. Dies bestimmt Datenverwendbarkeit, keine Motorfreigabe.

B nimmt C1es Frame-/Datenschlüssel und historische Registrierung an. Nötig sind
Gerät, `sensors`-Schlüssel, technische Quelle, Produzent/Start, Frame,
Kanal/Datenkennung, unveränderliche Aufnahmezeit/Uhr und Format; `coord_frame`
ist räumlicher Bezug, keine Aufnahme-ID. Nur `state_boot_id` darf beim erneuten
Referenzieren auf Cs neuen Ausgabekontext wechseln. Ein älterer registrierter
Frame kann mit explizitem Altersbudget gültig sein, obwohl der Sensor bereits
einen neueren Frame meldet. Ohne damaligen Registerbeleg bleibt die Zuordnung
`unknown`; widersprüchliche Metadaten oder fremde Uhr sind `invalid`.
Ein gültiger alter Beleg bestätigt keine aktuelle Sensorverfügbarkeit.
Farbe/Tiefe brauchen einen ausdrücklichen Paarungsbeleg, nicht bloß gleiche IDs.

Enge Ergänzung für Auftrag 2: Register-/Altersgrenzen als zwingenden gegebenen
Prüfkontext ausweisen; fehlt ein Altersbudget, Frische `unknown` mit Grund
`age_budget_unknown`, kein erfundener Standard. Verdrängte Metadaten erlauben
keine Wiederverwendung der Kennung. Reale Formate, Budgets und Speicherlimits
werden später vereinbart; sie sind keine Voraussetzung, fehlende Belege ehrlich
zu zeigen. Optionaler fehlender Detailabruf entwertet nicht automatisch eine
anderweitig bestätigte Fahrt; ein widersprüchlicher Abschlussbeleg erfordert
dagegen erneute B-Bewertung und darf nicht als gesicherter Abschluss erscheinen.

## V3: B entscheidet den 16er-Puffer und seine Resetregeln

B nimmt **maximal 16 bestätigte gerichtete Abschlüsse vollständig im Zustand**
an. Das ist ein Datenlimit, kein Nachweis ausreichender B2-Wegwahl oder einer
gemessenen Gerätegrenze. Optionale Bild-/Scanbelege bleiben referenzierte Details.

| Feld/Regel für `route.history` | B-Entscheidung und Begründung |
|---|---|
| Herkunft | `producer_id`, `producer_boot_id`, `time_basis_id`; Gerät und `map_version` aus Zustand. Eintragsschlüssel zusätzlich `entry_seq`. Historienproduzent wird nicht als Sensor erfunden. |
| Eintrag | `section`, `node`, `approach_from`, `exit_to`, `entry_seq`, `confirmed_mono_s` aus C1g. Abschnitt endet am Knoten, Zufahrt gehört zum Abschnitt, Ausfahrt ist dort tatsächlich bestätigt. Alle Kennungen müssen im gegebenen gerichteten Kartenkontext zusammenpassen. Der ausgehende Abschnitt zählt erst nach seinem eigenen Abschluss als befahren. |
| Bestätigung | Abschnitt und anschließendes Manöver erst nach bestätigtem Abschluss gemeinsam eintragen. Wunsch, Timer, Sollbewegung oder wiederholter Frame reichen nicht. Aufnahmezeit eines Belegs und `confirmed_mono_s` bleiben verschieden. |
| Reihenfolge | Ältester zuerst; `entry_seq` streng steigend, Zeiten nicht abnehmend und nicht nach Zustandserzeugung bei gleicher bestätigter Uhr. Keine Neunummerierung durch C oder Verwerfung; doppelte Übertragung fügt keinen Abschluss hinzu. |
| Kapazität | Beim 17. Abschluss fällt der älteste weg; `dropped_entries` zählt nur Kapazitätsverwerfungen seit Historienstart. Der verbleibende Ausschnitt bleibt `valid`. Beispiel: Sequenzen 0…16 erzeugen den Puffer 1…16 mit Zähler 1. |
| Gültig leer | Nur nach belegter B-Initialisierung: `status=valid`, `reason=null`, `entries=[]`, `dropped_entries=0`. Kein Nachweis früherer Stillstandszeit. |
| Fehlend | `status=missing`, Grund `history_unavailable`, `entries=null`, `dropped_entries=null`; unbekannte Herkunftsfelder ebenfalls `null`. Fehlender C-Übernahmestand ist kein B-Reset. |
| Erfassungslücke | `status=invalid`, Grund `capture_gap`, Nutzwerte `null`; keine Umdeutung als Kapazitätsverlust. Darstellbar bleibt die bekannte Produzentenidentität. Wiederholt gesendeter alter Puffer repariert die Lücke nicht. |
| Reset | Nur bestätigter neuer Historienproduzentenstart initialisiert Puffer/Zähler/Eintragssequenz neu. B-Prozessneustart bei gleicher Geräteuhr ändert deren Kennung nicht. STOPP, TEST, Reconnect und reiner C-Neustart setzen nichts zurück. |
| Karte/Uhr | Kartenwechsel erfordert neuen Historienproduzentenstart; bis dahin `invalid` mit `map_changed`. Keine alten Einträge unter neuer Karte. Fremde Uhr: `invalid`, `timebase_mismatch`; keine Subtraktion über Uhrenräume. |

Enge Ergänzung für Auftrag 4: Nach `capture_gap` bleibt der laufende Start
ungültig, bis B einen neuen, ausdrücklich kenntlichen Historienstart initialisiert.
Dieser beginnt eine neue Beobachtungsperiode und behauptet keine rekonstruierte
Vergangenheit. C kann keinen solchen Start selbst erfinden. Diese Regel verhindert,
dass ein geleerter Puffer einen Erfassungsausfall verdeckt. Fehlende/ungültige
Historie liefert keine daraus abgeleitete Streckenbevorzugung; konkrete Wegwahl
und Haltebedingungen bleiben B2/A vorbehalten. C1 erhält synthetischen Kartenkontext;
reale Kartenkennungen und Erkennungs-/Abschlusskriterien sind B2-Nachweise.

## V3: Räumen und Arm – konkrete B-Datenbelegung

Die folgenden Tabellen dokumentieren den B-Eingangsvorschlag. Für die spätere
öffentliche Auftrag-5-Belegung gilt die unten ausdrücklich angenommene
V3a-Konsolidierung auf `a4c16698ecca19b04a86636783a7ca3c2d26a4ff` vorrangig,
einschließlich ihrer vollständigen Referenz-/Qualitätsobjekte. Frühere
Kurzbezeichnungen hier sind keine zusätzliche konkurrierende Schnittstelle.

B nimmt die getrennten V3-Bereiche an. Für Auftrag 5 schlägt B folgende enge
Feld-/Codebelegung zur gemeinsamen Annahme durch A/C/O vor; sie ist keine neue
Ablaufsteuerung. Jeder Qualitätsblock hat `status` und `reason`; bei fehlenden
Werten bleiben Nutzwerte `null`, bekannte Identitäten bleiben sichtbar.

| Bereich | Konkrete Belegung für den Folgeauftrag |
|---|---|
| `clearing` | `producer_id`, `producer_boot_id`, `operation_id`, `time_basis_id`, `started_mono_s`, `updated_mono_s`, `phase`, `execution_status`, `result`, `abort_reason`, `object_ref`, `status`, `reason`. |
| Phasen/Codes | `phase`: `inaktiv`, `anschauen`, `ausrichten`, `greifen`, `ablegen`, `nachpruefen`, `fahrstellung_bestaetigen`, `beendet`; `execution_status`: `laufend`, `pausiert`, `beendet`; `result`: `offen`, `erfolgreich`, `nicht_raeumbar`, `abgebrochen`. Für inaktiv ohne Vorgang gilt die vollständige Feldbelegung unten; bekannte Produzenten-/Uhridentitäten bleiben erhalten. |
| Unterbrechung | Zusätzlich `interruption_reason`/`interrupted_mono_s`; bei Pause beide erforderlich, sonst `null`. Phase und Objekt bleiben erhalten, Ergebnis `offen`. Abbruch ist `execution_status=beendet`, `result=abgebrochen` mit nichtleerem `abort_reason`; außerhalb Abbruch ist dieser `null`. Gründe z. B. `person_hold`, `stop`, `object_lost`, `sensor_unavailable`, `actuator_error`, `limit_unproven`. Codes beschreiben gemeldete Ursachen, keine neue Schutzentscheidung. |
| Ergebnis | `erfolgreich` nur bei beendeter Ausführung mit getrennten `verification_ref` (bestätigte Fahrbereichsnachprüfung) und `travel_pose_ref` (bestätigte Fahrstellung), jeweils `valid` mit historischem Bezug auf diesen Vorgang. `nicht_raeumbar` ist beendet mit nichtleerem `result_reason`; außerhalb dieses Ergebnisses ist `result_reason=null`. Qualitäts-`reason` bleibt davon getrennt. Ein gesendeter Greifauftrag oder Timer begründet keinen Erfolg. C1 prüft Referenzkonsistenz; B liefert fachliche Bestätigung, deren reale Kriterien bleiben offen. |
| Objekt | `object_ref`: Gerät, Objektproduzent/Start, `object_id`. `observation`: tatsächlicher Quellen-/Frame-/Detailbezug, Klasse/Qualität, Lage/Geometrie in m/rad mit `coord_frame` und Kalibrierbezug. `estimate` separat: ursprüngliche `observation_ref`, Odometriequelle/Start/Uhr, Schätzzeit, Lage, Unsicherheit samt Qualität. Fehlende Unsicherheit bleibt unbekannt. Schätzung erneuert niemals die Aufnahmezeit. |
| Armziel | `arm.request`: eigene Produzentenidentität, `command_seq`, Erzeugung/Ablauf/Uhr, `operation_ref`, `object_ref`, `action`, `target` samt Einheit/Koordinatenbezug/Qualität. `arm.output` referenziert tatsächlich ausgegebenen Auftrag; `ack` separat mit Zeit/Status. Empfang bestätigt keine erreichte Stellung. |
| Messung/Freigabe | `arm.measured` und `camera_pose` führen echte Quelle, Frame/Messungskennung, Aufnahmezeit/Uhr, Einheit und Kalibrierbezug. Ohne Messung Nutzwerte `null`. Fahrt-/Armfreigabe getrennt mit Besitzer, Request-/Commandreferenz, Prüfzeit, Ergebnis/Gründen; fehlendes Ergebnis `unknown`. Wunsch, Phase und Parameter ersetzen keine Freigabe. |
| Politik/Sperren | `protection` mit `policy_id`, `policy_version`, `evidence_ref`, `status`, `reason`; bei fehlendem Beleg `unknown`, unbekannte Werte `null`. Pflichtquellenreferenz separat. Sperrliste mit `code`, Herkunft, Zeit/Uhr, Qualität; konsolidiert nach V3a ausschließlich `effect=motion/arm/both`, kein paralleles `scope`-Feld. Mehrere Ursachen bleiben gleichzeitig erhalten. |

Für einen **gültig inaktiven** B-Räumzustand muss B initialisiert und seine
Produzenten-/Uhrbindung belegt sein. Ohne diesen Beleg bleibt die Qualität
fehlend oder unbekannt mit Grund; C darf keine gültige Inaktivität erfinden.
Die folgende Belegung ist innerhalb des Räumblocks vollständig für die
benannten bedingten Felder; sie lässt die allgemeinen Pause-/Abbruch-/
Ergebnisregeln oben unverändert gelten:

| Felder im inaktiven Räumblock | Verbindliche Belegung |
|---|---|
| `producer_id`, `producer_boot_id`, `time_basis_id` | Bekannte, gebundene Identitäten erhalten; bei gültiger Inaktivität nicht `null`. |
| `phase`, `execution_status`, `result` | `inaktiv`, `beendet`, `offen`. Kein aktiver, pausierter oder erfolgreich abgeschlossener Vorgang wird behauptet. |
| `status`, `reason` | `valid`, `null` bei belegter Initialisierung und Bindung. Qualitätsgrund ist kein Ergebnis-/Abbruchgrund. |
| `operation_id`, `started_mono_s`, `updated_mono_s`, `object_ref` | Jeweils `null`: kein aktueller Vorgang und daher keine Vorgangszeiten oder Objektzuordnung. |
| `abort_reason`, `interruption_reason`, `interrupted_mono_s`, `result_reason` | Jeweils `null`: weder Abbruch noch Pause noch Ergebnis `nicht_raeumbar`. |
| `verification_ref`, `travel_pose_ref` | Jeweils `null`: keine Erfolgsnachweise für einen aktuellen Räumvorgang. |
| Vorgangsbezogene `observation`, `estimate` | Jeweils `null`, weil kein aktuelles Räumobjekt zugeordnet ist. Frühere Vorgangsdiagnosen bleiben bei ihrer alten Identität, statt hier als aktuell zu erscheinen. |

Beim Übergang von einem Räumvorgang zu gültigem `phase=inaktiv` gilt zusätzlich
**`arm.request=null`**. Der vorherige Vorgangs-/Objektbezug ist nicht mehr aktuell;
eine noch offene `valid_until_mono_s` erhält den alten Armwunsch nicht als
verwendbaren aktuellen Wunsch. Diese Nullregel gilt bereits im ersten inaktiven
Zustand. Ein späterer neuer Vorgang benötigt einen neuen, ihm zugeordneten
Armwunsch mit eigener neuer `command_seq`; der alte Wunsch wird weder neu
zugeordnet noch durch Zustandsausgabe oder Fristrest reaktiviert.

Diese Inaktivitätsregel setzt keine unabhängig gemeldete `arm.measured`,
`camera_pose`, Schutzpolitik oder Sperrliste zurück. Historische `arm.output`
und `ack` dürfen mit ursprünglichem Command-/Vorgangsbezug und Zeit/Qualität
sichtbar bleiben; sie sind keine aktuellen Wünsche. Bereits gemeldete Freigaben
bleiben ebenfalls ihrem geprüften Command-/Vorgangsbezug zugeordnet und können
ohne aktuellen Wunsch keine aktuelle Armfreigabe darstellen. Die Nullregel
bestätigt weder Stornierung eines ausgegebenen Auftrags noch mechanischen
Stillstand; tatsächliche Aktorreaktion und Freigabeverfahren bleiben separat.

`started <= updated <= generated` gilt bei vorhandenen Vorgangszeiten nur im
belegten gemeinsamen Uhrenraum; die inaktiven Nullwerte werden nicht verglichen.
Bei Objektwechsel wird der alte Vorgang beendet/abgebrochen und ein neuer
Vorgang angelegt; keine still übertragene Greifbestätigung. B-Neustart setzt
keinen alten Räumvorgang automatisch fort; dessen letzte bekannte Diagnose
bleibt dem alten Start zugeordnet. C-Neustart erzeugt keinen neuen Vorgang.
Wiederaufnahme nach Pause braucht eine neue ausdrückliche B-Entscheidung und
aktuelle getrennte Freigabeergebnisse; C1 simuliert diese Prüfung nicht.

Die vier C1h-Fälle Anschauen, Ausrichten, Greifen und Personenhalt müssen
darstellbar bleiben, einschließlich fehlender Kamerapose, alter Tiefe,
unbestätigter Greiferstellung und unbekannter Last. Personenhalt ist eine
Unterbrechung, kein Erfolg und nicht automatisch Abbruch. Wegfall einer Sperre
löscht keine andere. Odometrieschätzung ersetzt keine Schutzbeobachtung.

## B-Annahme des konkreten V3a-Datenanhangs für Auftrag 5

**B nimmt V3a aus [PR #142 auf exakt
`a4c16698ecca19b04a86636783a7ca3c2d26a4ff`](https://github.com/BBS-GuT/smartcity-roboter/blob/a4c16698ecca19b04a86636783a7ca3c2d26a4ff/docs/entwicklung/C1-vertragsentscheidungen.md)
als Datenmodell zur späteren Auftrag-5-Implementierung an.** Abgeglichen wurden
ausschließlich dieser Datenanhang und seine vier tabellarischen Fälle mit den
B-Vorgaben einschließlich `1a1a3e8c22dd52b1adbcd031a482b25b37a720d1` sowie
den im Anhang beschriebenen A-Vorgaben auf
`69da13138a9d1215dced02b8ca6b00b9c783c617`. Dies ist keine Anwendungscode-/
PR-Diffprüfung und keine Zustimmung im Namen von A/C/O. Aus B bleibt **keine
nötige Feld- oder Semantikkorrektur an diesem konkreten Anhang** vor Auftrag 5.

| Datenentscheidung | B-Annahme und Begründung |
|---|---|
| Vollständige Referenzen | Operation, Objekt, Beobachtung, Schätzung, Frame, Detail und Nachweis bewahren ihre unabhängigen Herkunftsschlüssel. Historische Aufnahmezuordnung ersetzt keinen aktuellen Sensorbeleg; C-Neustart erzeugt keine neue Herkunft. |
| Beobachtung/Schätzung/Erfolg | Echte Aufnahmezeit bleibt unverändert; Schätzung führt eigene Zeit, Odometrieherkunft und Unsicherheit. Erfolg verlangt gültige Nachweise `verification` und `travel_pose` zum selben Vorgang mit Quellen-/Zeitbezug. V3a-Nachweislinks `{ref, status, reason}` konkretisieren die bisherigen B-Kurzreferenzen; Ausgabe, Ack und Timer genügen nicht. |
| Atomare Pakete | Vollständige `evaluation_ref` bindet Ergebnis, Sperrbild und vorhandene Ausgabe. Änderungen verlangen neue Auswertung; kein Zusammenmischen jeweils neuester Teile durch C. `domain=motion/arm` bezeichnet den Auswertungsbereich, ausschließlich `effect=motion/arm/both` die Sperrwirkung. |
| Kontrollierter Nullwunsch | Eigene `request_reason`/`command_reason` kollidieren nicht mit Qualitäts-`reason=null`. `NO_REQUEST`, `NO_ARM_REQUEST` und `PROTECTIVE_ACTION_WITHOUT_REQUEST` unterscheiden belegte Fälle; unbekannte Referenzen bleiben unbekannt und ergeben kein `allowed`. Keine Ausgabe aus Nullwunsch oder Phase erfinden. |
| Inaktivität | Vollständige Nullbelegung erhält gebundene Produzenten-/Uhridentität; `arm.request=null` entwertet den alten Wunsch trotz Restfrist. Neuer Vorgang braucht neue Commandsequenz. Historische Ausgabe/Ack/Messung/Freigabe bleiben beim alten Bezug; kein aktueller Erfolg oder physischer Aktorstopp daraus. |

| Synthetischer Fall | Fachliches B-Votum |
|---|---|
| Anschauen | Angenommen: O/X bleibt zugeordnet, Sichtung 99 wird durch Zustand 10 nicht verjüngt. Klasse, Kamerapose, Politik und Armfreigabebesitzer bleiben unbekannt; C10 ist Wunsch, kein bestätigter Blick. |
| Ausrichten | Angenommen: Objektaufnahme 99 bleibt von neuen echten Arm-/Kameramessungen getrennt. `arm.request=null` hat einen eigenen begründeten Arm-Ergebnisbezug. Seitliche Schutzlücke erzeugt im Alternativfall ein neues vollständiges motion-Paket; keine neue Ausgabe mit altem Ergebnis mischen. Hypothetische Freigabe ist keine Gerätefreigabe. |
| Greifen | Angenommen: Est erneuert Obs/F nicht; unbekannte Unsicherheit verhindert gültige Schätzwerte. Fehlende Greiferstellung/Last sowie fehlende Ausgabe/Ack ergeben keinen Griffnachweis. Ergebnis `offen`, Erfolgsbelege `null`. |
| Personenhalt | Angenommen: `greifen` und O/X bleiben bei `pausiert/offen` mit Unterbrechungsgrund/-zeit erhalten. Person und alte Tiefe bleiben mit gleicher jeweiliger Blockreferenz in beiden Domänen sichtbar. Wegfall der Person löscht weder Tiefe noch STOPP; neue Sperrstände brauchen neue Pakete. Keine Behauptung von Abbruch, Erfolg oder physischem Lasthalten. |

Die Makros sind ausschließlich Lesekürzel vollständiger Referenzen, keine
zulässigen verkürzten JSON-IDs. Alle vier Beispiele sind tabellarische
Projektionen, keine geprüften v2-Fixtures. Dokumentarisch geprüft: Rollen-/
Vorgangs-/Objektbindung, Zeitfortschreibung, Qualitäts-/Nullbelegung sowie
getrennte Wunsch-/Ausgabe-/Nachweisbedeutung; keine Softwaretests konstruiert.

Restbedingungen: A/O bestätigen ihre eigene Annahme; O vergibt Auftrag 5 mit
Dateibesitz. Armfreigabebesitzer, Politik/#8, reale Pflichtquellen, Fristen,
Geometrie und Stellungs-/Last-/STOPP-Nachweise bleiben offen darstellbar.
Dies ist ausschließlich B-Annahme des Datenmodells. Zweite fachliche Annahme
erst am vollständig implementierten Gesamtcommit mit Vertrag, Schema,
Beispielen und funktionalen Nachweisen; keine Geräte-/Broker-/Handlungsfreigabe.

## Abgleich der sechs Folgeaufträge und offene Entscheidung an den Manager

| Auftrag aus #142 | Fachliches B-Votum / konkret nötige Ergänzung |
|---|---|
| 1 Version/Zeitfundament | Angenommen wie V1/V1a/V4: vollständiger exakter Bau-/JSON-Pfad einschließlich Nichtzeit-Decimalverträglichkeit; #11–#14-Regeln erhalten. Ns-Raster-/Fristgrenzen und C-Neustart bei gleichem Sensorstart funktional nachweisen. |
| 2 Details | Angenommen mit explizitem gegebenem Register-/Alterskontext und `age_budget_unknown` wie oben. Historische Registrierung und Farb-/Tiefenpaarung prüfen; kein Payloadspeicher oder Brokerbetrieb. |
| 3 Fahrwunsch | Angenommen einschließlich Anti-Replay-Höchststand aus aktuellem #142. Unabhängigen B-/C-Start, A-Neubindung, Umordnung 8/10/9/11 und unveränderte Fristen funktional nachweisen. Reales Maximalbudget bleibt A/B/O-Entscheidung. |
| 4 Historie | B nimmt 16 Einträge im Zustand, sichtbare Kapazitätsverwerfung, Status-/Reset-/Kartenregeln an; Ergänzung zur Lückenerholung oben. Kein B2-Wegwahl- oder Kartenabnahmenachweis. |
| 5 Räumen/Arm | B nimmt jetzt V3a auf `a4c16698ecca19b04a86636783a7ca3c2d26a4ff` einschließlich der vier Fälle an; die konsolidierte Belegung hat Vorrang vor B-Kurzvorschlägen. A/O-Annahme und O-Vergabe bleiben separat. Armfreigabebesitzer darf offen sichtbar bleiben. |
| 6 Gesamtannahme | Vorgehen angenommen; erst am gesondert gelieferten Gesamtcommit Vertrag, v2-Schema, Beispiele und tatsächliche funktionale Nachweise fachlich abgleichen. Diese erste Entscheidung ersetzt diesen zweiten Schritt nicht. |

Echte offene Entscheidung an den Manager: Armfreigabebesitzer A/B festlegen und
die behauptete Akteursabschaltung aus #126 direkt mit Carsten/#8 klären.
Hier wird keine solche Nutzerentscheidung übernommen. Aktualisierten Ziel-/
Abnahmecommit zu #8 benennen. A/C/O müssen die öffentlichen Datenvorschläge
und die hier engen Ergänzungen bestätigen; B behauptet deren Zustimmung nicht.

Reale Wunschdauer/Senderaten, B2-Karte und Abschlussbelege, Kanalbudgets/Formate,
Uhrbindung, Sensorpflichtmatrix, Hülle/Greifraum, Kalibrierung, Stellungs-/Last-
und STOPP-/Watchdognachweise bleiben gesonderte Aufgaben. Ihre Unbekanntheit ist
**kein Hindernis ehrlicher Darstellung** und darf nicht durch erfundene Werte
beseitigt werden. Geräte-/Broker-/Schutzpolitikfreigabe ist keine Voraussetzung
bloßer Datenannahme; umgekehrt erteilt Datenannahme keine reale Handlungsfreigabe.
Der Datenvalidator wird kein zweiter Motor- oder Armfreigabealgorithmus.

## Dokumentprüfung und Liefergrenze

Reine Dokumentation: keine Anwendungscode-/PR-Diffprüfung, keine Schema-,
Produkt-, Ziel- oder Teständerung; keine Roboteraktion, kein Merge, keine
Workflow-/Rulesetänderung. Links und synthetische Aussagen sind vor Lieferung
zu prüfen. Keine JSON-Codeblöcke und keine künstlichen Softwaretests in dieser
Datei. Tatsächlich geprüft unter Windows mit PowerShell 7.6.5 und Git
2.55.0.windows.4: 5/5 relative Markdownziele vorhanden, referenzierte BBS-Issues
und Entwurfsheads über GitHub gelesen, keine JSON-Codeblöcke. Das synthetische
Pufferbeispiel 0…16 → 1…16/Zähler 1 ist eine Mengen-/Zählkontrolle, keine Fahrt.
`git diff --cached --check` und die Ein-Datei-Grenze werden vor Commit geprüft.
Keine Softwaretests, ROS-Simulation oder Geräte-/Brokerprüfung durchgeführt.
Der native Befund zum Vorgänger `5475f9f` (inaktive Darstellung könnte bekannte
B-Identität löschen) ist durch die ausdrücklich feldweise Nullregel korrigiert.
Der weitere native Befund zum Vorgänger `16862eb` ("ausschließlich vier Felder
null" widerspricht den bedingten Grund-/Zeitregeln) ist durch eine vollständige
Tabelle für gültige Inaktivität korrigiert. Dokumentkontrolle: Produzent/Uhr
bleiben erhalten; Vorgang, Unterbrechung, Abbruch, Ergebnisgrund, Erfolgsbelege
und vorgangsbezogene Objektbeobachtung/Schätzung haben ausdrückliche Nullregeln.
Unabhängige Messungen, Ausgaben und Freigabe-/Schutzdaten werden nicht gelöscht.
Der native Befund zum Vorgänger `deba190` (alter Armwunsch bleibt bei Inaktivität
mit offener Frist aktuell) ist durch `arm.request=null` bereits im ersten
inaktiven Zustand ergänzt. Dokumentarischer Übergangsabgleich: laufender Vorgang
mit noch nicht abgelaufenem Wunsch → inaktiv ohne aktuellen Wunsch, historische
Ausgabe/Bestätigung behalten alte Bezüge → neuer Vorgang nur mit neuem Wunsch
und neuer Commandsequenz. Daraus folgt kein tatsächlicher Aktorstoppnachweis.
Aktueller nativer Review und CI-Status gehören zum konkreten Lieferhead
im Teil-PR; sie werden nicht aus älteren Entwurfsreviews abgeleitet.
