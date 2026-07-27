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
import os
import platform
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List

SCHEMA_VERSION = 1


def normalize_package_name(name: str) -> str:
    """Normalize a distribution name per PEP 503 (``Foo_Bar`` -> ``foo-bar``)."""
    return re.sub(r"[-_.]+", "-", name).strip().lower()


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
    env_var_names: List[str]
    captured_at: str
    schema_version: int = SCHEMA_VERSION

    # -- construction ------------------------------------------------------

    @classmethod
    def capture(cls) -> "Fingerprint":
        """Capture the fingerprint of the *current* interpreter.

        IMPORTANT: run this inside the target virtualenv (``python -m
        envdoctor capture``); a global install fingerprints the wrong
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
        )

    # -- serialization -----------------------------------------------------

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict) -> "Fingerprint":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        missing = {
            "python_version",
            "platform_system",
            "packages",
            "env_var_names",
        } - set(data)
        if missing:
            raise ValueError(
                f"not a valid EnvDoctor fingerprint; missing keys: {sorted(missing)}"
            )
        payload = {k: v for k, v in data.items() if k in known}
        # Normalize package names defensively so diffs never miss a match on
        # casing/separator differences.
        payload["packages"] = {
            normalize_package_name(k): v for k, v in payload.get("packages", {}).items()
        }
        payload.setdefault("python_implementation", "unknown")
        payload.setdefault("platform_release", "")
        payload.setdefault("platform_machine", "")
        payload.setdefault("libc", "unknown")
        payload.setdefault("captured_at", "")
        payload.setdefault("schema_version", SCHEMA_VERSION)
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
