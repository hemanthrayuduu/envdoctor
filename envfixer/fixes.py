"""Plain-English fix suggestions.

This module is intentionally a *library of remedies* keyed by difference
category — it is the accumulated knowledge asset of the project. Each function
turns a structured :class:`~envfixer.diff.Difference` into an actionable
sentence a developer can follow without further research.
"""

from __future__ import annotations

from . import diff as _d
from .diff import Difference


def fix_for(difference: Difference) -> str:
    """Return a plain-English remedy for a single difference."""
    handler = _HANDLERS.get(difference.category)
    if handler is None:
        return "Review this difference and align the two environments."
    return handler(difference)


def _fix_package_missing(d: Difference) -> str:
    ver = d.working_value or "the working version"
    return (
        f"Install '{d.key}' in the failing environment — it is present where the "
        f"code works but entirely absent where it fails. Add '{d.key}=={ver}' to "
        f"your requirements/lockfile so CI installs it too."
    )


def _fix_version_mismatch(d: Difference) -> str:
    return (
        f"Align '{d.key}': the working environment has {d.working_value} but the "
        f"failing one has {d.failing_value}. Pin '{d.key}=={d.working_value}' in "
        f"your requirements/lockfile so both environments resolve the same build."
    )


def _fix_python_version(d: Difference) -> str:
    return (
        f"Match the Python version: working uses {d.working_value}, failing uses "
        f"{d.failing_value}. Pin the interpreter in CI (e.g. actions/setup-python "
        f"with python-version: '{d.working_value}') or via your tool of choice."
    )


def _fix_platform_system(d: Difference) -> str:
    return (
        f"OS differs: working runs on {d.working_value}, failing on "
        f"{d.failing_value}. OS-specific behavior (path separators, default "
        f"encodings, available system libs) can diverge — reproduce CI locally "
        f"with the same OS (e.g. a matching Docker image)."
    )


def _fix_platform_machine(d: Difference) -> str:
    return (
        f"CPU architecture differs: working is {d.working_value}, failing is "
        f"{d.failing_value}. Packages with compiled extensions may have no "
        f"matching wheel for the failing arch and fall back to a source build "
        f"(or fail). Ensure wheels exist for {d.failing_value} or install build "
        f"toolchain in CI."
    )


def _fix_libc(d: Difference) -> str:
    hint = ""
    if "musl" in (d.failing_value or "").lower() or "musl" in (d.working_value or "").lower():
        hint = (
            " musl (Alpine) and glibc are not binary-compatible; many wheels are "
            "glibc-only. Switch the failing image to a glibc base (e.g. "
            "python:3.x-slim instead of python:3.x-alpine)."
        )
    return (
        f"C library differs: working uses '{d.working_value}', failing uses "
        f"'{d.failing_value}'.{hint}"
    )


def _fix_env_var_missing(d: Difference) -> str:
    return (
        f"Set the environment variable '{d.key}' in the failing environment. It "
        f"is present where the code works but missing in CI; export it in your "
        f"pipeline config or a secrets store (never commit its value)."
    )


def _fix_env_var_extra(d: Difference) -> str:
    return (
        f"The failing environment sets '{d.key}' but the working one does not. If "
        f"your code branches on this variable, that extra value may change "
        f"behavior — unset it in CI or make the code tolerate it."
    )


def _fix_package_extra(d: Difference) -> str:
    return (
        f"The failing environment has '{d.key}' ({d.failing_value}) which the "
        f"working one lacks. An unexpected extra package can shadow imports or "
        f"pull conflicting transitive deps; remove it if it is not needed."
    )


_HANDLERS = {
    _d.PACKAGE_MISSING: _fix_package_missing,
    _d.VERSION_MISMATCH: _fix_version_mismatch,
    _d.PYTHON_VERSION: _fix_python_version,
    _d.PLATFORM_SYSTEM: _fix_platform_system,
    _d.PLATFORM_MACHINE: _fix_platform_machine,
    _d.LIBC: _fix_libc,
    _d.ENV_VAR_MISSING: _fix_env_var_missing,
    _d.ENV_VAR_EXTRA: _fix_env_var_extra,
    _d.PACKAGE_EXTRA: _fix_package_extra,
}
