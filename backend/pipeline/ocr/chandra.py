"""Chandra-OCR-2 (Datalab) served by vLLM: the page image goes in, HTML layout blocks come out, and the blocks are sorted into
the four zones of the form, like ``rapidocr-v6-columns`` does for RapidOCR.

Chandra answers with one ``div`` per block, each carrying ``data-bbox`` (x0 y0 x1 y1, normalised 0 to 1000). Checkboxes, circled
radio buttons and picture descriptions are kept in the text, because they are what a text-only reader could not give.
"""

import base64
import logging
import time
from html.parser import HTMLParser
from pathlib import Path

import cv2
import httpx
import numpy as np

from ..core.errors import OcrError
from .base import OcrResult
from .columns import find_zone_cuts, group_by_zone

logger = logging.getLogger(__name__)

# The prompt the model was trained with, copied from github.com/datalab-to/chandra (chandra/prompts.py, "ocr_layout").
_ALLOWED_TAGS = [
    "math", "br", "i", "b", "u", "del", "sup", "sub", "table", "tr", "td", "p", "th", "div", "pre", "h1", "h2", "h3",
    "h4", "h5", "ul", "ol", "li", "input", "a", "span", "img", "hr", "tbody", "small", "caption", "strong", "thead",
    "big", "code", "chem",
]  # fmt: skip
_ALLOWED_ATTRIBUTES = [
    "class", "colspan", "rowspan", "display", "checked", "type", "border", "value", "style", "href", "alt", "align",
    "data-bbox", "data-label",
]  # fmt: skip

_PROMPT_ENDING = f"""
Only use these tags {_ALLOWED_TAGS}, and these attributes {_ALLOWED_ATTRIBUTES}.

Guidelines:
* Inline math: Surround math with <math>...</math> tags. Math expressions should be rendered in KaTeX-compatible LaTeX. Use display for block math.
* Tables: Use colspan and rowspan attributes to match table structure.
* Formatting: Maintain consistent formatting with the image, including spacing, indentation, subscripts/superscripts, and special characters.
* Images: Include a description of any images in the alt attribute of an <img> tag. Do not fill out the src property. Describe in detail inside the div tag. Also convert charts to high fidelity data, and convert diagrams to mermaid.
* Forms: Mark checkboxes and radio buttons properly.
* Text: join lines together properly into paragraphs using <p>...</p> tags.  Use <br> tags for line breaks within paragraphs, but only when absolutely necessary to maintain meaning.
* Chemistry: Use <chem>...</chem> tags for chemical formulas with reactive SMILES.
* Lists: Preserve indents and proper list markers.
* Use the simplest possible HTML structure that accurately represents the content of the block.
* Make sure the text is accurate and easy for a human to read and interpret.  Reading order should be correct and natural.
""".strip()

PROMPT = f"""
OCR this image to HTML, arranged as layout blocks.  Each layout block should be a div with the data-bbox attribute representing the bounding box of the block in x0 y0 x1 y1 format.  Bboxes are normalized 0-1000. The data-label attribute is the label for the block.

Use the following labels:
- Caption
- Footnote
- Equation-Block
- List-Group
- Page-Header
- Page-Footer
- Image
- Section-Header
- Table
- Text
- Complex-Block
- Code-Block
- Form
- Table-Of-Contents
- Figure
- Chemical-Block
- Diagram
- Bibliography
- Blank-Page

{_PROMPT_ENDING}
""".strip()

_LINE_BREAKS = {
    "br",
    "p",
    "tr",
    "li",
    "table",
    "caption",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "div",
}


