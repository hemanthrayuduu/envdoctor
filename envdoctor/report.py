"""Output renderers and CI exit-code policy.

Renders ranked causes (from ``diff``) or findings (from ``check``) as human
text, JSON, Markdown (for PR comments) or SARIF 2.1.0 (for inline CI
annotations). Also decides the process exit code via ``--fail-on`` so
EnvDoctor works as a CI guardrail, not just a report.
"""

from __future__ import annotations

import json
from typing import List

# fail-on threshold name -> minimum score that trips a non-zero exit.
FAIL_ON_THRESHOLDS = {
    "none": 101,   # never fail
    "low": 1,      # any surfaced difference
    "medium": 40,
    "high": 70,
}

_LEVEL_BY_CONFIDENCE = {"high": "error", "medium": "warning", "low": "note"}


def _normalize(items) -> List[dict]:
    """Coerce Cause/Finding objects into a common dict shape for rendering."""
    out: List[dict] = []
    for it in items:
        d = it.to_dict() if hasattr(it, "to_dict") else dict(it)
        out.append(
            {
                "category": d.get("category", "unknown"),
                "key": d.get("key", ""),
                "score": int(d.get("score", 0)),
                "confidence": d.get("confidence", "low"),
                "summary": d.get("rationale") or d.get("message") or "",
                "fix": d.get("fix", ""),
                "working_value": d.get("working_value"),
                "failing_value": d.get("failing_value"),
                "mentioned_in_traceback": d.get("mentioned_in_traceback", False),
            }
        )
    return out


def exit_code(items, fail_on: str) -> int:
    threshold = FAIL_ON_THRESHOLDS.get(fail_on, FAIL_ON_THRESHOLDS["high"])
    for item in _normalize(items):
        if item["score"] >= threshold:
            return 1
    return 0


def _bar(score: int, width: int = 20) -> str:
    filled = round(score / 100 * width)
    return "█" * filled + "·" * (width - filled)


def render_human(items, title: str) -> str:
    rows = _normalize(items)
    lines = [f"EnvDoctor — {title}", "=" * (12 + len(title)), ""]
    if not rows:
        lines.append("No likely causes found. The environments look equivalent. ✓")
        return "\n".join(lines)
    lines.append(f"{len(rows)} candidate cause(s), most likely first:\n")
    for i, r in enumerate(rows, 1):
        flag = "  [in traceback]" if r["mentioned_in_traceback"] else ""
        lines.append(
            f"{i}. [{r['confidence'].upper():6}] {r['score']:3d}/100 "
            f"{_bar(r['score'])}  {r['category']}: {r['key']}{flag}"
        )
        if r["working_value"] is not None or r["failing_value"] is not None:
            lines.append(
                f"      working: {r['working_value']!r}   failing: {r['failing_value']!r}"
            )
        lines.append(f"      why: {r['summary']}")
        lines.append(f"      fix: {r['fix']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_json(items, title: str) -> str:
    rows = _normalize(items)
    return json.dumps({"title": title, "causes": rows}, indent=2)


def render_markdown(items, title: str) -> str:
    rows = _normalize(items)
    lines = [f"### EnvDoctor — {title}", ""]
    if not rows:
        lines.append("No likely causes found — the environments look equivalent. ✓")
        return "\n".join(lines) + "\n"
    lines.append("| # | Confidence | Score | Category | Key | Fix |")
    lines.append("|---|-----------|-------|----------|-----|-----|")
    for i, r in enumerate(rows, 1):
        fix = r["fix"].replace("|", "\\|")
        lines.append(
            f"| {i} | {r['confidence']} | {r['score']} | {r['category']} | "
            f"`{r['key']}` | {fix} |"
        )
    return "\n".join(lines) + "\n"


def render_sarif(items, title: str) -> str:
    rows = _normalize(items)
    rules = {}
    results = []
    for r in rows:
        rules.setdefault(
            r["category"],
            {
                "id": r["category"],
                "name": r["category"],
                "shortDescription": {"text": r["category"].replace("_", " ")},
            },
        )
        results.append(
            {
                "ruleId": r["category"],
                "level": _LEVEL_BY_CONFIDENCE.get(r["confidence"], "note"),
                "message": {"text": f"{r['key']}: {r['summary']} Fix: {r['fix']}"},
                "properties": {"score": r["score"], "key": r["key"]},
            }
        )
    sarif = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "EnvDoctor",
                        "informationUri": "https://github.com/hemanthrayuduu/envdoctor",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(sarif, indent=2)


RENDERERS = {
    "human": render_human,
    "json": render_json,
    "markdown": render_markdown,
    "sarif": render_sarif,
}


def render(items, title: str, fmt: str) -> str:
    renderer = RENDERERS.get(fmt, render_human)
    return renderer(items, title)
