# Kleines historisches LiDAR-Belegpaket zu #59

Untersuchter öffentlicher Commit: `d92e366907fd538c377c272250a0e2d75120b5e2`.

## Voraussetzungen und Aufruf

Ein BBS-Git-Checkout mit diesem Commit im lokalen Objektbestand, Git und die unveränderten Pakete aus `requirements-test.txt`. Keine ROS-Installation oder Geräteverbindung nötig. In einer eigenen virtuellen Testumgebung aus der Projektwurzel:

```text
python -m pip install -r requirements-test.txt
python -m pip check
python docs/pruefungen/lidar-20261021/reproduzieren.py --output lidar-reproduktion.json
python docs/pruefungen/lidar-20261021/test_prototyp.py
```

Nach der Paketinstallation führt die Reproduktion keine Netzaufrufe aus. Git liest ausschließlich den festgelegten historischen Commit. Das Werkzeug exportiert diesen vollständigen öffentlichen Commit in ein temporäres Verzeichnis, startet die historischen Worker dort mit derselben Python-Testumgebung und überprüft vor einer Konstruktion die Herkunft der lokalen ROS-Attrappen. Es startet keinen echten ROS-Knoten oder Hardware-Agenten. Temporäre Pfade werden nicht in die Ergebnisdatei geschrieben. Die Ausgabedatei kann frei gewählt werden und gehört nicht zur Produktkonfiguration. Git-Blobhashes, Exportdateihashes und UTF-8-/LF-normalisierte Quellhashes werden getrennt erfasst; normalisierter Blob- und Exportinhalt müssen übereinstimmen. Damit werden Windows-Zeilenendkonvertierungen nicht als unveränderte Git-Blobbytes ausgegeben.

**Bedeutung des historischen Aufrufs:** Exitcode 0 heißt „historische Fehlersignatur und Gegenkontrollen am fixierten Commit reproduziert“. Es heißt ausdrücklich nicht „Sicherheitsprüfung bestanden“. Die Ausgabe trägt `product_acceptance: false`. Nichtnullbefehle entstehen ausschließlich an einer lokalen Publisherattrappe. Diese Worker gehören absichtlich nicht zu `tests/test_*.py` und schreiben das fehlerhafte Altverhalten nicht als gewünschte Produktregression fest.

## Umfang

- Historischer Fahrpfad: zehn Daten-/Kontrollfälle sowie zwei Richtungsfälle. Null, NaN, leer, Einzelkanal und alter Header sind von gültig frei, Gesamtausfall und Nahhindernis getrennt. `drive=False` erzeugt keine Fahrpublikationen. Ausschließlich `+inf` bleibt hinsichtlich der konkreten Treibersemantik gesondert offen.
- Historische Geometrie: drei synthetische Gegenbeispiele für unterschiedliche Sensorursprünge. Translationen nur als Werksmodellbezug, keine bestätigte Gerätepose.
- Archivierter Offline-Entwurf: 19 Testmethoden für Transformation, Gültigkeitsmaske, vorgegebenen kritischen Bereich, Zeit und explizite Pflichtquellen. Keine Fahrhüllenberechnung oder Produkt-/Motorintegration. Die Geometrie-Gegenkontrolle greift portabel auf den öffentlichen fixierten Quellstand zu.

Die Testumgebung des publizierten lokalen Nachweises und tatsächlich erzielte Ergebnisse werden in `nachweis.json` dokumentiert. Dieser Windows-/Python-3.12-Nachweis ersetzt nicht den unveränderten Ubuntu-22.04/Python-3.10-CI-Lauf oder eine reale Geräteabnahme. Der bestehende gemeinsame Runner bleibt unverändert:

```text
python scripts/pruefen.py --timeout 120 --test-timeout test_karte.py=600 --log-dir testlogs
```

Die optional gewählten Ergebnis-/Logdateien werden nicht automatisch veröffentlicht. Insbesondere einen fehlgeschlagenen Lauf mit lokalen Traceback-Pfaden nicht ungeprüft hochladen.

## Belege und Grenzen

- [Bereinigter fachlicher Bericht](../../abnahme/RM01-2026-10-21-lidar-software.md).
- [Quellhashes, Originalpaket-Prüfsummen und Aufbewahrung](quellen.json): nur öffentliche Quellbezüge und geprüfte Metadaten.
- `historisches-ergebnis.json`: tatsächlich hier ausgeführte historische Reproduktion.
- `nachweis.json`: getrennte Software-/Entwurfsergebnisse und Plattform.
- `manifest.json`: SHA256 der UTF-8-/LF-normalisierten kleinen Paketdateien; das Manifest schließt sich selbst aus. Vor einer Prüfung eines Windows-Arbeitsbaums CRLF/CR zu LF normalisieren oder die entsprechend normalisierten Git-Blobs lesen.

Es werden keine vollständigen Geräte-/Quellzustands-Snapshots, privaten Zugriffspfade, Bootkennungen, Seriennummern, Rohaufnahmezeitreihen oder Rohdatenarchive veröffentlicht. Die 832-Scan-Wiederverwendung der ursprünglichen Analyse wird im Bericht historisch referenziert; dieser kleine synthetische Aufruf behauptet keinen erneuten Replay-Lauf über nicht veröffentlichte Originale.

Produktkorrekturen werden einzeln unter #60–#65 und der ergänzenden Abdeckungsaufgabe umgesetzt. Gerätepose #66 und Geräteabnahme #67 bleiben getrennt. Elternissue #58 und die Gesamtgeräteabnahme werden durch dieses Dokumentationspaket nicht geschlossen.
