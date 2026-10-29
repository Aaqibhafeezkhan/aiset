"""Import-time paths and transcript scanning with an isolated Claude Code home."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SRC = str(Path(__file__).resolve().parents[1] / "src")


def normalized(path):
    value = path.as_posix()
    return value[0].lower() + value[1:] if len(value) > 1 and value[1] == ":" else value


PROBE = """
import json
from aiset import workspace
from aiset.core import Office
print(json.dumps({
    "projects": workspace.PROJECTS,
    "team": workspace.TEAM,
    "agents": workspace.AGENTS,
    "sessions": [t.path for t in Office({"members": []}).scan()],
}))
"""


class ClaudeHomeTest(unittest.TestCase):
    def probe(self, root, claude_home=None, workspace=None):
        env = dict(os.environ)
        for name in ("AISET_CLAUDE_HOME", "AISET_WORKSPACE", "AGENT_OFFICE_WORKSPACE"):
            env.pop(name, None)
        env.update(HOME=str(root / "home"), USERPROFILE=str(root / "home"), PYTHONPATH=SRC)
        if claude_home is not None:
            env["AISET_CLAUDE_HOME"] = claude_home
        if workspace is not None:
            env["AISET_WORKSPACE"] = str(workspace)
        result = subprocess.run([sys.executable, "-c", PROBE], cwd=root, env=env,
                                capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        data["sessions"] = [path.replace("\\", "/") for path in data["sessions"]]
        return data

    def session(self, home, slug="synthetic-project"):
        path = home / "projects" / slug / "session.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text('{"type":"user","message":{"role":"user","content":"synthetic"}}\n', encoding="utf-8")
        return normalized(path)

    def test_override_redirects_fallback_paths_and_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            alternate = root / "alternate"
            session = self.session(alternate)
            # A real-home decoy must not leak into the isolated office.
            self.session(root / "home" / ".claude")
            before = sorted(p.relative_to(root / "home").as_posix() for p in (root / "home").rglob("*"))
            result = self.probe(root, str(alternate))
            self.assertEqual(result["projects"], normalized(alternate / "projects"))
            self.assertEqual(result["team"], normalized(alternate / "team"))
            self.assertEqual(result["agents"], normalized(alternate / "agents"))
            self.assertEqual(result["sessions"], [session])
            self.assertEqual(sorted(p.relative_to(root / "home").as_posix() for p in (root / "home").rglob("*")), before)

    def test_override_does_not_create_default_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            self.probe(root, str(root / "alternate"))
            self.assertFalse((root / "home").exists())

    def test_unset_and_empty_override_keep_default_paths(self):
        for value in (None, ""):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                home = root / "home" / ".claude"
                session = self.session(home)
                result = self.probe(root, value)
                self.assertEqual(result["projects"], normalized(home / "projects"))
                self.assertEqual(result["team"], normalized(home / "team"))
                self.assertEqual(result["agents"], normalized(home / "agents"))
                self.assertEqual(result["sessions"], [session])

    def test_workspace_keeps_its_team_with_alternate_transcripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            workspace = root / "workspace"
            workspace.mkdir()
            result = self.probe(root, str(root / "alternate"), workspace)
            self.assertEqual(result["projects"], normalized(root / "alternate" / "projects"))
            self.assertEqual(result["team"], normalized(workspace / ".claude" / "team"))
            self.assertEqual(result["agents"], normalized(workspace / ".claude" / "agents"))

    def test_override_expands_tilde(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            result = self.probe(root, "~/alternate")
            self.assertEqual(result["projects"], normalized(root / "home" / "alternate" / "projects"))

    def test_relative_override_is_resolved_from_launch_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            session = self.session(root / "alternate")
            result = self.probe(root, "alternate")
            self.assertEqual(result["projects"], normalized(root / "alternate" / "projects"))
            self.assertEqual(result["sessions"], [session])


if __name__ == "__main__":
    unittest.main()
