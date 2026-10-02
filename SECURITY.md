# Security

## Reporting a problem

Please don't open a public issue for a security bug. Use GitHub's private reporting instead: **Security → Report a vulnerability** on this repo. You'll get a reply within 7 days.

## The trust model, in plain words

`sgl` runs the commands written in your pipeline file. **Treat a pipeline file like a Makefile or a CI config: only run ones you wrote or have read.** A pipeline from a stranger can run anything on your machine, in the same way a stranger's `Makefile` can.

What `sgl` protects you from, and what it doesn't:

| | |
|---|---|
| ✅ **Secrets in gate output** | Every line a gate prints is redacted before it reaches the console, the log, the agent's `$SGL_FEEDBACK` or a CI job summary. It masks the values of env vars whose names look secret (`*TOKEN*`, `*KEY*`, `*SECRET*`, `*PASSWORD*`...) and well-known token shapes (GitHub, OpenAI, Anthropic, AWS, Stripe, Slack, JWTs, private keys, `Authorization:` headers, `user:pass@` URLs) |
| ✅ **Private logs** | `.sgl/` is created owner-only (`0700`), and log files are `0600` |
| ✅ **No runaway processes** | A gate that times out is killed together with everything it started |
| ✅ **Path safety** | Pipeline names can't contain `/` or `..`, so they can't write outside `.sgl/` |
| ✅ **Real caps** | The `cap` gate locks its ledger, so ten runs fired at once still can't exceed the limit |
| ✅ **Safe URL checks** | `preflight --url` only follows `http` and `https` |
| ✅ **Hooks never trap you** | A broken pipeline file never blocks a Claude Code session |
| ❌ **Untrusted pipeline files** | Not protected, by design. See above |
| ❌ **Secrets in your own outputs** | Redaction covers what gates *print*. Files your stages write are yours to manage |

Redaction is a safety net, not a guarantee. The real rule: **don't make gates print secrets.**

## How this repo checks itself

Every push runs this repo's own stage gates ([`.sgl.yaml`](.sgl.yaml)): a gitleaks scan of the full history, bandit static analysis, the test suite, and a docs check. Third-party GitHub Actions are pinned to full commit SHAs, the gitleaks download is checksum-verified, and the workflow token is read-only. Dependabot watches dependencies and actions.
