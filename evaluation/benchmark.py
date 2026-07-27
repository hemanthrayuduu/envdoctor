"""Benchmark the ranking engine against the labelled corpus.

Metrics
-------
* **Top-1 accuracy** — the true cause is ranked #1 (the headline number).
* **Top-3 accuracy** — the true cause is in the top 3 (what matters when a
  human is triaging).
* **MRR** — mean reciprocal rank; rewards ranking the truth high.
* **False positives** — pure-noise scenarios that wrongly produce a
  high-confidence cause (a tool that cries wolf gets uninstalled).

Run as a module to print the report and gate CI:
    python -m evaluation.benchmark
Exits non-zero if Top-1 accuracy regresses below ``MIN_TOP1`` or any noise
case yields a high-confidence false positive.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import List, Optional

from envdoctor.diff import diff_fingerprints
from envdoctor.rank import rank_causes

from .cases_loader import load_real_world_cases
from .generate import Case, generate_cases

MIN_TOP1 = 0.90
MAX_FALSE_POSITIVES = 0


@dataclass
class Metrics:
    top1: float
    top3: float
    mrr: float
    false_positives: int
    total_labelled: int
    total_noise: int


def _rank_position(case: Case) -> Optional[int]:
    """1-based rank of the ground-truth cause, or None if absent."""
    diffs = diff_fingerprints(case.working, case.failing)
    causes = rank_causes(diffs, traceback_text=case.traceback)
    for index, cause in enumerate(causes, 1):
        if (cause.difference.category, cause.difference.key) == case.ground_truth:
            return index
    return None


def _has_high_confidence(case: Case) -> bool:
    diffs = diff_fingerprints(case.working, case.failing)
    causes = rank_causes(diffs, traceback_text=case.traceback)
    return any(c.confidence == "high" for c in causes)


def evaluate(cases: Optional[List[Case]] = None) -> Metrics:
    cases = cases if cases is not None else generate_cases()
    labelled = [c for c in cases if c.ground_truth is not None]
    noise = [c for c in cases if c.ground_truth is None]

    top1 = top3 = 0
    reciprocal_sum = 0.0
    for case in labelled:
        pos = _rank_position(case)
        if pos is not None:
            reciprocal_sum += 1.0 / pos
            if pos == 1:
                top1 += 1
            if pos <= 3:
                top3 += 1

    false_positives = sum(1 for case in noise if _has_high_confidence(case))
    n = len(labelled) or 1
    return Metrics(
        top1=top1 / n,
        top3=top3 / n,
        mrr=reciprocal_sum / n,
        false_positives=false_positives,
        total_labelled=len(labelled),
        total_noise=len(noise),
    )


def _report(metrics: Metrics, cases: List[Case]) -> str:
    lines = ["EnvDoctor ranking benchmark", "=" * 27, ""]
    for case in cases:
        if case.ground_truth is None:
            fp = _has_high_confidence(case)
            status = "FAIL (high-confidence false positive)" if fp else "ok (no false positive)"
            lines.append(f"  [noise]    {case.name:32} {status}")
        else:
            pos = _rank_position(case)
            status = f"rank #{pos}" if pos else "NOT FOUND"
            flag = "" if pos == 1 else "  <-- not top-1" if pos else "  <-- MISSED"
            lines.append(f"  [labelled] {case.name:32} {status}{flag}")
    lines += [
        "",
        f"Top-1 accuracy : {metrics.top1:.0%}  ({metrics.total_labelled} labelled cases)",
        f"Top-3 accuracy : {metrics.top3:.0%}",
        f"MRR            : {metrics.mrr:.3f}",
        f"False positives: {metrics.false_positives}  ({metrics.total_noise} noise cases)",
    ]
    return "\n".join(lines)


def _section(title: str, cases: List[Case]) -> Metrics:
    metrics = evaluate(cases)
    print(_report(metrics, cases).replace("EnvDoctor ranking benchmark", title, 1))
    print()
    return metrics


def main() -> int:
    synthetic = generate_cases()
    real_world = load_real_world_cases()

    _section("Synthetic corpus", synthetic)
    if real_world:
        _section("Real-world corpus", real_world)

    combined = synthetic + real_world
    metrics = evaluate(combined)
    print("Combined")
    print("=" * 8)
    print(f"Top-1 accuracy : {metrics.top1:.0%}  ({metrics.total_labelled} labelled cases)")
    print(f"Top-3 accuracy : {metrics.top3:.0%}")
    print(f"MRR            : {metrics.mrr:.3f}")
    print(f"False positives: {metrics.false_positives}  ({metrics.total_noise} noise cases)")
    print()

    ok = metrics.top1 >= MIN_TOP1 and metrics.false_positives <= MAX_FALSE_POSITIVES
    if ok:
        print(f"PASS (Top-1 >= {MIN_TOP1:.0%}, false positives <= {MAX_FALSE_POSITIVES})")
        return 0
    print(f"FAIL (require Top-1 >= {MIN_TOP1:.0%} and <= {MAX_FALSE_POSITIVES} false positives)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
