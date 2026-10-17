#!/usr/bin/env python3
"""Write a small table of contents next to each knowledge brief (<name>.index.md).

Agents read the index (about 1k tokens) instead of the whole brief (10k+), then read
only the sections they need with Read offset/limit. Field notes stay at the end of the
brief, so appending to them never shifts the line numbers above.

The office server refreshes stale indexes on every poll; run this by hand after
rewriting a brief:  ./brief_index.py            (all briefs)
                    ./brief_index.py frontend.md (one brief)
"""
import os
import re
import sys
from glob import glob

if __name__ == "__main__" and not __package__:  # run as a file: python src/aiset/brief_index.py
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    __package__ = "aiset"
from .workspace import KNOWLEDGE  # noqa: E402
ALWAYS = re.compile(r"glossary|pitfall|never do", re.I)


def index_path(brief):
    return brief[:-3] + ".index.md"


def build(brief):
    with open(brief, encoding="utf-8") as f:
        lines = f.read().splitlines()
    heads = [(i + 1, len(m.group(1)), m.group(2).strip())
             for i, l in enumerate(lines) if (m := re.match(r"^(##|###) (.+)", l))]
    name = os.path.basename(brief)
    header = next((l.lstrip("> ").strip() for l in lines[:6] if l.startswith(">")), "")
    out = [f"# Index of {name}", "",
           f"Brief: `{brief}` · {len(lines)} lines · ~{sum(len(l) + 1 for l in lines) // 4} tokens if read whole.",
           f"Source: {header}" if header else "",
           "",
           "Read the sections your task needs with `Read(file_path, offset=<start>, limit=<end - start + 1>)`.",
           "Always read the sections marked ★, and the Field notes (newest learnings).", "",
           "| Lines | ~Tokens | Section |", "|---|---|---|"]
    for n, (start, level, title) in enumerate(heads):
        end = next((s - 1 for s, lv, _ in heads[n + 1:] if lv <= level), len(lines))
        tokens = sum(len(l) + 1 for l in lines[start - 1:end]) // 4
        star = " ★" if ALWAYS.search(title) or title.lower() == "field notes" else ""
        indent = "└ " if level == 3 else ""
        last = "end" if title.lower() == "field notes" else end  # notes grow at the end of the file
        out.append(f"| {start}–{last} | {tokens} | {indent}{title}{star} |")
    return "\n".join(out) + "\n"


def refresh(briefs=None):
    """Rewrite indexes whose brief changed since the index was written. Returns the names updated."""
    changed = []
    for brief in briefs or glob(os.path.join(KNOWLEDGE, "*.md")):
        if brief.endswith(".index.md"):
            continue
        idx = index_path(brief)
        try:
            if os.path.exists(idx) and os.path.getmtime(idx) >= os.path.getmtime(brief):
                continue
            text = build(brief)
            with open(idx, "w", encoding="utf-8") as f:
                f.write(text)
            changed.append(os.path.basename(brief))
        except OSError:
            continue
    return changed


if __name__ == "__main__":
    names = sys.argv[1:]
    targets = [os.path.join(KNOWLEDGE, n) for n in names] or None
    if targets:  # explicit request: rebuild even if it looks fresh
        for t in targets:
            if os.path.exists(index_path(t)):
                os.utime(index_path(t), (0, 0))
    print("indexed:", ", ".join(refresh(targets)) or "nothing (all fresh)")
