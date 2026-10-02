"""Exceptions raised by the pipeline.

Each step raises its own subclass so callers can tell where a form failed. A failure on one form is recorded and the
run continues; nothing here is meant to stop a whole run.
"""


class PipelineError(Exception):
    """Base class of every error raised by the pipeline."""

    def __init__(self, message: str, *, form_id: str | None = None) -> None:
        """Create the error.

        Args:
            message: What went wrong.
            form_id: Identifier of the form being processed, when known.
        """
        super().__init__(message)
        self.form_id = form_id

    def __str__(self) -> str:
        prefix = f"[form {self.form_id}] " if self.form_id else ""
        return f"{prefix}{super().__str__()}"


class ConfigurationError(PipelineError):
    """A setting is missing or invalid."""


class StraighteningError(PipelineError):
    """The page could not be found or flattened in the photo."""


class OcrError(PipelineError):
    """The image could not be read into text."""


class StructuringError(PipelineError):
    """The text could not be turned into a valid record."""


class EvaluationError(PipelineError):
    """A prediction could not be scored against its answer key."""
