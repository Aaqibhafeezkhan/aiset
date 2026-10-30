"""PreToolUse gate for `aiset run` sessions: agents don't push and don't write to GitHub.

  python gate.py          reads the hook's JSON on stdin (Claude Code passes it); exit 2 blocks the call

`aiset run` passes it to `claude` with `--settings <board>/gate-settings.json`, so it applies to that session
only (subagents included, checked with claude 2.1.312) and changes no settings file of the user's. It is the
"everyone: git push blocked" slice of #56, with #56's decision shape `decide(tool_name, tool_input) ->
(allowed, reason)`, so it can fold into a guard module later.

Blocked:
- `git push`, `git send-pack`, `git http-push`, `git subtree push`, `git lfs push`, `git remote add|set-url`;
  aliases set with `git -c alias.*=` or `--config-env`, and existing aliases (looked up with `git config` in the
  session's folder) that push; `git $var` and `xargs git` with no subcommand (it comes from somewhere else).
- `git config` writes of keys that redirect a push or run code in gate 2's git or the user's later git
  (RISKY_CONFIG: remotes, url.*.insteadOf, aliases, core.hooksPath, core.fsmonitor, filters, credential
  helpers, includes, ...), and `git config --edit`. Reads (`--get`, `--list`, `get`) pass.
- Edit/Write/MultiEdit/NotebookEdit of a path inside a `.git` folder, and shell writes (`>`, tee, cp, mv,
  Set-Content, ...) that name `.git/hooks` or `.git/config`.
- every `gh issue` command (agents read the issue from issue.md), `gh` commands outside a list of reads,
  `gh api` with a non-GET method or fields.
- curl/wget writes to GitHub hosts; Invoke-RestMethod/Invoke-WebRequest to GitHub with a write -Method (also
  `-Method:Post`, an abbreviated `-Me`, a `$variable` or `(expression)` method, -CustomMethod), and .NET
  WebClient uploads.
- nested commands: `$(...)`, backticks, `eval`, `sh|bash|zsh -c` (also `-xc`), `cmd /c|/k`, `powershell|pwsh`
  with -Command or a positional command (the rest of the line is the command), `-EncodedCommand` in any
  abbreviation (`-e`, `-ec`, `-enc`, ...: blocked outright, it can't be read), `find -exec|-execdir|-ok`,
  `watch`, `xargs`.
- MCP tools of a GitHub or git server (a server name with `github`, or `gh`/`git` as a word) other than reads
  (an action that starts with get/list/search/read/view/status/diff/log/show as a word, or ends in
  _read/_list/_get).

Alias lookups: a static pass over every segment runs first; only when it finds nothing are unknown git
subcommands looked up as aliases, at most MAX_LOOKUPS per tool call within LOOKUP_DEADLINE seconds, with git
found by resolve_program (never from the session's folder). A lookup that fails, times out or goes over the
cap blocks the call (fail closed). The hook itself runs with a timeout and `onFailure: block` (launch.py).

A tripwire, not a sandbox. Out of scope by design; the hard line is that publishing lives in `aiset run`'s own
code after gate 2, outside the session, and gate 2 shows the push URL, the agents' commits and git config/hook
changes since gate 1, and runs its own git with hooks off:
- interpreters and scripts: `python -c`, `node -e`, perl, ruby, a script file (`bash x.sh`, `pwsh -File`),
  make/npm targets, git through a library (dulwich, libgit2);
- commands fed on stdin (`echo git push | sh`, `pwsh -Command -`), shell variables or functions that hold a
  command, PowerShell splatting (`irm @params`), escapes inside words in bash, `Start-Process`, .NET HTTP classes
  other than WebClient uploads, Windows short names (`GIT~1`);
- ssh or a raw socket to git-receive-pack; write tools of MCP servers whose name doesn't say GitHub or git;
- (K4) alias lookups see the hook's cwd and `git -C` only: `cd x && git ship`, `--git-dir`, GIT_DIR or
  GIT_CONFIG_* set in the command can point git at another config than the one looked up;
- edits through a symlink or junction to a .git folder (only the path's own components are checked).
"""
import json
import os
import re
import shlex
import subprocess
import sys
import time

HINT = ("Publishing happens in `aiset run` after the user approves at gate 2. "
        "Write your result to the task board instead.")
