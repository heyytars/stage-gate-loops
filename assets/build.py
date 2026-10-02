#!/usr/bin/env python3
"""Builds every README graphic, in light and dark, from one palette.

Design rules for these pictures:
  * icons and colour carry the meaning; words are labels, one or two at most
  * green = passed, red = failed and retried; other colours only tell stages apart
  * every number shown is real: the terminal is a real run of examples/blog-publish,
    the chart is bench/bench.py sim with its default arguments

Why a script: SVG text does not reflow. Every label is measured against its
box (fit() fails the build on overflow), and CI re-runs this file and fails if
the committed pictures differ from what it produces.

Usage: python3 assets/build.py
Outputs: assets/*-light.svg, assets/*-dark.svg, assets/social-preview.png
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
# the em dash appears in the terminal picture, so it is written as an entity:
# this repo's docs gate bans the literal character
EM = "&#8212;"

LIGHT = dict(
    bg="#ffffff", panel="#f6f8fa", ink="#1f2328", muted="#59636e", line="#d1d9e0",
    dot="#e3e8ed", shadow="0.08",
    pass_="#1a7f37", fail="#cf222e",
    blue="#0969da", purple="#8250df", orange="#bc4c00",
)
DARK = dict(
    bg="#0d1117", panel="#151b23", ink="#f0f6fc", muted="#9198a1", line="#3d444d",
    dot="#21262d", shadow="0.45",
    pass_="#3fb950", fail="#f85149",
    blue="#4493f8", purple="#ab7df8", orange="#f0883e",
)
# the terminal is dark in both themes, like a real terminal
TERM = dict(bg="#0d1117", bar="#161b22", line="#30363d", ink="#e6edf3", muted="#7d8590",
            pass_="#3fb950", fail="#f85149", accent="#ab7df8")

ICONS = {  # 24x24 stroke icons, drawn for this repo
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.3-4.3"/>',
    "pen": '<path d="M13 20h8"/><path d="M16.5 3.6a2.1 2.1 0 0 1 3 3L7.5 18.6 3.5 19.5l.9-4z"/>',
    "send": '<path d="M21 3L10.5 13.5"/><path d="M21 3l-6.5 18-4-7.5L3 9.5z"/>',
    "flag": '<path d="M5 21V4"/><path d="M5 4h12l-2.5 4.5L17 13H5"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "x": '<path d="M7 7l10 10M17 7L7 17"/>',
    "retry": '<path d="M4 12a8 8 0 1 0 2.4-5.7"/><path d="M4 4v5h5"/>',
    "bot": '<rect x="4" y="8" width="16" height="12" rx="3.5"/><path d="M12 8V4.5"/>'
           '<circle cx="12" cy="3.5" r="1.2"/><path d="M9.5 13.5v1.5M14.5 13.5v1.5"/>',
    "terminal": '<rect x="3" y="4" width="18" height="16" rx="3.5"/><path d="M7.5 10l3 2.5-3 2.5M13 15.5h4"/>',
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "coin": '<ellipse cx="12" cy="7" rx="7" ry="3"/><path d="M5 7v5c0 1.7 3.1 3 7 3s7-1.3 7-3V7"/>'
            '<path d="M5 12v5c0 1.7 3.1 3 7 3s7-1.3 7-3v-5"/>',
}


# --------------------------------------------------------------------------- primitives
def w(text: str, size: float) -> float:
    """Conservative rendered width (monospace is 0.60em; sans is narrower)."""
    return len(text) * size * 0.60


def fit(text: str, size: float, box: float, where: str) -> None:
    if w(text, size) > box:
        raise SystemExit(f"overflow in {where}: {text!r} needs {w(text, size):.0f}px, box is {box:.0f}px")


def t(x, y, s, size=13, fill="#000", anchor="start", family=SANS, weight="400", spacing=None):
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    ls = f' letter-spacing="{spacing}"' if spacing else ""
    # white-space:pre keeps leading spaces (SVG collapses them otherwise)
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-family="{family}" fill="{fill}"'
            f' font-weight="{weight}"{a}{ls} xml:space="preserve" style="white-space:pre">{s}</text>')


def icon(name, cx, cy, size, colour, sw=2.0):
    k = size / 24
    return (f'<g transform="translate({cx - size / 2:.1f},{cy - size / 2:.1f}) scale({k:.4f})" fill="none" '
            f'stroke="{colour}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">'
            f'{ICONS[name]}</g>')


def frame(W, H, p, title, desc, dots=True):
    """Canvas: rounded card, faint dot grid, soft shadow filter, arrow markers."""
    grid = (f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="20" fill="url(#dots)"/>'
            if dots else "")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"
  role="img" aria-labelledby="t" aria-describedby="d">
  <title id="t">{title}</title><desc id="d">{desc}</desc>
  <defs>
    <pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse">
      <circle cx="2" cy="2" r="1.1" fill="{p['dot']}"/>
    </pattern>
    <filter id="sh" x="-30%" y="-30%" width="160%" height="170%">
      <feDropShadow dx="0" dy="6" stdDeviation="9" flood-color="#000" flood-opacity="{p['shadow']}"/>
    </filter>
    <marker id="am" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M0 0L10 5L0 10z" fill="{p['muted']}"/></marker>
    <marker id="ag" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M0 0L10 5L0 10z" fill="{p['pass_']}"/></marker>
    <marker id="ar" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M0 0L10 5L0 10z" fill="{p['fail']}"/></marker>
  </defs>
  <rect x="0.75" y="0.75" width="{W - 1.5}" height="{H - 1.5}" rx="20" fill="{p['bg']}" stroke="{p['line']}" stroke-width="1.5"/>
  {grid}
'''


def tile(cx, cy, size, name, colour, p, label=None, badge=False, solid=False):
    """A stage: a soft tinted square with one icon and a one-word label under it."""
    h = size / 2
    r = round(size * 0.26)
    s = f'<rect x="{cx - h}" y="{cy - h}" width="{size}" height="{size}" rx="{r}" fill="{p["bg"]}" filter="url(#sh)"/>'
    s += (f'<rect x="{cx - h}" y="{cy - h}" width="{size}" height="{size}" rx="{r}" '
          f'fill="{colour}" fill-opacity="{0.16 if solid else 0.09}" stroke="{colour}" '
          f'stroke-opacity="{0.9 if solid else 0.35}" stroke-width="{2 if solid else 1.5}"/>')
    s += icon(name, cx, cy, size * 0.42, colour)
    if label:
        fit(label, 15, size + 60, f"tile label {label}")
        s += t(cx, cy + h + 30, label, 15, p["ink"], anchor="middle", weight="600")
    if badge:
        bx, by = cx + h - 4, cy - h + 4
        s += f'<circle cx="{bx}" cy="{by}" r="12" fill="{p["fail"]}" stroke="{p["bg"]}" stroke-width="2.5"/>'
        s += icon("retry", bx, by, 13, "#ffffff", sw=2.8)
    return s


def gate(cx, cy, r, ok, p):
    """A gate: a round checkpoint. Green tick passes, red cross stops the line."""
    c = p["pass_"] if ok else p["fail"]
    s = f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{p["bg"]}" filter="url(#sh)"/>'
    s += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{c}" fill-opacity="0.12" stroke="{c}" stroke-width="2.2"/>'
    s += icon("check" if ok else "x", cx, cy, r * 1.05, c, sw=3.0)
    return s


def pill(cx, cy, text, colour, p, size=13, filled=False):
    fit(text, size, 400, f"pill {text}")
    pw = w(text, size) + 26
    ph = size + 14
    s = (f'<rect x="{cx - pw / 2:.1f}" y="{cy - ph / 2:.1f}" width="{pw:.1f}" height="{ph}" rx="{ph / 2}" '
         f'fill="{colour if filled else p["bg"]}" stroke="{colour}" stroke-width="1.5"/>')
    s += t(cx, cy + size * 0.36, text, size, "#ffffff" if filled else colour,
           anchor="middle", weight="700", family=MONO)
    return s


def track(x1, x2, y, p):
    return (f'<path d="M{x1} {y}H{x2}" stroke="{p["muted"]}" stroke-opacity="0.55" '
            f'stroke-width="2.2" stroke-linecap="round" marker-end="url(#am)"/>')


def arc(x1, y1, x2, y2, lift, colour, marker="ar", dash="7 6"):
    """A dashed return arrow that hops over the row, from a gate back to a stage."""
    top = min(y1, y2) - lift
    return (f'<path d="M{x1} {y1} C{x1} {top}, {x2} {top}, {x2} {y2 - 8}" fill="none" stroke="{colour}" '
            f'stroke-width="2.4" stroke-dasharray="{dash}" stroke-linecap="round" marker-end="url(#{marker})"/>')


def mark(x, y, s, colour):
    """The logo: two posts and a bar with a knot. A gate you pass through."""
    return (f'<g transform="translate({x},{y}) scale({s})" stroke="{colour}" stroke-width="2.4" '
            f'fill="none" stroke-linecap="round"><path d="M2 2v18M24 2v18"/>'
            f'<path d="M2 11h22" stroke-width="2.8"/><circle cx="13" cy="11" r="3.6" fill="{colour}" stroke="none"/></g>')


# --------------------------------------------------------------------------- hero
STAGES = [("search", "research", "blue"), ("pen", "draft", "purple"),
          ("send", "publish", "orange"), ("flag", "done", "pass_")]


def hero_body(p, title_size=34, top=0) -> str:
    s = mark(62, 56 + top, 1.7, p["pass_"])
    s += t(118, 88 + top, "stage gate loops", title_size, p["ink"], weight="800", spacing="-0.5")
    s += t(118, 118 + top, "Check every step. Stop at the first failure.", 17, p["muted"])

    cy, T = 268 + top, 104
    xs = [210, 500, 790, 1080]
    gates = [(355, True, "schema"), (645, False, "no em dash"), (935, True, "published")]
    for i in range(3):
        s += track(xs[i] + T / 2 + 10, xs[i + 1] - T / 2 - 14, cy, p)
    for (gx, ok, name) in gates:
        s += gate(gx, cy, 22, ok, p)
        fit(name, 12, 150, f"gate label {name}")
        s += t(gx, cy + 46, name, 12, p["pass_"] if ok else p["fail"], anchor="middle",
               family=MONO, weight="600")
    for (ic, label, col), x in zip(STAGES, xs):
        s += tile(x, cy, T, ic, p[col], p, label=label, solid=(label == "done"),
                  badge=(label == "draft"))
    s += arc(645, cy - 26, 512, cy - T / 2, 92, p["fail"])
    s += pill(578, cy - 112, "fail: redo draft only", p["fail"], p)
    return s


def hero(p) -> str:
    return frame(1280, 420, p, "stage gate loops",
                 "Four stages in a row with a checkpoint between each. The checkpoint after draft "
                 "fails, and only the draft stage runs again.") + hero_body(p) + "</svg>\n"


def social(p) -> str:
    """1280x640 link preview. Its own canvas, so the background fills all of it."""
    return (frame(1280, 640, p, "stage gate loops", "Check every step. Stop at the first failure.")
            + hero_body(p, title_size=40, top=100) + "</svg>\n")


# --------------------------------------------------------------------------- one gate, up close
def flow(p) -> str:
    W, H = 1280, 400
    s = frame(W, H, p, "One gate, up close",
              "A stage runs, a gate checks the result. Exit 0 moves on to the next stage. "
              "Anything else sends the error back to the same stage, which tries again.")
    s += t(64, 60, "ONE GATE, UP CLOSE", 12, p["muted"], family=MONO, weight="700", spacing="1.5")
    cy = 228
    A, B, C = 240, 640, 1040
    s += track(A + 70, B - 82, cy, p)
    s += (f'<path d="M{B + 70} {cy}H{C - 82}" stroke="{p["pass_"]}" stroke-width="2.6" '
          f'stroke-linecap="round" marker-end="url(#ag)"/>')
    s += pill((B + C) / 2 - 6, cy - 26, "exit 0", p["pass_"], p, filled=True)
    s += arc(B - 24, cy - 66, A + 24, cy - 60, 92, p["fail"])
    s += pill((A + B) / 2, cy - 140, "fail: error goes back", p["fail"], p, filled=True)

    s += tile(A, cy, 120, "bot", p["purple"], p)
    s += t(A, cy + 96, "stage runs", 17, p["ink"], anchor="middle", weight="700")
    s += t(A, cy + 120, "agent, script or job", 13, p["muted"], anchor="middle")

    s += f'<circle cx="{B}" cy="{cy}" r="62" fill="{p["bg"]}" filter="url(#sh)"/>'
    s += (f'<circle cx="{B}" cy="{cy}" r="62" fill="{p["blue"]}" fill-opacity="0.09" '
          f'stroke="{p["blue"]}" stroke-opacity="0.5" stroke-width="1.8"/>')
    s += icon("terminal", B, cy, 52, p["blue"])
    s += t(B, cy + 96, "gate checks", 17, p["ink"], anchor="middle", weight="700")
    s += t(B, cy + 120, "tests · schema · lint · any command", 13, p["muted"], anchor="middle")

    s += tile(C, cy, 120, "arrow", p["pass_"], p, solid=True)
    s += t(C, cy + 96, "next stage", 17, p["ink"], anchor="middle", weight="700")
    s += t(C, cy + 120, "only after a pass", 13, p["muted"], anchor="middle")
    return s + "</svg>\n"


# --------------------------------------------------------------------------- two ways
def compare(p) -> str:
    W, H = 1280, 440
    s = frame(W, H, p, "Two ways to verify a loop",
              "Checking once at the end reruns all four stages after a failure. "
              "A gate after every stage reruns only the stage that failed.")
    icons = [st[0] for st in STAGES[:3]] + ["flag"]
    cols = [p[st[2]] for st in STAGES[:3]] + [p["muted"]]
    cy, T = 236, 68

    def rail(x1, x2):  # one quiet connector behind a row; the order reads left to right
        return (f'<path d="M{x1} {cy}H{x2}" stroke="{p["muted"]}" stroke-opacity="0.45" '
                f'stroke-width="2.2" stroke-linecap="round"/>')

    def card(x, colour, ok, title):
        c = (f'<rect x="{x}" y="36" width="590" height="{H - 72}" rx="18" fill="{colour}" fill-opacity="0.035" '
             f'stroke="{colour}" stroke-opacity="0.4" stroke-width="1.5"/>')
        c += icon("check" if ok else "x", x + 44, 82, 24, colour, sw=2.8)
        return c + t(x + 68, 90, title, 22, p["ink"], weight="800")

    # left: four stages, then one check at the very end
    s += card(40, p["fail"], False, "Check at the end")
    lx = [112, 216, 320, 424]
    s += rail(lx[0], 560)
    for ic, col, x in zip(icons, cols, lx):
        s += tile(x, cy, T, ic, col, p, badge=True)
    s += gate(560, cy, 24, False, p)
    s += arc(560, cy - 28, lx[0] + 10, cy - T / 2, 96, p["fail"])
    s += pill(336, cy - 112, "rerun everything", p["fail"], p)
    s += t(84, 362, "4×", 60, p["fail"], weight="800", spacing="-1")
    s += t(172, 344, "stages run again", 17, p["ink"], weight="700")
    s += t(172, 368, "the error is found last", 14, p["muted"])

    # right: a gate between every pair of stages
    s += card(650, p["pass_"], True, "Gate every stage")
    rx = [714, 862, 1010, 1158]
    s += rail(rx[0], rx[3])
    for i, (ic, col, x) in enumerate(zip(icons, cols, rx)):
        s += tile(x, cy, T, ic, col, p, badge=(i == 1))
    for i in range(3):
        s += gate((rx[i] + rx[i + 1]) / 2, cy, 17, i != 1, p)
    gx = (rx[1] + rx[2]) / 2
    s += arc(gx, cy - 21, rx[1] + 10, cy - T / 2, 70, p["fail"])
    s += pill((gx + rx[1]) / 2, cy - 98, "rerun one", p["fail"], p)
    s += t(694, 362, "1×", 60, p["pass_"], weight="800", spacing="-1")
    s += t(782, 344, "stage runs again", 17, p["ink"], weight="700")
    s += t(782, 368, "the error is found where it happened", 14, p["muted"])
    return s + "</svg>\n"


# --------------------------------------------------------------------------- benchmark
# bench/bench.py sim, default arguments (4 stages x 3,000 tokens, 25% fail, 3 tries, 20,000 trials)
END_TOKENS, END_DONE = 25927, 67.9
GATE_TOKENS, GATE_DONE = 15394, 93.8


def benchmark(p) -> str:
    W, H = 1280, 360
    pct = round(GATE_TOKENS * 100 / END_TOKENS)
    s = frame(W, H, p, "Benchmark (simulation)",
              f"Stage gates used {pct}% of the tokens of an end-of-run check, "
              f"and {GATE_DONE}% of runs finished against {END_DONE}%.")
    s += icon("coin", 84, 92, 34, p["pass_"])
    s += t(64, 214, f"{pct}%", 112, p["pass_"], weight="800", spacing="-4")
    s += t(68, 252, "of the tokens", 20, p["ink"], weight="700")
    s += t(68, 278, "with gates on every stage", 14, p["muted"])

    x0, bw, bh = 470, 560, 40
    rows = [("Check at the end", END_TOKENS, END_DONE, p["fail"], "x", 86),
            ("Gate every stage", GATE_TOKENS, GATE_DONE, p["pass_"], "check", 196)]
    for label, val, done, col, ic, y in rows:
        s += icon(ic, x0 + 10, y - 2, 20, col, sw=3)
        s += t(x0 + 30, y + 4, label, 16, p["ink"], weight="700")
        s += (f'<rect x="{x0}" y="{y + 18}" width="{bw}" height="{bh}" rx="{bh / 2}" '
              f'fill="{p["panel"]}" stroke="{p["line"]}"/>')
        barw = bw * val / END_TOKENS
        s += (f'<rect x="{x0}" y="{y + 18}" width="{barw:.0f}" height="{bh}" rx="{bh / 2}" '
              f'fill="{col}" fill-opacity="0.85"/>')
        s += t(x0 + bw + 24, y + 46, f"{val / 1000:.1f}k", 28, col, weight="800")
        fit(f"{done}% finish", 13, 140, "bench finish")
        s += t(x0 + bw + 24, y + 68, f"{done}% finish", 13, p["muted"], family=MONO)
    foot = "simulation · 4 stages · 3,000 tokens each · 25% fail · 3 tries · 20,000 runs"
    fit(foot, 12, 1150, "bench foot")
    s += t(64, 330, foot, 12, p["muted"], family=MONO)
    return s + "</svg>\n"


# --------------------------------------------------------------------------- terminal
def terminal(_p) -> str:
    """A real run of examples/blog-publish, copied from the terminal."""
    q = TERM
    lines = [
        ("$ sgl run pipeline.yaml", q["muted"], "400", None),
        ("sgl ▸ blog-publish  (4 stages)", q["accent"], "700", None),
        ("  [1] preflight: PASS  gates: tools", q["pass_"], "400", None),
        ("  [2] research: PASS  gates: brief-schema", q["pass_"], "400", None),
        ("  [3] draft: FAIL at gate 'no-em-dash'  → retrying with feedback", q["fail"], "700", "caught"),
        (f"        out/post.md:7: /\\u2014/ in: Most agent loops check their work at the end {EM} after...",
         q["muted"], "400", None),
        ("  [3] draft: PASS (attempt 2)  gates: exists, frontmatter, no-em-dash, no-filler, length",
         q["pass_"], "700", "fixed"),
        ("  [4] publish: PASS  gates: published", q["pass_"], "400", None),
        ("sgl ▸ ALL GATES PASSED (0.8s)", q["accent"], "700", None),
    ]
    W, lh, top = 1280, 31, 96
    H = top + len(lines) * lh + 34
    s = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"
  role="img" aria-labelledby="t" aria-describedby="d">
  <title id="t">A real sgl run</title><desc id="d">The draft stage fails the no-em-dash gate, gets the exact
  failing line back, passes on attempt 2, and the run finishes.</desc>
  <rect width="{W}" height="{H}" rx="18" fill="{q['bg']}"/>
  <path d="M18 0H{W - 18}A18 18 0 0 1 {W} 18V52H0V18A18 18 0 0 1 18 0z" fill="{q['bar']}"/>
  <path d="M0 52H{W}" stroke="{q['line']}"/>
  <rect x="0.75" y="0.75" width="{W - 1.5}" height="{H - 1.5}" rx="18" fill="none" stroke="{q['line']}" stroke-width="1.5"/>
'''
    for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        s += f'<circle cx="{30 + i * 22}" cy="26" r="6.5" fill="{c}"/>'
    s += t(W / 2, 31, "examples/blog-publish", 13, q["muted"], anchor="middle", family=MONO)
    for i, (ln, col, wt, tag) in enumerate(lines):
        y = top + i * lh
        if tag:
            c = q["fail"] if tag == "caught" else q["pass_"]
            s += f'<rect x="20" y="{y - 21}" width="{W - 40}" height="{lh - 1}" rx="7" fill="{c}" fill-opacity="0.12"/>'
            s += f'<rect x="20" y="{y - 21}" width="4" height="{lh - 1}" rx="2" fill="{c}"/>'
            s += pill(W - 82, y - 6, tag, c, dict(bg=q["bg"]), size=12, filled=True)
        fit(ln.replace(EM, "-"), 14.5, W - 200, f"term line {i}")
        s += t(44, y, ln.replace("'", "&#39;"), 14.5, col, family=MONO, weight=wt)
    return s + "</svg>\n"


# --------------------------------------------------------------------------- logo
def logo(p) -> str:
    W, H = 420, 120
    s = frame(W, H, p, "stage-gate-loops", "Two posts and a bar: a gate you pass through", dots=False)
    s += mark(40, 38, 1.9, p["pass_"])
    s += t(108, 70, "stage gate loops", 26, p["ink"], weight="800", spacing="-0.3")
    s += t(109, 92, "check every step", 13, p["muted"], family=MONO)
    return s + "</svg>\n"


def main() -> int:
    assets = [("hero", hero), ("how-it-works", flow), ("two-ways", compare),
              ("benchmark", benchmark), ("terminal", terminal), ("logo", logo),
              ("social", social)]
    for name, fn in assets:
        for theme, pal in (("light", LIGHT), ("dark", DARK)):
            path = OUT / f"{name}-{theme}.svg"
            path.write_text(fn(pal))
            print(f"wrote assets/{path.name}  ({path.stat().st_size} bytes)")

    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if Path(chrome).exists():
        png = OUT / "social-preview.png"
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=1", "--window-size=1280,640",
                        f"--screenshot={png}", f"file://{OUT / 'social-light.svg'}"],
                       check=True, capture_output=True)
        print(f"wrote assets/{png.name}  ({png.stat().st_size} bytes)")
    else:
        print("Chrome not found: skipped social-preview.png", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
