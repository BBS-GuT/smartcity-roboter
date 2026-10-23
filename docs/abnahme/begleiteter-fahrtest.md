# Begleiteter kurzer Fahrtest

`begleiteter_fahrtest` ist standardmäßig **false**. Der ausdrücklich ausgewählte
Testmodus erlaubt eine kurze Vorwärts-Linienfahrt trotz ungeklärter räumlicher
Messabdeckung. Er ist keine Freigabe für normalen autonomen Betrieb. Unbeobachtete
Flächen bleiben im Messmodell unbekannt und werden nicht als frei aufgefüllt.

Vor Auswahl müssen die Kamera in ihrer Fahrstellung kalibriert, der konkrete
Prüfbereich körperlich kontrolliert und die Bedienperson am STOPP bereit sein.
Die Auswahl erfolgt bei gestoppten Anwendungen in derselben lokalen Konfiguration
für KI und Linienfolger. Änderungen dieses Parameters während laufender Prozesse
werden abgewiesen. Es gibt keinen automatischen START.

Der Modus lockert ausschließlich die Pflicht zur lückenlosen aktuellen
Flächenmessung im vorderen Fahrkorridor und finalen Bewegungsbereich. Alle
konfigurierten LiDARs bleiben Pflichtquellen. Datenqualität, Aufnahme-/Empfangsalter,
bekannte Geometrie und gemessene Hindernisse bleiben wirksam. Die rückwärtigen und
Überweg-Flächenabfragen bleiben unverändert streng.

Zusätzlich verlangt die KI eine frische, gültige Tiefenmessung in der bestätigten
Fahrstellung mit zum Farbbild passender Aufnahmezeit und passendem Frame. Der
Tiefentest benutzt die kalibrierte Geometrie ohne adaptive Bodenkorrektur, damit
ein länger vorhandenes Hindernis nicht als Boden eingelernt wird. Erkannte
Tiefenhindernisse halten im Test immer; Arm- und KI-Manöver werden nicht ausgeführt.
Der Linienfolger verlangt die ausdrückliche Testmodus-Kennzeichnung der KI und
aktive KI-/Hindernispflichtprüfungen.

Der finale Publisher begrenzt die Geschwindigkeit der konfigurierten Fahrzeughülle
(Translation plus konservative Eckgeschwindigkeit durch Drehung) auf 0,05 m/s.
Nach spätestens sechs Sekunden ab dem ersten Bewegungsbefehl werden nur noch
Nullbefehle gesendet. Auch ein Halt nach Beginn beendet den Versuch dauerhaft;
Sensorwiederkehr oder Entfernen eines Gegenstands startet ihn nicht automatisch
neu. Ein neuer Versuch braucht Bedien-STOPP und einen neuen START/Prozess.
Rückwärtsfahrt, Seitwärtsfahrt und Drehen auf der Stelle sind im Modus gesperrt.

Die Begrenzung betrifft ausgegebene Befehle. Tatsächliche Fahrt, Bremsweg und Halt
müssen am Gerät beobachtet werden. Der Modus garantiert keine Erkennung in den
unbeobachteten Bereichen. Die Bedienperson muss bei drohender Berührung sofort
STOPP auslösen. Aus einem bestandenen kurzen Versuch folgt weder eine vollständige
Schutzabdeckung noch eine Abnahme für unbeaufsichtigte Runden.

KI und Linienfolger kennzeichnen den Testmodus in der Telemetrie. Bei einer
Abdeckungslücke bleibt der öffentliche LiDAR-Freiraumwert `null` und
`lidar_abdeckung` lautet `unbekannt`; es wird keine scheinbare freie Distanz gemeldet.

Softwaregegenproben stehen in `tests/test_fahrtest.py`. Sie verwenden ausschließlich
ROS-/Publisherattrappen und sind kein ausgeführter Fahrversuch.
