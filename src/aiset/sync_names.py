#!/usr/bin/env python3
"""Copy the names in roster.json into the agent definitions (<agents>/*.md, see workspace.py).

roster.json is the single place to rename team members. The office server runs this
automatically whenever roster.json changes; you can also run it by hand.
Only the name is rewritten, in three places: the description line, the
"You are **Name, the Role**" line, and the PM's team table.
"""
import os
import re
import sys

if __name__ == "__main__" and not __package__:  # run as a file: python src/aiset/sync_names.py
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    __package__ = "aiset"
from .workspace import AGENTS, load_roster  # noqa: E402


def sync(roster):
    changed = []
    for m in roster["members"]:
        path = os.path.join(AGENTS, m["id"] + ".md")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        new = re.sub(r'^(description: ")[^"·]+?( · )', lambda x: x.group(1) + m["name"] + x.group(2), text, count=1, flags=re.M)
        new = re.sub(r"(You are \*\*).+?(, the )", lambda x: x.group(1) + m["name"] + x.group(2), new, count=1)
        if new != text:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new)
            changed.append(m["id"])
    pm = os.path.join(AGENTS, "pm.md")
    if os.path.exists(pm):
        with open(pm, encoding="utf-8") as f:
            text = f.read()
        new = text
        for m in roster["members"]:
            new = re.sub(r"^(\| `%s` \| ).+?( · )" % re.escape(m["id"]),
                         lambda x: x.group(1) + m["name"] + x.group(2), new, count=1, flags=re.M)
        if new != text:
            with open(pm, "w", encoding="utf-8") as f:
                f.write(new)
            changed.append("pm table")
    return changed


if __name__ == "__main__":
    print("updated:", ", ".join(sync(load_roster())) or "nothing (already in sync)")
