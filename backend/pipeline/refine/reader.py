"""Re-reads chosen handwritten fields from crops of the page, with the same vision model that read the whole page.

The model sees a whole page at about one vision token per 32 by 32 pixels, so a handwritten digit is about half a token. The form is a
fixed template, so each field sits at a known place: the crop is cut there and enlarged, and every digit gets several tokens.
"""

import base64
import json
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import cv2
import httpx
import numpy as np

from ..core.errors import ConfigurationError
from ..core.schema import Record, Vehicle
from ..marks.align import to_template
from ..marks.layout import Layout, load_layout
from ..repair.base import Change
from ..structuring.prompts import CROP_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_MARGIN_X, _MARGIN_Y = (
    10,
    7,
)  # pixels (200 dpi) kept around a field box, for writing that runs a little outside it


@dataclass(frozen=True, slots=True)
class RefineResult:
    """The record with the re-read fields, and what changed."""

    record: Record
    changes: list[Change]
    failed: bool = False  # the server could not be reached: the record is the one that came in, and nothing should be saved as refined


class FieldRefiner:
    """Replaces chosen fields of a record by what a vision model reads from their crops."""

    def __init__(
        self,
        template_pdf: Path,
        server_url: str,
        fields: Sequence[str],
        model: str = "qwen3-8-27b",
        auth_token: str | None = None,
        scale: int = 3,
        timeout: float = 1800,
        retries: int = 3,
        retry_delay: float = 5,
    ) -> None:
        """Create the refiner.

        Args:
            template_pdf: The blank constat page, which gives the position of each field.
            server_url: Address of the vLLM server, without ``/v1``.
            fields: The fields to re-read: vehicle fields (``plate``, ``damage``) and header fields (``date``, ``phone_b``).
            model: The server's ``--served-model-name``.
            auth_token: A Modal proxy token as ``<id>.<secret>``, sent as a Bearer header.
            scale: How many times each crop is enlarged.
            timeout: Seconds to wait for the answer.
            retries: How many times a call that fails on the network or with a server error is tried.
            retry_delay: Seconds before the second try; each next wait is twice as long.

        Raises:
            ConfigurationError: If a field has no known position on the template.
        """
        self._layout: Layout = load_layout(template_pdf)
        known = self._layout.text_fields.keys() | self._layout.header_fields.keys()
        unknown = [f for f in fields if f not in known]
        if unknown:
            raise ConfigurationError(f"no position on the template for {unknown}")
        self._vehicle_fields = [f for f in fields if f in self._layout.text_fields]
        self._header_fields = [f for f in fields if f in self._layout.header_fields]
        self._url, self._model = server_url.rstrip("/"), model
        self._headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}
        self._scale, self._timeout = scale, timeout
        self._retries, self._retry_delay = retries, retry_delay

    def _cut(self, aligned: np.ndarray, box: tuple[int, int, int, int]) -> bytes:
        """One field of the aligned page, with its margin, enlarged, as PNG."""
        x0, y0, x1, y1 = box
        crop = aligned[
            max(y0 - _MARGIN_Y, 0) : y1 + _MARGIN_Y,
            max(x0 - _MARGIN_X, 0) : x1 + _MARGIN_X,
        ]
        crop = cv2.resize(
            crop, None, fx=self._scale, fy=self._scale, interpolation=cv2.INTER_CUBIC
        )
        return cv2.imencode(".png", crop)[1].tobytes()

    def crops(self, image_path: Path) -> dict[str, dict[str, bytes]]:
        """PNG crops by group (``header``, ``vehicle_a``, ``vehicle_b``) and field, cut from the page aligned on the template.

        Raises:
            ValueError: If the image cannot be read.
        """
        page = cv2.imread(str(image_path))
        if page is None:
            raise ValueError(f"image not found or unreadable: {image_path}")
        aligned = to_template(page, self._layout.template)
        out: dict[str, dict[str, bytes]] = {}
        if self._header_fields:
            out["header"] = {
                name: self._cut(aligned, self._layout.header_fields[name])
                for name in self._header_fields
            }
        if self._vehicle_fields:
            for side, vehicle in enumerate(("vehicle_a", "vehicle_b")):
                out[vehicle] = {
                    name: self._cut(aligned, self._layout.text_fields[name][side])
                    for name in self._vehicle_fields
                }
        return out

    def _schema(self) -> dict:
        def group(names: list[str]) -> dict:
            return {
                "type": "object",
                "properties": {
                    n: {"anyOf": [{"type": "string"}, {"type": "null"}]} for n in names
                },
                "required": names,
                "additionalProperties": False,
            }

        groups = {}
        if self._header_fields:
            groups["header"] = group(self._header_fields)
        if self._vehicle_fields:
            groups["vehicle_a"] = groups["vehicle_b"] = group(self._vehicle_fields)
        return {
            "type": "object",
            "properties": groups,
            "required": list(groups),
            "additionalProperties": False,
        }

    def _ask(self, crops: dict[str, dict[str, bytes]]) -> dict:
        content: list[dict] = []
        for group, by_field in crops.items():
            for name, png in by_field.items():
                data = base64.b64encode(png).decode()
                content += [
                    {"type": "text", "text": f"{group} {name}:"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{data}"},
                    },
                ]
        content.append({"type": "text", "text": "Answer with the JSON."})
        response = httpx.post(
            f"{self._url}/v1/chat/completions",
            headers=self._headers,
            timeout=self._timeout,
            json={
                "model": self._model,
                "temperature": 0,
                "max_tokens": 3000,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "fields", "schema": self._schema()},
                },
                "chat_template_kwargs": {"enable_thinking": False},
                "messages": [
                    {"role": "system", "content": CROP_SYSTEM_PROMPT},
                    {"role": "user", "content": content},
                ],
            },
        )
        response.raise_for_status()
        return json.loads(response.json()["choices"][0]["message"]["content"])

    @staticmethod
    def _read(answer: dict, group: str, name: str, before: str | None) -> str | None:
        """The value read for a field, or None when it is empty or the same as before."""
        value = (answer.get(group) or {}).get(name)
        if isinstance(value, str) and value.strip() and value.strip() != before:
            return value.strip()
        return None

    def refine(self, image_path: Path, record: Record) -> RefineResult:
        """Re-read the fields from the page. A field the model cannot read, or a failed call, keeps the value the record had."""
        crops = self.crops(image_path)
        for attempt in range(self._retries):
            try:
                answer = self._ask(crops)
                break
            except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
                logger.warning(
                    "crop reading failed for %s (try %d of %d): %r",
                    image_path.name,
                    attempt + 1,
                    self._retries,
                    exc,
                )
                if attempt + 1 < self._retries:
                    time.sleep(self._retry_delay * 2**attempt)
        else:
            return RefineResult(record, [], failed=True)
        changes: list[Change] = []
        update: dict[str, str | Vehicle] = {}
        for name in self._header_fields:
            before = getattr(record, name)
            if (value := self._read(answer, "header", name, before)) is not None:
                update[name] = value
                changes.append(Change("crop", name, before, value))
        if self._vehicle_fields:
            for vehicle in ("vehicle_a", "vehicle_b"):
                current = getattr(record, vehicle) or Vehicle()
                new = {}
                for name in self._vehicle_fields:
                    before = getattr(current, name)
                    if (value := self._read(answer, vehicle, name, before)) is not None:
                        new[name] = value
                        changes.append(
                            Change("crop", f"{vehicle}.{name}", before, value)
                        )
                if new:
                    update[vehicle] = current.model_copy(update=new)
        return RefineResult(record.model_copy(update=update), changes)
