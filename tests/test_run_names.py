"""P8 board_slug / branch_name (src/aiset/run/names.py). The stub lowercases and dashes; extend this file with
interfaces.md "P8" (NFKD, length cuts, git ref rules) when you replace it."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from aiset import core  # noqa: E402
from aiset.run.names import board_slug, branch_name  # noqa: E402


class NamesTest(unittest.TestCase):
    def test_example(self):
        self.assertEqual(board_slug(123, "Crash when the roster is empty!"), "issue-123-crash-when-the-roster-is-empty")
        self.assertEqual(branch_name(123, "Crash when the roster is empty!"), "aiset/issue-123-crash-when-the-roster-is-empty")

    def test_no_title_left(self):
        self.assertEqual(board_slug(5, "!!!"), "issue-5")
        self.assertEqual(board_slug(5, ""), "issue-5")

    def test_board_id_matches_task_id(self):
        for title in ("fix: login ../../etc", "x.lock", "Ünïcode tïtle"):
            bid = "2026-10-29-" + board_slug(9, title)
            self.assertRegex(bid, "^" + core.TASK_ID + "$")
            self.assertFalse(re.search(r"\.\.|[~^:?*\[\\ ]|\.lock$", branch_name(9, title)), title)

    def test_length_capped_at_a_dash(self):  # integration check F8: the stub already keeps the max_len contract
        title = "Crash when the roster is empty and the office never starts again after that"
        self.assertEqual(board_slug(123, title), "issue-123-crash-when-the-roster-is-empty")
        self.assertLessEqual(len(branch_name(123, title)), 60)
        self.assertEqual(branch_name(123, title), "aiset/issue-123-crash-when-the-roster-is-empty-and-the")
        self.assertEqual(board_slug(5, "x" * 100), "issue-5")
        self.assertEqual(board_slug(123456789, "word " * 30, max_len=10), "issue-123456789")


if __name__ == "__main__":
    unittest.main()
