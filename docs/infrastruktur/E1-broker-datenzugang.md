# E1 – Broker und externer Datenzugang

Stand 20.10.2026 · Entwurf v0.1 · Status **offen**, sofern nicht ausdrücklich anders bezeichnet. Keine Geräte- oder Bewegungsfreigabe.

Bezug GB-15/16/17/18, A13–A15. Keine Brokerangaben durch Carsten bestätigt. C1 [#14](https://github.com/davidheinrich73/smartcity-roboter/issues/14) bleibt der einzige gemeinsame Vertrag; dieses Erhebungsblatt ersetzt ihn nicht.

| Zu erheben | Projektbroker | Testbroker | Quelle / Rolle / Status |
|---|---|---|---|
| Host / Port / Transport (TLS/TCP/WebSocket) | offen | offen | Netzwerk-/Brokerteam; offen |
| Netz-/Zugriffsvoraussetzung, Zertifikatsprüfung | offen | offen | Netzwerkteam; offen |
| Sichere Bezugsstelle für Zugangsdaten (nur Verfahren/Kontakt) | offen | offen | Carsten / Brokerteam; offen |
| Leserechte, Topicbereich, Testidentitäten | offen | offen | Brokerteam + C; offen |
| Geräte-ID und eindeutige Client-ID je RM01–RM04 / externem Leser | offen | offen | Geräteteam + C; offen |
| Topicstruktur / Schema-/Vertragsversion | offen | offen | C1; offen |
| QoS, retained, Last Will, Reconnect / Puffergrenzen | offen | offen | C + Brokerteam; offen |

Keine Passwörter, Tokens, privaten Schlüssel oder Zugangsdaten in Repo/PR/Logs. Sicheren getrennten Bezug mit Carsten vereinbaren; weder öffentliche Broker noch Standardports als beschlossen einsetzen.

| Datenkanal | Tatsächliches Topic / Format / Einheit | Rate (Hz) / Größe (Byte) / Last | Geräte-/Start-/Sequenz-/Framekennung und Aufnahmezeit | Status / Zuständige |
|---|---|---|---|---|
| Zustand / Info / Ereignis / Verfügbarkeit | offen | offen | offen | offen; C |
| Farbbild | offen; Codec, Auflösung, Farbraum | offen | offen | offen; C + Dashboardteam |
| Tiefe | offen; Encoding, Skala, Ungültigkeitswerte, Auflösung | offen | offen; Bezug zu Farbbild/Intrinsik/Transformation | offen; C + Geräteteam |
| Scan 1 | offen; Winkelbezug, Reichweite, ungültige Werte | offen | offen; Sensor-/Koordinatenframe | offen; C + Geräteteam |
| Scan 2 | offen; getrennte physische Quelle | offen | offen; Sensor-/Koordinatenframe | offen; C + Geräteteam |

Vorschläge aus Zieldefinition §7 (Gerätepräfix, QoS 1, retained Zustand/Verfügbarkeit, Last Will) sind noch keine Vereinbarung. Einheiten, Zeitbasis/Unsicherheit, Schema und Zuordnung getrennter Detailnachrichten durch C festlegen lassen. Rate und Größe tatsächlich messen, Gesamtlast aus Messfenster protokollieren; keine erfundenen Grenzwerte.

## Prüfplan für externen Leser, erst nach Vertrag und Zugang

1. Synthetische Testidentitäten und freigegebenen Testbroker verwenden; Client-ID des Lesers muss von allen Publishern getrennt sein. Nur vereinbarte Lesetopics abonnieren.
2. Zustand und alle drei Detailarten einschließlich beider Scans dekodieren. Geräte-/Start-/Sequenz-/Framekennungen mit Panel abgleichen, Aufnahme- und Empfangszeit getrennt erfassen. Fremdgerät, Duplikat, fehlender Frame und alte retained Daten sichtbar unterscheiden.
3. Im abgestimmten Testaufbau Verbindung des Testclients/-publishers unterbrechen; keine Projekt-Netz-/Dienständerung aus E1. Datenalter trotz bestehender Verbindung durch ausbleibenden Datenstrom prüfen; Grenzwerte kommen von A/C.
4. Wiederverbindung: frischen vollständigen Zustand, begrenzte Warteschlange und erkennbare verworfene/alte Daten nachweisen. Wiederverbindung erzeugt keine Motorfreigabe; dieser reale Nachweis gehört in die spätere betreute A14-Abnahme.
5. Protokoll: Datum/Beobachter, Gerät/Commit/Karte/Konfiguration, Vertragsversion, Broker-Testkennung, Zeitbezug, erwartetes und tatsächliches Ergebnis, Rate/Bytes, Fehler und bereinigter Beleg. Keine Geheimnisse aufnehmen.

Übergabe an A: benötigte Pflichtquellen-/Altersgrenzen, gemessene Sensorlagen/Hülle und Lastgrenzen; keine Konfigurationsänderung hier. An C: Kennungen, Zeit-/Gültigkeitsmodell, Detailreferenzen/Frames, Formatspezifikation und Broker-/Reconnectfragen. Kein MQTT-Fernfahrweg.
