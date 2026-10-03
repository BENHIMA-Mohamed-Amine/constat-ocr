"""Builds the repairer named in the settings. A new rule is a new registered class; nothing else changes."""

from collections.abc import Callable

from ..core.config import Settings
from ..core.errors import ConfigurationError
from .base import RepairRule
from .repairer import Repairer
from .rules import (
    AttestationNumberFormat,
    PhoneWithoutSeparators,
    PolicyWithoutSpaces,
    ValidityDatesInOrder,
)

_RULES: dict[str, Callable[[], RepairRule]] = {}


def register_repair_rule(rule: type[RepairRule]) -> type[RepairRule]:
    """Class decorator that registers a rule under its ``name``."""
    _RULES[rule.name] = rule
    return rule


for _rule in (
    ValidityDatesInOrder,
    PhoneWithoutSeparators,
    PolicyWithoutSpaces,
    AttestationNumberFormat,
):
    register_repair_rule(_rule)


def build_repairer(settings: Settings) -> Repairer | None:
    """The repairer for ``settings.repairs`` (comma-separated rule names, or ``all``), or None when it is empty.

    Raises:
        ConfigurationError: If a name is not registered.
    """
    if not settings.repairs:
        return None
    names = (
        list(_RULES)
        if settings.repairs == "all"
        else [n.strip() for n in settings.repairs.split(",")]
    )
    unknown = [name for name in names if name not in _RULES]
    if unknown:
        raise ConfigurationError(
            f"unknown repair rules {unknown}; known: {sorted(_RULES)}"
        )
    return Repairer([_RULES[name]() for name in names])
