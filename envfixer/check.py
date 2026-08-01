"""Single-environment health check.

``diff`` needs two fingerprints; ``check`` gives value from *one*. It reuses
the same "rank + explain + fix" spine to surface problems in the current
environment — chiefly broken dependency chains (a package that requires
another which isn't installed), the same class of issue ``pip check`` finds,
but reported with a plain-English fix.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .model import Fingerprint, normalize_package_name
from .versions import satisfies

MISSING_DEPENDENCY = "missing_dependency"
VERSION_CONFLICT = "version_conflict"

# Leading distribution name in a PEP 508 requirement string.
_REQ_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
# Everything after the name (and optional extras): the version specifier set.
_REQ_SPEC_RE = re.compile(
    r"^\s*[A-Za-z0-9][A-Za-z0-9._-]*\s*(?:\[[^\]]*\])?\s*(.*)$"
)


def _requirement_specifier(requirement: str) -> str:
    """Return the version specifier set from a requirement, or ``''``."""
    match = _REQ_SPEC_RE.match(requirement)
    if not match:
        return ""
    spec = match.group(1).split(";")[0].strip()
    if spec.startswith("(") and spec.endswith(")"):
        spec = spec[1:-1].strip()
    # "name @ https://..." style direct references carry no comparable version.
    return "" if spec.startswith("@") else spec


@dataclass
class Finding:
    """A problem detected in a single environment."""

    category: str
    key: str
    score: int
    confidence: str
    message: str
    fix: str
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "key": self.key,
            "score": self.score,
            "confidence": self.confidence,
            "message": self.message,
            "fix": self.fix,
            "detail": dict(self.detail),
        }


def _requirement_name(requirement: str) -> Optional[str]:
    match = _REQ_NAME_RE.match(requirement)
    return normalize_package_name(match.group(1)) if match else None


def _iter_requirements():
    """Yield (dist_name, requirement_string) for unconditional requirements.

    Requirements carrying an environment marker (``; python_version < ...``) or
    an extra (``; extra == ...``) are skipped: they are conditional, so a
    missing target is not necessarily a broken environment.
    """
    from importlib import metadata

    for dist in metadata.distributions():
        name = dist.metadata["Name"] if dist.metadata else None
        if not name:
            continue
        for req in dist.requires or []:
            if ";" in req:  # has a marker/extra -> conditional, skip
                continue
            yield normalize_package_name(name), req


def analyze_dependencies(requirements, installed) -> List[Finding]:
    """Return findings for broken dependency chains in one environment.

    Two problems are detected:

    * **missing dependency** — a package is required but not installed at all;
    * **version conflict** — it *is* installed, but at a version that violates
      the requirement (e.g. ``flask`` needs ``werkzeug>=3`` and 2.3.7 is here).

    ``requirements`` is an iterable of ``(dist_name, requirement_string)``.
    ``installed`` may be a set of names (missing-only checking) or a mapping of
    ``{name: version}``, which additionally enables conflict detection. Pure and
    deterministic — live-metadata reading is kept separate so this is testable.
    """
    versions = dict(installed) if isinstance(installed, dict) else {}
    present = set(installed)
    findings: List[Finding] = []
    seen_missing = set()
    seen_conflict = set()

    for dist_name, req in requirements:
        dep = _requirement_name(req)
        if not dep:
            continue

        if dep not in present:
            if dep in seen_missing:
                continue
            seen_missing.add(dep)
            findings.append(
                Finding(
                    category=MISSING_DEPENDENCY,
                    key=dep,
                    score=75,
                    confidence="high",
                    message=(
                        f"'{dist_name}' requires '{dep}', but '{dep}' is not installed "
                        f"in this environment. Imports from '{dist_name}' may fail at runtime."
                    ),
                    fix=(
                        f"Install the missing dependency: pip install '{dep}'. If you use "
                        f"a lockfile, re-resolve it so '{dep}' is captured."
                    ),
                    detail={"required_by": dist_name, "requirement": req},
                )
            )
            continue

        # Installed — does its version actually satisfy the requirement?
        specifier = _requirement_specifier(req)
        installed_version = versions.get(dep)
        if not specifier or not installed_version:
            continue
        # ``None`` means we could not decide confidently; never guess.
        if satisfies(installed_version, specifier) is not False:
            continue
        marker = (dist_name, dep)
        if marker in seen_conflict:
            continue
        seen_conflict.add(marker)
        findings.append(
            Finding(
                category=VERSION_CONFLICT,
                key=dep,
                score=80,
                confidence="high",
                message=(
                    f"'{dist_name}' requires '{dep}{specifier}', but "
                    f"'{dep}' {installed_version} is installed. This dependency "
                    f"chain is broken and can fail at import or call time."
                ),
                fix=(
                    f"Install a compatible version: pip install '{dep}{specifier}'. "
                    f"If a lockfile pinned {installed_version}, re-resolve it so "
                    f"'{dist_name}' and '{dep}' agree."
                ),
                detail={
                    "required_by": dist_name,
                    "requirement": req,
                    "installed_version": installed_version,
                    "specifier": specifier,
                },
            )
        )

    findings.sort(key=lambda f: (-f.score, f.category, f.key))
    return findings


def check_environment(fingerprint: Optional[Fingerprint] = None) -> List[Finding]:
    """Inspect an environment and return ranked findings.

    When ``fingerprint`` is None the current interpreter is inspected live
    (which also lets us read dependency metadata). A passed-in fingerprint is
    used for its installed-package set only.
    """
    if fingerprint is None:
        fingerprint = Fingerprint.capture()
    # Pass the {name: version} mapping so version conflicts are detected too.
    return analyze_dependencies(_iter_requirements(), dict(fingerprint.packages))
