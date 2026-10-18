"""Registry: aiset-init remembers each team, so the office and the <team>-pm launcher work from any folder."""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from aiset import registry  # noqa: E402


def make_workspace(root, name):
    ws = os.path.join(root, name)
    os.makedirs(os.path.join(ws, ".claude", "team"))
    with open(os.path.join(ws, ".claude", "team", "roster.json"), "w") as f:
        f.write('{"team": "%s", "members": []}' % name)
    return ws


class RegistryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.old_home = os.environ.get("AISET_HOME")
        os.environ["AISET_HOME"] = os.path.join(self.root, "aiset-home")

    def tearDown(self):
        if self.old_home is None:
            os.environ.pop("AISET_HOME", None)
        else:
            os.environ["AISET_HOME"] = self.old_home
        self.tmp.cleanup()

    def test_register_newest_first_without_duplicates(self):
        shop, blog = make_workspace(self.root, "shop"), make_workspace(self.root, "blog")
        registry.register("Shop", shop)
        registry.register("Blog", blog)
        registry.register("Shop", shop)  # again: moves to the front, still once
        self.assertEqual([w["team"] for w in registry.workspaces()], ["Shop", "Blog"])

    def test_lookup_by_team_name_or_slug(self):
        ws = make_workspace(self.root, "bean")
        registry.register("Bean Board", ws)
        self.assertEqual(registry.lookup("bean board"), ws)
        self.assertEqual(registry.lookup("bean-board"), ws)
        self.assertIsNone(registry.lookup("nope"))
        self.assertEqual(registry.resolve("Bean Board"), ws)
        self.assertEqual(registry.resolve(ws), os.path.abspath(ws))

    def test_workspaces_without_a_team_are_dropped(self):
        ws = make_workspace(self.root, "gone")
        registry.register("gone", ws)
        os.remove(os.path.join(ws, ".claude", "team", "roster.json"))
        self.assertEqual(registry.workspaces(), [])

    def test_enclosing_walks_up(self):
        ws = make_workspace(self.root, "shop")
        deep = os.path.join(ws, "api", "app")
        os.makedirs(deep)
        self.assertEqual(registry.enclosing(deep), os.path.abspath(ws))
        self.assertIsNone(registry.enclosing(self.root))


class LauncherTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = os.path.join(self.tmp.name, "bin")
        self.ws = os.path.join(self.tmp.name, "my shop")
        os.makedirs(self.ws)

    def tearDown(self):
        self.tmp.cleanup()

    def test_writes_a_launcher_that_starts_the_pm_in_the_workspace(self):
        path = registry.write_launcher("My Shop", self.ws, self.bin)
        self.assertEqual(os.path.basename(path), "my-shop-pm.cmd" if os.name == "nt" else "my-shop-pm")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("claude --agent pm", text)
        self.assertIn(self.ws, text)

    def test_rewrites_its_own_launcher_but_not_a_foreign_command(self):
        first = registry.write_launcher("shop", self.ws, self.bin)
        self.assertEqual(registry.write_launcher("shop", self.ws, self.bin), first)
        with open(first, "w") as f:
            f.write("someone else's tool\n")
        self.assertIsNone(registry.write_launcher("shop", self.ws, self.bin))

    @unittest.skipUnless(os.name == "nt", "cmd.exe launcher")
    def test_cmd_launcher_changes_into_the_workspace(self):
        # a stand-in claude.cmd that prints the folder it was started in and its arguments
        with open(os.path.join(self.tmp.name, "claude.cmd"), "w") as f:
            f.write("@echo %CD% %*\n")
        path = registry.write_launcher("shop", self.ws, self.bin)
        env = dict(os.environ, PATH=self.tmp.name + os.pathsep + os.environ["PATH"])
        out = subprocess.run(["cmd", "/c", path, "--model", "haiku"], capture_output=True, text=True, env=env,
                             cwd=self.tmp.name).stdout.strip()
        self.assertEqual(out, self.ws + " --agent pm --model haiku")


if __name__ == "__main__":
    unittest.main()
