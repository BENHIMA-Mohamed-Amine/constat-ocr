"""Re-reads chosen handwritten fields from crops of the page, with the same vision model that read the whole page.

The model sees a whole page at about one vision token per 32 by 32 pixels, so a handwritten digit is about half a token. The form is a
fixed template, so each field sits at a known place: the crop is cut there and enlarged, and every digit gets several tokens.
"""

import base64
import json
import logging
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
    ) -> None:
        """Create the refiner.

        Args:
            template_pdf: The blank constat page, which gives the position of each field.
            server_url: Address of the vLLM server, without ``/v1``.
            fields: The vehicle fields to re-read, for example ``plate``.
            model: The server's ``--served-model-name``.
            auth_token: A Modal proxy token as ``<id>.<secret>``, sent as a Bearer header.
            scale: How many times each crop is enlarged.
            timeout: Seconds to wait for the answer.

        Raises:
            ConfigurationError: If a field has no known position on the template.
        """
        self._layout: Layout = load_layout(template_pdf)
        unknown = [f for f in fields if f not in self._layout.text_fields]
        if unknown:
            raise ConfigurationError(f"no position on the template for {unknown}")
        self._fields = list(fields)
        self._url, self._model = server_url.rstrip("/"), model
        self._headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}
        self._scale, self._timeout = scale, timeout

    def crops(self, image_path: Path) -> dict[str, dict[str, bytes]]:
        """PNG crops by vehicle (``vehicle_a``, ``vehicle_b``) and field, cut from the page aligned on the template and enlarged.

        Raises:
            ValueError: If the image cannot be read.
        """
        page = cv2.imread(str(image_path))
        if page is None:
            raise ValueError(f"image not found or unreadable: {image_path}")
        aligned = to_template(page, self._layout.template)
        out: dict[str, dict[str, bytes]] = {"vehicle_a": {}, "vehicle_b": {}}
        for side, vehicle in enumerate(out):
            for name in self._fields:
                x0, y0, x1, y1 = self._layout.text_fields[name][side]
                crop = aligned[
                    max(y0 - _MARGIN_Y, 0) : y1 + _MARGIN_Y,
                    max(x0 - _MARGIN_X, 0) : x1 + _MARGIN_X,
                ]
                crop = cv2.resize(
                    crop,
                    None,
                    fx=self._scale,
                    fy=self._scale,
                    interpolation=cv2.INTER_CUBIC,
                )
                out[vehicle][name] = cv2.imencode(".png", crop)[1].tobytes()
        return out

    def _schema(self) -> dict:
        vehicle = {
            "type": "object",
            "properties": {
                f: {"anyOf": [{"type": "string"}, {"type": "null"}]}
                for f in self._fields
            },
            "required": self._fields,
            "additionalProperties": False,
        }
        return {
            "type": "object",
            "properties": {"vehicle_a": vehicle, "vehicle_b": vehicle},
            "required": ["vehicle_a", "vehicle_b"],
            "additionalProperties": False,
        }

    def _ask(self, crops: dict[str, dict[str, bytes]]) -> dict:
        content: list[dict] = []
        for vehicle, by_field in crops.items():
            for name, png in by_field.items():
                data = base64.b64encode(png).decode()
                content += [
                    {"type": "text", "text": f"{vehicle} {name}:"},
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
                "max_tokens": 1000,
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

    def refine(self, image_path: Path, record: Record) -> RefineResult:
        """Re-read the fields from the page. A field the model cannot read, or a failed call, keeps the value the record had."""
        try:
            answer = self._ask(self.crops(image_path))
        except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
            logger.warning("crop reading failed for %s: %r", image_path.name, exc)
            return RefineResult(record, [])
        changes: list[Change] = []
        update: dict[str, Vehicle] = {}
        for vehicle in ("vehicle_a", "vehicle_b"):
            current = getattr(record, vehicle) or Vehicle()
            new = {}
            for name in self._fields:
                value = (answer.get(vehicle) or {}).get(name)
                before = getattr(current, name)
                if isinstance(value, str) and value.strip() and value.strip() != before:
                    new[name] = value.strip()
                    changes.append(
                        Change("crop", f"{vehicle}.{name}", before, new[name])
                    )
            if new:
                update[vehicle] = current.model_copy(update=new)
        return RefineResult(record.model_copy(update=update), changes)
