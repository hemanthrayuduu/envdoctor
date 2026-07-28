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
