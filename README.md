# EnvDoctor

**Root-cause diagnosis for "passes locally, fails in CI."**

EnvDoctor captures a privacy-safe fingerprint of a Python environment
(interpreter, OS/arch/libc, installed packages, and environment-variable
*names*), compares two of them, and **ranks the most likely cause** of an
environment-drift failure — then prints a plain-English fix for each.

Every other tool in this space stops at "here's the diff." EnvDoctor tells you
**which difference is probably the cause, and how to fix it.**

```text
$ envdoctor diff local.json ci.json

EnvDoctor — diagnosis
=====================

3 candidate cause(s), most likely first:

1. [HIGH  ]  82/100 ████████████████····  package_missing: pydantic
      working: '2.4.2'   failing: None
      why: A package present where the code works is entirely absent where it
           fails; a missing import is the single most common CI failure.
      fix: Install 'pydantic' in the failing environment — add
           'pydantic==2.4.2' to your requirements/lockfile so CI installs it.

2. [MEDIUM]  58/100 ████████████········  python_version: python
      working: '3.11.5'   failing: '3.9.18'
      ...
```

- **Zero runtime dependencies.** The core is pure standard library, so it runs
  inside any minimal CI container.
- **Privacy-safe by construction.** It records environment-variable *names*
  only — never values. The fingerprint is plain JSON you can eyeball.
- **A CI guardrail, not just a report.** Exit codes and `--fail-on` let it gate
  a build when environment drift is the likely culprit.

## Install

```bash
pip install envdoctor      # once published to PyPI
```

## Quick start

Capture a fingerprint **inside the environment you want to snapshot** (run it in
the target virtualenv, e.g. `python -m envdoctor capture`, so you fingerprint
the right interpreter):

```bash
# on your machine
python -m envdoctor capture -o local.json

# in CI
python -m envdoctor capture -o ci.json
```

Diagnose the difference (first argument = where it **works**, second = where it
**fails**):

```bash
envdoctor diff local.json ci.json
```

Have the failing traceback? Pass it — differences it names are boosted to
near-certainty:

```bash
envdoctor diff local.json ci.json --traceback ci-error.log
```

Health-check a single environment (no second fingerprint needed):

```bash
envdoctor check
```

## Commands

| Command | What it does |
|---------|--------------|
| `capture [-o FILE]` | Write this environment's fingerprint (stdout by default). |
| `diff WORKING FAILING [--traceback FILE]` | Rank the likely causes of the failure. |
| `check [FINGERPRINT]` | Surface broken dependency chains in one environment. |

Shared reporting flags on `diff`/`check`:

- `--format {human,json,markdown,sarif}` — `markdown` for PR comments, `sarif`
  for inline GitHub code-scanning annotations.
- `--fail-on {none,low,medium,high}` — exit non-zero when a cause of at least
  this confidence is found (default `high`).
- `--top N` — show only the top N results.

## Use in CI (GitHub Actions)

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
  with: { python-version: '3.11' }
- run: pip install -e . && pip install envdoctor
- run: python -m envdoctor capture -o ci.json
# compare against a committed baseline captured locally
- run: envdoctor diff local.json ci.json --format markdown --fail-on high
```

A reusable composite action lives in [`.github/actions/envdoctor`](.github/actions/envdoctor).

## How the ranking works

The ranking is a **transparent rule system**, not a black box — every score
comes with a human-readable rationale. In brief:

- **Missing package** (present where it works, absent where it fails) scores
  highest — it's the most common real cause.
- **Version mismatches** are scored by blast radius (major > minor > patch).
- **Python / libc / arch** differences are scored by how often they actually
  break code (e.g. glibc-vs-musl is weighted heavily).
- **Env-var names** are filtered by significance: `DATABASE_URL`, `*_TOKEN`,
  `AWS_*`, `PYTHONPATH` score high; shell noise like `SHLVL`/`TERM` is dropped.
- **A provided traceback** strongly boosts any difference it names.

See [`envdoctor/rank.py`](envdoctor/rank.py) for the exact rules.

## Evaluation

Because "ranks by likely cause" is an empirical claim, EnvDoctor ships a
benchmark that measures it. See **[EVALUATION.md](EVALUATION.md)**.

```bash
python -m evaluation.benchmark
```

## Privacy

EnvDoctor **never** reads environment-variable *values*, only their names. The
fingerprint is human-readable JSON; inspect it before sharing.

## Contributing

Issues and PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Good first
contributions: new fault scenarios in `evaluation/generate.py` and new remedies
in `envdoctor/fixes.py`.

## License

MIT — see [LICENSE](LICENSE).
