"""Synthetic fault injector.

Starting from a realistic base environment, each generator injects exactly one
*known* fault (plus optional noise) and records the ground-truth cause. This
same generator produces both the test fixtures and the benchmark corpus, which
keeps the ranking engine honest: it is scored against faults whose true cause
we control.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import List, Optional, Tuple

from envfixer import diff as _d
from envfixer.model import Fingerprint

_BASE = {
    "python_version": "3.11.5",
    "python_implementation": "CPython",
    "platform_system": "Linux",
    "platform_release": "5.15.0",
    "platform_machine": "x86_64",
    "libc": "glibc 2.35",
    "packages": {
        "requests": "2.31.0",
        "urllib3": "2.0.7",
        "certifi": "2023.7.22",
        "numpy": "1.26.0",
        "pandas": "2.1.1",
        "click": "8.1.7",
        "pyyaml": "6.0.1",
        "jinja2": "3.1.2",
        "markupsafe": "2.1.3",
        "sqlalchemy": "2.0.21",
        "pytest": "7.4.2",
        "flask": "3.0.0",
        "werkzeug": "3.0.0",
        "pydantic": "2.4.2",
        "packaging": "23.2",
    },
    "env_var_names": [
        "AWS_REGION", "CI", "DATABASE_URL", "HOME", "LANG", "PATH", "PWD",
        "PYTHONPATH", "SHLVL", "TERM", "USER", "VIRTUAL_ENV",
    ],
    "captured_at": "2026-07-27T00:00:00+00:00",
    "schema_version": 1,
}


@dataclass
class Case:
    """A labelled scenario: working vs failing with a known cause."""

    name: str
    working: Fingerprint
    failing: Fingerprint
    # (category, key) of the true cause, or None for a pure-noise case.
    ground_truth: Optional[Tuple[str, str]]
    traceback: Optional[str] = None


def _base() -> dict:
    return copy.deepcopy(_BASE)


def _fp(data: dict) -> Fingerprint:
    return Fingerprint.from_dict(data)


def _add_noise(data: dict) -> None:
    """Add differences that should never be flagged as a cause."""
    data["env_var_names"] = sorted(set(data["env_var_names"]) | {"LS_COLORS", "COLUMNS"})
    data["packages"]["certifi"] = "2023.11.17"  # patch bump on an unrelated pkg


def generate_cases() -> List[Case]:
    cases: List[Case] = []

    # 1. Missing package (the canonical CI failure).
    fail = _base()
    del fail["packages"]["pydantic"]
    cases.append(Case("missing_package", _fp(_base()), _fp(fail),
                      (_d.PACKAGE_MISSING, "pydantic")))

    # 2. Major version mismatch.
    fail = _base()
    fail["packages"]["pydantic"] = "1.10.13"
    cases.append(Case("major_version_mismatch", _fp(_base()), _fp(fail),
                      (_d.VERSION_MISMATCH, "pydantic")))

    # 3. Minor version mismatch.
    fail = _base()
    fail["packages"]["numpy"] = "1.24.0"
    cases.append(Case("minor_version_mismatch", _fp(_base()), _fp(fail),
                      (_d.VERSION_MISMATCH, "numpy")))

    # 4. Patch version mismatch (only difference -> should still surface).
    fail = _base()
    fail["packages"]["requests"] = "2.31.1"
    cases.append(Case("patch_version_mismatch", _fp(_base()), _fp(fail),
                      (_d.VERSION_MISMATCH, "requests")))

    # 5. Missing consequential env var.
    fail = _base()
    fail["env_var_names"] = [n for n in fail["env_var_names"] if n != "DATABASE_URL"]
    cases.append(Case("missing_env_var", _fp(_base()), _fp(fail),
                      (_d.ENV_VAR_MISSING, "DATABASE_URL")))

    # 6. Python minor mismatch.
    fail = _base()
    fail["python_version"] = "3.9.18"
    cases.append(Case("python_minor_mismatch", _fp(_base()), _fp(fail),
                      (_d.PYTHON_VERSION, "python")))

    # 7. libc glibc -> musl.
    fail = _base()
    fail["libc"] = "musl 1.2.4"
    cases.append(Case("libc_musl", _fp(_base()), _fp(fail),
                      (_d.LIBC, "libc")))

    # 8. Architecture mismatch.
    fail = _base()
    fail["platform_machine"] = "aarch64"
    cases.append(Case("arch_mismatch", _fp(_base()), _fp(fail),
                      (_d.PLATFORM_MACHINE, "platform_machine")))

    # 9-11. True cause buried under noise (ranking robustness).
    fail = _base()
    _add_noise(fail)
    del fail["packages"]["flask"]
    cases.append(Case("missing_package_with_noise", _fp(_base()), _fp(fail),
                      (_d.PACKAGE_MISSING, "flask")))

    fail = _base()
    _add_noise(fail)
    fail["packages"]["sqlalchemy"] = "1.4.49"
    cases.append(Case("major_mismatch_with_noise", _fp(_base()), _fp(fail),
                      (_d.VERSION_MISMATCH, "sqlalchemy")))

    fail = _base()
    _add_noise(fail)
    del fail["packages"]["pandas"]
    tb = (
        "Traceback (most recent call last):\n"
        "  File \"app.py\", line 3, in <module>\n"
        "    import pandas as pd\n"
        "ModuleNotFoundError: No module named 'pandas'\n"
    )
    cases.append(Case("missing_package_with_traceback", _fp(_base()), _fp(fail),
                      (_d.PACKAGE_MISSING, "pandas"), traceback=tb))

    # 12. Pure noise: no real cause; must NOT produce a high-confidence result.
    fail = _base()
    _add_noise(fail)
    cases.append(Case("pure_noise", _fp(_base()), _fp(fail), None))

    return cases
