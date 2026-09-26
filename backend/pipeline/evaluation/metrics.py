"""The metrics of docs/metrics.md. Each one aggregates the per-form results; adding a metric means adding a class."""

import math
from collections import Counter, defaultdict
from collections.abc import Sequence
from typing import Protocol

from .fields import FieldKind
from .results import FieldResult, FormResult

MetricResult = dict[str, object]
_TEXT_KINDS = (FieldKind.CRITICAL_TEXT, FieldKind.MINOR_TEXT)


class Metric(Protocol):
    """Anything that turns the per-form results into numbers."""

    name: str

    def compute(self, results: Sequence[FormResult]) -> MetricResult:
        """Aggregate the results of all forms."""
        ...


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _group(kind: FieldKind) -> str:
    return "critical" if kind is FieldKind.CRITICAL_TEXT else "minor"


def _fields(
    results: Sequence[FormResult], kinds: tuple[FieldKind, ...]
) -> list[FieldResult]:
    return [f for r in results for f in r.fields if f.kind in kinds]


class FieldAccuracy:
    """Metric 1: share of exactly right values, for critical and minor text fields, and per field."""

    name = "field_accuracy"

    def compute(self, results: Sequence[FormResult]) -> MetricResult:
        counts: dict[str, list[int]] = defaultdict(
            lambda: [0, 0]
        )  # key -> [correct, total]
        for f in _fields(results, _TEXT_KINDS):
            for key in (_group(f.kind), f"field:{f.name}"):
                counts[key][0] += f.correct
                counts[key][1] += 1
        entry = lambda c: {
            "correct": c[0],
            "total": c[1],
            "accuracy": _ratio(c[0], c[1]),
        }
        return {
            "critical": entry(counts["critical"]),
            "minor": entry(counts["minor"]),
            "per_field": {
                k.removeprefix("field:"): entry(v)
                for k, v in sorted(counts.items())
                if k.startswith("field:")
            },
        }


class FormsWithoutCriticalError:
    """Metric 2: share of forms whose critical fields are all right."""

    name = "forms_without_critical_error"

    def compute(self, results: Sequence[FormResult]) -> MetricResult:
        clean = sum(
            all(f.correct for f in r.fields if f.kind is FieldKind.CRITICAL_TEXT)
            for r in results
        )
        return {
            "forms": len(results),
            "without_critical_error": clean,
            "share": _ratio(clean, len(results)),
        }


class CharacterErrorRate:
    """Metric 3: character edits divided by expected characters, on text fields (partial credit for near misses)."""

    name = "character_error_rate"

    def compute(self, results: Sequence[FormResult]) -> MetricResult:
        totals: dict[str, list[int]] = defaultdict(
            lambda: [0, 0]
        )  # group -> [edits, characters]
        for f in _fields(results, _TEXT_KINDS):
            for key in ("overall", _group(f.kind)):
                totals[key][0] += f.edit_distance
                totals[key][1] += f.reference_length
        return {
            key: {
                "edits": totals[key][0],
                "characters": totals[key][1],
                "rate": _ratio(*totals[key]),
            }
            for key in ("overall", "critical", "minor")
        }


class CheckboxScore:
    """Metric 4: ticks found, missed and extra over all forms, plus how often the written tick count is right."""

    name = "checkbox_score"

    def compute(self, results: Sequence[FormResult]) -> MetricResult:
        found = missed = extra = 0
        for f in _fields(results, (FieldKind.TICKS,)):
            wanted, got = set(f.expected), set(f.predicted or [])  # type: ignore[arg-type]
            found += len(wanted & got)
            missed += len(wanted - got)
            extra += len(got - wanted)
        counts = _fields(results, (FieldKind.TICK_COUNT,))
        return {
            "ticks_found": found,
            "ticks_missed": missed,
            "ticks_extra": extra,
            "precision": _ratio(found, found + extra),
            "recall": _ratio(found, found + missed),
            "tick_count_correct": sum(f.correct for f in counts),
            "tick_count_total": len(counts),
        }


class CategoryAccuracy:
    """Metric 5: right choice per field, next to the score of always guessing the most common answer."""

    name = "category_accuracy"

    def compute(self, results: Sequence[FormResult]) -> MetricResult:
        by_field: dict[str, list[FieldResult]] = defaultdict(list)
        for f in _fields(results, (FieldKind.CATEGORY,)):
            by_field[f.name].append(f)
        out: MetricResult = {}
        for name, fields in sorted(by_field.items()):
            common, common_count = Counter(str(f.expected) for f in fields).most_common(
                1
            )[0]
            out[name] = {
                "correct": sum(f.correct for f in fields),
                "total": len(fields),
                "accuracy": _ratio(sum(f.correct for f in fields), len(fields)),
                "most_common_answer": common,
                "guess_most_common_accuracy": _ratio(common_count, len(fields)),
            }
        return out


class CostAndTime:
    """Metric 6: dollars per form, and the time the slowest 5% of forms take."""

    name = "cost_and_time"

    def __init__(
        self, input_price_per_million: float, output_price_per_million: float
    ) -> None:
        """Create the metric.

        Args:
            input_price_per_million: Dollars per million input tokens.
            output_price_per_million: Dollars per million output tokens.
        """
        self._input_price = input_price_per_million
        self._output_price = output_price_per_million

    def compute(self, results: Sequence[FormResult]) -> MetricResult:
        usages = [r.usage for r in results if r.usage is not None]
        if not usages:
            return {"forms_measured": 0}
        dollars = [
            (u.input_tokens * self._input_price + u.output_tokens * self._output_price)
            / 1e6
            for u in usages
        ]
        seconds = sorted(u.total_seconds for u in usages)
        return {
            "forms_measured": len(usages),
            "input_tokens": sum(u.input_tokens for u in usages),
            "output_tokens": sum(u.output_tokens for u in usages),
            "dollars_total": sum(dollars),
            "dollars_per_form": sum(dollars) / len(usages),
            "seconds_mean": sum(seconds) / len(seconds),
            "seconds_p95": seconds[max(0, math.ceil(0.95 * len(seconds)) - 1)],
        }  # nearest rank
