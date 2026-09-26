"""The one comparison rule: trim, collapse spaces, ignore case. Nothing more (no forgiveness for 0/O or 1/7)."""

import re

_SPACES = re.compile(r"\s+")


def normalize(value: object) -> str:
    """Return the comparison form of a value.

    Booleans become ``"true"`` / ``"false"`` so a yes/no field compares like any other choice.
    """
    text = ("true" if value else "false") if isinstance(value, bool) else str(value)
    return _SPACES.sub(" ", text).strip().casefold()
