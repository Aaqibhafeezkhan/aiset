"""Data shared by the `aiset run` parts. The contract every part is built against: change a field only with a
core review, because the contributor issues (board 2026-10-29-aiset-run-design, interfaces.md §0) cite it."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class IssueRef:
    repo: Optional[str]  # "owner/name"; None when only a number was given and there's no default repo
    number: int  # >= 1


@dataclass(frozen=True)
class Visible:  # P1a
    text: str
    counts: Dict[str, int] = field(default_factory=dict)  # only non-zero keys: format, tag, control, private, html_comment


@dataclass(frozen=True)
class IssueSnapshot:  # P1b
    markdown: str
    counts: Dict[str, int]  # P1a counts summed over title, body, comments
    truncated: Tuple[str, ...]  # fields that were cut: "title", "body", "comment:3", "comments"
    body_sha256: str  # hex sha256 of the raw body as fetched (UTF-8), "" for no body


@dataclass(frozen=True)
class AcItem:
    id: str  # "AC-1"
    text: str
    line: int  # 1-based line in the body; 0 when not from the body (typed in at gate 1)


@dataclass(frozen=True)
class AcResult:  # P2
    items: Tuple[AcItem, ...]
    rule: str  # "ac-lines" | "section" | "tasklist" | "none"
    dropped: int  # items beyond max_items


@dataclass(frozen=True)
class Verdict:  # P3
    ac: str  # "AC-1"
    status: str  # "pass" | "fail" | "done" | "untested" | "blocked" | "not-mine"
    evidence: str  # text after the status, "" if none
    source: str  # doc name as passed in, e.g. "handoff/tester.md"
    line: int


@dataclass(frozen=True)
class Claim:  # P4
    label: str  # "V" | "S" | "?"
    text: str
    evidence: str  # text inside the brackets after the label, "" if none
    line: int


@dataclass(frozen=True)
class PrInput:  # P6
    repo: str
    number: int
    title: str
    acs: Tuple[AcItem, ...]
    verdicts: Dict[str, Verdict]
    summary: str  # summary.md, written by the PM
    tester_status: Optional[str]  # "pass" | "fail" | None (no tester report)
    checks: Tuple[str, ...]  # lines of the tester's "## Checks" section, as written
    open_claims: Tuple[Claim, ...]  # [S] and [?] claims from the board
    claim_counts: Dict[str, int]  # {"V": n, "S": n, "?": n}
    cost: str  # P5 cost_line output
    board: str  # board id, e.g. "2026-10-29-issue-123-fix-login"
    branch: str
