"""
Regression test against tests/gcode/test.gcode (a real-world program
produced by the Autodesk Fusion / OpenBuilds GRBL post-processor).

The expected values in this file were captured when v4 was working
correctly. If a future change causes them to drift, this test fires —
which means EITHER the change introduced a real regression, OR the
expected values need to be updated because the new behavior is
deliberate. Either way, the test forces a conscious decision rather
than a silent break.
"""

import os

from core import parse_gcode_lines
from validators import (
    validate_startup_sequence,
    group_operations,
    profile_operation_depths,
    validate_spindle_and_feed,
)


_HERE = os.path.dirname(os.path.abspath(__file__))
_TEST_GCODE = os.path.join(_HERE, "gcode", "test.gcode")


def _load():
    """Load test.gcode and parse it. Cached at module load time would be
    nicer but per-test parsing is cheap and keeps tests independent."""
    with open(_TEST_GCODE, "r", encoding="utf-8") as f:
        return parse_gcode_lines(f.read().splitlines())


# ============================================================
# Parser-level expectations
# ============================================================

class TestRegressionParser:

    def test_total_line_count(self):
        parsed = _load()
        assert len(parsed["lines"]) == 110

    def test_line_type_breakdown(self):
        parsed = _load()
        code = sum(1 for L in parsed["lines"] if L["line_type"] == "CODE")
        comment = sum(1 for L in parsed["lines"] if L["line_type"] == "COMMENT")
        empty = sum(1 for L in parsed["lines"] if L["line_type"] == "EMPTY")
        assert code == 64
        assert comment == 39
        assert empty == 7

    def test_no_parser_issues(self):
        """test.gcode is well-formed and should produce no parser issues."""
        parsed = _load()
        assert parsed["parser_issues"] == []

    def test_final_modal_state(self):
        """At end of program, modal state should match what the program left set."""
        parsed = _load()
        final = parsed["lines"][-1]["state"]
        assert final["X"] == -10.0
        assert final["Y"] == -10.0
        assert final["Z"] == 25.4
        assert final["motion"] == "G0"
        assert final["distance"] == "G90"
        assert final["units"] == "G21"
        assert final["plane"] == "G17"
        assert final["spindle"] == "M5"
        assert final["feed"] == 2800.0
        assert final["speed"] == 18000.0


# ============================================================
# Validator-level expectations
# ============================================================

class TestRegressionValidators:

    def test_no_startup_sequence_issues(self):
        parsed = _load()
        assert validate_startup_sequence(parsed) == []

    def test_two_cutting_operations(self):
        parsed = _load()
        ops = group_operations(parsed)
        assert len(ops) == 2

    def test_depth_profile_two_clusters(self):
        parsed = _load()
        ops = group_operations(parsed)
        profile = profile_operation_depths(ops)
        assert len(profile) == 2

    def test_depth_profile_values(self):
        parsed = _load()
        ops = group_operations(parsed)
        profile = profile_operation_depths(ops)
        # Sorted ascending (deepest first)
        assert profile[0]["depth"] == -9.525
        assert profile[1]["depth"] == -3.31
        # Each cluster should have one operation
        assert profile[0]["count"] == 1
        assert profile[1]["count"] == 1

    def test_no_spindle_or_feed_issues(self):
        parsed = _load()
        assert validate_spindle_and_feed(parsed) == []
