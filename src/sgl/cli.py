"""sgl command line."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .gates import main as gate_main
from .runner import PipelineError, load, run


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "gate":
        return gate_main(argv[1:])

    ap = argparse.ArgumentParser(prog="sgl", description="Stage gate loops: stop the line at the first failed gate.")
    ap.add_argument("--version", action="version", version=f"sgl {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run a pipeline")
    r.add_argument("pipeline")
    r.add_argument("--gates-only", action="store_true", help="skip stage commands, only check gates")
    r.add_argument("--resume", action="store_true", help="skip stages that passed in the last stopped run")
    r.add_argument("--from", dest="start_at", help="start at this stage")
    r.add_argument("--json", action="store_true", help="print the result as JSON")
    r.add_argument("--quiet", "-q", action="store_true")

    v = sub.add_parser("validate", help="check a pipeline file without running it")
    v.add_argument("pipeline")

    sub.add_parser("gate", help="run a built-in gate: sgl gate --help")

    h = sub.add_parser("hook", help="agent runtime hooks")
    h.add_argument("runtime", choices=["claude-code"])
    h.add_argument("pipeline")

    a = ap.parse_args(argv)
    if a.cmd == "hook":
        from .adapters import claude_code_stop_hook
        return claude_code_stop_hook(a.pipeline)
    try:
        pl = load(a.pipeline)
    except PipelineError as e:
        print(f"sgl: {e}", file=sys.stderr)
        return 2

    if a.cmd == "validate":
        n = sum(len(s.gates) for s in pl.stages)
        print(f"ok: {pl.name}, {len(pl.stages)} stages, {n} gates")
        return 0

    res = run(pl, gates_only=a.gates_only, resume=a.resume, start_at=a.start_at,
              quiet=a.quiet or a.json)
    if a.json:
        print(json.dumps(res, indent=2))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
