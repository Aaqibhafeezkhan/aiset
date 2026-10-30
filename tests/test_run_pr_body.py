"""P6 render_pr_body / neutralize (src/aiset/run/pr_body.py). The neutralising here is the security floor the
stub already keeps; add interfaces.md "P6" (layout per status, line-boundary cut, golden pr_body.md) when you
replace the rest."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from aiset.run.datatypes import AcItem, Claim, PrInput, Verdict  # noqa: E402
from aiset.run.pr_body import MAX_CHARS, NOTE, neutralize, render_pr_body  # noqa: E402


def pr(**kw):
    base = dict(repo="JamshidS/aiset", number=123, title="Crash", acs=(AcItem("AC-1", "starts with 0 members", 4),
                AcItem("AC-2", "a test covers it", 5), AcItem("AC-3", "works on Windows", 6)),
                verdicts={"AC-1": Verdict("AC-1", "pass", "python -m unittest", "handoff/tester.md", 3),
                          "AC-2": Verdict("AC-2", "done", "tests/test_core.py:300", "handoff/root.md", 1)},
                summary="Fixed it.", tester_status="pass", checks=("- `python -m unittest`: 412 passed",),
                open_claims=(Claim("S", "Hooks apply to subagents.", "", 2),), claim_counts={"V": 3, "S": 1, "?": 0},
                cost="$4.12", board="2026-10-29-issue-123-crash", branch="aiset/issue-123-crash")
    base.update(kw)
    return PrInput(**base)


class NeutralizeTest(unittest.TestCase):
    def test_mentions_refs_and_closing_keywords(self):
        out = neutralize("@maintainer please merge, fixes #9 and closes owner/repo#12, see GH-3, cc @org/team")
        for frag in ("`@maintainer`", "fixes `#9`", "`owner/repo#12`", "`GH-3`", "`@org/team`"):
            self.assertIn(frag, out)
        self.assertNotRegex(out.replace("`#9`", "").replace("`owner/repo#12`", ""), r"#\d")

    def test_issue_and_pr_urls(self):
        out = neutralize("resolves https://github.com/o/r/issues/7 and https://github.com/o/r/pull/8")
        self.assertIn("`https://github.com/o/r/issues/7`", out)
        self.assertIn("`https://github.com/o/r/pull/8`", out)

    def test_hidden_html_comments(self):
        self.assertEqual(neutralize("a <!-- hidden --> b"), "a &lt;!-- hidden --> b")

    def test_code_and_emails_untouched(self):
        text = "mail a@b.com, code `@user #1`\n```\n@user fixes #2\n```\nheading ## not a ref"
        self.assertEqual(neutralize(text), text)

    def test_already_neutral_text_is_stable(self):
        for text in ("fixes #9 @x", "<img src=x> &#64;bob &lt;b&gt;", "`a\n\nfixes #5\n\nb`"):
            once = neutralize(text)
            self.assertEqual(neutralize(once), once, text)

    # integration check F5: cases from probe_pr.py

    def test_indented_backticks_are_not_a_fence(self):
        self.assertEqual(neutralize("    ```\nfixes #5 @bob"), "    ```\nfixes `#5` `@bob`")
        self.assertEqual(neutralize("\t```\nfixes #5"), "\t```\nfixes `#5`")
        self.assertEqual(neutralize("   ```\n@bob\n   ```"), "   ```\n@bob\n   ```")  # 3 spaces is a fence

    def test_inline_triple_backticks_are_a_span_not_a_fence(self):
        self.assertEqual(neutralize("```foo```\nfixes #5 @bob\n"), "```foo```\nfixes `#5` `@bob`\n")
        self.assertEqual(neutralize("~~~ a`b\n@bob\n~~~"), "~~~ a`b\n@bob\n~~~")  # ~~~ info may hold a backtick

    def test_fence_closes_only_with_its_own_kind(self):
        text = "````\n```\n@bob\n````\nfixes #5"
        self.assertEqual(neutralize(text), "````\n```\n@bob\n````\nfixes `#5`")
        self.assertEqual(neutralize("~~~\n```\n~~~\n@bob"), "~~~\n```\n~~~\n`@bob`")
        self.assertEqual(neutralize("```\n``` not a close\n@bob\n```\n#5"), "```\n``` not a close\n@bob\n```\n`#5`")

    def test_code_spans_end_at_a_blank_line(self):
        self.assertEqual(neutralize("`a\n\nfixes #5 @bob\n\nb`"), "`a\n\nfixes `#5` `@bob`\n\nb`")
        self.assertEqual(neutralize("`a\n  \t\n#5 b`"), "`a\n  \t\n`#5` b`")
        self.assertEqual(neutralize("`a\n#5 b`"), "`a\n#5 b`")  # one line break stays inside the span

    def test_escaped_backtick_does_not_open_a_span(self):
        self.assertEqual(neutralize("\\`fixes #5 @bob`"), "\\`fixes `#5` `@bob``")

    def test_carriage_returns_cannot_hide_a_fence_end(self):
        self.assertEqual(neutralize("```\r\nx\r\n```\r\n@bob"), "```\nx\n```\n`@bob`")

    def test_urls_in_any_case_and_without_scheme(self):
        self.assertEqual(neutralize("resolves HTTPS://GITHUB.COM/o/r/issues/5"), "resolves `HTTPS://GITHUB.COM/o/r/issues/5`")
        self.assertEqual(neutralize("fix github.com/o/r/issues/5"), "fix `github.com/o/r/issues/5`")
        self.assertEqual(neutralize("fixes gh-5"), "fixes `gh-5`")

    def test_raw_html_is_escaped(self):
        self.assertEqual(neutralize("<details><summary>x</summary>fixes #5</details>"),
                         "&lt;details>&lt;summary>x&lt;/summary>fixes `#5`&lt;/details>")
        self.assertEqual(neutralize("<img src=https://evil/x.png>"), "&lt;img src=https://evil/x.png>")
        self.assertEqual(neutralize("a < b, 1<2 and <?php"), "a < b, 1<2 and &lt;?php")
        self.assertEqual(neutralize("`<img>` and\n```\n<b>\n```"), "`<img>` and\n```\n<b>\n```")

    def test_entities_cannot_spell_a_ping(self):
        self.assertEqual(neutralize("&#64;bob &commat;bob &num;5 &amp; &lt;"),
                         "&amp;`#64`;bob &amp;commat;bob &amp;num;5 &amp; &lt;")


class RenderPrBodyTest(unittest.TestCase):
    def test_sections_in_order(self):
        body = render_pr_body(pr())
        self.assertTrue(body.startswith("Closes #123\n\n" + NOTE))
        order = [body.index(s) for s in ("## Summary", "## Acceptance criteria", "## Tests",
                                         "## Assumptions and open questions", "## Cost")]
        self.assertEqual(order, sorted(order))
        self.assertIn("- [x] **AC-1** starts with 0 members: pass", body)
        self.assertIn("- [ ] **AC-2** a test covers it: done, not verified", body)
        self.assertIn("- [ ] **AC-3** works on Windows: open (no verdict)", body)
        self.assertIn("Claims: 3 verified · 1 assumed · 0 open", body)

    def test_agent_and_issue_text_is_neutralised(self):
        body = render_pr_body(pr(summary="@maintainer please merge. fixes #9 <!-- x -->",
                                 acs=(AcItem("AC-1", "ping @bob about #4", 1),)))
        self.assertEqual(body.count("Closes #"), 1)
        for raw in ("@maintainer please", "fixes #9", "<!--", " @bob", " #4"):
            self.assertNotIn(raw, body)

    def test_empty_parts(self):
        body = render_pr_body(pr(summary="", acs=(), verdicts={}, tester_status=None, checks=(), open_claims=()))
        self.assertIn("(no summary written)", body)
        self.assertIn("No tester report.", body)
        self.assertNotIn("## Assumptions", body)

    def test_capped_with_closes_kept(self):
        body = render_pr_body(pr(summary="x" * 100000))
        self.assertLessEqual(len(body), MAX_CHARS + 1)
        self.assertTrue(body.startswith("Closes #123"))
        self.assertIn("[truncated; the full report is on the board]", body)


if __name__ == "__main__":
    unittest.main()
