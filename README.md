# aiset

A live office view of your AI team, plus the team itself.

## Install

Python 3.9+. The Python package has no third-party runtime dependencies. Repository discovery uses Git; TypeScript indexing also requires Node.js and a TypeScript installation. Creating and running agent sessions requires Claude Code. From this folder:

```sh
pip install -e .          # adds the commands aiset, aiset-init and teammap
```

Without installing, run the files directly: `python src/aiset/server.py`, `python src/aiset/teammap.py`, `python src/aiset/init_team.py`. Tests: `python -m unittest discover -s tests`.

Layout: the package is `src/aiset/` (code, `static/`, `templates/`, the sample `roster.json`, `teammap_ts.js`); `tests/` and `docs/` sit next to it.

## Use it on any project

Point it at a folder of git repositories (Windows, macOS or Linux):

```sh
aiset-init ~/work/example-project --team example-project  # scan repos, write the team into <folder>/.claude
cd ~/work/example-project && claude --agent pm            # talk to the PM; first ask: "build the knowledge briefs"
aiset --workspace ~/work/example-project                  # the office for that team
```

`init_team.py` makes one engineer per repo (stack detected from `package.json`, `requirements.txt`/`pyproject.toml`, Gradle/Maven, `go.mod`; compose/nginx-only repos get a DevOps engineer), plus the PM, QA engineer and integration checker. Everything lives in the workspace, so several teams can coexist:

- `<folder>/.claude/agents/*.md`: project agents, rendered from `src/aiset/templates/`. Claude Code loads them for sessions started in the folder.
- `<folder>/.claude/team/`: `roster.json`, `knowledge/`, `tasks/`, `episodes/`, `graph/`.

**Monorepos** work too: when the folder is itself one git repository, every top-level folder with a build file (`pom.xml`, `package.json`, `requirements.txt`, `Dockerfile`…) is a service. Above 12 services (or with `--group stack`) the team gets one engineer per stack (Java, Node.js, Python, frontend) instead of one per service, and the DevOps engineer owns the root CI and build files. A monorepo's `.claude/` is added to `.git/info/exclude`, so the team stays on your machine; `--share` lets git see it.

Edit names, roles and duties in `<folder>/.claude/team/roster.json` and run `init_team.py` again: new repos are added, your names are kept, and agent files are re-rendered (except the ones where you deleted the "generated" marker line). `teammap` finds the workspace from the current directory; it parses TypeScript with the repo's own `typescript`, or with aiset's (`npm install --no-save typescript` in this folder) before the frontends have `node_modules`.

Without a workspace (no `--workspace`, not inside one), everything below works as before: `~/.claude/agents`, `~/.claude/team`, the checkout root as the code root (the package directory in a non-editable installation) and the package's `src/aiset/roster.json`.

## Use the example team

The bundled roster is a sample team with no repositories assigned. Set each engineer's `repos` list to your repository folder names, or run `init_team.py` for your workspace to generate a team from its repositories. The roster defines the office display; use `init_team.py` to create agent files.

```sh
claude --agent pm          # talk to the PM (a Claude Code session in the application folder)
aiset               # open the office in your browser (http://127.0.0.1:8765)
```

Tell the PM what you need. The PM clarifies the request with you, writes acceptance criteria, and assigns the work. Engineers report back, the QA engineer tests the changes, the integration checker checks the other services, and the PM validates the result before reporting to you. Nothing is committed unless you ask.

| Agent id | Name (from roster.json) | Role | Knowledge brief |
|---|---|---|---|
| `pm` | Deniz | Project Manager: your contact, plans and validates | (reads all briefs) |
| `backend` | Emre | Backend engineering | `backend.md` |
| `frontend` | Selin | Frontend engineering | `frontend.md` |
| `platform` | Arda | Platform engineering | `platform.md` |
| `tester` | Derya | QA: tests, lint, type-check | (uses service briefs) |
| `integration-checker` | Ece | cross-service contracts | `cross-service.md` |
| `devops` | Bora | CI/CD, deployment, observability | `devops.md` |
| `security` | Can | Authentication, authorization, security | `security.md` |
| `research` | Ada | Research and technical exploration | `research.md` |

- Agent definitions live in `~/.claude/agents/*.md`. Edit them there or with `/agents`.
- Knowledge briefs live in `~/.claude/team/knowledge/`. Agents add to their own brief under `## Field notes`. To regenerate a brief, ask your PM, for example "refresh Emre's knowledge".
- You can also use any agent from a normal Claude session, for example "ask Emre why …".

## The office

The floor is drawn isometrically by default (rooms, desks, seated bots, a whiteboard with the open task boards); **Classic** in the top-right corner switches to the flat card layout. Hover a desk for its details.

- **Desks** show each team member as an animated bot. The animation and colour show the state:
  - working: typing
  - thinking: thought bubble
  - needs you: waving, and a red banner appears at the top
  - done: coffee
  - idle: asleep
