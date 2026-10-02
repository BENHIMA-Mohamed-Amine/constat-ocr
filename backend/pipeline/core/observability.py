"""Switches LangSmith tracing on. LangSmith reads its settings from environment variables, not from our Settings."""

import os

from .config import Settings


def configure_tracing(settings: Settings) -> bool:
    """Export the LangSmith environment variables for this process.

    Returns:
        True if tracing is on (it needs the API key), False otherwise.
    """
    if not settings.langsmith_tracing or settings.langsmith_api_key is None:
        os.environ["LANGSMITH_TRACING"] = "false"
        return False
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key.get_secret_value()
    return True
