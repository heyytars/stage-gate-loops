"""Adapters that plug sgl into agent runtimes."""

from __future__ import annotations

import json
import sys

from .runner import PipelineError, load, run


def claude_code_stop_hook(pipeline: str) -> int:
    """Claude Code `Stop` hook.

    When Claude says it's done, run the pipeline's gates against the working
    tree. If a gate fails, block the stop and hand Claude the exact failure,
    so it keeps working on that one thing. Claude Code caps consecutive
    continuations (8 by default), so a gate that can never pass cannot trap
    the session.
    """
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        event = {}
    try:
        pl = load(pipeline)
    except PipelineError as e:
        print(f"sgl hook: {e}", file=sys.stderr)
        return 0  # never wedge the session on a config error
    res = run(pl, gates_only=True, quiet=True)
    if res["ok"]:
        return 0
    reason = (f"Stage gate '{res['stopped_at']}' failed. Fix this before you finish:\n"
              f"{res['feedback'][-3000:]}")
    if event.get("stop_hook_active"):
        reason += "\n(This is a repeat failure. Change your approach.)"
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0
