"""Benchmark: stage gates vs a single check at the end.

Two modes.

  sim   Monte Carlo of the mechanism. Seeded, offline, free. It does NOT
        measure an LLM. It shows what the control flow alone does to cost
        when stages fail at a given rate. Every assumption is printed.

  real  Runs a real pipeline both ways with a real agent and meters tokens.
          A) gates:  sgl run as written (retry only the failed stage)
          B) end:    run every stage command, then every gate once at the
                     end; on any fail, rerun the whole pipeline
        Token use comes from bench/meter.py (wraps `claude -p --output-format json`).

  python bench/bench.py sim
  python bench/bench.py real examples/blog-publish/pipeline.yaml --runs 5
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import statistics as st
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sgl.runner import Pipeline, Stage, load, run  # noqa: E402


# ----------------------------------------------------------------------------- sim
def sim_gates(costs, fails, rng, max_attempts):
    spent = 0
    for c, p in zip(costs, fails):
        for _ in range(max_attempts):
            spent += c
            if rng.random() >= p:
                break
        else:
            return spent, False
    return spent, True


def sim_end(costs, fails, rng, max_attempts):
    spent = 0
    for _ in range(max_attempts):
        ok = True
        for c, p in zip(costs, fails):
            spent += c
            if rng.random() < p:
                ok = False  # the defect is there, but nobody looks until the end
        if ok:
            return spent, True
    return spent, False


def cmd_sim(a) -> int:
    costs = [int(x) for x in a.costs.split(",")]
    fails = [float(x) for x in a.fail.split(",")]
    if len(fails) == 1:
        fails = fails * len(costs)
    if len(fails) != len(costs):
        print("--fail needs one value or one per stage")
        return 2
    out = {}
    for name, fn in (("end-of-run check", sim_end), ("stage gates", sim_gates)):
        rng = random.Random(a.seed)
        res = [fn(costs, fails, rng, a.attempts) for _ in range(a.trials)]
        spent = [s for s, _ in res]
        out[name] = {
            "mean_tokens": round(st.mean(spent)),
            "p90_tokens": sorted(spent)[int(0.9 * len(spent)) - 1],
            "success_rate": round(sum(ok for _, ok in res) / len(res), 4),
        }
    base = out["end-of-run check"]["mean_tokens"]
    gated = out["stage gates"]["mean_tokens"]
    print("SIMULATION (mechanism only, not a model measurement)")
    print(f"  stages: {len(costs)}  token cost per stage run: {costs}")
    print(f"  per-attempt failure rate per stage: {fails}")
    print(f"  max attempts: {a.attempts}  trials: {a.trials}  seed: {a.seed}")
    print("  assumes every failure is caught by a deterministic gate (true by construction for gateable defects)")
    print()
    print(f"  {'strategy':<18}{'mean tokens':>12}{'p90 tokens':>12}{'success':>10}")
    for k, v in out.items():
        print(f"  {k:<18}{v['mean_tokens']:>12}{v['p90_tokens']:>12}{v['success_rate']:>10.1%}")
    print()
    print(f"  stage gates use {gated / base:.0%} of the tokens of an end-of-run check")
    if a.json:
        Path(a.json).write_text(json.dumps({"params": vars(a), "results": out}, indent=2, default=str))
    return 0


# ----------------------------------------------------------------------------- real
def _ledger_tokens(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for line in path.read_text().splitlines():
        u = json.loads(line)
        total += u.get("input_tokens", 0) + u.get("output_tokens", 0) \
            + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
    return total


def _fresh_copy(src_dir: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="sgl-bench-"))
    dst = tmp / src_dir.name
    shutil.copytree(src_dir, dst, ignore=shutil.ignore_patterns("out", ".sgl", "__pycache__"))
    return dst


def run_gated(pl_path: Path, env: dict) -> dict:
    pl = load(str(pl_path))
    pl.env.update(env)
    return run(pl, quiet=True)


def run_end(pl_path: Path, env: dict, max_attempts: int) -> dict:
    """Same stages and gates, but all checks deferred to the end. A failure
    reruns the whole pipeline, feeding the gate output back as feedback."""
    pl = load(str(pl_path))
    pl.env.update(env)
    work = Pipeline(name=pl.name + "-work", workdir=pl.workdir, env=pl.env,
                    stages=[Stage(name=s.name, run=s.run, gates=[], retries=0,
                                  timeout=s.timeout) for s in pl.stages if s.run])
    gates = [g for s in pl.stages for g in s.gates]
    check = Pipeline(name=pl.name + "-check", workdir=pl.workdir, env=pl.env,
                     stages=[Stage(name="final-review", run=None, gates=gates)])
    feedback = ""
    for attempt in range(1, max_attempts + 1):
        r = run(work, quiet=True, initial_feedback=feedback)
        if r["ok"]:
            r = run(check, quiet=True)
        if r["ok"]:
            return {"ok": True, "attempts": attempt}
        feedback = r["feedback"]
    return {"ok": False, "attempts": max_attempts}


def cmd_real(a) -> int:
    pl_path = Path(a.pipeline).resolve()
    meter = ROOT / "bench" / "meter.py"
    # --agent-cmd stub runs the offline stub agents: checks the harness, 0 tokens
    agent = "" if a.agent_cmd == "stub" else (a.agent_cmd or f"{sys.executable} {meter}")
    rows = {"stage gates": [], "end-of-run check": []}
    for i in range(a.runs):
        for name in rows:
            d = _fresh_copy(pl_path.parent)
            ledger = d / ".sgl" / "tokens.jsonl"
            ledger.parent.mkdir(parents=True, exist_ok=True)
            env = {"AGENT_CMD": agent, "SGL_METER_LEDGER": str(ledger),
                   "SGL_METER_MODEL": a.model}
            os.environ.update(env)
            p = d / pl_path.name
            res = run_gated(p, env) if name == "stage gates" else run_end(p, env, a.attempts)
            rows[name].append({"ok": res["ok"], "tokens": _ledger_tokens(ledger)})
            print(f"  run {i + 1} {name:<18} ok={res['ok']}  tokens={rows[name][-1]['tokens']}")
            shutil.rmtree(d.parent, ignore_errors=True)
    print(f"\nREAL RUN: {pl_path.parent.name}, model={a.model}, runs={a.runs}")
    print(f"  {'strategy':<18}{'mean tokens':>12}{'success':>10}")
    for k, v in rows.items():
        print(f"  {k:<18}{round(st.mean(r['tokens'] for r in v)):>12}"
              f"{sum(r['ok'] for r in v) / len(v):>10.0%}")
    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    s = sub.add_parser("sim")
    s.add_argument("--costs", default="3000,3000,3000,3000", help="tokens per stage run")
    s.add_argument("--fail", default="0.25", help="per-attempt failure rate, one value or one per stage")
    s.add_argument("--attempts", type=int, default=3)
    s.add_argument("--trials", type=int, default=20000)
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--json")
    r = sub.add_parser("real")
    r.add_argument("pipeline")
    r.add_argument("--runs", type=int, default=5)
    r.add_argument("--attempts", type=int, default=3)
    r.add_argument("--model", default="haiku")
    r.add_argument("--agent-cmd", help="override the metered agent command")
    r.add_argument("--json")
    a = ap.parse_args()
    return cmd_sim(a) if a.mode == "sim" else cmd_real(a)


if __name__ == "__main__":
    sys.exit(main())
