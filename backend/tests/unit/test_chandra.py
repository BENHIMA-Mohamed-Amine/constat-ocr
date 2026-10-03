"""Unit (1 test): the Chandra-OCR-2 engine, with a fake server and a page the test draws itself.

One pytest item made of 4 named sub-checks. No network and no model: the HTTP call is faked, so the checks cover what the engine
sends, how it reacts to a loop, and how it turns the HTML into zone text.
"""

from pathlib import Path

import pytest

from pipeline.ocr.chandra import PROMPT, ChandraOcrEngine, blocks_to_text, repeats
from pipeline.structuring.prompts import (
    CHANDRA_SYSTEM_PROMPT,
    COLUMNS_SYSTEM_PROMPT,
    PROMPTS,
)

from ..checks import run_checks
from .test_columns import _drawn_page

CUTS = (0.31, 0.69, 0.17)

PAGE_HTML = """
<div data-bbox="17 20 418 59" data-label="Section-Header"><h1>Constat amiable</h1></div>
<div data-bbox="30 300 280 330" data-label="Text"><p>Nom <u>FASSI</u></p></div>
<div data-bbox="350 400 650 480" data-label="Form"><table><tr>
<td><input type="checkbox"/> 9 Quittait</td><td>كان خارجا</td></tr><tr>
<td><input checked="" type="checkbox"/> 10 Prenait</td><td>كان على</td></tr></table></div>
<div data-bbox="720 300 980 330" data-label="Text"><p>Prénom Meryem</p></div>
<div data-bbox="30 560 190 580" data-label="Text"><p>A1 <input checked="" type="radio"/> B C</p></div>
<div data-bbox="200 700 300 800" data-label="Image"><img alt="impact on the front left"/></div>
<div data-bbox="720 900 980 950" data-label="Text"><p>cut off by the token cap
"""


def _repeat_check_spots_loops_only() -> None:
    """A tail of the same short pattern is a loop; ordinary HTML, even with repeated tags, is not.

    The Arabic letters loop is the one seen on the H100. A table full of ``<td>`` tags repeats short patterns too, so the
    check must allow more repeats for shorter patterns.
    """
    assert repeats("<div>start</div>" + " أ ب" * 300)
    assert repeats("text " + "Véhicule B\n" * 40)
    assert not repeats(PAGE_HTML)
    assert not repeats("<table>" + "<tr><td>1</td><td>2</td></tr>" * 6 + "</table>")


def _blocks_become_zone_text() -> None:
    """Each block goes to the zone of its centre, ticks and descriptions are kept, a block cut off by the cap is dropped.

    Checks the marks: ``[ ]`` and ``[x]`` for checkboxes, ``(x)`` for a checked radio button, ``[image: ...]`` for a picture,
    table cells on one line, and blocks in reading order inside a zone.
    """
    assert blocks_to_text(PAGE_HTML, CUTS) == (
        "## header\nConstat amiable\n\n"
        "## vehicle_a\nNom FASSI\nA1 (x) B C\n[image: impact on the front left]\n\n"
        "## circumstances\n[ ] 9 Quittait كان خارجا\n[x] 10 Prenait كان على\n\n"
        "## vehicle_b\nPrénom Meryem"
    )


class _Reply:
    def __init__(self, content: str) -> None:
        self._content = content

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"choices": [{"message": {"content": self._content}}]}


def _engine_sends_the_page_and_retries_a_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The request carries the model, the image and Datalab's prompt; a looping answer is regenerated warmer.

    Every request must carry the Bearer token. The fake server loops once, then answers. The first attempt must use temperature 0 and ``top_p`` 0.1, the second 0.2 and
    0.95, and the text returned is the second answer's.
    """
    calls = []

    def fake_post(url: str, **kwargs) -> _Reply:
        calls.append((url, kwargs["json"], kwargs["headers"]))
        return _Reply("<div>" + " أ ب" * 300 if len(calls) == 1 else PAGE_HTML)

    monkeypatch.setattr("pipeline.ocr.chandra.httpx.post", fake_post)
    page = tmp_path / "page.png"
    _drawn_page(page)
    result = ChandraOcrEngine(
        "http://host:1/", max_retries=2, auth_token="wk-id.ws-secret"
    ).read(page)

    assert len(calls) == 2
    assert calls[0][0] == "http://host:1/v1/chat/completions"
    first, second = calls[0][1], calls[1][1]
    assert all(h == {"Authorization": "Bearer wk-id.ws-secret"} for _, _, h in calls)
    assert first["model"] == "chandra-ocr-2" and first["max_tokens"] == 8000
    assert (first["temperature"], first["top_p"]) == (0, 0.1)
    assert (second["temperature"], second["top_p"]) == (0.2, 0.95)
    image_part, text_part = first["messages"][0]["content"]
    assert image_part["image_url"]["url"].startswith("data:image/png;base64,")
    assert text_part["text"] == PROMPT
    assert "## vehicle_b\n" in result.text and result.seconds >= 0


def _prompt_differs_from_columns_in_two_bullets() -> None:
    """The ``chandra`` prompt is the ``columns`` prompt with the tick sentences replaced, and it is registered by name.

    Everything else must be identical, so a run differs from v3b only in how the prompt describes the text it receives.
    """
    assert PROMPTS["chandra"] == CHANDRA_SYSTEM_PROMPT
    assert "[x]" in CHANDRA_SYSTEM_PROMPT and "[x]" not in COLUMNS_SYSTEM_PROMPT
    assert "cannot be seen in text" not in CHANDRA_SYSTEM_PROMPT
    shared = [
        line
        for line in COLUMNS_SYSTEM_PROMPT.splitlines()
        if "Ticked boxes" not in line
    ]
    assert all(
        line in CHANDRA_SYSTEM_PROMPT or "circumstances: the" in line for line in shared
    )


def test_chandra(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The loop check, the HTML to zone text conversion, the request and retry, and the prompt all behave as described."""
    run_checks(
        [
            ("repeat_check_spots_loops_only", _repeat_check_spots_loops_only),
            ("blocks_become_zone_text", _blocks_become_zone_text),
            (
                "engine_sends_the_page_and_retries_a_loop",
                lambda: _engine_sends_the_page_and_retries_a_loop(
                    tmp_path, monkeypatch
                ),
            ),
            (
                "prompt_differs_from_columns_in_two_bullets",
                _prompt_differs_from_columns_in_two_bullets,
            ),
        ]
    )
