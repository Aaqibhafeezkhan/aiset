"""Initialize single-package repositories without moving the checkout."""

import fnmatch
import json
import os
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aiset import init_team, research, teammap  # noqa: E402


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
            self.assertEqual([r["name"] for r in init_team.scan(str(root))], ["api", "."])


def _init(root, tmp, *args):
    with patch.dict(os.environ, {"AISET_HOME": str(Path(tmp) / "home")}), \
         patch.object(sys, "argv", ["aiset-init", str(root), "--no-launcher", *args]), \
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
            root_md = (root / ".claude/agents/root.md").read_text(encoding="utf-8")
            self.assertIn("pytest", root_md)  # the root engineer keeps its own checks
            self.assertIn("You own:\n\n- `.` at ", root_md)  # its own unit, not the new service's
            self.assertNotIn("- `svc` (", root_md)
            self.assertTrue(any("owns the repository root; the service folders belong to their own engineers" in str(c.args[0]) for c in out.call_args_list if c.args))
            third, _ = _init(root, tmp)  # idempotent: the note is not appended twice
            self.assertEqual(next(m for m in third["members"] if m["id"] == "root")["duty"].count("service folders"), 1)


class RootPackageOwnershipTest(unittest.TestCase):
    """A monorepo root with a manifest keeps its root unit (id root) alongside service folders."""

    SUPPORT_SHAPES = (("tests", "requirements.txt"), ("scripts", "requirements.txt"),
                      ("tools", "Dockerfile"), ("docs", "package.json"))
    MANIFEST_CONTENT = {"requirements.txt": "somepkg\n",
                        "package.json": '{"scripts": {"test": "node --test"}}',
                        "Dockerfile": "FROM python:3.12\n"}
    SUPPORT_CHECKS = {"requirements.txt": "pytest", "Dockerfile": "docker compose -f <file> config -q"}

    def _indexed_monorepo(self, tmp):
        root = Path(tmp) / "mono"
        root.mkdir()
        files = {
            "package.json": '{"workspaces": ["api", "web", "worker"]}',
            "root.py": "def root_task():\n    pass\n",
            "api/requirements.txt": "fastapi\n",
            "api/main.py": '@app.get("/api/items")\ndef items():\n    return []\n',
            "api/tests/test_main.py": "def test_items():\n    pass\n",
            "web/package.json": '{"scripts": {"test": "node --test"}}',
            "web/app.test.js": "test('app', () => {});\n",
            "worker/requirements.txt": "somepkg\n",
            "worker/jobs.py": "def run_job():\n    pass\n",
        }
        for rel, content in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(root), "add", *files], check=True, capture_output=True)
        roster, _ = _init(root, tmp)
        names = list(dict.fromkeys(r for m in roster["members"] for r in m.get("repos") or []))
        self.assertEqual(set(names), {"api", "web", "worker", "."})
        return root, names

    def test_root_index_lists_service_endpoint_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, names = self._indexed_monorepo(tmp)
            with patch.object(teammap, "REPOS", names), patch.object(teammap, "CODE_ROOT", str(root)), \
                 patch.object(teammap, "INDEX", str(Path(tmp) / "index")):
                linked = teammap.link([teammap.load_repo(n, True) for n in names])
            self.assertEqual([(e["repo"], e["file"]) for e in linked["endpoints"] if e["path"] == "/api/items"],
                             [("api", "main.py")])

    def test_root_index_partitions_tracked_files_across_units(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, names = self._indexed_monorepo(tmp)
            tracked = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], check=True,
                                     capture_output=True, text=True, encoding="utf-8").stdout.split("\0")
            expected = sorted(os.path.normpath(str(root / rel)) for rel in tracked if rel
                              and any(fnmatch.fnmatch(rel, glob) for glob in ("*.py", "*.js")))
            self.assertEqual(len(expected), 5)
            listed = []
            with patch.object(teammap, "REPOS", names), patch.object(teammap, "CODE_ROOT", str(root)), \
                 patch.object(teammap, "INDEX", str(Path(tmp) / "index")):
                for name in names:
                    listed.extend(os.path.normpath(str(root / name / rel))
                                  for rel in teammap.git_files(str(root / name), research.TEST_GLOBS))
            with self.subTest("each file has one unit"):
                self.assertEqual(sorted(path for path, count in Counter(listed).items() if count > 1), [])
            with self.subTest("all tracked sources are kept"):
                self.assertEqual(sorted(set(listed)), expected)

    def test_root_unit_scanned_alongside_support_folder_units(self):
        for folder, manifest in self.SUPPORT_SHAPES:
            with self.subTest(shape=(folder, manifest)):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp) / "mono"
                    (root / ".git").mkdir(parents=True)
                    (root / "pyproject.toml").write_text('[project]\nname="demo"\n')
                    (root / folder).mkdir()
                    (root / folder / manifest).write_text(self.MANIFEST_CONTENT[manifest])
                    expected_units = ["."] if folder == "docs" else [folder, "."]  # scan() skips docs/
                    self.assertEqual([r["name"] for r in init_team.scan(str(root))], expected_units)
                    first, _ = _init(root, tmp)
                    second, _ = _init(root, tmp)
                    self.assertEqual([m["id"] for m in first["members"]], [m["id"] for m in second["members"]])
                    for roster in (first, second):
                        owners = [m for m in roster["members"] if m.get("repos") == ["."]]
                        self.assertEqual(len(owners), 1)
                        self.assertEqual(owners[0]["id"], "root")
                        self.assertEqual(owners[0]["checks"], ["pytest"])
                    if folder != "docs":  # scan() skips docs/, so it gets no engineer anywhere
                        svc = next(m for m in second["members"] if m.get("repos") == [folder])
                        self.assertEqual(svc["checks"], [f"cd {folder} && {self.SUPPORT_CHECKS[manifest]}"])

    def test_root_unit_kept_alongside_a_real_service_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mono"
            (root / ".git").mkdir(parents=True)
            (root / "pyproject.toml").write_text('[project]\nname="demo"\n')
            (root / "api").mkdir()
            (root / "api/pyproject.toml").write_text('[project]\nname="api"\n')
            self.assertEqual([r["name"] for r in init_team.scan(str(root))], ["api", "."])
            roster, out = _init(root, tmp)
            by_repo = {r: m for m in roster["members"] for r in m.get("repos") or []}
            self.assertEqual(by_repo["api"]["id"], "api")
            self.assertEqual(by_repo["."]["id"], "root")
            self.assertIsNot(by_repo["api"], by_repo["."])
            self.assertIn("service folders", by_repo["."]["duty"])
            out.assert_any_call(f"root:    {by_repo['.']['name']} owns the repository root; "
                                "the service folders belong to their own engineers")

    def test_default_group_and_header_count_services_without_root(self):
        for services in (0, 12):
            with self.subTest(services=services), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "mono"
                (root / ".git").mkdir(parents=True)
                (root / "pyproject.toml").write_text('[project]\nname="demo"\n')
                for i in range(services):
                    service = root / f"service{i}"
                    service.mkdir()
                    (service / "requirements.txt").write_text("somepkg\n")
                roster, out = _init(root, tmp)
                with self.subTest("one engineer per repo through twelve services"):
                    self.assertNotEqual(roster.get("group"), "stack")
                with self.subTest("header counts services and keeps root-only singular"):
                    count = services or 1
                    self.assertIn(f"(monorepo, {count} service{'' if count == 1 else 's'},",
                                  out.call_args_list[0].args[0])

    def test_group_stack_scopes_root_owner_when_another_engineer_owns_a_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mono"
            (root / ".git").mkdir(parents=True)
            (root / "package.json").write_text('{}')
            (root / "web").mkdir()
            (root / "web/package.json").write_text('{}')
            (root / "api").mkdir()
            (root / "api/requirements.txt").write_text("somepkg\n")
            roster, _ = _init(root, tmp, "--group", "stack")
            owner = next(m for m in roster["members"] if "." in (m.get("repos") or []))
            self.assertEqual(set(owner["repos"]), {"web", "."})
            self.assertIn("service folders", owner["duty"])

    def test_group_stack_one_engineer_owns_root_and_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mono"
            (root / ".git").mkdir(parents=True)
            (root / "pyproject.toml").write_text('[project]\nname="demo"\n')
            (root / "api").mkdir()
            (root / "api/pyproject.toml").write_text('[project]\nname="api"\n')
            roster, _ = _init(root, tmp, "--group", "stack")
            owners = [m for m in roster["members"] if m.get("repos")]
            self.assertEqual(len(owners), 1)
            self.assertEqual(set(owners[0]["repos"]), {"api", "."})
            self.assertNotIn("service folders", owners[0]["duty"])

    def test_root_without_manifest_stays_unowned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mono"
            (root / ".git").mkdir(parents=True)
            (root / "api").mkdir()
            (root / "api/pyproject.toml").write_text('[project]\nname="api"\n')
            self.assertEqual([r["name"] for r in init_team.scan(str(root))], ["api"])

    def test_root_unit_survives_deleting_the_root_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mono"
            (root / ".git").mkdir(parents=True)
            (root / "pyproject.toml").write_text('[project]\nname="demo"\n')
            _init(root, tmp)
            (root / "pyproject.toml").unlink()
            (root / "api").mkdir()
            (root / "api/pyproject.toml").write_text('[project]\nname="api"\n')
            roster, out = _init(root, tmp)
            owner = next(m for m in roster["members"] if m.get("repos") == ["."])
            self.assertEqual(owner["id"], "root")
            self.assertEqual(owner["checks"], ["pytest"])  # kept from the first init's roster
            self.assertEqual(next(m for m in roster["members"] if m.get("repos") == ["api"])["id"], "api")
            root_md = (root / ".claude/agents/root.md").read_text(encoding="utf-8")
            self.assertIn("You own:\n\n- `.` at ", root_md)  # carry_root_unit kept the root unit in repos
            self.assertNotIn("- `api`", root_md)
            with self.subTest("carried root duty is scoped"):
                self.assertIn("service folders", owner["duty"])
            with self.subTest("carried root scope is announced"):
                out.assert_any_call(f"root:    {owner['name']} owns the repository root; "
                                    "the service folders belong to their own engineers")

    def test_group_stack_keeps_the_root_units_commands_unmasked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mono"
            (root / ".git").mkdir(parents=True)
            (root / "go.mod").write_text("module example.com/mono\n")
            (root / "server").mkdir()
            (root / "server/go.mod").write_text("module example.com/mono/server\n")
            roster, _ = _init(root, tmp, "--group", "stack")
            owner = next(m for m in roster["members"] if m.get("repos") == ["server", "."])
            self.assertEqual(owner["id"], "go-backend")
            agent = (root / ".claude/agents/go-backend.md").read_text(encoding="utf-8")
            self.assertNotIn("go test <service>/", agent)  # masking the root unit's name ate every dot
            self.assertIn("go test ./...", agent)
            self.assertIn("cd <service> && go test ./...", agent)  # service folders stay masked
