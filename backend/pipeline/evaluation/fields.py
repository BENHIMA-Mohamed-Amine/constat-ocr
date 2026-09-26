"""How each field of the record is scored. One place to change when a field is added or reclassified."""

from enum import StrEnum

from ..schema import Record, Vehicle


class FieldKind(StrEnum):
    """The way a field is scored."""

    CRITICAL_TEXT = "critical_text"  # exact match; a wrong value can break a claim
    MINOR_TEXT = "minor_text"  # exact match; a wrong value is a nuisance
    TICKS = "ticks"  # the set of ticked circumstance boxes
    TICK_COUNT = "tick_count"  # the number written in the tick-count box
    CATEGORY = "category"  # a choice from a short list, or yes/no


# Field names are unique across the record and its vehicles, so one table covers both.
FIELD_KINDS: dict[str, FieldKind] = {
    # top level
    "date": FieldKind.CRITICAL_TEXT,
    "time": FieldKind.MINOR_TEXT,
    "place": FieldKind.MINOR_TEXT,
    "phone_a": FieldKind.MINOR_TEXT,
    "phone_b": FieldKind.MINOR_TEXT,
    "other_damage": FieldKind.CATEGORY,
    # per vehicle
    "vehicle_type": FieldKind.CATEGORY,
    "make": FieldKind.MINOR_TEXT,
    "model": FieldKind.MINOR_TEXT,
    "plate": FieldKind.CRITICAL_TEXT,
    "coming_from": FieldKind.MINOR_TEXT,
    "going_to": FieldKind.MINOR_TEXT,
    "insured_last_name": FieldKind.MINOR_TEXT,
    "insured_first_name": FieldKind.MINOR_TEXT,
    "insured_address": FieldKind.MINOR_TEXT,
    "insurer": FieldKind.CRITICAL_TEXT,
    "attestation_no": FieldKind.CRITICAL_TEXT,
    "policy_no": FieldKind.CRITICAL_TEXT,
    "valid_from": FieldKind.CRITICAL_TEXT,
    "valid_to": FieldKind.CRITICAL_TEXT,
    "agency": FieldKind.MINOR_TEXT,
    "driver_last_name": FieldKind.MINOR_TEXT,
    "driver_first_name": FieldKind.MINOR_TEXT,
    "driver_address": FieldKind.MINOR_TEXT,
    "license_no": FieldKind.CRITICAL_TEXT,
    "license_category": FieldKind.CATEGORY,
    "license_issued": FieldKind.CRITICAL_TEXT,
    "license_prefecture": FieldKind.MINOR_TEXT,
    "license_valid_until": FieldKind.CRITICAL_TEXT,
    "damage": FieldKind.MINOR_TEXT,
    "circumstances": FieldKind.TICKS,
    "circumstance_count": FieldKind.TICK_COUNT,
    "impact_zone": FieldKind.CATEGORY,
}
VEHICLES = ("vehicle_a", "vehicle_b")
TOP_LEVEL_FIELDS = tuple(name for name in Record.model_fields if name not in VEHICLES)
VEHICLE_FIELDS = tuple(Vehicle.model_fields)
