"""Structural diff of two fingerprints.

The diff is *directional*: we compare a ``working`` environment against a
``failing`` one and describe what the failing side lacks or differs on. This
directionality is what lets the ranking engine reason about causes ("present
where it works, absent where it breaks").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .model import Fingerprint

# Difference categories (stable identifiers used by rank/fixes/report).
PACKAGE_MISSING = "package_missing"          # in working, absent in failing
PACKAGE_EXTRA = "package_extra"              # in failing, absent in working
VERSION_MISMATCH = "version_mismatch"
PYTHON_VERSION = "python_version"
PLATFORM_SYSTEM = "platform_system"
PLATFORM_MACHINE = "platform_machine"
LIBC = "libc"
ENV_VAR_MISSING = "env_var_missing"          # name in working, absent in failing
ENV_VAR_EXTRA = "env_var_extra"


@dataclass
class Difference:
    """One structured difference between working and failing environments."""

    category: str
    key: str
    working_value: Optional[str]
    failing_value: Optional[str]
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "key": self.key,
            "working_value": self.working_value,
            "failing_value": self.failing_value,
            "detail": dict(self.detail),
        }


def diff_fingerprints(working: Fingerprint, failing: Fingerprint) -> List[Difference]:
    """Return every structural difference (unranked)."""
    diffs: List[Difference] = []
    diffs.extend(_diff_interpreter(working, failing))
    diffs.extend(_diff_platform(working, failing))
    diffs.extend(_diff_packages(working, failing))
    diffs.extend(_diff_env_vars(working, failing))
    return diffs


def _diff_interpreter(working: Fingerprint, failing: Fingerprint) -> List[Difference]:
    if working.python_version != failing.python_version:
        return [
            Difference(
                category=PYTHON_VERSION,
                key="python",
                working_value=working.python_version,
                failing_value=failing.python_version,
                detail={
                    "working_implementation": working.python_implementation,
                    "failing_implementation": failing.python_implementation,
                },
            )
        ]
    return []


def _diff_platform(working: Fingerprint, failing: Fingerprint) -> List[Difference]:
    diffs: List[Difference] = []
    if working.platform_system != failing.platform_system:
        diffs.append(
            Difference(PLATFORM_SYSTEM, "platform_system",
                       working.platform_system, failing.platform_system)
        )
    if working.platform_machine != failing.platform_machine:
        diffs.append(
            Difference(PLATFORM_MACHINE, "platform_machine",
                       working.platform_machine, failing.platform_machine)
        )
    if working.libc != failing.libc:
        diffs.append(Difference(LIBC, "libc", working.libc, failing.libc))
    return diffs


def _diff_packages(working: Fingerprint, failing: Fingerprint) -> List[Difference]:
    diffs: List[Difference] = []
    for name, version in sorted(working.packages.items()):
        if name not in failing.packages:
            diffs.append(Difference(PACKAGE_MISSING, name, version, None))
        elif failing.packages[name] != version:
            diffs.append(
                Difference(VERSION_MISMATCH, name, version, failing.packages[name])
            )
    for name, version in sorted(failing.packages.items()):
        if name not in working.packages:
            diffs.append(Difference(PACKAGE_EXTRA, name, None, version))
    return diffs


def _diff_env_vars(working: Fingerprint, failing: Fingerprint) -> List[Difference]:
    diffs: List[Difference] = []
    working_names = set(working.env_var_names)
    failing_names = set(failing.env_var_names)
    for name in sorted(working_names - failing_names):
        diffs.append(Difference(ENV_VAR_MISSING, name, "set", None))
    for name in sorted(failing_names - working_names):
        diffs.append(Difference(ENV_VAR_EXTRA, name, None, "set"))
    return diffs
