"""Runs the repair rules in order and reports every field they changed."""

from collections.abc import Sequence

from ..core.schema import Record
from .base import Change, RepairResult, RepairRule


def _flatten(record: Record) -> dict[str, object]:
    """The record's fields by path, for example ``vehicle_a.plate``."""
    flat: dict[str, object] = {}
    for key, value in record.model_dump().items():
        if isinstance(value, dict):
            flat.update({f"{key}.{inner}": v for inner, v in value.items()})
        else:
            flat[key] = value
    return flat


class Repairer:
    """Applies a list of ``RepairRule`` to a record, in order."""

    def __init__(self, rules: Sequence[RepairRule]) -> None:
        """Create the repairer.

        Args:
            rules: The rules to apply, in order.
        """
        self._rules = list(rules)

    def repair(self, record: Record) -> RepairResult:
        """Apply every rule and list what each one changed."""
        changes: list[Change] = []
        for rule in self._rules:
            before = _flatten(record)
            record = rule.apply(record)
            after = _flatten(record)
            changes += [
                Change(rule.name, path, before[path], after[path])
                for path in after
                if before[path] != after[path]
            ]
        return RepairResult(record, changes)
