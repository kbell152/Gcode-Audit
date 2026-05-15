# Changelog

All notable changes to the G-Code Audit Engine are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project uses three-part semantic versioning (`vMAJOR.MINOR.PATCH`).
Note that some early git tags (`v5`, `v6`) use shorter forms from before
this convention was formalized; the CHANGELOG entry headers have been
retroactively standardized to the three-part form for consistency.

Each version entry includes:
- **Scope** — one-line summary of what this pass focused on
- **Added / Changed / Fixed / Deferred** — categorized changes
- **Test results** — what was run, what passed, regressions checked
- **Notes** — anything else worth recording

---

## [v7.0.0] - 2026-05-08

### Scope
Introduces config scaffolding and the rapid-into-material validator —
the highest-priority Tier 1 audit not yet covered. Migrates the
startup-sequence validator to read its safe-Z threshold from config.

### Added
- `src/config.py` — minimal config module with `CLEARANCE_HEIGHT = 0.0`.
  First named config value in the engine; future thresholds
  (max_plunge_ratio, max_feed, machine_envelope) will land here.
- `src/validators/rapid_into_material.py` — new validator detecting two
  hazards on G0 (rapid) motions:
    - `RAPID_INTO_MATERIAL` (CRITICAL): G0 ends at Z at or below the
      clearance height.
    - `RAPID_BELOW_CLEARANCE` (CRITICAL): G0 with XY motion where the
      starting Z is at or below clearance (controller path order not
      guaranteed within a G0 block).
  Respects modal motion (a bare-coordinate line under modal G0 is still
  a rapid). Accepts optional `clearance_height` argument that overrides
  `config.CLEARANCE_HEIGHT`.
- `tests/test_rapid_into_material.py` — 14 tests covering positive cases
  (plunge, traverse, combined, exactly-at-clearance, G91 incremental,
  modal carry-forward), negative cases (clean program, G1 ignored,
  unknown-Z indeterminate, retract above clearance), and explicit
  threshold override.

### Changed
- `src/validators/startup.py` now reads its safe-Z threshold from
  `config.CLEARANCE_HEIGHT` instead of the hardcoded `Z > 0` heuristic.
  Behavior with the default `CLEARANCE_HEIGHT = 0.0` is identical to
  the pre-v7 implementation. Accepts optional `clearance_height`
  argument for callers that need to override.
- `src/validators/__init__.py` re-exports `validate_rapid_into_material`.
- `src/runner.py` runs the new validator and reports under a new
  `=== RAPID-INTO-MATERIAL ISSUES ===` section.
- `src/_version.py` bumped to `7.0.0`.

### Test Results
- 94/94 tests passing (80 prior + 14 new).
- Regression fixture (`tests/gcode/test.gcode`) runs clean: no new flags
  introduced by either the new validator or the startup migration.

### Notes
- Design call on combined-hazard line: a single G0 that both plunges to
  unsafe Z *and* moves XY (starting from safe Z) fires only
  `RAPID_INTO_MATERIAL`, not both flags. The plunge message already
  conveys the underlying hazard; double-flagging would be noise. A G0
  starting from unsafe Z and moving XY *can* fire both flags when end
  Z is also unsafe — they describe distinct problems in that case.
- Traverse-flag rule is strict: any G0 with XY motion where the
  starting Z is at or below clearance is flagged, since G0 path order
  (Z-first vs XY-first vs simultaneous) is controller-defined and not
  guaranteed.
- `config.py` is intentionally minimal — a plain module of constants,
  no file loading. Config-file machinery is deferred until there's
  a second tunable value that justifies it.

---

## [v6.3.0] - 2026-05-08

### Scope
Add `--version` flag to runner CLI. Introduces a single source of truth for
the package version in `src/_version.py`.

### Added
- `src/_version.py` — module containing `__version__ = "6.3.0"`.
- `--version` argument to `runner.py`, prints `gcode-audit 6.3.0`.

### Changed
- `runner.py` imports `__version__` from `_version`.
- Usage block in `runner.py` docstring updated to mention `--version`.

### Test Results
- 80/80 tests passing.
- Manual verification: `--version`, default run, and `--help` all behave as expected.

### Notes
- No automated test for `--version` itself; argparse's `action="version"` is
  library code and calls `sys.exit()`, making clean unit testing awkward.
  Covered by manual verification.
- Version string format standardized on three-part semver going forward.
  Git tag for this release is `v6.3.0` to match the version string; earlier
  tags (`v6.0.1`, `v6.1`, `v6.2`) are left as-is.

---

## [v6.2.0] — 2026-05-06

**Files:** `src/runner.py`, `CHANGELOG.md`
**Scope:** CLI enhancement. Allow the runner to audit arbitrary G-code
files via a command-line argument. No engine changes.

### Added

- **Optional positional argument** to `runner.py` for specifying a
  G-code file to audit:
  - `python3 src/runner.py path/to/program.nc` — audit a specific file.
  - `python3 src/runner.py` (no argument) — falls back to the default
    `tests/gcode/test.gcode`, behavior identical to v6.1.
  - `python3 src/runner.py --help` — show usage info.
