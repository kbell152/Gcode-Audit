"""
Configuration values for the gcode-audit engine.

Currently a minimal module of named constants. As more validators come
online, this is where their tunable thresholds will live (max_plunge_ratio,
max_feed, machine_envelope, etc.).

Validators should read from this module rather than hardcoding values.
Tests and callers that need to override a value should pass it explicitly
as a function argument rather than mutating this module.

Future direction: if/when config-file loading becomes useful (per-machine
profiles, CLI overrides), this module is where that machinery will go.
"""

# Z height above which the machine is considered to be in a safe,
# non-cutting region. Motions with Z strictly greater than this value
# are treated as safe; motions with Z at or below this value are
# treated as being in (or at) the material.
#
# Default 0.0 matches the historical Z > 0 heuristic that lived in
# startup.py before v7. A future per-machine config layer is expected
# to override this.
CLEARANCE_HEIGHT = 0.0
