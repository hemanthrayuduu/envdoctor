"""The ranking engine — the core of EnvDoctor.

Given the structural differences between a working and a failing environment,
score each by how likely it is to be the *actual cause* of the failure, and
attach a plain-English fix. The scoring is a transparent, inspectable rule
system (not a black box): every score comes with a human-readable rationale,
and an optional traceback strongly boosts differences it names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from . import diff as _d
from .diff import Difference
from .fixes import fix_for
from .model import normalize_package_name
from .versions import VersionGap, version_gap

# --- confidence thresholds ------------------------------------------------
HIGH = 70
MEDIUM = 40
# Differences scoring at/below this are treated as noise and dropped by default.
NOISE_FLOOR = 5

# Env-var names that plausibly change program behavior. Matched against the
# variable NAME only (we never see values).
_CONSEQUENTIAL_ENV = re.compile(
    r"(_URL|_URI|_DSN|_TOKEN|_SECRET|_KEY|_PASSWORD|_PASS|_HOST|_PORT|_ENDPOINT|"
    r"_ACCOUNT|_REGION|_BUCKET|_CONN|_CONNECTION|API|DATABASE|REDIS|POSTGRES|MYSQL|"
    r"^AWS_|^GCP_|^GOOGLE_|^AZURE_|^PYTHON|PYTHONPATH|LD_LIBRARY_PATH|^SECRET|^CONFIG)",
    re.IGNORECASE,
)

# Obvious shell/session noise that is almost never a root cause.
_NOISE_ENV = {
    "_", "shlvl", "pwd", "oldpwd", "term", "ls_colors", "columns", "lines",
    "ps1", "ps2", "underscore", "hostname", "tmpdir", "term_program",
    "term_session_id", "colorterm", "editor", "pager", "mail",
}


@dataclass
class Cause:
    """A ranked candidate root cause with its remedy."""

    difference: Difference
    score: int
    confidence: str
    rationale: str
    fix: str
    mentioned_in_traceback: bool = False

    def to_dict(self) -> dict:
        return {
            "category": self.difference.category,
            "key": self.difference.key,
            "score": self.score,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "fix": self.fix,
            "mentioned_in_traceback": self.mentioned_in_traceback,
            "working_value": self.difference.working_value,
            "failing_value": self.difference.failing_value,
        }


def rank_causes(
    diffs: List[Difference],
    traceback_text: Optional[str] = None,
    drop_noise: bool = True,
) -> List[Cause]:
    """Score and order differences by likelihood of being the cause.

    Ties are broken deterministically by (category, key) so output is stable.
    """
    tokens = _traceback_tokens(traceback_text) if traceback_text else set()
    causes: List[Cause] = []
    for d in diffs:
        base, rationale = _base_score(d)
        mentioned = bool(tokens) and _mentioned(d.key, tokens)
        score = base
        if mentioned:
            score = min(99, base + 30)
            rationale += " Its name appears in the provided traceback, which is strong evidence."
        score = max(0, min(99, score))
        if drop_noise and score <= NOISE_FLOOR and not mentioned:
            continue
        causes.append(
            Cause(
                difference=d,
                score=score,
                confidence=_confidence(score),
                rationale=rationale,
                fix=fix_for(d),
                mentioned_in_traceback=mentioned,
            )
        )
    causes.sort(key=lambda c: (-c.score, c.difference.category, c.difference.key))
    return causes


def _confidence(score: int) -> str:
    if score >= HIGH:
        return "high"
    if score >= MEDIUM:
        return "medium"
    return "low"


def _base_score(d: Difference) -> tuple:
    """Return (score, rationale) for a difference, ignoring traceback."""
    category = d.category

    if category == _d.PACKAGE_MISSING:
        return 82, (
            "A package present where the code works is entirely absent where it "
            "fails; a missing import is the single most common CI failure."
        )

    if category == _d.VERSION_MISMATCH:
        gap = version_gap(d.working_value or "", d.failing_value or "")
        return {
            VersionGap.MAJOR: (68, "A major-version gap often includes breaking API changes."),
            VersionGap.MINOR: (42, "A minor-version gap can introduce behavior changes."),
            VersionGap.PATCH: (18, "Only a patch-level gap; usually bug fixes, rarely the cause."),
            VersionGap.UNKNOWN: (30, "Versions differ but the gap could not be classified."),
            VersionGap.NONE: (12, "Versions differ only in non-numeric metadata."),
        }[gap]

    if category == _d.PYTHON_VERSION:
        gap = version_gap(d.working_value or "", d.failing_value or "")
        base, why = {
            VersionGap.MAJOR: (90, "A major Python-version gap almost always breaks code."),
            VersionGap.MINOR: (58, "A minor Python-version gap changes stdlib/syntax behavior."),
            VersionGap.PATCH: (22, "Only a patch-level Python gap; rarely the cause."),
            VersionGap.UNKNOWN: (45, "Python versions differ by an unclear amount."),
            VersionGap.NONE: (20, "Python versions differ only in metadata."),
        }[gap]
        wi = (d.detail or {}).get("working_implementation")
        fi = (d.detail or {}).get("failing_implementation")
        if wi and fi and wi != fi:
            base = min(95, base + 15)
            why += f" Interpreter implementation also differs ({wi} vs {fi})."
        return base, why

    if category == _d.LIBC:
        values = f"{d.working_value} {d.failing_value}".lower()
        if "musl" in values:
            return 64, "glibc vs musl are binary-incompatible; many wheels are glibc-only."
        if "unknown" in values:
            return 35, "C library differs but one side is unknown; treat as a weaker signal."
        return 50, "The system C library differs, which can affect compiled extensions."

    if category == _d.PLATFORM_SYSTEM:
        return 52, "The operating system differs, which changes paths, encodings and system libs."

    if category == _d.PLATFORM_MACHINE:
        return 46, "CPU architecture differs; compiled wheels may not match the failing arch."

    if category == _d.ENV_VAR_MISSING:
        name = d.key
        if name.lower() in _NOISE_ENV:
            return 4, "A shell/session variable that is almost never a functional dependency."
        if _CONSEQUENTIAL_ENV.search(name):
            return 62, (
                "An environment variable that looks functionally significant is set "
                "where the code works but missing where it fails."
            )
        return 26, "An environment variable is missing in the failing environment."

    if category == _d.ENV_VAR_EXTRA:
        name = d.key
        if name.lower() in _NOISE_ENV:
            return 3, "An extra shell/session variable in the failing environment; almost certainly noise."
        if _CONSEQUENTIAL_ENV.search(name):
            return 22, "The failing environment sets a significant variable the working one lacks."
        return 6, "The failing environment has an extra environment variable."

    if category == _d.PACKAGE_EXTRA:
        return 12, "The failing environment has an extra package that could shadow imports or conflict."

    return 10, "Unclassified difference."


# --- traceback correlation ------------------------------------------------

def _traceback_tokens(text: str) -> set:
    tokens: set = set()
    for raw in re.findall(r"[A-Za-z0-9_.\-]+", text.lower()):
        tokens.add(raw)
        tokens.add(normalize_package_name(raw))
        tokens.add(raw.replace("-", "_"))
        tokens.add(raw.replace("_", "-"))
    return tokens


def _mentioned(key: str, tokens: set) -> bool:
    k = key.lower()
    variants = {
        k,
        normalize_package_name(k),
        k.replace("-", "_"),
        k.replace("_", "-"),
        k.replace("-", "").replace("_", ""),
    }
    return bool(variants & tokens)
