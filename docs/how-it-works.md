# How stage gate loops work

No jargon. If you can read a recipe, you can read this.

## The problem in one story

Imagine a four-step order: **take the order → cook → plate → deliver.**

In the usual setup, nobody checks anything until the plate reaches the customer. If the kitchen used salt instead of sugar at step two, you still cook it, you still plate it, and you still walk it to the table. Then the customer sends it back, and you start the whole four-step order again.

That is how most AI agent loops work today. The agent does all the steps, then something at the very end checks the result. When the check fails, all the work is thrown away, and you pay for every step a second time.

## The fix in one line

**Put a check after every step, and stop the moment a check fails.**

- If step two is wrong, you find out at step two.
- Steps three and four never run, so you don't pay for them.
- The agent gets told exactly what was wrong, fixes it, and only step two runs again.

## What a "check" is

A check (we call it a **gate**) is a command that answers one question with a yes or no. Nothing about it is clever, and nothing about it is a matter of taste:

| Question | The gate |
|---|---|
| Is the data the right shape? | A schema validator |
| Does the code still work? | A test suite |
| Does the file exist and have content? | A file check |
| Is the post the right length? | A word count |
| Did we already send three emails today? | A daily cap |

A gate gives an answer of **pass** or **fail**. It is not a model giving an opinion, so nobody can argue with it. A schema validator cannot be talked into accepting broken data, and a failing test cannot be talked into passing.

## The picture

```
HAPPY PATH
  stage 1 ──▶ [gate] ──▶ stage 2 ──▶ [gate] ──▶ stage 3 ──▶ [gate] ──▶ done
              pass                   pass                   pass

A FAILURE
  stage 1 ──▶ [gate] ──▶ stage 2 ──▶ [gate] ✗ fail
              pass                   │
                                     ├─ stop the line: stage 3 never runs
                                     ├─ hand the failure back to the agent
                                     └─ run stage 2 again, with the fix

WHAT THE OLD WAY COSTS
  stage 1 ──▶ stage 2 ──▶ stage 3 ──▶ stage 4 ──▶ [check] ✗
                                                   │
                                  all four stages were paid for, twice
```

## Three words you will see

**Stage.** One step of the work, done by your agent or by a plain script. Each stage declares an optional `run` command and one or more gates.

**Gate.** The check at the end of a stage. Any command where exit code `0` means pass. `sgl` ships seven common ones, and you can use `pytest`, `curl`, `gitleaks`, or a ten-line script just as easily.

**Stop the line.** The moment a gate fails. Nothing downstream runs. This comes from the Toyota factory floor, where any worker can pull the andon cord and halt production, because a defect caught at one station is far cheaper than the same defect found by a customer.

## What actually happens on a failure

1. The stage runs, then its gates run in order.
2. The first failing gate stops everything else in that stage.
3. The run ends and exits with code 1. The log holds the exact output of the gate that failed.
4. If the stage allows retries, it runs again and the gate's output is handed to the agent as `$SGL_FEEDBACK`. The agent sees the exact failure, not a vague instruction.
5. When retries run out, `sgl` stops and tells you where. Fix it, then `sgl run pipeline.yaml --resume` carries on from that stage. Earlier stages do not repeat.

## A worked example

This is the [`code-pr`](../examples/code-pr) example, run for real:

```
sgl ▸ code-pr  (3 stages)
  [1] preflight: PASS  gates: tools
  [2] implement: FAIL at gate 'tests'  → retrying with feedback
        FAIL: test_accents (test_slug.TestSlugify)
  [2] implement: PASS (attempt 2)  gates: compiles, tests
  [3] review-ready: PASS  gates: no-debug-left
sgl ▸ ALL GATES PASSED (0.3s)
```

The agent wrote a function that handled plain text but not accented letters. The test gate caught it at stage two, handed the failing test back, and the agent fixed that one function. Stage one did not rerun, and stage three only ran once the tests were green.

## What gates cannot do

Gates check the **shape** of the work: formats, schemas, tests, lengths, rules, limits. They cannot tell you whether an essay is worth reading or whether a design looks right. That judgement stays with a human or a model reviewer.

The point is to spend human attention on the part only a human can judge. By the time a reviewer looks at the work, every problem a machine could have caught has already been caught and fixed.

## Where to go next

- [`README.md`](../README.md) for commands and pipeline syntax
- [`examples/`](../examples) for three runnable pipelines
- [`SECURITY.md`](../SECURITY.md) for the trust model
- [The essay](https://gauravsingh.net/posts/stage-gate-loops/) for why this pattern exists and where it comes from
