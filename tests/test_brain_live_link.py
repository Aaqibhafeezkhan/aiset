"""Keep Brain's live-agent link as a one-time navigation hint."""

import unittest
from pathlib import Path


class BrainLiveLinkTest(unittest.TestCase):
    def test_live_hash_is_consumed_after_a_matching_agent_is_found(self):
        path = Path(__file__).resolve().parents[1] / "src" / "aiset" / "static" / "brain.html"
        source = path.read_text(encoding="utf-8")
        start = source.index("if (!follow) {", source.index("async function loadLive()"))
        end = source.index("  renderLive();", start)
        handler = source[start:end]

        self.assertIn("new URLSearchParams(location.hash.slice(1))", handler)
        self.assertIn('const agentId = hash.get("live");', handler)
        self.assertIn("const a = agentId && LIVE.agents.find", handler)
        self.assertLess(handler.index("if (a) {"), handler.index('hash.delete("live");'))
        self.assertLess(handler.index('hash.delete("live");'), handler.index("history.replaceState"))
        self.assertLess(handler.index("history.replaceState"), handler.index("follow = a.key"))
        self.assertIn("hash.toString()", handler)


if __name__ == "__main__":
    unittest.main()
