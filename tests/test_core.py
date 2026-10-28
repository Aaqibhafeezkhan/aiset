"""Regression tests for Transcript.state using synthetic Claude Code JSONL fixtures."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from aiset import core  # noqa: E402
from aiset.core import DONE, IDLE, OFF, THINKING, WAITING, WORKING, Transcript  # noqa: E402


BASE_TIME = datetime(2026, 10, 23, tzinfo=timezone.utc).timestamp()
FIXTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "transcripts")


class TranscriptStateTest(unittest.TestCase):
    def transcript(self, fixture_name, kind="main"):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = os.path.join(temp_dir.name, fixture_name)
        source = os.path.join(FIXTURE_DIR, fixture_name)
        with open(source, encoding="utf-8") as fixture:
            content = fixture.read()
        with open(path, "w", encoding="utf-8") as fixture:
            fixture.write(content)
        os.utime(path, (BASE_TIME, BASE_TIME))
        transcript = Transcript(path, kind, "synthetic-project")
        transcript.refresh()
        return transcript

    def test_no_parsed_activity_is_off(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "empty.jsonl")
            with open(path, "w", encoding="utf-8") as fixture:
                fixture.write("")
            os.utime(path, (BASE_TIME, BASE_TIME))
            transcript = Transcript(path, "main", "synthetic-project")
            transcript.refresh()
            self.assertEqual(transcript.state(BASE_TIME), (OFF, ""))

    def test_recent_user_message_means_thinking_until_ten_minutes(self):
        transcript = self.transcript("thinking.jsonl")
        self.assertEqual(transcript.state(BASE_TIME + 599)[0], THINKING)
        self.assertEqual(transcript.state(BASE_TIME + 600)[0], IDLE)

    def test_tool_call_is_working_up_to_two_minutes(self):
        transcript = self.transcript("working.jsonl")
        self.assertEqual(transcript.state(BASE_TIME + 119)[0], WORKING)
        self.assertEqual(transcript.state(BASE_TIME + 120)[0], WORKING)

    def test_tool_call_waits_for_approval_after_two_minutes_and_stops_after_thirty(self):
        transcript = self.transcript("working.jsonl")
        state, activity = transcript.state(BASE_TIME + 121)
        self.assertEqual(state, WAITING)
        self.assertTrue(activity.startswith("Waiting for your approval? · "))
        self.assertEqual(transcript.state(BASE_TIME + 1800)[0], WAITING)
        state, activity = transcript.state(BASE_TIME + 1801)
        self.assertEqual(state, IDLE)
        self.assertTrue(activity.startswith("Stopped mid-task · "))

    def test_explicit_question_waits_immediately(self):
        transcript = self.transcript("asking.jsonl")
        state, activity = transcript.state(BASE_TIME)
        self.assertEqual(state, WAITING)
        self.assertIn("Which option should I use?", activity)
        self.assertEqual(transcript.state(BASE_TIME + 1801)[0], WAITING)

    def test_subagent_handback_delivers_report(self):
        transcript = self.transcript("subagent-report.jsonl", kind="sub")
        self.assertEqual(transcript.state(BASE_TIME + 60), (DONE, "Report delivered"))

    def test_subagent_final_text_delivers_report(self):
        transcript = self.transcript("subagent-say.jsonl", kind="sub")
        self.assertEqual(transcript.state(BASE_TIME + 60), (DONE, "Report delivered"))

    def test_subagent_report_is_not_done_after_later_tool_activity(self):
        transcript = self.transcript("subagent-report-then-tool.jsonl", kind="sub")
        self.assertEqual(transcript.report, "Completed the assigned review.")
        self.assertEqual(transcript.state(BASE_TIME + 60)[0], WORKING)

    def test_silent_subagent_stops_only_after_three_minutes(self):
        transcript = self.transcript("subagent-silent.jsonl", kind="sub")
        self.assertEqual(transcript.state(BASE_TIME + 180)[0], WORKING)
        state, activity = transcript.state(BASE_TIME + 181)
        self.assertEqual(state, IDLE)
        self.assertTrue(activity.startswith("Stopped 3m ago (no activity) · "))


def jsonl(record):
    """One compact JSONL line, as Claude Code writes it (the long-file scan matches compact JSON)."""
    return json.dumps(record, separators=(",", ":")) + "\n"


def assistant(msg_id, output_tokens, content=None):
    return jsonl({
        "type": "assistant",
        "timestamp": "2026-10-23T00:00:00Z",
        "message": {
            "id": msg_id,
            "model": "claude-sonnet-4-5",
            "content": content or [{"type": "text", "text": f"reply {msg_id}"}],
            "usage": {"input_tokens": 1, "output_tokens": output_tokens},
        },
    })


def read_call(tool_id, path):
    return [{"type": "tool_use", "id": tool_id, "name": "Read", "input": {"file_path": path}}]


class TranscriptRefreshTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.path = os.path.join(temp_dir.name, "session.jsonl")

    def write(self, text, mode="a"):
        # newline="\n" keeps byte offsets the same on Windows
        with open(self.path, mode, encoding="utf-8", newline="\n") as f:
            f.write(text)

    def transcript(self):
        transcript = Transcript(self.path, "main", "synthetic-project")
        transcript.refresh()
        return transcript

    def snapshot(self, transcript):
        return (dict(transcript.totals), len(transcript.events), transcript.offset, transcript.size)

    def test_appended_lines_are_parsed_once(self):
        self.write(assistant("m1", 10) + assistant("m2", 20), "w")
        transcript = self.transcript()
        self.assertEqual(transcript.totals["output"], 30)
        self.assertEqual(transcript.totals["turns"], 2)
        self.assertEqual(len(transcript.events), 2)

        self.write(assistant("m3", 5) + assistant("m4", 7))
        transcript.refresh()
        self.assertEqual(transcript.totals["output"], 42)
        self.assertEqual(transcript.totals["turns"], 4)
        self.assertEqual(len(transcript.events), 4)
        self.assertEqual(transcript.offset, os.path.getsize(self.path))

        before = self.snapshot(transcript)
        transcript.refresh()
        self.assertEqual(self.snapshot(transcript), before)

    def test_unchanged_file_is_not_parsed_again(self):
        self.write(assistant("m1", 10), "w")
        transcript = self.transcript()
        with mock.patch.object(core, "open", create=True) as opened, \
                mock.patch.object(transcript, "_parse") as parse:
            transcript.refresh()
        opened.assert_not_called()
        parse.assert_not_called()

    def test_partial_last_line_waits_for_its_newline(self):
        self.write(assistant("m1", 10), "w")
        transcript = self.transcript()

        # one complete line plus a half-written one (no trailing newline yet) in the same read
        self.write(assistant("m2", 20))
        complete = os.path.getsize(self.path)
        line = assistant("m3", 5)
        self.write(line[:-1])
        transcript.refresh()
        self.assertEqual(transcript.totals["output"], 30)
        self.assertEqual(len(transcript.events), 2)
        self.assertEqual(transcript.offset, complete)

        self.write("\n")
        transcript.refresh()
        self.assertEqual(transcript.totals["output"], 35)
        self.assertEqual(transcript.totals["turns"], 3)
        self.assertEqual(len(transcript.events), 3)
        self.assertEqual(transcript.offset, os.path.getsize(self.path))

        transcript.refresh()
        self.assertEqual(transcript.totals["output"], 35)
        self.assertEqual(len(transcript.events), 3)

    def test_partial_first_line_is_not_parsed(self):
        self.write(assistant("m1", 10)[:-1], "w")
        transcript = self.transcript()
        self.assertEqual(transcript.offset, 0)
        self.assertEqual(len(transcript.events), 0)
        self.write("\n")
        transcript.refresh()
        self.assertEqual(transcript.totals["output"], 10)
        self.assertEqual(len(transcript.events), 1)

    def test_same_message_on_two_lines_counts_tokens_once(self):
        # Claude Code logs one API message once per content block
        self.write(assistant("m1", 10) + assistant("m1", 10, read_call("t1", "/repo/a.py")), "w")
        transcript = self.transcript()
        self.assertEqual(transcript.totals["output"], 10)
        self.assertEqual(transcript.totals["turns"], 1)
        self.assertEqual(len(transcript.events), 2)

    def test_long_file_replays_only_the_tail_but_counts_the_head(self):
        head = assistant("h1", 100, read_call("t1", "/repo/head.py")) + assistant("h2", 200)
        padding = "".join(assistant(f"p{i}", 0) for i in range(5))
        self.write(head + padding, "w")
        tail = "".join(assistant(f"t{i}", 1) for i in range(5)) + assistant("t5", 1, read_call("t2", "/repo/tail.py"))
        self.write(tail)
        tail_bytes = len(tail.encode("utf-8"))
        self.assertGreater(os.path.getsize(self.path), tail_bytes + 1)

        with mock.patch.object(core, "TAIL_BYTES", tail_bytes + 1):
            transcript = self.transcript()

        self.assertEqual(transcript.totals["output"], 306)
        self.assertEqual(transcript.files[("read", "/repo/head.py")], 1)
        self.assertEqual(transcript.files[("read", "/repo/tail.py")], 1)
        texts = [e["text"] for e in transcript.events]
        self.assertEqual(len(texts), 6)
        self.assertNotIn("Reading head.py", texts)
        self.assertNotIn("reply h2", texts)
        self.assertIn("Reading tail.py", texts)
        self.assertEqual(transcript.offset, os.path.getsize(self.path))

    def test_missing_file_is_ignored(self):
        transcript = Transcript(self.path, "main", "synthetic-project")
        transcript.refresh()
        self.assertEqual((transcript.offset, transcript.size), (0, -1))
        self.assertEqual(len(transcript.events), 0)
        self.assertEqual(transcript.totals, {})


if __name__ == "__main__":
    unittest.main()
