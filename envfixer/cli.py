"""Command-line interface: ``capture``, ``diff`` and ``check``.

Dependency-free (argparse only) so the CLI runs in any environment the code
under test does.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__
from .check import check_environment
from .diff import diff_fingerprints
from .model import UNKNOWN, Fingerprint
from .rank import rank_causes
from .report import RENDERERS, exit_code, render


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="envfixer",
        description="Root-cause diagnosis for 'passes locally, fails in CI'.",
    )
    parser.add_argument("--version", action="version", version=f"envfixer {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_cap = sub.add_parser("capture", help="capture this environment's fingerprint")
    p_cap.add_argument(
        "-o", "--output", help="write fingerprint JSON here (default: stdout)"
    )
    p_cap.add_argument(
        "--from-freeze",
        metavar="FILE",
        help="build the fingerprint from a pip freeze / requirements dump "
             "instead of this interpreter ('-' reads stdin). Lets you diagnose "
             "a CI failure from its logs, without installing EnvFixer there.",
    )
    p_cap.add_argument("--python-version", help="python version for --from-freeze")
    p_cap.add_argument("--platform-system", help="OS for --from-freeze (e.g. Linux)")
    p_cap.add_argument("--platform-machine", help="arch for --from-freeze (e.g. x86_64)")
    p_cap.add_argument("--libc", help="libc for --from-freeze (e.g. 'musl 1.2.4')")

    p_diff = sub.add_parser(
        "diff", help="diagnose why WORKING passes but FAILING fails"
    )
    p_diff.add_argument("working", help="fingerprint JSON from the environment that works")
    p_diff.add_argument("failing", help="fingerprint JSON from the environment that fails")
    p_diff.add_argument(
        "--traceback", help="path to the failing run's traceback/log to correlate"
    )
    _add_report_args(p_diff)

    p_check = sub.add_parser(
        "check", help="health-check a single environment (this one by default)"
    )
    p_check.add_argument(
        "fingerprint", nargs="?", help="fingerprint JSON to check (default: capture live)"
    )
    _add_report_args(p_check)

    return parser


def _add_report_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--format", choices=sorted(RENDERERS), default="human", help="output format"
    )
    p.add_argument(
        "--fail-on",
        choices=["none", "low", "medium", "high"],
        default="high",
        help="exit non-zero when a cause of at least this confidence is found",
    )
    p.add_argument("--top", type=int, default=0, help="show only the top N results (0 = all)")


def _cmd_capture(args) -> int:
    if args.from_freeze:
        if args.from_freeze == "-":
            freeze_text = sys.stdin.read()
        else:
            with open(args.from_freeze, "r", encoding="utf-8") as fh:
                freeze_text = fh.read()
        fp = Fingerprint.from_freeze(
            freeze_text,
            python_version=args.python_version or UNKNOWN,
            platform_system=args.platform_system or UNKNOWN,
            platform_machine=args.platform_machine or UNKNOWN,
            libc=args.libc or UNKNOWN,
        )
    else:
        fp = Fingerprint.capture()
    text = fp.to_json()
    if args.output:
        fp.save(args.output)
        print(f"Wrote fingerprint to {args.output}", file=sys.stderr)
    else:
        print(text)
    return 0


def _cmd_diff(args) -> int:
    working = Fingerprint.load(args.working)
    failing = Fingerprint.load(args.failing)
    traceback_text = None
    if args.traceback:
        with open(args.traceback, "r", encoding="utf-8") as fh:
            traceback_text = fh.read()
    diffs = diff_fingerprints(working, failing)
    causes = rank_causes(diffs, traceback_text=traceback_text)
    if args.top and args.top > 0:
        causes = causes[: args.top]
    print(render(causes, "diagnosis", args.format))
    return exit_code(causes, args.fail_on)


def _cmd_check(args) -> int:
    fingerprint = Fingerprint.load(args.fingerprint) if args.fingerprint else None
    findings = check_environment(fingerprint)
    if args.top and args.top > 0:
        findings = findings[: args.top]
    print(render(findings, "environment health check", args.format))
    return exit_code(findings, args.fail_on)


_DISPATCH = {"capture": _cmd_capture, "diff": _cmd_diff, "check": _cmd_check}


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _DISPATCH[args.command](args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"envfixer: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
