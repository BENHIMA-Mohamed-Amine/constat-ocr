"""Fills the record with a vision model on a vLLM server: the page image goes in, a validated ``Record`` comes out.

The server is asked for JSON that follows the ``Record`` schema (guided decoding), so the keys and types are always right; the
prompt says how each value must be written.
"""

import base64
import json
import logging
import time

import httpx
from pydantic import ValidationError

from ..core.errors import StructuringError
from ..core.schema import Record
from .base import StructuringInput, StructuringResult
from .output_format import format_instructions
from .prompts import VLM_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


class VisionStructurer:
    """A ``Structurer`` that reads the image with a vision model served by vLLM."""

    def __init__(
        self,
        server_url: str,
        model: str = "qwen3-8-27b",
        system_prompt: str = VLM_SYSTEM_PROMPT,
        max_tokens: int = 4000,
        timeout: float = 1800,
        auth_token: str | None = None,
    ) -> None:
        """Create the structurer.

        Args:
            server_url: Address of the vLLM server, without ``/v1``.
            model: The server's ``--served-model-name``.
            system_prompt: The task instructions; the output format is appended to them.
            max_tokens: Cap on one answer. A full record is about 1,000 tokens.
            timeout: Seconds to wait for one answer.
            auth_token: A Modal proxy token as ``<id>.<secret>``, sent as a Bearer header. The servers require one.
        """
        self._url, self._model = server_url.rstrip("/"), model
        self._headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}
        self._system_prompt = f"{system_prompt}\n{format_instructions(Record)}"
        self._max_tokens, self._timeout = max_tokens, timeout

    def structure(self, inputs: StructuringInput) -> StructuringResult:
        """Ask the model for the record of one form."""
        data = base64.b64encode(inputs.image_path.read_bytes()).decode()
        mime = _MIME.get(inputs.image_path.suffix.lower(), "image/jpeg")
        body = {
            "model": self._model,
            "temperature": 0,
            "max_tokens": self._max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "record", "schema": Record.model_json_schema()},
            },
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{data}"},
                        },
                        {"type": "text", "text": "Fill the record for this form."},
                    ],
                },
            ],
        }
        started = time.perf_counter()
        try:
            response = httpx.post(
                f"{self._url}/v1/chat/completions",
                headers=self._headers,
                json=body,
                timeout=self._timeout,
            )
            response.raise_for_status()
            reply = response.json()
        except httpx.HTTPError as exc:
            raise StructuringError(
                f"model call failed: {exc!r}", form_id=inputs.form_id
            ) from exc
        seconds = time.perf_counter() - started
        try:
            record = Record.model_validate(
                json.loads(reply["choices"][0]["message"]["content"])
            )
        except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
            raise StructuringError(
                f"model output did not match the schema: {exc!r}",
                form_id=inputs.form_id,
            ) from exc
        if not record.model_dump(exclude_none=True):
            raise StructuringError(
                "model returned a record with no value at all", form_id=inputs.form_id
            )
        usage = reply.get("usage", {})
        logger.info(
            "structure %s: %s in, %s out tokens, %.1fs",
            inputs.form_id,
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
            seconds,
        )
        return StructuringResult(
            record,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
            seconds,
        )
