"""The environment fingerprint: schema, capture, and (de)serialization.

Design notes
------------
* **Privacy-safe by construction.** We record environment variable *names*
  only, never their values. The fingerprint is plain JSON you can eyeball.
* **Zero third-party dependencies** in this module so ``capture`` runs cleanly
  inside minimal / hostile CI containers.
"""

from __future__ import annotations

import json
import locale as _locale
import os
import platform
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

SCHEMA_VERSION = 2

#: Sentinel for a field we could not determine (e.g. a fingerprint synthesized
#: from a ``pip freeze`` dump knows nothing about the OS). Unknown fields are
#: *skipped* when diffing so a partial fingerprint never invents a difference.
UNKNOWN = "unknown"


def is_unknown(value) -> bool:
    """True when a fingerprint field carries no usable information."""
    return value is None or (isinstance(value, str) and value.strip() in ("", UNKNOWN))


def normalize_package_name(name: str) -> str:
    """Normalize a distribution name per PEP 503 (``Foo_Bar`` -> ``foo-bar``)."""
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def _detect_timezone() -> str:
    """Local timezone as ``NAME±HH:MM`` (e.g. ``UTC+00:00``, ``EST-05:00``).

    CI runners almost always run UTC while laptops don't — a classic source of
    date/time test failures that no lockfile captures.
    """
    try:
        now = datetime.now().astimezone()
        offset = now.utcoffset()
        if offset is None:  # pragma: no cover - defensive
            return UNKNOWN
        total = int(offset.total_seconds())
        sign = "+" if total >= 0 else "-"
        hours, remainder = divmod(abs(total), 3600)
        minutes = remainder // 60
        name = now.tzname() or (time.tzname[0] if time.tzname else "")
        return f"{name}{sign}{hours:02d}:{minutes:02d}".strip()
    except Exception:  # pragma: no cover - never let capture crash
        return UNKNOWN


def _detect_locale_encoding() -> str:
    """Preferred text encoding (e.g. ``UTF-8`` vs ``ANSI_X3.4-1968``).

    An ASCII-only locale in CI turns perfectly good code into
    ``UnicodeEncodeError`` — another cause lockfiles cannot see.
    """
    try:
        encoding = _locale.getpreferredencoding(False)
        return encoding or UNKNOWN
    except Exception:  # pragma: no cover - defensive
        return UNKNOWN


def _detect_libc() -> str:
    """Best-effort libc description, e.g. ``glibc 2.35``.

    ``platform.libc_ver()`` returns empty strings on musl-based images
    (Alpine), which is itself a useful signal, so we surface ``musl`` when we
    can infer it and ``unknown`` otherwise.
    """
    lib, ver = platform.libc_ver()
    if lib:
        return f"{lib} {ver}".strip()
    # musl's ldd reports its version via a file that libc_ver misses; treat an
    # empty result on Linux as a hint rather than a hard claim.
    if sys.platform.startswith("linux"):
        return "unknown (possibly musl)"
    return "unknown"


