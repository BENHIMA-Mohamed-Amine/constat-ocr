"""Where each step saves its output, so any step can be re-run or inspected on its own."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol


class ArtifactStore(Protocol):
    """Saves and loads the output of a step for a form."""

    def write_text(self, step: str, form_id: str, text: str) -> None:
        """Save text."""
        ...

    def write_json(self, step: str, form_id: str, data: Mapping[str, Any]) -> None:
        """Save a JSON document."""
        ...

    def read_text(self, step: str, form_id: str) -> str:
        """Load text saved earlier."""
        ...

    def read_json(self, step: str, form_id: str) -> dict[str, Any]:
        """Load a JSON document saved earlier."""
        ...

    def exists(self, step: str, form_id: str) -> bool:
        """Whether that step already saved something for that form."""
        ...

    def path(self, step: str, form_id: str, suffix: str) -> Path:
        """Where a step's file for a form lives, for artifacts that are not text or JSON (such as images)."""
        ...


class FileArtifactStore:
    """Keeps artifacts as files: ``<root>/<step>/<form_id>.txt`` or ``.json``."""

    def __init__(self, root: Path) -> None:
        """Create the store.

        Args:
            root: Folder that holds one sub-folder per step.
        """
        self._root = root

    def path(self, step: str, form_id: str, suffix: str) -> Path:
        return self._root / step / f"{form_id}{suffix}"

    def _path(self, step: str, form_id: str, suffix: str) -> Path:
        return self.path(step, form_id, suffix)

    def write_text(self, step: str, form_id: str, text: str) -> None:
        path = self._path(step, form_id, ".txt")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_json(self, step: str, form_id: str, data: Mapping[str, Any]) -> None:
        path = self._path(step, form_id, ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def read_text(self, step: str, form_id: str) -> str:
        return self._path(step, form_id, ".txt").read_text(encoding="utf-8")

    def read_json(self, step: str, form_id: str) -> dict[str, Any]:
        return json.loads(
            self._path(step, form_id, ".json").read_text(encoding="utf-8")
        )

    def exists(self, step: str, form_id: str) -> bool:
        return any(
            self._path(step, form_id, suffix).is_file() for suffix in (".txt", ".json")
        )
