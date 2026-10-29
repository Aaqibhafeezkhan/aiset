"""The aiset run session gate (src/aiset/run/gate.py): what it blocks, what it lets through, and the hook protocol."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from aiset.run import gate  # noqa: E402

GATE = os.path.join(HERE, "..", "src", "aiset", "run", "gate.py")


def isolate_git(test):
    """Real git in these tests reads no user or system config (aliases, hooks, templates)."""
    p = mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    p.start()
    test.addCleanup(p.stop)
    for k in ("GIT_TEMPLATE_DIR", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CONFIG", "GIT_CONFIG_COUNT"):
        os.environ.pop(k, None)

BLOCKED = [
    "git push", "git push origin aiset/issue-1-x", "git -C repo push", "git -c a=b --no-pager push -f",
    "cd repo && git push", "make test; git push", "timeout 30 git push", "env -i GIT_TRACE=1 git push",
    "if true; then git push; fi", "(git push)", "echo $(git push)", "echo `git push`", "bash -c 'git push'",
    "sh -lc \"cd x && git push\"", "eval git push", "/usr/bin/git push", "git.exe push", "sudo git push",
    "git remote add fork https://github.com/me/x", "git remote set-url origin x", "git config remote.origin.url x",
    "git config --global url.x.pushInsteadOf y",
    "gh pr create --draft", "gh pr merge 3", "gh pr comment 3 -b hi", "gh -R o/r pr create",
    "gh issue view 1", "gh issue list", "gh issue comment 1 -b x", "gh issue close 1",
    "gh api -X POST repos/o/r/issues", "gh api --method=PATCH repos/o/r", "gh api repos/o/r/issues -f title=t",
    "gh api graphql -F query=@q.graphql", "gh release create v1", "gh repo create x", "gh repo delete x",
    "gh gist create f", "gh workflow run ci", "gh secret set X", "gh extension install x",
    "curl -X POST https://api.github.com/repos/o/r/issues", "curl -d '{}' https://api.github.com/repos/o/r/pulls",
    "curl --json '{}' https://api.github.com/x", "wget --post-data=x https://api.github.com/x",
    "echo \"unbalanced; git push",
    # integration check F3: bypasses found by probe_gate.py
    "git -c alias.x=push x", "git -C . -c alias.x=push x", "git -c alias.x='!git push' x",
    "git --config-env=alias.x=CMD x", "git config alias.p push", "git config --global alias.p push",
    "git config set alias.p push", "git send-pack origin HEAD", "git-send-pack origin HEAD", "git http-push x",
    "git subtree push --prefix x origin main", "git lfs push origin main", "x=$(echo push); git $x",
    "powershell -c git push", "pwsh -NoProfile -Command git push", "powershell -ExecutionPolicy Bypass git push",
    "powershell -EncodedCommand ZwBpAHQAIABwAHUAcwBoAA==", "pwsh -enc ZwBpAHQA", "pwsh -e ZwBpAHQA", "pwsh -ec x",
    "cmd /k git push", "bash -xc 'git push'", "echo push | xargs git", "xargs -I{} git {}", "echo pr | xargs gh",
    "find . -exec git push \\;", "find . -name x -execdir git push {} +", "watch git push", "watch -n 2 git push",
    "Invoke-RestMethod -Uri https://api.github.com/x -Method:Post", "$m='Post'; irm https://api.github.com/x -Method $m",
    "irm https://api.github.com/x -Me Post", "iwr https://api.github.com/x -CustomMethod PATCH",
    "(New-Object Net.WebClient).UploadString('https://api.github.com/x', 'b')",
    # F2: redirecting gate 2's push or running code in it
    "git config core.hooksPath .githooks", "git config --local core.fsmonitor ./x.sh", "git config url.a.insteadOf b",
    "git config remote.origin.pushurl https://evil", "git config --add remote.origin.pushurl https://evil",
    "git config filter.x.clean ./run.sh", "git config include.path ../x", "git config --edit",
    "git config --remove-section alias", "echo 'curl x' > .git/hooks/pre-push", "cp evil .git/hooks/post-commit",
    "tee .git/config < x", "Set-Content .git\\hooks\\pre-push 'x'",
]
ALLOWED = [
    "git status", "git diff HEAD", "git log --oneline -5", "git switch -c x", "git remote -v", "git config user.name",
    "grep -rn \"git push\" docs", "echo 'gh pr create is not run here'", "ls; pwd",
    "gh --version", "gh auth status", "gh pr view 3", "gh pr list", "gh repo view o/r", "gh search issues x",
    "gh api repos/o/r", "gh api -X GET repos/o/r/issues -f state=open", "gh run list",
    "curl https://api.github.com/repos/o/r", "curl -X POST https://example.com/api", "python -m unittest",
    "git config --get remote.origin.url", "git config --list", "git config get alias.x", "git stash push",
    "git commit -m push", "git log --grep push", "git -c core.pager=cat log", "powershell -c git status",
    "pwsh -NoProfile -Command Get-ChildItem", "echo x | xargs git log", "find . -name '*.py' -exec grep -l push {} ;",
    "watch -n 2 git status", "irm https://api.github.com/x -Method Get", "cat .git/config", "ls .git/hooks",
    "bash -c 'git status'", "cmd /c dir",
]


class DecideTest(unittest.TestCase):
    def setUp(self):
        isolate_git(self)

    def test_blocked(self):
        for cmd in BLOCKED:
            allowed, reason = gate.decide("Bash", {"command": cmd})
            self.assertFalse(allowed, cmd)
            self.assertIn("gate 2", reason)

    def test_allowed(self):
        for cmd in ALLOWED:
            self.assertEqual(gate.decide("Bash", {"command": cmd}), (True, ""), cmd)

    def test_powershell(self):
        self.assertFalse(gate.decide("PowerShell", {"command": "git push"})[0])
        self.assertFalse(gate.decide("PowerShell", {"command": "Invoke-RestMethod -Uri https://api.github.com/repos/o/r/issues -Method Post -Body $b"})[0])
        self.assertTrue(gate.decide("PowerShell", {"command": "Invoke-RestMethod https://api.github.com/repos/o/r"})[0])

    def test_other_tools(self):
        self.assertEqual(gate.decide("Edit", {"file_path": "x", "old_string": "git push"}), (True, ""))
        self.assertEqual(gate.decide("Agent", {"prompt": "git push it"}), (True, ""))
        self.assertTrue(gate.decide("Bash", {})[0])

    def test_github_mcp_tools(self):
        self.assertFalse(gate.decide("mcp__github__create_pull_request", {})[0])
        self.assertFalse(gate.decide("mcp__github__add_issue_comment", {})[0])
        self.assertTrue(gate.decide("mcp__github__get_issue", {})[0])
        self.assertTrue(gate.decide("mcp__github__list_pull_requests", {})[0])
        self.assertTrue(gate.decide("mcp__other__create_thing", {})[0])
        # F4: any GitHub or git server name, not just one with "github" in it
        for name in ("mcp__gh__create_issue", "mcp__github-server__push_files", "mcp__GitHub__merge_pull_request",
                     "mcp__plugin_github_github__add_issue_comment", "mcp__git__git_push", "mcp__my_gh__create_pr"):
            self.assertFalse(gate.decide(name, {})[0], name)
        for name in ("mcp__gh__get_issue", "mcp__git__git_status", "mcp__git__git_log", "mcp__digit__create_x",
                     "mcp__gitlab_like__x"):
            self.assertTrue(gate.decide(name, {})[0], name)
        # integration re-check K10: read tools by their real names pass; login/ready aren't reads
        for name in ("mcp__github__issue_read", "mcp__github__pull_request_read", "mcp__github__get_file_contents",
                     "mcp__github__search_code", "mcp__github__list_commits", "mcp__github__get_me",
                     "mcp__git__git_diff_staged", "mcp__github__releases_list"):
            self.assertTrue(gate.decide(name, {})[0], name)
        for name in ("mcp__github__login", "mcp__github__ready_for_review", "mcp__github__issue_write",
                     "mcp__github__logout", "mcp__github__showcase_create", "mcp__git__git_reader_push",
                     "mcp__github__update_pull_request_branch", "mcp__github__getaway_push"):
            self.assertFalse(gate.decide(name, {})[0], name)

    def test_edits_inside_git_dir(self):
        for path in (".git/hooks/pre-push", "C:\\repo\\.git\\config", "/r/.GIT/hooks/post-commit", "sub/.git",
                     "r/.git./config", "C:\\r\\.git::$INDEX_ALLOCATION\\hooks\\pre-push", "r/.git:x/config",
                     "r/.GIT . /hooks/x", "GIT~1/hooks/pre-push", "r/git~12/config"):
            for tool in ("Edit", "Write", "MultiEdit"):
                self.assertFalse(gate.decide(tool, {"file_path": path})[0], (tool, path))
        self.assertFalse(gate.decide("NotebookEdit", {"notebook_path": ".git/x.ipynb"})[0])
        for path in (".github/workflows/ci.yml", ".gitignore", "src/git/x.py", "docs/.gitkeep"):
            self.assertTrue(gate.decide("Write", {"file_path": path})[0], path)

    def test_powershell_backtick_escapes(self):
        self.assertFalse(gate.decide("PowerShell", {"command": "g`it p`ush"})[0])

    def test_existing_aliases_are_looked_up(self):
        with tempfile.TemporaryDirectory() as repo:
            subprocess.run(["git", "init", "-q", repo], check=True)
            for name, value in (("ship", "push"), ("yolo", "!git push origin HEAD"), ("st", "status"),
                                ("deep", "ship -f")):
                subprocess.run(["git", "-C", repo, "config", "alias." + name, value], check=True)
            for cmd in ("git ship", "git yolo", "git deep", "git -C . ship"):
                self.assertFalse(gate.decide("Bash", {"command": cmd}, cwd=repo)[0], cmd)
            for cmd in ("git st", "git nosuchalias"):
                self.assertTrue(gate.decide("Bash", {"command": cmd}, cwd=repo)[0], cmd)
            p = subprocess.run([sys.executable, GATE], capture_output=True, text=True, timeout=60, input=json.dumps(
                {"tool_name": "Bash", "tool_input": {"command": "git ship"}, "cwd": repo}))
            self.assertEqual(p.returncode, 2)
            self.assertIn("alias", p.stderr)

    def test_static_pass_runs_before_any_lookup(self):  # K3
        with mock.patch.object(gate, "_alias") as alias:
            self.assertFalse(gate.decide("Bash", {"command": "git a; git b; git c; git push"})[0])
        alias.assert_not_called()  # the push is found without running git
        with mock.patch.object(gate, "_alias", return_value=None) as alias:
            self.assertTrue(gate.decide("Bash", {"command": "git a; git a; git -C x a; git status"})[0])
        self.assertEqual(alias.call_count, 2)  # one lookup per (name, -C), none for built-ins

    def test_lookups_are_capped_and_fail_closed(self):  # K3
        many = "; ".join(f"git x{i}" for i in range(gate.MAX_LOOKUPS + 1))
        with mock.patch.object(gate.subprocess, "run", return_value=mock.Mock(returncode=1, stdout="")) as run:
            allowed, reason = gate.decide("Bash", {"command": many})
        self.assertFalse(allowed)
        self.assertIn(f"more than {gate.MAX_LOOKUPS}", reason)
        self.assertEqual(run.call_count, gate.MAX_LOOKUPS)
        for effect, expect in ((subprocess.TimeoutExpired("git", 1), "TimeoutExpired"), (OSError("x"), "OSError"),
                               (mock.Mock(returncode=128, stdout=""), "exit code 128")):
            kw = {"side_effect": effect} if isinstance(effect, BaseException) else {"return_value": effect}
            with mock.patch.object(gate.subprocess, "run", **kw):
                allowed, reason = gate.decide("Bash", {"command": "git ship"})
            self.assertFalse(allowed, expect)
            self.assertIn(expect, reason)
        with mock.patch.object(gate, "resolve_program", return_value=None):
            allowed, reason = gate.decide("Bash", {"command": "git ship"})
        self.assertFalse(allowed)
        self.assertIn("git is not on PATH", reason)

    def test_lookups_stop_at_the_deadline(self):  # K3
        clock = iter([0.0, 0.0, gate.LOOKUP_DEADLINE + 1, gate.LOOKUP_DEADLINE + 2])  # start, 1st, 2nd lookup
        with mock.patch.object(gate.time, "monotonic", side_effect=lambda: next(clock)), \
                mock.patch.object(gate.subprocess, "run", return_value=mock.Mock(returncode=1, stdout="")) as run:
            allowed, reason = gate.decide("Bash", {"command": "git a; git b"})
        self.assertFalse(allowed)
        self.assertIn("ran out of time", reason)
        self.assertEqual(run.call_count, 1)
        self.assertLessEqual(run.call_args[1]["timeout"], gate.LOOKUP_DEADLINE)

    def test_docstring_lists_what_is_out_of_scope(self):
        self.assertIn("tripwire, not a sandbox", gate.__doc__)
        for item in ("python -c", "pwsh -File", "splatting", "stdin", "(K4)", "symlink or junction"):
            self.assertIn(item, gate.__doc__)


class ResolveProgramTest(unittest.TestCase):  # integration re-check K1
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = os.path.realpath(tmp.name)
        self.repo, self.bin = os.path.join(self.root, "repo"), os.path.join(self.root, "bin")
        self.ext = ".CMD" if os.name == "nt" else ""
        for d in (self.repo, os.path.join(self.repo, "tools"), self.bin):
            os.makedirs(d)
            self.make(os.path.join(d, "git" + self.ext.lower()))
        old = os.getcwd()
        os.chdir(self.repo)
        self.addCleanup(os.chdir, old)
        p = mock.patch.dict(os.environ, {"PATHEXT": ".COM;.EXE;.BAT;.CMD"})
        p.start()
        self.addCleanup(p.stop)

    def make(self, path):
        with open(path, "w") as f:
            f.write("@echo planted\n" if os.name == "nt" else "#!/bin/sh\necho planted\n")
        os.chmod(path, 0o755)

    def path(self, *entries):
        return os.pathsep.join(entries)

    def found(self, *entries, avoid=()):
        return gate.resolve_program("git", *avoid, path=self.path(*entries))

    def test_skips_cwd_relative_and_avoided_folders(self):
        want = os.path.join(self.bin, "git" + self.ext)
        got = self.found("", ".", "tools", self.repo, os.path.join(self.repo, "tools"), self.bin, avoid=[self.repo])
        self.assertEqual(os.path.normcase(got), os.path.normcase(want))
        self.assertTrue(os.path.isabs(got))
        # the current folder is skipped even when nothing is avoided
        self.assertEqual(os.path.normcase(self.found(self.repo, self.bin)), os.path.normcase(want))
        self.assertIsNone(self.found("", ".", self.repo, os.path.join(self.repo, "tools"), avoid=[self.repo]))
        self.assertIsNone(self.found(os.path.join(self.repo, "tools"), avoid=[os.path.join(self.repo, ".")]))

    def test_program_below_cwd_is_found_but_cwd_itself_is_not(self):
        tools = os.path.join(self.repo, "tools")
        want = os.path.normcase(os.path.join(tools, "git" + self.ext))
        self.assertEqual(os.path.normcase(self.found(tools)), want)
        self.assertIsNone(self.found(".", self.repo))
        self.assertIsNone(self.found(tools, avoid=[self.repo]))

    def test_quoted_entries_and_pathext(self):
        got = self.found('"' + self.bin + '"', avoid=[self.repo])
        self.assertEqual(os.path.normcase(got), os.path.normcase(os.path.join(self.bin, "git" + self.ext)))
        if os.name == "nt":
            with mock.patch.dict(os.environ, {"PATHEXT": ".EXE"}):
                self.assertIsNone(self.found(self.bin))  # git.cmd isn't a program without .CMD in PATHEXT

    def test_drive_relative_path_is_not_absolute_on_windows(self):
        self.assertFalse(gate._windows_abs("\\tools", True))
        self.assertTrue(gate._windows_abs("C:\\tools", True) or os.name != "nt")

    def test_alias_lookup_uses_resolved_git(self):
        with mock.patch.object(gate, "resolve_program", return_value="/abs/git") as resolve, \
                mock.patch.object(gate.subprocess, "run", return_value=mock.Mock(returncode=1, stdout="")) as run:
            self.assertTrue(gate.decide("Bash", {"command": "git nosuch"}, cwd=self.repo)[0])
        self.assertEqual(run.call_args[0][0][0], "/abs/git")
        self.assertEqual(resolve.call_args[0], ("git", self.repo))


class HookProtocolTest(unittest.TestCase):
    """Run as Claude Code runs it: the file by path (so a module in run/ must never shadow the standard library)."""

    def setUp(self):
        isolate_git(self)

    def hook(self, payload):
        data = payload if isinstance(payload, str) else json.dumps(payload)
        return subprocess.run([sys.executable, GATE], input=data, capture_output=True, text=True, timeout=60)

    def test_block_exits_2_with_reason(self):
        p = self.hook({"tool_name": "Bash", "tool_input": {"command": "git push"}, "session_id": "s"})
        self.assertEqual(p.returncode, 2)
        self.assertIn("git push is blocked", p.stderr)

    def test_allow_exits_0_silently(self):
        p = self.hook({"tool_name": "Bash", "tool_input": {"command": "git status"}})
        self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "", ""))

    def test_unreadable_input_fails_closed(self):
        p = self.hook("not json")
        self.assertEqual(p.returncode, 2)
        self.assertIn("blocked", p.stderr)


if __name__ == "__main__":
    unittest.main()
