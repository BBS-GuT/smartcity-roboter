#!/bin/bash
# Startet ALLES: Kamera, KI-Zentrale und das Control-Panel.
# Wird vom Dock-/Desktop-Symbol "SmartCity Panel" aufgerufen (siehe installieren.sh).
#
# Anzeige, in dieser Reihenfolge:
#   1. eigenes Panel-Fenster (ohne Browser)  -> Fenster schliessen = alles aus, Roboter haelt an
#   2. sonst ein Browser                      -> zum Beenden DIESES Terminal schliessen oder
#                                                im Panel unter System "Panel beenden"
# Fehlt beides: scripts/browser_installieren.sh
# Laptop-Zugriff ist standardmaessig AN. Ausschalten:  scripts/panel.sh --kein-netz
source "$(dirname "$0")/env.sh"
export DISPLAY="${DISPLAY:-:0}"
PORT=8080
URL="http://localhost:$PORT"

if curl -s -o /dev/null "$URL/api/status"; then
    echo "Panel laeuft schon, oeffne nur die Anzeige."
else
    echo "Starte Panel (Kamera und KI-Zentrale starten automatisch mit) ..."
    # Ausgabe des Panels auch in logs/panel.log (vorheriger Lauf: logs/panel.alt.log)
    mkdir -p "$REPO_DIR/logs"
    [ -f "$REPO_DIR/logs/panel.log" ] && mv -f "$REPO_DIR/logs/panel.log" "$REPO_DIR/logs/panel.alt.log"
    PYTHONUNBUFFERED=1 python3 "$REPO_DIR/panel/panel.py" --port "$PORT" --autostart "$@" > >(tee "$REPO_DIR/logs/panel.log") 2>&1 &
    PANEL=$!
    # Beim Beenden dieses Skripts (auch Terminal schliessen) das Panel sauber beenden
    trap 'kill -TERM $PANEL 2>/dev/null; wait $PANEL 2>/dev/null' EXIT
    for _ in $(seq 40); do
        curl -s -o /dev/null "$URL/api/status" && break
        kill -0 $PANEL 2>/dev/null || { echo "Panel ist abgestuerzt, siehe Meldungen oben."; exit 1; }
        sleep 0.5
    done
fi

# 1. Eigenes Fenster (WebKit)
if python3 -c "import gi; gi.require_version('Gtk', '3.0')" 2>/dev/null && \
   python3 -c "import gi
for v in ('4.1', '4.0'):
    try: gi.require_version('WebKit2', v); break
    except ValueError: pass
from gi.repository import WebKit2" 2>/dev/null; then
    echo "Oeffne Panel-Fenster (F11 = Vollbild an/aus, Strg+Q = schliessen)"
    python3 "$REPO_DIR/panel/fenster.py" "$URL"
    echo "Fenster geschlossen -> Panel wird beendet, Roboter haelt an."
    exit 0
fi

# 2. Browser (laeuft unabhaengig, das Panel laeuft weiter, bis dieses Terminal zu ist)
GEOEFFNET=""
for B in epiphany-browser epiphany firefox falkon chromium-browser chromium google-chrome; do
    command -v "$B" >/dev/null || continue
    echo "Oeffne $URL mit $B ..."
    "$B" "$URL" >/dev/null 2>&1 &
    BPID=$!
    sleep 6
    # Ein Browser, der sich sofort wieder beendet, ist kaputt (z. B. Chromium-Snap auf dem Jetson)
    # ODER hat die Seite an ein schon offenes Fenster uebergeben. Beides ist ok, wenn eins offen ist.
    if kill -0 $BPID 2>/dev/null || pgrep -f "$B" >/dev/null; then
        GEOEFFNET=$B
        break
    fi
    echo "  $B hat sich sofort beendet (kaputt?). Naechster Browser ..."
done

echo
if [ -n "$GEOEFFNET" ]; then
    echo "Panel ist offen in $GEOEFFNET."
else
    echo "Kein funktionierender Browser gefunden -> scripts/browser_installieren.sh"
fi
echo "Adresse am Roboter: $URL"
for IP in $(hostname -I); do
    [[ "$IP" == *.*.*.* ]] && echo "Adresse vom Laptop:  http://$IP:$PORT  (Laptop-Zugriff ist an, abschalten unter System)"
done
echo
echo ">>> Dieses Fenster offen lassen. Schliessen oder Strg+C = alles aus, Roboter haelt an. <<<"
[ -n "$PANEL" ] && wait $PANEL