- **`Auditing: <path>` header line** at the top of the report output so
  users can confirm which file was processed.
- **Clean error handling for missing files** — prints
  `Error: file not found: <path>` to stderr and exits with code 1
  rather than producing a Python traceback.
- **Path normalization** — the displayed path collapses `..` segments
  (e.g. `src/../tests/gcode/test.gcode` becomes
  `tests/gcode/test.gcode`) for cleaner output.

### Changed

- **Argument parsing now uses `argparse`** (Python standard library).
  This gives `--help` for free and provides scaffolding for future
  flags such as `--version`.

### Test Results

No tests added or modified. The runner is exercised by manual ad-hoc
invocation; the engine behavior it depends on is already covered by
the 80-test suite. Verified by:
- `python3 src/runner.py` with no arguments — output identical to
  v6.1 except for the new `Auditing:` header line.
- `python3 src/runner.py --help` — clean usage display.
- Running with an explicit file path — produces a correct audit report
  for that file.
- Running with a missing file path — prints clean error to stderr,
  exits with code 1.

### Notes

- This is the smallest change that makes the runner usable as an actual
  diagnostic tool rather than a regression demo. Without this, every
  ad-hoc audit required editing the runner.
- Adding `argparse` here means the eventual `--version` flag (queued
  for v7) is a one-line addition rather than a refactor.
- This entry is paired with a retroactive v6.1 entry below — see
  that entry's Notes section for context.

---

## [v6.1.0] — 2026-05-06

**Files:** `README.md`, `AUDIT_CATALOG.md`
**Scope:** Documentation pass following the v6 module split. No code
changes.

### Changed

- **`README.md`** — Repository Layout section updated to reflect the
  post-v6 `src/` structure (`core.py`, `runner.py`, and the
  `validators/` package with one file per validator). Running It
  section updated to use `python3 src/runner.py` from the repo root,
  replacing the obsolete `cd src && python3 gcode_audit_v4_050526.py`.
  The "backward-compatible API across versions" line was softened to
  "Stable parser and validator return shapes across versions" — more
  precise, since v6 did change import paths even though the parser
  and validator return shapes were preserved.
- **`AUDIT_CATALOG.md`** — added a new "Controller dialect support"
  entry under Cross-Cutting Concerns (`[?]` — under consideration),
  documenting that the engine currently treats G-code as a single
  dialect and noting where FluidNC, GRBL-HAL, and classic GRBL
  diverge. Footer "Last updated" line bumped to `2026-05-06
  (alongside v6.1)`.

### Notes

- This entry is being added retroactively in the v6.2 commit. v6.1
  was committed and pushed without a CHANGELOG entry; the gap was
  caught while preparing v6.2 and corrected here. The `Last updated`
  line in AUDIT_CATALOG.md still reads `(alongside v6.0.1)` from when
  it was written — minor inaccuracy preserved rather than rewriting
  history again. Will read correctly on its next update.
- No tests run, no engine code touched.

---

## [v6.0.1] — 2026-05-06

**Files:** `.gitignore`, `CHANGELOG.md`
**Scope:** Cleanup. Remove a build artifact that was inadvertently
committed in v6 and prevent recurrence.

### Removed

- **`v6-split.zip`** — distribution archive of the v6 split, intended
  only as a transfer mechanism between development environments. Was
  picked up by `git add -A` during the v6 commit and should not have
  been tracked. The v6 tagged snapshot still contains the file; this
  commit removes it going forward.

### Changed

- **`.gitignore`** — added `*.zip` to the build artifacts section so
  archives don't get committed again.

### Notes

- v6 itself was already pushed and tagged when the issue was caught,
  so the fix is forward-only rather than a history rewrite. Anyone
  checking out the `v6` tag will still get the zip; anyone working
  from `main` after this commit will not.
- No engine code changes. Tests not re-run because no code under test
  was touched.

---

## [v6.0.0] — 2026-05-06

**Files:** `src/core.py`, `src/runner.py`, `src/validators/` (new package),
`tests/test_*.py` (imports updated), `tests/conftest.py` (docstring updated)
**Scope:** Module split. Structural refactor only — no behavior changes,
no new validators.

### Added

- **`src/core.py`** — parser, tokenizer, modal state model, and modal
  group constants. Public API: `parse_gcode_lines`, `tokenize`,
  `strip_comments`, plus the modal group constants (`MOTION_CODES`,
  `SPINDLE_ON_CODES`, etc.) which validators import.
- **`src/validators/`** — new package containing one validator per file:
  - `startup.py` — `validate_startup_sequence`
  - `spindle_feed.py` — `validate_spindle_and_feed`
  - `depth.py` — `group_operations`, `profile_operation_depths`
  - `__init__.py` — re-exports all four functions so callers can do
    `from validators import validate_startup_sequence` instead of
    importing from individual submodules.
- **`src/runner.py`** — CLI entry point. Wraps the previous `__main__`
  block in a `main()` function with `if __name__ == "__main__": main()`
  at the bottom. Same output as before, now invokable as
  `python src/runner.py`.

