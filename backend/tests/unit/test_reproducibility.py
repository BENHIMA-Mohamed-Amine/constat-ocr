"""Unit: every run's ``run.json`` carries enough metadata to reproduce it, no network needed.

A version's results are only meaningful if someone can later tell exactly what produced them: which
model, which package versions, which dataset. This test does not call Groq or read a real image; it
only needs the real Tesseract binary (for its version string) and a couple of fake forms.
"""

from pathlib import Path

import pytest

from pipeline.core.config import Settings
from pipeline.data.dataset import FormRef
from pipeline.flow.runner import describe_run


@pytest.fixture
def settings() -> Settings:
    """Settings built from a dummy Groq key, so this test needs no real secret."""
    return Settings(groq_api_key="dummy-key-for-tests", langsmith_tracing=False)


@pytest.fixture
def forms() -> list[FormRef]:
    """A short fake form list, enough for describe_run's per-form listing."""
    return [
        FormRef("000000", "dev", Path("a.jpg"), Path("a.json")),
        FormRef("000100", "test", Path("b.jpg"), Path("b.json")),
    ]


def test_describe_run_has_no_missing_metadata(
    settings: Settings, forms: list[FormRef]
) -> None:
    """Every field needed to reproduce or audit a run is present and non-empty.

    Specifically: the LLM provider, model id, temperature and reasoning effort; the OCR engine's
    name, its configured languages, and the real installed Tesseract version (not a placeholder);
    the installed version of every package the pipeline depends on; the dataset fingerprint that
    was passed in; and the exact command that was run. A missing or empty value here would mean a
    run's ``run.json`` cannot answer "what exactly produced this result?" later.
    """
    description = describe_run("v1-dev", settings, forms, fingerprint="deadbeef")

    assert description["run_id"] == "v1-dev"
    assert description["dataset_fingerprint"] == "deadbeef"
    assert description["forms"] == [
        {"id": "000000", "split": "dev"},
        {"id": "000100", "split": "test"},
    ]

    llm = description["llm"]
    assert llm["provider"] == "groq"
    assert llm["model"]
    assert llm["temperature"] == 0.0
    assert llm["reasoning_effort"]

    ocr = description["ocr"]
    assert ocr["engine"] == "rapidocr-v6"
    assert ocr["languages"] == ["fra"]
    assert ocr["tesseract"], "Tesseract must be installed for this to be non-empty"

    versions = description["versions"]
    expected_packages = {
        "langchain",
        "langchain-core",
        "langchain-groq",
        "langchain-community",
        "langgraph",
        "langsmith",
        "pydantic",
        "pytesseract",
        "opencv-python",
        "rapidocr",
        "jiwer",
    }
    assert set(versions) == expected_packages
    assert all(versions.values()), "every package version must be non-empty"

    assert description["python"]
    assert description["date_utc"]
