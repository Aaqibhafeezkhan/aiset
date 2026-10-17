"""Where the team lives: one place that works out every path the office and its tools use.

A workspace is a folder of repositories with the team inside it (made by init_team.py):

  <workspace>/.claude/agents/*.md       the agents (Claude Code loads them for sessions in <workspace>)
  <workspace>/.claude/team/roster.json  names, roles, which repos each engineer owns
  <workspace>/.claude/team/knowledge/   knowledge briefs
  <workspace>/.claude/team/tasks/       task boards
  <workspace>/.claude/team/episodes/    task summaries
  <workspace>/.claude/team/graph/       teammap index and code graphs

The workspace is AISET_WORKSPACE (or the older AGENT_OFFICE_WORKSPACE) if set (server.py --workspace sets it), otherwise the
nearest folder above the current directory that has .claude/team/roster.json. Without one,
the original single-team layout is used: ~/.claude/agents, ~/.claude/team, the application folder.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.realpath(__file__))
# the checkout (src/aiset -> repo root) for a source tree; the package folder when installed
APP_DIR = os.path.dirname(os.path.dirname(HERE)) if os.path.basename(os.path.dirname(HERE)) == "src" else HERE
HOME = os.path.expanduser("~")


def norm(path):
    """Forward slashes and a lowercase drive letter, so Windows paths compare as strings.

    C:\\Users\\x and /c/Users/x (Git Bash) both become c:/Users/x; POSIX paths are unchanged.
    """
    p = str(path or "").replace("\\", "/")
    m = re.match(r"^/([a-zA-Z])(/|$)", p) if os.name == "nt" else None
    if m:
        p = m.group(1) + ":/" + p[3:]
    if re.match(r"^[a-zA-Z]:", p):
        p = p[0].lower() + p[1:]
    return p


def relative(path, root):
    """path relative to root (both normalised), or None when it's outside."""
    p, r = norm(path), norm(root).rstrip("/")
    if os.name == "nt":
        if p.lower().startswith(r.lower() + "/"):
            return p[len(r) + 1:]
    elif p.startswith(r + "/"):
        return p[len(r) + 1:]
    return None


def root_pattern(root):
    """Regex for root as it may appear in a shell command: either slash, either drive form."""
    r = norm(root).rstrip("/")
    m = re.match(r"^([a-z]):(.*)$", r)
    if m:
        return r"(?i:(?:%s:|/%s)%s)" % (m.group(1), m.group(1), re.escape(m.group(2)).replace("/", r"[\\/]"))
    return re.escape(r)


def slug(path):
    """The folder name Claude Code gives a project under ~/.claude/projects (lowercased)."""
    return re.sub(r"[^a-z0-9]", "-", str(path).lower())


def _find():
    ws = os.environ.get("AISET_WORKSPACE") or os.environ.get("AGENT_OFFICE_WORKSPACE")
    if ws:
        return os.path.abspath(ws)
    d = os.getcwd()
    while True:
        if os.path.isfile(os.path.join(d, ".claude", "team", "roster.json")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


WORKSPACE = _find()
if WORKSPACE:
    CODE_ROOT = norm(WORKSPACE)
    TEAM = CODE_ROOT + "/.claude/team"
    AGENTS = CODE_ROOT + "/.claude/agents"
    ROSTER = TEAM + "/roster.json"
else:
    CODE_ROOT = norm(APP_DIR)
    TEAM = norm(os.path.join(HOME, ".claude", "team"))
    AGENTS = norm(os.path.join(HOME, ".claude", "agents"))
    ROSTER = norm(os.path.join(HERE, "roster.json"))
KNOWLEDGE = TEAM + "/knowledge"
BOARDS = TEAM + "/tasks"
EPISODES = TEAM + "/episodes"
GRAPHS = TEAM + "/graph"
PROJECTS = norm(os.path.join(HOME, ".claude", "projects"))


def load_roster():
    with open(ROSTER, encoding="utf-8") as f:
        return json.load(f)


def roster_repos():
    """Every repo an engineer owns, in roster order; [] when the roster can't be read."""
    try:
        members = load_roster()["members"]
    except (OSError, ValueError, KeyError):
        return []
    out = []
    for m in members:
        for r in m.get("repos") or []:
            if r not in out:
                out.append(r)
    return out
