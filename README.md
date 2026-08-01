# EnvFixer

[![PyPI version](https://img.shields.io/pypi/v/envfixer.svg)](https://pypi.org/project/envfixer/)
[![Python versions](https://img.shields.io/pypi/pyversions/envfixer.svg)](https://pypi.org/project/envfixer/)
[![CI](https://github.com/hemanthrayuduu/envdoctor/actions/workflows/ci.yml/badge.svg)](https://github.com/hemanthrayuduu/envdoctor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Root-cause diagnosis for "passes locally, fails in CI."**

EnvFixer captures a privacy-safe fingerprint of a Python environment
(interpreter, OS/arch/libc, installed packages, and environment-variable
*names*), compares two of them, and **ranks the most likely cause** of an
environment-drift failure — then prints a plain-English fix for each.

Every other tool in this space stops at "here's the diff." EnvFixer tells you
**which difference is probably the cause, and how to fix it.**

```text
$ envfixer diff local.json ci.json

EnvFixer — diagnosis
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
pip install envfixer
```

## Quick start

Capture a fingerprint **inside the environment you want to snapshot** (run it in
the target virtualenv, e.g. `python -m envfixer capture`, so you fingerprint
the right interpreter):

```bash
# on your machine
python -m envfixer capture -o local.json

# in CI
python -m envfixer capture -o ci.json
```

Diagnose the difference (first argument = where it **works**, second = where it
**fails**):

```bash
envfixer diff local.json ci.json
```

Have the failing traceback? Pass it — differences it names are boosted to
near-certainty:

```bash
envfixer diff local.json ci.json --traceback ci-error.log
```

Health-check a single environment (no second fingerprint needed) — finds
missing dependencies *and* version conflicts, each with a fix:

```bash
envfixer check
```

**No EnvFixer in the failing environment?** Diagnose it from its logs. Any
`pip freeze` output works as an input, so you never have to install anything in
the broken container:

```bash
envfixer capture --from-freeze ci-freeze.txt --python-version 3.9.18 -o ci.json
envfixer diff local.json ci.json
```

Anything the dump cannot tell us (OS, env vars, timezone…) stays `unknown` and
is **skipped** when diffing — a partial fingerprint never invents a difference.

## Commands

| Command | What it does |
|---------|--------------|
| `capture [-o FILE]` | Write this environment's fingerprint (stdout by default). |
| `capture --from-freeze FILE` | Build a fingerprint from a `pip freeze`/requirements dump (`-` = stdin). |
| `diff WORKING FAILING [--traceback FILE]` | Rank the likely causes of the failure. |
| `check [FINGERPRINT]` | Surface missing dependencies and version conflicts in one environment. |

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
- run: pip install envfixer
- run: envfixer capture -o ci.json
# compare against a committed baseline captured locally
- run: envfixer diff local.json ci.json --format markdown --fail-on high
```

A reusable composite action lives in [`.github/actions/envfixer`](.github/actions/envfixer).

## How the ranking works

The ranking is a **transparent rule system**, not a black box — every score
comes with a human-readable rationale. In brief:

- **Missing package** (present where it works, absent where it fails) scores
  highest — it's the most common real cause.
- **Version mismatches** are scored by blast radius (major > minor > patch).
- **Python / libc / arch** differences are scored by how often they actually
  break code (e.g. glibc-vs-musl is weighted heavily).
- **Timezone and locale/encoding** drift is scored too — the UTC-CI date bug
  and the ASCII-locale `UnicodeEncodeError` are real causes no lockfile sees.
- **Env-var names** are filtered by significance: `DATABASE_URL`, `*_TOKEN`,
  `AWS_*`, `PYTHONPATH` score high; shell noise like `SHLVL`/`TERM` is dropped.
- **A provided traceback** strongly boosts any difference it names.

See [`envfixer/rank.py`](envfixer/rank.py) for the exact rules.

## Evaluation

Because "ranks by likely cause" is an empirical claim, EnvFixer ships a
benchmark that measures it against both a synthetic fault injector and a curated
**real-world** corpus (missing test plugins, urllib3 v2, Python 3.12 dropping
`distutils`, Alpine/musl wheel gaps, NumPy 2.0 ABI breaks, UTC timezone drift,
ASCII-locale encoding errors, …). On the current
corpus (23 labelled cases): **Top-1 100%, MRR 1.000, 0 false positives.** See
**[EVALUATION.md](EVALUATION.md)**.

```bash
python -m evaluation.benchmark
```

## Privacy

EnvFixer **never** reads environment-variable *values*, only their names. The
fingerprint is human-readable JSON; inspect it before sharing.

## Contributing

Issues and PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Good first
contributions: new fault scenarios in `evaluation/generate.py` and new remedies
in `envfixer/fixes.py`.

## License

MIT — see [LICENSE](LICENSE).
