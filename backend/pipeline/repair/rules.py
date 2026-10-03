"""The repair rules. Each is small, deterministic, and changes only what it can be sure of.

A rule that comes from the synthetic forms rather than from real forms says so in its docstring.
"""

import re
from datetime import datetime

from ..core.schema import Record

_DATE_FORMAT = "%d/%m/%Y"
_VEHICLES = ("vehicle_a", "vehicle_b")


def _parse(value: str | None) -> datetime | None:
    try:
        return datetime.strptime(value or "", _DATE_FORMAT)
    except ValueError:
        return None


class ValidityDatesInOrder:
    """Swap an attestation's start and end dates when the start is after the end.

    The validity line of vehicle B is written right to left, so its two dates are read in reverse order. On any real attestation the
    start comes before the end.
    """

    name = "validity-dates"

    def apply(self, record: Record) -> Record:
        for side in _VEHICLES:
            vehicle = getattr(record, side)
            start, end = _parse(vehicle.valid_from), _parse(vehicle.valid_to)
            if start and end and start > end:
                swapped = vehicle.model_copy(
                    update={
                        "valid_from": vehicle.valid_to,
                        "valid_to": vehicle.valid_from,
                    }
                )
                record = record.model_copy(update={side: swapped})
        return record


class PhoneWithoutSeparators:
    """Remove spaces, dots and dashes from the phone numbers (``07 85 29 52 21`` becomes ``0785295221``)."""

    name = "phone-digits"

    def apply(self, record: Record) -> Record:
        update = {
            field: re.sub(r"[\s.\-]", "", value)
            for field in ("phone_a", "phone_b")
            if (value := getattr(record, field))
        }
        return record.model_copy(update=update)


class PolicyWithoutSpaces:
    """Remove spaces from the policy numbers (``6579549 44 0492 94`` becomes ``657954944049294``)."""

    name = "policy-spaces"

    def apply(self, record: Record) -> Record:
        for side in _VEHICLES:
            vehicle = getattr(record, side)
            if vehicle.policy_no:
                fixed = vehicle.model_copy(
                    update={"policy_no": re.sub(r"\s", "", vehicle.policy_no)}
                )
                record = record.model_copy(update={side: fixed})
        return record


class AttestationNumberFormat:
    """Write an attestation number as three characters, a space, then the digits (``59a 15 0196573`` becomes ``59A 150196573``).

    This is the format of the synthetic forms. Real attestation numbers differ between insurers, so this rule is only trusted on
    synthetic data.
    """

    name = "attestation-format"

    def apply(self, record: Record) -> Record:
        for side in _VEHICLES:
            vehicle = getattr(record, side)
            compact = re.sub(r"\s", "", vehicle.attestation_no or "")
            if re.fullmatch(r"\d{2}[A-Za-z]\d+", compact):
                fixed = vehicle.model_copy(
                    update={"attestation_no": f"{compact[:3].upper()} {compact[3:]}"}
                )
                record = record.model_copy(update={side: fixed})
        return record
