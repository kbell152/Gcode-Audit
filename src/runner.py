#!/usr/bin/env python3

"""
Command-line runner for the gcode-audit engine.

Loads a G-code file, runs the parser and all validators, and prints
a summary report. Used for ad-hoc testing against tests/gcode/test.gcode
and as a usage example for the engine modules.
"""

import os

from core import parse_gcode_lines
from validators import (
    validate_startup_sequence,
    group_operations,
    profile_operation_depths,
    validate_spindle_and_feed,
)


def main():
    # Default test file path — relative to repo root.
    # Adjust if running from a different location.
    _here = os.path.dirname(os.path.abspath(__file__))
    _test_path = os.path.join(_here, "..", "tests", "gcode", "test.gcode")

    with open(_test_path, "r", encoding="utf-8") as f:
        gcode = f.read().splitlines()

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

    print("\n=== ANALYSIS END ===\n")


if __name__ == "__main__":
    main()
