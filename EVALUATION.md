# Evaluation

EnvDoctor's central claim is that it **ranks environment differences by how
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

## Roadmap for the corpus

The synthetic corpus proves the engine against controlled faults. The next step
toward real-world fidelity is a curated set of mined "works locally, fails in
CI" cases (from public issues/Q&A where the accepted answer names the cause)
under `evaluation/cases/`. Contributions there are especially welcome.
