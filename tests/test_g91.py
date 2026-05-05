"""
Tests for G91 incremental coordinate interpretation (added in v4).

Each test is an independent pytest function — pytest discovers them by
name (test_*) and runs them all, reporting which pass/fail. Failures
in one test do not prevent others from running.

Run from repo root:
    pytest tests/test_g91.py        # just this file
    pytest                           # full suite
    pytest -k g91                    # tests with "g91" in the name
"""

from gcode_audit_v4_050526 import parse_gcode_lines


# ============================================================
# Baseline: G90 absolute mode (unchanged from v3)
# ============================================================

def test_g90_absolute_mode_replaces_position():
    """G90 mode: each X/Y/Z replaces the previous value."""
    parsed = parse_gcode_lines([
        "G90",
        "G0 X10 Y20 Z5",
        "G1 X15 Y25 Z-1",
        "X20",          # absolute: X becomes 20
        "Y30",          # absolute: Y becomes 30
    ])
    final = parsed["lines"][-1]["state"]
    assert final["X"] == 20.0
    assert final["Y"] == 30.0
    assert parsed["parser_issues"] == []


# ============================================================
# Core G91 incremental behavior
# ============================================================

def test_g91_increments_from_prior_position():
    """G91 mode: each X/Y/Z is added to the previous value."""
    parsed = parse_gcode_lines([
        "G90",
        "G0 X10 Y20 Z5",   # establish absolute starting position
        "G91",             # switch to incremental
        "X5",              # X: 10 + 5 = 15
        "Y3",              # Y: 20 + 3 = 23
        "X-2 Y-1",         # X: 15-2=13, Y: 23-1=22
        "Z-6",             # Z: 5 + (-6) = -1
    ])
    final = parsed["lines"][-1]["state"]
    assert final["X"] == 13.0
    assert final["Y"] == 22.0
    assert final["Z"] == -1.0
    assert parsed["parser_issues"] == []


def test_g91_to_g90_round_trip():
    """G90 → G91 → G90: each switch correctly changes interpretation."""
    parsed = parse_gcode_lines([
        "G90",
        "G0 X100 Y100",    # absolute: X=100, Y=100
        "G91",
        "X10 Y10",         # incremental: X=110, Y=110
        "G90",
        "X50",             # absolute: X=50, Y stays 110
    ])
    final = parsed["lines"][-1]["state"]
    assert final["X"] == 50.0
    assert final["Y"] == 110.0


def test_g91_persists_across_continuation_lines():
    """G91 mode and motion mode both persist across lines without G-codes."""
    parsed = parse_gcode_lines([
        "G90",
        "G1 X0 Y0 Z5 F100",
        "G91",
        "Z-1",      # incremental, motion still G1: Z = 5-1 = 4
        "Z-1",      # Z = 4-1 = 3
        "Z-1",      # Z = 3-1 = 2
    ])
    final = parsed["lines"][-1]["state"]
    assert final["Z"] == 2.0
    assert final["motion"] == "G1"
    assert final["distance"] == "G91"


# ============================================================
# Edge case: G91 with no prior position
# ============================================================

def test_g91_no_prior_position_emits_info_issue():
    """G91 active at startup: first axis use is treated absolute, INFO issue logged."""
    parsed = parse_gcode_lines([
        "G91",
        "G0 X5 Y10",   # no prior X or Y; absolute, two INFO issues
        "X3",          # now X has prior (5): X = 5+3 = 8
    ])
    final = parsed["lines"][-1]["state"]
    assert final["X"] == 8.0
    assert final["Y"] == 10.0

    issues = parsed["parser_issues"]
    assert len(issues) == 2  # one each for X and Y on line 2
    for issue in issues:
        assert issue["type"] == "INCREMENTAL_NO_PRIOR"
        assert issue["severity"] == "INFO"
        assert issue["line_index"] == 2


def test_g91_no_prior_position_only_first_axis_use_flagged():
    """After an axis has any prior value, subsequent G91 moves on that axis don't re-flag."""
    parsed = parse_gcode_lines([
        "G91",
        "X5",          # no prior X → INFO, X=5
        "X10",         # has prior → no INFO, X=5+10=15
        "X-3",         # has prior → no INFO, X=15-3=12
    ])
    final = parsed["lines"][-1]["state"]
    assert final["X"] == 12.0

    issues = parsed["parser_issues"]
    assert len(issues) == 1
    assert issues[0]["line_index"] == 2


# ============================================================
# Mid-line G-code / coordinate ordering
# ============================================================

def test_g91_takes_effect_before_coordinate_on_same_line():
    """A line with `G91 X5` interprets X5 as incremental (G-codes apply first)."""
    parsed = parse_gcode_lines([
        "G90",
        "G0 X10 Y20",   # establish: X=10, Y=20
        "G91 X5",       # G91 first, then X5 incremental: X = 10+5 = 15
    ])
    assert parsed["lines"][-1]["state"]["X"] == 15.0


def test_coordinate_order_does_not_matter_within_a_line():
    """G91 effect does not depend on token order: `X3 G91` behaves like `G91 X3`."""
    parsed = parse_gcode_lines([
        "G90",
        "G0 X10",
        "G91",          # already in G91 from this line forward
        "X3 G91",       # G91 redundant; X3 incremental: X = 10+3 = 13
    ])
    assert parsed["lines"][-1]["state"]["X"] == 13.0


def test_g90_takes_effect_before_coordinate_on_same_line():
    """A line with `G90 X100` interprets X100 as absolute (G-codes apply first)."""
    parsed = parse_gcode_lines([
        "G91",
        "G0 X10 Y10",   # G91 with no prior → absolute fallback, X=10, Y=10
        "X5",           # incremental: X = 10+5 = 15
        "G90 X100",     # G90 first, then X100 absolute → X = 100
    ])
    final = parsed["lines"][-1]["state"]
    assert final["X"] == 100.0
    assert final["Y"] == 10.0
