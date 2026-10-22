"""Hermetic checks for the micro-ROS agent wrapper; no ROS installation needed."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/microros_agent_stable.sh'


class MicroRosAgentStartTests(unittest.TestCase):
    def test_minimal_environment_and_agent_arguments(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / 'home'
            binary = root / 'bin'
            capture = root / 'capture.txt'
            device = root / 'serial-device'
            binary.mkdir()
            device.touch()

            for name, marker in (('yahboomcar_ws', 'YAHBOOM'),
                                 ('mircoROS_agent', 'MICROROS'),
                                 ('M3Pro_ws', 'M3PRO')):
                setup = home / name / 'install/setup.bash'
                setup.parent.mkdir(parents=True)
                setup.write_text(f'export SOURCED_{marker}=1\n', encoding='utf-8')

            fake_ros2 = binary / 'ros2'
            fake_ros2.write_text(
                '#!/bin/bash\n'
                '{\n'
                '  printf "args=%s\\n" "$*"\n'
                '  env | sort\n'
                '} > "$MICROROS_TEST_CAPTURE"\n',
                encoding='utf-8')
            fake_ros2.chmod(0o755)

            environment = os.environ.copy()
            for name in ('ROS_DOMAIN_ID', 'ROS_LOCALHOST_ONLY', 'RMW_IMPLEMENTATION'):
                environment.pop(name, None)
            environment.update({
                'MICROROS_WORKSPACE_HOME': str(home),
                'PATH': str(binary) + os.pathsep + environment.get('PATH', ''),
                'MICROROS_TEST_CAPTURE': str(capture),
                'MICROROS_ROS2': str(fake_ros2),
                'MICROROS_SERIAL_DEVICE': str(device),
                'MICROROS_BAUD': '123456',
                'MICROROS_VERBOSITY': '6',
                'FASTRTPS_DEFAULT_PROFILES_FILE': '/project/fastdds.xml',
                'FASTDDS_DEFAULT_PROFILES_FILE': '/project/fastdds.xml',
                'RMW_FASTRTPS_USE_QOS_FROM_XML': '1',
            })
            result = subprocess.run(['bash', str(SCRIPT)], env=environment,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = capture.read_text(encoding='utf-8')
            self.assertIn(
                f'args=run micro_ros_agent micro_ros_agent serial --dev {device} '
                '-b 123456 -v 6', output)
            self.assertIn('SOURCED_YAHBOOM=1', output)
            self.assertIn('SOURCED_MICROROS=1', output)
            self.assertNotIn('SOURCED_M3PRO=', output)
            self.assertNotIn('FASTRTPS_DEFAULT_PROFILES_FILE=', output)
            self.assertNotIn('FASTDDS_DEFAULT_PROFILES_FILE=', output)
            self.assertNotIn('RMW_FASTRTPS_USE_QOS_FROM_XML=', output)
            self.assertIn('ROS_DOMAIN_ID=30', output)
            self.assertIn('ROS_LOCALHOST_ONLY=0', output)

    def test_domain_file_matches_panel_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            device = root / 'serial-device'
            device.touch()
            (root / 'ros_domain_id').write_text('31\n', encoding='utf-8')
            capture = root / 'capture.txt'
            fake_ros2 = root / 'ros2'
            fake_ros2.write_text('#!/bin/bash\nprintf "%s" "$ROS_DOMAIN_ID" > "$MICROROS_TEST_CAPTURE"\n', encoding='utf-8')
            fake_ros2.chmod(0o755)
            environment = os.environ.copy()
            environment.pop('ROS_DOMAIN_ID', None)
            environment.pop('ROS_DOMAIN_ID_OVERRIDE', None)
            environment.update({'MICROROS_WORKSPACE_HOME': str(root),
                                'MICROROS_SERIAL_DEVICE': str(device),
                                'MICROROS_ROS2': str(fake_ros2),
                                'MICROROS_TEST_CAPTURE': str(capture)})
            result = subprocess.run(['bash', str(SCRIPT)], env=environment,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(capture.read_text(), '31')

    def test_missing_device_fails_after_bounded_wait(self):
        with tempfile.TemporaryDirectory() as temporary:
            environment = os.environ.copy()
            for name in ('ROS_DOMAIN_ID', 'ROS_LOCALHOST_ONLY', 'RMW_IMPLEMENTATION'):
                environment.pop(name, None)
            environment.update({
                'MICROROS_WORKSPACE_HOME': temporary,
                'MICROROS_SERIAL_DEVICE': str(Path(temporary) / 'missing'),
                'MICROROS_DEVICE_WAIT_SECONDS': '0',
            })
            result = subprocess.run(['bash', str(SCRIPT)], env=environment,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            self.assertIn('micro-ROS serial device not available', result.stderr)


if __name__ == '__main__':
    unittest.main()
