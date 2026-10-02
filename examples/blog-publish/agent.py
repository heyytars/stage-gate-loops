"""The 'agent' for the blog example.

Offline stub by default, so the demo is free and deterministic. The stub makes
the mistake real agents make (an em dash in the first draft), reads the gate's
feedback from SGL_FEEDBACK, and fixes it on the retry.

Real mode: set AGENT_CMD to any CLI that takes a prompt as its last argument
and prints the answer, e.g. AGENT_CMD="claude -p".
"""

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

OUT = Path("out")
TOPIC = "Why agent loops should verify at every step, not at the end"
FEEDBACK = os.environ.get("SGL_FEEDBACK", "")
ATTEMPT = int(os.environ.get("SGL_ATTEMPT", "1"))


def real(prompt: str) -> str:
    cmd = shlex.split(os.environ["AGENT_CMD"]) + [prompt]
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout.strip()


def research() -> None:
    if os.environ.get("AGENT_CMD"):
        text = real(
            f"Write a research brief as JSON only, no prose, for a blog post on: {TOPIC}. "
            'Keys: topic, audience, angle, sources (list of {title, url}, https only, at least 2). '
            + (f"Your last attempt failed this check, fix it:\n{FEEDBACK}" if FEEDBACK else "")
        )
        text = text.strip().removeprefix("```json").removesuffix("```").strip()
    else:
        text = json.dumps({
            "topic": TOPIC,
            "audience": "engineers running agents on a schedule",
            "angle": "end-of-run review wastes the run; gates catch it at the source",
            "sources": [
                {"title": "Toyota Production System", "url": "https://global.toyota/en/company/vision-and-philosophy/production-system/"},
                {"title": "Continuous Integration", "url": "https://martinfowler.com/articles/continuousIntegration.html"},
            ],
        }, indent=2)
    OUT.mkdir(exist_ok=True)
    (OUT / "brief.json").write_text(text)


DRAFT = """---
title: "Verify at every step"
description: "Why agent loops should stop at the first failed check."
date: 2026-10-02
---

Most agent loops check their work at the end{dash}after every stage has already run.
If stage two went wrong, stages three, four and five still burn time and tokens.
A stage gate moves the check to the transition. Each stage ends at a tool that
returns pass or fail. A schema validator, a test suite, a linter. Not a model's
opinion. When the gate fails, the line stops, the failure goes back to the agent
as feedback, and only that stage runs again. Nothing downstream is wasted, and
the log shows exactly which check broke and why. It's the same idea as the andon
cord on a factory line and the red build in CI: catch the defect where it starts.
"""


def draft() -> None:
    if os.environ.get("AGENT_CMD"):
        brief = (OUT / "brief.json").read_text()
        text = real(
            "Write a short blog post in markdown with YAML frontmatter (title, description, date). "
            f"80 to 400 words. Brief:\n{brief}\n"
            + (f"Your last draft failed this check, fix only that:\n{FEEDBACK}" if FEEDBACK else "")
        )
    else:
        fixed = "em dash" in FEEDBACK or "—" in FEEDBACK
        text = DRAFT.format(dash=", " if fixed else " — ")
    (OUT / "post.md").write_text(text)
    print(f"draft written (attempt {ATTEMPT})")


def publish() -> None:
    dest = OUT / "published"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(OUT / "post.md", dest / "post.md")
    print("published to out/published/post.md")


if __name__ == "__main__":
    {"research": research, "draft": draft, "publish": publish}[sys.argv[1]]()
