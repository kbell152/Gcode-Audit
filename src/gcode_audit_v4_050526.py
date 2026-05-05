#!/usr/bin/env python3

# ============================================
# G-CODE AUDIT ENGINE
# Version: v4
# Date:    05/05/26
# File:    gcode_audit_v4_050526.py
# ============================================
#
# This pass: G91 incremental coordinate interpretation.
# No new validators added in this pass.
#
# Changes from v3:
#   - When state["distance"] == "G91", X/Y/Z words are now interpreted
#     incrementally (added to previous position) instead of being treated
#     as absolute. When state["distance"] == "G90" or is None, X/Y/Z are
#     interpreted as absolute (unchanged from v3 behavior).
#   - G/M codes on a line are applied BEFORE coordinate words, so a line
#     like "G91 X10" correctly takes G91 into account when interpreting
#     X10. (Previously token order would have mattered.)
#   - When G91 is active but no prior position exists for an axis (i.e.
#     state["X"] is None and we see X10 in incremental mode), the value
#     is treated as absolute for that axis on that line. An informational
#     issue is recorded in a new top-level "parser_issues" list in the
#     return value of parse_gcode_lines.
#
# Parser output shape (v4 — additive, backward-compatible):
#   {
#     "lines": [ { "line_index", "state", "tokens", "line_type" }, ... ],
#     "parser_issues": [ { ... }, ... ]   # NEW in v4, may be empty
#   }
#
# All existing validators continue to read parser_output["lines"] and
# work unchanged. Validators that want to surface parser-level issues
# can read parser_output.get("parser_issues", []).
#
# Known limitations carried forward (not addressed in this pass):
#   - G92 (set-position) coordinate offsets not tracked.
#   - Arc geometry not validated.
#   - "Safe Z" still hardcoded as Z > 0.

import re


# ============================================
# TOKENIZER
# ============================================

# A G-code "word" is a single letter followed by a signed number.
# Number may be int, float, or have a leading sign.
# We use a regex so that "G1X10Y20" tokenizes as ["G1", "X10", "Y20"]
# regardless of spacing.
_WORD_RE = re.compile(r"([A-Za-z])\s*([+-]?\d*\.?\d+)")


def strip_comments(line):
    """
    Remove G-code comments from a line.
    Supports both "(...)" inline/parenthetical and ";..." to end-of-line.
    Parenthetical comments may appear mid-line and are removed in place.
    Returns the cleaned line (may be empty after stripping).
    """
    if not isinstance(line, str):
        raise ValueError("strip_comments expected a string")

    # Remove ;-style comments (everything from ; to end of line)
    semi_idx = line.find(";")
    if semi_idx != -1:
        line = line[:semi_idx]

    # Remove parenthetical comments. Use a non-greedy match.
    # Note: real G-code does not nest parentheses, so this is safe.
    line = re.sub(r"\([^)]*\)", " ", line)

    return line


def tokenize(line):
    """
    Tokenize a G-code line (with comments already stripped) into a list
    of normalized word tokens, e.g. ["G1", "X10.0", "Y20.5"].

    Numeric codes are normalized: G01 -> G1, M03 -> M3, G00 -> G0, etc.
    This applies only to G/M/T words where the number is an integer code,
    not to coordinate/parameter words like X, Y, Z, F, S, I, J, K, R, P.
    """
    if not isinstance(line, str):
        raise ValueError("tokenize expected a string")

    matches = _WORD_RE.findall(line)
    tokens = []
    for letter, number in matches:
        letter = letter.upper()
        # Normalize integer codes for G, M, T (drop leading zeros).
        # Coordinate/parameter words keep their numeric form as-is.
        if letter in ("G", "M", "T"):
            try:
                # G/M/T codes are typically integer-valued.
                # If someone writes G1.1 it's preserved as float string.
                if "." in number:
                    n_val = float(number)
                    if n_val.is_integer():
                        tokens.append(f"{letter}{int(n_val)}")
                    else:
                        tokens.append(f"{letter}{n_val}")
                else:
                    tokens.append(f"{letter}{int(number)}")
            except ValueError:
                tokens.append(f"{letter}{number}")
        else:
            tokens.append(f"{letter}{number}")
    return tokens


