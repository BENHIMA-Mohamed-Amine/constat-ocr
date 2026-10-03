"""The repair contract. A rule takes a record and returns a record; the ``Repairer`` runs the rules and reports what changed."""

from dataclasses import dataclass
from typing import Protocol

from ..core.schema import Record


class RepairRule(Protocol):
    """One deterministic fix to a record."""

    name: str

    def apply(self, record: Record) -> Record:
        """Return the record with the fix applied (the same record when there is nothing to fix)."""
        ...


@dataclass(frozen=True, slots=True)
class Change:
    """One field a rule changed."""

    rule: str
    path: str
    before: object
    after: object


@dataclass(frozen=True, slots=True)
class RepairResult:
    """The repaired record and every change made to it."""

    record: Record
    changes: list[Change]
