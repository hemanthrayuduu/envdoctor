"""Lightweight, dependency-free version parsing.

We deliberately avoid a hard dependency on ``packaging`` in the core so the
capture/diff path stays zero-dependency. This is a pragmatic PEP 440 subset:
it extracts the numeric release segment (``1.2.3``) which is all the ranking
engine needs to reason about the *magnitude* of a version gap. Anything it
cannot parse degrades gracefully to an "unknown" gap rather than crashing.
"""

from __future__ import annotations

import re
from enum import IntEnum
from typing import List, Optional, Tuple

_RELEASE_RE = re.compile(r"(\d+(?:\.\d+)*)")


class VersionGap(IntEnum):
    """How far apart two versions are, ordered by blast radius."""

    NONE = 0
    PATCH = 1
    MINOR = 2
    MAJOR = 3
    UNKNOWN = 4  # could not parse one/both sides


def parse_release(version: str) -> Optional[Tuple[int, ...]]:
    """Return the numeric release tuple, or ``None`` if unparseable."""
    if not version:
        return None
    match = _RELEASE_RE.search(str(version))
    if not match:
        return None
    try:
        return tuple(int(p) for p in match.group(1).split("."))
    except ValueError:  # pragma: no cover - defensive
        return None


def _pad(a: Tuple[int, ...], b: Tuple[int, ...]) -> Tuple[List[int], List[int]]:
    width = max(len(a), len(b))
    return (
        list(a) + [0] * (width - len(a)),
        list(b) + [0] * (width - len(b)),
    )


def compare_releases(left: str, right: str) -> Optional[int]:
    """Compare two versions by release segment: -1, 0, 1 — or None if unknown."""
    a = parse_release(left)
    b = parse_release(right)
    if a is None or b is None:
        return None
    pa, pb = _pad(a, b)
    if pa < pb:
        return -1
    return 0 if pa == pb else 1


# Pre-release / dev markers. We deliberately refuse to reason about these
# (returning "unknown") rather than risk a wrong verdict on an edge case.
_PRERELEASE_RE = re.compile(r"(?i)(?:a|b|c|rc|alpha|beta|pre|dev)\d", re.IGNORECASE)

_SPEC_RE = re.compile(r"^\s*(===|==|!=|~=|>=|<=|>|<)\s*(.+?)\s*$")


def _is_prerelease(version: str) -> bool:
    return bool(_PRERELEASE_RE.search(version or ""))


def _satisfies_one(version: str, operator: str, bound: str) -> Optional[bool]:
    if operator == "===":  # arbitrary equality: exact string match
        return version.strip() == bound.strip()

    wildcard = bound.endswith(".*")
    if wildcard:
        if operator not in ("==", "!="):
            return None  # wildcards are only defined for == and !=
        prefix = parse_release(bound[:-2])
        actual = parse_release(version)
        if prefix is None or actual is None:
            return None
        matched = actual[: len(prefix)] == prefix
        return matched if operator == "==" else not matched

    if operator == "~=":
        # ~=X.Y.Z  <=>  >=X.Y.Z, ==X.Y.*
        base = parse_release(bound)
        if base is None or len(base) < 2:
            return None
        lower_ok = compare_releases(version, bound)
        if lower_ok is None:
            return None
        prefix = base[:-1]
        actual = parse_release(version)
        if actual is None:
            return None
        return lower_ok >= 0 and actual[: len(prefix)] == prefix

    cmp = compare_releases(version, bound)
    if cmp is None:
        return None
    return {
        "==": cmp == 0,
        "!=": cmp != 0,
        ">=": cmp >= 0,
        "<=": cmp <= 0,
        ">": cmp > 0,
        "<": cmp < 0,
    }[operator]


def satisfies(version: str, specifier_set: str) -> Optional[bool]:
    """Does ``version`` satisfy a PEP 440 specifier set (e.g. ``>=3.0,<4``)?

    Returns ``True``/``False``, or ``None`` when the answer cannot be
    determined confidently (unparseable specifier, or a pre-release/dev version
    where our simplified ordering could be wrong). Callers must treat ``None``
    as "don't report" — never guess.
    """
    if not specifier_set or not specifier_set.strip():
        return None
    if _is_prerelease(version):
        return None

    result = True
    for raw in specifier_set.split(","):
        raw = raw.strip()
        if not raw:
            continue
        match = _SPEC_RE.match(raw)
        if not match:
            return None
        operator, bound = match.group(1), match.group(2)
        if _is_prerelease(bound) and operator != "===":
            return None
        outcome = _satisfies_one(version, operator, bound)
        if outcome is None:
            return None
        result = result and outcome
    return result


def version_gap(left: str, right: str) -> VersionGap:
    """Classify the gap between two version strings.

    The first differing position of the padded release tuples determines the
    magnitude: position 0 -> MAJOR, position 1 -> MINOR, else PATCH.
    """
    a = parse_release(left)
    b = parse_release(right)
    if a is None or b is None:
        return VersionGap.UNKNOWN if left != right else VersionGap.NONE
    pa, pb = _pad(a, b)
    if pa == pb:
        return VersionGap.NONE
    for index, (x, y) in enumerate(zip(pa, pb)):
        if x != y:
            if index == 0:
                return VersionGap.MAJOR
            if index == 1:
                return VersionGap.MINOR
            return VersionGap.PATCH
    return VersionGap.NONE  # pragma: no cover - unreachable given pa != pb
