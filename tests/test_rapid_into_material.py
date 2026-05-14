"""
Tests for validate_rapid_into_material.

The validator flags two distinct hazards on G0 (rapid) motions:

  RAPID_INTO_MATERIAL — G0 ends at Z at or below the clearance height.
  RAPID_BELOW_CLEARANCE — G0 with XY motion where the starting Z is at
    or below clearance (controller path order not guaranteed).

When a single line both plunges to unsafe Z and moves XY, only the
RAPID_INTO_MATERIAL flag fires — the plunge message already conveys
the underlying hazard.

Tests cover positive cases (each flag type, alone and combined), negative
cases (clean programs, G1 motions ignored, unknown-Z safe-haven), modal
motion carry-forward, G91 incremental motion, and the explicit
clearance_height override.
"""

from core import parse_gcode_lines
from validators import validate_rapid_into_material


class TestRapidIntoMaterial:

    # --------------------------------------------------------
    # Negative cases — clean programs should produce no flags
    # --------------------------------------------------------

    def test_clean_program_no_flags(self):
        """Standard program: lift to safe Z, traverse, plunge with G1 — no flags."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G0 Z5",          # establish safe Z
            "G0 X10 Y10",     # traverse at safe Z
            "G1 Z-1 F100",    # plunge with G1 (not G0)
            "G1 X20",         # cut
            "G0 Z5",          # retract
        ])
        assert validate_rapid_into_material(parsed) == []

    def test_g1_plunge_below_clearance_not_flagged(self):
        """G1 plunging below clearance is not this validator's concern."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G0 Z5",
            "G1 Z-5 F100",    # G1 plunge — should NOT flag
        ])
        assert validate_rapid_into_material(parsed) == []

    def test_g0_at_unknown_z_not_flagged(self):
        """G0 XY motion when Z has never been set is indeterminate, not flagged."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G0 X10 Y10",     # Z is None — we cannot claim a violation
        ])
        assert validate_rapid_into_material(parsed) == []

    def test_g0_retract_above_clearance_not_flagged(self):
        """G0 ending above clearance after a cut is the expected pattern."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G0 Z5",
            "G1 Z-1 F100",
            "G1 X10",
            "G0 Z5",          # retract via rapid to safe Z — should NOT flag
        ])
        assert validate_rapid_into_material(parsed) == []

    # --------------------------------------------------------
    # Positive cases — RAPID_INTO_MATERIAL (plunge)
    # --------------------------------------------------------

    def test_rapid_plunge_into_material_flagged(self):
        """G0 ending below clearance — the classic crash setup."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G0 Z5",
            "G0 Z-1",         # rapid plunge into material
        ])
        issues = validate_rapid_into_material(parsed)
        plunge = [i for i in issues if i["type"] == "RAPID_INTO_MATERIAL"]
        assert len(plunge) == 1
        assert plunge[0]["severity"] == "CRITICAL"
        assert plunge[0]["line_index"] == 3

    def test_rapid_to_exactly_clearance_flagged(self):
        """G0 ending exactly at clearance (Z=0) is at-or-below — flagged."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G0 Z5",
            "G0 Z0",          # exactly at clearance — should flag
        ])
        issues = validate_rapid_into_material(parsed)
        plunge = [i for i in issues if i["type"] == "RAPID_INTO_MATERIAL"]
        assert len(plunge) == 1

    # --------------------------------------------------------
    # Positive cases — RAPID_BELOW_CLEARANCE (traverse)
    # --------------------------------------------------------

    def test_rapid_traverse_below_clearance_flagged(self):
        """G0 XY motion while Z is below clearance — controller path ambiguous."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G0 Z5",
            "G1 Z-1 F100",    # legitimately get below clearance via G1
            "G0 X10 Y10",     # rapid XY while Z=-1 — should flag
        ])
        issues = validate_rapid_into_material(parsed)
        traverse = [i for i in issues if i["type"] == "RAPID_BELOW_CLEARANCE"]
        assert len(traverse) == 1
        assert traverse[0]["severity"] == "CRITICAL"
        assert traverse[0]["line_index"] == 4

    def test_rapid_retract_with_xy_motion_flagged(self):
        """G0 from unsafe Z to safe Z with XY motion is ambiguous (no Z-first guarantee)."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G0 Z5",
            "G1 Z-1 F100",
            "G0 X10 Y10 Z5",  # XY moves AND Z rises out of material — ambiguous
        ])
        issues = validate_rapid_into_material(parsed)
        # Start Z is unsafe (-1), end Z is safe (5). Per the design,
        # this fires RAPID_BELOW_CLEARANCE (start-Z-unsafe case),
        # but does NOT fire RAPID_INTO_MATERIAL (end-Z is safe).
        traverse = [i for i in issues if i["type"] == "RAPID_BELOW_CLEARANCE"]
        plunge = [i for i in issues if i["type"] == "RAPID_INTO_MATERIAL"]
        assert len(traverse) == 1
        assert len(plunge) == 0

    # --------------------------------------------------------
    # Single-flag-on-combined-hazard rule (row 2 of the design table)
    # --------------------------------------------------------

    def test_combined_plunge_and_xy_yields_only_plunge_flag(self):
        """G0 from safe Z plunging while XY moves: one flag, not two."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G0 Z5",
            "G0 X10 Y10 Z-5", # plunge + XY in one line, from safe start
        ])
        issues = validate_rapid_into_material(parsed)
        plunge = [i for i in issues if i["type"] == "RAPID_INTO_MATERIAL"]
        traverse = [i for i in issues if i["type"] == "RAPID_BELOW_CLEARANCE"]
        assert len(plunge) == 1
        assert len(traverse) == 0
        assert len(issues) == 1

    def test_combined_below_and_xy_yields_both_flags(self):
        """G0 from unsafe Z to deeper unsafe Z with XY motion: both flags fire."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G0 Z5",
            "G1 Z-1 F100",    # below clearance via G1
            "G0 X10 Y10 Z-2", # already below; XY moves; ends deeper below
        ])
        issues = validate_rapid_into_material(parsed)
        plunge = [i for i in issues if i["type"] == "RAPID_INTO_MATERIAL"]
        traverse = [i for i in issues if i["type"] == "RAPID_BELOW_CLEARANCE"]
        assert len(plunge) == 1
        assert len(traverse) == 1

    # --------------------------------------------------------
    # Modal motion carry-forward
    # --------------------------------------------------------

    def test_modal_g0_carry_forward_still_flagged(self):
        """A line with no explicit motion word inherits G0 modally — still flagged."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G0 Z5",
            "G0 X0 Y0",       # modal G0 set
            "Z-1",            # no motion word, but modal G0 active — rapid plunge
        ])
        issues = validate_rapid_into_material(parsed)
        plunge = [i for i in issues if i["type"] == "RAPID_INTO_MATERIAL"]
        assert len(plunge) == 1
        assert plunge[0]["line_index"] == 4

    def test_modal_g1_means_no_flag(self):
        """After G1 is active modally, a bare Z- line is a cut, not a rapid."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G0 Z5",
            "G1 X0 Y0 F100",  # modal G1 set
            "Z-1",            # bare Z under modal G1 — a cut, not a rapid
        ])
        assert validate_rapid_into_material(parsed) == []

    # --------------------------------------------------------
    # G91 incremental motion
    # --------------------------------------------------------

    def test_g91_incremental_plunge_flagged(self):
        """Rapid into material via G91 incremental motion is flagged correctly."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G0 Z5",          # absolute: Z=5
            "G91",            # switch to incremental
            "G0 Z-10",        # incremental: Z = 5 + (-10) = -5
        ])
        issues = validate_rapid_into_material(parsed)
        plunge = [i for i in issues if i["type"] == "RAPID_INTO_MATERIAL"]
        assert len(plunge) == 1

    # --------------------------------------------------------
    # Explicit clearance_height override
    # --------------------------------------------------------

    def test_explicit_clearance_height_override(self):
        """Passing clearance_height overrides the config default."""
        parsed = parse_gcode_lines([
            "G90 G21",
            "G0 Z10",
            "G0 Z3",          # safe under default (>0), unsafe under threshold=5
        ])
        # Under default (CLEARANCE_HEIGHT=0.0), Z=3 is safe.
        assert validate_rapid_into_material(parsed) == []
        # Under override threshold=5, Z=3 is at-or-below — flagged.
        issues = validate_rapid_into_material(parsed, clearance_height=5.0)
        plunge = [i for i in issues if i["type"] == "RAPID_INTO_MATERIAL"]
        assert len(plunge) == 1
