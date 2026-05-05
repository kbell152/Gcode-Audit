"""
Tests for the parser layer: tokenization, comment stripping, line
classification, and modal state propagation.

These tests lock in the parser's contract — they should remain green
across all future versions unless we deliberately change the parser
contract (in which case the tests get updated alongside the change).
"""

from gcode_audit_v4_050526 import parse_gcode_lines, tokenize, strip_comments


# ============================================================
# Tokenizer
# ============================================================

class TestTokenizer:
    """Tokenizer should handle all valid G-code word formats."""

    def test_space_separated_tokens(self):
        assert tokenize("G1 X10 Y20") == ["G1", "X10", "Y20"]

    def test_no_space_tokens(self):
        """G1X10Y20 is a valid form many controllers and post-processors emit."""
        assert tokenize("G1X10Y20Z-1.5") == ["G1", "X10", "Y20", "Z-1.5"]

    def test_zero_padded_g_code_normalized(self):
        """G01 must normalize to G1 (Fanuc/Haas post-processors emit zero-padded)."""
        assert tokenize("G01 X10.0") == ["G1", "X10.0"]

    def test_zero_padded_m_code_normalized(self):
        """M03 must normalize to M3 (same reason)."""
        assert tokenize("M03 S18000") == ["M3", "S18000"]

    def test_g00_normalized_to_g0(self):
        assert tokenize("G00 X10") == ["G0", "X10"]

    def test_negative_coordinates_preserved(self):
        assert tokenize("X-1.5 Y-2.0 Z-0.001") == ["X-1.5", "Y-2.0", "Z-0.001"]

    def test_decimal_coordinates_preserved(self):
        assert tokenize("X10.123 Y20.456") == ["X10.123", "Y20.456"]

    def test_mixed_case_normalized_to_upper(self):
        assert tokenize("g1 x10 y20") == ["G1", "X10", "Y20"]

    def test_arc_parameters(self):
        assert tokenize("G2 X10 Y20 I5 J0") == ["G2", "X10", "Y20", "I5", "J0"]

    def test_empty_string_yields_no_tokens(self):
        assert tokenize("") == []

    def test_whitespace_only_yields_no_tokens(self):
        assert tokenize("   \t  ") == []


# ============================================================
# Comment stripping
# ============================================================

class TestCommentStripping:
    """Both () and ; comment styles should be removed before tokenization."""

    def test_parenthetical_comment_at_end_of_line(self):
        result = strip_comments("G1 X10 (rapid here)")
        assert "(" not in result and ")" not in result
        assert "G1 X10" in result

    def test_parenthetical_comment_mid_line(self):
        """Mid-line comments are common in some post-processor output."""
        result = strip_comments("G1 X10 (note) Y20")
        # After stripping, both G1 X10 and Y20 should remain
        assert "G1" in result and "X10" in result and "Y20" in result
        assert "(" not in result

    def test_multiple_parenthetical_comments(self):
        result = strip_comments("X10 (a) Y20 (b) Z5")
        for tok in ("X10", "Y20", "Z5"):
            assert tok in result
        assert "(" not in result

    def test_semicolon_comment_to_end_of_line(self):
        result = strip_comments("G1 X10 ; this is a comment")
        assert "G1 X10" in result
        assert ";" not in result
        assert "comment" not in result

    def test_semicolon_overrides_parens_after_it(self):
        """Anything after ; including unmatched parens is dropped."""
        result = strip_comments("G1 X10 ; (this stays inside the comment)")
        assert "G1 X10" in result
        assert "this" not in result

    def test_entire_line_comment(self):
        """Whole-line () comment should produce empty/whitespace string."""
        result = strip_comments("(entire line is a comment)")
        assert result.strip() == ""


# ============================================================
# Line classification
# ============================================================

class TestLineClassification:
    """Every line gets a line_type: CODE, COMMENT, or EMPTY."""

    def test_blank_line_classified_empty(self):
        parsed = parse_gcode_lines([""])
        assert parsed["lines"][0]["line_type"] == "EMPTY"

    def test_whitespace_only_classified_empty(self):
        parsed = parse_gcode_lines(["   \t  "])
        assert parsed["lines"][0]["line_type"] == "EMPTY"

    def test_pure_comment_classified_comment(self):
        parsed = parse_gcode_lines(["(this is a comment)"])
        assert parsed["lines"][0]["line_type"] == "COMMENT"

    def test_semicolon_only_line_classified_comment(self):
        parsed = parse_gcode_lines(["; just a comment"])
        assert parsed["lines"][0]["line_type"] == "COMMENT"

    def test_code_line_classified_code(self):
        parsed = parse_gcode_lines(["G1 X10"])
        assert parsed["lines"][0]["line_type"] == "CODE"

    def test_code_with_inline_comment_classified_code(self):
        parsed = parse_gcode_lines(["G1 X10 (inline)"])
        assert parsed["lines"][0]["line_type"] == "CODE"


# ============================================================
# State persistence
# ============================================================

