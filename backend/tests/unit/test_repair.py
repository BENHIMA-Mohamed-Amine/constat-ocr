"""Unit (1 test): the repair step, on records the test builds itself.

One pytest item made of 4 named sub-checks. No dataset, model or network: each rule runs on a known record, the change report is
checked, the registry is exercised, and the graph is run with a fake reader and a fake structurer.
"""

from pathlib import Path

import pytest

from pipeline.core.config import Settings
from pipeline.core.errors import ConfigurationError
from pipeline.core.schema import Record
from pipeline.data.storage import FileArtifactStore
from pipeline.evaluation import FormScorer
from pipeline.flow.graph import build_graph
from pipeline.repair import Repairer, build_repairer
from pipeline.repair.rules import (
    AttestationNumberFormat,
    PhoneWithoutSeparators,
    PolicyWithoutSpaces,
    ValidityDatesInOrder,
)
from pipeline.structuring import StructuringResult

from ..checks import run_checks
from ..conftest import FakeOcrEngine, sample_truth

TRUTH = sample_truth(3)


def _with_vehicle(record: Record, side: str, **fields: str | None) -> Record:
    return record.model_copy(
        update={side: getattr(record, side).model_copy(update=fields)}
    )


def _rules_fix_what_they_claim() -> None:
    """Each rule fixes its own case and leaves everything else alone.

    The dates swap only when the start is after the end (vehicle B reversed, vehicle A left alone, an unreadable date left alone);
    phone and policy numbers lose their separators; an attestation number gets its three-characters-space-digits shape, and a value
    that does not look like one is not touched.
    """
    record = _with_vehicle(
        TRUTH,
        "vehicle_a",
        valid_from="01/02/2025",
        valid_to="31/01/2026",
        attestation_no="XYZ",
    )
    record = _with_vehicle(
        record,
        "vehicle_b",
        valid_from="16/07/2026",
        valid_to="17/07/2025",
        attestation_no="59a 15 0196573",
    )
    swapped = ValidityDatesInOrder().apply(record)
    assert (swapped.vehicle_b.valid_from, swapped.vehicle_b.valid_to) == (
        "17/07/2025",
        "16/07/2026",
    )
    assert (swapped.vehicle_a.valid_from, swapped.vehicle_a.valid_to) == (
        "01/02/2025",
        "31/01/2026",
    )
    unreadable = _with_vehicle(record, "vehicle_b", valid_from="??/07/2026")
    assert ValidityDatesInOrder().apply(unreadable) == unreadable

    phones = TRUTH.model_copy(update={"phone_a": "07 85.29-52 21", "phone_b": None})
    assert PhoneWithoutSeparators().apply(phones).phone_a == "0785295221"
    assert PhoneWithoutSeparators().apply(phones).phone_b is None

    policy = _with_vehicle(TRUTH, "vehicle_a", policy_no="6579549 44 0492 94")
    assert PolicyWithoutSpaces().apply(policy).vehicle_a.policy_no == "657954944049294"

    formatted = AttestationNumberFormat().apply(record)
    assert formatted.vehicle_b.attestation_no == "59A 150196573"
    assert formatted.vehicle_a.attestation_no == "XYZ"
    assert (
        AttestationNumberFormat()
        .apply(_with_vehicle(TRUTH, "vehicle_a", attestation_no="74a839185206"))
        .vehicle_a.attestation_no
        == "74A 839185206"
    )


def _repairer_reports_every_change() -> None:
    """The result lists each changed field with the rule, the path, the value before and the value after; nothing else.

    A record with nothing to fix gives an empty list, because a report that always lists something would hide what the step does.
    """
    noisy = TRUTH.model_copy(update={"phone_a": "07 85 29 52 21"})
    result = Repairer([PhoneWithoutSeparators(), PolicyWithoutSpaces()]).repair(noisy)
    assert [(c.rule, c.path, c.before, c.after) for c in result.changes] == [
        ("phone-digits", "phone_a", "07 85 29 52 21", "0785295221")
    ]
    assert Repairer([PhoneWithoutSeparators()]).repair(TRUTH).changes == []


def _registry_builds_named_rules() -> None:
    """No setting means no step, ``all`` builds every rule, a list builds those, and an unknown name fails loudly.

    A wrong name must not be skipped silently, because a run scored without the rule would be reported as a run with it.
    """

    def settings(repairs: str | None) -> Settings:
        return Settings(
            groq_api_key="dummy-key-for-tests", langsmith_tracing=False, repairs=repairs
        )

    assert build_repairer(settings(None)) is None
    assert len(build_repairer(settings("all"))._rules) == 4
    assert [
        r.name for r in build_repairer(settings("validity-dates, phone-digits"))._rules
    ] == ["validity-dates", "phone-digits"]
    with pytest.raises(ConfigurationError, match="validity-dates"):
        build_repairer(settings("nope"))


class _NoisyStructurer:
    """Returns the truth with spaces inside the first phone number, as the model sometimes does."""

    def structure(self, inputs) -> StructuringResult:
        record = TRUTH.model_copy(
            update={
                "phone_a": " ".join(
                    TRUTH.phone_a[i : i + 2] for i in range(0, len(TRUTH.phone_a), 2)
                )
            }
        )
        return StructuringResult(record, input_tokens=1, output_tokens=1, seconds=0.1)


def _graph_scores_the_repaired_record(tmp_path: Path) -> None:
    """With a repairer the score sees the repaired record and the repair is saved; without one it sees the model's record.

    The same noisy answer is scored twice: the phone field is wrong without the repair step and right with it, and
    ``repaired/<id>.json`` exists only in the second run.
    """
    state = {"form_id": "000000", "image_path": "x.jpg", "truth": TRUTH}

    def phone_a_correct(repairer: Repairer | None, folder: str) -> bool:
        store = FileArtifactStore(tmp_path / folder)
        graph = build_graph(
            FakeOcrEngine(), _NoisyStructurer(), FormScorer(), store, repairer=repairer
        )
        result = graph.invoke(state)["result"]
        assert store.exists("repaired", "000000") == (repairer is not None)
        return next(f.correct for f in result.fields if f.path == "phone_a")

    assert not phone_a_correct(None, "plain")
    assert phone_a_correct(Repairer([PhoneWithoutSeparators()]), "repaired")


def test_repair(tmp_path: Path) -> None:
    """The rules fix their cases, the changes are reported, the registry picks rules by name, and the graph scores the repair."""
    run_checks(
        [
            ("rules_fix_what_they_claim", _rules_fix_what_they_claim),
            ("repairer_reports_every_change", _repairer_reports_every_change),
            ("registry_builds_named_rules", _registry_builds_named_rules),
            (
                "graph_scores_the_repaired_record",
                lambda: _graph_scores_the_repaired_record(tmp_path),
            ),
        ]
    )
