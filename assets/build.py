#!/usr/bin/env python3
"""Builds the README/SVG assets in both light and dark themes.

Why a script: SVG text does not reflow. Every label is measured against its
container (monospace, 0.60em per char) and the script exits loudly if a string
would overflow. Edit the copy, re-run, and the layout stays correct.

  python3 assets/build.py

Outputs: assets/*-light.svg, assets/*-dark.svg, assets/social-preview.png
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
# the em dash is drawn as text, so it must never be written literally in this file
EM = "&#8212;"

LIGHT = dict(
    bg="#ffffff", panel="#f6f8fa", ink="#1f2328", muted="#59636e", line="#d1d9e0",
    pass_="#1a7f37", fail="#cf222e", brand="#1a7f37", zebra="#eff2f5",
)
DARK = dict(
    bg="#0d1117", panel="#161b22", ink="#e6edf3", muted="#9198a1", line="#30363d",
    pass_="#3fb950", fail="#f85149", brand="#3fb950", zebra="#1c2128",
)


def w(text: str, size: float) -> float:
    """Approximate rendered width of monospace text."""
    return len(text) * size * 0.60


def fit(text: str, size: float, box: float, where: str) -> None:
    if w(text, size) > box:
        raise SystemExit(f"overflow in {where}: {text!r} needs {w(text, size):.0f}px, box is {box:.0f}px")


def t(x, y, s, size=13, fill=None, anchor="start", family=MONO, weight="400", opacity=None):
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    o = f' opacity="{opacity}"' if opacity else ""
    fam = f' font-family="{family}"' if family else ""
    return (f'<text x="{x}" y="{y}" font-size="{size}"{fam} fill="{fill}"'
            f' font-weight="{weight}"{a}{o}>{s}</text>')


def rect(x, y, wd, h, c, r=6, sw=1.5, dash=None, fill="none"):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x}" y="{y}" width="{wd}" height="{h}" rx="{r}" fill="{fill}" '
            f'stroke="{c}" stroke-width="{sw}"{d}/>')


def arrow(x1, y1, x2, y2, c, marker="a"):
    return f'<path d="M{x1} {y1} L{x2} {y2}" stroke="{c}" stroke-width="1.6" marker-end="url(#{marker})"/>'


def header(wd, h, p, title, desc):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{wd}" height="{h}" viewBox="0 0 {wd} {h}"
  role="img" aria-labelledby="t" aria-describedby="d">
  <title id="t">{title}</title><desc id="d">{desc}</desc>
  <defs>
    <marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M0 0 L10 5 L0 10 z" fill="{p['muted']}"/>
    </marker>
    <marker id="af" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M0 0 L10 5 L0 10 z" fill="{p['fail']}"/>
    </marker>
  </defs>
  <rect width="{wd}" height="{h}" rx="12" fill="{p['bg']}"/>
  <rect x="0.75" y="0.75" width="{wd - 1.5}" height="{h - 1.5}" rx="11" fill="none"
        stroke="{p['line']}" stroke-width="1.5"/>
'''


def gate_mark(x, y, s, p, colour=None):
    """The logo mark: two posts and a bar between them. A gate you pass through."""
    c = colour or p["brand"]
    return f'''<g transform="translate({x},{y}) scale({s})" stroke="{c}" stroke-width="2.2"
     fill="none" stroke-linecap="round">
  <path d="M2 2 v16 M22 2 v16"/>
  <path d="M2 10 h20" stroke-width="2.6"/>
  <circle cx="12" cy="10" r="3.2" fill="{c}" stroke="none"/>
</g>'''


def stage_card(x, y, bw, bh, num, name, note, p, colour=None, verdict=None):
    """A stage box: number, name, one-line role, optional PASS/FAIL tag."""
    col = colour or p["line"]
    s = rect(x, y, bw, bh, col, r=9, sw=1.6 if colour else 1.4)
    s += t(x + 14, y + 23, f"STAGE {num}", 10, p["muted"], weight="700")
    fit(name, 15, bw - 28, f"stage name {name}")
    s += t(x + 14, y + 45, name, 15, p["ink"], weight="700", family=SANS)
    s += t(x + 14, y + 63, note, 10, p["muted"])
    if verdict:
        s += t(x + bw - 14, y + 23, verdict, 10, col, anchor="end", weight="700")
    return s


# --------------------------------------------------------------------------- hero
def hero_body(p) -> str:
    """The hero artwork without its frame, so the social card can reuse it."""
    s = gate_mark(44, 40, 2.0, p)
    title = "Stage gate loops"
    tag = "Check every step. Stop at the first failure."
    fit(title, 40, 1000, "hero title")
    s += t(100, 78, title, 40, p["ink"], weight="700", family=SANS)
    s += t(100, 108, tag, 15, p["muted"], family=SANS)

    s += rect(40, 148, 1200, 196, p["line"], r=10, fill=p["panel"])
    # slot must hold: box 250 + gap to diamond 9 + diamond 40 + gap to next box 4 = 296 min
    bx, bw, gap, gy, bh = 60, 250, 60, 186, 88
    gatex = bx + bw + 9
    for i in range(4):
        x = bx + i * (bw + gap)
        if i < 3:
            s += stage_card(x, gy, bw, bh, i + 1, ["research", "draft", "publish"][i],
                            "the agent does the work", p)
            gname = ["brief-schema", "frontmatter", "published"][i]
            cx = gatex + i * (bw + gap) + 13
            s += f'<path d="M{cx + 3} {gy + bh / 2} l10 -15 h20 l10 15 l-10 15 h-20 z" ' \
                 f'fill="{p["bg"]}" stroke="{p["muted"]}" stroke-width="1.4"/>'
            s += t(cx + 13, gy + bh / 2 + 38, "gate", 10, p["muted"], anchor="middle")
            fit(gname, 10, 90, f"gate {gname}")
            s += t(cx + 13, gy + bh / 2 + 52, gname, 10, p["pass_"], anchor="middle")
            if i < 2:
                s += arrow(x + bw + 4, gy + bh / 2, gatex + i * (bw + gap) - 3, gy + bh / 2, p["muted"])
                s += arrow(gatex + i * (bw + gap) + 29, gy + bh / 2,
                           bx + (i + 1) * (bw + gap) - 4, gy + bh / 2, p["muted"])
        else:
            s += rect(x, gy, bw, bh, p["brand"], r=9, sw=1.8)
            s += t(x + 14, gy + 23, "STAGE 4", 10, p["muted"], weight="700")
            s += t(x + 14, gy + 45, "done", 15, p["ink"], weight="700", family=SANS)
            s += t(x + 14, gy + 63, "\u2713 every gate passed", 11, p["brand"])

    fx = bx + 1 * (bw + gap) + bw + 13 - 37
    s += f'<path d="M{fx} {gy + bh} v18" stroke="{p["fail"]}" stroke-width="1.6" marker-end="url(#af)"/>'
    s += t(fx + 12, gy + bh + 30, "FAIL: stop the line, hand the failure back, rerun only this stage",
           12, p["fail"])
    s += t(60, 378, "Each gate is a command. Exit 0 = pass, anything else = fail. No model decides.",
           12, p["muted"])
    return s


def hero(p) -> str:
    W, H = 1280, 420
    s = header(W, H, p, "Stage gate loops",
               "Four stages, each ending in a gate that must pass before the next stage runs")
    return s + hero_body(p) + "</svg>\n"


def social(p) -> str:
    """1280x640 card for link previews. The background must fill the whole
    canvas: a preview that is cropped to 640 with a white band at the bottom
    looks broken in every chat client."""
    W, H = 1280, 640
    s = header(W, H, p, "Stage gate loops", "Check every step. Stop at the first failure.")
    return s + f'<g transform="translate(0,{(H - 420) / 2:.0f})">' + hero_body(p) + "</g></svg>\n"


# --------------------------------------------------------------------------- flow
def flow(p) -> str:
    W, H = 1280, 640
    s = header(W, H, p, "How a run flows",
               "Stage three fails a gate and retries; the rest is skipped")
    s += rect(40, 30, 1200, 42, p["line"], r=8, fill=p["panel"])
    s += t(60, 58, "sgl run pipeline.yaml", 14, p["ink"], weight="700")

    y, bh = 100, 78
    steps = [
        ("1", "preflight", "pass", p["pass_"]),
        ("2", "research", "pass", p["pass_"]),
        ("3", "draft", "fail", p["fail"]),
        ("3", "draft (retry)", "pass", p["pass_"]),
        ("4", "publish", "pass", p["pass_"]),
    ]
    x0, bw, gap = 48, 210, 36
    for i, (num, name, verdict, col) in enumerate(steps):
        x = x0 + i * (bw + gap)
        s += rect(x, y, bw, bh, col, r=9, sw=1.6)
        s += t(x + 12, y + 22, f"STAGE {num}", 10, p["muted"], weight="700")
        s += t(x + bw - 12, y + 22, verdict.upper(), 10, col, anchor="end", weight="700")
        fit(name, 15, bw - 24, f"flow name {name}")
        s += t(x + 12, y + 46, name, 15, p["ink"], weight="700", family=SANS)
        note = "gate passed" if verdict == "pass" and "retry" not in name else (
            "gate failed" if verdict == "fail" else "gate passed")
        s += t(x + 12, y + 66, note, 10, col)
        if i + 1 < len(steps):
            s += arrow(x + bw + 3, y + bh / 2, x + bw + gap - 4, y + bh / 2, p["muted"])

    # detail box, centred under the failing card, with clearance from the row
    fx = x0 + 2 * (bw + gap)
    s += f'<path d="M{fx + bw / 2} {y + bh} v26" stroke="{p["fail"]}" stroke-width="1.6" marker-end="url(#af)"/>'
    bwid, bhgt = 820, 158
    bxx = fx + bw / 2 - bwid / 2 + 60
    s += rect(bxx, 232, bwid, bhgt, p["fail"], r=10, sw=1.5, fill=p["panel"])
    s += t(bxx + 22, 262, "Gate output, handed back to the agent as $SGL_FEEDBACK", 13,
           p["fail"], weight="700")
    lines = [
        "PASS: exists, frontmatter, no-filler, length",
        f"FAIL: 1 banned match(es) {EM} retry with feedback",
        f"out/post.md:7: /\\u2014/ in: ...check their work at the end ({EM})...",
    ]
    for j, ln in enumerate(lines):
        fit(ln, 12, bwid - 44, f"detail {j}")
        s += t(bxx + 22, 288 + j * 24, ln, 12, p["ink"])
    s += t(bxx + 22, 288 + 3 * 24 + 4, "Only stage 3 runs again.", 12, p["brand"], weight="700")

    # why it is cheaper
    s += rect(40, 430, 1200, 120, p["line"], r=10, fill=p["panel"])
    s += t(64, 462, "Why this is cheaper", 15, p["ink"], weight="700", family=SANS)
    old = "Old way: run all four stages, check at the end, find the problem, pay for all four again."
    new = "Here: the failure is caught at stage 3, and only stage 3 runs a second time."
    for j, ln in enumerate([old, new]):
        fit(ln, 12, 1140, f"cost line {j}")
        s += t(64, 492 + j * 24, ("&#10007; " if j == 0 else "&#10003; ") + ln, 12,
               p["fail"] if j == 0 else p["pass_"])
    s += t(64, 492 + 2 * 24 + 12, "The publish stage above never sees a bad draft.", 11, p["muted"])
    return s + "</svg>\n"


# --------------------------------------------------------------------------- compare
def compare(p) -> str:
    W, H = 1220, 500
    s = header(W, H, p, "Two ways to verify a loop",
               "Verifying at the end against verifying at every transition")
    pw, ph, px, py = 560, 400, 40, 46
    for i, (title, colour, note) in enumerate([
        ("End-of-run check", p["fail"], "verify once, at the end"),
        ("Stage gates", p["pass_"], "verify at every transition"),
    ]):
        x = px + i * (pw + 20)
        s += rect(x, py, pw, ph, colour, r=12, sw=1.8, fill=p["panel"])
        s += t(x + 26, py + 34, title, 20, p["ink"], weight="700", family=SANS)
        s += t(x + 26, py + 56, note, 12, p["muted"])

    # ---- left: four stages, one check at the end, everything runs again
    x = px
    bw, bh, gap = 96, 52, 12
    y0 = py + 80
    for i in range(4):
        cx = x + 26 + i * (bw + gap)
        s += rect(cx, y0, bw, bh, p["line"], r=7)
        s += t(cx + bw / 2, y0 + 31, f"stage {i + 1}", 11, p["ink"], anchor="middle")
        if i < 3:
            s += arrow(cx + bw + 2, y0 + bh / 2, cx + bw + gap - 3, y0 + bh / 2, p["muted"])
    cx = x + 26 + 4 * (bw + gap)
    s += rect(cx, y0, 92, bh, p["fail"], r=7, sw=1.8)
    s += t(cx + 46, y0 + 25, "check", 11, p["ink"], anchor="middle", weight="700")
    s += t(cx + 46, y0 + 42, "fails", 10, p["fail"], anchor="middle")

    # loop-back arrow, drawn in clear space below the row
    ly = y0 + bh + 26
    s += f'<path d="M{cx + 46} {y0 + bh} v14" stroke="{p["fail"]}" stroke-width="1.6" marker-end="url(#af)"/>'
    s += f'<path d="M{x + 26 + 3} {ly} h{cx + 46 - (x + 26) - 6}" stroke="{p["fail"]}" ' \
         f'stroke-width="1.6" stroke-dasharray="5 4" fill="none"/>'
    s += f'<path d="M{x + 26 + 3} {ly} v-14" stroke="{p["fail"]}" stroke-width="1.6" marker-end="url(#af)"/>'
    s += t(x + 200, ly + 22, "every stage runs again", 12, p["fail"], anchor="middle", weight="700")
    fit("every stage runs again", 12, 300, "loop label")

    for j, ln in enumerate(["The work is done in full.",
                            "The check happens at the end.",
                            "It fails.",
                            "All four stages run a second time."]):
        s += t(x + 26, py + 190 + j * 26, f"{j + 1}.", 12, p["muted"])
        fit(ln, 12, pw - 90, f"left {j}")
        s += t(x + 50, py + 190 + j * 26, ln, 12, p["ink"])
    s += t(x + 26, py + 190 + 4 * 26 + 22, "Paid for work that was already wrong.",
           13, p["fail"], weight="700", family=SANS)
    s += t(x + 26, py + 190 + 4 * 26 + 46, "The failure is found last, when it costs the most.",
           11, p["muted"])

    # ---- right: each stage followed by its own gate
    x2 = px + pw + 20
    for i in range(4):
        yy = py + 80 + i * 62
        s += rect(x2 + 26, yy, 230, 46, p["line"], r=7)
        s += t(x2 + 40, yy + 29, f"stage {i + 1}", 12, p["ink"])
        s += arrow(x2 + 258, yy + 23, x2 + 278, yy + 23, p["muted"])
        s += rect(x2 + 282, yy, 150, 46, p["pass_"], r=7, sw=1.5)
        s += t(x2 + 357, yy + 29, "&#10003; gate", 12, p["pass_"], anchor="middle", weight="700")
        if i < 3:
            s += f'<path d="M{x2 + 434} {yy + 23} h16 v62 h-424" stroke="{p["muted"]}" ' \
                 f'stroke-width="1.4" fill="none" marker-end="url(#a)"/>'
        else:
            s += t(x2 + 444, yy + 28, "done", 11, p["pass_"], weight="700")
    # the failure branch, in the gap between rows
    s += f'<path d="M{x2 + 300} {py + 80 + 46} v14" stroke="{p["fail"]}" stroke-width="1.5" marker-end="url(#af)"/>'
    s += t(x2 + 310, py + 80 + 58, "a gate fails: stop and rerun it", 11, p["fail"])
    fit("a gate fails: stop and rerun it", 11, pw - 300, "right fail label")
    s += t(x2 + 26, py + 190 + 4 * 26 + 22, "Paid for one stage, once.",
           13, p["pass_"], weight="700", family=SANS)
    s += t(x2 + 26, py + 190 + 4 * 26 + 46, "The failure is found at the step that caused it.",
           11, p["muted"])
    return s + "</svg>\n"


# --------------------------------------------------------------------------- benchmark
def benchmark(p) -> str:
    W, H = 1040, 500
    s = header(W, H, p, "Benchmark: tokens per successful run",
               "Modelled over 20,000 seeded trials of the same four-stage pipeline")
    s += t(40, 66, "Same pipeline, same failure rate, two strategies", 19, p["ink"],
           weight="700", family=SANS)
    sub = "Model: 4 stages x 3,000 tokens, 25% chance a stage fails per attempt, 3 attempts"
    fit(sub, 12, 960, "bench sub")
    s += t(40, 92, sub, 12, p["muted"])

    x0, bw, bh = 360, 300, 90
    for i, (label, val, note, col) in enumerate([
        ("End-of-run check", 25927, "67.9% of runs finished", p["fail"]),
        ("Stage gates", 15394, "93.8% of runs finished", p["pass_"]),
    ]):
        y = 140 + i * 130
        s += t(40, y + 34, label, 17, p["ink"], weight="700", family=SANS)
        s += t(40, y + 58, note, 12, p["muted"])
        barw = bw * val / 30000
        # a light track makes the bar's length readable, and a tinted fill keeps
        # it solid in both themes (a bare stroke looked empty on white)
        s += rect(x0, y, bw, bh, p["line"], r=7, sw=1, fill=p["zebra"])
        s += f'<rect x="{x0}" y="{y}" width="{barw:.0f}" height="{bh}" rx="7" fill="{col}" opacity="0.18"/>'
        s += rect(x0, y, barw, bh, col, r=7, sw=1.6)
        s += t(x0 + bw + 20, y + 46, f"{val:,}", 22, col, weight="700")
        s += t(x0 + bw + 20, y + 68, "tokens", 11, p["muted"])

    s += rect(40, 406, 960, 64, p["line"], r=10, fill=p["panel"])
    head = "Stage gates used 59% of the tokens and finished far more often."
    fit(head, 14, 920, "bench head")
    s += t(64, 432, head, 14, p["ink"], weight="700", family=SANS)
    foot = "Modelled control-flow numbers, not a model measurement. See bench/README.md."
    fit(foot, 11, 920, "bench foot")
    s += t(64, 452, foot, 11, p["muted"])
    return s + "</svg>\n"


# --------------------------------------------------------------------------- terminal
def terminal(p) -> str:
    lines = [
        ("sgl run pipeline.yaml", p["ink"], "700"),
        ("  [1] preflight: PASS  |  gates: tools", p["pass_"], "400"),
        ("  [2] research: PASS  |  gates: brief-schema", p["pass_"], "400"),
        (f"  [3] draft: FAIL at gate 'no-em-dash'  |  retrying with feedback", p["fail"], "400"),
        (f"        out/post.md:7: /\\u2014/ in: ...check their work at the end ({EM})...",
         p["muted"], "400"),
        ("  [3] draft: PASS (attempt 2)  |  gates: exists, frontmatter, no-em-dash",
         p["pass_"], "400"),
        ("  [4] publish: PASS  |  gates: published", p["pass_"], "400"),
        ("ALL GATES PASSED (0.86s)", p["ink"], "700"),
    ]
    W = 1140
    H = 56 + len(lines) * 27 + 30
    s = header(W, H, p, "A real sgl run",
               "Stage three fails a gate, the failure goes back, only that stage reruns")
    s += rect(28, 26, W - 56, H - 52, p["line"], r=10, fill=p["panel"])
    for i, c in enumerate([p["fail"], "#d4a72c", p["pass_"]]):
        s += f'<circle cx="{52 + i * 18}" cy="50" r="5.5" fill="{c}"/>'
    for i, (ln, col, weight) in enumerate(lines):
        fit(ln, 13, W - 120, f"term {i}")
        s += t(50, 88 + i * 27, ln, 13, col, weight=weight)
    return s + "</svg>\n"


# --------------------------------------------------------------------------- logo
def logo(p) -> str:
    W, H = 340, 130
    s = header(W, H, p, "stage-gate-loops", "Two posts and a bar: a gate you pass through")
    s += gate_mark(52, 34, 2.4, p)
    s += t(132, 68, "stage-gate-loops", 17, p["ink"], weight="700", family=SANS)
    s += t(132, 90, "deterministic gates", 11, p["muted"])
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
