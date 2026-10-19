# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Security

- The office now refuses read requests whose `Host` isn't its own address. Before, only writes were checked, so a web page using DNS rebinding could read the dashboard's data, including transcript excerpts.
- Task ids in `/api/board` and `/api/task` must be plain task names. `..` previously resolved to the team folder.

### Fixed

- The office footer now suggests the `<team>-pm` launcher when `aiset-init` writes it and the command is on `PATH`; `--no-launcher` and unavailable launchers keep the roster's existing PM command.
- Code-scanning findings: explicit returns, documented intentional `except` blocks, unused variables in the dashboard, and a `Map` for the route cache. The `<team>-pm` launcher is now made executable for its owner only.

## [0.1.0] - 2026-10-18

### Added

- First public release, on PyPI as `aiset-cli`.
- `aiset-init`: scans a folder of repositories or a monorepo, detects each stack, and generates a team in `<folder>/.claude/`: a PM, one engineer per repo or stack, a QA engineer and an integration checker, with knowledge brief stubs.
- `<team>-pm` launcher, written by `aiset-init`, that starts the PM from any folder (`.cmd` on Windows).
- Workspace registry (`~/.aiset/workspaces.json`): the office finds the most recent team when started outside a workspace, and `aiset --workspace` accepts a team name.
- The office (`aiset`), a local dashboard:
  - **Office**: live view of agents, assignments, task boards, models, tokens and estimated cost.
  - **Brain**: graph of agents, briefs, episodes, files, endpoints, models and API calls, with live trails.
  - **Architecture**: services and infrastructure read from code and config, with evidence and a Mermaid export.
  - **Settings**: names, roles, duties, colours and the model per agent.
- `teammap`: code map and research commands (`endpoint`, `symbol`, `model`, `arch`, `impact`, `relevant`, `failures`) for Python and TypeScript repositories.
- Research evaluation scripts in `eval/`.
- CI on Linux, Windows and macOS for Python 3.9 to 3.13, lint, package build checks and CodeQL.

[Unreleased]: https://github.com/JamshidS/aiset/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/JamshidS/aiset/releases/tag/v0.1.0
