# Claude Code adapter

Blocks Claude from finishing a turn while any gate in your pipeline fails. Claude receives the gate's exact output as the reason and keeps working.

## Setup

1. Install: `pip install git+https://github.com/heyytars/stage-gate-loops`
2. Put a pipeline in your repo, e.g. `.sgl.yaml`:

```yaml
name: repo-gates
stages:
  - name: build
    gates:
      - run: python -m compileall -q src
  - name: tests
    gates:
      - run: pytest -q
  - name: hygiene
    gates:
      - run: sgl gate no-pattern src/app.py -p "breakpoint\(" -p "print\("
```

3. Add the hook to `.claude/settings.json` (project) or `~/.claude/settings.json` (all projects). A copy is in [`settings.json`](settings.json):

```json
{
  "hooks": {
    "Stop": [{ "hooks": [{ "type": "command", "command": "sgl hook claude-code .sgl.yaml" }] }]
  }
}
```

## Behaviour

- The hook runs `--gates-only`. Stage commands never run, so it only checks the working tree.
- All gates pass: exit 0, no output, Claude stops normally.
- A gate fails: it prints `{"decision": "block", "reason": "..."}`. Claude continues with the failure in context. On a repeat failure (`stop_hook_active`), the reason tells Claude to change its approach.
- If the pipeline file is missing or invalid, it exits 0 silently. A config mistake must never trap a session.
- Claude Code caps consecutive stop-hook continuations at 8 (`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`), so an impossible gate ends the loop rather than spinning forever.

Keep hook gates fast. They run every time Claude tries to stop.
