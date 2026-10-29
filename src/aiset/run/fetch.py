"""Read-only GitHub calls for `aiset run`, through the user's `gh` (its auth, its host config): the issue and the
repo's default branch. Writing to GitHub (the PR) lives in gitops.create_pr, behind gate 2."""
import json
import subprocess

from . import RunError, program

ISSUE_FIELDS = "number,title,body,url,state,author,labels,updatedAt"


def gh(args, cwd=None):
    """stdout of `gh <args>`; RunError with gh's own message when it fails or isn't installed."""
    exe = program("gh", cwd, hint=": install the GitHub CLI from https://cli.github.com and run `gh auth login`")
    p = subprocess.run([exe, *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RunError(f"gh {args[0]} {args[1] if len(args) > 1 else ''} failed: {(p.stderr or p.stdout).strip()}")
    return p.stdout


def issue(repo, number, comments=False):
    """The issue as `gh issue view --json` returns it; a pull request number is refused."""
    fields = ISSUE_FIELDS + (",comments" if comments else "")
    data = json.loads(gh(["issue", "view", str(number), "--repo", repo, "--json", fields]))
    if "/pull/" in (data.get("url") or ""):
        raise RunError(f"#{number} is a pull request, not an issue")
    return data


def default_branch(repo):
    out = gh(["repo", "view", repo, "--json", "defaultBranchRef", "--jq", ".defaultBranchRef.name"]).strip()
    if not out:
        raise RunError(f"could not read the default branch of {repo}; pass --base")
    return out
