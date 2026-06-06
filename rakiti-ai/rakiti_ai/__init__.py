"""Development launcher package for running Rafiki AI without installation.

The application code lives in src/rakiti_ai. This small package extends the
module search path so `python -m rakiti_ai` works from the project directory.
"""

from __future__ import annotations

from pathlib import Path

_SRC_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "rakiti_ai"
if _SRC_PACKAGE.is_dir():
    __path__.append(str(_SRC_PACKAGE))

__version__ = "0.1.0"
