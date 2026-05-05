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

## [v4] — 2026-05-05

**File:** `src/gcode_audit_v4_050526.py`
**Scope:** G91 incremental coordinate interpretation. No new validators
added in this pass.

### Added

- **`parser_issues` in parse_gcode_lines return value.** New top-level
  list in the parser output, alongside `lines`. Used to surface issues
  detected during parsing itself (initially: G91 with no prior position).
  Always present, possibly empty.
- **`INCREMENTAL_NO_PRIOR` informational issue.** Emitted (per-axis) when
  G91 incremental motion is requested but no prior position exists for
  that axis. The value is treated as absolute for that axis on that line
  and execution continues — matching the behavior of most real
  controllers when reset.
- **Synthetic test suite for G91 behavior.** Seven test cases in
  `tests/test_g91.py` covering: pure G90, pure G91, G90↔G91 round trip,
  no-prior-position edge case, mid-line G-code/coordinate ordering, and
  mode persistence across continuation lines. All pass.

### Changed

- **`_apply_tokens_to_state` rewritten as a two-pass function.** Pass 1
  applies G-codes and M-codes (so any modal change like G90↔G91 takes
  effect first). Pass 2 applies coordinate words using the now-current
  modal state. This means a line like `G91 X10` correctly interprets X10
  as incremental even though the tokens are in source order.
- **X/Y/Z interpretation now respects distance mode.** When
  `state["distance"] == "G91"`, X/Y/Z values are added to the previous
  position (incremental). When G90 or unset, values replace the previous
  position (absolute, unchanged from v3). Position state is now
  trustworthy for programs that use G91.

### Fixed

- **Position state correctness for G91 programs.** Previously the parser
  always treated coordinates as absolute, producing wrong position state
  for any program that used G91. Now correct.

### Deferred (carried forward)

- **G92 (set-position) coordinate offsets.** G92 lets a program redefine
  the current coordinate without moving. Tracking it correctly requires
  adding a coordinate-offset layer; not addressed in this pass.
- **Arc geometry validation.** Unchanged from v3 — G2/G3 arcs are
  tokenized and motion mode is captured, but actual arc paths are not
  computed.
- **Configurable safe Z.** Still hardcoded as `Z > 0`. Should become
  machine-config-driven in a future pass.
- **Module split.** Deferred to next pass; was originally planned to
  bundle with G91 work but split into a standalone task per agreed
  one-task-at-a-time workflow.

### Test Results

**Regression check** — `tests/gcode/test.gcode` (the v3 baseline file):

| Check                | v3 result                            | v4 result                            | Status   |
|----------------------|--------------------------------------|--------------------------------------|----------|
| Lines parsed         | 110 (64 code / 39 comment / 7 empty) | 110 (64 code / 39 comment / 7 empty) | ✓ match  |
| Parser issues        | (n/a — feature is new)               | (none)                               | ✓ clean  |
| Sequence issues      | (none)                               | (none)                               | ✓ match  |
| Operations found     | 2                                    | 2                                    | ✓ match  |
| Depth profile        | -9.5250 (1), -3.3100 (1)             | -9.5250 (1), -3.3100 (1)             | ✓ match  |
| Spindle/feed issues  | (none)                               | (none)                               | ✓ match  |
| Final modal state    | G0, G90, G21, G17, M5, F2800, S18000 | G0, G90, G21, G17, M5, F2800, S18000 | ✓ match  |

**Synthetic G91 tests** — `tests/test_g91.py`, all 7 pass:

| # | Test                                            | Status |
|---|-------------------------------------------------|--------|
| 1 | Pure G90 absolute mode (baseline)               | ✓ PASS |
| 2 | G91 with prior position established             | ✓ PASS |
| 3 | G90 → G91 → G90 round trip                      | ✓ PASS |
| 4 | G91 active at startup (no prior position)       | ✓ PASS |
| 5 | G91 + coordinates on same line                  | ✓ PASS |
| 6 | G90 switch + coordinates on same line           | ✓ PASS |
| 7 | G91 mode persists across continuation lines     | ✓ PASS |

### Notes

- Parser output shape extended additively. Existing validators that read
  `parser_output["lines"]` continue to work without changes. Validators
  may now also read `parser_output.get("parser_issues", [])` if they want
  to include parser-level findings in their output.
- The `INCREMENTAL_NO_PRIOR` issue is severity `INFO` because it's not
  necessarily a bug — some legitimate programs deliberately start in G91
  to perform machine-relative jogs. Validators that want to escalate this
  for their machine context can do so via configuration in a later pass.
- Audit catalog item "Incremental mode without absolute reset" (Tier 2)
  was previously blocked on G91 interpretation. It is now unblocked but
  not yet implemented; remains `[ ]` in `AUDIT_CATALOG.md`.

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
