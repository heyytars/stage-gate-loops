# GitHub Action

Runs an `sgl` pipeline in CI. The job fails at the first failed gate, and the job summary shows the stage that stopped and the gate output.

```yaml
# .github/workflows/gates.yml
name: gates
on: [pull_request]
jobs:
  gates:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - uses: heyytars/stage-gate-loops@main
        id: sgl
        with:
          pipeline: .sgl.yaml
          gates-only: true
```

| Input | Default | |
|---|---|---|
| `pipeline` | (required) | Path to the pipeline YAML |
| `gates-only` | `false` | Skip stage commands and only check gates. Use this to gate a PR an agent opened |
| `version` | `main` | sgl git ref to install. Pin a tag for reproducible CI |

| Output | |
|---|---|
| `ok` | `true` if every gate passed |
| `stopped-at` | The stage that stopped the line |

Use `steps.sgl.outputs.stopped-at` to route the failure: comment on the PR, label it, or hand it back to the agent that opened it.
