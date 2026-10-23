#!/bin/bash
# Start separately, or set SMARTCITY_MQTT=1 before starting the panel.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ "$#" -gt 0 ]; then
    exec "${MQTT_PYTHON:-python3}" "$ROOT/mqtt/panel_bridge.py" "$@"
fi
exec "${MQTT_PYTHON:-python3}" "$ROOT/mqtt/auto_bridge.py"
