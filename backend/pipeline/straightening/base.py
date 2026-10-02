"""The straightening contract. Any method that flattens a phone photo implements ``Straightener``."""

from pathlib import Path
from typing import Protocol


class Straightener(Protocol):
    """Turns a phone photo of a page into an upright, cropped image of the page."""

    def straighten(self, image_path: Path, out_path: Path) -> None:
        """Write the straightened image to ``out_path``.

        Raises:
            StraighteningError: If the image cannot be read or no page is found.
        """
        ...
