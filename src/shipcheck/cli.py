import argparse
import json
import sys
from pathlib import Path

from shipcheck import __version__
from shipcheck.models import InputError
from shipcheck.output import render_json_error, render_json_result, render_text_error, render_text_result
from shipcheck.checks.runner import check_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shipcheck",
        description="Check local Python release-state consistency.",
    )
    parser.add_argument("--version", action="version", version=f"ShipCheck {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="check a Python project")
    check.add_argument("path", nargs="?", default=".", type=Path, help="project directory (default: current directory)")
    check.add_argument("--format", choices=("text", "json"), default="text", help="output format")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "check":
        return 2
    try:
        result = check_project(args.path)
    except InputError as error:
        output = render_json_error(error, __version__) if args.format == "json" else render_text_error(error, __version__)
        print(output)
        return 2

    output = render_json_result(result, __version__) if args.format == "json" else render_text_result(result, __version__)
    print(output)
    return 1 if result.status == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
