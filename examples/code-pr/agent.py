"""The 'agent' for the code example.

Stub mode: the first attempt ships a slugify that forgets accents (a classic
miss). The test gate fails, the failing test output arrives in SGL_FEEDBACK,
and the second attempt handles it.

Real mode: AGENT_CMD="claude -p". The prompt includes the tests and, on retry,
the exact failure.
"""

import os
import re
import shlex
import subprocess
from pathlib import Path

TARGET = Path("src/slug.py")
FEEDBACK = os.environ.get("SGL_FEEDBACK", "")

NAIVE = '''import re


def slugify(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return text.strip("-")
'''

FIXED = '''import re
import unicodedata


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return text.strip("-")
'''


def main() -> None:
    TARGET.parent.mkdir(exist_ok=True)
    if os.environ.get("AGENT_CMD"):
        tests = Path("tests/test_slug.py").read_text()
        prompt = (
            "Write src/slug.py: a Python module with slugify(text: str) -> str that passes "
            f"these tests. Reply with the code only, no fences.\n\n{tests}\n"
            + (f"\nYour last version failed:\n{FEEDBACK}\nFix it." if FEEDBACK else "")
        )
        out = subprocess.run(shlex.split(os.environ["AGENT_CMD"]) + [prompt],
                             check=True, capture_output=True, text=True).stdout
        code = re.sub(r"^```\w*\n|```\s*$", "", out.strip(), flags=re.M)
    else:
        code = FIXED if "test_accents" in FEEDBACK else NAIVE
    TARGET.write_text(code)


if __name__ == "__main__":
    main()
