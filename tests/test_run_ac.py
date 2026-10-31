"""P2 extract_ac (src/aiset/run/ac.py). The stub reads task-list lines only; add interfaces.md "P2" (AC-n lines,
sections, fences and HTML comments skipped, max_len) when you replace it."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from aiset.run.ac import extract_ac  # noqa: E402
from aiset.run.datatypes import AcItem, AcResult  # noqa: E402


class ExtractAcTest(unittest.TestCase):
    def test_task_list(self):
        r = extract_ac("Crash.\n\n- [ ] `aiset` starts with 0 members\n- [x] a test covers it\n")
        self.assertEqual(r, AcResult((AcItem("AC-1", "`aiset` starts with 0 members", 3),
                                      AcItem("AC-2", "a test covers it", 4)), "tasklist", 0))

    def test_none(self):
        self.assertEqual(extract_ac(""), AcResult((), "none", 0))
        self.assertEqual(extract_ac("just prose"), AcResult((), "none", 0))

    def test_max_items(self):
        r = extract_ac("".join(f"- [ ] item {i}\n" for i in range(25)))
        self.assertEqual((len(r.items), r.dropped, r.items[-1].id), (20, 5, "AC-20"))


if __name__ == "__main__":
    unittest.main()