@dataclass
class Fingerprint:
    """A privacy-safe snapshot of a Python environment."""

    python_version: str
    python_implementation: str
    platform_system: str
    platform_release: str
    platform_machine: str
    libc: str
    packages: Dict[str, str]
    #: ``None`` means "not known" (e.g. synthesized from a freeze file) — which
    #: is different from an empty list, meaning "known to have no variables".
    env_var_names: Optional[List[str]]
    captured_at: str
    schema_version: int = SCHEMA_VERSION
    timezone: str = UNKNOWN
    locale_encoding: str = UNKNOWN
    #: How this fingerprint was produced: ``capture`` (live) or ``freeze``
    #: (synthesized from a requirements/pip-freeze dump).
    source: str = "capture"

    # -- construction ------------------------------------------------------

    @classmethod
    def capture(cls) -> "Fingerprint":
        """Capture the fingerprint of the *current* interpreter.

        IMPORTANT: run this inside the target virtualenv (``python -m
        envfixer capture``); a global install fingerprints the wrong
        environment.
        """
        return cls(
            python_version=platform.python_version(),
            python_implementation=platform.python_implementation(),
            platform_system=platform.system(),
            platform_release=platform.release(),
            platform_machine=platform.machine(),
            libc=_detect_libc(),
            packages=_installed_packages(),
            env_var_names=sorted(os.environ.keys()),
            captured_at=datetime.now(timezone.utc).isoformat(),
            timezone=_detect_timezone(),
            locale_encoding=_detect_locale_encoding(),
            source="capture",
        )

    @classmethod
    def from_freeze(
        cls,
        text: str,
        python_version: str = UNKNOWN,
        python_implementation: str = UNKNOWN,
        platform_system: str = UNKNOWN,
        platform_machine: str = UNKNOWN,
        libc: str = UNKNOWN,
    ) -> "Fingerprint":
        """Synthesize a fingerprint from ``pip freeze`` / requirements text.

        This is what lets you diagnose a CI failure from its *logs alone* —
        no need to install EnvFixer inside the broken environment. Everything
        we cannot learn from the dump stays ``unknown`` and is skipped when
        diffing, so a partial fingerprint never invents a difference.
        """
        return cls(
            python_version=python_version,
            python_implementation=python_implementation,
            platform_system=platform_system,
            platform_release=UNKNOWN,
            platform_machine=platform_machine,
            libc=libc,
            packages=parse_freeze(text),
            env_var_names=None,  # a freeze dump says nothing about env vars
            captured_at=datetime.now(timezone.utc).isoformat(),
            timezone=UNKNOWN,
            locale_encoding=UNKNOWN,
            source="freeze",
        )

    # -- serialization -----------------------------------------------------

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict) -> "Fingerprint":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        missing = {"python_version", "platform_system", "packages"} - set(data)
        if missing:
            raise ValueError(
                f"not a valid EnvFixer fingerprint; missing keys: {sorted(missing)}"
            )
        payload = {k: v for k, v in data.items() if k in known}
        # Normalize package names defensively so diffs never miss a match on
        # casing/separator differences.
        payload["packages"] = {
            normalize_package_name(k): v for k, v in payload.get("packages", {}).items()
        }
        payload.setdefault("env_var_names", None)
        payload.setdefault("python_implementation", UNKNOWN)
        payload.setdefault("platform_release", "")
        payload.setdefault("platform_machine", "")
        payload.setdefault("libc", UNKNOWN)
        payload.setdefault("captured_at", "")
        payload.setdefault("schema_version", SCHEMA_VERSION)
        # Schema v1 fingerprints predate these fields; treat them as unknown so
        # comparing a v1 against a v2 capture cannot fabricate a difference.
        payload.setdefault("timezone", UNKNOWN)
        payload.setdefault("locale_encoding", UNKNOWN)
        payload.setdefault("source", "capture")
        return cls(**payload)

    @classmethod
    def from_json(cls, text: str) -> "Fingerprint":
        return cls.from_dict(json.loads(text))

    # -- io ----------------------------------------------------------------

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.to_json())

    @classmethod
    def load(cls, path: str) -> "Fingerprint":
        with open(path, "r", encoding="utf-8") as fh:
            return cls.from_json(fh.read())


#: ``name==version`` as emitted by ``pip freeze`` (extras/whitespace tolerated).
_FREEZE_RE = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*==\s*([^\s;#]+)"
)


def parse_freeze(text: str) -> Dict[str, str]:
    """Extract ``{name: version}`` from ``pip freeze``/requirements text.

    Only exact ``==`` pins carry a known installed version, so anything else
    (editable installs, VCS/URL requirements, bare or range-pinned names,
    ``-r`` includes, comments) is skipped rather than guessed at.
    """
    packages: Dict[str, str] = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = _FREEZE_RE.match(line)
        if not match:
            continue
        packages[normalize_package_name(match.group(1))] = match.group(2).strip()
    return packages


def _installed_packages() -> Dict[str, str]:
    """Map normalized distribution name -> version for the current env."""
    from importlib import metadata  # stdlib since 3.8

    packages: Dict[str, str] = {}
    for dist in metadata.distributions():
        name = dist.metadata["Name"] if dist.metadata else None
        if not name:
            continue
        packages[normalize_package_name(name)] = dist.version or "unknown"
    return packages
