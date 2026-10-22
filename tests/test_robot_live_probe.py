"""Reproduce concurrent battery-probe writers without ROS or robot access."""
import ast
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import time
import unittest


class BatteryProbeTests(unittest.TestCase):
    def save_function(self, output):
        path = Path(__file__).resolve().parents[1] / 'mqtt/robot_live_test.py'
        module = ast.parse(path.read_text(encoding='utf-8'))
        probe = next(node.value.value for node in module.body
                     if isinstance(node, ast.Assign)
                     and any(isinstance(target, ast.Name) and target.id == 'BATTERY_PROBE'
                             for target in node.targets))
        function = next(node for node in ast.parse(probe).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'save')
        namespace = {'Path': Path, 'json': json, 'tempfile': tempfile, 'time': time, 'output': output}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<probe save>', 'exec'), namespace)
        return namespace['save']

    def test_overlapping_writers_leave_a_complete_record_and_no_temp_files(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'battery.json'
            save = self.save_function(output)
            with ThreadPoolExecutor(max_workers=8) as workers:
                list(workers.map(save, [{'voltage_v': 12.73, 'sequence': n} for n in range(80)]))
            record = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(record['voltage_v'], 12.73)
            self.assertIn(record['sequence'], range(80))
            self.assertEqual(list(Path(directory).glob('*.tmp')), [])

    def test_invalid_record_preserves_previous_measurement(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'battery.json'
            save = self.save_function(output)
            save({'voltage_v': 12.73})
            with self.assertRaises(ValueError):
                save({'voltage_v': float('nan')})
            self.assertEqual(json.loads(output.read_text())['voltage_v'], 12.73)
            self.assertEqual(list(Path(directory).glob('*.tmp')), [])


if __name__ == '__main__':
    unittest.main()