WRAPPERS = {"sudo", "env", "command", "builtin", "nohup", "time", "nice", "exec", "xargs", "stdbuf", "timeout",
            "then", "do", "else", "elif", "if", "while", "until", "!", "{", "(", "}", ")"}
POSIX_SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "fish"}
GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"}
GIT_PUSHES = {"push", "send-pack", "http-push"}
GIT_BUILTINS = {
    "add", "am", "annotate", "apply", "archive", "bisect", "blame", "branch", "bundle", "cat-file", "check-ignore",
    "checkout", "cherry", "cherry-pick", "clean", "clone", "commit", "config", "describe", "diff", "diff-files",
    "diff-index", "diff-tree", "difftool", "fetch", "for-each-ref", "format-patch", "fsck", "gc", "grep",
    "hash-object", "help", "init", "log", "ls-files", "ls-remote", "ls-tree", "maintenance", "merge", "merge-base",
    "mv", "name-rev", "notes", "pull", "range-diff", "rebase", "reflog", "remote", "reset", "restore", "rev-list",
    "rev-parse", "revert", "rm", "shortlog", "show", "show-ref", "sparse-checkout", "stash", "status", "submodule",
    "switch", "symbolic-ref", "tag", "update-index", "update-ref", "var", "version", "whatchanged", "worktree",
    "write-tree", "subtree", "lfs",
} | GIT_PUSHES
# git config keys (lowercased) that redirect a push or run code when gate 2, or the user later, runs git.
# gitops snapshots the same keys at gate 1 and compares them at gate 2.
RISKY_CONFIG = re.compile(
    r"^(?:alias\..+|url\..+|remote\..+|branch\..+\.pushremote|core\.(?:hookspath|fsmonitor|sshcommand|gitproxy"
    r"|askpass|editor|pager|attributesfile|worktree)|credential(?:\..+)?|filter\..+|diff\.external"
    r"|diff\..+\.(?:command|textconv)|merge\..+\.driver|gpg\..+|include\.path|includeif\..+|http\..+"
    r"|sequence\.editor|ssh\.variant|uploadpack\..+|receive\..+|protocol\..+|safe\.directory|submodule\..+"
    r"|push\..+)$")
# what `git -c` may not set for one command: aliases, and anything that changes where a push goes
RISKY_DASH_C = re.compile(r"^(?:alias\..+|url\..+|remote\..+|branch\..+\.pushremote)$")
GIT_CONFIG_READS = {"--get", "--get-all", "--get-regexp", "--get-urlmatch", "-l", "--list", "get", "list",
                    "--get-color", "--get-colorbool"}
GH_VALUE_OPTS = {"-R", "--repo", "--hostname"}
GH_READS = {
    "pr": {"view", "list", "status", "diff", "checks"},
    "release": {"view", "list", "download"},
    "repo": {"view", "list", "clone"},
    "run": {"view", "list", "watch", "download"},
    "workflow": {"view", "list"},
    "gist": {"view", "list"},
    "label": {"list"},
    "cache": {"list"},
    "ruleset": {"list", "view", "check"},
    "variable": {"list", "get"},
    "secret": {"list"},
    "org": {"list"},
    "auth": {"status"},
    "search": None, "status": None, "browse": None, "help": None, "version": None, "completion": None,
}
GITHUB_HOSTS = re.compile(r"(?:^|[/@.])(?:api\.github\.com|uploads\.github\.com|github\.com)(?:[:/]|$)", re.I)
PS_WRITE = re.compile(
    r"\b(?:Invoke-RestMethod|Invoke-WebRequest|irm|iwr)\b.*(?:-Me\w*(?:\s*:\s*|\s+)(?:['\"]?(?:Post|Put|Patch|Delete)"
    r"|['\"]?[$(])|-CustomMethod\b)|\.Upload(?:String|Data|File|Values)(?:Async|TaskAsync)?\s*\(", re.I | re.S)
PS_ENCODED = re.compile(r"^[-/]e(?:c|n(?:c(?:o(?:d(?:e(?:d(?:c(?:o(?:m(?:m(?:a(?:n(?:d)?)?)?)?)?)?)?)?)?)?)?)?)?$", re.I)
PS_COMMAND = re.compile(r"^[-/]c(?:o(?:m(?:m(?:a(?:n(?:d)?)?)?)?)?)?$", re.I)
PS_FILE = re.compile(r"^[-/]f(?:i(?:l(?:e)?)?)?$", re.I)
PS_OPTION = re.compile(r"^(?:-|/[A-Za-z]+$)")
PS_VALUE_OPTS = {"executionpolicy", "ex", "ep", "windowstyle", "w", "win", "inputformat", "inp", "if", "outputformat",
                 "o", "of", "op", "workingdirectory", "wd", "configurationname", "config", "version", "v",
                 "psconsolefile", "custompipename", "settingsfile", "settings", "configurationfile"}
