"""The office's HTTP surface: task ids can't leave the team folder, and other hosts can't read (DNS rebinding)."""
import os
import sys
import tempfile
import unittest
import unittest.mock


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from aiset import core  # noqa: E402
from aiset.server import Handler  # noqa: E402


class TaskIdTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        team = os.path.join(self.tmp.name, "team")
        self.boards, self.episodes = os.path.join(team, "tasks"), os.path.join(team, "episodes")
        os.makedirs(os.path.join(self.boards, "2026-10-18-fix-bugs"))
        os.makedirs(self.episodes)
        with open(os.path.join(team, "brief.md"), "w") as f:  # what ".." would reach from the boards folder
            f.write("not a task\n")
        with open(os.path.join(self.episodes, "2026-10-18-fix-bugs.md"), "w") as f:
            f.write("TASK: fix bugs\n")
        patches = [unittest.mock.patch.object(core, "BOARDS", self.boards), unittest.mock.patch.object(core, "EPISODES", self.episodes)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_real_task_is_found(self):
        self.assertTrue(core._board_dir("2026-10-18-fix-bugs"))
        self.assertTrue(core._board_dir("20261018-fix-bugs"))  # legacy date format
        self.assertTrue(core._episode_path("2026-10-18-fix-bugs").endswith("2026-10-18-fix-bugs.md"))

    def test_ids_that_leave_the_folder_are_refused(self):
        for bad in ("..", ".", "../..", "a/../..", "..\\..", "", ".hidden", "x\0y"):
            with self.subTest(bad=bad):
                self.assertIsNone(core._board_dir(bad))
                self.assertIsNone(core.board_detail(bad))
                self.assertIsNone(core.task_detail(None, bad))
                path = core._episode_path(bad)
                self.assertTrue(path is None or os.path.dirname(path) == os.path.realpath(self.episodes))


class HostTest(unittest.TestCase):
    def handler(self, host, origin=None):
        h = Handler.__new__(Handler)  # no socket: only the header checks are exercised
        h.port = 8765
        h.headers = {k: v for k, v in (("Host", host), ("Origin", origin)) if v is not None}
        return h

    def test_reads_need_this_servers_host(self):
        self.assertTrue(self.handler("127.0.0.1:8765")._host_ok())
        self.assertTrue(self.handler("localhost:8765")._host_ok())
        for host in ("evil.example:8765", "127.0.0.1:9999", "", None):
            with self.subTest(host=host):
                self.assertFalse(self.handler(host)._host_ok())

    def test_writes_also_refuse_a_foreign_origin(self):
        self.assertTrue(self.handler("127.0.0.1:8765", "http://127.0.0.1:8765")._same_origin())
        self.assertFalse(self.handler("127.0.0.1:8765", "https://evil.example")._same_origin())
        self.assertFalse(self.handler("evil.example:8765")._same_origin())


if __name__ == "__main__":
    unittest.main()
