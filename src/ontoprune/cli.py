"""
Command-Line Interface for OntoPrune Middleware.

Provides pipeable CLI commands:
- `ontoprune translate <file> <target>`
- `ontoprune check <response_file> --against <contract_file>`
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ontoprune import __version__, check, translate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ontoprune",
        description="OntoPrune: Neuro-Symbolic Context Pruning Middleware",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: translate
    trans_p = subparsers.add_parser("translate", help="Prune code to minimal context")
    trans_p.add_argument("file", type=str, help="Python source file path")
    trans_p.add_argument("target", type=str, help="Target function or method name")
    trans_p.add_argument(
        "--format",
        "-f",
        default="stubs",
        choices=["stubs", "turtle", "json", "nl"],
        help="Output format (default: stubs)",
    )
    trans_p.add_argument(
        "--include-body",
        action="store_true",
        help="Include the source code body of the target function",
    )
    trans_p.add_argument(
        "--project-root",
        default=None,
        type=str,
        help="Optional root directory of the project (auto-detected if omitted)",
    )

    # Subcommand: check
    check_p = subparsers.add_parser("check", help="Verify model response against contract")
    check_p.add_argument(
        "response_file", type=str, help="File containing LLM output (or - for stdin)"
    )
    check_p.add_argument("--against", required=True, type=str, help="Contract file path")

    args = parser.parse_args(argv)

    if args.command == "translate":
        try:
            rendered = translate(
                source_or_file=args.file,
                target=args.target,
                fmt=args.format,
                include_body=args.include_body,
                multi_module=True,
                project_root=args.project_root,
            )
            sys.stdout.write(rendered + "\n")
            return 0
        except Exception as err:
            sys.stderr.write(f"Error during translation: {err}\n")
            return 1

    elif args.command == "check":
        try:
            if args.response_file == "-":
                response_text = sys.stdin.read()
            else:
                response_text = Path(args.response_file).read_text(encoding="utf-8")

            contract_text = Path(args.against).read_text(encoding="utf-8")
            violations = check(response_text, against=contract_text)

            if violations:
                sys.stdout.write(f"VIOLATIONS FOUND ({len(violations)}):\n")
                for v in violations:
                    sys.stdout.write(f"  - Invalid call: {v}()\n")
                return 2
            else:
                sys.stdout.write("VALID: 0 hallucinated API calls detected.\n")
                return 0
        except Exception as err:
            sys.stderr.write(f"Error during verification: {err}\n")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