GIT_DIR_NAMED = re.compile(r"\.git[/\\]+(?:hooks|config)\b", re.I)
SHELL_WRITE = re.compile(r">|\b(?:tee|cp|mv|ln|install|rsync|sed\s+-i|chmod|touch|Set-Content|Add-Content|Out-File"
                         r"|New-Item|Copy-Item|Move-Item|sc|ac)\b", re.I)
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
MCP_READ = re.compile(r"^(?:get|list|search|read|view|status|diff|log|show)(?:_|$)|_(?:read|list|get)$")
MAX_LOOKUPS = 8  # git alias lookups per tool call
LOOKUP_DEADLINE = 5.0  # seconds for all of them; the hook's own timeout (launch.HOOK_TIMEOUT) is longer
SUBSTITUTION = re.compile(r"\$\(([^()]*)\)|`([^`]*)`|<\(([^()]*)\)")
RAW_FALLBACK = re.compile(r"\bgit\b[^\n;&|]*\b(?:push|send-pack)\b|\bgh\b[^\n;&|]*\b(?:issue|pr|api|release|repo)\b"
                          r"|\bremote\s+(?:add|set-url)\b", re.I)
NUMBER = re.compile(r"^\d+(?:\.\d+)?[smhd]?$")


def _segments(cmd):
    """Token lists of the simple commands in cmd, split on && || ; | and newlines outside quotes
    (as core._shell_segments, kept here so the hook stays light). Raises ValueError on unbalanced quotes."""
    lex = shlex.shlex(cmd.replace("\n", " ; "), posix=True, punctuation_chars=";&|")
    lex.whitespace_split = True
    out, seg = [], []
    for t in lex:
        if t and set(t) <= set(";&|"):
            if seg:
                out.append(seg)
            seg = []
        else:
            seg.append(t)
    if seg:
        out.append(seg)
    return out


def _verb(token):
    v = token.replace("\\", "/").rsplit("/", 1)[-1].lower().lstrip("({").rstrip(")}")
    return v[:-4] if v.endswith(".exe") else v


def _windows_abs(path, windows):
    return os.path.isabs(path) and (not windows or bool(os.path.splitdrive(path)[0]))


def _norm(path):
    return os.path.normcase(os.path.realpath(path))


def _inside(path, roots):
    return any(path == r or path.startswith(r.rstrip(os.sep) + os.sep) for r in roots)


def resolve_program(name, *avoid, path=None, windows=None):
    """Absolute path of program `name` (git, gh, claude) from PATH, else None. Unlike shutil.which (which on
    Windows looks in the current folder first, .cmd/.bat included) it skips empty, `.` and relative PATH entries,
    the current folder, and any folder inside `avoid` (the repo, the workspace: places agents can write to), and
    never returns a file that resolves into them. On Windows the name gets each PATHEXT extension."""
    windows = os.name == "nt" if windows is None else windows
    exts = [""]
    if windows:
        exts = [e for e in (os.environ.get("PATHEXT") or ".COM;.EXE;.BAT;.CMD").split(";") if e.strip()]
    cwd = _norm(os.getcwd())
    roots = [_norm(a) for a in avoid if a]
    entries = (os.environ.get("PATH", "") if path is None else path).split(os.pathsep)
    for entry in entries:
        entry = entry.strip().strip('"')
        if not entry or entry == "." or not _windows_abs(entry, windows):
            continue
        real = _norm(entry)
        if real == cwd or _inside(real, roots):
            continue
        for ext in exts:
            cand = os.path.join(entry, name + ext)
            if not os.path.isfile(cand) or _inside(_norm(cand), roots):
                continue
            if windows or os.access(cand, os.X_OK):
                return cand
    return None


class _Lookups:
    """One tool call's alias lookups: queued during the static pass, run after it within a cap and deadline."""

    def __init__(self, cwd):
        self.cwd, self.pending, self.seen, self.done = cwd, [], set(), 0
        self.deadline = time.monotonic() + LOOKUP_DEADLINE


