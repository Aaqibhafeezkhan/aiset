"""The office should suggest the launcher only when it can be used from PATH."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from aiset import init_team, registry  # noqa: E402


class PMCommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.workspace = os.path.join(self.root, "workspace")
        self.repo = os.path.join(self.workspace, "service")
        os.makedirs(os.path.join(self.repo, ".git"))
        with open(
            os.path.join(self.repo, "pyproject.toml"), "w", encoding="utf-8"
        ) as f:
            f.write("[project]\nname = 'service'\n")
        self.bin_dir = os.path.join(self.root, "bin")
        self.old_home = os.environ.get("AISET_HOME")
        os.environ["AISET_HOME"] = os.path.join(self.root, ".aiset")

    def tearDown(self):
        if self.old_home is None:
            os.environ.pop("AISET_HOME", None)
        else:
            os.environ["AISET_HOME"] = self.old_home
        self.tmp.cleanup()

    def run_init(self, *args, on_path=True, scripts_dir_side_effect=None):
        scripts_dir_patch = (
            patch.object(registry, "scripts_dir", side_effect=scripts_dir_side_effect)
            if scripts_dir_side_effect is not None
            else patch.object(
                registry, "scripts_dir", return_value=(self.bin_dir, on_path)
            )
        )
        with (
            patch.object(
                sys, "argv", ["aiset-init", self.workspace, "--team", "Demo", *args]
            ),
            scripts_dir_patch,
            patch("builtins.print"),
        ):
            init_team.main()
        roster_path = os.path.join(self.workspace, ".claude", "team", "roster.json")
        with open(roster_path, encoding="utf-8") as f:
            return json.load(f)

    def test_launcher_on_path_sets_the_roster_command(self):
        roster = self.run_init()

        self.assertEqual(roster["pmCommand"], "demo-pm")
        self.assertTrue(os.path.isfile(os.path.join(self.bin_dir, "demo-pm")))

    def test_no_launcher_preserves_an_existing_pm_command(self):
        team_dir = os.path.join(self.workspace, ".claude", "team")
        os.makedirs(team_dir)
        with open(os.path.join(team_dir, "roster.json"), "w", encoding="utf-8") as f:
            json.dump({"team": "Demo", "pmCommand": "custom-pm", "members": []}, f)

        roster = self.run_init(
            "--no-launcher",
            scripts_dir_side_effect=AssertionError("launcher should be skipped"),
        )

        self.assertEqual(roster["pmCommand"], "custom-pm")

    def test_launcher_off_path_keeps_the_existing_command(self):
        roster = self.run_init(on_path=False)

        self.assertEqual(roster["pmCommand"], "claude --agent pm")
        self.assertTrue(os.path.isfile(os.path.join(self.bin_dir, "demo-pm")))

    def test_foreign_launcher_name_keeps_the_existing_command(self):
        os.makedirs(self.bin_dir)
        launcher_name = "demo-pm.cmd" if os.name == "nt" else "demo-pm"
        with open(
            os.path.join(self.bin_dir, launcher_name), "w", encoding="utf-8"
        ) as f:
            f.write("another command\n")

        roster = self.run_init()

        self.assertEqual(roster["pmCommand"], "claude --agent pm")


if __name__ == "__main__":
    unittest.main()
