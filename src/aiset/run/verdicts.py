"""P3 AC verdict parser (part of #58): `parse_verdicts(docs, known) -> {ac id: Verdict}`.

STUB: only lines that are exactly `AC-<n>: pass` or `AC-<n>: fail` (no evidence, no other statuses, no
list markers, no `not-mine` rule, no code-fence skipping); later lines win. The full rules are the contributor
issue: board 2026-10-29-aiset-run-design, issues/04-p3-parse-verdicts.md, interfaces.md "P3".
Keep the signature.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, Sequence, Tuple

from .datatypes import Verdict

_LINE = re.compile(r"^(AC-\d+): (pass|fail)\s*$")


def parse_verdicts(docs: Sequence[Tuple[str, str]], known: Iterable[str]) -> Dict[str, Verdict]:
    known = set(known)
    out = {}
    for name, text in docs:
        for n, line in enumerate((text or "").split("\n"), 1):
            m = _LINE.match(line)
            if m and m.group(1) in known:
                out[m.group(1)] = Verdict(m.group(1), m.group(2), "", name, n)
    return out
