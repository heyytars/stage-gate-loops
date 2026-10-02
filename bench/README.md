# Benchmark: does verifying at the gate actually save anything?

Two modes. Be clear on which one you are reading.

## `sim` models the control flow only

```bash
python bench/bench.py sim
python bench/bench.py sim --costs 2000,4000,4000,2000 --fail 0.05,0.4,0.2,0.05
```

It does **not** measure a model. It answers one narrow question: if a stage fails at a given rate, what does it cost to verify at the gate instead of at the end?

Assumptions, all printed when you run it:

| Assumption | Default |
|---|---|
| Stages | 4 |
| Tokens per stage run | 3,000 each |
| Chance a stage fails on an attempt | 25% |
| Attempts allowed | 3 |
| Trials | 20,000, seeded (reproducible) |
| Strategy A | Run every stage, check once at the end, rerun the whole pipeline on a fail |
| Strategy B | Each stage ends at a gate, only the failed stage reruns |

Published result (seed 7):

| Strategy | Mean tokens | 90th percentile | Runs that finished |
|---|---|---|---|
| End-of-run check | 25,927 | 36,000 | 67.9% |
| Stage gates | 15,394 | 21,000 | 93.8% |

Stage gates used **59%** of the tokens. At a 10% failure rate the saving shrinks to **24%**. The mechanism is simple: a failure costs one stage instead of the whole run, so the more often your stages break, the more gates are worth.

Two things this model does not capture, both of which favour the end-of-run strategy, so the real gap should be wider:

1. It gives the end-of-run check a perfect reviewer. It assumes the final check always catches what a gate would catch. In practice a model reviewing its own pipeline's output misses some of them.
2. It charges nothing for the time a human spends reading a failure that a gate could have described precisely.

## `real` runs a real model and meters the tokens

```bash
python bench/bench.py real examples/blog-publish/pipeline.yaml --runs 10
python bench/bench.py real examples/blog-publish/pipeline.yaml --runs 10 --model haiku
```

It runs the same pipeline both ways, with a real agent, and counts tokens from the API:

- **A, stage gates:** `sgl` as written. A failure retries only that stage.
- **B, end-of-run check:** run every stage command, then every gate once at the end. Any failure reruns the whole pipeline, with the gate output handed back as feedback.

Token counts come from `bench/meter.py`, which wraps `claude -p --output-format json` and appends the usage record to a ledger. It needs the Claude Code CLI, logged in.

Use `--agent-cmd stub` to check the harness itself without a model. That runs the offline stub agents, so it reports 0 tokens and proves the plumbing rather than the economics.

**No real-model numbers are published yet.** The maintainer's CLIs were not logged in when this was written, and inventing plausible figures would defeat the point. Run it and open an issue with your numbers.

## Files

| File | |
|---|---|
| `bench.py` | Both modes |
| `meter.py` | Metered agent wrapper: prints the answer, logs the token usage |
| `results-sim.json` | A saved `sim` run, for the README chart |
