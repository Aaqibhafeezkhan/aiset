"""Task ids: boards named <yyyymmdd>-<slug> (older PM template) and <yyyy-mm-dd>-<slug> are one task."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from aiset import core  # noqa: E402


class TaskIdTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, core, "BOARDS", core.BOARDS)
        self.addCleanup(setattr, core, "EPISODES", core.EPISODES)
        core.BOARDS, core.EPISODES = self.tmp.name + "/tasks", self.tmp.name + "/episodes"
        os.makedirs(core.BOARDS + "/20261017-login-fix")
        os.makedirs(core.EPISODES)
        with open(core.BOARDS + "/20261017-login-fix/brief.md", "w") as f:
            f.write("TITLE: Login\nSTATUS: closed\n")
        with open(core.EPISODES + "/2026-10-17-login-fix.md", "w") as f:
            f.write("TASK: Login\nOUTCOME: ok\n")

    def test_both_formats_match_one_id(self):
        for text in ("BOARD: ~/.claude/team/tasks/20261017-login-fix", "TASK: 2026-10-17-login-fix"):
            self.assertEqual(core.task_id(core.ASSIGN_RE.search(text).group(1)), "2026-10-17-login-fix")
        self.assertEqual(core.WRITE_RE.findall("mkdir -p team/tasks/20261017-x && cat > team/episodes/2026-10-17-x.md"),
                         [("tasks", "20261017-x"), ("episodes", "2026-10-17-x")])

    def test_legacy_board_links_to_episode(self):
        meta = core.task_meta("20261017-login-fix")
        self.assertEqual(meta["id"], "2026-10-17-login-fix")
        self.assertTrue(meta["hasBoard"] and meta["hasEpisode"])
        self.assertEqual((meta["status"], meta["outcome"]), ("closed", "ok"))
        self.assertTrue(core.board_detail("2026-10-17-login-fix")["path"].endswith("20261017-login-fix"))
        self.assertEqual(core.boards(1e9)[0]["id"], "2026-10-17-login-fix")


if __name__ == "__main__":
    unittest.main()
