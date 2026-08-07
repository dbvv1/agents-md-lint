"""Command line interface.

    agents-md-lint check [PATH]     report stale references
    agents-md-lint check --json     machine-readable output

Exits non-zero when findings exceed the threshold, so it drops into CI or a
pre-commit hook without a wrapper script.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .check import Report, check_file, find_context_files, find_repo_root

__version__ = "0.1.0"


def _as_dict(report: Report) -> dict:
    return {
        "file": str(report.file),
        "checked": report.checked,
        "findings": [
            {
                "kind": str(f.ref.kind),
                "value": f.ref.value,
                "line": f.ref.line_no,
                "reason": f.reason,
                "suggestion": f.suggestion,
                "context": f.ref.line,
            }
            for f in report.findings
        ],
    }


def cmd_check(args: argparse.Namespace) -> int:
    target = Path(args.path).resolve()

    if target.is_file():
        files = [target]
        root = find_repo_root(target.parent)
    else:
        root = find_repo_root(target)
        files = find_context_files(target)

    if not files:
        print(f"no context files found under {target}", file=sys.stderr)
        # Nothing to check is not a failure: a repo without a context file is
        # a normal state, not drift.
        return 0

    reports = [check_file(f, root) for f in files]
    total = sum(len(r.findings) for r in reports)
    checked = sum(r.checked for r in reports)

    if args.json:
        print(json.dumps({"reports": [_as_dict(r) for r in reports]}, indent=2))
    else:
        for report in reports:
            if report.findings or args.verbose:
                print(report.format())
        if total == 0:
            print(f"clean: {checked} references across {len(files)} file(s) all resolve")
        else:
            print(f"\n{total} stale reference(s) across {len(files)} file(s)")

    return 1 if total > args.threshold else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agents-md-lint",
        description="Report when the files your agent trusts no longer match the repo.",
    )
    parser.add_argument("--version", action="version", version=f"agents-md-lint {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="check context files for stale references")
    check.add_argument("path", nargs="?", default=".", help="file or directory (default: .)")
    check.add_argument("--json", action="store_true", help="machine-readable output")
    check.add_argument("-v", "--verbose", action="store_true", help="also print clean files")
    check.add_argument(
        "--threshold",
        type=int,
        default=0,
        help="exit non-zero only above this many findings (default: 0)",
    )
    check.set_defaults(func=cmd_check)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
