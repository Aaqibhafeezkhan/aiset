"""P7 issue reference parser: `parse_issue_ref("123" | "#123" | "owner/name#123" | issue URL) -> IssueRef`.

STUB: accepts only digits and a plain https://github.com/<owner>/<name>/issues/<n> URL. The full rules
(`#123`, `owner/name#123`, `www.`, no scheme, `#issuecomment-…`, pull-request and other-host errors, owner and
name validation) are the contributor issue: board 2026-10-29-aiset-run-design, issues/08-p7-parse-issue-ref.md,
interfaces.md "P7". Keep the signature; raise ValueError with a message the CLI prints as is.
"""
from __future__ import annotations

import re
from typing import Optional

from .datatypes import IssueRef

_URL = re.compile(r"https://github\.com/([A-Za-z0-9-]+/[A-Za-z0-9._-]+)/issues/(\d+)")


def parse_issue_ref(text: str, default_repo: Optional[str] = None) -> IssueRef:
    text = (text or "").strip()
    if text.isdigit():
        number, repo = int(text), default_repo
    else:
        m = _URL.fullmatch(text)
        if not m:
            raise ValueError(f"not an issue number or URL: {text!r}")
        repo, number = m.group(1), int(m.group(2))
    if number < 1:
        raise ValueError("issue numbers start at 1")
    return IssueRef(repo=repo, number=number)
