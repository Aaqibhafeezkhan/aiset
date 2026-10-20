"""Workspace slug and the session filter: matching Claude Code's project folders."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from aiset import core  # noqa: E402
from aiset.workspace import slug  # noqa: E402


KEEP = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")


def claude_code_folder(path):
    """How Claude Code names a project folder: keep [A-Za-z0-9] per UTF-16 unit, then lowercase.

    Mirrors the JS behaviour the office has to match. Encoding to UTF-16 and
    walking it two bytes at a time is what makes an emoji cost two dashes: it is
    one character but two code units, and neither unit is alphanumeric.
    """
    units = path.encode("utf-16-le")
    out = []
    for i in range(0, len(units), 2):
        unit = units[i] | (units[i + 1] << 8)
        ch = chr(unit)
        out.append(ch if ch in KEEP else "-")
    return "".join(out).lower()


class SlugTest(unittest.TestCase):
    def test_ascii_paths_are_unchanged(self):
        """The common case must not move: lowercase, everything else a dash."""
        self.assertEqual(slug("C:\\Users\\ada\\shop"), "c--users-ada-shop")
        self.assertEqual(slug("/home/ada/shop"), "-home-ada-shop")
        self.assertEqual(slug("shop"), "shop")

    def test_dotted_turkish_i_matches_claude_code(self):
        """Regression: "İ".lower() is two characters, so lowercasing first spent two dashes."""
        path = "C:\\Users\\İsmail\\shop"
        self.assertEqual(slug(path), claude_code_folder(path))
        self.assertEqual(slug(path), "c--users--smail-shop")

    def test_non_ascii_letters_match_claude_code(self):
        """"Ü".lower() is "ü"; substituting first keeps it a single dash either way."""
        for path in ("C:\\Users\\Ünsal\\app", "/home/ümit/app", "C:\\work\\ÄÖÜ",
                     "C:\\Users\\İsmail\\shop", "/home/日本/app"):
            self.assertEqual(slug(path), claude_code_folder(path))

    def test_emoji_is_replaced_per_utf16_code_unit(self):
        """An emoji is one character but two UTF-16 units, so it becomes two dashes."""
        path = "C:\\work\\🙂app"
        self.assertEqual(slug(path), claude_code_folder(path))
        self.assertEqual(slug(path), "c--work---app")

    def test_single_characters(self):
        for ch in "azAZ09":
            self.assertEqual(slug(ch), ch.lower())
        for ch in "._ -/\\:":
            self.assertEqual(slug(ch), "-")

    def test_result_is_lowercase(self):
        self.assertEqual(slug("C:\\Work\\APP"), "c--work-app")


class WorkspaceProjectTest(unittest.TestCase):
    """core.workspace_project(): which ~/.claude/projects folders are this workspace's."""

    def setUp(self):
        self.addCleanup(setattr, core, "WS_SLUG", core.WS_SLUG)
        core.WS_SLUG = slug("C:\\work\\app")

    def test_own_folder_matches(self):
        self.assertTrue(core.workspace_project("c--work-app"))

    def test_folder_inside_the_workspace_matches(self):
        self.assertTrue(core.workspace_project("c--work-app-src-api"))

    def test_sibling_folder_does_not_match(self):
        """Regression: a bare startswith let C:\\work\\apples onto the floor."""
        self.assertFalse(core.workspace_project("c--work-apples"))

    def test_numbered_sibling_folder_does_not_match(self):
        self.assertFalse(core.workspace_project("c--work-app2"))

    def test_unrelated_folder_does_not_match(self):
        self.assertFalse(core.workspace_project("c--other-app"))

    def test_case_is_ignored(self):
        self.assertTrue(core.workspace_project("C--Work-App"))

    def test_without_a_workspace_everything_matches(self):
        core.WS_SLUG = None
        self.assertTrue(core.workspace_project("c--work-apples"))


if __name__ == "__main__":
    unittest.main()
