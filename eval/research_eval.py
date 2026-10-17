#!/usr/bin/env python3
"""Compare the current way of researching (greps, reads, teammap queries) with the research tools, on the same tasks
and the same repository state.

  python eval/research_eval.py <ws>/.claude/team/eval/tasks.json --workspace <ws>                 # size mode (default)
  python eval/research_eval.py <ws>/.claude/team/eval/tasks.json --workspace <ws> --mode agent --confirm-cost [--runs 3]

A task file names one workspace's files, so it lives with that workspace (<ws>/.claude/team/eval/), not here.

size mode runs each task's scripted steps twice: `baseline` (what an agent does today) and `treatment` (the research
tools, plus the reads an agent would still do to check them). It records steps (tool calls), output size in
characters, wall time and whether the expected facts appear in the output. Characters are not tokens, and a scripted
baseline is not an agent: this mode compares output sizes only.

agent mode runs `claude -p` on each task's question, once told not to use the research commands and once told to use
them, and records what Claude Code reports: input, output, cache-read and cache-write tokens, tool calls by name,
reads, turns, duration and cost, and whether the final answer contains the expected facts. It needs --confirm-cost
(it spends tokens). Before and after every run it checks that the repositories are in the same state (HEAD, status
and diff); a run that changed them is marked invalid and the evaluation stops.

Both modes also measure the index: a cold `teammap index --force`, a warm `teammap index`, and the size on disk of the
index and of the stored research results.

Steps in a task file: {"cmd": "teammap impact /x GET"} runs a command in the workspace (`teammap` is this checkout's
teammap; no shell, so no pipes), {"read": "repo/path", "lines": [a, b]} stands for a Read tool call. Only put
read-only commands in a task file: they are run as written.
"""
import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAMMAP = os.path.join(ROOT, "src", "aiset", "teammap.py")
NO_TOOLS = ("Answer from the code. Do not use the teammap commands impact, failures, relevant or research; "
            "the other teammap commands, grep and reads are fine.")
WITH_TOOLS = ("Answer from the code. Start with the teammap research commands (impact, failures, relevant) where they "
              "fit, then read only what you need to confirm.")


def env_for(ws):
    env = dict(os.environ, AISET_WORKSPACE=ws, PYTHONIOENCODING="utf-8")
    env.pop("MSYSTEM", None)  # we pass arguments directly; nothing to un-mangle
    return env


def run_step(step, ws):
    """One step's output and seconds. {AISET} in a step is this checkout (for the bundled test-output fixtures)."""
    root = ROOT.replace("\\", "/")  # shlex reads backslashes as escapes
    step = {k: v.replace("{AISET}", root) if isinstance(v, str) else v for k, v in step.items()}
    t0 = time.time()
    if "read" in step:
        path = os.path.join(ws, step["read"])
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
        a, b = step.get("lines") or [1, len(lines)]
        out = "\n".join(f"{n:>6}\t{lines[n - 1]}" for n in range(a, min(b, len(lines)) + 1))  # like Read's cat -n
    else:
        args = shlex.split(step["cmd"], posix=True)
        if args[0] == "teammap":
            args = [sys.executable, TEAMMAP] + args[1:]
        p = subprocess.run(args, cwd=os.path.join(ws, step.get("cwd", "")), env=env_for(ws), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=600)
        out = p.stdout + p.stderr
    return out, time.time() - t0


def score(text, expect):
    found = [e for e in expect if e in text]
    return {"found": found, "missing": [e for e in expect if e not in text], "recall": round(len(found) / len(expect), 2) if expect else None}


def size_mode(tasks, ws):
    rows = []
    for t in tasks:
        row = {"id": t["id"]}
        for variant in ("baseline", "treatment"):
            outs, secs = [], 0.0
            for step in t[variant]:
                out, s = run_step(step, ws)
                outs.append(out)
                secs += s
            text = "\n".join(outs)
            row[variant] = {"steps": len(t[variant]), "reads": sum(1 for s in t[variant] if "read" in s),
                            "chars": len(text), "seconds": round(secs, 2), **score(text, t.get("expect", []))}
        rows.append(row)
    return rows


def repo_state(ws, repos):
    """HEAD, status and the diff of every repo: equal states mean the same starting point for a run."""
    h = hashlib.sha256()
    for r in repos:
        for args in (["rev-parse", "HEAD"], ["status", "--porcelain", "--untracked-files=all"], ["diff"]):
            h.update(subprocess.run(["git", "-C", os.path.join(ws, r), *args], capture_output=True).stdout)
    return h.hexdigest()


