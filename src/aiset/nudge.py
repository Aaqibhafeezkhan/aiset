#!/usr/bin/env python3
"""PreToolUse hook: point an agent at teammap when it greps for something the code index can answer.

  python nudge.py <workspace>     reads the hook's JSON on stdin (Claude Code passes it)

init_team.py writes it into the engineer, tester and integration-checker agent files, so it runs only
while one of those agents is working. It never blocks or approves a call: for a grep after a symbol or a
route, or a whole-file read of a long source file, it prints one line of extra context with the teammap
command that answers it, and Claude Code carries on with the call as usual. Each suggestion is made once
per session.
"""
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
if __name__ == "__main__" and not __package__:  # run as a file: python src/aiset/nudge.py
    sys.path.insert(0, os.path.dirname(HERE))
    __package__ = "aiset"
from .core import _shell_segments  # noqa: E402
from .workspace import norm, relative, script_command  # noqa: E402

SOURCE_EXT = (".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
# what teammap can index: a repo with one of these at its top
INDEXABLE = ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "package.json", "tsconfig.json")
GREP_CMDS = {"grep", "egrep", "rg", "ag"}
LONG_FILE = 300  # lines; a whole-file read of a longer source file gets a suggestion
DEFINITION = re.compile(r"^\^?\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?"
                        r"(?:def|class|function|interface|type|const|let|var)\s+([A-Za-z_]\w*)\b")
CALL = re.compile(r"^([A-Za-z_][\w.]*)\\?\(\)?$")
IDENT = re.compile(r"^(?:\\b)?([A-Za-z_]\w{2,})(?:\\b)?$")
ROUTE = re.compile(r"^\^?['\"]?((?:/[\w{}:.-]+)+/?)['\"]?\$?$")


def _repo(ws, path):
    """(repo name, path inside it) when path is in one of the workspace's indexable repos, else None.

    The workspace folder itself counts (repo "") once teammap has indexed something in it.
    """
    index = os.path.join(ws, ".claude", "team", "graph", "index")
    if norm(path).rstrip("/") == norm(ws).rstrip("/"):
        return ("", "") if os.path.isdir(index) and any(f.endswith(".json") for f in os.listdir(index)) else None
    rel = relative(path, ws)
    if rel is None or rel.startswith("."):
        return None
    name, _, rest = rel.partition("/")
    indexed = os.path.isfile(os.path.join(index, name + ".json"))
    if not indexed and not any(os.path.isfile(os.path.join(ws, name, f)) for f in INDEXABLE):
        return None
    return name, rest


def _grep_query(pattern):
    """(teammap subcommand, query) for a grep pattern the index answers, else None."""
    p = pattern.strip().replace("\\/", "/")
    m = ROUTE.match(p)
    if m and len(m.group(1)) > 2:
        return "endpoint", m.group(1)
    m = DEFINITION.match(p)
    if m:
        return "code", m.group(1)
    m = CALL.match(p) or IDENT.match(p)
    if m:
        name = m.group(1)
        # a plain lowercase word is as likely to be text as a name: leave it to grep
        if "_" in name or "." in name or name[0].isupper() or re.search(r"[a-z][A-Z]", name):
            return "symbol", name
    return None


def _grep_args(tokens):
    """(pattern, paths) from a grep/rg command's arguments."""
    pattern, paths, skip = None, [], False
    for i, a in enumerate(tokens):
        if skip:
            skip = False
            continue
        if a in ("-e", "--regexp") and i + 1 < len(tokens):
            pattern, skip = tokens[i + 1], True
        elif a in ("-f", "-g", "--glob", "-t", "--type", "--include", "--exclude", "-A", "-B", "-C", "-m", "--max-count"):
            skip = True
        elif a.startswith("-"):
            continue
        elif pattern is None:
            pattern = a
        else:
            paths.append(a)
    return pattern, paths


def _lines(path):
    try:
        with open(path, "rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def suggest(ws, tool, inp, cwd, teammap="teammap"):
    """(key, message) for a tool call worth a suggestion, or None to stay silent."""
    def where(p):
        p = os.path.expanduser(p or "")
        return norm(os.path.normpath(p if os.path.isabs(p) else os.path.join(cwd or ws, p)))

    def for_grep(pattern, paths, filters=""):
        if not pattern or re.search(r"\.(md|json|ya?ml|toml|txt|lock|csv|html|css)\b", filters):
            return None
        q = _grep_query(pattern)
        hits = [_repo(ws, where(p)) for p in (paths or [cwd or ws])]
        if not q or not hits or not all(hits):
            return None
        sub, name = q
        what = {"endpoint": "the handler, its request/response models and the frontend callers",
                "code": "just that definition with line numbers",
                "symbol": "its definition, signature, callers and callees"}[sub]
        return f"{sub}:{name}", (f"aiset: `{teammap} {sub} {name}` gives {what} in one call. "
                                 "Use teammap first for names and routes; grep for text it doesn't index.")

    def for_read(path):
        if not path.endswith(SOURCE_EXT):
            return None
        hit = _repo(ws, path)
        n = _lines(path) if hit else 0
        if n <= LONG_FILE:
            return None
        rel = "/".join(p for p in hit if p)
        return f"read:{rel}", (f"aiset: {rel} has {n} lines. `{teammap} file {os.path.basename(path)}` lists its "
                               "symbols and routes, `code <name>` prints one of them; "
                               "Read with offset/limit for the part you'll edit.")

    if tool == "Grep":
        return for_grep(inp.get("pattern", ""), [inp["path"]] if inp.get("path") else [],
                        f"{inp.get('glob', '')} {inp.get('type', '')}")
    if tool == "Read":
        if inp.get("offset") or inp.get("limit"):
            return None
        return for_read(where(inp.get("file_path")))
    if tool == "Bash":
        cmd = inp.get("command", "")
        if "teammap" in cmd:
            return None
        segments = list(_shell_segments(cmd))
        for tok in segments:
            verb, args = os.path.basename(tok[0]), tok[1:]
            if verb == "git" and args[:1] == ["grep"]:
                verb, args = "grep", args[1:]
            if verb in GREP_CMDS:
                pattern, paths = _grep_args(args)
                return for_grep(pattern, paths, " ".join(a for a in args if "." in a and a not in paths))
            if verb == "cat" and len(args) == 1 and len(segments) == 1:  # piped into head/grep: a partial read
                return for_read(where(args[0]))
    return None


def _seen(session, key):
    """True when this session already got this suggestion; records it otherwise."""
    name = re.sub(r"[^\w-]", "", session or "none")
    path = os.path.join(tempfile.gettempdir(), f"aiset-nudge-{name}.txt")
    try:
        with open(path, encoding="utf-8") as f:
            if key in f.read().splitlines():
                return True
    except OSError:
        pass
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(key + "\n")
    except OSError:
        pass
    return False


def main(argv):
    try:
        data = json.load(sys.stdin)
        ws = os.path.abspath(argv[0]) if argv else data.get("cwd")
        hit = suggest(ws, data.get("tool_name"), data.get("tool_input") or {}, data.get("cwd"), script_command("teammap"))
        if hit and not _seen(data.get("session_id"), hit[0]):
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": hit[1]}}))
    except Exception:  # a hint is never worth getting in the agent's way
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
