"""Built-in gates. Each one is a plain check that exits 0 (pass) or 1 (fail).

Call them from a pipeline as `sgl gate <name> ...`. They have no third-party
dependencies, so a gate never breaks because a package moved.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List

GATES: Dict[str, Callable[[List[str]], int]] = {}


def gate(name: str):
    def wrap(fn):
        GATES[name] = fn
        return fn
    return wrap


def _fail(msg: str) -> int:
    print(f"FAIL: {msg}")
    return 1


def _ok(msg: str) -> int:
    print(f"PASS: {msg}")
    return 0


# --------------------------------------------------------------------------- exists
@gate("exists")
def exists(argv: List[str]) -> int:
    """Files exist and are not near-empty."""
    ap = argparse.ArgumentParser(prog="sgl gate exists")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--min-bytes", type=int, default=1)
    a = ap.parse_args(argv)
    bad = []
    for p in a.paths:
        f = Path(p)
        if not f.is_file():
            bad.append(f"{p}: missing")
        elif f.stat().st_size < a.min_bytes:
            bad.append(f"{p}: {f.stat().st_size} bytes < {a.min_bytes}")
    if bad:
        return _fail("; ".join(bad))
    return _ok(f"{len(a.paths)} file(s) present")


# --------------------------------------------------------------------------- no-pattern
@gate("no-pattern")
def no_pattern(argv: List[str]) -> int:
    """Fail if a regex matches anywhere in the files (em dashes, TODOs, banned words)."""
    ap = argparse.ArgumentParser(prog="sgl gate no-pattern")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--pattern", "-p", action="append", required=True)
    ap.add_argument("--ignore-case", "-i", action="store_true")
    a = ap.parse_args(argv)
    flags = re.IGNORECASE if a.ignore_case else 0
    pats = [re.compile(p, flags) for p in a.pattern]
    hits = []
    for p in a.paths:
        try:
            lines = Path(p).read_text(errors="replace").splitlines()
        except FileNotFoundError:
            return _fail(f"{p}: missing")
        for n, line in enumerate(lines, 1):
            for pat in pats:
                if pat.search(line):
                    hits.append(f"{p}:{n}: /{pat.pattern}/ in: {line.strip()[:120]}")
    if hits:
        print("\n".join(hits[:20]))
        return _fail(f"{len(hits)} banned match(es)")
    return _ok("no banned patterns")


# --------------------------------------------------------------------------- words
@gate("words")
def words(argv: List[str]) -> int:
    """Word count within bounds (frontmatter excluded)."""
    ap = argparse.ArgumentParser(prog="sgl gate words")
    ap.add_argument("path")
    ap.add_argument("--min", type=int, default=0)
    ap.add_argument("--max", type=int, default=10 ** 9)
    a = ap.parse_args(argv)
    text = Path(a.path).read_text(errors="replace")
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    n = len(text.split())
    if not a.min <= n <= a.max:
        return _fail(f"{n} words, expected {a.min}-{a.max}")
    return _ok(f"{n} words")


# --------------------------------------------------------------------------- frontmatter
@gate("frontmatter")
def frontmatter(argv: List[str]) -> int:
    """Markdown has YAML frontmatter with the required, non-empty keys."""
    ap = argparse.ArgumentParser(prog="sgl gate frontmatter")
    ap.add_argument("path")
    ap.add_argument("--require", required=True, help="comma-separated keys")
    a = ap.parse_args(argv)
    m = re.match(r"\A---\n(.*?)\n---\n", Path(a.path).read_text(errors="replace"), re.S)
    if not m:
        return _fail("no frontmatter block")
    import yaml
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        return _fail(f"frontmatter is not valid YAML: {e}")
    missing = [k for k in a.require.split(",") if k.strip() and not meta.get(k.strip())]
    if missing:
        return _fail(f"missing or empty: {', '.join(missing)}")
    return _ok("frontmatter complete")


# --------------------------------------------------------------------------- schema
_TYPES = {"object": dict, "array": list, "string": str, "integer": int,
          "number": (int, float), "boolean": bool, "null": type(None)}


def _check(v: Any, s: Dict[str, Any], path: str, errs: List[str]) -> None:
    t = s.get("type")
    if t:
        ok = isinstance(v, _TYPES[t]) and not (t in ("integer", "number") and isinstance(v, bool))
        if not ok:
            errs.append(f"{path}: expected {t}, got {type(v).__name__}")
            return
    if "enum" in s and v not in s["enum"]:
        errs.append(f"{path}: {v!r} not in {s['enum']}")
    if isinstance(v, str):
        if len(v) < s.get("minLength", 0):
            errs.append(f"{path}: shorter than {s['minLength']}")
        if "maxLength" in s and len(v) > s["maxLength"]:
            errs.append(f"{path}: longer than {s['maxLength']}")
        if "pattern" in s and not re.search(s["pattern"], v):
            errs.append(f"{path}: does not match /{s['pattern']}/")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if "minimum" in s and v < s["minimum"]:
            errs.append(f"{path}: {v} < {s['minimum']}")
        if "maximum" in s and v > s["maximum"]:
            errs.append(f"{path}: {v} > {s['maximum']}")
    if isinstance(v, dict):
        for k in s.get("required", []):
            if k not in v:
                errs.append(f"{path}.{k}: required")
        for k, sub in (s.get("properties") or {}).items():
            if k in v:
                _check(v[k], sub, f"{path}.{k}", errs)
    if isinstance(v, list):
        if len(v) < s.get("minItems", 0):
            errs.append(f"{path}: fewer than {s['minItems']} items")
        if "items" in s:
            for i, item in enumerate(v):
                _check(item, s["items"], f"{path}[{i}]", errs)


@gate("schema")
def schema(argv: List[str]) -> int:
    """JSON file matches a schema (type, required, properties, items, enum,
    min/maxLength, pattern, minimum/maximum, minItems). No dependencies."""
    ap = argparse.ArgumentParser(prog="sgl gate schema")
    ap.add_argument("path")
    ap.add_argument("--schema", required=True)
    a = ap.parse_args(argv)
    try:
        data = json.loads(Path(a.path).read_text())
    except FileNotFoundError:
        return _fail(f"{a.path}: missing")
    except json.JSONDecodeError as e:
        return _fail(f"{a.path}: not valid JSON ({e})")
    errs: List[str] = []
    _check(data, json.loads(Path(a.schema).read_text()), "$", errs)
    if errs:
        print("\n".join(errs[:20]))
        return _fail(f"{len(errs)} schema violation(s)")
    return _ok("schema valid")


# --------------------------------------------------------------------------- preflight
@gate("preflight")
def preflight(argv: List[str]) -> int:
    """Can this run work at all? Commands on PATH, env vars set (values are
    never printed), URLs reachable. Run it as the first gate of any loop."""
    ap = argparse.ArgumentParser(prog="sgl gate preflight")
    ap.add_argument("--cmd", action="append", default=[])
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--url", action="append", default=[])
    ap.add_argument("--timeout", type=float, default=8)
    a = ap.parse_args(argv)
    bad = [f"command not found: {c}" for c in a.cmd if not shutil.which(c)]
    bad += [f"env var not set: {e}" for e in a.env if not os.environ.get(e)]
    # urllib can be handed file:// and other schemes, so each URL's scheme is
    # checked against an allowlist right here and everything else is refused.
    # bandit's B310 is suppressed below; keep that comment bare (adding prose
    # after the id makes bandit read the words as more test ids and warn).
    for u in a.url:
        if urllib.parse.urlsplit(u).scheme not in ("http", "https"):
            bad.append(f"{u}: only http(s) URLs are allowed")
            continue
        try:
            req = urllib.request.Request(u, method="HEAD", headers={"User-Agent": "sgl-preflight"})
            with urllib.request.urlopen(req, timeout=a.timeout) as r:  # nosec B310
                if r.status >= 500:
                    bad.append(f"{u}: HTTP {r.status}")
        except urllib.error.HTTPError as e:
            if e.code >= 500:
                bad.append(f"{u}: HTTP {e.code}")
        except Exception as e:  # network down, DNS, TLS
            bad.append(f"{u}: unreachable ({type(e).__name__})")
    if bad:
        return _fail("; ".join(bad))
    return _ok(f"{len(a.cmd)} cmd, {len(a.env)} env, {len(a.url)} url checks")


# --------------------------------------------------------------------------- cap
@gate("cap")
def cap(argv: List[str]) -> int:
    """Rate cap: fewer than --max ledger entries for --key today (posts/day, emails/day).
    With --record, appends an entry when the gate passes, so place it as the
    gate right before the side effect."""
    import datetime as dt
    import fcntl
    ap = argparse.ArgumentParser(prog="sgl gate cap")
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--max", type=int, required=True)
    ap.add_argument("--record", action="store_true")
    a = ap.parse_args(argv)
    if "\t" in a.key or "\n" in a.key:
        return _fail("key must not contain tabs or newlines")
    today = dt.date.today().isoformat()
    led = Path(a.ledger)
    led.parent.mkdir(parents=True, exist_ok=True)
    # Count-then-append must be atomic, or two runs fired at once both see
    # "2/3 used" and both send. An exclusive lock makes the cap a real cap.
    with open(led, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        used = sum(1 for r in f.read().splitlines() if r.split("\t")[:2] == [today, a.key])
        if used >= a.max:
            return _fail(f"cap reached for '{a.key}': {used}/{a.max} today")
        if a.record:
            f.write(f"{today}\t{a.key}\n")
            f.flush()
            used += 1
    return _ok(f"'{a.key}' {used}/{a.max} today")


def main(argv: List[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: sgl gate <name> [args]\n\ngates:")
        for n, fn in GATES.items():
            print(f"  {n:<12} {(fn.__doc__ or '').strip().splitlines()[0]}")
        return 0 if argv else 2
    name, rest = argv[0], argv[1:]
    if name not in GATES:
        print(f"unknown gate: {name}. Try: {', '.join(GATES)}")
        return 2
    return GATES[name](rest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
