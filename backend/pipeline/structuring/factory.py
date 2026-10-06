"""Builds the chat model, and the structurer, named in the settings. A new provider or structurer is a new registered builder;
nothing else changes."""

from collections.abc import Callable

from langchain_core.language_models import BaseChatModel

from ..core.config import Settings
from ..core.errors import ConfigurationError
from .base import Structurer

ModelBuilder = Callable[[Settings], BaseChatModel]
_BUILDERS: dict[str, ModelBuilder] = {}


def register_model_builder(provider: str) -> Callable[[ModelBuilder], ModelBuilder]:
    """Decorator that registers a builder under a provider name."""

    def decorator(builder: ModelBuilder) -> ModelBuilder:
        _BUILDERS[provider] = builder
        return builder

    return decorator


@register_model_builder("groq")
def _groq(settings: Settings) -> BaseChatModel:
    from langchain_groq import (
        ChatGroq,  # imported here so other providers do not need the package
    )

    return ChatGroq(
        model=settings.llm_model,
        api_key=settings.groq_api_key,
        temperature=settings.llm_temperature,
        max_retries=settings.llm_max_retries,
        reasoning_effort=settings.llm_reasoning_effort,
    )


def build_chat_model(settings: Settings) -> BaseChatModel:
    """The chat model for ``settings.llm_provider``.

    Raises:
        ConfigurationError: If the provider is not registered.
    """
    try:
        return _BUILDERS[settings.llm_provider](settings)
    except KeyError:
        raise ConfigurationError(
            f"unknown LLM provider {settings.llm_provider!r}; known: {sorted(_BUILDERS)}"
        ) from None


StructurerBuilder = Callable[[Settings], Structurer]
_STRUCTURERS: dict[str, StructurerBuilder] = {}


def register_structurer(name: str) -> Callable[[StructurerBuilder], StructurerBuilder]:
    """Decorator that registers a structurer builder under a name."""

    def decorator(builder: StructurerBuilder) -> StructurerBuilder:
        _STRUCTURERS[name] = builder
        return builder

    return decorator


@register_structurer("text")
def _text(settings: Settings) -> Structurer:
    from .langchain_structurer import LangChainStructurer
    from .prompts import PROMPTS

    return LangChainStructurer(
        build_chat_model(settings), PROMPTS[settings.structuring_prompt]
    )


@register_structurer("vision")
def _vision(settings: Settings) -> Structurer:
    from .prompts import PROMPTS
    from .vision import VisionStructurer

    if not settings.qwen3_8_27b_server_url:
        raise ConfigurationError("QWEN3_8_27B_SERVER_URL is not set")
    return VisionStructurer(
        settings.qwen3_8_27b_server_url,
        system_prompt=PROMPTS[settings.structuring_prompt],
        auth_token=settings.modal_proxy_token(),
    )


def build_structurer(settings: Settings) -> Structurer:
    """The structurer for ``settings.structurer``.

    Raises:
        ConfigurationError: If the structurer is not registered.
    """
    try:
        return _STRUCTURERS[settings.structurer](settings)
    except KeyError:
        raise ConfigurationError(
            f"unknown structurer {settings.structurer!r}; known: {sorted(_STRUCTURERS)}"
        ) from None
