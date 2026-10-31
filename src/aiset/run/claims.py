"""P4 claim-label parser (part of #61): `parse_claims(text) -> [Claim]`, `count_claims(text) -> {"V","S","?"}`.

STUB: only a label at the very start of a line (`[V] text`, `[S] text`, `[?] text`), no evidence inside
the brackets, no list markers, no labels mid-line, no code skipping. The full rules are the contributor issue:
board 2026-10-29-aiset-run-design, issues/05-p4-parse-claims.md, interfaces.md "P4". Keep the signatures.
"""
from __future__ import annotations

import re
from typing import Dict, List

from .datatypes import Claim

_LINE = re.compile(r"^\[(V|S|\?)\]\s+(\S.*)$")


def parse_claims(text: str) -> List[Claim]:
    out = []
    for n, line in enumerate((text or "").split("\n"), 1):
        m = _LINE.match(line.rstrip())
        if m:
            out.append(Claim(m.group(1), m.group(2).strip(), "", n))
    return out


def count_claims(text: str) -> Dict[str, int]:
    counts = {"V": 0, "S": 0, "?": 0}
    for c in parse_claims(text):
        counts[c.label] += 1
    return counts
