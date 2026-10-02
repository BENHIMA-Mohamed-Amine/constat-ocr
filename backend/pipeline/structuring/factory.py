"""Builds the chat model named in the settings. A new provider is a new registered builder; nothing else changes."""

from collections.abc import Callable

from langchain_core.language_models import BaseChatModel

from ..core.config import Settings
from ..core.errors import ConfigurationError

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
