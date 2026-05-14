#!/usr/bin/env python3

"""
Command-line runner for the gcode-audit engine.

Loads a G-code file, runs the parser and all validators, and prints
a summary report.

Usage:
    python3 src/runner.py                       # uses default test.gcode
    python3 src/runner.py path/to/program.nc    # audits a specific file
    python3 src/runner.py --version             # show engine version
    python3 src/runner.py --help                # show usage info
"""

import argparse
import os
import sys

from _version import __version__
from core import parse_gcode_lines
from validators import (
    validate_startup_sequence,
    group_operations,
    profile_operation_depths,
    validate_spindle_and_feed,
    validate_rapid_into_material,
)


def _default_gcode_path():
    """
    Default G-code path used when no file argument is supplied.
    Resolved relative to this file so the runner works from any cwd.
    """
    _here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(_here, "..", "tests", "gcode", "test.gcode")


def main():
    parser = argparse.ArgumentParser(
        description="Audit a G-code file and print a summary report."
    )
    parser.add_argument(
        "gcode_file",
        nargs="?",
        default=None,
        help="Path to a G-code file. If omitted, runs against "
             "tests/gcode/test.gcode.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"gcode-audit {__version__}",
    )
    args = parser.parse_args()

    gcode_path = args.gcode_file if args.gcode_file else _default_gcode_path()
    gcode_path = os.path.normpath(gcode_path)

    try:
        with open(gcode_path, "r", encoding="utf-8") as f:
            gcode = f.read().splitlines()
    except FileNotFoundError:
        print(f"Error: file not found: {gcode_path}", file=sys.stderr)
        sys.exit(1)

    print(f"\nAuditing: {gcode_path}")

    parsed = parse_gcode_lines(gcode)

    print("\n=== PARSING G-CODE ===")
    n_total = len(parsed["lines"])
    n_code = sum(1 for L in parsed["lines"] if L["line_type"] == "CODE")
    n_comment = sum(1 for L in parsed["lines"] if L["line_type"] == "COMMENT")
    n_empty = sum(1 for L in parsed["lines"] if L["line_type"] == "EMPTY")
    print(f"Parsed {n_total} lines  ({n_code} code, {n_comment} comment, {n_empty} empty)")

    parser_issues = parsed.get("parser_issues", [])
    print("\n=== PARSER ISSUES ===")
    if not parser_issues:
        print("  (none)")
    for issue in parser_issues:
        print(f"  {issue}")

    # Show final modal state for sanity
    if parsed["lines"]:
        final_state = parsed["lines"][-1]["state"]
        print("\n=== FINAL MODAL STATE ===")
        for k in ("X", "Y", "Z", "motion", "distance", "units", "plane",
                  "spindle", "coolant", "feed", "speed", "tool"):
            print(f"  {k:>10} : {final_state.get(k)}")

    sequence_issues = validate_startup_sequence(parsed)
    print("\n=== SEQUENCE ISSUES ===")
    if not sequence_issues:
        print("  (none)")
    for issue in sequence_issues:
        print(f"  {issue}")

    operations = group_operations(parsed)
    print(f"\n=== OPERATIONS ===\n  {len(operations)} operations found")

    depth_profile = profile_operation_depths(operations)
    print("\n=== DEPTH PROFILE ===")
    if not depth_profile:
        print("  (no cutting operations)")
    for cluster in depth_profile:
        print(f"  Depth {cluster['depth']:.4f}  ->  {cluster['count']} operations")

    spindle_issues = validate_spindle_and_feed(parsed)
    print("\n=== SPINDLE / FEED ISSUES ===")
    if not spindle_issues:
        print("  (none)")
    for issue in spindle_issues:
        print(f"  {issue}")

    rapid_issues = validate_rapid_into_material(parsed)
    print("\n=== RAPID-INTO-MATERIAL ISSUES ===")
    if not rapid_issues:
        print("  (none)")
    for issue in rapid_issues:
        print(f"  {issue}")

    print("\n=== ANALYSIS END ===\n")


if __name__ == "__main__":
    main()
