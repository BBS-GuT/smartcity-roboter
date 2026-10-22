"""WebApp display and battery parsing without ROS or robot commands."""
import ast
import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mqtt_data', ROOT / 'panel/mqtt_data.py')
data = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data)


class MqttViewTests(unittest.TestCase):
    def test_process_flags_never_become_measured_state(self):
        view = data.summary({'fahren': False, 'tempo': 0.15, 'akku': None})
        for name in ('state', 'measured_speed_m_s', 'position_on_site_plan', 'battery_voltage_v'):
            self.assertIsNone(view[name])

    def test_voltage_precision(self):
        self.assertEqual(data.summary({'akku': 12.345678})['battery_voltage_v'], 12.346)

    def test_common_battery_does_not_inherit_another_sources_age(self):
        view = data.summary({'akku': None, 'akku_alter': 60},
                            {'diagnostics': {'battery_v': {'status': 'valid', 'value': 12.4}}})
        self.assertEqual(view['battery_voltage_v'], 12.4)
        self.assertIsNone(view['battery_age_s'])

    def test_invalid_and_stale_motion_are_unknown(self):
        for value, status in [(float('nan'), 'valid'), (True, 'valid'), (1, 'stale')]:
            view = data.summary({}, {'motion': {'measured_v_m_s': {'value': value, 'status': status}}})
            self.assertIsNone(view['measured_speed_m_s'])
        self.assertEqual(data.measured({'value': 0, 'status': 'valid'}), 0)

    def test_battery_parser_prefers_voltage_and_rejects_invalid_values(self):
        tree = ast.parse((ROOT / 'panel/panel.py').read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'PanelNode')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_akku')
        namespace = {'math': math}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<battery>', 'exec'), namespace)
        values = []
        node = SimpleNamespace(_set=lambda name, value: values.append(value))
        namespace['_akku'](node, SimpleNamespace(voltage=12.34567, data=1))
        self.assertEqual(values, [12.34567])
        for invalid in [float('nan'), float('inf'), True, 0, 90, '12.3']:
            namespace['_akku'](node, SimpleNamespace(data=invalid))
        self.assertEqual(values, [12.34567])


if __name__ == '__main__':
    unittest.main()
