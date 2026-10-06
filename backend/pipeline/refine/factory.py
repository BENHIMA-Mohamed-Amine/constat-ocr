"""Builds the field refiner named in the settings, or none when no field is named."""

from ..core.config import BACKEND_DIR, Settings
from ..core.errors import ConfigurationError
from .reader import FieldRefiner


def build_refiner(settings: Settings) -> FieldRefiner | None:
    """The refiner for ``settings.refine_fields`` (comma-separated), or None when the setting is empty.

    Raises:
        ConfigurationError: If the server URL or a field name is not valid.
    """
    if not settings.refine_fields:
        return None
    if not settings.qwen3_8_27b_server_url:
        raise ConfigurationError("QWEN3_8_27B_SERVER_URL is not set")
    return FieldRefiner(
        BACKEND_DIR / "assets" / "constat-template.pdf",
        settings.qwen3_8_27b_server_url,
        [f.strip() for f in settings.refine_fields.split(",") if f.strip()],
        auth_token=settings.modal_proxy_token(),
        scale=settings.refine_scale,
    )
