# G-Code Audit Engine

Python static-analysis tool for CNC G-code. Parses G-code line-by-line, tracks full modal
machine state, and applies validators to catch errors/unsafe sequences **before** the
program runs. Diagnostic only — it does not generate toolpaths or drive a machine. See
`README.md`, `AUDIT_CATALOG.md` (planned audits + status), and `CHANGELOG.md`.

## Runtime & deps
Runtime code uses the **Python standard library only** — no third-party runtime deps.
Dev/test needs pytest:
```
python3 -m venv .venv
.venv/bin/python3 -m pip install -r requirements-dev.txt
```

## Run
```
.venv/bin/python3 src/runner.py --help
```
`src/runner.py` is the argparse CLI entry point.

## Test
```
.venv/bin/python3 -m pytest
```
Config in `pytest.ini` (`testpaths = tests`, `test_*.py`, verbose + short tracebacks).

## Layout
- `src/core.py` — tokenizer, parser, modal state model
- `src/runner.py` — CLI entry
- `src/config.py`, `src/_version.py`
- `src/validators/` — one file per validator (`startup.py`, `spindle_feed.py`,
  `depth.py`, `rapid_into_material.py`); `__init__.py` re-exports the public API
- `tests/` — parser, G91, validators, regression (pinned against `tests/gcode/test.gcode`)
- `docs/` — changelog PDFs and notes

## Conventions
- Codes are normalized (`G01`→`G1`, `M03`→`M3`) in the parser.
- Keep validator return shapes stable (regression tests pin outputs).
- `CHANGELOG.md` is canonical and append-only.
