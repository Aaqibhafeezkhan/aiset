# Contributing to Aiset

Thanks for helping. Bug reports, ideas, docs fixes and code are all welcome.

## Ways to contribute

- **Report a bug** or **suggest a feature** with the [issue templates](https://github.com/JamshidS/aiset/issues/new/choose).
- **Ask a question** or share how you use Aiset in [Discussions](https://github.com/JamshidS/aiset/discussions).
- **Improve the docs** in `README.md` and `docs/`.
- **Send a pull request** for an open issue. For anything larger than a small fix, open an issue first so we can agree on the approach before you spend time on it.

Security problems go through [SECURITY.md](SECURITY.md), not public issues.

## Picking an issue and opening your first PR

Look for issues labeled [`good first issue`](https://github.com/JamshidS/aiset/labels/good%20first%20issue) or [`help wanted`](https://github.com/JamshidS/aiset/labels/help%20wanted). Check for existing comments and pull requests, then comment on the issue before starting so others know you are working on it. If no pull request is opened after a week, someone else may take it.

For your first pull request from a fork, CI waits for a maintainer to approve the workflow run. A missing CI result does not mean the checks failed. If you have a workflow run from your fork, link it in the PR while you wait.

AI-assisted contributions are welcome, including work prepared with Claude Code or Codex. The same standards apply: read and understand every line you submit, make sure tests cover the change and pass locally, and say what was generated in the PR description.

Keep one issue per pull request and leave unrelated formatting changes and renames out of it.

## Development setup

You need Python 3.9+ and Git. Node.js is only needed if you work on TypeScript indexing.

```sh
git clone https://github.com/JamshidS/aiset.git
cd aiset
python -m pip install -e .
```

With Make available, `make` lists every shortcut. The ones you'll use most:

```sh
make check            # compile everything, then run the tests
make test             # tests only
make lint             # ruff, as CI runs it (pip install ruff)
make office WS=...    # run the dashboard against a workspace
make typescript       # install TypeScript for teammap's TS indexer
```

Without Make: `python -m unittest discover -s tests`.

### Project layout

| Path | What lives there |
|---|---|
| `src/aiset/` | the package: dashboard server, `aiset-init`, `teammap`, Brain and architecture maps |
| `src/aiset/static/`, `templates/` | dashboard front end and agent templates |
| `tests/` | `unittest` tests and fixtures |
| `eval/` | research-tool evaluation scripts (`make eval-agent` spends model tokens) |
| `docs/` | user guide, feature inventory, research results |

## Guidelines

- **No new runtime dependencies.** The package uses only the Python standard library. If you think a dependency is worth it, raise it in an issue first.
- **Stay compatible with Python 3.9.** Avoid `match`, `X | Y` type unions at runtime, and other 3.10+ features.
- **Keep the dashboard local.** It binds to `127.0.0.1` and validates `Host`/`Origin`. Don't weaken that.
- **Match the surrounding code**: naming, comment density and structure.
- **Add or update tests** for behaviour changes, and make sure `make check` and `make lint` pass. CI runs both on Linux, Windows and macOS for every pull request.
- **Note user-facing changes** under `[Unreleased]` in [CHANGELOG.md](CHANGELOG.md).
- **Update the docs** (`README.md`, `docs/USER-GUIDE.md`, `docs/FEATURES.md`) when you change user-facing behaviour.
- **Be honest about measurements.** Claims about token or cost savings in docs need evidence from `eval/`.

## Commits and pull requests

1. Branch from `master` (for example `fix/brain-graph-empty-workspace`).
2. Use [Conventional Commit](https://www.conventionalcommits.org/) prefixes: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`.
3. Keep each PR focused on one change. Fill in the pull request template.
4. Link the issue it closes (`Closes #12`).
5. A maintainer will review. Expect questions; they are about the code, not about you.

## Code of conduct

Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
