#!/usr/bin/env python3
"""D1b: Runner mit temporaeren kuenstlichen Skripten, ohne ROS oder Fachimporte."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'scripts/pruefen.py'


class Runner(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / 'tests').mkdir()

    def script(self, name, source):
        (self.root / 'tests' / name).write_text(source, encoding='utf-8')

    def run_runner(self, *args, root=None):
        return subprocess.run([sys.executable, str(RUNNER), '--root', str(root or self.root), *args],
                              cwd=self.root.parent, capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=30)

    def test_discovery_lists_all_real_scripts_without_imports(self):
        result = self.run_runner('--list', root=ROOT)
        expected = sorted('tests/' + path.name for path in (ROOT / 'tests').glob('test_*.py'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), expected)
        # Ein Import dieses Skripts wuerde sofort fehlschlagen.
        self.script('test_only_discover.py', "raise RuntimeError('must not import')")
        self.assertEqual(self.run_runner('--list').returncode, 0)

    def test_sorted_separate_processes_and_project_cwd(self):
        self.script('test_a.py', "from pathlib import Path\nPath('marker').write_text('ok')\n"
                    "import builtins\nbuiltins.d1_marker = True\nprint('first')\n")
        self.script('test_b.py', "from pathlib import Path\nimport builtins\n"
                    "assert Path('marker').read_text() == 'ok'\n"
                    "assert not hasattr(builtins, 'd1_marker')\nprint('second')\n")
        # Historische Probes und Hilfsskripte gehoeren nicht zur Regression.
        (self.root / 'docs/pruefungen').mkdir(parents=True)
        (self.root / 'docs/pruefungen/test_probe.py').write_text('raise RuntimeError()')
        self.script('helper.py', 'raise RuntimeError()')
        result = self.run_runner('--log-dir', str(self.root / 'logs'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertLess(result.stdout.index('first'), result.stdout.index('second'))
        self.assertIn('2/2 Skripte bestanden', result.stdout)
        self.assertIn('second', (self.root / 'logs/test_b.log').read_text(encoding='utf-8'))

    def test_failure_keeps_stdout_stderr_and_continues(self):
        self.script('test_a.py', "import sys\nprint('before failure')\nprint('diagnosis', file=sys.stderr)\nsys.exit(7)")
        self.script('test_b.py', "print('after failure')")
        result = self.run_runner()
        self.assertEqual(result.returncode, 1)
        for message in ('before failure', 'diagnosis', 'Exitcode 7', 'after failure', '1/2 Skripte bestanden'):
            self.assertIn(message, result.stdout)

    def test_missing_dependency_is_failure(self):
        self.script('test_missing.py', 'import d1_intentionally_missing_dependency_38502')
        result = self.run_runner()
        self.assertEqual(result.returncode, 1)
        self.assertIn('ModuleNotFoundError', result.stdout)

    def test_unittest_skip_is_incomplete(self):
        self.script('test_skip.py', "import unittest\nclass Check(unittest.TestCase):\n"
                    " @unittest.skip('missing required package')\n def test_schema(self): pass\n"
                    "unittest.main()\n")
        result = self.run_runner()
        self.assertEqual(result.returncode, 1)
        self.assertIn('UNVOLLSTAENDIG', result.stdout)
        self.assertIn('skipped=1', result.stdout)

    def test_timeout_keeps_partial_output_and_continues(self):
        self.script('test_a.py', "import time\nprint('before timeout', flush=True)\ntime.sleep(60)")
        self.script('test_b.py', "print('after timeout')")
        result = self.run_runner('--timeout', '0.8')
        self.assertEqual(result.returncode, 1)
        for message in ('TIMEOUT', 'before timeout', 'after timeout', '1/2 Skripte bestanden'):
            self.assertIn(message, result.stdout)

    def test_individual_timeout_override(self):
        self.script('test_long.py', 'import time\ntime.sleep(1.2)')
        result = self.run_runner('--timeout', '0.8', '--test-timeout', 'test_long.py=10')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_invalid_timeout_and_empty_suite_fail(self):
        self.assertEqual(self.run_runner().returncode, 2)
        self.script('test_ok.py', 'pass')
        for value in ('0', '-1', 'nan', 'inf', 'not-a-number'):
            with self.subTest(value=value):
                self.assertEqual(self.run_runner('--timeout', value).returncode, 2)
        self.assertEqual(self.run_runner('--test-timeout', 'test_unknown.py=1').returncode, 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