# ============================================
# MODAL GROUPS
# ============================================
#
# G-code organizes commands into modal groups. Within a group, only
# one command is active at a time, and it persists until replaced.
# Reference: NIST RS274/NGC modal group definitions.

# Motion modes (group 1)
_MOTION_CODES = {"G0", "G1", "G2", "G3", "G38.2", "G80", "G81", "G82", "G83"}

# Plane selection (group 2)
_PLANE_CODES = {"G17", "G18", "G19"}

# Distance mode (group 3)
_DISTANCE_CODES = {"G90", "G91"}

# Units (group 6)
_UNITS_CODES = {"G20", "G21"}

# Spindle (M-code group)
_SPINDLE_ON_CODES = {"M3", "M4"}
_SPINDLE_OFF_CODES = {"M5"}

# Coolant (M-code group)
_COOLANT_ON_CODES = {"M7", "M8"}
_COOLANT_OFF_CODES = {"M9"}


# ============================================
# PARSER
# ============================================


def parse_gcode_lines(raw_lines):
    """
    Parse a list of raw G-code lines into structured per-line entries
    with full modal state tracking.

    Returns:
        {
          "lines": [
            {
              "line_index": int (1-based),
              "state": dict (full modal snapshot AFTER this line),
              "tokens": list of normalized tokens (empty for COMMENT/EMPTY),
              "line_type": "CODE" | "COMMENT" | "EMPTY"
            },
            ...
          ],
          "parser_issues": [
            {
              "type": str,
              "severity": str,
              "line_index": int,
              "message": str
            },
            ...
          ]
        }

    The "parser_issues" list is new in v4 and is used to surface issues
    detected during parsing itself (e.g. G91 incremental motion with no
    prior position). It is always present, possibly empty.
    """
    if not isinstance(raw_lines, list):
        raise ValueError("Input must be a list of G-code lines")

    parsed = []
    parser_issues = []

    # Full modal state. None means "not yet set" (no default assumed).
    # Defaults are deliberately NOT injected so the analyzer can detect
    # programs that fail to declare units, distance mode, etc.
    state = {
        # Position (set by coordinate words)
        "X": None,
        "Y": None,
        "Z": None,
        # Modal groups
        "motion": None,         # G0 / G1 / G2 / G3 / etc.
        "distance": None,       # G90 (absolute) / G91 (incremental)
        "units": None,          # G20 (inch) / G21 (mm)
        "plane": None,          # G17 / G18 / G19
        "spindle": None,        # M3 / M4 / M5
        "coolant": None,        # M7 / M8 / M9
        # Parameter modals
        "feed": None,           # F value
        "speed": None,          # S value
        "tool": None,           # T value
    }

    for i, raw_line in enumerate(raw_lines, start=1):

        if not isinstance(raw_line, str):
            raise ValueError(f"Invalid line at index {i}: expected string")

        original = raw_line
        stripped = original.strip()

        # Classify empty
        if stripped == "":
            parsed.append({
                "line_index": i,
                "state": state.copy(),
                "tokens": [],
                "line_type": "EMPTY",
            })
            continue

        # Strip comments and check what remains
        cleaned = strip_comments(stripped).strip()

        if cleaned == "":
            # Line was entirely a comment
            parsed.append({
                "line_index": i,
                "state": state.copy(),
                "tokens": [],
                "line_type": "COMMENT",
            })
            continue

        # Tokenize the cleaned line
        tokens = tokenize(cleaned)

        if not tokens:
            # Line had content but produced no recognizable tokens.
            # Treat as COMMENT-equivalent for state purposes but mark
            # explicitly so it's traceable.
            parsed.append({
                "line_index": i,
                "state": state.copy(),
                "tokens": [],
                "line_type": "COMMENT",
            })
            continue

        # Apply tokens to state. _apply_tokens_to_state may append to
        # parser_issues for parser-level concerns (e.g. G91 with no
        # prior position).
        _apply_tokens_to_state(tokens, state, line_index=i,
                               parser_issues=parser_issues)

        parsed.append({
            "line_index": i,
            "state": state.copy(),
            "tokens": tokens,
            "line_type": "CODE",
        })

    return {"lines": parsed, "parser_issues": parser_issues}


