"""EnvFixer — root-cause diagnosis for "passes locally, fails in CI".

EnvFixer captures a privacy-safe fingerprint of a Python environment
(interpreter, platform, installed packages and *env-var names only*) and
compares two of them to rank the most likely cause of an environment-drift
failure — then prints a plain-English fix for each.
"""

from .model import UNKNOWN, Fingerprint, parse_freeze
from .diff import Difference, diff_fingerprints
from .rank import Cause, rank_causes
from .check import Finding, analyze_dependencies, check_environment

__version__ = "0.2.0"

__all__ = [
    "Fingerprint",
    "UNKNOWN",
    "parse_freeze",
    "Difference",
    "diff_fingerprints",
    "Cause",
    "rank_causes",
    "Finding",
    "analyze_dependencies",
    "check_environment",
    "__version__",
]