- **Speech bubbles** show what the agent is doing right now.
- **Desk cards** show the agent's current task and who assigned it.
- **Assignment lines** run from the PM to each agent with a running task.
- **Tasks** (side panel) lists the PM's tasks with the tokens and estimated cost all agents spent on each: total, a bar split by agent, and each agent's share. Click one for the breakdown by agent, every run (click a run to open that agent), and the board (brief, contract, handoffs, log) and episode. Open `/#tab=boards` to land on it.
  - A task is named by its board (`.claude/team/tasks/<id>/`) or its episode (`.claude/team/episodes/<id>.md`). A subagent belongs to the task in its `BOARD:` or `TASK:` line, or else to the task the PM was on when it assigned it. The PM's own turns go to the task it is on: the one its latest assignment or board/episode write named. Turns after a task closes (its episode is written) go to the next task the PM names, so the clarifying questions for a new request count toward it. Work with no board or episode yet shows as **open** while the session is active, and as **untracked** afterwards.
  - Tokens come from the last `--brain-days` of transcripts, not just the `--hours` window, so a long-running task's total is complete.
  - **Routes** (the drawer's second tab) shows where each agent went on the task: one line per run (files, reads, edits, searches, tests, DB queries, assignments, time), a **files × agents** grid (filled dot = edited, ring = read, dashed = searched; files more than one agent opened are highlighted; filter by repo), and each run's step-by-step route with consecutive repeats folded (`×n`). Click a file in the grid to trace only the steps that touched it. Steps are read from the whole transcript when you open the tab, including files read or searched through Bash (`cat`, `sed -n`, `grep`, `rg`, `find`…, following `cd` and `VAR=…`). The PM's steps are limited to its turns on this task. Open `/#open=task:<id>&view=routes` to land on it. Each task card has **🧭 Agent routes** (this tab) and **🧠 Map**.
  - **Map** opens `/brain#task=<id>`: the Brain shows only the places the task's agents went (files, brief sections, endpoints, models) and draws each agent's route over them in its colour. The agent opened in the side panel stands out; the others fade. Each step is listed with its time; click one to select its node. `exit` goes back to the live view.
- **Task board** groups assignments into: needs clarification, in progress, failed review, and done. It's built from the agents' reports (`STATUS:` lines).
- **Live feed** lists every tool call and message across the team.
- **Clicking a desk** opens the agent's knowledge brief status, assignment, report, and activity timeline.

- **Tokens and models**: each desk, task card and drawer shows the model (opus/sonnet/haiku) and the tokens used (fresh input, cache write, cache read, output) plus the current context size. Next to the tokens is an estimated cost at Anthropic list prices (`PRICES` in `core.py`); cache writes are priced by their TTL, since subagents write a 5 minute cache and lead sessions a 1 hour one. Most of a task's cost is usually cache writes, not the far larger cache-read token count. The top bar totals the team (the PM and the agents it assigned) and all sessions. A task card says "inherited" when the lead didn't choose a model, and shows the PM's `MODEL:` reason when it did.

## The Brain (`/brain`)

A graph of what the team knows and touched, with the same items as a tree on the side:

- **Agents** own **briefs** (split into their `##`/`###` **sections**, each with a token estimate) and **repos**.
- **Files** link to the agents that read or edited them (from transcripts, `--brain-days`, default 30) and to the sections that mention them.
- **Episodes** are task summaries the PM writes to `~/.claude/team/episodes/` when a task closes (format in `~/.claude/agents/pm.md`). They link to the agents involved and the files touched.
- **Code graph**: any `~/.claude/team/graph/*.json` file (`{"nodes": [{"id", "type", "label", ...}], "edges": [{"source", "target", "type"}]}`) is merged in, so a code indexer can extend the Brain without changes here. Node ids without a `prefix:` are namespaced as `code:`; use `file:<repo>/<path>` to attach to the file nodes above.

**Live**: the panel at the top right lists running agents (and, with a longer window, recently finished ones). Each agent's last steps are drawn on the map as a trail of arrows in its colour, a small bot marks the node it is on now, and the files it has touched in this task pulse. A step is placed by what it touched: a file it read or edited, the brief section at the line it read, or the endpoint, model or file a `teammap` query asked about. "Follow" keeps the camera on an agent; open `/brain#live=<agent-id>` (or "Watch in Brain" in the office drawer) to start following one.

Click a node or tree row for details and neighbours, double-click (or "Focus on this") to show only its neighbourhood, `/` to search, Esc to clear.

Options: `aiset --hours 24` (time window), `--port 9000`, `--no-browser`. Open `http://127.0.0.1:8765/#open=backend` to go straight to one agent.

It reads session transcripts without modifying them. It also synchronizes agent names and writes brief indexes and graph caches. It parses the transcripts Claude Code already writes in `~/.claude/projects` (`core.py`), builds the Brain graph (`brain.py`), serves both as JSON (`server.py`), and draws them (`src/aiset/static/index.html`, `src/aiset/static/brain.html`). See the installation requirements above.

"Needs you" is detected when the PM asks you a question (AskUserQuestion). If a session's tool call has had no result for 2 minutes, the office also shows "waiting for your approval?". This is a guess, because permission prompts aren't written to the transcript.

## Architecture (`/architecture`)

What each repository in the workspace is built with and what it connects to, read statically from the code and its configuration (`archmap.py`):

- **System map** in four columns: clients (frontends), services (APIs), async work and pipelines (Celery, Airflow, workers), and data and infrastructure (databases, caches, brokers, storage, auth, monitoring, services outside the workspace). Libraries, algorithms and scripts are listed below the map; **Libraries & scripts** puts them on it.
- **Links** are coloured by kind (HTTP, database, broker, jobs, cache, auth, storage). Solid links are certain: a frontend call matched to a backend route by URL (from `teammap`), or a dependency the code uses and configures. Dashed links are inferred from names, such as `BackendServiceClient` or `BACKEND_SERVICE_URL` → `backend`; **Inferred links** hides them.
- **Big systems**: above ~16 services the cards turn into one line (name, framework, a coloured dot per component) and the services column splits in two. **Clicking a box focuses on it**: the map is laid out again with only that box and what it links to, so everything fits on one screen; click another box to move along, Esc or **Show everything** to go back (**Focus on click** turns this off). **Find a service** (or `/`) highlights matches; Enter focuses the first.
- **Click a repo** for its languages, stack, how it runs (Dockerfile, compose, Makefile, `package.json`), how it's built and deployed, the infrastructure it uses and the services it calls and is called by. Every item has its evidence (`file:line` and the line itself); links open in VS Code.
- **Confidence**: *wired* (dependency or code, plus configuration), *used* (the code uses it), *declared* (only a dependency), *inferred* (from names), *exact* (URL match).
- **Mermaid** gives the same map as a Mermaid diagram for docs and PRs. **Rescan** reads the repositories again (otherwise the map is cached for a minute).
- Environment variables are read by **name only**: `.env` files and `secrets/` folders are never opened, and credentials in evidence lines are masked.
- Agents get the same in text, and more: `teammap arch [repo]`, `teammap arch <component>`, `teammap arch impact <service>`, `teammap arch path <a> <b>` (add `--json` for JSON). The scan is cached in `<team>/graph/index/arch.json` until a file changes, so a query takes ~0.2 s. Engineers, the integration checker and the PM are told when to use them (templates and agent files). Detectors are rules in `archmap.py` (`DETECTORS`); adding a technology is adding one rule. The plan for the next steps (queue producer/consumer pairs, request flows, manual corrections) is in [docs/ARCHITECTURE-PLAN.md](docs/ARCHITECTURE-PLAN.md).

## Token-saving setup (the agents use these)

- **Tool whitelists**: every agent file has a `tools:` line. Without one, an agent carries every tool, connector and skill definition (~31k tokens) on every turn; with it, it starts at ~5k.
- **Brief indexes**: `brief_index.py` writes `<name>.index.md` (sections, line ranges, token sizes) next to each knowledge brief; agents read the index and then only the sections they need. The office refreshes stale indexes on every poll; run `python src/aiset/brief_index.py <name>.md` after rewriting a brief.
- **Task boards**: shared memory per request (brief, contract, handoffs, log), so the PM doesn't relay between agents. Rules are in `pm.md` and each engineer's file.
- **`teammap`** (`src/aiset/teammap.py`, installed as the `teammap` command): a code map of the repositories configured in your team's roster.

  ```sh
  teammap endpoint items        # handler, request/response models, frontend callers
  teammap symbol get_item           # definition, signature, callers, callees
  teammap code list_items            # just that function's source, with line numbers (a class: header + method list)
  teammap arch backend      # stack, how it runs, infrastructure it uses, services it calls and is called by
  teammap arch rabbitmq                # who uses a component (mongodb, redis, kafka…), with env names and file:line
  teammap arch impact auth-server      # who calls it, two levels up: what a change can break
  teammap arch path api-gateway backend    # the HTTP hops from one service to another
  teammap model CreateItemRequest  # fields, endpoints, matching frontend type + field diff
  teammap file items_router
  teammap search item_status
  teammap index                        # refresh everything, print counts
  ```

  Python is parsed with `ast`, TypeScript with frontend's own `typescript` package (`teammap_ts.js`). The cache in `~/.claude/team/graph/index/` refreshes changed files on every query, and each refresh writes the Brain graph (`~/.claude/team/graph/<repo>.json`). Frontend calls are matched to backend routes by resolved URL; "no backend match" usually means the route doesn't exist on the current branch.

## Renaming agents

Edit the `name` fields in `<workspace>/.claude/team/roster.json`, or in `src/aiset/roster.json` when using the bundled sample from a source checkout. The running office picks the change up within a couple of seconds and copies the names into `~/.claude/agents/*.md`, so the agents use their new names too. (You can also run `python src/aiset/sync_names.py` by hand.) Agent sessions that are already running keep the old names until they're restarted.
