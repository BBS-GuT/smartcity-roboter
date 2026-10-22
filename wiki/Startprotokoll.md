# Startprotokoll vor jeder Fahrt

Diese **manuelle Checkliste** wird vor TEST/START für den vereinbarten Prüf- oder Betriebsumfang abgearbeitet. Sie setzt eine abgeschlossene [Erste Inbetriebnahme](Erste-Inbetriebnahme) und passende Gerätebelege voraus. Ein Häkchen ersetzt keine Geräteabnahme und keinen Nachweis der tatsächlich wirksamen Motorsperre. Ein automatischer Gesamtcheck mit gemeinsamer Bereitschafts-/Motorfreigabe ist noch offene Entwicklungsarbeit.

## Vorbereiten und prüfen

- [ ] **Gerät und Platz:** Beschriftung RM01–RM04 stimmt mit dem Geräteblatt überein. Prüfbereich ist frei, eine Person bedient und beobachtet. Vor dem Einschalten bekannte Startbewegungen aus dem Geräteprotokoll berücksichtigen, insbesondere eine eingerichtete Arm-Ausgangsposition. Solange die ROS-Trennung nicht nachgewiesen ist, andere Roboter mit derselben Domain im selben Netz ausgeschaltet lassen.
- [ ] **Software und Einstellungen:** Im [Panel](Bedienung-mit-dem-Panel) unter **System → Systemcheck** Gerätename und Software-Version mit dem festgelegten Stand vergleichen. Geladene Karte und lokale Einstellungen gehören zu diesem Gerät und Aufbau; die zugehörigen Kalibrierbelege liegen vor. Fehlende Versions- oder Kalibrierzuordnung bleibt ungeprüft.
- [ ] **Netz und ROS:** Systemcheck und IP-Adresse in der Panel-Kopfzeile passen zum Geräteblatt. Bei vereinbartem Fernzugriff das Panel am Laptop öffnen. Die dokumentierte Domain muss für unsere Programme **und** Hersteller-/micro-ROS-Agent gelten; eine Zahl im Terminal allein belegt das nicht. Nach Änderungen zuerst die Zuordnung gemäß [Roboter und Netz](Roboter-und-Netz) prüfen lassen.
- [ ] **Akku, Board und Uhr:** Unter **System** Akku und Fehler prüfen und mit den festgelegten Gerätegrenzen vergleichen. Datum/Uhrzeit des Roboters mit einer Referenz vergleichen; den Synchronisationsstatus gemäß Geräteprotokoll prüfen. Keine Unterspannung oder ungeklärten Boardfehler übergehen.
- [ ] **Arm, Kamera und Sensoren:** Arm/Kamera befinden sich in der für dieses Gerät bestätigten Fahrstellung. Sensorfenster sind frei, Halterungen unverändert. Im Startcheck keine ungemessenen Posen anfahren oder Greifer-/Kalibrierläufe starten.
- [ ] **Wirkliche Sensordaten:** Unter **Sensoren** Farbe, Tiefe, beide LiDAR-Quellen (`/scan0`, `/scan1`), Odometrie und IMU für den vorgesehenen Umfang prüfen: richtige Quelle, fortlaufende Messungen, plausibles Alter und gültige Werte gemäß Gerätebeleg. Bild und Scans dürfen nicht eingefroren sein. Ein vorhandenes Topic oder eine Messrate allein beweist keine gültige Messung. Fehlende Alters-/Gültigkeitsnachweise durch die Geräteprüfung klären lassen.
- [ ] **Ein Bedienweg:** Zuständige Person, erreichbarer STOPP und das am Gerät geprüfte Abbruchverfahren sind klar. Gamepad und Panel nicht gleichzeitig benutzen. Das dokumentierte Startverfahren darf keine konkurrierenden alten Fahr-/Armprogramme enthalten; nach einer Startänderung müssen die Befehlsquellen erneut geprüft werden.
- [ ] **Datenverbindung:** Vereinbarten Netz-/Brokerstatus und Aktualität der übertragenen Daten prüfen und fehlende Anzeigen oder Übertragungen als offen notieren. Ein Brokerausfall darf die lokale Steuerung nicht blockieren; eine Wiederverbindung erzeugt keine neue Fahrfreigabe. Eine noch fehlende MQTT-Funktion gilt dadurch nicht als abgenommen.

**Fehlt eine Pflichtvoraussetzung für den vorgesehenen Versuch, nicht START drücken.** Ursache und betroffenen Prüfumfang notieren. Fehlende Sensoren oder Schutzprüfungen nicht abschalten, um die Liste abzuhaken.

## TEST, dann bewusster START

1. **TEST** wählen. Im Dashboard Kamerabild, Linie, Wahrnehmung, Entscheidung und Haltgründe ansehen. Der Roboter muss dabei tatsächlich stehen bleiben; ein laufender Prozess ist kein Stillstandsnachweis.
2. Bei alten/fehlenden Daten, unplausibler Anzeige oder unerwarteter Bewegung abbrechen. **STOPP** benutzen und den Stillstand nach dem am Gerät geprüften Verfahren herstellen. Unter **System → Logs herunterladen** die Belege sichern; siehe [Fehlersuche](Fehlersuche).
3. Erst nach geklärten Pflichtpunkten und für den vereinbarten Prüf-/Betriebsumfang bewusst **START** drücken. Nur das dafür bestätigte Tempo und Fahrgebiet verwenden, STOPP erreichbar halten. Aktive Haltgründe gelten weiter. Nach Bedien-STOPP oder kritischem Fehler darf eine Wiederfreigabe nicht allein durch Sensorwiederkehr, Grün oder Netzverbindung entstehen.

Wegräumen gehört zum Grundbetrieb. Für einen Versuch mit Wegräumen müssen die geräteeigenen Arm-/Greiferwerte und der benötigte Schutzbereich ebenfalls bestätigt sein; ein bestandener Liniencheck nimmt das Greifen nicht mit ab.

## Wann wieder einrichten?

Kalibrierung und Updates erfolgen bei der Einrichtung oder nach einer relevanten Änderung, nicht automatisch vor jeder Fahrt. Nach Umbau, Sensortausch, geänderter Armfahrstellung oder betroffenem Software-/Treiberwechsel die zugehörigen Prüfungen aus der [Ersten Inbetriebnahme](Erste-Inbetriebnahme) wiederholen. Geräteeigene Kalibrierungen erhalten und nicht von einem anderen Roboter kopieren. Automatische Kartenkalibrierung nicht pauschal einschalten.

## Kurz protokollieren

```text
Datum/Uhrzeit / Person / Roboter:
Software-Commit / Karte / Konfigurations- und Kalibrierbeleg:
IP / ROS-Domain / geprüfter Umfang:
Startcheck und TEST: bestanden | nicht bestanden | nicht geprüft
Offene Punkte / Haltgrund / Logbeleg:
Bewusster START für diesen Umfang: ja | nein
```

Einrichtung, Startcheck und reale Fahrabnahme werden getrennt dokumentiert. Die Grundlage sind die [Geräteblätter](https://github.com/BBS-GuT/smartcity-roboter/tree/main/docs/geraete) und die [Zieldefinition](https://github.com/BBS-GuT/smartcity-roboter/blob/main/docs/zieldefinition-grundbetrieb.md).
