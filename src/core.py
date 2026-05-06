#!/usr/bin/env python3

# ============================================
# G-CODE AUDIT ENGINE — CORE
# ============================================
#
# Parser, tokenizer, modal state model, and modal-group constants.
# Validators live in src/validators/ and import from this module.
#
# Versioning is tracked via git tags (v5, v6, ...) — filenames no
# longer carry version suffixes.
#
# Behavior is unchanged from gcode_audit_v4_050526.py; this file is
# the result of a structural-only split (v6).
#
# Parser output shape:
#   {
#     "lines": [ { "line_index", "state", "tokens", "line_type" }, ... ],
#     "parser_issues": [ { ... }, ... ]
#   }
#
# Known limitations carried forward:
#   - G92 (set-position) coordinate offsets not tracked.
#   - Arc geometry not validated.
#   - "Safe Z" still hardcoded as Z > 0 (in startup validator).

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
#
# These constants are public — validator modules legitimately import
# them. The leading-underscore convention from the single-file era
# was dropped during the v6 split.

# Motion modes (group 1)
MOTION_CODES = {"G0", "G1", "G2", "G3", "G38.2", "G80", "G81", "G82", "G83"}

# Plane selection (group 2)
PLANE_CODES = {"G17", "G18", "G19"}

# Distance mode (group 3)
DISTANCE_CODES = {"G90", "G91"}

# Units (group 6)
UNITS_CODES = {"G20", "G21"}

# Spindle (M-code group)
SPINDLE_ON_CODES = {"M3", "M4"}
SPINDLE_OFF_CODES = {"M5"}

# Coolant (M-code group)
COOLANT_ON_CODES = {"M7", "M8"}
COOLANT_OFF_CODES = {"M9"}


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

    The "parser_issues" list surfaces issues detected during parsing
    itself (e.g. G91 incremental motion with no prior position). It
    is always present, possibly empty.
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
            if token in MOTION_CODES:
                state["motion"] = token
            elif token in PLANE_CODES:
                state["plane"] = token
            elif token in DISTANCE_CODES:
                state["distance"] = token
            elif token in UNITS_CODES:
                state["units"] = token
            # Other G-codes (G54, G94, G4, etc.) are not modal in groups
            # we currently track. They're preserved in the tokens list.

        elif letter == "M":
            if token in SPINDLE_ON_CODES:
                state["spindle"] = token
            elif token in SPINDLE_OFF_CODES:
                state["spindle"] = token
            elif token in COOLANT_ON_CODES:
                state["coolant"] = token
            elif token in COOLANT_OFF_CODES:
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
