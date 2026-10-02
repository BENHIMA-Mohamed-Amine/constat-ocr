"""Builds the straightener named in the settings. A new method is a new registered builder; nothing else changes."""

from collections.abc import Callable

from ..core.config import Settings
from ..core.errors import ConfigurationError
from .base import Straightener

StraightenerBuilder = Callable[[Settings], Straightener]
_BUILDERS: dict[str, StraightenerBuilder] = {}


def register_straightener(
    name: str,
) -> Callable[[StraightenerBuilder], StraightenerBuilder]:
    """Decorator that registers a builder under a straightener name."""

    def decorator(builder: StraightenerBuilder) -> StraightenerBuilder:
        _BUILDERS[name] = builder
        return builder

    return decorator


@register_straightener("opencv")
def _opencv(settings: Settings) -> Straightener:
    from .opencv import OpenCvStraightener

    return OpenCvStraightener()


def build_straightener(settings: Settings) -> Straightener | None:
    """The straightener for ``settings.straightener``, or None when the photo is left as it is.

    Raises:
        ConfigurationError: If the name is not registered.
    """
    if settings.straightener is None:
        return None
    try:
        return _BUILDERS[settings.straightener](settings)
    except KeyError:
        raise ConfigurationError(
            f"unknown straightener {settings.straightener!r}; known: {sorted(_BUILDERS)}"
        ) from None
