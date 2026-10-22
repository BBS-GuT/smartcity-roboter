"""Read-only WebApp fields from fresh panel sources; no inferred movement."""
import math


def measured(record):
    if not isinstance(record, dict) or record.get('status') != 'valid':
        return None
    value = record.get('value')
    return value if (isinstance(value, (int, float)) and not isinstance(value, bool)
                     and math.isfinite(value)) else None


def summary(panel, common=None):
    common = common or {}
    runtime = common.get('runtime') or {}
    route = common.get('route') or {}
    voltage = panel.get('akku')
    if voltage is None:
        voltage = measured((common.get('diagnostics') or {}).get('battery_v'))
    return {
        'robot_id': panel.get('roboter') or None,
        'source': 'Lokale Telemetriequelle; MQTT-Zustellung separat ausgewiesen',
        'broker': panel.get('mqtt') or {},
        'state': runtime.get('state'),
        'hold_reasons': runtime.get('hold_reasons', []),
        'position_on_site_plan': None,
        'position_reason': 'Keine verifizierte Zuordnung zum Spielfeldplan',
        'battery_voltage_v': round(voltage, 3) if voltage is not None else None,
        'battery_age_s': panel.get('akku_alter') if panel.get('akku') is not None else None,
        'battery_percent_estimate': panel.get('akku_prozent') if panel.get('akku') is not None else None,
        'direction': route.get('direction'),
        'measured_speed_m_s': measured((common.get('motion') or {}).get('measured_v_m_s')),
        'events': panel.get('ereignisse', [])[:10],
        'board_diagnosis': panel.get('board_diagnose'),
    }