class TestStatePersistence:
    """Modal state values carry forward unchanged unless overwritten."""

    def test_position_persists_through_blank_lines(self):
        parsed = parse_gcode_lines(["G90", "G0 X10 Y20", "", "", "G1 Z-1"])
        # The blank lines should preserve X=10 and Y=20
        for entry in parsed["lines"]:
            if entry["line_type"] == "EMPTY":
                assert entry["state"]["X"] == 10.0
                assert entry["state"]["Y"] == 20.0

    def test_motion_mode_inherited_on_continuation_line(self):
        """A line with no G-code inherits the previous motion mode."""
        parsed = parse_gcode_lines(["G90", "G1 X10 F100", "X20", "X30"])
        assert parsed["lines"][2]["state"]["motion"] == "G1"
        assert parsed["lines"][3]["state"]["motion"] == "G1"

    def test_feed_rate_persists_until_changed(self):
        parsed = parse_gcode_lines(["G1 F100", "X10", "X20 F200", "X30"])
        assert parsed["lines"][0]["state"]["feed"] == 100.0
        assert parsed["lines"][1]["state"]["feed"] == 100.0
        assert parsed["lines"][2]["state"]["feed"] == 200.0
        assert parsed["lines"][3]["state"]["feed"] == 200.0

    def test_spindle_state_tracked(self):
        parsed = parse_gcode_lines(["M3 S1000", "G1 X10", "M5"])
        assert parsed["lines"][0]["state"]["spindle"] == "M3"
        assert parsed["lines"][0]["state"]["speed"] == 1000.0
        assert parsed["lines"][2]["state"]["spindle"] == "M5"

    def test_tool_number_tracked(self):
        parsed = parse_gcode_lines(["T5 M6", "G1 X10"])
        assert parsed["lines"][0]["state"]["tool"] == 5
        assert parsed["lines"][1]["state"]["tool"] == 5


# ============================================================
# Modal G-codes captured
# ============================================================

class TestModalCodes:
    """The various modal G-code groups should each update their state slot."""

    def test_g90_captured_as_distance(self):
        parsed = parse_gcode_lines(["G90"])
        assert parsed["lines"][0]["state"]["distance"] == "G90"

    def test_g21_captured_as_units(self):
        parsed = parse_gcode_lines(["G21"])
        assert parsed["lines"][0]["state"]["units"] == "G21"

    def test_g17_captured_as_plane(self):
        parsed = parse_gcode_lines(["G17"])
        assert parsed["lines"][0]["state"]["plane"] == "G17"

    def test_motion_modes_captured(self):
        for code in ("G0", "G1", "G2", "G3"):
            parsed = parse_gcode_lines([code])
            assert parsed["lines"][0]["state"]["motion"] == code

    def test_unknown_g_code_does_not_set_motion(self):
        """G54 (work coordinate) is not a motion code and shouldn't pollute motion state."""
        parsed = parse_gcode_lines(["G1 X10", "G54"])
        # motion should still be G1 after the G54 line
        assert parsed["lines"][1]["state"]["motion"] == "G1"


# ============================================================
# Parser output shape (contract)
# ============================================================

class TestParserOutputShape:
    """The parser output dict shape is part of the public contract."""

    def test_returns_dict_with_lines_key(self):
        parsed = parse_gcode_lines(["G1 X10"])
        assert isinstance(parsed, dict)
        assert "lines" in parsed
        assert isinstance(parsed["lines"], list)

    def test_returns_parser_issues_key(self):
        """parser_issues key is always present, even if empty."""
        parsed = parse_gcode_lines(["G1 X10"])
        assert "parser_issues" in parsed
        assert isinstance(parsed["parser_issues"], list)

    def test_each_line_entry_has_required_keys(self):
        parsed = parse_gcode_lines(["G1 X10"])
        entry = parsed["lines"][0]
        for key in ("line_index", "state", "tokens", "line_type"):
            assert key in entry

    def test_line_indices_are_one_based(self):
        parsed = parse_gcode_lines(["G1 X10", "G1 X20", "G1 X30"])
        assert parsed["lines"][0]["line_index"] == 1
        assert parsed["lines"][1]["line_index"] == 2
        assert parsed["lines"][2]["line_index"] == 3

    def test_state_is_independent_per_line(self):
        """Each entry's state must be a snapshot, not a shared reference."""
        parsed = parse_gcode_lines(["G0 X10", "G0 X20"])
        # If they were shared, both would show X=20
        assert parsed["lines"][0]["state"]["X"] == 10.0
        assert parsed["lines"][1]["state"]["X"] == 20.0


# ============================================================
# Defensive input handling
# ============================================================

class TestInputValidation:
    """Parser should reject obviously-bad inputs cleanly, not crash mysteriously."""

    def test_non_list_input_raises_value_error(self):
        import pytest
        with pytest.raises(ValueError):
            parse_gcode_lines("G1 X10")  # passed a string instead of list

    def test_non_string_line_raises_value_error(self):
        import pytest
        with pytest.raises(ValueError):
            parse_gcode_lines(["G1 X10", 42, "G1 X20"])

    def test_empty_input_returns_empty_lines(self):
        parsed = parse_gcode_lines([])
        assert parsed["lines"] == []
        assert parsed["parser_issues"] == []
