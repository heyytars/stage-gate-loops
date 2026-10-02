# Stage gate loops

**Agent loops check their work at the end. Stage gate loops check it at every step, with a tool that can't be talked into a pass.**

```
stage 1 ──▶ gate ──▶ stage 2 ──▶ gate ──▶ stage 3 ──▶ gate ──▶ done
              │ fail             │ fail             │ fail
              └─ stop the line, hand the failure back, rerun only that stage
```

A gate is any command. Exit `0` means pass. Anything else stops the line. No model grades the work, so there's nothing to argue with: the schema validates or it doesn't, and the tests go green or they don't.

`sgl` is a small runner for this pattern: about 200 lines for the runner and 250 for the built-in gates, with PyYAML as the only dependency. It works with any agent: Claude Code, Codex, your own scripts, or plain cron.

## Try it in a minute

```bash
pip install git+https://github.com/heyytars/stage-gate-loops
git clone https://github.com/heyytars/stage-gate-loops && cd stage-gate-loops/examples/blog-publish
sgl run pipeline.yaml
```

```
sgl ▸ blog-publish  (4 stages)
  [1] preflight: PASS  gates: tools
  [2] research: PASS  gates: brief-schema
  [3] draft: FAIL at gate 'no-em-dash'  → retrying with feedback
        out/post.md:7: /\u2014/ in: Most agent loops check their work at the end (em dash here) after every...
  [3] draft: PASS (attempt 2)  gates: exists, frontmatter, no-em-dash, no-filler, length
  [4] publish: PASS  gates: published
sgl ▸ ALL GATES PASSED (0.86s)
```

The draft broke a rule, so the gate caught it at stage 3. The agent got the exact line back and fixed it, and only that stage ran again. Research didn't rerun, and publish never saw a bad draft.

The examples use offline stub agents, so they're free and give the same result every time. Point them at a real model with `AGENT_CMD="claude -p" sgl run pipeline.yaml`.

## A pipeline

```yaml
name: blog-publish
stages:
  - name: preflight            # can this run work at all?
    gates:
      - run: sgl gate preflight --cmd python3 --env API_TOKEN

  - name: draft
    run: python3 agent.py draft
    retries: 2                  # on fail, rerun this stage with the failure in $SGL_FEEDBACK
    gates:
      - name: frontmatter
        run: sgl gate frontmatter out/post.md --require title,date
      - name: no-em-dash
        run: sgl gate no-pattern out/post.md -p "\u2014"   # em dash
      - name: tests
        run: pytest -q          # any command is a gate
```

Each stage runs its command, then its gates in order. When a gate fails:

1. The line stops. Nothing downstream runs.
2. If the stage has `retries`, it runs again with the gate's output in `$SGL_FEEDBACK` (and `$SGL_ATTEMPT`), so the agent fixes the thing that broke and nothing else.
3. When retries run out, the run ends at that stage and exits 1. `sgl run pipeline.yaml --resume` picks up from the breakpoint once you've fixed it.

Every step is logged as JSON lines in `.sgl/runs/`.

## Commands

