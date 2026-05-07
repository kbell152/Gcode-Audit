# G-Code Audit Engine

A Python-based static analysis system for CNC G-code programs. The system parses
G-code line-by-line, tracks full machine modal state, and applies validation
rules to detect errors, unsafe sequences, and logical flaws **before** the
program reaches the machine.

This is a **diagnostic tool**, not a control system. It does not generate
toolpaths or send commands to a machine. It audits G-code that has already
been generated (typically by a CAM post-processor) and surfaces issues for
human review.

## Project Status

Early development. Current capabilities:

- Robust G-code parser with full modal state tracking
- Tokenizer handles space-separated and no-space formats, comments, blank lines
- Code normalization (`G01` → `G1`, `M03` → `M3`, etc.)
- Three working validators: startup sequence, depth profile, spindle/feed
- Stable parser and validator return shapes across versions

See `AUDIT_CATALOG.md` for the full list of planned audits and their status.
See `CHANGELOG.md` for version-by-version build notes.
See `docs/TEST_SUMMARY.md` for an overview of what the test suite covers.

## Repository Layout

```
gcode-audit/
├── README.md                    This file
├── CHANGELOG.md                 Version history (canonical, append-only)
├── AUDIT_CATALOG.md             Planned audits + implementation status
├── pytest.ini                   Pytest configuration
├── requirements-dev.txt         Dev dependencies (pytest)
├── src/
│   ├── core.py                  Parser, tokenizer, modal state model
│   ├── runner.py                CLI entry point
│   └── validators/              One file per validator, plus __init__.py
│       ├── __init__.py          Re-exports the public validator API
│       ├── startup.py           validate_startup_sequence
│       ├── spindle_feed.py      validate_spindle_and_feed
│       └── depth.py             group_operations, profile_operation_depths
├── tests/
│   ├── README.md                How to run / how to add tests
│   ├── conftest.py              Pytest fixtures and path setup
│   ├── test_parser.py           Tokenizer / comments / modal state
│   ├── test_g91.py              G91 incremental coordinate handling
│   ├── test_validators.py       Each validator (positive + negative cases)
│   ├── test_regression.py       Pinned outputs against test.gcode
│   └── gcode/
│       └── test.gcode           Real-world test program (Fusion/GRBL)
└── docs/
    └── changelogs/              On-demand PDF snapshots of CHANGELOG.md
```

## Running It

From the repo root:

```bash
python3 src/runner.py
```

By default, it expects `test.gcode` at `tests/gcode/test.gcode`. The runner
prints parser stats, parser issues, final modal state, sequence issues,
operation groupings, depth profile, and spindle/feed issues.

## Running the Tests

First-time setup (one time per machine):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

After that, every time you want to run tests:

```bash
source .venv/bin/activate    # activate the venv if not already active
pytest                       # runs the whole suite
```

See `tests/README.md` for more on running and writing tests.

## Design Principles

1. **State is persistent** — modal values carry forward unless changed.
2. **Motion is defined by change**, not presence (X10 on a line isn't motion
   if X was already 10).
3. **Order matters more than values** — sequencing validation is central.
4. **Analysis must be deterministic and explainable** — every issue points
   to a line and a clear rule.
5. **No hidden assumptions** — defaults that do exist (like "safe Z = Z > 0")
   are documented and slated to become configurable.

## Important Caveat

This tool augments human review; it does not replace it. CNC machines are
unforgiving and edge cases are infinite. Always have an experienced operator
review G-code before running it on real hardware, especially programs flagged
as clean by this tool. A clean audit means "no issues this tool knows how to
detect" — not "this program is safe to run."
