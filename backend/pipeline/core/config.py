"""Settings, read from the environment and from ``backend/.env`` (which git ignores).

Secrets are never given defaults or printed. Everything else has a default that matches what v1 was designed with.
"""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from .errors import ConfigurationError

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    """All settings of a run."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", extra="ignore", frozen=True
    )

    # secrets
    groq_api_key: SecretStr
    langsmith_api_key: SecretStr | None = None

    # observability (LangSmith reads these from the environment, see observability.py)
    langsmith_tracing: bool = True
    langsmith_project: str = "constat-ocr"

    # language model
    llm_provider: str = "groq"
    llm_model: str = "openai/gpt-oss-120b"
    llm_reasoning_effort: str | None = (
        "low"  # fewer hidden reasoning tokens: cheaper and faster, enough for extraction
    )
    llm_temperature: float = 0.0
    llm_max_retries: int = 5  # the client waits for the provider's retry-after before retrying a rate-limited call
    input_price_per_million: float = 0.15  # dollars per million input tokens (Groq)
    output_price_per_million: float = 0.60  # dollars per million output tokens (Groq)

    # ocr
    ocr_engine: str = "rapidocr-v6"  # see pipeline/ocr/factory.py for the names
    ocr_languages: tuple[str, ...] = ("fra",)

    # a Modal proxy token (wk-...) and its secret (ws-...): the model servers require them
    modal_proxy_token_id: str | None = None
    modal_proxy_token_secret: SecretStr | None = None
    chandra_ocr_2_server_url: str | None = (
        None  # the vLLM server of engine "chandra-ocr-2" (backend/serving/)
    )
    qwen3_8_27b_server_url: str | None = (
        None  # the vLLM server of the vision structurer (backend/serving/)
    )
    structurer: str = "text"  # "vision" reads the image with a vision model instead of the OCR text (see structuring/factory.py)
    read_marks: bool = False  # read ticks, tiles and circles from the template positions (needs the straightened page)
    repairs: str | None = (
        None  # comma-separated repair rules, or "all"; see pipeline/repair/factory.py
    )
    structuring_prompt: str = "flat"  # "columns" goes with the OCR engine that returns zone blocks (see structuring/prompts.py)

    # straightening: flatten the photo before OCR; None leaves the photo as it is (v1 and v2)
    straightener: str | None = (
        None  # see pipeline/straightening/factory.py for the names
    )

    # data and outputs
    dataset_dir: Path = REPO_DIR / "data" / "synthetic"
    runs_dir: Path = REPO_DIR / "runs"

    # evaluation set: the first N forms of each split (kept small by the LLM provider's free-plan limits)
    eval_dev_count: int = 5
    eval_test_count: int = 20

    def modal_proxy_token(self) -> str:
        """The proxy token the model servers require, as ``<id>.<secret>``.

        Raises:
            ConfigurationError: If the id or the secret is not set.
        """
        if not (self.modal_proxy_token_id and self.modal_proxy_token_secret):
            raise ConfigurationError(
                "MODAL_PROXY_TOKEN_ID and MODAL_PROXY_TOKEN_SECRET are not set"
            )
        return f"{self.modal_proxy_token_id}.{self.modal_proxy_token_secret.get_secret_value()}"
