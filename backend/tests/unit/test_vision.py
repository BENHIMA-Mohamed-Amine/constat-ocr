"""Unit (1 test): the vision structurer, with a fake server and no model.

One pytest item made of 3 named sub-checks. The HTTP call is faked, so the checks cover what is sent (image, token, schema, prompt
rules), how the answer becomes a ``Record``, and that a bad answer fails the form instead of returning an empty record.
"""

import json
from pathlib import Path

import httpx
import pytest

from pipeline.core.errors import StructuringError
from pipeline.core.schema import Record
from pipeline.structuring.base import StructuringInput
from pipeline.structuring.prompts import PROMPTS
from pipeline.structuring.vision import VisionStructurer

from ..checks import run_checks


class _Reply:
    def __init__(self, content: str) -> None:
        self._content = content

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {
            "choices": [{"message": {"content": self._content}}],
            "usage": {"prompt_tokens": 4000, "completion_tokens": 500},
        }


def _sent_and_parsed(inputs: StructuringInput, monkeypatch) -> None:
    """The request carries the image, the token, the schema and the rules; the JSON answer becomes a ``Record``."""
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent.update(url=url, headers=headers, body=json)
        return _Reply('{"date": "29/06/2022", "vehicle_a": {"plate": "52033-D-39"}}')

    monkeypatch.setattr(httpx, "post", fake_post)
    result = VisionStructurer(
        "https://x.modal.run/", system_prompt=PROMPTS["vlm"], auth_token="wk-1.ws-2"
    ).structure(inputs)
    assert result.record.vehicle_a.plate == "52033-D-39"
    assert (result.input_tokens, result.output_tokens) == (4000, 500)
    assert sent["url"] == "https://x.modal.run/v1/chat/completions"
    assert sent["headers"] == {"Authorization": "Bearer wk-1.ws-2"}
    body = sent["body"]
    assert (
        body["response_format"]["json_schema"]["schema"] == Record.model_json_schema()
    )
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert "dd/mm/yyyy" in body["messages"][0]["content"]
    assert body["messages"][1]["content"][0]["image_url"]["url"].startswith(
        "data:image/jpeg;base64,"
    )


def _bad_answers_fail_the_form(inputs: StructuringInput, monkeypatch) -> None:
    """Text that is not JSON, a wrong type and an empty record each raise ``StructuringError``."""
    for content in ("not json", '{"date": 5, "vehicle_a": 3}', "{}"):
        monkeypatch.setattr(httpx, "post", lambda *a, _c=content, **k: _Reply(_c))
        with pytest.raises(StructuringError):
            VisionStructurer("https://x.modal.run").structure(inputs)


def _server_failure_fails_the_form(inputs: StructuringInput, monkeypatch) -> None:
    """A network or HTTP error raises ``StructuringError`` with the form id."""

    def boom(*args, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "post", boom)
    with pytest.raises(StructuringError, match="000000"):
        VisionStructurer("https://x.modal.run").structure(inputs)


def test_vision_structurer(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "page.jpg"
    image.write_bytes(b"jpeg bytes")
    inputs = StructuringInput("000000", image, None)
    run_checks(
        [
            ("sent and parsed", lambda: _sent_and_parsed(inputs, monkeypatch)),
            ("bad answers", lambda: _bad_answers_fail_the_form(inputs, monkeypatch)),
            (
                "server failure",
                lambda: _server_failure_fails_the_form(inputs, monkeypatch),
            ),
        ]
    )
