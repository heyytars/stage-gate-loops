"""Stage gate runner.

A pipeline is a list of stages. Each stage runs a command, then every gate
attached to it. A gate is any command: exit code 0 means pass, anything else
means fail. On fail the line stops. The stage can be retried (with the gate
output handed back as feedback) up to `retries` times, and after that the run
ends at that exact breakpoint.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .redact import redact, secret_values

FEEDBACK_LIMIT = 4000  # chars of gate output handed back on retry


@dataclass
class Gate:
    name: str
    run: str
    timeout: int = 300


@dataclass
class Stage:
    name: str
    run: Optional[str]
    gates: List[Gate] = field(default_factory=list)
    retries: int = 0
    timeout: int = 1800


@dataclass
class Pipeline:
    name: str
    stages: List[Stage]
    workdir: Path
    env: Dict[str, str] = field(default_factory=dict)


class PipelineError(ValueError):
    pass


def load(path: str) -> Pipeline:
    p = Path(path).resolve()
    if not p.exists():
        raise PipelineError(f"pipeline file not found: {path}")
    data = yaml.safe_load(p.read_text()) or {}
    if not isinstance(data, dict) or not data.get("stages"):
        raise PipelineError("pipeline needs a non-empty 'stages' list")

    stages: List[Stage] = []
    seen = set()
    for i, s in enumerate(data["stages"]):
        if not isinstance(s, dict) or not s.get("name"):
            raise PipelineError(f"stage #{i + 1} needs a 'name'")
        if not isinstance(s["name"], str) or CONTROL.search(s["name"]):
            raise PipelineError(f"stage #{i + 1}: name must be text on one line")
        if s["name"] in seen:
            raise PipelineError(f"duplicate stage name: {s['name']}")
        seen.add(s["name"])
        gates = []
        for j, g in enumerate(s.get("gates") or []):
            if isinstance(g, str):
                g = {"name": f"gate-{j + 1}", "run": g}
            if not g.get("run"):
                raise PipelineError(f"gate #{j + 1} in stage '{s['name']}' needs 'run'")
            gates.append(Gate(name=g.get("name", f"gate-{j + 1}"), run=g["run"],
                              timeout=int(g.get("timeout", 300))))
        if not s.get("run") and not gates:
            raise PipelineError(f"stage '{s['name']}' has neither 'run' nor 'gates'")
        stages.append(Stage(name=s["name"], run=s.get("run"), gates=gates,
                            retries=int(s.get("retries", 0)),
                            timeout=int(s.get("timeout", 1800))))

    workdir = (p.parent / data.get("workdir", ".")).resolve()
    env = {str(k): str(v) for k, v in (data.get("env") or {}).items()}
    name = str(data.get("name", p.stem))
    # The name becomes a file name under .sgl/. Refuse anything that could
    # climb out of it ("../../x") or hide (".x").
    if not SAFE_NAME.fullmatch(name):
        raise PipelineError(f"pipeline name must match {SAFE_NAME.pattern}: {name!r}")
    return Pipeline(name=name, stages=stages, workdir=workdir, env=env)


SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _sh(cmd: str, cwd: Path, env: Dict[str, str], timeout: int) -> subprocess.CompletedProcess:
    # shell=True is deliberate: commands come from the pipeline file the user
    # wrote and trusts, exactly like a Makefile or a CI config. sgl never
    # interpolates untrusted input into them; feedback travels via env vars.
    #
    # Each command gets its own process group, so a timeout kills the whole
    # tree, not just the shell (otherwise `sleep 600 &` outlives the gate).
    # All output is redacted HERE, the single choke point, before it can reach
    # the console, the log, $SGL_FEEDBACK or a CI job summary.
    #
    # bandit B602 is suppressed below, not ignored: shell is the product. A gate
    # IS a shell command, exactly like a CI `run:` step or a Makefile recipe.
    # sgl never builds a command from untrusted input; commands come from the
    # pipeline file, and values reach the command as environment variables, never
    # as interpolated text. Keep the nosec on one line and add no prose to it:
    # bandit parses the comment text after the id as more test ids and warns.
    proc = subprocess.Popen(  # nosec B602
        cmd, shell=True, cwd=str(cwd), env=env, start_new_session=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, errors="replace")
    try:
        out, _ = proc.communicate(timeout=timeout)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        out, _ = proc.communicate()
        out = (out or "") + f"\n[sgl] timed out after {timeout}s"
        code = 124
    return subprocess.CompletedProcess(cmd, code, redact(out or "", secret_values(env)), None)


def _kill_tree(proc: subprocess.Popen) -> None:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            return
        try:
            proc.wait(timeout=2)
            return
        except subprocess.TimeoutExpired:
            continue


class Log:
    """Append-only JSON lines log, one file per run."""

    def __init__(self, root: Path, pipeline: str, quiet: bool = False):
        _private_dir(root)
        stamp = time.strftime("%Y%m%dT%H%M%S")
        self.path = root / f"{pipeline}-{stamp}-{os.getpid()}.jsonl"
        self.quiet = quiet

    def event(self, kind: str, **data: Any) -> None:
        rec = {"ts": round(time.time(), 3), "event": kind, **data}
        # owner-only (0600): logs hold command output, even if redacted
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a") as f:
            f.write(json.dumps(rec) + "\n")

    def say(self, msg: str) -> None:
        if not self.quiet:
            print(msg, flush=True)


def _private_dir(path: Path) -> None:
    """Create a directory readable by the owner only (0700), and its .sgl parent."""
    path.mkdir(parents=True, exist_ok=True)
    targets = [path] + ([path.parent] if path.parent.name == ".sgl" else [])
    for p in targets:
        try:
            os.chmod(p, 0o700)
        except OSError:
            pass


def _state_path(pl: Pipeline) -> Path:
    return pl.workdir / ".sgl" / f"{pl.name}.state.json"


def run(pl: Pipeline, gates_only: bool = False, resume: bool = False,
        start_at: Optional[str] = None, quiet: bool = False,
        initial_feedback: str = "") -> Dict[str, Any]:
    """Run the pipeline. Returns a result dict; result['ok'] is the verdict."""
    log = Log(pl.workdir / ".sgl" / "runs", pl.name, quiet=quiet)
    state_file = _state_path(pl)
    passed: List[str] = []
    if resume and state_file.exists():
        try:
            saved = json.loads(state_file.read_text()).get("passed", [])
        except (ValueError, AttributeError):
            saved = []
        # only trust names that are really stages of THIS pipeline
        passed = [n for n in saved if isinstance(n, str) and n in {s.name for s in pl.stages}]

    names = [s.name for s in pl.stages]
    if start_at and start_at not in names:
        raise PipelineError(f"unknown stage: {start_at}")
    skipping = bool(start_at)

    log.event("run_start", pipeline=pl.name, gates_only=gates_only)
    log.say(f"sgl ▸ {pl.name}  ({len(pl.stages)} stages)")
    t0 = time.time()

    for idx, st in enumerate(pl.stages, 1):
        if skipping and st.name != start_at:
            log.say(f"  [{idx}] {st.name}: skipped (--from)")
            continue
        skipping = False
        if st.name in passed:
            log.say(f"  [{idx}] {st.name}: already passed, skipped (--resume)")
            continue

        feedback = initial_feedback
        for attempt in range(1, st.retries + 2):
            env = {**os.environ, **pl.env, "SGL_STAGE": st.name,
                   "SGL_ATTEMPT": str(attempt), "SGL_FEEDBACK": feedback}

            failed = None
            if st.run and not gates_only:
                r = _sh(st.run, pl.workdir, env, st.timeout)
                log.event("stage", stage=st.name, attempt=attempt, code=r.returncode,
                          output=r.stdout[-FEEDBACK_LIMIT:])
                if r.returncode != 0:
                    failed = "(stage command)"
                    feedback = f"stage command failed (exit {r.returncode}):\n{r.stdout[-FEEDBACK_LIMIT:]}"

            for g in (st.gates if failed is None else []):
                r = _sh(g.run, pl.workdir, env, g.timeout)
                ok = r.returncode == 0
                log.event("gate", stage=st.name, gate=g.name, attempt=attempt,
                          passed=ok, code=r.returncode, output=r.stdout[-FEEDBACK_LIMIT:])
                if not ok:
                    failed = g.name
                    feedback = f"gate '{g.name}' failed (exit {r.returncode}):\n{r.stdout[-FEEDBACK_LIMIT:]}"
                    break

            if failed is None:
                tag = f" (attempt {attempt})" if attempt > 1 else ""
                log.say(f"  [{idx}] {st.name}: PASS{tag}  gates: {', '.join(g.name for g in st.gates) or 'none'}")
                passed.append(st.name)
                break

            more = attempt <= st.retries
            log.say(f"  [{idx}] {st.name}: FAIL at gate '{failed}'" + ("  → retrying with feedback" if more else ""))
            for line in feedback.strip().splitlines()[1:6]:
                log.say(f"        {line}")
        else:
            # every attempt failed: stop the line
            _private_dir(state_file.parent)
            state_file.write_text(json.dumps({"passed": passed, "stopped_at": st.name}))
            result = {"ok": False, "stopped_at": st.name, "passed": passed,
                      "feedback": feedback, "log": str(log.path),
                      "seconds": round(time.time() - t0, 2)}
            log.event("run_end", **{k: v for k, v in result.items() if k != "log"})
            log.say(f"sgl ▸ STOPPED at '{st.name}'. Fix it, then: sgl run <pipeline> --resume")
            log.say(f"      log: {log.path}")
            return result

    if state_file.exists():
        state_file.unlink()
    result = {"ok": True, "stopped_at": None, "passed": passed, "feedback": "",
              "log": str(log.path), "seconds": round(time.time() - t0, 2)}
    log.event("run_end", **{k: v for k, v in result.items() if k != "log"})
    log.say(f"sgl ▸ ALL GATES PASSED ({result['seconds']}s)")
    return result


def main_exit(result: Dict[str, Any]) -> None:
    sys.exit(0 if result["ok"] else 1)
