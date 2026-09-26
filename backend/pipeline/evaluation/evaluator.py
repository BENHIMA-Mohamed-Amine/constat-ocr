"""Runs the metrics over the scored forms."""

from collections.abc import Sequence

from .metrics import (
    CategoryAccuracy,
    CharacterErrorRate,
    CheckboxScore,
    CostAndTime,
    FieldAccuracy,
    FormsWithoutCriticalError,
    Metric,
    MetricResult,
)
from .results import FormResult


class Evaluator:
    """Applies a list of metrics. New metrics are added by passing another ``Metric``; nothing here changes."""

    def __init__(self, metrics: Sequence[Metric]) -> None:
        """Create the evaluator.

        Args:
            metrics: The metrics to compute, in the order they should appear.
        """
        self._metrics = tuple(metrics)

    def summarize(self, results: Sequence[FormResult]) -> dict[str, MetricResult | int]:
        """Compute every metric over all forms."""
        summary: dict[str, MetricResult | int] = {
            "forms": len(results),
            "forms_with_output": sum(r.produced_output for r in results),
        }
        for metric in self._metrics:
            summary[metric.name] = metric.compute(results)
        return summary


def build_default_evaluator(
    input_price_per_million: float, output_price_per_million: float
) -> Evaluator:
    """The six metrics of docs/metrics.md."""
    return Evaluator(
        [
            FieldAccuracy(),
            FormsWithoutCriticalError(),
            CharacterErrorRate(),
            CheckboxScore(),
            CategoryAccuracy(),
            CostAndTime(input_price_per_million, output_price_per_million),
        ]
    )
