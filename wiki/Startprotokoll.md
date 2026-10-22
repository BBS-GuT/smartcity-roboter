# Startprotokoll vor jeder Fahrt

Für einen Fahrversuch gilt die vollständige **manuelle Checkliste** unten, auch vor der ersten Fahrt: Einrichtungsschritte 1–5 der [Ersten Inbetriebnahme](Erste-Inbetriebnahme) und passende Gerätebelege müssen dafür vorliegen. Der reine Kalibrier-TEST während dieser Einrichtung hat den eigenen Vorabcheck im nächsten Abschnitt und setzt die noch zu ermittelnde Kalibrierung nicht voraus. Ein Häkchen ersetzt keine Geräteabnahme und keinen Nachweis der tatsächlich wirksamen Motorsperre. Ein automatischer Gesamtcheck mit gemeinsamer Bereitschafts-/Motorfreigabe ist noch offene Entwicklungsarbeit.

Beide Abläufe verwenden die vorhandene Schaltfläche **TEST**. „Kalibrier-TEST“ bezeichnet hier nur den Zweck der Prüfung, keine zusätzliche Panel-Funktion.

## Kalibrier-TEST ohne Fahrt

Dieser Vorabcheck gilt nur für die stehende Kamera-/Draufsichtprüfung in Einrichtungsschritt 4. Die vollständige Fahrcheckliste wird dafür noch nicht verlangt.

- [ ] Gerät und Softwarestand sind zugeordnet; den Nachweis von Quellstand und Anwendungsstart unten verwenden. ROS-Zuordnung und Startverfahren sind bekannt, andere Roboter mit gleicher Domain bleiben ausgeschaltet. Kein Gamepad oder anderes Fahr-/Armprogramm greift gleichzeitig ein.
- [ ] Der betreute Aufbau steht still, STOPP und das am Gerät geprüfte Abbruchverfahren sind erreichbar. Bekannte Einschalt-/Armbewegungen vorher berücksichtigen. Arm/Kamera sind wie in Einrichtungsschritt 3 eingestellt; der Bewegungsbereich ist frei.
- [ ] Die für diesen Bildtest benötigten Kamerabilder kommen aktuell vom richtigen Gerät. Kamerahöhe/-neigung dürfen noch eingemessen werden; eine abgeschlossene Kamera-, LiDAR- oder Greifkalibrierung ist keine Voraussetzung dieses reinen Bildtests.

Nur **TEST** wählen und die Kameradarstellung prüfen: **kein START**, keine Fahr-, Arm- oder Greifkommandos betätigen. Bei unerwarteter Bewegung oder unbrauchbaren Bildern abbrechen und STOPP sowie das geprüfte Abbruchverfahren verwenden. Anschließend STOPP, Werte dokumentieren und die Einrichtung fortsetzen. Dieser Test bestätigt keine Fahrbereitschaft; vor einem Fahrversuch folgt der vollständige Check.

## Check vor einem Fahrversuch

Nach abgeschlossenen Einrichtungsschritten 1–5 und vor **TEST** zur Fahrvorbereitung sowie **START** alle folgenden Punkte prüfen:

