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
- Backward-compatible API across versions

See `AUDIT_CATALOG.md` for the full list of planned audits and their status.
See `CHANGELOG.md` for version-by-version build notes.

## Repository Layout

```
gcode-audit/
├── README.md                    This file
├── CHANGELOG.md                 Version history (canonical, append-only)
├── AUDIT_CATALOG.md             Planned audits + implementation status
├── src/
│   ├── gcode_audit_v3_050226.py Current single-file engine (v3)
│   └── validators/              (Future: per-validator modules after split)
├── tests/
│   └── gcode/
│       └── test.gcode           Real-world test program (Fusion/GRBL)
└── docs/
    └── changelogs/              On-demand PDF snapshots of CHANGELOG.md
```

## Running It

```bash
cd src
python3 gcode_audit_v3_050226.py
```

By default, it expects `test.gcode` in the working directory. Adjust the path
in the `__main__` block, or run from `tests/gcode/` with the script copied in.

The runner prints parser stats, final modal state, sequence issues, operation
groupings, depth profile, and spindle/feed issues.

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
