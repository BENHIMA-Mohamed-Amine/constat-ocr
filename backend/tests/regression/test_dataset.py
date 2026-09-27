"""Regression (1 test): the ``generator.dataset`` command is deterministic and correct.

One pytest item made of 3 named sub-checks, each calling ``generate`` directly (not the CLI) on
tiny counts into temporary directories, so the whole test runs in well under a minute without
touching the real ``data/synthetic/`` tree.
"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from generator.dataset import generate

from ..checks import run_checks


def _rows(out: Path) -> list[dict]:
    """Parse every line of ``manifest.jsonl`` in ``out``."""
    return [json.loads(line) for line in (out / "manifest.jsonl").read_text().splitlines()]


def _same_command_gives_identical_manifest() -> None:
    """The same seed/count/dev, run with 1 worker and with 2, produces byte-identical output.

    Compares the returned summary dicts and every manifest row (which includes each image's and
    each answer key's SHA-256) between two separate output directories. Different worker counts
    must not change which seed produces which form, or introduce any non-determinism (such as
    Pillow's own unseeded noise generator did, before it was replaced with seeded noise).
    """
    with TemporaryDirectory() as a, TemporaryDirectory() as b:
        first = generate(a, count=5, dev=2, seed=7, workers=1)
        second = generate(b, count=5, dev=2, seed=7, workers=2)
        assert first == second
        assert _rows(Path(a)) == _rows(Path(b))


def _split_and_level_are_as_asked() -> None:
    """The first ``dev`` forms are the dev split, the rest test; every form is at the "phone" level.

    Levels other than "phone" exist in the generator (``scan``, ``bad``) for one-off experiments
    via ``python -m generator``, but the frozen dataset that versions are compared on must only
    ever contain "phone" forms, and every form's image and answer-key file must actually exist on
    disk.
    """
    with TemporaryDirectory() as out:
        generate(out, count=5, dev=2, seed=7, workers=1)
        rows = _rows(Path(out))
        assert [row["split"] for row in rows] == ["dev", "dev", "test", "test", "test"]
        assert {row["level"] for row in rows} == {"phone"}
        for row in rows:
            assert (Path(out) / row["image"]).exists()
            assert (Path(out) / row["truth"]).exists()


def _different_seed_changes_the_fingerprint() -> None:
    """Two datasets generated with different seeds have different answer-key fingerprints.

    The fingerprint (docs/synthetic-data.md) is what lets a run's ``run.json`` prove it used the
    exact frozen dataset; if the seed had no effect, two different datasets could be mistaken for
    the same one.
    """
    with TemporaryDirectory() as out:
        first = generate(out, count=5, dev=2, seed=7, workers=1)
        second = generate(out, count=5, dev=2, seed=8, workers=1)
        assert first["fingerprint"] != second["fingerprint"]


def test_dataset_command_is_deterministic_and_correct() -> None:
    """The dataset command is reproducible, splits/labels forms as asked, and the seed matters.

    See the module docstring: runs 3 named sub-checks and reports every one that fails.
    """
    run_checks([
        ("same_command_gives_identical_manifest", _same_command_gives_identical_manifest),
        ("split_and_level_are_as_asked", _split_and_level_are_as_asked),
        ("different_seed_changes_the_fingerprint", _different_seed_changes_the_fingerprint),
    ])
