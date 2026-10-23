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


def _init(root, tmp):
    with patch.dict(os.environ, {"AISET_HOME": str(Path(tmp) / "home")}), \
         patch.object(sys, "argv", ["aiset-init", str(root), "--no-launcher"]), \
         patch("builtins.print") as out:
        init_team.main()
    return json.loads((root / ".claude/team/roster.json").read_text()), out


class UniqueMemberIdTest(unittest.TestCase):
    def _single_package_repo(self, tmp):
        root = Path(tmp) / "project"
        (root / ".git").mkdir(parents=True)
        (root / "pyproject.toml").write_text('[project]\nname="demo"\n')
        return root

    def test_service_called_root_added_after_root_unit_gets_its_own_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._single_package_repo(tmp)
            _init(root, tmp)
            (root / "root").mkdir()
            (root / "root/pyproject.toml").write_text('[project]\nname="svc"\n')
            roster, _ = _init(root, tmp)
            ids = [m["id"] for m in roster["members"]]
            self.assertEqual(len(ids), len(set(ids)))
            owners = {m["id"]: m["repos"] for m in roster["members"] if m.get("repos")}
            self.assertEqual(owners["root"], ["."])
            self.assertEqual(owners["root-2"], ["root"])
            files = {m["knowledge"] for m in roster["members"] if m.get("knowledge")}
            self.assertEqual(len(files), len([m for m in roster["members"] if m.get("knowledge")]))
            self.assertTrue((root / ".claude/agents/root.md").is_file())
            self.assertTrue((root / ".claude/agents/root-2.md").is_file())

    def test_service_named_like_a_fixed_member_does_not_collide(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mono"
            (root / ".git").mkdir(parents=True)
            for name in ("pm", "tester", "api"):
                (root / name).mkdir()
                (root / name / "pyproject.toml").write_text('[project]\nname="%s"\n' % name)
            roster, _ = _init(root, tmp)
            ids = [m["id"] for m in roster["members"]]
            self.assertEqual(len(ids), len(set(ids)))
            by_repo = {r: m["id"] for m in roster["members"] for r in m.get("repos") or []}
            self.assertEqual(by_repo["pm"], "pm-2")
            self.assertEqual(by_repo["tester"], "tester-2")
            self.assertEqual(by_repo["api"], "api")
            self.assertIn("Project Manager", next(m["role"] for m in roster["members"] if m["id"] == "pm"))

    def test_root_owner_keeps_the_root_but_is_scoped_once_a_service_appears(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._single_package_repo(tmp)
            first, _ = _init(root, tmp)
            self.assertNotIn("service folders", next(m for m in first["members"] if m["id"] == "root")["duty"])
            (root / "svc").mkdir()
            (root / "svc/pyproject.toml").write_text('[project]\nname="svc"\n')
            second, out = _init(root, tmp)
            owner = next(m for m in second["members"] if m["id"] == "root")
            self.assertEqual(owner["repos"], ["."])
            self.assertEqual(owner["duty"].count("service folders"), 1)
            self.assertTrue(any("still owns the repository root" in str(c.args[0]) for c in out.call_args_list if c.args))
            third, _ = _init(root, tmp)  # idempotent: the note is not appended twice
            self.assertEqual(next(m for m in third["members"] if m["id"] == "root")["duty"].count("service folders"), 1)
