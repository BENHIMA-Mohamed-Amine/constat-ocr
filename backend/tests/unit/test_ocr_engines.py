"""Unit (1 test): the OCR engine registry and the CPU engine added in v2.

One pytest item made of 2 named sub-checks. It uses the real RapidOCR models (about 12 MB, downloaded on the
first run), on an image the test draws itself, so it needs neither the dataset nor a network call to an LLM.
"""

from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from pipeline.core.config import Settings
from pipeline.core.errors import ConfigurationError
from pipeline.ocr import build_ocr_engine
from pipeline.ocr.rapidocr import RapidOcrEngine

from ..checks import run_checks


def _registry_builds_known_engines_and_rejects_unknown() -> None:
    """``build_ocr_engine`` returns the engine named in the settings and raises for an unknown name.

    A wrong name must fail loudly and list the known engines, not fall back silently to another engine,
    because a run scored with the wrong engine would be reported under the wrong version.
    """
    settings = Settings(
        groq_api_key="dummy-key-for-tests",
        langsmith_tracing=False,
        ocr_engine="tesseract",
    )
    assert type(build_ocr_engine(settings)).__name__ == "LangChainTesseractEngine"
    with pytest.raises(ConfigurationError, match="rapidocr"):
        build_ocr_engine(settings.model_copy(update={"ocr_engine": "nope"}))


def _rapidocr_reads_printed_text(tmp_path: Path) -> None:
    """RapidOCR returns the words of a clean printed image, with French accents intact, and a time.

    This checks that the engine is wired to models that can read Latin text at all, not how well it
    reads handwriting (that is what the benchmark run measures).
    """
    image = Image.new("RGB", (900, 160), "white")
    ImageDraw.Draw(image).text(
        (30, 40),
        "Constat amiable, déclaration 41654",
        "black",
        ImageFont.load_default(size=48),
    )
    path = tmp_path / "printed.png"
    image.save(path)

    result = RapidOcrEngine().read(path)
    assert "amiable" in result.text, result.text
    assert "41654" in result.text, result.text
    assert result.seconds > 0


def test_ocr_engines(tmp_path: Path) -> None:
    """The engine registry picks the configured engine and the RapidOCR engine reads text."""
    run_checks(
        [
            (
                "registry_builds_known_engines_and_rejects_unknown",
                _registry_builds_known_engines_and_rejects_unknown,
            ),
            (
                "rapidocr_reads_printed_text",
                lambda: _rapidocr_reads_printed_text(tmp_path),
            ),
        ]
    )
