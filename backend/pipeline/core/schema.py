"""The record: what the pipeline extracts, and the shape of the answer key.

This is the single definition of that shape. The LLM is asked to produce a ``Record``, the evaluation compares two
``Record`` objects, and a test checks that the data generator's answer keys match it. Every field is optional so the
model can answer ``null`` when the text does not contain a value, instead of guessing.

The accident sketch is not part of it: v1 does not read or score the sketch.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VehicleType = Literal["car", "moto", "tricycle", "bus", "truck"]
ImpactZone = Literal[
    "front",
    "rear",
    "left",
    "right",
    "front_left",
    "front_right",
    "rear_left",
    "rear_right",
]
LicenseCategory = Literal["A1", "A", "B", "C", "D", "E", "F"]


class Vehicle(BaseModel):
    """Everything the form says about one vehicle and its driver."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    vehicle_type: VehicleType | None = Field(
        None, description="Type of vehicle: the highlighted tile of the picture"
    )
    make: str | None = Field(
        None, description="Make of the vehicle, the 'Marque, Type' line"
    )
    model: str | None = Field(
        None, description="Model of the vehicle, the 'Véhicule' line"
    )
    plate: str | None = Field(None, description="Registration number, like 41654-A-55")
    coming_from: str | None = Field(
        None, description="'Venant de': street the vehicle came from"
    )
    going_to: str | None = Field(
        None, description="'Allant vers': street the vehicle was going to"
    )
    insured_last_name: str | None = Field(
        None, description="Last name of the insured person, the 'Assuré' block"
    )
    insured_first_name: str | None = Field(
        None, description="First name of the insured person"
    )
    insured_address: str | None = Field(
        None, description="Address of the insured person"
    )
    insurer: str | None = Field(
        None, description="Insurance company, 'Sté d'assurance'"
    )
    attestation_no: str | None = Field(
        None, description="Insurance attestation number, like 38A 158802852"
    )
    policy_no: str | None = Field(
        None, description="Insurance policy number ('N° de police'), digits only"
    )
    valid_from: str | None = Field(
        None, description="Attestation valid from, dd/mm/yyyy"
    )
    valid_to: str | None = Field(
        None, description="Attestation valid until, dd/mm/yyyy"
    )
    agency: str | None = Field(None, description="Insurance agency, office or broker")
    driver_last_name: str | None = Field(
        None, description="Last name of the driver, the 'Conducteur' block"
    )
    driver_first_name: str | None = Field(None, description="First name of the driver")
    driver_address: str | None = Field(None, description="Address of the driver")
    license_no: str | None = Field(
        None, description="Driving licence number, like 37/022297"
    )
    license_category: LicenseCategory | None = Field(
        None, description="Licence category that is circled"
    )
    license_issued: str | None = Field(
        None, description="Licence issue date, dd/mm/yyyy"
    )
    license_prefecture: str | None = Field(
        None, description="Prefecture that issued the licence"
    )
    license_valid_until: str | None = Field(
        None, description="Licence valid until, dd/mm/yyyy"
    )
    damage: str | None = Field(
        None, description="Visible damage to this vehicle, 'Dégâts apparents'"
    )
    circumstances: list[int] | None = Field(
        None,
        description="Numbers (1 to 23) of the circumstance boxes ticked for this vehicle; empty list if none",
    )
    circumstance_count: int | None = Field(
        None, description="Number written in the tick-count box of this vehicle"
    )
    impact_zone: ImpactZone | None = Field(
        None, description="Where the vehicle was hit: the zone of the blue patch"
    )


class Record(BaseModel):
    """One filled constat amiable."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    date: str | None = Field(None, description="Accident date, dd/mm/yyyy")
    time: str | None = Field(None, description="Accident time, like 19h00")
    place: str | None = Field(None, description="Exact place of the accident")
    phone_a: str | None = Field(
        None, description="Phone number on the left of the phone line (vehicle A side)"
    )
    phone_b: str | None = Field(
        None, description="Phone number on the right of the phone line (vehicle B side)"
    )
    other_damage: bool | None = Field(
        None,
        description="True if material damage to other vehicles or objects is marked OUI, false if NON",
    )
    vehicle_a: Vehicle | None = Field(
        None, description="Vehicle A: the left column of the form"
    )
    vehicle_b: Vehicle | None = Field(
        None, description="Vehicle B: the right column of the form"
    )
