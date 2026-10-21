"""Team files written in another encoding (PowerShell 5.1's ANSI codepage) or with a UTF-8 BOM still load."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from aiset import brain, brief_index, core, init_team, registry, settings, sync_names, workspace  # noqa: E402

CP1254 = "Görev tamamlandı".encode("cp1254")  # not valid UTF-8


class EncodingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, data):
        path = os.path.join(self.tmp.name, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def patch(self, module, name, value):
        self.addCleanup(setattr, module, name, getattr(module, name))
        setattr(module, name, value)

    def test_text_readers_replace_a_bad_byte(self):
        log = self.write("tasks/t1/log.md", b"# Log\n" + CP1254 + b"\n")
        self.assertIn("G�rev", core._read(log))

        self.patch(core, "KNOWLEDGE", self.tmp.name)
        self.patch(brain, "KNOWLEDGE", self.tmp.name)
        brief = self.write("api.md", b"> header\n## Field notes\n- " + CP1254 + b"\n")
        self.assertTrue(core.knowledge_info("api.md")["exists"])
        self.assertEqual([s[1] for s in brain.brief_sections("api.md")], ["Field notes"])
        self.assertIn("Field notes", brief_index.build(brief))

        self.patch(brain, "EPISODES", self.tmp.name + "/episodes")
        self.write("episodes/e1.md", b"TASK: " + CP1254 + b"\n")
        self.assertEqual(len(brain.read_episodes()), 1)

    def test_name_sync_keeps_bytes_it_does_not_understand(self):
        self.patch(sync_names, "AGENTS", self.tmp.name)
        path = self.write("backend.md", b'description: "Emre \xc2\xb7 Backend"\n'
                          b"You are **Emre, the Backend Engineer**.\n" + CP1254 + b"\n")
        roster = {"members": [{"id": "backend", "name": "Ali"}]}
        self.assertEqual(sync_names.sync(roster), ["backend"])
        with open(path, "rb") as f:
            data = f.read()
        self.assertIn(b"You are **Ali, the Backend Engineer**", data)
        self.assertIn(CP1254, data)

    def test_json_readers_accept_a_bom(self):
        bom = b"\xef\xbb\xbf"
        roster = self.write("team/roster.json", bom + b'{"team": "Shop", "members": []}')
        self.patch(workspace, "ROSTER", roster)
        self.assertEqual(workspace.load_roster()["team"], "Shop")

        self.patch(settings, "PATH", self.write("team/settings.json", bom + b'{"ui": {"tabs": {"board": false}}}'))
        self.assertFalse(settings.load()["ui"]["tabs"]["board"])

        app = self.write("app/package.json", bom + b'{"dependencies": {"react": "19"}}')
        self.assertEqual(init_team.detect(os.path.dirname(app))[0], "frontend")

    def test_registry_accepts_a_bom(self):
        old = os.environ.get("AISET_HOME")
        self.addCleanup(lambda: os.environ.pop("AISET_HOME", None) if old is None else os.environ.update(AISET_HOME=old))
        os.environ["AISET_HOME"] = os.path.join(self.tmp.name, "home")
        ws = os.path.join(self.tmp.name, "shop")
        self.write("shop/.claude/team/roster.json", b'{"team": "Shop", "members": []}')
        self.write("home/workspaces.json", b"\xef\xbb\xbf" + json.dumps({"workspaces": [{"path": ws, "team": "Shop"}]}).encode())
        self.assertEqual([w["team"] for w in registry.workspaces()], ["Shop"])


if __name__ == "__main__":
    unittest.main()
