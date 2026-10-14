# EnvFixer

[![PyPI version](https://img.shields.io/pypi/v/envfixer.svg)](https://pypi.org/project/envfixer/)
[![Python versions](https://img.shields.io/pypi/pyversions/envfixer.svg)](https://pypi.org/project/envfixer/)
[![CI](https://github.com/hemanthrayuduu/envdoctor/actions/workflows/ci.yml/badge.svg)](https://github.com/hemanthrayuduu/envdoctor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Your tests pass locally. CI fails. EnvFixer tells you why.**

Instead of making you eyeball two giant `pip freeze` outputs, EnvFixer compares
the two environments, **ranks the differences by how likely each one is to be
the actual cause**, and prints a plain-English fix for each.

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

## Install

```bash
pip install envfixer
```

No dependencies, so it installs anywhere — including a minimal CI container.

## Quick start

**1. Snapshot the environment where your code works.**

```bash
envfixer capture -o local.json
```

> Run this inside the virtualenv your code actually uses, so you snapshot the
> right interpreter. If `envfixer` isn't on your `PATH`, `python -m envfixer`
> works identically (e.g. `python -m envfixer capture -o local.json`).

**2. Snapshot the environment where it breaks** — the same command, run in CI:

```bash
envfixer capture -o ci.json
```

**3. Compare them.**

```bash
envfixer diff local.json ci.json
```

> ⚠️ **Order matters: working environment first, failing one second.** That's
> how EnvFixer knows which side is broken. Swapping them inverts the diagnosis.

That's it. You get a ranked list of likely causes, each with a fix.

## What it catches

| What differs | Real example |
|--------------|--------------|
| A package is **missing** | `pydantic` is installed locally but not in CI |
| A package **version** differs | `urllib3` 1.26 locally, 2.x in CI (breaking change) |
| **Python version** differs | 3.11 locally, 3.9 in CI |
| **OS, CPU or C library** differs | glibc laptop vs Alpine (musl) container — many wheels don't work on musl |
| **Timezone** differs | your local time vs a UTC runner, so `date.today()` disagrees |
| **Text encoding** differs | UTF-8 locally, ASCII in CI → `UnicodeEncodeError` |
| An **environment variable** is missing | `DATABASE_URL` set locally, absent in CI |

## Other things you can do

### Diagnose CI without installing anything there

Got the CI logs but can't install EnvFixer in that environment? Feed it any
`pip freeze` output instead:

```bash
envfixer capture --from-freeze ci-freeze.txt --python-version 3.9.18 -o ci.json
envfixer diff local.json ci.json
```

Whatever the dump can't tell us (OS, env vars, timezone…) is marked `unknown`
and **skipped** — a partial snapshot never invents a difference that isn't real.

### Check a single environment

No second snapshot needed. Finds broken dependency chains — a package that's
missing, or installed at a version another package doesn't accept:

```bash
envfixer check
```

```text
1. [HIGH  ]  80/100 ████████████████····  version_conflict: werkzeug
      why: 'flask' requires 'werkzeug>=3.0.0', but 'werkzeug' 2.3.7 is
           installed. This dependency chain is broken.
      fix: Install a compatible version: pip install 'werkzeug>=3.0.0'. If a
           lockfile pinned 2.3.7, re-resolve it so 'flask' and 'werkzeug' agree.
```

### Point it at the traceback

If you have the error output, pass it — anything the traceback mentions gets a
big confidence boost:

```bash
envfixer diff local.json ci.json --traceback ci-error.log
```

### Fail the build on drift

EnvFixer exits non-zero when it finds a likely cause, so it works as a CI gate:

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
  with: { python-version: '3.11' }
- run: pip install envfixer
- run: envfixer capture -o ci.json
# local.json is a baseline you captured on a working machine and committed
- run: envfixer diff local.json ci.json --format markdown --fail-on high
```

A reusable composite action lives in [`.github/actions/envfixer`](.github/actions/envfixer).

## Command reference

| Command | What it does |
|---------|--------------|
| `envfixer capture [-o FILE]` | Snapshot this environment (prints to stdout by default). |
| `envfixer capture --from-freeze FILE` | Build a snapshot from a `pip freeze`/requirements dump (`-` reads stdin). |
| `envfixer diff WORKING FAILING` | Rank the likely causes of the failure. |
| `envfixer check [FILE]` | Find missing dependencies and version conflicts in one environment. |

Options for `diff` and `check`:

| Option | What it does |
|--------|--------------|
| `--format {human,json,markdown,sarif}` | `markdown` for PR comments, `sarif` for inline GitHub annotations. |
| `--fail-on {none,low,medium,high}` | Exit non-zero when a cause of at least this confidence is found (default: `high`). |
| `--top N` | Show only the top N results. |
| `--traceback FILE` | (`diff` only) Boost differences named in the error output. |

## How the ranking works

It's a **transparent rule system**, not a black box — every result tells you its
score *and* the reasoning behind it. The short version:

- A **missing package** scores highest — it's the most common real cause.
- **Version gaps** are scored by blast radius: major > minor > patch.
- **Python, libc and CPU** differences are weighted by how often they really
  break things (glibc-vs-musl is scored heavily; a patch bump isn't).
- **Timezone and encoding** drift is scored too — causes no lockfile can see.
- **Environment variables** are filtered by significance: `DATABASE_URL`,
  `*_TOKEN`, `AWS_*` matter; shell noise like `SHLVL` and `TERM` is dropped.
- **A traceback**, if you provide one, strongly boosts whatever it names.

The exact rules live in [`envfixer/rank.py`](envfixer/rank.py).

## Does the ranking actually work?

"Ranks by likely cause" is a claim that can be measured, so we measure it. A
benchmark of **23 labelled scenarios** — both injected faults and reconstructions
of real-world CI failures — scores the engine on every commit:

**Top-1 accuracy 100% · MRR 1.000 · 0 false positives**

```bash
python -m evaluation.benchmark
```

CI blocks any change that makes those numbers worse. Details and the full case
list are in **[EVALUATION.md](EVALUATION.md)**.

## Privacy

EnvFixer records environment-variable **names only — never their values**. The
snapshot is plain JSON you can read before sharing it.

## Contributing

Issues and PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Good first
contributions: add a failure scenario to `evaluation/generate.py`, or improve a
fix message in `envfixer/fixes.py`.

## License

MIT — see [LICENSE](LICENSE).