class _LookupFailed(Exception):
    pass


def _alias(name, pre, look):
    """The value of git alias `name` in the session's repo (pre: the command's -C options), else None.
    Raises _LookupFailed when it can't tell: no git outside the session's folder, an error, the cap or deadline."""
    if look.done >= MAX_LOOKUPS:
        raise _LookupFailed(f"more than {MAX_LOOKUPS} unknown git subcommands to look up")
    left = look.deadline - time.monotonic()
    if left <= 0:
        raise _LookupFailed("the alias lookups ran out of time")
    look.done += 1
    exe = resolve_program("git", look.cwd)
    if not exe:
        raise _LookupFailed("git is not on PATH outside the session's folder")
    try:
        p = subprocess.run([exe, *pre, "config", "--get", "alias." + name], cwd=look.cwd or None, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=left)
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        raise _LookupFailed(f"the alias lookup failed ({e.__class__.__name__})") from None
    if p.returncode == 1 and not p.stdout.strip():
        return None  # no such alias
    if p.returncode != 0:
        raise _LookupFailed(f"the alias lookup failed (git exit code {p.returncode})")
    return p.stdout.strip() or None


def _git_config(rest):
    if any(a in GIT_CONFIG_READS for a in rest):
        return None
    if any(a in ("-e", "--edit", "edit") for a in rest):
        return "git config --edit"
    sections = any(a in ("--rename-section", "--remove-section", "rename-section", "remove-section") for a in rest)
    for a in rest:
        key = a.split("=", 1)[0]
        if RISKY_CONFIG.match(key) or (sections and RISKY_CONFIG.match(key + ".x")):
            return f"git config of {key} (it can redirect a push or run code in git)"
    return None


def _git(args, look, via_xargs=False, depth=0):
    i, pre = 0, []
    while i < len(args) and args[i].startswith("-"):
        a = args[i]
        value = None
        if a in ("-c", "--config-env") and i + 1 < len(args):
            value = args[i + 1]
        elif a.startswith("--config-env="):
            value = a.split("=", 1)[1]
        if value is not None and RISKY_DASH_C.match(value.split("=", 1)[0].lower()):
            return f"git {a} {value.split('=', 1)[0]}"
        if a == "-C" and i + 1 < len(args):
            pre += ["-C", args[i + 1]]
        i += 2 if a in GIT_VALUE_OPTS else 1
    if i >= len(args):
        return "xargs git (its subcommand comes from the input)" if via_xargs else None
    sub, rest = args[i].lower(), [a.lower() for a in args[i + 1:]]
    if any(c in sub for c in "$`{%"):
        return "git with a subcommand from a variable"
    if sub in GIT_PUSHES:
        return f"git {sub}"
    if sub in ("subtree", "lfs") and "push" in rest:
        return f"git {sub} push"
    if sub == "remote" and rest[:1] and rest[0] in ("add", "set-url"):
        return f"git remote {rest[0]}"
    if sub == "config":
        return _git_config(rest)
    if sub not in GIT_BUILTINS:
        key = (sub, tuple(pre))
        if key not in look.seen:  # looked up after the static pass over the whole command (_run_lookups)
            look.seen.add(key)
            look.pending.append((sub, pre, args[i + 1:], depth))
    return None


def _run_lookups(look):
    """Looks up the unknown git subcommands the static pass queued (and any an alias leads to); what's blocked
    or None. Fails closed: a lookup that can't be done blocks the call."""
    while look.pending:
        sub, pre, rest, depth = look.pending.pop(0)
        if depth >= 4:
            return f"git {sub} (aliases nested too deep to check)"
        try:
            value = _alias(sub, pre, look)
        except _LookupFailed as e:
            return f"git {sub} (can't tell whether it is an alias that pushes: {e})"
        if not value:
            continue
        try:
            hit = (_check(value[1:], depth + 1, look) if value.startswith("!")
                   else _git(shlex.split(value) + rest, look, False, depth + 1))
        except ValueError:
            hit = "an unreadable alias"
        if hit:
            return f"git {sub} (an alias for {hit})"
    return None


