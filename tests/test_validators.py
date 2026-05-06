"""
Tests for the validators: validate_startup_sequence, group_operations,
profile_operation_depths, and validate_spindle_and_feed.

For each validator we test BOTH:
  - Positive cases: known-bad programs that SHOULD trigger the issue
  - Negative cases: known-good programs that SHOULD NOT trigger it

Negative cases are just as important as positive ones — they catch
"oops, the validator now flags everything" regressions.
"""

from core import parse_gcode_lines
from validators import (
    validate_startup_sequence,
    group_operations,
    profile_operation_depths,
    validate_spindle_and_feed,
)


# ============================================================
# validate_startup_sequence
# ============================================================

class TestStartupSequence:

    def test_clean_startup_no_issues(self):
        """Standard startup: lift Z, move XY, then plunge — no issues."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G0 Z5",          # establish safe Z
            "G0 X10 Y10",     # XY at safe Z
            "G1 Z-1 F100",    # plunge into material
        ])
        assert validate_startup_sequence(parsed) == []

    def test_cut_before_safe_z_flagged_critical(self):
        """First Z move is below zero with no prior safe Z lift — CRITICAL."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G1 Z-1 F100",    # plunge with no prior Z>0
        ])
        issues = validate_startup_sequence(parsed)
        assert len(issues) >= 1
        cut_issues = [i for i in issues if i["type"] == "SEQUENCE_ERROR"
                      and i["severity"] == "CRITICAL"]
        assert len(cut_issues) == 1
        assert cut_issues[0]["line_index"] == 2

    def test_xy_motion_before_safe_z_flagged_warning(self):
        """XY motion before any Z lift — WARNING (not critical because no cut yet)."""
        parsed = parse_gcode_lines([
            "G90",
            "G0 X10 Y10",     # initial XY motion at unknown Z
            "G0 X20 Y20",     # second XY — this is the first detectable change
            "G0 Z5",
        ])
        issues = validate_startup_sequence(parsed)
        warning_issues = [i for i in issues
                          if i["type"] == "SEQUENCE_ERROR"
                          and i["severity"] == "WARNING"]
        assert len(warning_issues) == 1

    def test_safe_z_then_xy_then_cut_no_issues(self):
        """Proper sequence: safe Z first, then XY, then cut."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G0 Z5",          # safe Z
            "G0 X10 Y10",     # XY at safe Z
            "G0 X20 Y20",     # more XY at safe Z
            "G1 Z-1 F100",    # plunge
            "G1 X30 Y30",     # cut
        ])
        assert validate_startup_sequence(parsed) == []


# ============================================================
# group_operations
# ============================================================

class TestGroupOperations:

    def test_no_cutting_means_no_operations(self):
        """If Z never goes below 0, there are no cutting operations."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G0 Z5",
            "G0 X10 Y10",
            "G0 X20 Y20",
        ])
        assert group_operations(parsed) == []

    def test_single_cutting_pass(self):
        """One contiguous run of Z<=0 lines forms one operation."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G0 Z5",
            "G0 X10 Y10",
            "G1 Z-1 F100",    # cut starts
            "G1 X20",
            "G1 Y20",
            "G0 Z5",          # cut ends (Z back above 0)
        ])
        ops = group_operations(parsed)
        assert len(ops) == 1
        assert ops[0]["min_z"] == -1.0

    def test_two_separated_cutting_passes(self):
        """Two cuts separated by a Z lift form two operations."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G0 Z5",
            "G1 Z-1 F100",    # op 1 starts
            "G1 X10",
            "G0 Z5",          # op 1 ends
            "G0 X20",
            "G1 Z-2",         # op 2 starts
            "G1 X30",
            "G0 Z5",          # op 2 ends
        ])
        ops = group_operations(parsed)
        assert len(ops) == 2
        assert ops[0]["min_z"] == -1.0
        assert ops[1]["min_z"] == -2.0

    def test_operation_open_at_eof_still_recorded(self):
        """If file ends mid-cut (no Z lift at end), the open operation is closed."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G0 Z5",
            "G1 Z-1 F100",
            "G1 X10",
            # no final Z lift
        ])
        ops = group_operations(parsed)
        assert len(ops) == 1


# ============================================================
# profile_operation_depths
# ============================================================

class TestProfileDepths:

    def test_empty_operations_yields_empty_profile(self):
        assert profile_operation_depths([]) == []

    def test_single_operation_yields_single_cluster(self):
        ops = [{"start_line": 1, "end_line": 5, "min_z": -1.0, "max_z": 0.0}]
        profile = profile_operation_depths(ops)
        assert len(profile) == 1
        assert profile[0]["depth"] == -1.0
        assert profile[0]["count"] == 1

    def test_similar_depths_cluster_within_tolerance(self):
        """Depths within tolerance (default 0.01) are merged into one cluster."""
        ops = [
            {"start_line": 1, "end_line": 5, "min_z": -1.000, "max_z": 0.0},
            {"start_line": 6, "end_line": 10, "min_z": -1.005, "max_z": 0.0},
            {"start_line": 11, "end_line": 15, "min_z": -1.008, "max_z": 0.0},
        ]
        profile = profile_operation_depths(ops)
        assert len(profile) == 1
        assert profile[0]["count"] == 3

    def test_distinct_depths_form_separate_clusters(self):
        ops = [
            {"start_line": 1, "end_line": 5, "min_z": -1.0, "max_z": 0.0},
            {"start_line": 6, "end_line": 10, "min_z": -3.0, "max_z": 0.0},
            {"start_line": 11, "end_line": 15, "min_z": -5.0, "max_z": 0.0},
        ]
        profile = profile_operation_depths(ops)
        assert len(profile) == 3

    def test_clusters_sorted_by_depth_ascending(self):
        """Output should be sorted from deepest (most negative) to shallowest."""
        ops = [
            {"start_line": 1, "end_line": 5, "min_z": -2.0, "max_z": 0.0},
            {"start_line": 6, "end_line": 10, "min_z": -5.0, "max_z": 0.0},
            {"start_line": 11, "end_line": 15, "min_z": -1.0, "max_z": 0.0},
        ]
        profile = profile_operation_depths(ops)
        depths = [c["depth"] for c in profile]
        assert depths == sorted(depths)


# ============================================================
# validate_spindle_and_feed
# ============================================================

class TestSpindleAndFeed:

    def test_clean_program_no_issues(self):
        """Spindle on, feed set, then cut — no issues."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "M3 S1000",
            "G0 Z5",
            "G1 Z-1 F100",
            "G1 X10",
        ])
        assert validate_spindle_and_feed(parsed) == []

    def test_cut_with_spindle_off_flagged_critical(self):
        """G1 motion after M5 (spindle off) — CRITICAL."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "M3 S1000",
            "G1 Z-1 F100",
            "M5",                # spindle off
            "G1 X10",            # cutting motion with spindle off!
        ])
        issues = validate_spindle_and_feed(parsed)
        critical = [i for i in issues if i["severity"] == "CRITICAL"
                    and i["type"] == "SPINDLE_ERROR"]
        assert len(critical) == 1

    def test_cut_with_spindle_never_started_flagged_warning(self):
        """G1 motion without ever issuing M3/M4 — WARNING."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G1 Z-1 F100",
            "G1 X10",
        ])
        issues = validate_spindle_and_feed(parsed)
        spindle_missing = [i for i in issues if i["type"] == "SPINDLE_WARNING"]
        assert len(spindle_missing) == 1

    def test_cut_without_feed_rate_flagged_warning(self):
        """G1 motion without ever setting an F value — WARNING."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "M3 S1000",
            "G1 Z-1",            # no F set
        ])
        issues = validate_spindle_and_feed(parsed)
        feed_missing = [i for i in issues if i["type"] == "FEED_WARNING"]
        assert len(feed_missing) == 1

    def test_zero_padded_m3_normalized_correctly(self):
        """The v3 fix: M03 must be treated identically to M3."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "M03 S1000",         # zero-padded
            "G1 Z-1 F100",
            "G1 X10",
        ])
        assert validate_spindle_and_feed(parsed) == []

    def test_zero_padded_m5_normalized_correctly(self):
        """M05 must trigger spindle-off detection same as M5."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "M3 S1000",
            "G1 Z-1 F100",
            "M05",               # zero-padded spindle off
            "G1 X10",            # cut after M05
        ])
        issues = validate_spindle_and_feed(parsed)
        critical = [i for i in issues if i["severity"] == "CRITICAL"]
        assert len(critical) == 1

    def test_g0_rapids_do_not_trigger_spindle_check(self):
        """G0 (rapid) is not a cutting motion — no spindle/feed required."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G0 X10 Y10",        # rapid with no spindle, no feed
            "G0 Z5",
        ])
        # Should be no issues — G0 is not cutting
        assert validate_spindle_and_feed(parsed) == []

    def test_issue_reported_once_per_violation_window(self):
        """Repeated cuts in the same off-window should not flood the issue list."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G1 Z-1 F100",       # no spindle ever set — first violation, flagged
            "G1 X10",            # still no spindle, but already flagged
            "G1 X20",            # ditto
            "G1 X30",            # ditto
        ])
        issues = validate_spindle_and_feed(parsed)
        warnings = [i for i in issues if i["type"] == "SPINDLE_WARNING"]
        # Expected: exactly one, not four
        assert len(warnings) == 1
