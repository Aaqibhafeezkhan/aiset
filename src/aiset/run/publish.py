"""Collect a finished board into a PrInput, render pr.md through P6, and make the commit message / PR title."""
import re
import time
import unicodedata

from . import board
from .claims import count_claims, parse_claims
from .cost import cost_line
from .pr_body import render_pr_body
from .datatypes import AcItem, PrInput
from .verdicts import parse_verdicts


def safe_title(title):
    """The issue title as a commit subject and PR title: mentions and issue references can't ping or close.
    Invisible format characters (zero-width space, word joiner, bidi marks: Unicode Cf) go first, so `#\\u20605`
    can't hide a reference; issue/PR URLs become `owner/name# n`; `#n`, `GH-n` get a space after `#` / `-`."""
    t = "".join(ch for ch in (title or "") if unicodedata.category(ch) != "Cf")
    t = " ".join(t.split())
    t = re.sub(r"(?:https?://)?(?:www\.)?github\.com/([\w.-]+/[\w.-]+)/(?:issues|pull)/(\d+)\S*", r"\1#\2", t, flags=re.I)
    t = re.sub(r"(?<![\w.+-])@(?=[A-Za-z0-9])", "", t)
    return re.sub(r"(#|GH-)(\d)", r"\1 \2", t, flags=re.I)


def _tester(board_dir):
    text = board.read_text(board_dir, "handoff/tester.md")
    if not text:
        return None, ()
    m = re.findall(r"^STATUS:\s*(pass|fail)\b", text, re.M | re.I)
    checks, inside = [], False
    for line in text.split("\n"):
        if line.startswith("## "):
            inside = line.strip().lower() == "## checks"
            continue
        if inside and line.strip():
            checks.append(line.rstrip())
    return (m[-1].lower() if m else None), tuple(checks)


def _usage(board_id):
    """This board's usage from the office's transcript scan; None when it can't be read."""
    try:
        from ..core import Office
        from ..workspace import load_roster
        office = Office(load_roster(), hours=24 * 30)
        office.scan()
        return office.tasks_usage(time.time()).get(board_id)
    except Exception:  # cost is a nice-to-have in the PR; never block publishing on it
        return None


def collect(board_dir, run, usage=None):
    acs = tuple(AcItem(i, t, 0) for i, t in board.brief_acs(board_dir))
    docs = board.handoffs(board_dir)
    summary = board.read_text(board_dir, "summary.md")
    claim_texts = [summary] + [t for _, t in docs]
    claims = [c for t in claim_texts for c in parse_claims(t)]
    counts = {"V": 0, "S": 0, "?": 0}
    for t in claim_texts:
        for k, v in count_claims(t).items():
            counts[k] = counts.get(k, 0) + v
    status, checks = _tester(board_dir)
    board_id = board_dir.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    return PrInput(
        repo=run["issue"]["repo"], number=run["issue"]["number"], title=run.get("title") or "",
        acs=acs, verdicts=parse_verdicts(docs, [a.id for a in acs]), summary=summary,
        tester_status=status, checks=checks, open_claims=tuple(c for c in claims if c.label in ("S", "?")),
        claim_counts=counts, cost=cost_line(usage), board=board_id, branch=run.get("branch") or "")


def render(board_dir, run, usage=None):
    """Writes pr.md and returns (path, text)."""
    pr = collect(board_dir, run, usage)
    if usage is None:
        pr = PrInput(**{**pr.__dict__, "cost": cost_line(_usage(pr.board))})
    text = render_pr_body(pr)
    return board.write_text(board_dir, "pr.md", text), text
