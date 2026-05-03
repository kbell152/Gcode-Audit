# Changelog

All notable changes to the G-Code Audit Engine are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project follows simple integer versioning (v1, v2, v3, ...) for now;
semantic versioning may be adopted later.

Each version entry includes:
- **Scope** — one-line summary of what this pass focused on
- **Added / Changed / Fixed / Deferred** — categorized changes
- **Test results** — what was run, what passed, regressions checked
- **Notes** — anything else worth recording

---

## [v3] — 2026-05-02

**File:** `src/gcode_audit_v3_050226.py`
**Scope:** Parser expansion + tokenizer rewrite + M03/M3 normalization fix.
No new validators added in this pass (deliberate — scoped per agreement).

### Added

- **Full modal state tracking.** The per-line `state` dict now carries motion
  mode (G0/G1/G2/G3), distance (G90/G91), units (G20/G21), plane
  (G17/G18/G19), spindle (M3/M4/M5), coolant (M7/M8/M9), feed (F), speed (S),
  and tool (T) — in addition to X/Y/Z position.
- **Line classification.** Each parsed line is tagged `line_type`: `CODE`,
  `COMMENT`, or `EMPTY`. Validators can filter to CODE-only lines without
  re-checking token contents.
- **Comment handling.** Both parenthetical `(...)` and semicolon-to-end-of-line
  `;...` styles are stripped before tokenization. Multi-comment lines and
  inline mid-line comments (`X10 (note) Y20`) work correctly.

### Changed

- **Tokenizer rewrite.** Replaced naive `str.split()` with a regex-based
  G-code word tokenizer. Now handles space-separated form (`G1 X10 Y20`),
  no-space form (`G1X10Y20`), and mid-line comments correctly.
- **Code normalization.** Numeric G/M/T codes are normalized at parse time:
  `G01` → `G1`, `M03` → `M3`, `G00` → `G0`. This single change eliminates an
  entire class of false negatives from real-world post-processor output.
- **Spindle/feed validator rewrite.** `validate_spindle_and_feed` now reads
  modal state instead of re-scanning raw tokens. Cleaner code, and the
  M03/M3 normalization fix flows through automatically.
- **Modal inheritance verified.** Continuation lines without an explicit
  G-code (e.g. `Z-1.058` after a prior `G1`) correctly inherit the active
  motion mode. Verified end-to-end against test.gcode.

### Fixed

- **M03/M3 mismatch in spindle validator (v2 bug).** v2's spindle/feed
  validator used `"M3" in upper_tokens`, which silently failed to match
  zero-padded `M03` emitted by Fanuc, Haas, and many other post-processors.
  Fixed by normalizing at the parser level.
- **Empty-line handling.** v2 raised `ValueError` on blank lines, making it
  unable to run on most real-world G-code. Now blank lines are recorded as
  `line_type: "EMPTY"` and state is preserved.
- **Comment-only line handling.** Lines that are entirely `(...)` comments
  no longer break parsing.

### Deferred

- **G91 incremental coordinate interpretation.** Parser tracks distance mode
  in state but does not yet *interpret* G91 incremental coordinates — X/Y/Z
  values are always treated as absolute. There is a `TODO` comment in
  `_apply_tokens_to_state` flagging this. Programs using G91 will produce
  inaccurate position state. **Recommended for next pass.**
- **Arc geometry validation.** G2/G3 arcs are tokenized correctly and motion
  mode is captured, but the actual arc path (using I/J/K offsets or R radius)
  is not yet computed. Future audits like "arc with invalid geometry" will
  need an arc-resolution helper.
- **Configurable safe Z.** Inherited from v2 — "safe Z" is hardcoded as
  `Z > 0`. Should become machine-config-driven before this tool is used
  across different setups.
- **Malformed token surfacing.** If a coordinate fails to parse as a float,
  the parser silently skips it without emitting any issue. Worth adding a
  low-severity informational issue type later.
- **Module split.** Per the agreed structure, the next pass should split
  the engine into core + per-validator files before adding new validators.

### Test Results

Run against `tests/gcode/test.gcode` (Autodesk Fusion / OpenBuilds GRBL
post-processor output, 110 lines, 2 cutting operations):

| Check               | v2 result                  | v3 result                              | Status   |
|---------------------|----------------------------|----------------------------------------|----------|
| Lines parsed        | 110                        | 110 (64 code / 39 comment / 7 empty)   | ✓ match  |
| Sequence issues     | (none)                     | (none)                                 | ✓ match  |
| Operations found    | 2                          | 2                                      | ✓ match  |
| Depth profile       | -9.5250 (1), -3.3100 (1)   | -9.5250 (1), -3.3100 (1)               | ✓ match  |
| Spindle/feed issues | (none)                     | (none)                                 | ✓ match  |
| Final modal state   | n/a                        | G0, G90, G21, G17, M5, F2800, S18000   | ✓ new    |

**Edge case spot-checks** (run separately):
- No-space tokens: `G1X10Y20Z-1.5` → `['G1', 'X10', 'Y20', 'Z-1.5']`
- Zero-padded G code: `G01 X10.0 Y20.0` → `['G1', 'X10.0', 'Y20.0']`
- Zero-padded M code: `M03 S18000` → `['M3', 'S18000']`
- Inline comment: `G1 X10 (rapid here) Y20` → `['G1', 'X10', 'Y20']`
- Semicolon comment: `G1 X10 ; comment` → `['G1', 'X10']`

### Notes

- Backward-compatible: parser output shape unchanged, existing validators
  work without modification.
- Marks the transition from "auditor AI" mode to "single trusted voice"
  mode per project-management decision. Dual-AI checks-and-balances
  retired in favor of human-in-the-loop review by Larry and project owner.

---

## [v2] — 2026-05-01

**File:** `g-code_verification_v1.py` (milestone 050126_v2, "HARDENED")
**Scope:** Add spindle/feed validation; harden parser against real-world input.

### Added

- **`validate_spindle_and_feed`** — first validator that reads G-code
  semantics beyond X/Y/Z. Detects cutting motion (G1/G2/G3) while spindle
  is off, before spindle activation, or without a feed rate set.
- **`profile_operation_depths`** — clusters operations by min Z within
  tolerance, replacing the v1 baseline-comparison approach.
- **Empty-line tolerance.** Blank lines are now recorded as `line_type:
  "EMPTY"` with state preserved instead of raising `ValueError`.
- **Comment-only line tolerance.** Lines starting with `(` and ending with
  `)` are recorded as `line_type: "COMMENT"`.

### Changed

- **Malformed token handling.** Tokens that fail float parsing are now
  preserved with an `INVALID:` prefix instead of crashing the parser.
  (Note: nothing downstream consumes these markers — addressed in v3
  follow-up planning.)

### Known issues at v2 (carried into v3 backlog)

- Parser still only tracks X/Y/Z in `state`; modal commands (G90/G91/G20/G21
  etc.) are not retained beyond the tokens list.
- Spindle validator uses literal token match (`"M3" in upper_tokens`),
  which fails on zero-padded forms like `M03`. **(Fixed in v3.)**
- Tokenizer relies on `str.split()`, which fails on no-space token forms
  like `G1X10Y20`. **(Fixed in v3.)**
- Inline mid-line comments are not handled. **(Fixed in v3.)**

### Notes

- This was the version Larry handed off when work transferred from
  ChatGPT-driven development.

---
