# Contributing to EnvDoctor

Thanks for your interest! EnvDoctor is a small, focused, zero-dependency tool,
and it's designed to be easy to contribute to.

## Development setup

```bash
git clone https://github.com/hemanthrayuduu/envdoctor
cd envdoctor
python -m pip install -e ".[dev]"
```

## Running the checks locally

```bash
python -m pytest              # unit tests
python -m evaluation.benchmark   # ranking-quality benchmark (CI gate)
```

Both run in CI on every pull request; the benchmark blocks merges that regress
Top-1 accuracy below 90% or introduce a high-confidence false positive.

## Great first contributions

EnvDoctor's value lives in two accumulating knowledge assets — both are easy,
high-impact places to help:

1. **New fault scenarios** in `evaluation/generate.py`. More labelled cases =
   a more trustworthy ranking. Add a `Case`, give it a ground truth, and the
   benchmark will score the engine against it.
2. **New or better fixes** in `envdoctor/fixes.py`. Clearer, more actionable
   plain-English remedies directly improve the product.
3. **Real-world mined cases** under `evaluation/cases/` (see EVALUATION.md).

## Scope discipline

EnvDoctor **diagnoses** environment drift; it deliberately does not try to
*prevent* it (that's the job of lockfiles, `uv`, Docker). Please keep proposals
aligned with "capture → diff/check → rank → explain → fix." Features that share
the fingerprint and the ranking engine are welcome; a new subsystem (CVE
scanning, dependency pinning, env-var management) belongs in a different tool.

## Guidelines

- Keep the **core** (`capture`/`diff`/`check`) free of third-party runtime
  dependencies so it runs in minimal CI containers.
- Never read or emit environment-variable *values* — names only.
- Add or update tests for any behavior change.
