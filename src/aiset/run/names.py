"""P8 board slug and branch name from an issue number and title.

STUB: lowercase, every run of characters other than a-z/0-9 becomes one `-`; the slug is cut to max_len at the
last `-` that fits (`issue-<n>` is never cut), and the branch name to its own max_len. No NFKD yet (so
`İstanbul` loses its first letter). The full rules (NFKD + ASCII, cut at the last `-` within max_len,
`issue-<n>` never cut, valid git ref, matches core.TASK_ID with a date prefix) are the contributor issue:
board 2026-10-29-aiset-run-design, issues/09-p8-names.md, interfaces.md "P8". Keep the signatures.
"""
from __future__ import annotations

import re


def _cut(head: str, words: str, max_len: int) -> str:
    room = max_len - len(head) - 1
    if room < 1:
        words = ""  # `issue-<n>` alone is longer than max_len: it is never cut
    elif len(words) > room:
        words = words[:room + 1]
        words = words[:words.rfind("-")] if "-" in words else ""
    words = words.strip("-")
    return f"{head}-{words}" if words else head


def board_slug(number: int, title: str, *, max_len: int = 40) -> str:
    words = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return _cut(f"issue-{number}", words, max_len)


def branch_name(number: int, title: str, *, prefix: str = "aiset/", max_len: int = 60) -> str:
    words = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return prefix + _cut(f"issue-{number}", words, max_len - len(prefix))
