#!/usr/bin/env python3
"""aiset: a live office view of your Claude Code agent team, in the browser.

  aiset                        start on http://127.0.0.1:8765 and open the browser
  aiset --port 9000            use another port
  aiset --hours 24             include agents active in the last 24 hours (default 12)
  aiset --no-browser           don't open a browser tab
  aiset --brain-days 60        how far back the Brain page looks (default 30)
  aiset --workspace DIR        show the team of a workspace made by init_team.py
                               (default: the workspace you're in, else the original ~/.claude team)
"""
import argparse
import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import sys

if __name__ == "__main__" and not __package__:  # run as a file: python src/aiset/server.py
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    __package__ = "aiset"
HERE = os.path.dirname(os.path.realpath(__file__))
# every module reads its paths from workspace.py on import, so settle the workspace first
for _i, _a in enumerate(sys.argv):
    if _a == "--workspace" and _i + 1 < len(sys.argv):
        os.environ["AISET_WORKSPACE"] = os.path.abspath(sys.argv[_i + 1])
    elif _a.startswith("--workspace="):
        os.environ["AISET_WORKSPACE"] = os.path.abspath(_a.split("=", 1)[1])
from . import brain, brief_index, sync_names, workspace  # noqa: E402
from .core import Office, board_detail, task_detail, task_routes  # noqa: E402


ROSTER = workspace.ROSTER
_roster_mtime = None


def reload_roster(office):
    """Pick up edits to roster.json without a restart, and copy new names into the agent files."""
    global _roster_mtime
    try:
        mtime = os.path.getmtime(ROSTER)
        if mtime == _roster_mtime:
            return
        roster = workspace.load_roster()
    except (OSError, ValueError) as e:  # mid-edit or invalid JSON: keep the last good roster
        print(f"roster.json not loaded: {e}")
        return
    first = _roster_mtime is None
    _roster_mtime = mtime
    if office is not None:
        office.roster = roster
        if Handler.brain_office is not None:
            Handler.brain_office.roster = roster
    changed = sync_names.sync(roster)
    if changed and not first:
        print("roster changed → updated agent files:", ", ".join(changed))
    return roster


class Handler(BaseHTTPRequestHandler):
    office = None
    brain_office = None  # same parser, longer window
    lock = threading.Lock()

    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/state":
            with self.lock:
                reload_roster(self.office)
                brief_index.refresh()
                state = self.office.state()
            return self._send(200, json.dumps(state).encode(), "application/json")
        if path == "/api/detail":
            from urllib.parse import parse_qs, urlparse
            key = parse_qs(urlparse(self.path).query).get("key", [""])[0]
            with self.lock:
                item = self.office.detail(key)
            return self._send(200 if item else 404, json.dumps(item).encode(), "application/json")
        if path == "/api/board":
            from urllib.parse import parse_qs, urlparse
            item = board_detail(parse_qs(urlparse(self.path).query).get("id", [""])[0])
            return self._send(200 if item else 404, json.dumps(item).encode(), "application/json")
        if path == "/api/task/routes":
            from urllib.parse import parse_qs, urlparse
            tid = parse_qs(urlparse(self.path).query).get("id", [""])[0]
            with self.lock:
                item = task_routes(self.office, tid) if tid else None
            return self._send(200 if item else 404, json.dumps(item).encode(), "application/json")
        if path == "/api/task":
            from urllib.parse import parse_qs, urlparse
            tid = parse_qs(urlparse(self.path).query).get("id", [""])[0]
            with self.lock:
                item = task_detail(self.office, tid) if tid else None
            return self._send(200 if item else 404, json.dumps(item).encode(), "application/json")
        if path == "/api/brain/task":
            from urllib.parse import parse_qs, urlparse
            tid = parse_qs(urlparse(self.path).query).get("id", [""])[0]
            with self.lock:
                if not self.office.task_usage:
                    self.office.state()
                data = brain.task_trails(self.office, self.office.roster, tid) if tid else None
            return self._send(200 if data else 404, json.dumps(data).encode(), "application/json")
        if path == "/api/brain/live":
            from urllib.parse import parse_qs, urlparse
            since = float(parse_qs(urlparse(self.path).query).get("since", ["1800"])[0])
            with self.lock:
                data = brain.live(self.office, self.office.roster, since)
            return self._send(200, json.dumps(data).encode(), "application/json")
        if path == "/api/brain":
            with self.lock:
                reload_roster(self.office)
                graph = brain.build(self.brain_office, self.office.roster)
            return self._send(200, json.dumps(graph).encode(), "application/json")
        if path in ("/api/arch", "/api/arch/mermaid"):
            from urllib.parse import parse_qs, urlparse
            from . import archmap
            q = parse_qs(urlparse(self.path).query)
            with self.lock:
                data = archmap.get(0 if q.get("refresh") else 60)
            if path.endswith("mermaid"):
                return self._send(200, archmap.mermaid(data, bool(q.get("all"))).encode(), "text/plain; charset=utf-8")
            return self._send(200, json.dumps(data).encode(), "application/json")
        page = {"/": "index.html", "/index.html": "index.html", "/brain": "brain.html", "/architecture": "architecture.html"}.get(path)
        if page:
            with open(os.path.join(HERE, "static", page), encoding="utf-8") as f:
                html = f.read()
            # the pages were written for the first team; a workspace roster names its own
            roster = self.office.roster
            safe = lambda s: "".join(c for c in str(s) if c not in "\"'`<>\\")  # lands in JS strings and HTML
            html = html.replace("__PM_COMMAND__", safe(roster.get("pmCommand", "claude --agent pm"))).replace("__TEAM_NAME__", safe(roster.get("team", "AI Team")))
            return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
        self._send(404, b"not found", "text/plain")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
    ap = argparse.ArgumentParser(description="Live office view of your Claude Code agents.")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--hours", type=float, default=12, help="show agents active within this many hours")
    ap.add_argument("--brain-days", type=float, default=30, help="how far back the Brain page looks")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--workspace", help="folder made by init_team.py (read before argparse, see top of file)")
    args = ap.parse_args()
    if args.workspace and not os.path.isfile(workspace.ROSTER):
        sys.exit(f"no team in {workspace.WORKSPACE} (expected {workspace.ROSTER}).\n"
                 "Run init_team.py on it first. In Git Bash write the path with / (C:/Users/... or /c/Users/...), not \\.")
    roster = reload_roster(None)
    if roster is None:
        sys.exit(f"could not read {ROSTER}")
    if not workspace.WORKSPACE:
        print("No workspace given: showing the original team. Use --workspace <folder> for another one.")
    Handler.office = Office(roster, args.hours)
    Handler.brain_office = Office(roster, args.brain_days * 24)
    Handler.office.history = Handler.brain_office
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"🏢 {roster.get('team', 'Agent')} office running at {url}  (Ctrl+C to stop)")
    print(f"   team: {workspace.TEAM}")
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