def agent_run(question, system, ws, agent):
    cmd = ["claude", "-p", question, "--output-format", "stream-json", "--verbose", "--append-system-prompt", system]
    if agent:
        cmd += ["--agent", agent]
    t0 = time.time()
    p = subprocess.run(cmd, cwd=ws, env=env_for(ws), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600)
    tools, result = {}, {}
    for line in p.stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "assistant":
            for b in (ev.get("message") or {}).get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    name = b.get("name")
                    if name == "Bash" and "teammap" in json.dumps(b.get("input", {})):
                        name = "Bash(teammap " + next((w for w in ("impact", "failures", "relevant", "research", "arch", "endpoint",
                                                                   "symbol", "model", "file", "search", "code") if w in json.dumps(b.get("input", {}))), "?") + ")"
                    tools[name] = tools.get(name, 0) + 1
        elif ev.get("type") == "result":
            result = ev
    u = result.get("usage") or {}
    return {"ok": p.returncode == 0 and bool(result), "seconds": round(time.time() - t0, 1),
            "duration_ms": result.get("duration_ms"), "turns": result.get("num_turns"), "cost_usd": result.get("total_cost_usd"),
            "input_tokens": u.get("input_tokens"), "output_tokens": u.get("output_tokens"),
            "cache_read_tokens": u.get("cache_read_input_tokens"), "cache_write_tokens": u.get("cache_creation_input_tokens"),
            "tool_calls": sum(tools.values()), "tools": tools, "reads": tools.get("Read", 0), "answer": result.get("result") or "",
            "stderr": p.stderr[-2000:] if p.returncode else ""}


def agent_mode(tasks, ws, repos, runs, agent):
    start = repo_state(ws, repos)
    rows = []
    for t in tasks:
        for variant, system in (("baseline", NO_TOOLS), ("treatment", WITH_TOOLS)):
            for n in range(runs):
                if repo_state(ws, repos) != start:
                    raise SystemExit("the repositories changed since the evaluation started; restore them and run again")
                r = agent_run(t["question"], system, ws, t.get("agent", agent))
                r.update(score(r["answer"], t.get("expect", [])))
                r["valid"] = repo_state(ws, repos) == start
                rows.append({"id": t["id"], "variant": variant, "run": n + 1, **r})
                if not r["valid"]:
                    rows[-1]["note"] = "the agent changed the repositories; this run doesn't count"
                    return rows
    return rows


def index_cost(ws):
    def dir_size(p):
        return sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(p) for f in fs) if os.path.isdir(p) else 0
    graph = os.path.join(ws, ".claude", "team", "graph")
    out = {}
    for label, args in (("cold_index_seconds", ["index", "--force"]), ("warm_index_seconds", ["index"])):
        t0 = time.time()
        subprocess.run([sys.executable, TEAMMAP, *args], cwd=ws, env=env_for(ws), capture_output=True)
        out[label] = round(time.time() - t0, 2)
    out["index_bytes"] = dir_size(os.path.join(graph, "index"))
    out["research_store_bytes"] = dir_size(os.path.join(graph, "research"))
    return out


def table(rows, mode):
    if mode == "size":
        lines = ["| task | variant | steps | reads | output chars | seconds | expected found |", "|---|---|---|---|---|---|---|"]
        for r in rows:
            for v in ("baseline", "treatment"):
                x = r[v]
                lines.append(f"| {r['id']} | {v} | {x['steps']} | {x['reads']} | {x['chars']:,} | {x['seconds']} | "
                             f"{len(x['found'])}/{len(x['found']) + len(x['missing'])}{' (missing: ' + ', '.join(x['missing']) + ')' if x['missing'] else ''} |")
        tb = sum(r["baseline"]["chars"] for r in rows)
        tt = sum(r["treatment"]["chars"] for r in rows)
        lines.append(f"\nTotal output: baseline {tb:,} characters, treatment {tt:,} characters. "
                     "Characters, not tokens; scripted steps, not agent runs.")
        return "\n".join(lines)
    lines = ["| task | variant | run | valid | input | output | cache read | cache write | tool calls | reads | turns | s | cost $ | expected |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['id']} | {r['variant']} | {r['run']} | {r['valid']} | {r['input_tokens']} | {r['output_tokens']} | "
                     f"{r['cache_read_tokens']} | {r['cache_write_tokens']} | {r['tool_calls']} | {r['reads']} | {r['turns']} | "
                     f"{r['seconds']} | {r['cost_usd']} | {r['recall']} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tasks")
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--mode", choices=("size", "agent"), default="size")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--agent", default=None, help="agent for agent mode (default: none, a plain session)")
    ap.add_argument("--confirm-cost", action="store_true")
    ap.add_argument("--out", default=None, help="write the results as JSON here")
    ap.add_argument("--skip-index", action="store_true")
    a = ap.parse_args()
    with open(a.tasks, encoding="utf-8") as f:
        spec = json.load(f)
    ws = os.path.abspath(a.workspace)
    repos = spec.get("repos") or []
    result = {"mode": a.mode, "workspace": ws, "tasks_file": os.path.abspath(a.tasks), "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "repo_state": repo_state(ws, repos) if repos else None}
    if not a.skip_index:
        result["index"] = index_cost(ws)
    if a.mode == "size":
        result["rows"] = size_mode(spec["tasks"], ws)
    else:
        if not a.confirm_cost:
            raise SystemExit("agent mode runs Claude Code on every task twice per run and spends tokens; add --confirm-cost")
        result["rows"] = agent_mode(spec["tasks"], ws, repos, a.runs, a.agent)
    print(table(result["rows"], a.mode))
    if result.get("index"):
        print("\nIndex: " + ", ".join(f"{k} {v:,}" if isinstance(v, int) else f"{k} {v}" for k, v in result["index"].items()))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=1)
        print(f"\nresults: {a.out}")


if __name__ == "__main__":
    main()
