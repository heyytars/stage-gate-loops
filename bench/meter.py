"""Metered agent: `python bench/meter.py "<prompt>"`.

Calls `claude -p --output-format json`, prints the answer, and appends the
token usage to $SGL_METER_LEDGER. Use it as AGENT_CMD in any example.
Needs the Claude Code CLI, logged in (`claude` then /login).
"""

import json
import os
import subprocess
import sys


def main() -> int:
    prompt = sys.argv[-1]
    model = os.environ.get("SGL_METER_MODEL", "haiku")
    r = subprocess.run(["claude", "-p", "--model", model, "--output-format", "json", prompt],
                       capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        print(r.stdout or r.stderr, file=sys.stderr)
        return 1
    if d.get("is_error") or r.returncode != 0:
        print(d.get("result", "agent error"), file=sys.stderr)
        return 1
    ledger = os.environ.get("SGL_METER_LEDGER")
    if ledger:
        with open(ledger, "a") as f:
            f.write(json.dumps(d.get("usage", {})) + "\n")
    print(d.get("result", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
