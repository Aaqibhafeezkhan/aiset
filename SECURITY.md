# Security Policy

## Supported versions

Aiset is pre-1.0. Security fixes land on `master` and in the next release; older versions are not patched.

| Version | Supported |
|---|---|
| latest `master` | ✅ |
| 0.1.x | ✅ |
| older | ❌ |

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately through GitHub: go to the repository's **Security** tab and choose **Report a vulnerability** ([direct link](https://github.com/JamshidS/aiset/security/advisories/new)).

Include as much of this as you can:

- what the issue is and what an attacker could do with it
- the affected version or commit
- steps to reproduce, or a proof of concept
- your OS and Python version, if relevant
- any suggested fix

### What to expect

- **Acknowledgement** within 3 business days.
- **Initial assessment** (confirmed, needs more info, or not a vulnerability) within 7 days.
- **Fix and disclosure**: we aim to release a fix within 30 days for confirmed issues, then publish a GitHub Security Advisory. We will credit you unless you prefer to stay anonymous.

Please give us a reasonable chance to fix the issue before disclosing it publicly.

## Scope

Aiset runs on the developer's own machine. Things we especially want to hear about:

- **The local dashboard** (`aiset`, `src/aiset/server.py`): it binds to `127.0.0.1` and checks the `Host` and `Origin` headers. Bypasses of those checks, DNS-rebinding, CSRF from a web page the user visits, or anything that lets a remote site read transcripts or change settings.
- **Path handling**: reading or writing files outside the selected workspace or its `.claude/` folder (path traversal, symlink tricks).
- **Code execution**: `aiset-init`, `teammap` or the TypeScript indexer executing code from an indexed repository in a way the user wouldn't expect.
- **Data exposure**: transcripts, briefs, or settings leaking somewhere they shouldn't.

### Out of scope

- Exposing the dashboard to a network yourself (for example through a reverse proxy or port forward). It is designed for local use only; see "Storage & privacy" in the [README](README.md).
- Behaviour of Claude Code, the Claude API, or the model itself. Report those to [Anthropic](https://www.anthropic.com/responsible-disclosure-policy).
- Prompt injection that only changes what an agent writes in its own workspace files, without crossing a security boundary.
- Vulnerabilities in third-party tools Aiset calls (Node.js, TypeScript, Git). Report those upstream.
