"""Compare one predicted record with its answer key, field by field."""

import jiwer

from ..errors import EvaluationError
from ..schema import Record, Vehicle
from .fields import FIELD_KINDS, TOP_LEVEL_FIELDS, VEHICLE_FIELDS, VEHICLES, FieldKind
from .normalize import normalize
from .results import FieldResult, FormResult, Usage

_TEXT_KINDS = (FieldKind.CRITICAL_TEXT, FieldKind.MINOR_TEXT)


class FormScorer:
    """Turns a (prediction, answer key) pair into a ``FormResult``."""

    def score(
        self,
        form_id: str,
        prediction: Record | None,
        truth: Record,
        usage: Usage | None = None,
    ) -> FormResult:
        """Score every field of a form.

        Args:
            form_id: Identifier of the form.
            prediction: What the pipeline produced, or ``None`` if it produced nothing. Every field then counts as wrong.
            truth: The answer key.
            usage: Time and tokens the form took, if measured.

        Raises:
            EvaluationError: If the answer key itself is missing a value.
        """
        results = [
            self._field(
                name,
                FIELD_KINDS[name],
                getattr(truth, name),
                getattr(prediction, name, None),
                form_id,
            )
            for name in TOP_LEVEL_FIELDS
        ]
        for side in VEHICLES:
            truth_vehicle: Vehicle | None = getattr(truth, side)
            if truth_vehicle is None:
                raise EvaluationError(f"answer key has no {side}", form_id=form_id)
            predicted_vehicle: Vehicle | None = getattr(prediction, side, None)
            results += [
                self._field(
                    f"{side}.{name}",
                    FIELD_KINDS[name],
                    getattr(truth_vehicle, name),
                    getattr(predicted_vehicle, name, None),
                    form_id,
                )
                for name in VEHICLE_FIELDS
            ]
        return FormResult(
            form_id=form_id,
            produced_output=prediction is not None,
            fields=tuple(results),
            usage=usage,
        )

    @staticmethod
    def _field(
        path: str,
        kind: FieldKind,
        expected: object,
        predicted: object | None,
        form_id: str,
    ) -> FieldResult:
        if expected is None:
            raise EvaluationError(
                f"answer key has no value for {path}", form_id=form_id
            )
        if kind is FieldKind.TICKS:
            wanted = sorted(set(expected))  # type: ignore[arg-type]
            got = None if predicted is None else sorted(set(predicted))  # type: ignore[arg-type]
            return FieldResult(path, kind, wanted, got, correct=got == wanted)
        if kind is FieldKind.TICK_COUNT:
            return FieldResult(
                path,
                kind,
                int(expected),
                None if predicted is None else int(predicted),  # type: ignore[arg-type]
                correct=predicted is not None and int(predicted) == int(expected),
            )  # type: ignore[arg-type]
        wanted_text = normalize(expected)
        got_text = None if predicted is None else normalize(predicted)
        if kind not in _TEXT_KINDS:
            return FieldResult(
                path, kind, wanted_text, got_text, correct=got_text == wanted_text
            )
        if not got_text:  # nothing read: every character is missing
            edits = len(wanted_text)
        else:
            out = jiwer.process_characters(wanted_text, got_text)
            edits = out.substitutions + out.deletions + out.insertions
        return FieldResult(
            path,
            kind,
            wanted_text,
            got_text,
            correct=got_text == wanted_text,
            edit_distance=edits,
            reference_length=len(wanted_text),
        )
