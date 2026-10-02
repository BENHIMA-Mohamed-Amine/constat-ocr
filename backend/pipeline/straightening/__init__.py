"""Step 0 (optional): flatten the phone photo before OCR reads it."""

from .base import Straightener
from .factory import build_straightener, register_straightener

__all__ = ["Straightener", "build_straightener", "register_straightener"]
