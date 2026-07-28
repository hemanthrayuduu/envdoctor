"""Load curated real-world scenarios from ``evaluation/cases/*.json``.

Each case file describes a shared ``base`` environment plus ``working`` and
``failing`` overrides, so only the *differing* bits need to be written out.
This keeps hand-curated cases compact and readable while producing the same
:class:`~evaluation.generate.Case` objects the synthetic generator does.

Override semantics
------------------
* ``packages`` is merged into the base package map. A package mapped to
  ``null`` is *removed* (models "installed locally, absent in CI").
* ``env_var_names`` (and any scalar field) replaces the base value outright.
"""

from __future__ import annotations

import copy
import json
import os
from typing import List, Optional

from envfixer.model import Fingerprint

from .generate import Case

CASES_DIR = os.path.join(os.path.dirname(__file__), "cases")

# Fields a case file's ``base`` must provide for a valid fingerprint.
_REQUIRED_BASE = {"python_version", "platform_system", "packages", "env_var_names"}


def _merge(base: dict, overrides: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in (overrides or {}).items():
        if key == "packages" and isinstance(value, dict):
            packages = dict(merged.get("packages", {}))
            for name, version in value.items():
                if version is None:
                    packages.pop(name, None)  # removed in this environment
                else:
                    packages[name] = version
            merged["packages"] = packages
        else:
            merged[key] = value
    return merged


def _case_from_dict(data: dict) -> Case:
    base = data["base"]
    missing = _REQUIRED_BASE - set(base)
    if missing:
        raise ValueError(f"case '{data.get('name')}' base missing keys: {sorted(missing)}")
    working = Fingerprint.from_dict(_merge(base, data.get("working", {})))
    failing = Fingerprint.from_dict(_merge(base, data.get("failing", {})))
    gt = data.get("ground_truth")
    ground_truth = (gt["category"], gt["key"]) if gt else None
    return Case(
        name=data["name"],
        working=working,
        failing=failing,
        ground_truth=ground_truth,
        traceback=data.get("traceback"),
    )


def load_real_world_cases(cases_dir: Optional[str] = None) -> List[Case]:
    """Load and return every curated case, sorted by filename."""
    cases_dir = cases_dir or CASES_DIR
    if not os.path.isdir(cases_dir):
        return []
    cases: List[Case] = []
    for filename in sorted(os.listdir(cases_dir)):
        if not filename.endswith(".json"):
            continue
        with open(os.path.join(cases_dir, filename), "r", encoding="utf-8") as fh:
            cases.append(_case_from_dict(json.load(fh)))
    return cases
