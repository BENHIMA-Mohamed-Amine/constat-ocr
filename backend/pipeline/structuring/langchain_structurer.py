"""Fills the record with a LangChain chat model in JSON mode.

JSON mode returns valid JSON but does not enforce a schema, so the output format is described in the prompt (see
``output_format``) and the answer is then validated against ``Record``.
"""

import logging
import time

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from ..errors import StructuringError
from ..schema import Record
from .base import StructuringInput, StructuringResult
from .output_format import format_instructions
from .prompts import HUMAN_PROMPT, SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class LangChainStructurer:
    """A text-only ``Structurer``: the OCR text goes in, a validated ``Record`` comes out."""

    def __init__(
        self, model: BaseChatModel, system_prompt: str = SYSTEM_PROMPT
    ) -> None:
        """Create the structurer.

        Args:
            model: Any LangChain chat model that supports JSON mode.
            system_prompt: The task instructions; the output format is appended to them.
        """
        self._chain = model.with_structured_output(
            Record, method="json_mode", include_raw=True
        )
        self._system_prompt = f"{system_prompt}\n{format_instructions(Record)}"

    def structure(self, inputs: StructuringInput) -> StructuringResult:
        """Ask the model for the record of one form."""
        if inputs.ocr_text is None:
            raise StructuringError(
                "this structurer needs OCR text", form_id=inputs.form_id
            )
        messages = [
            SystemMessage(self._system_prompt),
            HumanMessage(HUMAN_PROMPT.format(ocr_text=inputs.ocr_text)),
        ]
        started = time.perf_counter()
        try:
            answer = self._chain.invoke(messages)
        except Exception as exc:  # boundary with a provider client: any failure (rate limit, network, bad request) is a failed form
            raise StructuringError(
                f"model call failed: {exc}", form_id=inputs.form_id
            ) from exc
        seconds = time.perf_counter() - started
        record = answer.get("parsed")
        if not isinstance(record, Record):
            raise StructuringError(
                f"model output did not match the schema: {answer.get('parsing_error')}",
                form_id=inputs.form_id,
            )
        if not record.model_dump(
            exclude_none=True
        ):  # e.g. the model wrapped its answer in another key: nothing was read
            raise StructuringError(
                "model returned a record with no value at all", form_id=inputs.form_id
            )
        usage = getattr(answer.get("raw"), "usage_metadata", None) or {}
        logger.info(
            "structure %s: %s in, %s out tokens, %.1fs",
            inputs.form_id,
            usage.get("input_tokens"),
            usage.get("output_tokens"),
            seconds,
        )
        return StructuringResult(
            record, usage.get("input_tokens", 0), usage.get("output_tokens", 0), seconds
        )
