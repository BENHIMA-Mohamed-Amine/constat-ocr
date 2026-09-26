"""Reads the frozen dataset and picks the forms a run is evaluated on."""

import json
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigurationError
from .schema import Record


@dataclass(frozen=True, slots=True)
class FormRef:
    """One form of the dataset."""

    form_id: str
    split: str
    image_path: Path
    truth_path: Path

    def load_truth(self) -> Record:
        """The answer key of this form."""
        return Record.model_validate_json(self.truth_path.read_text(encoding="utf-8"))


class DatasetReader:
    """Reads ``manifest.jsonl`` and ``dataset.json`` written by ``python -m generator.dataset``."""

    def __init__(self, root: Path) -> None:
        """Create the reader.

        Args:
            root: Dataset folder, for example ``data/synthetic``.

        Raises:
            ConfigurationError: If the dataset has not been generated.
        """
        manifest = root / "manifest.jsonl"
        if not manifest.is_file():
            raise ConfigurationError(
                f"no dataset at {root}: run `python -m generator.dataset` first"
            )
        self._root = root
        self._rows = [
            json.loads(line)
            for line in manifest.read_text(encoding="utf-8").splitlines()
        ]

    @property
    def fingerprint(self) -> str:
        """Hash of all answer keys: identifies exactly which data a run used."""
        return json.loads((self._root / "dataset.json").read_text(encoding="utf-8"))[
            "fingerprint"
        ]

    def first(self, split: str, count: int) -> list[FormRef]:
        """The first ``count`` forms of a split, in id order."""
        rows = [row for row in self._rows if row["split"] == split][:count]
        return [
            FormRef(
                row["id"], split, self._root / row["image"], self._root / row["truth"]
            )
            for row in rows
        ]
