# Begleiteter Fahrbetrieb mit vorhandener Sensorabdeckung

`begleiteter_fahrbetrieb` ist standardmäßig **false**. Die ausdrückliche Auswahl erlaubt fortlaufende Fahrt mit der vorhandenen Sensorik trotz bekannter räumlicher Messlücken. Es gibt weder eine zusätzliche Sechs-Sekunden-Grenze noch eine zusätzliche Geschwindigkeitsbegrenzung oder Verriegelung nach einem normalen Hindernishalt. Geschwindigkeit, Linienführung, Verkehrsentscheidungen und STOPP folgen der vorhandenen Steuerung. Die Auswahl startet keine Fahrt.

Die Auswahl erfolgt bei gestoppten Anwendungen in derselben lokalen Konfiguration für KI und Linienfolger. Ein Wechsel während laufender Prozesse wird abgewiesen. Kamera und Fahrzeuggeometrie müssen zum tatsächlichen Aufbau passen. Die Bedienperson prüft die Strecke und greift bei verlorener Spur oder drohender Berührung mit STOPP ein. Unbeobachtete Flächen bleiben unbekannt; die Auswahl bescheinigt keine vollständige Schutzabdeckung und keine autonome Abnahme.

Gelockert wird ausschließlich die Pflicht zur lückenlosen aktuellen Flächenmessung im vorderen Fahrkorridor und finalen Bewegungsbereich. Alle konfigurierten LiDARs bleiben Pflichtquellen. Datenqualität, Aufnahme- und Empfangsalter, bekannte Geometrie und gemessene Hindernisse bleiben wirksam. Rückwärtige und Überweg-Flächenabfragen bleiben unverändert.

Die KI verlangt außerdem eine frische, gültige Tiefenmessung in der bestätigten Fahrstellung mit zum Farbbild passender Aufnahmezeit und passendem Frame. Das kalibrierte Bodenmodell lernt keine neuen Gegenstände als Boden ein. Erkannte Tiefenhindernisse führen zum Halt. Automatische Armbewegungen und KI-Manöver bleiben in dieser Betriebsart gesperrt. Der Linienfolger verlangt deren ausdrückliche Kennzeichnung durch die KI sowie aktive KI- und Hindernispflichtprüfungen.

KI und Linienfolger kennzeichnen die Betriebsart in ihrer Telemetrie. Bei einer Abdeckungslücke bleiben `lidar=null` und `lidar_abdeckung=unbekannt` erhalten; fehlende Flächen werden nicht als frei ausgegeben.

Die Softwaregegenproben in `tests/test_fahrtest.py` prüfen die Auswahl, reale Hindernis- und Fehlerhalte sowie den finalen Publisher ohne künstliches Zeitlimit. Sie ersetzen keine beobachtete Fahrt oder Haltprüfung am RM-01.
In dieser ausdruecklich gewaehlten Betriebsart wird fuer die am RM-01 beobachtete kleine MCU-Uhrabweichung (etwa 30 ms voraus bei kontinuierlichen aktuellen Scans) ein begrenzter Uhrspielraum von hoechstens 100 ms beruecksichtigt. Die Rohzeitstempel werden nicht umgeschrieben. Aufnahmealter, monotones Empfangsalter, Fortschritt und Doppelerkennung bleiben wirksam; groessere Zukunftswerte und Uhrspruenge halten weiterhin. Im Standardbetrieb bleibt der Spielraum null. Dieser Abgleich ersetzt keine dauerhaft stabile Uhrsynchronisation.
