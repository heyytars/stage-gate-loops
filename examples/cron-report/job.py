"""A tiny scheduled job. Offline: 'fetch' reads a local fixture so the demo
needs no network. Swap fetch() for a real API call in your own job.

Set BREAK=1 to simulate an upstream API returning junk, and watch the
data-schema gate stop the line before a broken report is ever written.
"""

import json
import os
import shutil
import sys
from pathlib import Path

OUT = Path("out")


def fetch() -> None:
    OUT.mkdir(exist_ok=True)
    if os.environ.get("BREAK"):
        data = {"date": "2026-10-02", "metrics": [{"name": "signups", "value": None}]}
    else:
        data = json.loads(Path("fixture.json").read_text())
    (OUT / "data.json").write_text(json.dumps(data, indent=2))


def report() -> None:
    data = json.loads((OUT / "data.json").read_text())
    lines = [f"# Daily report, {data['date']}", ""]
    for m in data["metrics"]:
        lines.append(f"- {m['name']}: {m['value']}")
    (OUT / "report.md").write_text("\n".join(lines) + "\n")


def deliver() -> None:
    # Real job: send email / post to Slack. Here: drop it in an outbox.
    box = OUT / "outbox"
    box.mkdir(exist_ok=True)
    shutil.copy(OUT / "report.md", box / "report.md")
    print("delivered to out/outbox/report.md")


if __name__ == "__main__":
    {"fetch": fetch, "report": report, "deliver": deliver}[sys.argv[1]]()