def repeats(
    text: str,
    base_max_repeats: int = 4,
    window: int = 500,
    scaling: float = 3.0,
    cut_from_end: int = 0,
) -> bool:
    """Whether the end of ``text`` is the same short pattern repeated again and again (a generation loop).

    From Datalab's client (chandra/model/util.py, ``detect_repeat_token``). The shorter the pattern, the more repeats it takes
    to count, so a normal table full of ``<td>`` tags is not mistaken for a loop.

    Args:
        text: The model's answer.
        base_max_repeats: Repeats allowed for a long pattern.
        window: How far back to look.
        scaling: How many more repeats a short pattern is allowed.
        cut_from_end: Ignore this many trailing characters (an answer cut off mid-pattern).
    """
    if cut_from_end:
        text = text[:-cut_from_end]
    for size in range(1, window // 2 + 1):
        tail = text[-size:]
        limit = int(base_max_repeats * (1 + scaling / size))
        count, position = 0, len(text) - size
        while position >= 0 and text[position : position + size] == tail:
            count += 1
            position -= size
        if count > limit:
            return True
    return False


def _looped(text: str) -> bool:
    return repeats(text) or (len(text) > 50 and repeats(text, cut_from_end=50))


class _BlockParser(HTMLParser):
    """Collects the top-level ``div`` blocks of Chandra's HTML as (bbox, text); a block cut off by the token cap is dropped."""

    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[tuple[list[float], str]] = []
        self._depth = 0
        self._bbox: list[float] | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "div":
            if self._depth == 0 and "data-bbox" in attributes:
                self._bbox, self._parts = (
                    [float(v) for v in attributes["data-bbox"].split()],
                    [],
                )
            self._depth += 1
        if self._bbox is None:
            return
        if tag == "input":
            checked = "checked" in attributes
            if attributes.get("type") == "radio":
                self._parts.append("(x)" if checked else "( )")
            else:
                self._parts.append("[x]" if checked else "[ ]")
        elif tag == "img":
            self._parts.append(f"[image: {attributes.get('alt') or ''}]")
        elif tag in _LINE_BREAKS:
            self._parts.append("\n")
        elif tag in ("td", "th"):
            self._parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if self._bbox is not None and tag in _LINE_BREAKS and tag != "div":
            self._parts.append("\n")
        if tag == "div":
            self._depth -= 1
            if self._depth == 0 and self._bbox is not None:
                self.blocks.append((self._bbox, "".join(self._parts)))
                self._bbox = None

    def handle_data(self, data: str) -> None:
        if self._bbox is not None:
            self._parts.append(data)


def blocks_to_text(page_html: str, cuts: tuple[float, float, float]) -> str:
    """The page's blocks as four labelled zones (header, vehicle_a, circumstances, vehicle_b), each in reading order.

    Args:
        page_html: Chandra's answer.
        cuts: The zone cuts of the page, from ``find_zone_cuts``.
    """
    parser = _BlockParser()
    parser.feed(page_html)
    boxes, texts = [], []
    for (x0, y0, x1, y1), raw in parser.blocks:
        lines = [" ".join(line.split()) for line in raw.splitlines()]
        text = "\n".join(line for line in lines if line)
        if text:
            boxes.append(np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]]))
            texts.append(text)
    return group_by_zone(boxes, texts, (1000, 1000), cuts)


class ChandraOcrEngine:
    """An ``OcrEngine`` that reads a page with Chandra-OCR-2 on a vLLM server and returns the text grouped by zone."""

    def __init__(
        self,
        server_url: str,
        model: str = "chandra-ocr-2",
        max_tokens: int = 8000,
        max_retries: int = 6,
        timeout: float = 1800,
        auth_token: str | None = None,
    ) -> None:
        """Create the engine.

        Args:
            server_url: Address of the vLLM server, without ``/v1``.
            model: The server's ``--served-model-name``.
            max_tokens: Cap on one answer. A normal page is about 5,500 tokens, so a loop is cut off at this size.
            max_retries: How many times to regenerate an answer that ends in a loop.
            timeout: Seconds to wait for one answer.
            auth_token: A Modal proxy token as ``<id>.<secret>``, sent as a Bearer header. The servers require one.
        """
        self._url, self._model = server_url.rstrip("/"), model
        self._headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}
        self._max_tokens, self._max_retries, self._timeout = (
            max_tokens,
            max_retries,
            timeout,
        )

    def _generate(
        self, image: bytes, mime: str, temperature: float, top_p: float
    ) -> str:
        data = base64.b64encode(image).decode()
        response = httpx.post(
            f"{self._url}/v1/chat/completions",
            timeout=self._timeout,
            headers=self._headers,
            json={
                "model": self._model,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": self._max_tokens,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{data}"},
                            },
                            {"type": "text", "text": PROMPT},
                        ],
                    }
                ],
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def read(self, image_path: Path) -> OcrResult:
        if not image_path.is_file():
            raise OcrError(f"image not found: {image_path}", form_id=image_path.stem)
        mime = (
            "image/jpeg"
            if image_path.suffix.lower() in (".jpg", ".jpeg")
            else "image/png"
        )
        started = time.perf_counter()
        try:
            image = image_path.read_bytes()
            cuts = find_zone_cuts(cv2.imread(str(image_path)))
            # Datalab's client: on a loop, regenerate warmer (0.2, 0.4, ... up to 0.8) with a wider top_p
            for attempt in range(self._max_retries + 1):
                temperature, top_p = (
                    (0.0, 0.1) if attempt == 0 else (min(0.2 * attempt, 0.8), 0.95)
                )
                page_html = self._generate(image, mime, temperature, top_p)
                if not _looped(page_html):
                    break
                logger.warning(
                    "chandra %s: answer ended in a loop (attempt %d)",
                    image_path.name,
                    attempt + 1,
                )
            text = blocks_to_text(page_html, cuts)
        except (
            httpx.HTTPError,
            KeyError,
            IndexError,
            ValueError,
        ) as exc:  # boundary with a network service
            raise OcrError(
                f"Chandra failed on {image_path.name}: {exc!r}", form_id=image_path.stem
            ) from exc
        seconds = time.perf_counter() - started
        logger.info(
            "ocr %s: %d characters in %.1fs", image_path.name, len(text), seconds
        )
        return OcrResult(text=text, seconds=seconds)