- [ ] **Gerät und Platz:** Beschriftung RM01–RM04 stimmt mit dem Geräteblatt überein. Prüfbereich ist frei, eine Person bedient und beobachtet. Vor dem Einschalten bekannte Startbewegungen aus dem Geräteprotokoll berücksichtigen, insbesondere eine eingerichtete Arm-Ausgangsposition. Solange die ROS-Trennung nicht nachgewiesen ist, andere Roboter mit derselben Domain im selben Netz ausgeschaltet lassen.
- [ ] **Software und Einstellungen:** Im [Panel](Bedienung-mit-dem-Panel) unter **System → Systemcheck** Gerätename und Software-Version mit dem festgelegten Stand vergleichen. Zusätzlich Quellstand und Anwendungsstart nach dem Prüfweg unten bestätigen; der Systemcheck allein zeigt weder lokale Änderungen noch die Version bereits laufender Programme. Geladene Karte und lokale Einstellungen gehören zu diesem Gerät und Aufbau; die zugehörigen Kalibrierbelege liegen vor. Fehlende Versions- oder Kalibrierzuordnung bleibt ungeprüft.
- [ ] **Netz und ROS:** Systemcheck und IP-Adresse in der Panel-Kopfzeile passen zum Geräteblatt. Bei vereinbartem Fernzugriff das Panel am Laptop öffnen. Die dokumentierte Domain muss für unsere Programme **und** Hersteller-/micro-ROS-Agent gelten; eine Zahl im Terminal allein belegt das nicht. Nach Änderungen zuerst die Zuordnung gemäß [Roboter und Netz](Roboter-und-Netz) prüfen lassen.
- [ ] **Akku, Board und Uhr:** Akkuanzeige in der **Kopfzeile** ansehen; unter **Sensoren** die Akkuspannung und vorhandene Board-/Agentmeldungen prüfen und mit den festgelegten Gerätegrenzen vergleichen. Datum/Uhrzeit des Roboters mit einer Referenz vergleichen; den Synchronisationsstatus gemäß Geräteprotokoll prüfen. Keine Unterspannung oder ungeklärten Boardfehler übergehen.
- [ ] **Arm, Kamera und Sensoren:** Arm/Kamera befinden sich in der für dieses Gerät bestätigten Fahrstellung. Sensorfenster sind frei, Halterungen unverändert. Im Startcheck keine ungemessenen Posen anfahren oder Greifer-/Kalibrierläufe starten.
- [ ] **Wirkliche Sensordaten:** Unter **Sensoren** Farbe, Tiefe, beide LiDAR-Quellen (`/scan0`, `/scan1`), Odometrie und IMU für den vorgesehenen Umfang prüfen: richtige Quelle, fortlaufende Messungen, plausibles Alter und gültige Werte gemäß Gerätebeleg. Bild und Scans dürfen nicht eingefroren sein. Ein vorhandenes Topic oder eine Messrate allein beweist keine gültige Messung. Fehlende Alters-/Gültigkeitsnachweise durch die Geräteprüfung klären lassen.
- [ ] **Ein Bedienweg:** Zuständige Person, erreichbarer STOPP und das am Gerät geprüfte Abbruchverfahren sind klar. Gamepad und Panel nicht gleichzeitig benutzen. Das dokumentierte Startverfahren darf keine konkurrierenden alten Fahr-/Armprogramme enthalten; nach einer Startänderung müssen die Befehlsquellen erneut geprüft werden.
- [ ] **Datenverbindung:** Vereinbarten Netz-/Brokerstatus und Aktualität der übertragenen Daten prüfen und fehlende Anzeigen oder Übertragungen als offen notieren. Ein Brokerausfall darf die lokale Steuerung nicht blockieren; eine Wiederverbindung erzeugt keine neue Fahrfreigabe. Eine noch fehlende MQTT-Funktion gilt dadurch nicht als abgenommen.

**Fehlt eine Pflichtvoraussetzung für den vorgesehenen Versuch, nicht START drücken.** Ursache und betroffenen Prüfumfang notieren. Fehlende Sensoren oder Schutzprüfungen nicht abschalten, um die Liste abzuhaken.

## Quellstand und Anwendungsstart

Ein passender Git-Stand beweist nicht, dass schon laufende Programme diesen Code geladen haben. Updates und Quelländerungen gehören ausschließlich ins Wartungsfenster, nicht in einen laufenden Kalibrier-TEST oder Fahrbetrieb.

**Nach einem Update oder einer Quelländerung gilt:**

1. TEST/Fahrt mit STOPP beenden und alle betroffenen Anwendungsprogramme nach dem dokumentierten Startverfahren geordnet beenden. STOPP allein beendet nicht die Prozesse. Dazu gehören Panelserver, KI, Kartograf, Linienfolger und weitere betroffene Komponenten des Geräteprofils; auch getrennt gestartete Instanzen berücksichtigen.
2. Update oder Quelländerung bei beendeten betroffenen Anwendungen ausführen. Falls die vorhandene System-Update-Funktion schon bei laufendem Panel benutzt wurde, müssen anschließend ebenfalls alle betroffenen Anwendungsprozesse einschließlich Panel geordnet beendet werden; der Updatehinweis allein erledigt das nicht.
3. Alle betroffenen Komponenten aus dem festgelegten Projektordner über den dokumentierten Startweg neu starten. Die verantwortliche Person bestätigt anhand des Geräte-/Startprotokolls, dass die alten Instanzen tatsächlich beendet und die neuen gestartet sind. Nur die Browserseite neu laden oder neu öffnen zählt nicht als Anwendungsneustart.
4. Erst danach den folgenden Git-Nachweis und den passenden Check für Kalibrier-TEST oder Fahrversuch durchführen. Neustartbeleg mit Datum/Startzeit, betroffenen Komponenten und Commit im Geräteprotokoll festhalten.

