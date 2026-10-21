"""Initialize single-package repositories without moving the checkout."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aiset import init_team  # noqa: E402


class SingleRepoTest(unittest.TestCase):
    def test_root_python_project_initializes_once_and_stays_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            (root / ".git").mkdir(parents=True)
            (root / "src" / "pkg").mkdir(parents=True)
            (root / "src" / "pkg" / "__init__.py").write_text("")
            (root / "pyproject.toml").write_text('[project]\nname="demo"\n')
            with patch.dict(os.environ, {"AISET_HOME": str(Path(tmp) / "home")}), \
                 patch.object(sys, "argv", ["aiset-init", str(root), "--no-launcher"]), \
                 patch("builtins.print"):
                init_team.main()
                init_team.main()
            roster = json.loads((root / ".claude/team/roster.json").read_text())
            owners = [m for m in roster["members"] if m.get("repos") == ["."]]
            self.assertEqual(len(owners), 1)
            self.assertEqual(owners[0]["id"], "root")
            self.assertEqual(owners[0]["checks"], ["pytest"])
            self.assertTrue((root / ".claude/agents/root.md").is_file())
            self.assertIn("/.claude/", (root / ".git/info/exclude").read_text())

    def test_root_node_and_existing_monorepo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / "package.json").write_text('{"scripts":{"test":"node --test"}}')
            repos = init_team.scan(str(root))
            self.assertEqual([r["name"] for r in repos], ["."])
            self.assertEqual(repos[0]["checks"], ["npm run test"])
            (root / "api").mkdir()
            (root / "api/pyproject.toml").write_text('[project]\nname="api"\n')
            self.assertEqual([r["name"] for r in init_team.scan(str(root))], ["api"])
