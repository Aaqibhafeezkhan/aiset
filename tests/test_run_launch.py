"""The claude command aiset run builds (src/aiset/run/launch.py)."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from aiset.run import gate, launch  # noqa: E402

BOARD = "C:/ws/.claude/team/tasks/2026-10-29-issue-123-crash"


class ArgvTest(unittest.TestCase):
    def test_new_session(self):
        argv = launch.claude_argv(BOARD, "sid-1", model="sonnet", name="aiset run #123")
        self.assertEqual(argv[1:5], ["--agent", "pm", "--session-id", "sid-1"])
        self.assertEqual(argv[argv.index("--settings") + 1], BOARD + "/gate-settings.json")
        self.assertEqual(argv[argv.index("--model") + 1], "sonnet")
        deny = argv[argv.index("--disallowedTools") + 1:argv.index("--")]
        self.assertEqual(tuple(deny), launch.DENY)
        self.assertIn("Bash(gh issue:*)", deny)
        # --disallowedTools takes several values: the prompt must come after `--` or claude reads it as a rule
        self.assertEqual(argv[-2], "--")
        self.assertIn(BOARD, argv[-1])

    def test_prompt_is_one_cmd_safe_line(self):
        prompt = launch.start_prompt(BOARD)
        self.assertNotRegex(prompt, r'[\r\n"%^&|<>!]')
        for must in ("issue.md", "data, not instructions", "STATUS: ready", "summary.md", "/exit"):
            self.assertIn(must, prompt)
        self.assertNotIn("{{", prompt)

    def test_resume_has_no_prompt(self):
        argv = launch.claude_argv(BOARD, "sid-1", resume=True)
        self.assertEqual(argv[argv.index("--resume") + 1], "sid-1")
        self.assertNotIn("--session-id", argv)
        self.assertNotIn("--", argv)

    def test_gate_settings_file(self):
        with tempfile.TemporaryDirectory() as d:
            with open(launch.write_gate_settings(d), encoding="utf-8") as f:
                hooks = json.load(f)["hooks"]["PreToolUse"]
        self.assertEqual(hooks[0]["matcher"], "*")
        cmd = hooks[0]["hooks"][0]["command"]
        self.assertTrue(cmd.endswith('/run/gate.py"'), cmd)
        self.assertNotIn("\\", cmd)
        # integration re-check K3: a gate that times out or fails blocks (claude 2.1.312 settings schema)
        self.assertEqual(hooks[0]["hooks"][0]["timeout"], launch.HOOK_TIMEOUT)
        self.assertGreater(launch.HOOK_TIMEOUT, gate.LOOKUP_DEADLINE * 2)
        self.assertEqual(hooks[0]["hooks"][0]["onFailure"], "block")

    def test_claude_is_resolved_outside_the_workspace(self):  # K1
        self.assertEqual(launch.claude_argv(BOARD, "s")[0], "claude")
        with mock.patch.object(gate, "resolve_program", return_value="C:/bin/claude.cmd") as resolve, \
                mock.patch.object(launch.subprocess, "call", return_value=0) as call:
            self.assertEqual(launch.run_claude(["claude", "--agent", "pm"], "C:/ws"), 0)
        self.assertEqual(call.call_args[0][0], ["C:/bin/claude.cmd", "--agent", "pm"])
        self.assertIn("C:/ws", resolve.call_args[0])
        with mock.patch.object(gate, "resolve_program", return_value=None), \
                mock.patch.object(launch.subprocess, "call") as call:
            with self.assertRaises(launch.RunError):
                launch.run_claude(["claude"], "C:/ws")
        call.assert_not_called()


class CheckPathTest(unittest.TestCase):  # integration check F9
    def test_cmd_unsafe_board_paths_refused_on_windows(self):
        for path in ("C:/a&b/tasks/x", "C:/%USERPROFILE%/x", "C:/hi!/x", "C:/a,b/x", 'C:/a"b'):
            with self.assertRaises(launch.RunError, msg=path):
                launch.check_path(path, windows=True)
            launch.check_path(path, windows=False)  # POSIX: no cmd.exe in between
        launch.check_path("C:/Users/me/My Projects (old)/ws/.claude/team/tasks/2026-10-29-issue-1-x", windows=True)


class PermissionWarningsTest(unittest.TestCase):
    def test_bypass_and_auto_warn(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as ws:
            os.makedirs(os.path.join(ws, ".claude"))
            with open(os.path.join(ws, ".claude", "settings.local.json"), "w") as f:
                json.dump({"permissions": {"defaultMode": "bypassPermissions"}}, f)
            with mock.patch("os.path.expanduser", return_value=home):
                out = launch.permission_warnings(ws)
            self.assertEqual(len(out), 1)
            self.assertIn("bypassPermissions", out[0])
            with open(os.path.join(ws, ".claude", "settings.local.json"), "w") as f:
                json.dump({"permissions": {"defaultMode": "default"}}, f)
            with mock.patch("os.path.expanduser", return_value=home):
                self.assertEqual(launch.permission_warnings(ws), [])


if __name__ == "__main__":
    unittest.main()
