"""P2 acceptance-criteria extractor: `extract_ac(body) -> AcResult`.

STUB: only task-list lines `- [ ] text` / `- [x] text` (rule "tasklist"), no code-fence or HTML-comment
skipping, no `AC-n:` lines or "Acceptance criteria" sections, no length cap. The full rules are the contributor
issue: board 2026-10-29-aiset-run-design, issues/03-p2-extract-ac.md, interfaces.md "P2". Keep the signature.
"""
from __future__ import annotations

import re

from .datatypes import AcItem, AcResult

_TASK = re.compile(r"^\s*[-*+]\s+\[[ xX]\]\s+(\S.*)$")


def extract_ac(body: str, *, max_items: int = 20, max_len: int = 300) -> AcResult:
    found = []
    for n, line in enumerate((body or "").split("\n"), 1):
        m = _TASK.match(line)
        if m:
            found.append((m.group(1).strip(), n))
    items = tuple(AcItem(f"AC-{i}", text, n) for i, (text, n) in enumerate(found[:max_items], 1))
    if not items:
        return AcResult((), "none", 0)
    return AcResult(items, "tasklist", max(0, len(found) - max_items))
