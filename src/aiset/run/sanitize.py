"""P1a hidden-character sanitiser: `visible_text(text) -> Visible`.

STUB: returns the text unchanged and reports nothing. Until the real one lands, zero-width, bidi, tag and
control characters and HTML comments in an issue are NOT made visible or counted at gate 1. The full rules
are the contributor issue: board 2026-10-29-aiset-run-design, issues/01-p1a-visible-text.md,
interfaces.md "P1a". Keep the signature.
"""
from __future__ import annotations

from .datatypes import Visible


def visible_text(text: str) -> Visible:
    return Visible(text or "", {})
