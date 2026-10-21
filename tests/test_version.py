"""Version flags must work without an initialized workspace."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aiset import __version__  # noqa: E402


class VersionTest(unittest.TestCase):
    def test_version_flags(self):
        source = Path(__file__).resolve().parents[1] / "src"
        for module in ("server", "init_team", "teammap"):
            with self.subTest(module=module), tempfile.TemporaryDirectory() as home:
                env = dict(os.environ)
                env.update(HOME=home, USERPROFILE=home, AISET_HOME=home,
                           AISET_WORKSPACE=home, PYTHONPATH=str(source),
                           PYTHONDONTWRITEBYTECODE="1")
                result = subprocess.run(
                    [sys.executable, "-m", "aiset." + module, "--version"],
                    cwd=home, env=env, capture_output=True, text=True, timeout=10, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip().split()[-1], __version__)
                self.assertEqual(list(Path(home).iterdir()), [])
