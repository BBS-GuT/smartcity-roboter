# RM02: Wiederortungsverlust ab Minute 3

Stand: 22.10.2026. Refs [#40](https://github.com/BBS-GuT/smartcity-roboter/issues/40),
[#107](https://github.com/BBS-GuT/smartcity-roboter/issues/107).
**Status: Datenvoraussetzung offen; kein reproduzierter Originalfall und keine Geräteabnahme.**

## Prüfgrundlage und Herkunft

Die lesende Codeprüfung und Suchinventur erfolgten auf
`d082a2b46cb311e6fddfda53bb2e745410f7d572` im kanonischen BBS-Repository.
Der historische lokale Kartierungsaudit vom 22.10. bezog sich auf
`62f04bad158be638eaad4d5c33e8ba724915bf7d`; seine Aussage zu fehlender
Replaydatei und fehlendem Nachweis gilt auch für die unten tatsächlich geprüften
Ablagen. Seine synthetischen Bewegungsprobes sind kein Originalreplay.

Die Originalreferenz ist
[davidheinrich73/smartcity-roboter PR #44](https://github.com/davidheinrich73/smartcity-roboter/pull/44),
nicht die gleich nummerierte BBS-PR. Dessen live gelesener Beschreibung zufolge:

| Datensatz / Stand | Berichtete sichere Abgleiche Minute 1 / 2 / 3 / 4 |
|---|---|
| `smartcity_20261020_112619`, alter Vergleichsstand | 56 / 0 / 0 / 0 % |
| dieselbe Aufnahme, PR44 mit `/scan1`, Selbstkalibrierung aus | 72 / 91 / 0 / 0 % |

Das sind übernommene historische Berichtswerte, **keine in dieser Prüfung neu
gemessenen Zahlen**. Original-PR44 nennt Head
`ef1c31e3216919e034b86c0f305a75edea097655`, Merge
`3bd76435431466733b85d2d5f9dbe31e28dd3ab1` und als damalige Basis `a01c453`.
Diese Softwarebezüge beweisen nicht den tatsächlich installierten Aufnahme-SHA.
Der Bericht ordnet den Lauf 11:20–11:31 dem Stand vor PR44 zu. Aufnahmebeginn,
erstes/letztes Ereignis und Dauer sind ohne Datei nicht aus dem Namen ableitbar.

[Problemprotokoll](../problemprotokoll.md), Abschnitt zum Lauf 11:20–11:31:
Odometrie meldet beim Übergang Stillstand, die Kartenübereinstimmung bricht ein.
Umsetzen und Verdeckung sind Vermutungen. Daraus folgt weder gemessener realer
Stillstand noch eine bestätigte Fehlerursache.

Die spätere Aufnahme `smartcity_20261020_115423` ist ein anderer Datensatz.
Ihr Praxisbericht (11:54–12:00, PR44, 94 % sicher, längste Unsicherheit 7,8 s,
ein Raum ohne Doppelbild im Panel) ist ein positiver historischer Teilbeleg.
Er ersetzt weder den Übergang von `112619` noch eine aktuelle
[#42-Abnahme](https://github.com/BBS-GuT/smartcity-roboter/issues/42).
Der am 22.10. gelesene
[PR #165](https://github.com/BBS-GuT/smartcity-roboter/pull/165) auf Head
`fd720e1963537eb8d43ff3c2451fd7395a26d46a` enthält dazu ein allgemeines
Abnahmegerüst ohne Originaldatenpfad, installierten SHA oder Messprotokoll.

## Tatsächlich durchsuchte Bereiche und Grenzen

Die Suche ging über den Aufnahmenamen hinaus: Dateiinventur einschließlich
versteckter Dateien (ohne `.git`, Abhängigkeitspakete), Aufzeichnungsformate
`jsonl`, `jsonl.gz`, `bag`, `mcap`, `db3`, Aufnahmenverzeichnisse,
Projekttextverweise und Archiv-Inhaltsverzeichnisse.

- `C:\SmartCity`: Entwicklungskopien, `research`, `pruefung`, `betrieb`,
  `output`, `smartcity-roboter` und Übergaben; auch frühere PR44-Snapshots,
  Wiki-Spiegel und Metadaten gelesen. Sie verweisen auf den Fall, liefern aber
  keinen zugänglichen Originalpfad oder Download der Aufnahme.
- Dateiinventuren in `Downloads`, `Documents`, `OneDrive`, `source`,
  `OneDrive - ENKO Software GmbH & Co. KG` und `iuk26b` unter dem lokalen
  Benutzerprofil: kein benannter RM02-Datensatz gefunden. Fachfremde persönliche
  Archive wurden nicht inhaltlich geöffnet.
- Ergänzend `C:\Users\CarstenHaas\.codex\attachments`: alle sechs Dateien
  anhand Namen/Dateikennungen geprüft (fünf TXT, eine JSON, keine ZIP-/GZIP-/
  TAR-Kennung). Aufgabenbezogene Textsuche fand nur den bereits gelesenen
  Startauftrag, keine Aufnahme oder weitere lokale Work-Datenreferenz.
  Die Dateinameninventur der lokalen `.codex\codex-remote-attachments` und
  `.codex\.chatgpt-projects` lieferte ebenfalls keinen passenden Aufnahme-
  oder Archivkandidaten. Keine beliebigen privaten Inhalte und keine Cloud
  wurden durchsucht. Die tatsächlich referenzierten Projektablagen liegen
  unter dem oben geprüften `C:\SmartCity`; ein weiterer konkreter Work-Pfad
  ging aus den geprüften aufgabenbezogenen Quellen nicht hervor.
- Inhaltsverzeichnisse aller 14 gefundenen Projekt-ZIP/TAR/TAR.GZ-Archive unter
  `C:\SmartCity` gelesen: zwei alte SmartCity-Quell-TARs, Upstream-ZIP,
  Yahboom-Workspace-ZIP, drei RM01-Sicherungsarchive, RM01-Paket,
  main-Baseline, actionlint und vier RM01-Belegarchive. Keine Einträge für
  `112619`, `115423`, `aufnahmen` oder einen RM02-Replaycontainer gefunden.
- Neun vorhandene `raw_scans.jsonl.gz` aus RM01-LiDAR-Prüfungen wurden anhand
  des ersten JSON-Datensatzes geprüft: Scanformat mit `topic`, `ranges`,
  `recv_wall_ns`, nicht das Messfahrtformat `typ`/`t`/`kopf` mit Odometrie und
  IMU. Die zugehörigen RM01-Herkunftsverzeichnisse und Archive sind keine
  Ersatzaufnahme. Vorhandene `karte.npz` aus Forschungsprobes sind synthetische
  Testartefakte, kein nachgewiesener RM02-Initialzustand.
- GitHub: #40 einschließlich Kommentare (keine), ursprüngliches Quellissue
  #63, Original-PR44 samt Beschreibung/Kommentaren, PR165 und rekursiver
  BBS-Gitbaum am Basiscommit gelesen. Im Gitbaum keine Originalaufnahme;
  lokale Git-Historie für `karten/aufnahmen` ohne Treffer.

Die Inventur beweist **kein endgültiges Nichtvorhandensein**: nicht zugängliche
Datenträger, fremde Rechner, nicht lokal vorliegende Cloudinhalte, unbekannte
Containerformate und nicht durchsuchte Gitobjekte bleiben außerhalb des Nachweises.
Kein Roboter, Netzwerkgerät oder externer Nachrichtendienst wurde angesprochen.
Lokale Suchbelege liegen außerhalb des Repositorys unter
`C:\SmartCity\uebergaben\nacht-20261022\107\40` (`dateikandidaten.txt`,
`komprimiert-und-zusatzwurzeln.txt`, `archive.json`, `original-pr44.json`,
`attachments-metadata.json`).

## Konkrete fehlende Voraussetzung

Bereitzustellen ist die vollständige ursprüngliche gzip-JSONL-Messfahrt
`smartcity_20261020_112619` in einer abgestimmten lokalen Belegablage, zusammen
mit Herkunft (Bereitsteller, Quellpfad/Export, Bereitstellungszeit), Dateigröße,
SHA256, erstem/letztem Ereigniszeitpunkt und tatsächlich installiertem Software-SHA.
Das Format ist in [lib/aufnahme.py](../../lib/aufnahme.py) beschrieben.
Den vollständigen Kopf `cfg`, Sensorquellen, Haupt-LiDAR, Selbstkalibrierung,
Einbau-/Spiegelparameter und die Zeitstempelbehandlung sichern.
SHA256 und Rohdaten bleiben bis dahin **nicht verfügbar**, nicht geschätzt.
Große oder private Aufnahmen zuerst lokal prüfen, nicht ungeprüft committen.

## Vorbereiteter Replaypfad (noch nicht mit Original ausgeführt)

Der aktuelle [Replay](../../kartograf/abspielen.py) liest Kopfkonfiguration,
überschreibt nur ausdrücklich gesetzte Werte und beginnt mit einer neuen Karte.
Er lädt keine vorher gespeicherte Livekarte. Die vollständige Aufnahme muss vom
ersten Ereignis durchlaufen; Minute 3 isoliert mit leerer Karte ist unzulässig.
Für die Livegleichheit gegebenenfalls zusätzlich den anfänglichen Karten-,
Kalibrierungs- und Ortungszustand beschaffen. Ohne diesen Nachweis ist das
Ergebnis ein Replay mit eigenem Kartenstart, keine identische Live-Reproduktion.

Nach Bereitstellung, jeweils im Checkout des festgehaltenen Vergleichscommits
(PowerShell; Pfade sind ein Bereitstellungsvorschlag, keine vorhandenen Dateien):

```powershell
$aufnahme = 'C:\SmartCity\uebergaben\nacht-20261022\107\40\original\smartcity_20261020_112619.jsonl.gz'
$ausgabe = 'C:\SmartCity\uebergaben\nacht-20261022\107\40\replay-basis'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:TMP = 'C:\SmartCity\uebergaben\nacht-20261022\107\40'
$env:TEMP = $env:TMP
git rev-parse HEAD
Get-FileHash -Algorithm SHA256 -LiteralPath $aufnahme
& 'C:\SmartCity\entwicklung\d1-evidence\venv\Scripts\python.exe' `
  kartograf/abspielen.py $aufnahme --ausgabe $ausgabe `
  --setze 'haupt_lidar="/scan1"' --setze 'selbst_kalibrieren=false' `
  2>&1 | Tee-Object -FilePath ($ausgabe + '.log')
```

Dies entspricht den expliziten Parametern des historischen PR44-Vergleichs.
Übrige Werte kommen aus `kopf.cfg`; sie müssen vor dem Lauf protokolliert werden.
Kein `--kurz`: sonst fehlen Minutenwerte. Kamera bleibt für diesen Vergleich
aktiv; eine zusätzliche Auswertung ohne Kamera separat kennzeichnen.
Umgebung: vorhandenes CPython 3.12.14, NumPy 1.26.4, OpenCV 4.10.0, ohne ROS.
Ein Exitcode allein genügt nicht: `aufnahme.lesen()` kann bei beschädigten Daten
vorzeitig enden. Dateiintegrität, erwartete Ereigniszahl und Endzeit separat prüfen.

## Auswertefenster und Wiederholungsvergleich

Nach vollständigem Replay das Fenster relativ zum ersten Diagnoseeintrag
markieren: Minute 2 `[60,120)` s gegen Minute 3 `[120,180)` s, zusätzlich die
genaue letzte sichere/erste dauerhaft unsichere Zuordnung. Die Minuten des
Programms beginnen beim ersten Diagnoseeintrag, nicht zwingend bei Aufnahmebeginn.
Die folgende zusätzliche Auswertung berechnet je Fenster Scananzahl, sicheren
Anteil, mediane Güte, Punkte/Scan, Suchfenster und längste beobachtete
Unsicherheitsfolge mit absoluten Ereigniszeiten. Sie durchläuft ebenfalls die
**Vollaufnahme**, speichert alle Diagnosezeilen und exportiert die Original-
Odometrie-/IMU-Ereignisse zur getrennten Bewegungsanalyse. Die Länge einer
Unsicherheitsfolge reicht vom ersten bis zum letzten unsicheren Diagnosepunkt
im Fenster (Abtastung wie im Replay, keine interpolierte Messung). Der Export
bewahrt die Rohwerte und Zeitstempel; er behauptet keinen realen Stillstand.

Im selben Checkout und mit den PowerShell-Variablen/Umgebungswerten oben:

```powershell
@'
import hashlib, json, pathlib, subprocess, sys
import numpy as np
sys.path.insert(0, str(pathlib.Path('kartograf').resolve()))
import abspielen as replay

datei, ziel = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
ziel.mkdir(parents=True, exist_ok=True)
overrides = {'haupt_lidar': '/scan1', 'selbst_kalibrieren': False}
erg = replay.abspielen(str(datei), overrides, kamera=True)
d = np.asarray(erg['kartierer'].diagnose if erg['kartierer'] else [], dtype=float).reshape(-1, 5)
if not len(d):
    raise SystemExit('Keine Diagnose; kein auswertbarer Replay')
with datei.open('rb') as f:
    sha256 = hashlib.file_digest(f, 'sha256').hexdigest()
meta = {'software_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'datei_sha256': sha256,
        'kopf': erg['kopf'], 'overrides': overrides,
        'diagnose_spalten': ['t', 'guete', 'sicher', 'suchfenster', 'punkte'],
        'diagnose_t0': float(d[0, 0]), 'kamera': True}
np.savetxt(ziel / 'diagnose.csv', d, delimiter=',',
           header='t,guete,sicher,suchfenster,punkte', comments='')

def fenster(a, b):
    rows = d[(d[:, 0] >= d[0, 0] + a) & (d[:, 0] < d[0, 0] + b)]
    if not len(rows):
        return {'relativ_s': [a, b], 'n': 0}
    folgen, start, ende = [], None, None
    for row in rows:
        if not row[2]:
            start = float(row[0]) if start is None else start
            ende = float(row[0])
        elif start is not None:
            folgen.append([start, ende]); start = ende = None
    if start is not None:
        folgen.append([start, ende])
    lang = max(folgen, key=lambda pair: pair[1] - pair[0], default=None)
    werte, anzahl = np.unique(rows[:, 3], return_counts=True)
    return {'relativ_s': [a, b], 'absolut_s': [float(rows[0, 0]), float(rows[-1, 0])],
            'n': len(rows), 'sicher_anteil': float(rows[:, 2].mean()),
            'guete_median': float(np.median(rows[:, 1])),
            'punkte_median': float(np.median(rows[:, 4])),
            'suchfenster_anzahl': dict(zip(map(str, werte), map(int, anzahl))),
            'unsichere_folgen_absolut_s': folgen,
            'laengste_unsicherheit_s': 0.0 if lang is None else lang[1] - lang[0]}

meta['fenster'] = [fenster(60, 120), fenster(120, 180)]
meta['sicherheitswechsel_absolut_s'] = [
    {'vorher_t': float(d[i-1, 0]), 't': float(d[i, 0]), 'sicher': bool(d[i, 2])}
    for i in range(1, len(d)) if d[i, 2] != d[i-1, 2]]
with (ziel / 'bewegung.jsonl').open('w', encoding='utf-8') as f:
    for e in replay.A.lesen(str(datei)):
        if e.get('typ') in ('odom', 'imu'):
            f.write(json.dumps(e, ensure_ascii=False) + '\n')
(ziel / 'vergleich.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
(ziel / 'replay.log').write_text(replay.diagnose_text(erg), encoding='utf-8')
replay.bilder_schreiben(erg, str(ziel))
print(json.dumps(meta['fenster'], ensure_ascii=False, indent=2))
'@ | & 'C:\SmartCity\entwicklung\d1-evidence\venv\Scripts\python.exe' - $aufnahme ($ausgabe + '-fenster')
```

`diagnose.csv` und `sicherheitswechsel_absolut_s` erlauben, letzte sichere und
erste anhaltend unsichere Zuordnung nachzuvollziehen, ohne einen unbekannten
Übergangszeitpunkt zu erfinden. Die beiden festen Minutenfenster sind ein
Ausgangspunkt; ein anschließend enger gewähltes Fenster mit denselben
absoluten Grenzen auf beiden Softwareständen zusätzlich dokumentieren.

Die ausführbare Dokumentanleitung wurde ohne Produktänderungen mit einer
ausdrücklich synthetischen Stillstandsaufnahme durch den echten Replay/
Kartierer geprüft: 183 Einsekundenschritte, 180 identische Strahlen pro Scan,
je ein Odometrie-/IMU-Ereignis. Vorab erwartete 60/60 Diagnosepunkte in den
beiden Fenstern und 366 exportierte Bewegungsereignisse wurden bestätigt;
absolute Fenstergrenzen waren 1060–1119 und 1120–1179 s. Eine zusätzliche
synthetische API-Kontrolle mit Sicherheitswechsel bei 1120 s prüfte die
Persistenz dieses Übergangs und einer 59-s-Unsicherheitsfolge. Diese Kontrollen
prüfen ausschließlich die Dokumentanleitung, nicht den RM02-Originalfehler.

Getrennt daneben aus den Originalereignissen ausweisen:
Odometrie-Positions-/Winkeldelta und Twist, IMU-Drehratenintegral samt
Zeitstempellücken, Scanversorgung und Abgleich mit der Karte. Gemeldeter
Odometrie-Stillstand belegt keine körperliche Ruhe; zur Ursache Umsetzen oder
Verdeckung braucht es zusätzliche Beobachtung. Keine erfundene Ground Truth.

| Nachweis | Basis `d082a2b…` | integrierter Stand nach #31–33 |
|---|---|---|
| Originaldatei / SHA256 / Zeitbereich | fehlt | gleicher Datensatz erforderlich |
| tatsächlicher Replay / Fensterkennzahlen | nicht ausgeführt | nicht ausgeführt |
| Rot-Grün-Vergleich des Originalfehlers | nicht möglich | offen bis Datenbereitstellung und Head-Zuteilung |

Für den späteren Vergleich denselben Datei-SHA256, Kopf, Overrides,
Kartenstart und Auswertefenster verwenden; Ausgabeordner trennen und beide
vollständigen Software-SHAs sichern. Eine Verbesserung synthetischer Tests von
#31–33 sagt das Ergebnis dieser Aufnahme nicht voraus. #40 und #107 bleiben
bei fehlenden Daten offen. Bezug zur Zieldefinition: GB-12/13 und A05/A11;
dieses Dokument erteilt keine Fahr-, Karten- oder Gerätefreigabe.
