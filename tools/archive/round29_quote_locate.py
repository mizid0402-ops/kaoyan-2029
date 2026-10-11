"""Historical round-29 entrypoint retained after helper extraction."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from cs408_quote_locate import build_keymap, locate_quote

__all__ = ["build_keymap", "locate_quote"]