def _gh_api(args):
    method, fields = None, False
    for i, a in enumerate(args):
        if a in ("-X", "--method") and i + 1 < len(args):
            method = args[i + 1].upper()
        elif a.startswith("--method="):
            method = a.split("=", 1)[1].upper()
        elif a.startswith("-X") and len(a) > 2:
            method = a[2:].upper()
        elif re.match(r"^(-f|-F|--field|--raw-field|--input)(=|$)", a) or re.match(r"^-[fF]\w", a):
            fields = True
    if method and method not in ("GET", "HEAD"):
        return f"gh api -X {method}"
    if fields and method is None:
        return "gh api with fields (a POST)"
    return None


def _gh(args):
    words, i = [], 0
    while i < len(args) and len(words) < 2:
        a = args[i]
        if a in GH_VALUE_OPTS:
            i += 2
            continue
        if not a.startswith("-"):
            words.append(a.lower())
        i += 1
    if not words:
        return None  # gh --version, gh --help
    group, verb = words[0], (words[1] if len(words) > 1 else None)
    if group == "issue":
        return "gh issue (agents read the issue from issue.md on the board)"
    if group == "api":
        return _gh_api(args)
    if group not in GH_READS:
        return f"gh {group}"
    reads = GH_READS[group]
    if reads is None or verb is None or verb in reads:
        return None
    return f"gh {group} {verb}"


def _http(verb, args):
    if not any(GITHUB_HOSTS.search(a) for a in args):
        return None
    for i, a in enumerate(args):
        if verb == "curl":
            if a in ("-X", "--request") and i + 1 < len(args) and args[i + 1].upper() not in ("GET", "HEAD"):
                return f"curl -X {args[i + 1].upper()} to GitHub"
            m = re.match(r"^-X(\w+)$", a) or re.match(r"^--request=(.+)$", a, re.I)
            if m and m.group(1).upper() not in ("GET", "HEAD"):
                return "curl write request to GitHub"
            if re.match(r"^(-d|--data\S*|-F|--form\S*|--json|-T|--upload-file)(=|$)", a) or re.match(r"^-[dFT]\S", a):
                return "curl upload to GitHub"
        else:
            m = re.match(r"^--method=(.*)$", a, re.I)
            if m and m.group(1).upper() not in ("GET", "HEAD"):
                return "wget write request to GitHub"
            if re.match(r"^--(post-data|post-file|body-data|body-file)", a, re.I):
                return "wget write request to GitHub"
    return None


def _powershell(args, depth, look):
    """powershell/pwsh: -Command (any abbreviation) or a positional command takes the rest of the line."""
    i = 0
    while i < len(args):
        a = args[i]
        if PS_ENCODED.match(a):
            return "powershell -EncodedCommand (an encoded command can't be checked)"
        if PS_COMMAND.match(a):
            return _check(" ".join(args[i + 1:]), depth + 1, look)
        if PS_FILE.match(a):
            return None  # a script file: out of scope
        if PS_OPTION.match(a):
            i += 2 if a[1:].split(":", 1)[0].lower() in PS_VALUE_OPTS else 1
            continue
        return _check(" ".join(args[i:]), depth + 1, look)
    return None


def _segment(tok, depth, look):
    tok = [t.strip("()") for t in tok if t.strip("()")]  # (git push) and $(...) leftovers
    via_xargs = False
    while tok and (re.match(r"^[A-Za-z_]\w*=", tok[0]) or _verb(tok[0]) in WRAPPERS or tok[0].startswith("-")
                   or NUMBER.match(tok[0])):
        via_xargs = via_xargs or _verb(tok[0]) == "xargs"
        tok = tok[1:]  # env assignments, wrappers and their options (timeout 30, env -i, xargs -0)
    if not tok:
        return None
    verb, args = _verb(tok[0]), tok[1:]
    if verb.startswith("git-") and len(verb) > 4:  # git-push, git-send-pack
        verb, args = "git", [verb[4:]] + args
    if verb == "eval":
        return _check(" ".join(args), depth + 1, look)
    if verb in ("pwsh", "powershell"):
        return _powershell(args, depth, look)
    if verb == "cmd":
        for i, a in enumerate(args):
            if a.lower() in ("/c", "/k", "/r"):
                return _check(" ".join(args[i + 1:]), depth + 1, look)
        return None
    if verb in POSIX_SHELLS:
        for i, a in enumerate(args):
            if re.match(r"^-[A-Za-z]*c[A-Za-z]*$", a) and i + 1 < len(args):
                return _check(args[i + 1], depth + 1, look)
        return None
    if verb == "find":
        for i, a in enumerate(args):
            if a in ("-exec", "-execdir", "-ok", "-okdir"):
                inner = []
                for b in args[i + 1:]:
                    if b in (";", "+"):
                        break
                    inner.append(b)
                hit = _check(" ".join(shlex.quote(b) for b in inner), depth + 1, look)
                if hit:
                    return hit
        return None
    if verb == "watch":
        while args and (args[0].startswith("-") or NUMBER.match(args[0])):
            args = args[1:]
        return _check(" ".join(args), depth + 1, look)
    if verb == "git":
        return _git(args, look, via_xargs, depth)
    if verb == "gh":
        if via_xargs and not any(not a.startswith("-") for a in args):
            return "xargs gh (its subcommand comes from the input)"
        return _gh(args)
    if verb in ("curl", "wget"):
        return _http(verb, args)
    return None


