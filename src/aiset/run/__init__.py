"""`aiset run <issue>`: work a GitHub issue with the team, then open a draft PR after the user approves.

Core modules (cli, fetch, board, gitops, launch, gate, publish) hold the flow and the security boundaries.
The pure parts (refs, names, sanitize, issue_md, ac, verdicts, claims, cost, pr_body) are small functions
with a fixed signature from datatypes.py; several start as naive stubs meant to be replaced by contributors.
"""


class RunError(Exception):
    """A failure the CLI prints as one line and exits 1 on (no traceback)."""


# Folders agents can write to (the workspace): cli.run sets it. PATH entries inside them are never searched.
AVOID = []


def program(name, *avoid, hint=""):
    """Absolute path of `name` (git, gh, claude, the editor) through gate.resolve_program, skipping the current
    folder, relative PATH entries and anything inside `avoid` or AVOID; RunError when there is none."""
    from .gate import resolve_program
    exe = resolve_program(name, *avoid, *AVOID)  # not cached: tests and callers may change PATH or AVOID
    if not exe:
        raise RunError(f"`{name}` was not found on PATH (folders inside the repo or workspace, the current folder "
                       f"and relative PATH entries are skipped on purpose){hint}")
    return exe