Ohne erneute Änderung seit dem bestätigten Anwendungsstart ist kein wiederholter Programmneustart nötig; der Startbeleg muss weiterhin zum laufenden Stand passen.

Dafür ist kein Roboter-Neustart erforderlich. Bei unklarem Anwendungsneustart oder verbliebenen alten Prozessen keinen TEST und keine Fahrt beginnen.

Im Terminal des Roboters in den **tatsächlich vom Panel gestarteten Projektordner** wechseln; der Pfad steht im Geräteprotokoll. Diesen lesenden Prüfweg für den Kalibrier-TEST und für die Fahrvorbereitung verwenden:

```bash
git rev-parse HEAD
git status --short --untracked-files=all
```

Beide Befehle müssen fehlerfrei laufen: Der erste muss den festgelegten vollständigen Commit ausgeben, der zweite **keine Ausgabe**. Jede Änderung an versionierten Dateien und jede unversionierte Datei bleibt zunächst ungeprüft, auch bei passender Commit-ID. Befund sichern und mit der zuständigen Person klären; nichts durch Löschen oder Zurücksetzen verbergen. Ignorierte geräteeigene Konfigurations-, Karten- und Kalibrierdaten brauchen weiterhin ihren gesonderten Beleg.

## Fahrversuch: TEST, dann bewusster START

1. Nach dem vollständigen Check **TEST** zur Fahrvorbereitung wählen. Im Dashboard Kamerabild, Linie, Wahrnehmung, Entscheidung und Haltgründe ansehen. Der Roboter muss dabei tatsächlich stehen bleiben; ein laufender Prozess ist kein Stillstandsnachweis.
2. Bei alten/fehlenden Daten, unplausibler Anzeige oder unerwarteter Bewegung abbrechen. **STOPP** benutzen und den Stillstand nach dem am Gerät geprüften Verfahren herstellen. Unter **System → Logs herunterladen** die Belege sichern; siehe [Fehlersuche](Fehlersuche).
3. Erst nach geklärten Pflichtpunkten und für den vereinbarten Prüf-/Betriebsumfang bewusst **START** drücken. Nur das dafür bestätigte Tempo und Fahrgebiet verwenden, STOPP erreichbar halten. Aktive Haltgründe gelten weiter. Nach Bedien-STOPP oder kritischem Fehler darf eine Wiederfreigabe nicht allein durch Sensorwiederkehr, Grün oder Netzverbindung entstehen.

Wegräumen gehört zum Grundbetrieb. Für einen Versuch mit Wegräumen müssen die geräteeigenen Arm-/Greiferwerte und der benötigte Schutzbereich ebenfalls bestätigt sein; ein bestandener Liniencheck nimmt das Greifen nicht mit ab.

## Wann wieder einrichten?

Kalibrierung und Updates erfolgen bei der Einrichtung oder nach einer relevanten Änderung, nicht automatisch vor jeder Fahrt. Nach Umbau, Sensortausch, geänderter Armfahrstellung oder betroffenem Software-/Treiberwechsel die zugehörigen Prüfungen aus der [Ersten Inbetriebnahme](Erste-Inbetriebnahme) wiederholen. Geräteeigene Kalibrierungen erhalten und nicht von einem anderen Roboter kopieren. Automatische Kartenkalibrierung nicht pauschal einschalten.

## Kurz protokollieren

```text
Datum/Uhrzeit / Person / Roboter:
Software-Commit / Karte / Konfigurations- und Kalibrierbeleg:
Anwendungsstart nach Update / Komponenten / Startzeit / Beleg:
IP / ROS-Domain / geprüfter Umfang:
Startcheck und TEST: bestanden | nicht bestanden | nicht geprüft
Offene Punkte / Haltgrund / Logbeleg:
Bewusster START für diesen Umfang: ja | nein
```

Einrichtung, Startcheck und reale Fahrabnahme werden getrennt dokumentiert. Die Grundlage sind die [Geräteblätter](https://github.com/BBS-GuT/smartcity-roboter/tree/main/docs/geraete) und die [Zieldefinition](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/zieldefinition-grundbetrieb.md).
