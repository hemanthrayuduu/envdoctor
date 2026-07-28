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

MISSING_DEPENDENCY = "missing_dependency"

# Leading distribution name in a PEP 508 requirement string.
_REQ_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


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
    """Return findings for unconditional requirements that are not installed.

    ``requirements`` is an iterable of ``(dist_name, requirement_string)`` and
    ``installed`` is the set of normalized package names present. Pure and
    deterministic — the live-metadata reading is kept separate so this logic is
    fully testable.
    """
    installed = set(installed)
    findings: List[Finding] = []
    seen = set()

    for dist_name, req in requirements:
        dep = _requirement_name(req)
        if not dep or dep in installed or dep in seen:
            continue
        seen.add(dep)
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

    findings.sort(key=lambda f: (-f.score, f.key))
    return findings


def check_environment(fingerprint: Optional[Fingerprint] = None) -> List[Finding]:
    """Inspect an environment and return ranked findings.

    When ``fingerprint`` is None the current interpreter is inspected live
    (which also lets us read dependency metadata). A passed-in fingerprint is
    used for its installed-package set only.
    """
    if fingerprint is None:
        fingerprint = Fingerprint.capture()
    return analyze_dependencies(_iter_requirements(), set(fingerprint.packages))
