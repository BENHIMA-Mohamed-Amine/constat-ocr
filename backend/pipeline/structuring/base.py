"""The structuring contract. Any structurer (text-only LLM now, a vision model later) implements ``Structurer``."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..core.schema import Record


@dataclass(frozen=True, slots=True)
class StructuringInput:
    """Everything a structurer may use to fill the record of one form."""

    form_id: str
    image_path: Path  # unused by text-only structurers; a vision model reads it
    ocr_text: str | None


@dataclass(frozen=True, slots=True)
class StructuringResult:
    """A filled record, with what it cost."""

    record: Record
    input_tokens: int
    output_tokens: int
    seconds: float


class Structurer(Protocol):
    """Fills a ``Record`` for one form."""

    def structure(self, inputs: StructuringInput) -> StructuringResult:
        """Fill the record.

        Raises:
            StructuringError: If no valid record could be produced.
        """
        ...
