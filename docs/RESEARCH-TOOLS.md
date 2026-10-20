# Research tools: results report

Status: 2026-10-17. For usage and limitations, see the [user guide](USER-GUIDE.md#research-tools-teammap-impact-failures-relevant).

## What was done

| Tool | Command | Infrastructure it reuses |
|---|---|---|
| API change impact | `teammap impact <endpoint path \| function \| Model> [METHOD]` | the teammap index, `link()` (endpoint, model, frontend call), `call_sites`, `file_imports`, `mirror_types`, `model_uses`, the episode reader |
| Test failure analysis | `teammap failures <file \| ->` | the index (frame → enclosing function), the workspace data area |
| Task-related code | `teammap relevant "<task>"` | symbols, endpoints and models in the index; `brief_sections`, `read_episodes` |
| Records | `teammap research show <id>`, `research list` | `<team>/graph/research/` |

- Code: [src/aiset/research.py](../src/aiset/research.py). teammap hands these subcommands off to it, the same way it does `arch`.
- Shared functions weren't copied. In teammap, the logic inside `callers_of` and `cmd_model` was split out into the `call_sites`, `model_uses`, `mirror_types` and `import_resolver` functions; the existing commands' output stayed the same.
- Agent templates were updated: engineer (all three), tester (`failures`), integration checker (`impact`), PM (`relevant`, `impact`). They all share the same rule: the short result first, then only the code or log lines needed. `~` lines and "gaps" are verified in the code. If a result is empty or incomplete, the agent carries on researching the usual way.
- Evaluation harness: [eval/research_eval.py](../eval/research_eval.py) and the sample workspace's tasks. The task file contains that workspace's file names, so it lives in the workspace itself, not in the aiset repo: `example-usage/.claude/team/eval/tasks.json`.
- Side fix: Git Bash (the agents' shell on Windows) was turning arguments like `/products` into `C:/Program Files/Git/products`. Because of this, `teammap endpoint /…` never matched on Windows. `teammap` now undoes that conversion.

## Verified behaviour

Automated tests: all 23 tests pass with `python -m unittest discover -s tests`. 17 of them are new (`tests/test_research.py`).

- **Parsing real output:** pytest 8.4's four traceback styles (long, short, native, `--tb=no`), Python 3.11 unittest, the Node 20 test runner (TAP) and JUnit XML were taken from real runs. The Jest and Vitest samples were written by hand from their formats because those tools weren't installed; those tests only exercise the parser.
- **Grouping identical failures:** In all five Python formats, the same five tests, the same messages and the same two-test `ValueError` group (`billing.py:6`, `parse_qty`) are found.
- **Frame order:** Python frames are printed outermost first, JavaScript frames innermost first. In both, the innermost frame where the error surfaced is picked correctly.
- **Root cause:** No group gets a root cause (`root_cause: null`). When the test runner itself shortens the message (`--tb=no`), this is reported as a gap.
- **Unrecognised output:** The result is "unrecognized". No guess is produced.
- **Log safety:** `$(touch …)`, backticks and `python -c` commands in the log are not run; the test confirms this with a marker file.
- **End-to-end workspace test:** On a FastAPI-style backend and a TS frontend with tsconfig aliases, the following were verified:
  - **Consumers:** An `http.get` to the same URL is found as an exact match. The literal in the API client with the same path shape and method, and the screen that calls it, are found as inferred. A POST in the same block of lines isn't wrongly attributed to the GET.
  - **Model and symbol:** The subclass, importing files and tests are found.
  - **Queries without a match:** A symbol that isn't found gives "not-found"; a query matching more than one endpoint gives "ambiguous".
  - **No index:** If no repo is configured, the result says "no repositories to index".
- **Cache:** Making the same call a second time returns it from the record. When a related file is changed without committing, the result is recomputed; the new caller also shows up in the result and `uncommitted ≥ 1` appears.
- **When the tool code changes:** The tool's own code is part of the fingerprint too. This was added after a stale result was seen being returned as "valid" during development.
- **Output limit:** `--max-chars` and `--limit` name the part that was cut; `research show` shows the remaining lines.
- **Repos:** After all the calls, the repos' `git status` output stays the same.

The comparison and measurements below were done on a real workspace: a FastAPI backend (`example-api`) and a Next.js frontend (`example-web`), 297 files in total. Project, repo, file and endpoint names were replaced with sample names; line numbers and counts are the measured values.

Manual comparison on the sample workspace (tool output against `git grep`):

| Query | Tool | Checked with grep |
|---|---|---|
| `GET /products/` consumers | `api-client.ts:202` and 6 places calling `api.products.list()` | 6 of 6 calls, no extras |
| `GET /products/{id}` | `api-client.ts:203` and 2 callers | 2 of 2 |
| `PATCH /products/{id}` | `api-client.ts:207` and `product-management.tsx:86` | same |
| `DELETE /products/{id}` | `api-client.ts:210`, no callers | `products.remove(` doesn't appear anywhere |
| Tests | none | `app/tests/test_product.py` is an empty file; "no tests" is correct |

## Measured results (size mode, not a real agent run)

Measured with scripted steps on the same state of the sample workspace. The baseline is today's way: the existing teammap query, then grep and reads. The treatment is the research command plus the read done to verify it. Values are characters, not tokens.

| Task | Steps (baseline → tool) | Reads | Output characters | Expected facts |
|---|---|---|---|---|
| PATCH consumers | 5 → 2 | 2 → 1 | 4,260 → 2,287 | 2/2 → 2/2 |
| GET list consumers | 5 → 2 | 2 → 1 | 5,599 → 2,827 | 4/4 → 4/4 |
| `ProductResponse` usage | 2 → 1 | 0 → 0 | 1,687 → 2,167 | 3/3 → 3/3 |
| Location of batch stock adjustment | 3 → 2 | 1 → 1 | 5,163 → 5,495 | 4/4 → 4/4 |
| Failing test triage | 1 → 1 | 1 → 0 | 3,932 → 2,112 | 5/5 → 5/5 |
| **Total** | **16 → 8** | **6 → 3** | **20,641 → 14,888** | same |

Index cost (sample workspace: 297 files): cold `teammap index --force` 1.2 s, warm 0.2–0.3 s. The index is 2.1 MB, the records about 0.14 MB. Time per research command is 0.3–0.4 s, most of it spent updating the index.

How to read this:
- **Mixed result:** In two of the five tasks, the tool output is longer.
  - In the `ProductResponse` task, the existing `teammap model` already gave a short answer. `impact` adds gaps, imports and the record line to it.
  - In the batch task, the baseline stayed targeted because the word to search for (`adjust`) was known in advance. An agent that didn't know the word would search more, but this wasn't measured.
- **The baseline's limit:** The baseline steps were written by hand. A real agent might take fewer or more steps.
- **Accuracy:** Accuracy was measured by whether the expected file and symbol names appear in the output. The correctness of the whole answer wasn't measured.

## Assumptions not yet verified

- **Token savings aren't proven.** No real agent run was done. Agent mode should be used to measure the savings:
  ```sh
  python eval/research_eval.py <example-usage>/.claude/team/eval/tasks.json --workspace <example-usage> --mode agent --confirm-cost --runs 3
  ```
  This mode records the input, output, cache-read and cache-write tokens Claude Code reports, plus tool calls, reads, number of turns, duration and cost. Before and after every run, it verifies the repos are in the same state. It wasn't run because it costs money.
- **Why it could go down:** Fewer turns and fewer reads should shrink the context re-sent on every turn. But this depends on the agent using the tool output correctly. The agent will still read code to verify `~` lines.
- **Why it could go up:** If the agent doesn't trust the result and greps anyway, the cost grows by the size of the tool output.
- **The cache contributes little:** The fingerprint computation already updates the index, so a record saves only a few hundred milliseconds over computing. Its real value is that the same question can be tracked under the same record id.

## Known limitations (this version)

- **Languages:** Python and TypeScript only. The sample workspace has no repos in other languages.
- **Matching by name:** Callers are matched by name. Other functions with the same name can get mixed in; calls made through dependency injection can be missed.
- **`relevant` only matches words:** A task description in Turkish doesn't match English code (the query "ürün partisi stok düzeltmesi", Turkish for "product batch stock adjustment", returned nothing and says so explicitly).
- **Weak mirror-type guesses:** The frontend mirror-type guess (inherited from teammap's `model` command) can give weak candidates. For example, the `Warehouse` type was listed for `ProductResponse` with 6 shared fields; the row is marked as inferred.
- **Specific formats only:** `failures` only recognises the listed formats. The Jest and Vitest samples weren't taken from a real run.
