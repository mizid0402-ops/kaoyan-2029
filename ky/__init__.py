"""Pure domain models and scheduling core for the kaoyan-2029 study system.

This package deliberately contains no side effects at import time and never
writes to the study workspace. Anything that mutates authoritative study state
belongs in the controlled generation flow, not here.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