| | |
|---|---|
| `sgl run pipeline.yaml` | Run it. Exit 0 = all gates passed, 1 = stopped |
| `--resume` | Skip stages that passed in the last stopped run |
| `--from <stage>` | Start at a stage |
| `--gates-only` | Check gates only, skip stage commands (to gate work an agent already did) |
| `--json` | Machine-readable result |
| `sgl validate pipeline.yaml` | Check the file without running anything |
| `sgl gate <name> ...` | Run a built-in gate on its own |
| `sgl hook claude-code pipeline.yaml` | Claude Code `Stop` hook ([below](#claude-code)) |

## Built-in gates

All built-in gates are standard-library only, so a gate can't break because a package changed underneath it.

| Gate | Checks |
|---|---|
| `preflight --cmd X --env Y --url Z` | Tools on PATH, env vars set (values are never printed), URLs reachable |
| `schema file.json --schema s.json` | JSON matches a schema: type, required, enum, pattern, min/max, items |
| `frontmatter file.md --require a,b` | Markdown frontmatter has the keys, and they're not empty |
| `no-pattern file -p REGEX` | A banned pattern is absent: em dashes (`\u2014`), `TODO`, `print(`, filler phrases |
| `words file.md --min N --max M` | Length is within bounds |
| `exists file --min-bytes N` | The output is really there and isn't empty |
| `cap --ledger f --key k --max N --record` | At most N side effects per day (posts, emails, deploys) |

Your own gates are just commands: `pytest`, `tsc --noEmit`, `ruff check`, `gitleaks detect`, `curl -fsS https://staging/health`, or a 10-line script.

## Claude Code

Add the hook to block Claude from finishing while a gate fails. Claude gets the exact failure and keeps working:

```json
{
  "hooks": {
    "Stop": [{ "hooks": [{ "type": "command", "command": "sgl hook claude-code .sgl.yaml" }] }]
  }
}
```

The hook runs the pipeline with `--gates-only` against the working tree. On a fail, it returns `{"decision": "block", "reason": "<gate output>"}`. Claude Code limits consecutive continuations to 8 by default, so a gate that can never pass can't trap the session. A broken pipeline file never blocks either. See [`adapters/claude-code`](adapters/claude-code).

## GitHub Action

```yaml
- uses: heyytars/stage-gate-loops@main
  with:
    pipeline: .sgl.yaml
    gates-only: true    # gate a PR an agent opened
```

The job fails at the first failed gate, and the job summary shows which stage stopped and why. See [`adapters/github-action`](adapters/github-action).

## Examples

| | Shows |
|---|---|
| [`blog-publish`](examples/blog-publish) | Content loop: schema, frontmatter and style gates, retry with feedback |
| [`code-pr`](examples/code-pr) | Code loop: a failing test goes back to the agent, which fixes it |
| [`cron-report`](examples/cron-report) | Scheduled job: preflight, schema stop on bad upstream data (`BREAK=1`), daily cap before delivery |

## Does it save anything? The benchmark

[`bench/bench.py`](bench) has two modes. Be clear on what each one proves.

**`sim`** models only the control flow: N stages, a failure rate per stage, retries. It doesn't measure a model. It shows what verifying at the end costs on its own:

```
$ python bench/bench.py sim            # 4 stages × 3,000 tokens, 25% failure per attempt, 3 attempts
  strategy           mean tokens  p90 tokens   success
  end-of-run check         25927       36000     67.9%
  stage gates              15394       21000     93.8%
```

Over 20,000 seeded trials, stage gates used 59% of the tokens and finished far more often. That's because a failure costs one stage instead of the whole run. At a 10% failure rate the saving shrinks to 24%. **The more often a stage breaks, the more gates are worth.** Change the numbers with `--costs` and `--fail` to match your own loop.

**`real`** runs one example both ways with a real model and counts tokens from the API: (A) `sgl` as written, (B) every stage first, then every gate once at the end, with a full rerun on a fail. It needs the `claude` CLI, logged in:

```bash
python bench/bench.py real examples/blog-publish/pipeline.yaml --runs 10
```

We haven't published real-model numbers yet. Run it and send yours as an issue. What's in this README is what the code shows, nothing more.

## Where gates don't apply

Gates check the **structure** of the work: format, schema, tests, types, length, rules, caps. They can't tell you whether an essay is persuasive or a design is right. That stays with a reviewer, human or model. The point is that by the time review happens, every failure a machine can catch has already been caught. The reviewer spends their attention on what matters.

Good gates come from the real failures you've seen. A gate that passes everything is decoration. A gate that's too strict stalls the loop. Start with the defect your agent produces most often, and gate that.

## Background

The pattern isn't new. It's the Toyota andon cord (anyone can stop the line), test-driven development (the check exists before the work), and CI (a red build blocks the merge), applied to agent loops. Those loops mostly still verify at the end, with the same kind of model that did the work.

Read the essay: [Stage Gate Loops: Why Agent Verification Has to Move From the End to Every Transition](https://gauravsingh.net/posts/stage-gate-loops/).

## License

MIT
