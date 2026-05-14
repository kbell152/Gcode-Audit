"""
Rapid-into-material validator.

Detects G0 (rapid) motions that interact unsafely with the clearance
plane:

  RAPID_INTO_MATERIAL — A G0 motion ends at or below the clearance
    height. The machine is rapiding *to* or *into* material, which is
    one of the most common ways a CNC program crashes.

  RAPID_BELOW_CLEARANCE — A G0 motion has XY component (X or Y
    changes) and either the starting Z or the ending Z is at or below
    the clearance height. The motion crosses, traverses through, or
    stays in the not-safe region while moving laterally. Controllers
    do not synchronize XY and Z within a single G0 block — the path
    is implementation-defined — so any G0 that straddles the
    clearance plane while changing XY is ambiguous and flagged.

Both issues are reported as CRITICAL.

This validator respects modal motion: a line with no explicit motion
word that follows a prior G0 is still treated as a rapid, since
state["motion"] reflects the active modal motion.
"""

from config import CLEARANCE_HEIGHT


def validate_rapid_into_material(parser_output, clearance_height=None):
    """
    Detect unsafe G0 motions relative to the clearance plane.

    Args:
        parser_output: dict returned by core.parse_gcode_lines.
        clearance_height: optional override for the safe-Z threshold.
            If None, uses config.CLEARANCE_HEIGHT.

    Returns:
        list of issue dicts, each with keys:
            type:     "RAPID_INTO_MATERIAL" | "RAPID_BELOW_CLEARANCE"
            severity: "CRITICAL"
            line_index: int (1-based)
            message: str
    """
    if not isinstance(parser_output, dict):
        raise ValueError("Invalid parser_output: expected dict")

    lines = parser_output.get("lines")
    if not isinstance(lines, list):
        raise ValueError("Invalid parser_output: 'lines' must be list")

    threshold = CLEARANCE_HEIGHT if clearance_height is None else clearance_height

    issues = []
    prev_x = None
    prev_y = None
    prev_z = None

    for entry in lines:
        if not isinstance(entry, dict):
            raise ValueError("Invalid line entry: expected dict")
        if "line_index" not in entry or "state" not in entry:
            raise ValueError("Invalid line entry: missing required keys")

        idx = entry["line_index"]
        state = entry["state"]
        if not isinstance(state, dict):
            raise ValueError(f"Invalid state at line {idx}")

        cur_x = state.get("X")
        cur_y = state.get("Y")
        cur_z = state.get("Z")
        motion = state.get("motion")

        # Only G0 (rapid) motions are this validator's concern. Modal
        # motion is respected: a line with no explicit motion word that
        # follows a prior G0 still has state["motion"] == "G0".
        #
        # A line where motion is G0 but no axis word appeared is a no-op
        # for path purposes; skip those by checking whether any of X/Y/Z
        # actually changed.
        xy_changed = (
            (cur_x is not None and prev_x is not None and cur_x != prev_x)
            or (cur_y is not None and prev_y is not None and cur_y != prev_y)
        )
        z_changed = (cur_z is not None and prev_z is not None and cur_z != prev_z)
        # First-occurrence handling: if prev_* is None, treat appearance
        # of a coordinate as a change so the initial G0 positioning move
        # is evaluated.
        if prev_x is None and cur_x is not None:
            xy_changed = xy_changed or True
        if prev_y is None and cur_y is not None:
            xy_changed = xy_changed or True
        if prev_z is None and cur_z is not None:
            z_changed = True

        is_rapid_with_motion = (motion == "G0") and (xy_changed or z_changed)

        if is_rapid_with_motion:
            # RAPID_INTO_MATERIAL — end Z at or below clearance.
            if cur_z is not None and cur_z <= threshold:
                issues.append({
                    "type": "RAPID_INTO_MATERIAL",
                    "severity": "CRITICAL",
                    "line_index": idx,
                    "message": (
                        f"G0 rapid ends at Z={cur_z} "
                        f"(at or below clearance height {threshold})"
                    ),
                })

            # RAPID_BELOW_CLEARANCE — XY motion straddles or stays in
            # the not-safe region. We check both endpoints: starting Z
            # at-or-below OR ending Z at-or-below triggers the flag,
            # because controllers don't guarantee Z-then-XY ordering
            # within a G0 block.
            if xy_changed:
                start_z_unsafe = (prev_z is not None and prev_z <= threshold)
                end_z_unsafe = (cur_z is not None and cur_z <= threshold)
                if start_z_unsafe or end_z_unsafe:
                    # Don't double-report: if RAPID_INTO_MATERIAL already
                    # fired on this line (end Z unsafe), and start Z is
                    # safe, the plunge flag is the more accurate one.
                    # Only add the traverse flag when start Z is unsafe
                    # — that's the case the plunge flag doesn't cover.
                    if start_z_unsafe:
                        issues.append({
                            "type": "RAPID_BELOW_CLEARANCE",
                            "severity": "CRITICAL",
                            "line_index": idx,
                            "message": (
                                f"G0 with XY motion while Z={prev_z} is at "
                                f"or below clearance height {threshold} "
                                f"(controller path order not guaranteed)"
                            ),
                        })

        prev_x = cur_x if cur_x is not None else prev_x
        prev_y = cur_y if cur_y is not None else prev_y
        prev_z = cur_z if cur_z is not None else prev_z

    return issues