### Changed

- **Modal group constants no longer underscore-prefixed.** In the single-
  file era they were "internal" (`_SPINDLE_ON_CODES` etc.). After the
  split, validators legitimately import them, so they are part of
  `core`'s public surface and the underscore was dropped.
- **Test imports updated.** Each test file's import line was rewritten
  to use the new module structure:
  - `from gcode_audit_v4_050526 import ...` →
    `from core import ...` and/or `from validators import ...`
  - Test bodies are unchanged — only imports were touched.
- **`tests/conftest.py` docstring updated** to reference the new import
  pattern. The `sys.path` setup code is unchanged.

### Removed

- **`src/gcode_audit_v4_050526.py`** — fully replaced by the split
  modules above. Preserved in git history via tag `v5`.

### Test Results

Full suite, run via `pytest` from repo root:

| File                  | Tests | Status     |
|-----------------------|-------|------------|
| `test_parser.py`      | 41    | All pass   |
| `test_g91.py`         | 9     | All pass   |
| `test_validators.py`  | 21    | All pass   |
| `test_regression.py`  | 9     | All pass   |
| **Total**             | **80**| **All pass** |

Runner verified separately: `python src/runner.py` against
`tests/gcode/test.gcode` produces output identical to v4 (110 lines
parsed, 2 operations, depth profile -9.525 / -3.31, no validator
issues, final modal state matches).

### Notes

- This pass was scoped strictly structural. No new validators, no parser
  changes, no behavior changes. The tests are what made the split safe —
  every behavior is locked in by the test suite, so a clean 80/80
  before-and-after is strong evidence the refactor introduced no drift.
- Filenames no longer carry version/date suffixes (`core.py`, not
  `core_v6_050626.py`). Versioning is tracked via git tags going forward.
- `src/gcode_audit_v3_050226.py` was removed in a prior housekeeping
  commit on the same day, before the v6 split began. Preserved in git
  history via commit `1b3bbeb` ("Initial commit: v3 engine").
- The README still references the old `gcode_audit_v4_050526.py` path
  and is now stale — to be addressed in a follow-up pass (v6.1).
- The engine has no `--version` flag yet; queued for v7 alongside the
  config scaffolding.

---

## [v5.0.0] — 2026-05-05

**Files:** `tests/`, `pytest.ini`, `requirements-dev.txt`
**Scope:** Test infrastructure. No engine changes.

### Added

- **pytest-based test suite** with 80 tests covering parser, G91
  behavior, all four validators, and a real-world regression file.
- **`requirements-dev.txt`** — single source of truth for development
  dependencies. Currently just `pytest>=8.0`.
- **`pytest.ini`** — test discovery configuration and default options
  (verbose output, short tracebacks, summary at end).
- **`tests/conftest.py`** — sets up import path so test files can
  import from `src/` without per-file `sys.path` manipulation.
- **`tests/README.md`** — how to run tests, where to add new ones,
  patterns and conventions used in the suite.
- **`tests/test_parser.py`** — 41 tests covering tokenizer,
  comment stripping, line classification, modal state propagation,
  parser output shape (the public contract), and defensive input
  validation.
- **`tests/test_g91.py`** — converted from v4's standalone script into
  pytest format. 9 tests covering G90 baseline, G91 increment, mode
  round trips, persistence across continuation lines, no-prior-position
  edge case, and mid-line G-code/coordinate ordering.
- **`tests/test_validators.py`** — 21 tests covering each validator
  with both positive (known-bad programs that should flag) and negative
  (known-good programs that shouldn't flag) cases.
- **`tests/test_regression.py`** — 9 tests locking in expected output
  for `tests/gcode/test.gcode`. Catches "I changed something and now
  the real-world file produces different results" failures.

### Changed

- **`tests/test_g91.py`** rewritten in pytest format. Each scenario is
  now a separate test function, so a failure in one doesn't prevent
  others from running and pytest can report exactly which scenarios
  broke.

### Test Results

Full suite, run via `pytest` from repo root:

| File                  | Tests | Status     |
|-----------------------|-------|------------|
| `test_parser.py`      | 41    | All pass   |
| `test_g91.py`         | 9     | All pass   |
| `test_validators.py`  | 21    | All pass   |
| `test_regression.py`  | 9     | All pass   |
| **Total**             | **80**| **All pass** |

### Notes

- Engine code unchanged in this pass — `gcode_audit_v4_050526.py` is
  identical to what shipped in v4. Version bump is for the
  infrastructure addition.
- Tests assume the venv is active. If you see
  `ModuleNotFoundError: No module named 'pytest'`, run
  `source .venv/bin/activate` first.
- Going forward, the workflow for any code change is: write/update
  tests → run `pytest` → make change → run `pytest` again.
- The regression test (`test_regression.py`) is intentionally strict.
  If a future change makes it fail, that's the test doing its job —
  forcing a conscious decision about whether the new behavior is
  intended.

---

## [v4.0.0] — 2026-05-05

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

## [v3.0.0] — 2026-05-02

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

## [v2.0.0] — 2026-05-01

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
