"""P5 cost_line / cost_table (src/aiset/run/cost.py). The stub prints only `$x.xx`; add interfaces.md "P5"
(tokens, runs, agents, model families, unknown cost, the table) when you replace it."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from aiset.run.cost import cost_line, cost_table  # noqa: E402

USAGE = {"tokens": {"total": 1930000, "cost": 4.123, "byModel": {"opus": 812000, "sonnet": 1118000}},
         "agents": [{"agent": "pm", "runs": 1, "tokens": {"total": 812000, "cost": 2.1}}], "runs": [{}]}


class CostTest(unittest.TestCase):
    def test_line_starts_with_dollars(self):
        self.assertTrue(cost_line(USAGE).startswith("$4.12"))

    def test_no_usage(self):
        for usage in (None, {}, {"tokens": {"total": 0}}):
            self.assertEqual(cost_line(usage), "cost not available (no transcripts found for this task)")
        self.assertEqual(cost_table(None), "")


if __name__ == "__main__":
    unittest.main()
