"""Repository paths and importers stay usable on every supported OS."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from aiset import archmap, teammap  # noqa: E402


class RepositoryPathsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.workspace = tmp.name
        self.repo = os.path.join(self.workspace, "service")
        os.makedirs(self.repo)
        self.git("init", "-q")
        self.git("config", "core.quotepath", "true")

    def git(self, *args):
        return subprocess.run(["git", "-C", self.repo, *args], check=True, capture_output=True)

    def write(self, relative, text):
        path = os.path.join(self.repo, *relative.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def scan(self):
        with patch.object(archmap, "CODE_ROOT", self.workspace):
            return archmap.scan_repo("service")

    def test_workflow_is_detected_with_a_repository_relative_path(self):
        self.write(".github/workflows/ci.yml", "name: CI\non: [push]\njobs: {}\n")

        self.assertIn({"kind": "GitHub Actions", "file": ".github/workflows/ci.yml"},
                      self.scan()["deploy"])

    def test_test_files_do_not_supply_infrastructure_evidence(self):
        self.write("app/cache.py", "import redis\n")
        self.write("tests/test_x.py", "import redis\n")

        redis = next(c for c in self.scan()["components"] if c["id"] == "redis")
        self.assertEqual({e["file"] for e in redis["evidence"]}, {"app/cache.py"})

    def test_dag_directory_is_recognized_without_an_airflow_import(self):
        self.write("jobs/dags/daily.py", "def run():\n    pass\n")

        self.assertEqual(self.scan()["kind"], "pipeline")

    def test_nested_dependency_evidence_uses_forward_slashes(self):
        self.write("config/requirements-dev.txt", "redis>=5\n")

        redis = next(c for c in self.scan()["components"] if c["id"] == "redis")
        self.assertEqual(redis["evidence"][0]["file"], "config/requirements-dev.txt")

    def test_git_files_preserves_unicode_and_spaces(self):
        expected = {"app/ürün.py", "app/space name.py"}
        for path in expected | {"lib/generated.d.ts", "vendor/node_modules/ignored.py"}:
            self.write(path, "")
        self.git("add", ".")

        self.assertEqual(set(teammap.git_files(self.repo, ["*.py", "*.ts"])), expected)

    @unittest.skipIf(os.name == "nt", "Windows filenames cannot contain tabs or newlines")
    def test_git_files_preserves_tabs_and_newlines(self):
        expected = {"app/tab\tname.py", "app/line\nname.py"}
        for path in expected:
            self.write(path, "")
        self.git("add", ".")

        self.assertEqual(set(teammap.git_files(self.repo, ["*.py"])), expected)

    def test_symbol_in_a_unicode_filename_is_indexed(self):
        self.write("app/ürün.py", "def urun_total():\n    return 42\n")
        self.git("add", ".")
        with patch.object(teammap, "CODE_ROOT", self.workspace), \
                patch.object(teammap, "INDEX", os.path.join(self.workspace, "index")):
            repo = teammap.load_repo("service")
        output = io.StringIO()
        with redirect_stdout(output):
            teammap.cmd_symbol([repo], teammap.link([repo]), ["urun_total"], 5)

        self.assertIn("service/app/ürün.py:1-2", output.getvalue())


def ts(*specs):
    return {"lang": "ts", "data": {"imports": [{"from": spec} for spec in specs]}}


class FileCommandImportersTest(unittest.TestCase):
    def output(self, repo, path):
        out = io.StringIO()
        with patch.object(teammap, "episodes_touching", return_value=[]), redirect_stdout(out):
            teammap.cmd_file([repo], {"endpoints": [], "apifns": []}, [path], 5)
        return out.getvalue()

    def test_typescript_importers_resolve_relative_index_paths(self):
        repo = {"name": "web", "root": "/nowhere", "files": {
            "src/page.tsx": ts("./api"),
            "src/api/index.ts": ts(),
        }}

        self.assertIn("imported by 1: src/page.tsx", self.output(repo, "src/api/index.ts"))

    def test_typescript_importers_resolve_tsconfig_aliases_once_per_file(self):
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, "tsconfig.json"), "w", encoding="utf-8") as f:
                json.dump({"compilerOptions": {"paths": {"@/*": ["src/*"]}}}, f)
            repo = {"name": "web", "root": root, "files": {
                "src/page.tsx": ts("@/api/items", "@/api/items"),
                "src/api/items.ts": ts(),
            }}

            self.assertIn("imported by 1: src/page.tsx", self.output(repo, "src/api/items.ts"))

    def test_python_importers_resolve_relative_imports(self):
        repo = {"name": "service", "root": "/nowhere", "files": {
            "app/main.py": {"lang": "py", "data": teammap.py_extract("from . import worker\n")},
            "app/worker.py": {"lang": "py", "data": teammap.py_extract("def work():\n    pass\n")},
        }}

        self.assertIn("imported by 1: app/main.py", self.output(repo, "app/worker.py"))


if __name__ == "__main__":
    unittest.main()
