"""
Validators for the gcode-audit engine.

Each validator reads the parser output (from core.parse_gcode_lines)
and returns a list of issue dicts. They are re-exported here so callers
can do:

    from validators import validate_startup_sequence, group_operations

instead of importing each one from its individual module.
"""

from .startup import validate_startup_sequence
from .spindle_feed import validate_spindle_and_feed
from .depth import group_operations, profile_operation_depths
from .rapid_into_material import validate_rapid_into_material

__all__ = [
    "validate_startup_sequence",
    "validate_spindle_and_feed",
    "group_operations",
    "profile_operation_depths",
    "validate_rapid_into_material",
]
