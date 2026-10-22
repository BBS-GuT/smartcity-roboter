# C1f: Eigenständig zuordenbarer Fahrwunsch B → A

**Stand:** 22.10.2026. **Status:** fachlicher Entwurf; Freigabe durch A/B/C/O
ausdrücklich ausstehend. Auftrag [#16](https://github.com/BBS-GuT/smartcity-roboter/issues/16),
Elternauftrag [#3](https://github.com/BBS-GuT/smartcity-roboter/issues/3).
Grundlage: BBS-main `88a82d46023a1e53b7bda78a7f66063872c225c3`,
[bestehender Vertrag](../schnittstellen-grundbetrieb.md),
[C1-Auftrag](../auftraege/C-zustand-mqtt-und-panel.md) und
[Zieldefinition](../zieldefinition-grundbetrieb.md) §6–8, GB-13 bis GB-18,
Abnahmebezug A11–A15. Dies ist kein Abnahmenachweis.

## Zweck und Grenze

Im Basisstand hat `motion.request` nur `request_id`, `valid_until_mono_s`,
`v_m_s`, `w_rad_s`, `maneuver` und `hold_reasons`. Ohne den äußeren Zustand
fehlen Geräte-, Produzentenstart-, Sequenz- und bestätigter Zeitbezug.
Beliebiger Text in `request_id` behebt diese Lücke nicht.

Vorgeschlagen wird eine eigenständig übertragbare Darstellung desselben
Fahrwunsches im **einzigen gemeinsamen C1-Vertrag**. Die nachfolgende Tabelle
beschreibt die künftige vollständige B→A-Nachricht. Sie ist kein zweiter
Zustandsvertrag und kein bereits unterstütztes JSON-Schema. Feldnamen und
Versionierung sind vor einer Umsetzung gemeinsam anzunehmen. Diese Lieferung
ändert weder Laufzeitfelder noch Code, Schema, Transport oder Motoradapter.
Sie schließt #3 nicht; erst ein angenommener Entwurf ermöglicht einen separat
zugeteilten kleinen Implementierungsauftrag.

Ein strukturell gültiger und frischer Fahrwunsch bleibt eine Absicht von B.
Er enthält kein `motor_enabled`, keine endgültige Motorausgabe und keine
Freigabe. A prüft weiterhin STOPP, Fehler, Pflichtsensoren, Verkehrs- und
Schutzbedingungen im gemeinsamen Motorweg. TEST darf einen Wunsch zeigen,
ohne Bewegung freizugeben. Leere Wunschgründe sind kein Sicherheitsnachweis;
gemessene Bewegung und A-Ausgabe bleiben eigene Zustandsdaten.

## Vorgeschlagene Feldtabelle

Alle Felder sind Pflichtfelder; nur `maneuver` darf `null` sein. Zahlen sind
endliche JSON-Zahlen, nie Boolean, `NaN` oder ±Unendlich. Kennungen sind
nichtleere, exakt verglichene Zeichenfolgen ohne implizite Aliasauflösung.

| Feld | Typ / Einheit | Bedeutung und Geltungsbereich |
|---|---|---|
| `contract_version` | Text | Gemeinsam festgelegte Version der Fahrwunschdarstellung im C1-Vertrag; unbekannte Version nicht als verwendbaren Wunsch übernehmen. `c1f-draft` unten ist ausschließlich eine Beispielmarkierung. |
| `robot_id` | `RM01`…`RM04` | Ziel und Ursprung gehören demselben lokalen Gerät; A erwartet seine festgelegte Gerätekennung. |
| `producer_id` | Text | Logischer B-Produzent, unabhängig von Prozess-ID, Transporttopic und Gerätename; nur der lokal zugelassene Produzent darf diese Rolle liefern. |
| `producer_boot_id` | Text | Eindeutige Startkennung dieser Produzenteninstanz, neu bei jedem B-Neustart; auch nach Geräte-/Uhrenneustart niemals wiederverwenden. |
| `request_seq` | ganze Zahl ≥ 0 | Eigene Requestsequenz, ab 0 je `(robot_id, producer_id, producer_boot_id)`, strikt steigend für jeden neuen Wunsch. Keine Zustandssequenz; Lücken zulässig, kein Umlauf oder Rücksetzen im selben Produzentenstart. |
| `request_id` | Text | Opake Diagnose-/Korrelationskennung; keine daraus abgeleitete Identität, Sequenz oder Uhr. Wiederverwendung macht zwei verschiedene Sequenzen nicht gleich. |
| `time_basis_id` | Text | Kennung der gemeinsam bestätigten lokalen monotonen Uhr samt Neustartbereich; keine UTC-Uhr und keine produzentenrelative Stoppuhr. |
| `generated_mono_s` | Zahl ≥ 0, s | Erzeugungszeit des Wunsches in genau dieser lokalen Uhr. Bei höherer Sequenz im selben Produzentenstart mindestens die zuletzt angenommene Erzeugungszeit; wird bei Wiederholung nicht erneuert. |
| `valid_until_mono_s` | Zahl ≥ 0, s | Ausschließliche Ablaufgrenze in derselben Uhr; strikt größer als `generated_mono_s`. Keine Verlängerung durch Empfang oder Wiederholung. |
| `v_m_s` | Zahl, m/s | Gewünschte lineare Bewegung; bestehender v1-Strukturbereich −1…1, keine damit bestätigte Fahrgrenze. |
| `w_rad_s` | Zahl, rad/s | Gewünschte Drehbewegung; bestehender v1-Strukturbereich −10…10, keine damit bestätigte Fahrgrenze. |
| `maneuver` | Text oder `null` | Gewähltes Manöver nach gemeinsamem C1-Vokabular; keine Freigabewirkung. |
| `hold_reasons` | eindeutige Liste von Codes | Fachliche Wunsch-Haltegründe aus dem gemeinsamen C1-Vokabular; keine zweite Liste endgültiger A-Sperren. |

Die eindeutige Requestkennung ist das Tupel
`(robot_id, producer_id, producer_boot_id, request_seq)`. `request_id` ist
kein Ersatz dafür. Eine Wiederholung desselben Tupels muss denselben gesamten
Inhalt tragen; geänderter Inhalt bei gleicher Sequenz ist ein Widerspruch,
kein Update. Ein neuer Wunsch erhält eine neue Sequenz, auch bei gleicher Bewegung.

## Produzentenstart, Zustandsstart und lokale Zeit

Der äußere Zustand behält `robot_id`, `boot_id`, `seq` für den Start und die
Sequenz seines Zustandsproduzenten C. Diese Werte identifizieren den
**Zustandsdatensatz**, nicht den enthaltenen B-Fahrwunsch. C übernimmt die
angenommene Fahrwunschnachricht ohne Umbenennung oder Neuberechnung ihrer
Identität und Zeitwerte als `motion.request`. Ein Zustand darf denselben
Wunsch mehrfach abbilden; seine neue `seq` erzeugt keinen neuen B-Wunsch.
`motion.request = null` bedeutet kein verfügbarer Wunsch; kein Nullfahrwunsch
mit erfundener Identität wird daraus erzeugt.

Ein B-Neustart erneuert `producer_boot_id` und beginnt `request_seq` bei 0,
auch wenn C weiterläuft. Ein reiner C-Neustart erneuert Zustands-`boot_id` und
Zustands-`seq`, während B mit eigener Identität und Sequenz weiterlaufen kann.
Keine Gleichheit der beiden Startkennungen voraussetzen oder verlangen.

**Vorgeschlagene Zeitvereinbarung:** B und A verwenden auf demselben Gerät
dieselbe systemweite monotone Uhr, einschließlich identischem Ursprung,
Einheit, Uhrtyp und Verhalten bei Suspend. Keine Prozessstartzeit abziehen.
`time_basis_id` bezeichnet Gerät, konkrete Uhreninstanz und deren Neustartbereich.
Ein Geräte-/Uhrenneustart oder ein Wechsel des Uhrenraums erneuert diese
Kennung. Ein alleiniger B- oder C-Neustart setzt diese Uhr nicht zurück.
Numerisch ähnliche Werte oder gleiche API-Namen belegen keine gemeinsame Uhr.

Die lokale Start-/Prozessverwaltung muss A vor Übernahme von Wünschen das
erwartete Gerät, den zugelassenen Produzenten, dessen aktiven Start und die
bestätigte Zeitbasis bereitstellen. Diese Zuordnung wird nicht aus der ersten
eingehenden Nachricht, einem Topic oder einem selbst behaupteten
`time_basis_id` als vertrauenswürdig übernommen. Fehlt der Nachweis derselben
lokalen Uhr, ist der Wunsch unverwendbar; keine UTC-Umrechnung, kein
Fristneustart ab Empfang und kein stiller Offsetausgleich. Andere Geräte und
externe Telemetrieleser können diese monotone Uhr nicht zur eigenen
Motorfreigabe verwenden. UTC-Synchronisation des Zustands ändert das nicht.

Bei bestätigter Basis gilt für A zum Prüfzeitpunkt `now_mono_s`:

**Exakte Vergleichssemantik des Entwurfs:** Alle Zeitwerte dieser Nachricht,
die vereinbarte Maximaldauer sowie die lokalen Vergleichswerte `now_mono_s`,
`bind_mono_s` und die zuletzt angenommene Erzeugungszeit werden als ganze
Nanosekunden verglichen. Die `_s`-Felder bleiben JSON-Zahlen in Sekunden;
ihr dezimaler Zahlenwert muss exakt ein Vielfaches von `0.000000001` s sein
und zwischen 0 und `9223372036.854775807` s liegen (0…2⁶³−1 ns).
Auch Exponentialschreibweise und nachgestellte Dezimalnullen sind erlaubt,
sofern der exakte Wert diese Bedingungen erfüllt.

JSON-Zahlentokens werden vor einer Binärfloat-Umwandlung exakt dezimal gelesen
und ohne Rundung in ganze Nanosekunden überführt. Differenzen und Vergleiche
erfolgen ausschließlich auf diesen Ganzzahlen; die Formeln unten verwenden
Sekunden nur als lesbare Notation. Kein Epsilon, kein gerundetes Ergebnis und
kein `float`-Zwischenschritt. Werte außerhalb des Rasters/Bereichs sind
ungültig und werden nicht auf einen passenden Wert gerundet.

B und A müssen die bestätigte lokale Uhr als ganzzahlige Nanosekunden
bereitstellen und für die Nachricht exakt in Dezimalsekunden darstellen;
das Raster behauptet keine tatsächliche Messauflösung von 1 ns. Eine bloße
Binärfloat-Uhr ohne festgelegten exakten Bezug erfüllt diesen Vorschlag nicht.
Die lokale Bindungszeit nutzt denselben Weg. Der bestehende v1-JSON-Ladepfad
mit Binärfloats implementiert diese vorgeschlagene Semantik noch nicht;
das bleibt Teil des späteren ausdrücklich zugeteilten Implementierungsauftrags.

```text
0 <= generated_mono_s <= now_mono_s < valid_until_mono_s
0 < valid_until_mono_s - generated_mono_s <= vereinbarte_maximale_wunschdauer_s
```

Für eine höhere Sequenz im selben gebundenen Produzentenstart gilt zusätzlich
`generated_mono_s >= zuletzt_angenommene_generated_mono_s`. Gleiche Zeiten
sind bei begrenzter Uhrenauflösung zulässig; rückläufige Zeiten sind gemäß
GB-13 ungültig, auch wenn Sequenz und eigene Frist sonst passen. A speichert
Sequenz und Erzeugungszeit gemeinsam nur nach vollständiger Annahme.

Auch `now_mono_s` muss endlich sein. Zukunftszeit, negative Werte, vertauschte
Grenzen oder zu lange Wunschdauer sind ungültig; Gleichheit von `now` und
Ablaufgrenze bedeutet bereits abgelaufen. Die maximale Wunschdauer bleibt
eine mit A/B zu bestätigende Grenze aus Raten, Latenzen und Haltverhalten;
die Beispielspanne von 0,20 s ist keine solche Festlegung. A prüft die Frist
auch während der Verwendung erneut. Neue Empfangszeit, Transport-Reconnect
oder C-Neustart verlängern sie nicht.

## Übernahme und Fehlerfälle bei A

Die folgenden Zuordnungen sind vorgeschlagenes Empfängerverhalten, keine
neuen öffentlichen Haltegrundcodes. Ein verworfener Eingang ersetzt keinen
noch separat gültigen aktuellen Wunsch und verlängert dessen Frist nicht.
Ist kein gültiger aktueller Wunsch vorhanden, bleibt der Motorweg ohne
verwendbaren Fahrwunsch; A setzt das vereinbarte sichere Haltverhalten durch.

| Eingang / Ereignis | Zuordnung und Verhalten |
|---|---|
| Fremdes `robot_id` oder nicht zugelassener `producer_id` | Nicht übernehmen; getrennt diagnostizieren, lokale Sequenz nicht verändern. |
| Anderer oder unbekannter `producer_boot_id` | Nicht mit Sequenzen des aktiven Starts vergleichen, nicht automatisch umschalten. Erst lokal bestätigter Startwechsel bindet den neuen Produzentenstart. |
| Bestätigter B-Startwechsel | Bisherigen Wunsch und seine Verwendbarkeit verwerfen, alten Start sperren; Sequenzvergleich für den neuen Start neu beginnen. Warten auf einen frischen neuen Wunsch; Startwechsel selbst gibt keine Bewegung frei. |
| Identisches Tupel und identischer Inhalt | Duplikat: keine erneute Ausführung, keine Fristerneuerung, kein erneuter Manöverbeginn. |
| Identisches Tupel, anderer Inhalt | Widersprüchlicher Request: nicht übernehmen; Diagnose, keine Änderung des zuletzt gültigen Inhalts. |
| Kleinere Sequenz im selben aktiven Start | Verspätet/replay: verwerfen. Nur höhere Sequenz kann ein neuer Wunsch sein. |
| Höhere Sequenz, aber kleinere Erzeugungszeit als zuletzt angenommen im selben Start | Zeitregression: verwerfen; bisherigen Wunsch, Sequenzstand und angenommene Erzeugungszeit unverändert lassen. Ein älterer Fahrwunsch darf einen neueren Haltwunsch nicht ersetzen. |
| Unbestätigte/fremde `time_basis_id`, Zukunft oder ungültige Zahlen | Nicht verwendbar; keine Altersberechnung mit fremder Uhr. |
| `now_mono_s >= valid_until_mono_s` | Abgelaufen; nicht übernehmen bzw. bisher verwendeten Wunsch auslaufen lassen. Keine alte Bewegung weiterführen, weil kein neuer Request kommt. |
| Neuerer, vollständig gültiger Wunsch | Als aktuellen Wunsch übernehmen und Sequenzstand samt Erzeugungszeit aktualisieren; im selben Start darf die Erzeugungszeit nicht zurücklaufen. A prüft alle eigenen Sperren weiterhin. Ungültige Nachrichten ändern diese Vergleichswerte nicht. |
| A-Neustart oder verlorener Empfängerzustand | Keine Wiederaufnahme aus gepuffertem Zustand. Lokale Zuordnung neu bestätigen, Puffer verwerfen und auf einen nach der erneuten Bindung erzeugten Wunsch warten; alte Requests auch bei noch offener Frist nicht wieder ausführen. |

Nach Ablauf werden Sequenzstand und zuletzt angenommene Erzeugungszeit im
aktiven Empfängerkontext nicht gelöscht;
ein verspätetes älteres Paket darf nicht zum aktuellen Wunsch werden.
Die Zeit der erneuten A-Bindung stammt aus der bestätigten lokalen Uhr;
für den ersten Wunsch danach gilt zusätzlich `generated_mono_s > bind_mono_s`.
Bei Uhrenwechsel wird der bisherige Kontext verworfen und neu gebunden.
Gleichzeitige konkurrierende B-Instanzen werden nicht anhand der höchsten
Sequenz ausgewählt; ihre Zulassung ist vorab lokal eindeutig festzulegen.

## Synthetische Beispiele und Gegenbeispiele

Keine realen Geräte- oder Brokerkennungen außer dem Gerätetyp `RM02`.
Das folgende JSON ist eine vollständige Beispielnachricht dieses Entwurfs;
es ist kein gültiger neuer v1-Schemabeleg. `request_id` ist absichtlich
ohne eingebettete Identitätsinformation gewählt.

```json
{
  "contract_version": "c1f-draft",
  "robot_id": "RM02",
  "producer_id": "beispiel-fahrentscheidung",
  "producer_boot_id": "beispiel-b-start-001",
  "request_seq": 17,
  "request_id": "wunsch",
  "time_basis_id": "beispiel-rm02-monouhr-001",
  "generated_mono_s": 120.0,
  "valid_until_mono_s": 120.2,
  "v_m_s": 0.1,
  "w_rad_s": 0.0,
  "maneuver": null,
  "hold_reasons": []
}
```

Beispielkontext: A ist an RM02, den genannten Produzenten, B-Start und
Uhrenbereich gebunden; Bindung bei 119,0 s, zuletzt angenommene Sequenz 16
mit Erzeugungszeit 119,90 s.
Die nur für diese Beispiele angenommene Höchstdauer ist 0,20 s.
Alle folgenden Zeilen sind **unabhängige** Varianten der obigen Nachricht;
nicht genannte Felder bleiben gleich.

| Fall / Änderung | Lokales Jetzt / Kontext | Erwartetes Ergebnis |
|---|---|---|
| Unveränderte Nachricht | 120,05 s | Neue Sequenz 17 zuordenbar und frisch; ausschließlich Wunsch, keine Motorfreigabe. |
| `v_m_s = 0`, Gründe `RED_LIGHT`, `FRONT_BLOCKED` | 120,05 s | Frischer Haltwunsch mit beiden Gründen. |
| Identische Wiederholung | 120,10 s, Sequenz 17 schon angenommen | Duplikat, Ablauf bleibt 120,20 s. |
| Nur `v_m_s = 0.2` | 120,10 s, Sequenz 17 schon angenommen | Widerspruch bei gleichem Tupel, nicht übernehmen. |
| Nur `request_id = "RM01-start-999-seq-999"` | 120,05 s | Identität bleibt RM02/B-Start-001/17; Text wird nicht geparst. |
| Nur `robot_id = "RM01"` | 120,05 s | Fremdgerät, verwerfen, auch bei gleichlautender `request_id`. |
| Nur `request_seq = 15` | 120,05 s | Alte Sequenz, verwerfen. |
| `request_seq = 18`, Erzeugung 120,00 s, Ablauf 120,20 s, Fahrwunsch 0,1 m/s | 120,15 s; zuvor Haltwunsch Sequenz 17, Erzeugung 120,10 s, Ablauf 120,30 s angenommen | Trotz höherer Sequenz und offener Frist Zeitregression: verwerfen; Haltwunsch 17 und Vergleichswerte bleiben erhalten. |
| `request_seq = 18`, Erzeugung 120,10 s, Ablauf 120,30 s | Derselbe Haltwunsch-17-Kontext, jetzt 120,15 s | Gleiche Erzeugungszeit bei höherer Sequenz zulässig; vollständig gültigen Wunsch übernehmen, A-Sperren weiterhin prüfen. |
| `request_seq = 18`, Erzeugung 120,12 s, Ablauf 120,32 s | Derselbe Haltwunsch-17-Kontext, jetzt 120,15 s | Steigende Erzeugungszeit zulässig; vollständig gültigen Wunsch übernehmen, A-Sperren weiterhin prüfen. |
| Neuer B-Start `beispiel-b-start-002`, Sequenz 0 | 120,05 s, alter B-Start noch gebunden | Anderer Start, nicht automatisch übernehmen. |
| Derselbe neue B-Start, Sequenz 0 | Neue Bindung bei 119,90 s, jetzt 120,05 s | Nach lokal bestätigtem Wechsel erster frischer Wunsch; alter Start bleibt gesperrt. |
| Unverändert | 120,20 s oder später | Abgelaufen, auch ohne zwischenzeitlich neueren Wunsch. |
| `generated_mono_s = 121.0`, Ablauf 121,20 s | 120,05 s | Zukunftszeit, ungültig. |
| Andere `time_basis_id` | 120,05 s | Zahlen nicht vergleichbar, verwerfen. |
| C-Zustand neu: `boot_id = "beispiel-c-start-009"`, `seq = 0` | B unverändert, jetzt 120,05 s | Neue Zustandsidentität, B-Tupel unverändert; kein neuer B-Wunsch. |
| A neu gebunden bei 120,02 s | 120,05 s | Alter Wunsch von 120,00 s wird trotz offener Ablaufgrenze nicht wieder aufgenommen. |

Randbeispiele der exakten Zeitvergleiche, jeweils unabhängig und bei sonst
gültiger Zuordnung/Sequenz; Maximaldauer ausschließlich hier `0.20` s:

| Erzeugung / Ablauf / lokales Jetzt (s) | Exakte Prüfung in ns | Ergebnis |
|---|---|---|
| 120.00 / 120.20 / 120.05 | Dauer 200000000 ≤ 200000000 | Zulässig; kein binärer Subtraktionsfehler. |
| 120.10 / 120.30 / 120.15 | Dauer 200000000 ≤ 200000000 | Ebenfalls zulässig am gleichen Dauerrand. |
| 120.00 / 120.200000001 / 120.05 | Dauer 200000001 > 200000000 | Unzulässig; schon 1 ns Überschreitung wird verworfen. |
| 120.00 / 120.20 / 120.199999999 | Jetzt 120199999999 < Ablauf 120200000000 | Noch innerhalb der Frist. |
| 120.00 / 120.20 / 120.20 | Jetzt = Ablauf = 120200000000 | Bereits abgelaufen, ohne Toleranzverlängerung. |
| 120.00 / 120.20 / 120.200000001 | Jetzt > Ablauf um 1 ns | Abgelaufen. |
| 120.00 / 120.2000000001 / 120.05 | Ablauf ist kein ganzzahliger ns-Wert | Ungültig; nicht auf 120.20 runden. |

Negative Struktur-/Zeitkontrollen: fehlendes `producer_boot_id`, negative
Sequenz, gebrochene Sequenz, Boolean als Sequenz, negative Zeit, Ablauf gleich
Erzeugung sowie `NaN`/±Unendlich sind ungültig. Die Sonderzahlen werden nicht
als JSON-Beispiele ausgegeben. Eine abweichende `request_id` darf keine
dieser Gegenproben gültig machen.

## Offene Entscheidungen und Übergabe

1. **A/B/C/O:** Feldnamen, Pflichtumfang und gemeinsame Vertragsversion
   annehmen; Abbildung als dasselbe `motion.request` bestätigen. Der bisherige
   v1-Validator und das Schema erhalten diese neuen Felder hier noch nicht.
2. **A/B:** Zulässigen logischen Produzenten, Erzeugung der eindeutigen
   Startkennungen und lokale Bestätigung des aktiven Starts festlegen;
   konkreten Prozess-/Transportpfad samt Verhalten bei A-/B-Neustart binden.
3. **A/B/C:** Gemeinsame lokale monotone Uhr einschließlich Ursprung,
   Suspendverhalten, Uhrenbereichskennung und Bestätigungsnachweis festlegen.
   Die vorgeschlagene Vergleichbarkeit ist noch kein Gerätebefund.
4. **A/B/O:** Maximale Wunschdauer, Sende-/Prüfraten und sicheres Haltverhalten
   bei Ausfall/Fristende einschließlich Watchdog und realem Halt nachweisen;
   Diagnoseabbildung für die Fehlerfälle bestätigen. Keine Beispielzahl gilt
   als freigegebener Grenzwert.
5. **C/O:** Angenommenen Entwurfscommit festhalten und danach ein eigenes
   kleines Implementierungsissue für gemeinsamen Vertrag, Schema und passende
   positive/negative Softwareprüfungen vergeben. A-/B-Adapter erst auf
   akzeptiertem Vertragsstand; ROS-, Geräte- und Brokerabnahmen separat.

Fachliche Freigabe A/B/C/O und diese Entscheidungen bleiben ausstehend.
Keine der Beispielprüfungen bestätigt Laufzeitimplementierung oder Bewegung.
