"""Regression tests for Transcript.state using synthetic Claude Code JSONL fixtures."""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

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


if __name__ == "__main__":
    unittest.main()
