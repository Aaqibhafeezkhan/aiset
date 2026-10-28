"""Regression tests for Transcript.state using synthetic Claude Code JSONL fixtures."""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from aiset.core import (  # noqa: E402
    DONE,
    IDLE,
    OFF,
    THINKING,
    WAITING,
    WORKING,
    Transcript,
    bash_targets,
    describe_tool,
)


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


class DescribeToolTest(unittest.TestCase):
    def test_bash_test_runners_are_test(self):
        for cmd in ("pytest -q tests", "npm test", "npm run test -- --watch=false", "ruff check src"):
            with self.subTest(cmd=cmd):
                self.assertEqual(describe_tool("Bash", {"command": cmd}), ("test", cmd))

    def test_other_bash_commands_are_shell(self):
        self.assertEqual(describe_tool("Bash", {"command": "ls -la"}), ("shell", "ls -la"))

    def test_bash_description_wins_over_the_command(self):
        inp = {"command": "pytest -q", "description": "Run the unit tests"}
        self.assertEqual(describe_tool("Bash", inp), ("test", "Run the unit tests"))

    def test_bash_command_is_clipped(self):
        kind, text = describe_tool("Bash", {"command": "echo " + "x" * 200})
        self.assertEqual(kind, "shell")
        self.assertEqual(len(text), 120)
        self.assertTrue(text.endswith("…"))

    def test_file_tools_show_the_base_name(self):
        self.assertEqual(describe_tool("Read", {"file_path": "/repo/src/a.py"}), ("read", "Reading a.py"))
        self.assertEqual(describe_tool("Edit", {"file_path": "/repo/src/a.py"}), ("edit", "Editing a.py"))
        self.assertEqual(describe_tool("Write", {"file_path": "/repo/b.md"}), ("edit", "Writing b.md"))
        self.assertEqual(
            describe_tool("NotebookEdit", {"notebook_path": "/repo/nb/c.ipynb"}),
            ("edit", "Editing c.ipynb"),
        )

    def test_search_tools_show_the_pattern(self):
        self.assertEqual(describe_tool("Grep", {"pattern": "def main"}), ("search", "Searching for def main"))
        self.assertEqual(describe_tool("Glob", {"pattern": "**/*.py"}), ("search", "Searching for **/*.py"))

    def test_delegation_shows_the_agent_and_description(self):
        inp = {"subagent_type": "reviewer", "description": "Review the diff"}
        self.assertEqual(describe_tool("Agent", inp), ("delegate", "Assigned reviewer: Review the diff"))
        self.assertEqual(describe_tool("Task", inp), ("delegate", "Assigned reviewer: Review the diff"))
        self.assertEqual(
            describe_tool("Task", {"description": "Look around"}),
            ("delegate", "Assigned an agent: Look around"),
        )

    def test_ask_user_question_shows_the_first_question(self):
        inp = {"questions": [{"question": "Ship it?"}, {"question": "Really?"}]}
        self.assertEqual(describe_tool("AskUserQuestion", inp), ("ask", "Asking you: Ship it?"))

    def test_web_tools(self):
        self.assertEqual(describe_tool("WebSearch", {"query": "python 3.9"}), ("web", "Web: python 3.9"))
        self.assertEqual(
            describe_tool("WebFetch", {"url": "https://example.com"}),
            ("web", "Web: https://example.com"),
        )

    def test_mcp_tools_use_the_tool_name(self):
        self.assertEqual(describe_tool("mcp__server__some_tool", {}), ("tool", "Using some tool"))

    def test_unknown_tools_fall_back_to_the_name(self):
        self.assertEqual(describe_tool("MysteryTool", {"x": 1}), ("tool", "MysteryTool"))

    def test_missing_input_does_not_crash(self):
        for name in ("Bash", "Read", "Edit", "Write", "NotebookEdit", "Grep", "Glob", "Agent", "Task",
                     "SendMessage", "AskUserQuestion", "WebSearch", "WebFetch", "Skill", "mcp__s__t", "Other"):
            with self.subTest(name=name):
                kind, text = describe_tool(name, None)
                self.assertIsInstance(kind, str)
                self.assertIsInstance(text, str)


class BashTargetsTest(unittest.TestCase):
    """Expected paths go through os.path.normpath, as bash_targets does, so they match on Windows too."""

    def test_read_commands(self):
        self.assertEqual(bash_targets("cat a.py"), [("read", "a.py", None)])
        self.assertEqual(bash_targets("head -n 20 a.py"), [("read", "a.py", None)])
        self.assertEqual(bash_targets("tail -n 5 a.py b.md"), [("read", "a.py", None), ("read", "b.md", None)])

    def test_sed_print_range_is_a_read_with_lines(self):
        self.assertEqual(bash_targets("sed -n 10,20p a.py"), [("read", "a.py", "10–20")])

    def test_sed_in_place_is_an_edit(self):
        self.assertEqual(bash_targets("sed -i 's/x/y/' a.py"), [("edit", "a.py", None)])

    def test_redirect_and_tee_are_edits(self):
        self.assertEqual(bash_targets("echo hi > out.txt"), [("edit", "out.txt", None)])
        self.assertEqual(bash_targets("echo hi >> out.txt"), [("edit", "out.txt", None)])
        self.assertEqual(bash_targets("echo hi | tee out.txt"), [("edit", "out.txt", None)])

    def test_grep_searches_the_path_not_the_pattern(self):
        self.assertEqual(
            bash_targets("grep -n foo src/a.py"),
            [("search", os.path.normpath("src/a.py"), None)],
        )

    def test_grep_with_dash_e_has_no_positional_pattern(self):
        self.assertEqual(bash_targets("grep -e foo a.py"), [("search", "a.py", None)])

    def test_cd_resolves_relative_paths(self):
        self.assertEqual(
            bash_targets("cd /repo && cat a.py"),
            [("read", os.path.normpath(os.path.join("/repo", "a.py")), None)],
        )

    def test_variable_assignments_are_expanded(self):
        self.assertEqual(
            bash_targets("T=/repo; cat $T/a.py"),
            [("read", os.path.normpath("/repo/a.py"), None)],
        )
        self.assertEqual(
            bash_targets('T="/repo"; cat ${T}/a.py'),
            [("read", os.path.normpath("/repo/a.py"), None)],
        )

    def test_heredoc_body_is_not_read_as_commands(self):
        cmd = "cat > f.py <<'EOF'\ncat secret.py\nrm -rf b.py\nEOF"
        self.assertEqual(bash_targets(cmd), [("edit", "f.py", None)])

    def test_globs_urls_and_unknown_commands_add_nothing(self):
        for cmd in ("cat *.py", "cat https://example.com/a.py", "python x.py", "rm a.py", ""):
            with self.subTest(cmd=cmd):
                self.assertEqual(bash_targets(cmd), [])

    def test_paths_without_an_extension_are_dropped_unless_they_exist(self):
        self.assertEqual(bash_targets("cat no-such-file-here"), [])
        with tempfile.TemporaryDirectory() as tmp:
            # Single quotes keep Windows backslashes through shlex.
            self.assertEqual(
                bash_targets(f"ls '{tmp}'"),
                [("search", os.path.normpath(tmp), None)],
            )


if __name__ == "__main__":
    unittest.main()
