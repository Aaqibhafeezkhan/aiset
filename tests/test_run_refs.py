"""P7 parse_issue_ref (src/aiset/run/refs.py). The stub handles digits and a plain issue URL; extend this file
with the rest of interfaces.md "P7" when you replace it."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from aiset.run.datatypes import IssueRef  # noqa: E402
from aiset.run.refs import parse_issue_ref  # noqa: E402


class ParseIssueRefTest(unittest.TestCase):
    def test_bare_number_uses_the_default_repo(self):
        self.assertEqual(parse_issue_ref("58", default_repo="JamshidS/aiset"), IssueRef("JamshidS/aiset", 58))
        self.assertEqual(parse_issue_ref(" 7 "), IssueRef(None, 7))

    def test_issue_url(self):
        self.assertEqual(parse_issue_ref("https://github.com/JamshidS/aiset/issues/58"), IssueRef("JamshidS/aiset", 58))

    def test_errors_are_value_errors(self):
        for bad in ("0", "abc", "", "https://github.com/JamshidS/aiset/pull/45"):
            with self.assertRaises(ValueError, msg=bad):
                parse_issue_ref(bad)


if __name__ == "__main__":
    unittest.main()