def _check(cmd, depth, look):
    """What the shell command does that's blocked, or None."""
    if depth > 4:
        return "deeply nested shell command"
    if PS_WRITE.search(cmd) and GITHUB_HOSTS.search(cmd.replace("https://", "/")):
        return "a PowerShell web request that writes to GitHub"
    if GIT_DIR_NAMED.search(cmd) and SHELL_WRITE.search(cmd):
        return "a write into .git/hooks or .git/config"
    for m in SUBSTITUTION.finditer(cmd):
        hit = _check(next(g for g in m.groups() if g is not None), depth + 1, look)
        if hit:
            return hit
    try:
        segments = _segments(cmd)
    except ValueError:  # unbalanced quotes: judge the raw text rather than nothing
        return "an unparseable command that mentions publishing" if RAW_FALLBACK.search(cmd) else None
    for tok in segments:
        hit = _segment(tok, depth, look)
        if hit:
            return hit
    return None


def _in_git_dir(path):
    """True for a path with a `.git` folder (or gitfile) in it; Windows ignores trailing dots and spaces, and
    `name::$INDEX_ALLOCATION` (an NTFS stream suffix) names the folder itself. A symlink or junction that points
    at a .git folder under another name is out of scope (only the path's own components are checked)."""
    parts = re.split(r"[/\\]+", (path or "").lower())
    return any(p.split(":")[0].rstrip(". ") == ".git" or re.fullmatch(r"git~\d+", p.split(":")[0].rstrip(". "))
               for p in parts)


def decide(tool_name, tool_input, cwd=None):
    """(allowed, reason) for one tool call in an aiset run session. cwd: the session's folder (alias lookups)."""
    name = tool_name or ""
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    if name.startswith("mcp__"):
        parts = name.split("__")
        server = "__".join(parts[1:-1]).lower()
        if "github" in server or re.search(r"(?:^|[^a-z0-9])(?:gh|git)(?:$|[^a-z0-9])", server):
            action = re.sub(r"^(?:git|gh|github)_", "", parts[-1].lower())
            if not MCP_READ.search(action):
                return False, f"aiset run: the GitHub/git tool {name} is blocked in this session. {HINT}"
        return True, ""
    if name in EDIT_TOOLS:
        path = tool_input.get("file_path") or tool_input.get("notebook_path")
        if isinstance(path, str) and _in_git_dir(path):
            return False, (f"aiset run: editing {path} (inside .git: hooks, config) is blocked in this session. "
                           f"{HINT}")
        return True, ""
    if name not in ("Bash", "PowerShell"):
        return True, ""
    cmd = tool_input.get("command")
    if not isinstance(cmd, str):
        return True, ""
    look = _Lookups(cwd)
    hit = _check(cmd, 0, look)  # the static pass: no git is run
    if not hit and name == "PowerShell" and "`" in cmd:
        hit = _check(cmd.replace("`", ""), 0, look)  # g`it p`ush: PowerShell's escape character
    hit = hit or _run_lookups(look)
    if hit:
        return False, f"aiset run: {hit} is blocked in this session. {HINT}"
    return True, ""


def main():
    try:
        data = json.load(sys.stdin)
        allowed, reason = decide(data.get("tool_name"), data.get("tool_input"), cwd=data.get("cwd"))
    except Exception as e:  # a gate that can't read its input fails closed
        allowed, reason = False, f"aiset run: the gate could not read this tool call ({e.__class__.__name__}); blocked."
    if allowed:
        return 0
    print(reason, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
