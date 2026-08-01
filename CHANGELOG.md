# Changelog

All notable changes to EnvFixer are documented here. This project follows
[semantic versioning](https://semver.org/).

## [0.2.0] - 2026-07-29

### Added

- **Diagnose from logs alone — `capture --from-freeze FILE`** (`-` reads stdin).
  Builds a fingerprint from any `pip freeze` / requirements dump, so you can
  diagnose a CI failure without installing EnvFixer in the broken environment.
  Optional `--python-version`, `--platform-system`, `--platform-machine` and
  `--libc` fill in what the dump cannot know.
- **Version-conflict detection in `check`.** Beyond "dependency not installed",
  `check` now reports a dependency installed at a version that *violates* a
  requirement (e.g. `flask` needs `werkzeug>=3.0.0` but 2.3.7 is present) — a
  `pip check` superset that also prints a plain-English fix.
- **Timezone and locale/encoding in the fingerprint**, with ranking and fixes.
  These catch two classic drift causes that lockfiles cannot see: the UTC-CI
  date-boundary bug and the ASCII-locale `UnicodeEncodeError`.
- Zero-dependency PEP 440 specifier evaluation (`envfixer.versions.satisfies`),
  which deliberately answers "unknown" rather than guessing on pre-release or
  unparseable specifiers.

### Changed

- Fingerprint schema is now **version 2**. Schema v1 files still load; fields
  they lack are treated as unknown.
- **Unknown fields are skipped when diffing.** A partial fingerprint can no
  longer manufacture a difference out of data it never had.
- Packages that `pip freeze` conventionally omits (`pip`, `setuptools`,
  `wheel`, `distribute`, `pkg-resources`) are ignored when either side came
  from a freeze dump, and EnvFixer never reports *itself* as a cause. Between
  two live captures these are still compared normally.

### Evaluation

- Corpus grown to **23 labelled cases** (14 synthetic + 9 real-world), adding
  timezone drift, ASCII-locale drift, a partial-fingerprint scenario, and two
  real-world cases. Still **Top-1 100% · MRR 1.000 · 0 false positives**.
- 72 unit tests (up from 49).

## [0.1.0] - 2026-07-28

Initial release.

- `capture`, `diff` and `check` commands; human / JSON / Markdown / SARIF output.
- Transparent ranking engine with plain-English fixes and `--fail-on` exit codes.
- Traceback correlation; privacy-safe fingerprints (env-var names only).
- Zero runtime dependencies; evaluation benchmark gating CI.