def _apply_tokens_to_state(tokens, state, line_index, parser_issues):
    """
    Update the modal state dict in place based on the tokens on one line.

    Two-pass approach:
      Pass 1: Apply G-codes and M-codes (so any modal change like G90/G91
              takes effect BEFORE coordinate words are interpreted).
      Pass 2: Apply coordinate words (X/Y/Z) and parameter words (F/S/T)
              using the now-current modal state. X/Y/Z interpretation
              depends on state["distance"]:
                - "G91": value is added to previous position (incremental)
                - "G90" or None: value replaces previous position (absolute)

    G91 edge cases:
      - If G91 is active but no prior position exists for an axis (state
        is None), the value is treated as absolute for that axis on that
        line, and an INCREMENTAL_NO_PRIOR informational issue is added
        to parser_issues.

    Unknown tokens are silently ignored at the parser level (they remain
    in the tokens list for downstream inspection).
    """
    # ----- Pass 1: G-codes and M-codes -----
    for token in tokens:
        if not token:
            continue
        letter = token[0]

        if letter == "G":
            if token in _MOTION_CODES:
                state["motion"] = token
            elif token in _PLANE_CODES:
                state["plane"] = token
            elif token in _DISTANCE_CODES:
                state["distance"] = token
            elif token in _UNITS_CODES:
                state["units"] = token
            # Other G-codes (G54, G94, G4, etc.) are not modal in groups
            # we currently track. They're preserved in the tokens list.

        elif letter == "M":
            if token in _SPINDLE_ON_CODES:
                state["spindle"] = token
            elif token in _SPINDLE_OFF_CODES:
                state["spindle"] = token
            elif token in _COOLANT_ON_CODES:
                state["coolant"] = token
            elif token in _COOLANT_OFF_CODES:
                state["coolant"] = token
            # Other M-codes (M6, M30, etc.) preserved in tokens list.

    # ----- Pass 2: coordinate words and parameter words -----
    incremental = (state["distance"] == "G91")

    for token in tokens:
        if not token:
            continue
        letter = token[0]
        rest = token[1:]

        if letter in ("X", "Y", "Z"):
            try:
                value = float(rest)
            except ValueError:
                # Malformed coordinate; skip silently (preserved in tokens)
                continue

            if incremental:
                prior = state[letter]
                if prior is None:
                    # G91 active but no prior position for this axis.
                    # Treat as absolute for this axis on this line, and
                    # record an informational issue.
                    state[letter] = value
                    parser_issues.append({
                        "type": "INCREMENTAL_NO_PRIOR",
                        "severity": "INFO",
                        "line_index": line_index,
                        "message": (
                            f"G91 incremental {letter}{value} with no "
                            f"prior {letter} position; treated as absolute"
                        ),
                    })
                else:
                    state[letter] = prior + value
            else:
                # G90 (absolute) or distance mode unset: replace.
                state[letter] = value

        elif letter == "F":
            try:
                state["feed"] = float(rest)
            except ValueError:
                pass
        elif letter == "S":
            try:
                state["speed"] = float(rest)
            except ValueError:
                pass
        elif letter == "T":
            try:
                state["tool"] = int(float(rest))
            except ValueError:
                pass
        # I, J, K, R, P, etc. are arc/parameter words used by the active
        # motion command; they don't update persistent modal state.


# ============================================
# STARTUP VALIDATION (UNCHANGED FROM v2)
# ============================================


