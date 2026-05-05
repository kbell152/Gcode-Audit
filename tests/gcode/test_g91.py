#!/usr/bin/env python3
"""
Synthetic test cases for G91 incremental coordinate interpretation.
Tests added in v4 (gcode_audit_v4_050526.py).
"""

import sys
import os
_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_here, "..", "src"))

from gcode_audit_v4_050526 import parse_gcode_lines


def show(label, parsed, axes=("X", "Y", "Z")):
    print(f"\n--- {label} ---")
    for entry in parsed["lines"]:
        if entry["line_type"] != "CODE":
            continue
        s = entry["state"]
        pos = "  ".join(f"{a}={s[a]}" for a in axes)
        dist = s["distance"] or "—"
        print(f"  L{entry['line_index']:>2}  [{dist}]  {pos}  tokens={entry['tokens']}")
    if parsed.get("parser_issues"):
        print("  parser_issues:")
        for pi in parsed["parser_issues"]:
            print(f"    {pi}")


# Test 1: pure G90 (absolute) — baseline behavior
print("=" * 60)
print("TEST 1: Pure G90 absolute mode (baseline behavior)")
print("=" * 60)
prog1 = [
    "G90",
    "G0 X10 Y20 Z5",
    "G1 X15 Y25 Z-1",
    "X20",      # absolute: X becomes 20
    "Y30",      # absolute: Y becomes 30
]
parsed = parse_gcode_lines(prog1)
show("Expected: positions replace, no parser_issues", parsed)
final = parsed["lines"][-1]["state"]
assert final["X"] == 20.0, f"Test 1 failed: X={final['X']}"
assert final["Y"] == 30.0, f"Test 1 failed: Y={final['Y']}"
assert not parsed["parser_issues"], "Test 1: should be no parser_issues"
print("  ✓ PASS")


# Test 2: pure G91 (incremental) — values add
print("\n" + "=" * 60)
print("TEST 2: G91 with prior position established")
print("=" * 60)
prog2 = [
    "G90",
    "G0 X10 Y20 Z5",   # establish absolute starting position
    "G91",             # switch to incremental
    "X5",              # X: 10 + 5 = 15
    "Y3",              # Y: 20 + 3 = 23
    "X-2 Y-1",         # X: 15-2=13, Y: 23-1=22
    "Z-6",             # Z: 5-6 = -1
]
parsed = parse_gcode_lines(prog2)
show("Expected: each motion adds to previous", parsed)
final = parsed["lines"][-1]["state"]
assert final["X"] == 13.0, f"Test 2 failed: X={final['X']}"
assert final["Y"] == 22.0, f"Test 2 failed: Y={final['Y']}"
assert final["Z"] == -1.0, f"Test 2 failed: Z={final['Z']}"
assert not parsed["parser_issues"], "Test 2: should be no parser_issues"
print("  ✓ PASS")


# Test 3: G90 → G91 → G90 round trip
print("\n" + "=" * 60)
print("TEST 3: G90 → G91 → G90 round trip")
print("=" * 60)
prog3 = [
    "G90",
    "G0 X100 Y100",    # absolute: X=100, Y=100
    "G91",
    "X10 Y10",         # incremental: X=110, Y=110
    "G90",
    "X50",             # absolute: X=50, Y stays 110
]
parsed = parse_gcode_lines(prog3)
show("Expected: mode switches respected", parsed)
final = parsed["lines"][-1]["state"]
assert final["X"] == 50.0, f"Test 3 failed: X={final['X']}"
assert final["Y"] == 110.0, f"Test 3 failed: Y={final['Y']}"
print("  ✓ PASS")


# Test 4: Edge case — G91 with no prior position
print("\n" + "=" * 60)
print("TEST 4: G91 active at startup (no prior position)")
print("=" * 60)
prog4 = [
    "G91",
    "G0 X5 Y10",       # no prior X or Y; treated as absolute, INFO issue
    "X3",              # now X has prior (5), so X = 5+3 = 8
]
parsed = parse_gcode_lines(prog4)
show("Expected: first motion treated absolute, INFO issue", parsed)
final = parsed["lines"][-1]["state"]
assert final["X"] == 8.0, f"Test 4 failed: X={final['X']}"
assert final["Y"] == 10.0, f"Test 4 failed: Y={final['Y']}"
issues = parsed["parser_issues"]
assert len(issues) == 2, f"Test 4 failed: expected 2 INFO issues (X and Y), got {len(issues)}"
assert all(i["type"] == "INCREMENTAL_NO_PRIOR" for i in issues)
print("  ✓ PASS")


# Test 5: G91 and G-code on same line — order doesn't matter
print("\n" + "=" * 60)
print("TEST 5: G91 and coordinates on same line")
print("=" * 60)
prog5 = [
    "G90",
    "G0 X10 Y20",       # establish: X=10, Y=20
    "G91 X5",           # G91 takes effect first, then X5 → X = 10+5 = 15
    "X3 G91",           # already in G91, X = 15+3 = 18 (order of G91 vs X)
]
parsed = parse_gcode_lines(prog5)
show("Expected: G/M codes always applied before coordinates", parsed)
final = parsed["lines"][-1]["state"]
assert final["X"] == 18.0, f"Test 5 failed: X={final['X']}"
print("  ✓ PASS")


# Test 6: G90 and coordinates on same line
print("\n" + "=" * 60)
print("TEST 6: G90 switch and coordinates on same line")
print("=" * 60)
prog6 = [
    "G91",
    "G0 X10 Y10",       # G91 with no prior, treated absolute: X=10, Y=10
    "X5",               # X = 10+5 = 15
    "G90 X100",         # G90 takes effect, then X=100 absolute
]
parsed = parse_gcode_lines(prog6)
show("Expected: G90 on same line switches to absolute interpretation", parsed)
final = parsed["lines"][-1]["state"]
assert final["X"] == 100.0, f"Test 6 failed: X={final['X']}"
assert final["Y"] == 10.0, f"Test 6 failed: Y={final['Y']}"
print("  ✓ PASS")


# Test 7: Modal inheritance with G91 — line with no G-code keeps mode
print("\n" + "=" * 60)
print("TEST 7: G91 mode persists across lines without G-codes")
print("=" * 60)
prog7 = [
    "G90",
    "G1 X0 Y0 Z5 F100",  # absolute baseline
    "G91",
    "Z-1",               # incremental, motion mode G1 inherited: Z = 5-1 = 4
    "Z-1",               # Z = 4-1 = 3
    "Z-1",               # Z = 3-1 = 2
]
parsed = parse_gcode_lines(prog7)
show("Expected: G91 stays active, motion stays G1, Z decrements", parsed)
final = parsed["lines"][-1]["state"]
assert final["Z"] == 2.0, f"Test 7 failed: Z={final['Z']}"
assert final["motion"] == "G1", f"Test 7 failed: motion={final['motion']}"
print("  ✓ PASS")


print("\n" + "=" * 60)
print("ALL TESTS PASSED")
print("=" * 60)
