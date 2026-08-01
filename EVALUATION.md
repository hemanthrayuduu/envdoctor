# Evaluation

EnvFixer's central claim is that it **ranks environment differences by how
likely each is to be the actual cause** of a failure. That is an empirical
claim, so it is measured — not asserted — and the measurement gates CI.

## The benchmark corpus

`evaluation/generate.py` is a **synthetic fault injector**. Starting from one
realistic base environment, each scenario injects exactly one *known* fault
(optionally buried under noise) and records the ground-truth cause:

| Scenario | Injected fault | Ground truth |
|----------|----------------|--------------|
| `missing_package` | remove a package | `package_missing` |
| `major/minor/patch_version_mismatch` | bump a version | `version_mismatch` |
| `missing_env_var` | drop `DATABASE_URL` | `env_var_missing` |
| `python_minor_mismatch` | change Python 3.11 → 3.9 | `python_version` |
| `libc_musl` | glibc → musl | `libc` |
| `arch_mismatch` | x86_64 → aarch64 | `platform_machine` |
| `timezone_drift` | local timezone → UTC | `timezone` |
| `locale_ascii_drift` | UTF-8 → ASCII locale | `locale` |
| `partial_freeze_fingerprint` | failing side synthesized from a freeze dump | the real missing package |
| `*_with_noise` | true cause + patch bumps + shell-var churn | the true cause |
| `*_with_traceback` | missing package + matching traceback | `package_missing` |
| `pure_noise` | only shell-var / patch noise | **none** (must not flag) |

The same generator produces both the unit-test fixtures and the benchmark
corpus, which keeps the ranking honest: it is scored against faults whose true
cause we control.

## Metrics

`evaluation/benchmark.py` reports:

- **Top-1 accuracy** — the true cause is ranked #1 (headline number).
- **Top-3 accuracy** — the true cause is in the top 3 (what matters when a
  human triages).
- **MRR** (mean reciprocal rank) — rewards ranking the truth high.
- **False positives** — pure-noise scenarios that wrongly produce a
  high-confidence cause. A tool that cries wolf gets uninstalled, so this must
  stay at **0**.

## Running it

```bash
python -m evaluation.benchmark
```

## CI gate

The benchmark exits non-zero if **Top-1 accuracy drops below 90%** or **any
noise case yields a high-confidence false positive**. It runs on every push and
pull request (see `.github/workflows/ci.yml`), so a change that degrades the
ranking cannot merge.

## Real-world corpus

Alongside the synthetic generator, `evaluation/cases/*.json` holds curated
scenarios distilled from well-documented, real-world "works locally, fails in
CI" failures. Each file names the ground-truth cause and cites an authoritative
reference for the underlying breakage:

| Case | Drift | Ground truth | Reference |
|------|-------|--------------|-----------|
| `01_missing_test_plugin` | `pytest-mock` not in CI requirements | `package_missing` | pytest-mock docs |
| `02_urllib3_v2_major_bump` | urllib3 1.26 → 2.x removed APIs | `version_mismatch` | urllib3 v2 migration guide |
| `03_python312_removed_distutils` | Python 3.11 → 3.12 dropped `distutils` | `python_version` | Python 3.12 "What's New" |
| `04_alpine_musl_wheel` | glibc → musl (Alpine) wheel gap | `libc` | PEP 656 (musllinux) |
| `05_missing_secret_key_env` | Django `SECRET_KEY` unset in CI | `env_var_missing` | Django settings docs |
| `06_arch_mismatch_arm64` | arm64 ↔ x86_64 wheel gap | `platform_machine` | pypa/manylinux |
| `07_numpy2_abi_break` | numpy 1.26 → 2.0 C-ABI break | `version_mismatch` | NumPy 2.0 migration guide |
| `08_utc_timezone_date_test` | laptop timezone vs UTC CI runner | `timezone` | datetime docs (local-time dependence) |
| `09_ascii_locale_unicode_error` | UTF-8 → C/POSIX ASCII locale | `locale` | PEP 540 (UTF-8 mode) |

Case files use a compact `base` + `working`/`failing` override format (a package
mapped to `null` models "present locally, absent in CI"); see
`evaluation/cases_loader.py`. These are *representative* reconstructions of
common failures, not scraped verbatim, so they can be shared freely.

## Current results

Both corpora are scored on every push/PR. On the current corpus (14 synthetic +
9 real-world = **23 labelled cases**, 1 noise case):

- **Top-1 accuracy: 100%** &nbsp;·&nbsp; **Top-3: 100%** &nbsp;·&nbsp; **MRR: 1.000** &nbsp;·&nbsp; **0 false positives**

## Contributing more cases

Adding a case is a great first contribution: drop a JSON file in
`evaluation/cases/` with a `base`, `working`/`failing` overrides, a
`ground_truth`, and a `source`. The benchmark will pick it up automatically and
score the engine against it.
