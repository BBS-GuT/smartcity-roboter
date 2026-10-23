# RM01: erhaltener Fahrstand vom 23.10.2026

Der erhaltene Produktstand ist `f69ac3907c536df867fe6eec9157d8c44f4466ad`,
basierend auf `74a6c8de05a90ed2785ebd9da57dbff3827044d0` mit dem
Zebrastreifenfix. Genau dieser Stand wurde auf RM01 installiert. Der Bediener
meldete anschließend erfolgreiche Fahrt und präzisierte den Nachweis:
**Linienfolgen und Abbiegen funktionieren einigermaßen.**

Das ist eine teilweise beobachtete Fahrfähigkeit. Eine vollständige
Spurtreue-, Kreuzungs-, Überweg- oder wiederholte STOPP/START-Abnahme liegt
damit nicht vor. Ein erfolgreicher automatischer Räumzyklus ist ebenfalls
nicht nachgewiesen.

## Zebrastreifenfix

Die Erkennung verlangt eine zusammenhängende regelmäßige Balkenreihe in
benachbarten Bildzeilen. Ein Auftrag entsteht erst nach drei verschiedenen,
frischen, aufeinanderfolgenden Aufnahmen mit passender Erkennung.
Getrennte Balkenpaare, verstreute Zeilen und ein einzelner Treffer genügen
nicht. Sechs gezielte Softwaregegenproben prüfen diese Fälle.

Zwölf auf RM01 stationär aufgenommene Bilder ohne Überweg ergaben keine
Zebrastreifenerkennung. Auch die Sichtprüfung zeigte nur eine Leitlinie.
Eine reale Positivprobe vor einem echten Überweg war vor Ort nicht möglich.
Das Bild des ursprünglichen Fehlalarms ist nicht gespeichert.

## Zuordnung des PR

Der Produktcode dieses PR entspricht dem genannten installierten Fahrstand.
Die aktuellen Prüf- und Review-Workflows von `main` bleiben erhalten; dieses
Dokument ergänzt dessen Herkunft und Nachweisgrenzen. Der installierte
Roboter und seine Sicherung werden durch die PR-Aktualisierung nicht verändert.

Die zusätzliche Entwicklung bis
`3d542f3fa5b38d196059ea9c9a955a28c4362936` bleibt im separaten Zweig
`archive/rm01-entwicklung-20261023-3d542f3` erhalten. Ihre weitergehenden
STOPP/START-, Sensorstatus-, Bodenreferenz- und Räumänderungen gehören nicht
zum erhaltenen Fahrstand.

Die zuletzt am Gerät eingestellten 0,30 m/s sind ein Bedienwert zur Laufzeit.
Die PR-Übernahme verändert den Geschwindigkeitsstandard im Quellcode nicht.

Bekannte Reviewbefunde zur echten Bodenreferenz, zur Tiefengültigkeit entlang
gekrümmter Fahrwege und zur Simulatorzuordnung bleiben für diesen erhaltenen
Stand zu prüfen beziehungsweise zu beheben. Die Uhrkorrektur und der
Board-Neustart waren Geräteaktionen; das Zurückspielen des Codes stellt
keine dauerhaft synchronisierten Hardwareuhren her. Pflichtprüfungen und
unabhängiger Review gelten für den aktuellen PR-Commit weiterhin.
