"""Shared pytest fixtures for the pipeline and generator test suites.

Fixtures here are consumed across categories: unit tests use the fakes to run the graph without
Tesseract or a network call; the integration test uses ``sample_truth`` for its own bookkeeping.

Also loads ``backend/.env`` into the environment on import (before any test module runs), so
``GROQ_API_KEY``/``LANGSMITH_API_KEY`` are visible both to ``Settings`` (which reads the file
itself) and to ``os.environ`` directly — which is what
``tests/integration/test_pipeline_e2e.py``'s ``skipif`` checks. Locally this means the E2E test
runs without having to ``source .env`` by hand; in CI, where the real secret is already exported by
the workflow and there is no ``.env`` file to find, this is a harmless no-op.
"""

import random
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from dotenv import load_dotenv

from generator.data import sample_record
from pipeline.core.errors import StructuringError
from pipeline.core.schema import Record
from pipeline.data.storage import FileArtifactStore
from pipeline.ocr import OcrResult
from pipeline.structuring import StructuringInput, StructuringResult

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class FakeOcrEngine:
    """A fake :class:`pipeline.ocr.OcrEngine` that returns fixed text without touching Tesseract."""

    def __init__(self, text: str = "some text", seconds: float = 0.5) -> None:
        """Create the fake.

        Args:
            text: The text every call to :meth:`read` returns.
            seconds: The duration every call reports.
        """
        self.text = text
        self.seconds = seconds
        self.calls = 0

    def read(self, image_path: Path) -> OcrResult:
        """Return the fixed text and count the call."""
        self.calls += 1
        return OcrResult(self.text, self.seconds)


class FakeStructurer:
    """A fake :class:`pipeline.structuring.Structurer` that perturbs one field of a known record.

    Returns ``truth`` with vehicle A's plate changed by one character (so exactly one field is
    wrong), or raises :class:`StructuringError` when ``fail`` is set, to exercise error handling
    without a real model call.
    """

    def __init__(self, truth: Record, fail: bool = False) -> None:
        """Create the fake.

        Args:
            truth: The record to return, with vehicle A's plate perturbed.
            fail: If True, every call raises :class:`StructuringError` instead.
        """
        self.truth = truth
        self.fail = fail
        self.calls = 0

    def structure(self, inputs: StructuringInput) -> StructuringResult:
        """Return the perturbed record, or raise if ``fail`` is set."""
        self.calls += 1
        if self.fail:
            raise StructuringError("model down", form_id=inputs.form_id)
        plate = self.truth.vehicle_a.plate
        flipped = plate[:-1] + ("0" if plate[-1] != "0" else "1")
        record = self.truth.model_copy(
            update={
                "vehicle_a": self.truth.vehicle_a.model_copy(update={"plate": flipped})
            }
        )
        return StructuringResult(
            record, input_tokens=100, output_tokens=50, seconds=1.5
        )


def sample_truth(seed: int) -> Record:
    """A generated, schema-validated record for a given seed.

    Args:
        seed: The generator seed; the same seed always returns the same record.

    Returns:
        The record, as the :mod:`generator` would have written it to an answer-key file.
    """
    return Record.model_validate(sample_record(random.Random(seed)))


@pytest.fixture
def fake_ocr_engine() -> FakeOcrEngine:
    """A fresh :class:`FakeOcrEngine` per test, so call counts start at zero."""
    return FakeOcrEngine()


@pytest.fixture
def fake_structurer() -> FakeStructurer:
    """A fresh :class:`FakeStructurer`, bound to the fixed seed-3 record, per test."""
    return FakeStructurer(sample_truth(3))


@pytest.fixture
def tmp_run_dir() -> Iterator[FileArtifactStore]:
    """A :class:`FileArtifactStore` in a temporary directory, removed after the test."""
    with TemporaryDirectory() as tmp:
        yield FileArtifactStore(Path(tmp) / "run")
