"""P3 parse_verdicts (src/aiset/run/verdicts.py). The stub reads `AC-n: pass|fail` lines only; add interfaces.md
"P3" (evidence, all statuses, not-mine rule, list markers, fences) when you replace it."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from aiset.run.datatypes import Verdict  # noqa: E402
from aiset.run.verdicts import parse_verdicts  # noqa: E402


class ParseVerdictsTest(unittest.TestCase):
    def test_later_wins_and_unknown_ignored(self):
        out = parse_verdicts([("handoff/root.md", "AC-1: fail\nAC-2: pass"),
                              ("handoff/tester.md", "AC-1: pass\nAC-9: pass")], known=["AC-1", "AC-2"])
        self.assertEqual(out, {"AC-1": Verdict("AC-1", "pass", "", "handoff/tester.md", 1),
                               "AC-2": Verdict("AC-2", "pass", "", "handoff/root.md", 2)})

    def test_empty(self):
        self.assertEqual(parse_verdicts([], ["AC-1"]), {})
        self.assertEqual(parse_verdicts([("a", "")], ["AC-1"]), {})


if __name__ == "__main__":
    unittest.main()
