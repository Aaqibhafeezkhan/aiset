"""P1a visible_text (src/aiset/run/sanitize.py). The stub returns text unchanged; these tests pin the contract the
real one must keep. Add interfaces.md "P1a" cases (zero-width, bidi, tags, controls, HTML comments) when you
replace it."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from aiset.run.datatypes import Visible  # noqa: E402
from aiset.run.sanitize import visible_text  # noqa: E402


class VisibleTextTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(visible_text(""), Visible("", {}))

    def test_plain_text_is_unchanged_with_no_counts(self):
        text = "Crash on empty roster.\n\t- naïve, 日本語, 👩‍💻"
        v = visible_text(text)
        self.assertIsInstance(v, Visible)
        self.assertEqual((v.text, v.counts), (text, {}))


if __name__ == "__main__":
    unittest.main()
