import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile
import os
import subprocess

path=Path(__file__).parents[1]/"mqtt"/"update_panel_mqtt.py"
spec=importlib.util.spec_from_file_location("updater",path)
updater=importlib.util.module_from_spec(spec); spec.loader.exec_module(updater)

class Tests(unittest.TestCase):
    def test_process_matching(self):
        cwd=Path("/home/u/smartcity-roboter")
        self.assertEqual(updater.python_script("python3 -u panel/panel.py",cwd),(cwd/"panel/panel.py").resolve())
        self.assertEqual(updater.python_script("/usr/bin/env X=1 python3 mqtt/robot_live_test.py",cwd),(cwd/"mqtt/robot_live_test.py").resolve())
        self.assertIsNone(updater.python_script("python3 - --activate",cwd))
        self.assertTrue(updater.hazardous_process("python3 ./ki/zentrale.py"))
        self.assertTrue(updater.hazardous_process("python3 line_follower.py"))
        self.assertFalse(updater.hazardous_process("python3 panel/panel.py"))
    def test_validation(self):
        updater.validate_file("x.py",b"x=1\n")
        updater.validate_file("x.html",b'<div id="s-mqtt"></div>')
        updater.validate_file("x.sh",b"#!/bin/bash\nmicro_ros_agent\n")
        with self.assertRaises(SyntaxError): updater.validate_file("x.py",b"if:\n")
        with self.assertRaises(RuntimeError): updater.validate_file("x.html",b"<html/>")
        with self.assertRaises(RuntimeError): updater.validate_file("x.sh",b"#!/bin/bash\ntrue")
        with self.assertRaises(subprocess.CalledProcessError):
            updater.validate_file('x.sh', b'#!/bin/bash\n# micro_ros_agent\nif;\n')

    def test_install_rollback_after_second_replace_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo/'panel').mkdir()
            (repo/'panel/one.py').write_bytes(b'old-one')
            (repo/'panel/two.py').write_bytes(b'old-two')
            original_replace = os.replace
            calls = []
            def failing_replace(source, destination):
                calls.append(str(destination))
                if len(calls) == 2: raise OSError('simulated disk failure')
                return original_replace(source, destination)
            with patch.object(updater.os, 'replace', side_effect=failing_replace):
                with self.assertRaises(OSError):
                    updater.install(repo, {'panel/one.py': b'new-one', 'panel/two.py': b'new-two'})
            self.assertEqual((repo/'panel/one.py').read_bytes(), b'old-one')
            self.assertEqual((repo/'panel/two.py').read_bytes(), b'old-two')

    def test_running_drive_or_ki_blocks_activation(self):
        for command in ('python3 ./ki/zentrale.py', 'python3 line_follower/line_follower.py'):
            with self.assertRaises(RuntimeError): updater.preflight([(123, command)])

    def test_battery_output_rejects_boolean_and_unrelated_fields(self):
        self.assertEqual(updater.battery_text({'akku':12.730806}), '12.731 V')
        for record in ({'akku':True}, {'battery':12.7}, {'akku':float('nan')}, {}):
            self.assertEqual(updater.battery_text(record), 'unbekannt')

if __name__=="__main__": unittest.main()
