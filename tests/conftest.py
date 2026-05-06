"""
pytest configuration for the gcode-audit test suite.

This file is automatically discovered and loaded by pytest before any
tests run. Its only job here is to make src/ importable from test files
so they can do `from core import ...` and `from validators import ...`
without each test file needing its own sys.path manipulation.
"""

import sys
import os

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_TESTS_DIR)
_SRC_DIR = os.path.join(_REPO_ROOT, "src")

if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

