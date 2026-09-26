"""Plain data passed between scoring and the metrics."""

from dataclasses import dataclass, field

from .fields import FieldKind


@dataclass(frozen=True, slots=True)
class Usage:
    """What one form cost to process."""

    ocr_seconds: float
    structure_seconds: float
    input_tokens: int
    output_tokens: int

    @property
    def total_seconds(self) -> float:
        """Time for both steps."""
        return self.ocr_seconds + self.structure_seconds


@dataclass(frozen=True, slots=True)
class FieldResult:
    """The score of one field of one form."""

    path: str  # "plate" for a top-level field, "vehicle_a.plate" for a vehicle field
    kind: FieldKind
    expected: str | int | list[int]  # normalised for text and choices, sorted for ticks
    predicted: str | int | list[int] | None  # None: the pipeline gave no value
    correct: bool
    edit_distance: int = (
        0  # text fields: character edits between expected and predicted
    )
    reference_length: int = 0  # text fields: characters in the expected value

    @property
    def name(self) -> str:
        """The field name without its vehicle prefix."""
        return self.path.rsplit(".", 1)[-1]


@dataclass(frozen=True, slots=True)
class FormResult:
    """The scores of one form."""

    form_id: str
    produced_output: bool  # False when the pipeline failed to give any record
    fields: tuple[FieldResult, ...] = field(default_factory=tuple)
    usage: Usage | None = None
