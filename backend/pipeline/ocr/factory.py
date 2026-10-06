"""Builds the OCR engine named in the settings. A new engine is a new registered builder; nothing else changes."""

from collections.abc import Callable

from ..core.config import Settings
from ..core.errors import ConfigurationError
from .base import OcrEngine

EngineBuilder = Callable[[Settings], OcrEngine]
_BUILDERS: dict[str, EngineBuilder] = {}


def register_ocr_engine(name: str) -> Callable[[EngineBuilder], EngineBuilder]:
    """Decorator that registers a builder under an engine name."""

    def decorator(builder: EngineBuilder) -> EngineBuilder:
        _BUILDERS[name] = builder
        return builder

    return decorator


@register_ocr_engine("tesseract")
def _tesseract(settings: Settings) -> OcrEngine:
    from .tesseract import LangChainTesseractEngine

    return LangChainTesseractEngine(settings.ocr_languages)


@register_ocr_engine("rapidocr")
def _rapidocr(settings: Settings) -> OcrEngine:
    from .rapidocr import RapidOcrEngine

    return RapidOcrEngine("v5")


@register_ocr_engine("rapidocr-v6")
def _rapidocr_v6(settings: Settings) -> OcrEngine:
    from .rapidocr import RapidOcrEngine

    return RapidOcrEngine("v6")


@register_ocr_engine("rapidocr-v6-columns")
def _rapidocr_v6_columns(settings: Settings) -> OcrEngine:
    from .columns import ColumnRapidOcrEngine

    return ColumnRapidOcrEngine("v6")


@register_ocr_engine("chandra-ocr-2")
def _chandra_ocr_2(settings: Settings) -> OcrEngine:
    from .chandra import ChandraOcrEngine

    if not settings.chandra_ocr_2_server_url:
        raise ConfigurationError("CHANDRA_OCR_2_SERVER_URL is not set")
    return ChandraOcrEngine(
        settings.chandra_ocr_2_server_url, auth_token=settings.modal_proxy_token()
    )


@register_ocr_engine("none")
def _none(settings: Settings) -> OcrEngine:
    from .none import NoOcrEngine

    return NoOcrEngine()


@register_ocr_engine("doctr")
def _doctr(settings: Settings) -> OcrEngine:
    from .doctr import DoctrEngine

    return DoctrEngine()


def build_ocr_engine(settings: Settings) -> OcrEngine:
    """The OCR engine for ``settings.ocr_engine``.

    Raises:
        ConfigurationError: If the engine is not registered.
    """
    try:
        return _BUILDERS[settings.ocr_engine](settings)
    except KeyError:
        raise ConfigurationError(
            f"unknown OCR engine {settings.ocr_engine!r}; known: {sorted(_BUILDERS)}"
        ) from None
