"""usage_cost prices older models at their own list prices, and Haiku 5.5's long prompts at its higher rate."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from aiset.core import usage_cost  # noqa: E402

# 1000 input, 500 output, 10,000 cache read, 1,500 written for 5 minutes and 500 for 1 hour
USAGE = {
    "input_tokens": 1000,
    "output_tokens": 500,
    "cache_read_input_tokens": 10_000,
    "cache_creation_input_tokens": 2000,
    "cache_creation": {"ephemeral_5m_input_tokens": 1500, "ephemeral_1h_input_tokens": 500},
}


class UsageCostTest(unittest.TestCase):
    def test_older_models_use_their_own_prices(self):
        expected = {
            # 1000*5 + 500*25 + 10000*0.50 + 1500*6.25 + 500*10
            "claude-opus-4-8": 0.036875,
            "claude-opus-4-7": 0.036875,
            "claude-opus-4-6": 0.036875,
            # 1000*3 + 500*15 + 10000*0.30 + 1500*3.75 + 500*6
            "claude-sonnet-4-6": 0.022125,
            # 1000*1 + 500*5 + 10000*0.10 + 1500*1.25 + 500*2
            "claude-haiku-4-5": 0.007375,
            "claude-haiku-4-5-20251001": 0.007375,
        }
        for model, cost in expected.items():
            with self.subTest(model=model):
                self.assertAlmostEqual(usage_cost(model, USAGE), cost, places=9)

    def test_current_models_are_unchanged(self):
        # 1000*4 + 500*20 + 10000*0.20 + 1500*5 + 500*8
        self.assertAlmostEqual(usage_cost("claude-opus-5-5", USAGE), 0.0275, places=9)
        # 1000*0.10 + 500*0.50 + 10000*0.01 + 1500*0.125 + 500*0.20, a 13,000-token prompt
        self.assertAlmostEqual(usage_cost("claude-haiku-5-5", USAGE), 0.0007375, places=9)

    def test_haiku_5_5_prompts_over_100k_tokens_use_the_long_prompt_rates(self):
        long_prompt = {"input_tokens": 90_000, "cache_read_input_tokens": 20_000, "output_tokens": 1000}
        # 90000*0.50 + 1000*2.50 + 20000*0.05
        self.assertAlmostEqual(usage_cost("claude-haiku-5-5", long_prompt), 0.0485, places=9)
        # exactly 100K stays at the standard rate: 100000*0.10
        at_limit = {"input_tokens": 100_000, "output_tokens": 0}
        self.assertAlmostEqual(usage_cost("claude-haiku-5-5", at_limit), 0.01, places=9)
        # cache writes count toward the prompt: 60000*0.50 + 50000*0.625 (5-minute writes)
        with_writes = {"input_tokens": 60_000, "cache_creation_input_tokens": 50_000}
        self.assertAlmostEqual(usage_cost("claude-haiku-5-5", with_writes), 0.06125, places=9)


if __name__ == "__main__":
    unittest.main()
