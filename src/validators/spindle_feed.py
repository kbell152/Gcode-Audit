"""
Spindle / feed validator.

Detects cutting motions (G1/G2/G3) that occur while the spindle is off
(M5), has never been turned on, or no feed rate has been declared.

Reads modal state from the parser output rather than re-scanning tokens,
so M03/M3 normalization done in the parser is automatically honored.
"""

from core import SPINDLE_ON_CODES, SPINDLE_OFF_CODES


def validate_spindle_and_feed(parser_output):
    """
    Detect cutting motions (G1/G2/G3) that occur while:
      - the spindle has been turned off (M5),
      - the spindle has never been turned on,
      - no feed rate has been declared.

    Each issue type is reported once per offense window (suppressed
    until the underlying state changes back) to avoid log spam.
    """
    if not isinstance(parser_output, dict):
        raise ValueError("Invalid parser_output")

    lines = parser_output.get("lines")
    if not isinstance(lines, list):
        raise ValueError("Invalid parser_output: 'lines' must be list")

    issues = []

    spindle_off_reported = False
    spindle_missing_reported = False
    feed_missing_reported = False

    cutting_motions = {"G1", "G2", "G3"}

    for entry in lines:
        if not isinstance(entry, dict):
            raise ValueError("Invalid entry in lines")
        if "line_index" not in entry or "state" not in entry:
            raise ValueError("Malformed entry in parser output")

        # Skip non-code lines
        if entry.get("line_type") != "CODE":
            continue

        idx = entry["line_index"]
        state = entry["state"]
        if not isinstance(state, dict):
            raise ValueError(f"Invalid state at line {idx}")

        motion = state.get("motion")
        spindle = state.get("spindle")
        feed = state.get("feed")

        # Reset suppression flags when underlying state recovers.
        if spindle in SPINDLE_ON_CODES:
            spindle_off_reported = False
            spindle_missing_reported = False
        if feed is not None:
            feed_missing_reported = False

        # Only flag on lines that are actually cutting moves.
        if motion not in cutting_motions:
            continue

        if spindle in SPINDLE_OFF_CODES and not spindle_off_reported:
            issues.append({
                "type": "SPINDLE_ERROR",
                "severity": "CRITICAL",
                "line_index": idx,
                "message": "Cutting motion detected while spindle is OFF",
            })
            spindle_off_reported = True

        if spindle is None and not spindle_missing_reported:
            issues.append({
                "type": "SPINDLE_WARNING",
                "severity": "WARNING",
                "line_index": idx,
                "message": "Cutting motion before spindle activation",
            })
            spindle_missing_reported = True

        if feed is None and not feed_missing_reported:
            issues.append({
                "type": "FEED_WARNING",
                "severity": "WARNING",
                "line_index": idx,
                "message": "Cutting motion without feed rate",
            })
            feed_missing_reported = True

    return issues
