"""P4 parse_claims / count_claims (src/aiset/run/claims.py). The stub finds labels at the start of a line only; add
interfaces.md "P4" (labels anywhere, evidence, code skipped) when you replace it."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from aiset.run.claims import count_claims, parse_claims  # noqa: E402
from aiset.run.datatypes import Claim  # noqa: E402


class ClaimsTest(unittest.TestCase):
    def test_line_start_labels(self):
        text = "[V] The office needs no change.\n[S] Hooks apply to subagents.\nnot a [V] claim here\n[?] Empty roster file."
        self.assertEqual(parse_claims(text), [Claim("V", "The office needs no change.", "", 1),
                                              Claim("S", "Hooks apply to subagents.", "", 2),
                                              Claim("?", "Empty roster file.", "", 4)])

    def test_counts_have_all_keys(self):
        self.assertEqual(count_claims(""), {"V": 0, "S": 0, "?": 0})
        self.assertEqual(count_claims("[S] a\n[S] b\n[v] lowercase is not a label"), {"V": 0, "S": 2, "?": 0})


if __name__ == "__main__":
    unittest.main()
