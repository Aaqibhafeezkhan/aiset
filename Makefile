# aiset: common tasks. `make` or `make help` lists them.
# Workspace targets take WS=<folder of repositories>, e.g. `make office WS=~/work/shop`.

PYTHON ?= $(shell python -c "import sys" >/dev/null 2>&1 && echo python || echo python3)
SRC    := src/aiset
WS     ?=
TEAM   ?=
TASKS  ?= $(WS)/.claude/team/eval/tasks.json
RUNS   ?= 1
PORT   ?= 8765
Q      ?=

ws_flag = $(if $(WS),--workspace "$(WS)")

.DEFAULT_GOAL := help
.PHONY: help install typescript test check office init index impact relevant failures eval eval-agent clean

help: ## list the targets
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  make %-12s %s\n", $$1, $$2}'
	@echo ""
	@echo "  Variables: WS=<workspace> TEAM=<name> Q=<query> TASKS=<tasks.json> RUNS=<n> PORT=<port> PYTHON=<python>"

install: ## pip install -e . (adds the aiset, aiset-init and teammap commands)
	$(PYTHON) -m pip install -e .

typescript: ## TypeScript for teammap, used before a frontend has its own node_modules
	npm install --no-save typescript

test: ## run the tests
	$(PYTHON) -m unittest discover -s tests

check: ## compile everything, then run the tests
	$(PYTHON) -m compileall -q $(SRC) eval tests
	$(PYTHON) -m unittest discover -s tests

office: ## open the office (WS= optional: without it, the workspace you're in or the default team)
	$(PYTHON) $(SRC)/server.py $(ws_flag) --port $(PORT)

init: _need_ws ## set up or update the team in WS (TEAM= optional)
	$(PYTHON) $(SRC)/init_team.py "$(WS)" $(if $(TEAM),--team "$(TEAM)")

index: _need_ws ## refresh WS's code index and Brain graph
	cd "$(WS)" && $(PYTHON) "$(CURDIR)/$(SRC)/teammap.py" index

impact: _need_ws _need_q ## teammap impact Q=<endpoint path|function|Model> in WS
	cd "$(WS)" && $(PYTHON) "$(CURDIR)/$(SRC)/teammap.py" impact $(Q)

relevant: _need_ws _need_q ## teammap relevant Q="<task in a sentence>" in WS
	cd "$(WS)" && $(PYTHON) "$(CURDIR)/$(SRC)/teammap.py" relevant "$(Q)"

failures: _need_ws _need_q ## teammap failures Q=<saved test output> in WS
	cd "$(WS)" && $(PYTHON) "$(CURDIR)/$(SRC)/teammap.py" failures "$(Q)"

eval: _need_ws ## compare output sizes, current way vs research tools (TASKS= defaults to WS's .claude/team/eval/tasks.json)
	$(PYTHON) eval/research_eval.py "$(TASKS)" --workspace "$(WS)"

eval-agent: _need_ws ## the same with real Claude Code runs: spends tokens (RUNS= runs per variant)
	$(PYTHON) eval/research_eval.py "$(TASKS)" --workspace "$(WS)" --mode agent --confirm-cost --runs $(RUNS)

clean: ## remove caches and build output (not the workspaces' indexes)
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in [*pathlib.Path('.').rglob('__pycache__'), pathlib.Path('build'), pathlib.Path('dist'), *pathlib.Path('src').glob('*.egg-info')] if 'node_modules' not in p.parts]"

_need_ws:
	@test -n "$(WS)" || { echo "set WS=<workspace folder>, e.g. make $(MAKECMDGOALS) WS=~/work/shop"; exit 2; }

_need_q:
	@test -n "$(Q)" || { echo "set Q=..., e.g. make impact WS=... Q='/items/{item_id} GET'"; exit 2; }