def validate_startup_sequence(parser_output):
    """
    Detect cutting motion or XY motion before a safe Z height is
    established. "Safe Z" is currently defined as Z > 0 — this is a
    known assumption documented in the project notes.
    """
    if not isinstance(parser_output, dict):
        raise ValueError("Invalid parser_output: expected dict")

    lines = parser_output.get("lines")
    if not isinstance(lines, list):
        raise ValueError("Invalid parser_output: 'lines' must be list")

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

        if safe_z_line is None and z is not None and z > 0:
            safe_z_line = idx

        if first_xy_line is None:
            if (x is not None and prev_x is not None and x != prev_x) or (
                y is not None and prev_y is not None and y != prev_y
            ):
                first_xy_line = idx

        if first_cut_line is None and z is not None and z <= 0:
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


# ============================================
# OPERATION GROUPING (UNCHANGED FROM v2)
# ============================================


def group_operations(parser_output):
    """
    Group consecutive lines where Z <= 0 into "operations" (cutting
    sequences). Returns a list of {start_line, end_line, min_z, max_z}.
    """
    if not isinstance(parser_output, dict):
        raise ValueError("Invalid parser_output")

    lines = parser_output.get("lines")
    if not isinstance(lines, list):
        raise ValueError("Invalid parser_output: 'lines' must be list")

    operations = []
    current_op = None

    for entry in lines:
        if not isinstance(entry, dict):
            raise ValueError("Invalid entry in lines")
        if "line_index" not in entry or "state" not in entry:
            raise ValueError("Malformed entry in parser output")

        idx = entry["line_index"]
        state = entry["state"]
        if not isinstance(state, dict):
            raise ValueError(f"Invalid state at line {idx}")

        z = state.get("Z")

        if z is not None and z <= 0:
            if current_op is None:
                current_op = {
                    "start_line": idx,
                    "end_line": idx,
                    "min_z": z,
                    "max_z": z,
                }
            else:
                current_op["end_line"] = idx
                current_op["min_z"] = min(current_op["min_z"], z)
                current_op["max_z"] = max(current_op["max_z"], z)
        else:
            if current_op is not None:
                operations.append(current_op)
                current_op = None

    if current_op is not None:
        operations.append(current_op)

    return operations


# ============================================
# DEPTH PROFILING (UNCHANGED FROM v2)
# ============================================


def profile_operation_depths(operations, tolerance=0.01):
    """
    Cluster operations by their min_z depth (within tolerance) and
    return a sorted list of {depth, count} clusters.
    """
    if not isinstance(operations, list):
        raise ValueError("Invalid operations")

    clusters = []

    for op in operations:
        if not isinstance(op, dict):
            raise ValueError("Invalid operation entry")

        depth = op.get("min_z")
        if depth is None:
            continue

        matched = False
        for cluster in clusters:
            if abs(depth - cluster["depth"]) <= tolerance:
                cluster["count"] += 1
                matched = True
                break

        if not matched:
            clusters.append({"depth": depth, "count": 1})

    clusters.sort(key=lambda x: x["depth"])
    return clusters


# ============================================
# SPINDLE / FEED VALIDATION (REWRITTEN)
# ============================================
#
# This validator now reads modal state instead of re-scanning tokens
# on every line. As a side effect, the M03/M3 normalization bug from
# v2 is fixed: the parser normalizes both forms to "M3" before this
# validator ever sees them.


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
        if spindle in _SPINDLE_ON_CODES:
            spindle_off_reported = False
            spindle_missing_reported = False
        if feed is not None:
            feed_missing_reported = False

        # Only flag on lines that are actually cutting moves.
        if motion not in cutting_motions:
            continue

        if spindle in _SPINDLE_OFF_CODES and not spindle_off_reported:
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


# ============================================
# MAIN RUNNER
# ============================================

if __name__ == "__main__":

    # Default test file path — relative to repo root.
    # Adjust if running from a different location.
    import os
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
