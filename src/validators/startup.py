"""
Startup-sequence validator.

Detects cutting motion or XY motion before a "safe Z" height has been
established. The safe-Z threshold is read from config.CLEARANCE_HEIGHT
(default 0.0, matching the historical Z > 0 heuristic this validator
used prior to v7).

Behavior with the default CLEARANCE_HEIGHT of 0.0 is identical to the
pre-v7 implementation: Z strictly greater than the threshold is safe;
Z at or below the threshold is treated as a cut.
"""

from config import CLEARANCE_HEIGHT


def validate_startup_sequence(parser_output, clearance_height=None):
    """
    Detect cutting motion or XY motion before a safe Z height is
    established.

    Args:
        parser_output: dict returned by core.parse_gcode_lines.
        clearance_height: optional override for the safe-Z threshold.
            If None, uses config.CLEARANCE_HEIGHT.
    """
    if not isinstance(parser_output, dict):
        raise ValueError("Invalid parser_output: expected dict")

    lines = parser_output.get("lines")
    if not isinstance(lines, list):
        raise ValueError("Invalid parser_output: 'lines' must be list")

    threshold = CLEARANCE_HEIGHT if clearance_height is None else clearance_height

    safe_z_line = None
    first_xy_line = None
    first_cut_line = None
    issues = []
    prev_x = None
    prev_y = None

    for entry in lines:
        if not isinstance(entry, dict):
            raise ValueError("Invalid line entry: expected dict")
        if "line_index" not in entry or "state" not in entry:
            raise ValueError("Invalid line entry: missing required keys")

        idx = entry["line_index"]
        state = entry["state"]
        if not isinstance(state, dict):
            raise ValueError(f"Invalid state at line {idx}")

        x = state.get("X")
        y = state.get("Y")
        z = state.get("Z")

        if safe_z_line is None and z is not None and z > threshold:
            safe_z_line = idx

        if first_xy_line is None:
            if (x is not None and prev_x is not None and x != prev_x) or (
                y is not None and prev_y is not None and y != prev_y
            ):
                first_xy_line = idx

        if first_cut_line is None and z is not None and z <= threshold:
            first_cut_line = idx

        prev_x = x if x is not None else prev_x
        prev_y = y if y is not None else prev_y

    if first_cut_line is not None:
        if safe_z_line is None or first_cut_line < safe_z_line:
            issues.append({
                "type": "SEQUENCE_ERROR",
                "severity": "CRITICAL",
                "line_index": first_cut_line,
                "message": "Cut occurred before safe Z was established",
            })

    if first_xy_line is not None:
        if safe_z_line is None or first_xy_line < safe_z_line:
            if not (first_cut_line is not None and first_cut_line == first_xy_line):
                issues.append({
                    "type": "SEQUENCE_ERROR",
                    "severity": "WARNING",
                    "line_index": first_xy_line,
                    "message": "XY motion occurred before safe Z",
                })

    return issues
