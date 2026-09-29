"""Shared helper for merging several named sub-checks into one pytest test.

Used across the suite to keep "one test = one capability verified" (one pytest item per file) while
still naming exactly which sub-check failed, and reporting every failure at once rather than
stopping at the first — a merged test that only ever shows its first failure would hide the rest
on the next run too.
"""

from collections.abc import Callable, Iterable


def run_checks(checks: Iterable[tuple[str, Callable[[], None]]]) -> None:
    """Run every ``(name, check)`` pair, and fail with all the names/errors that failed, if any.

    Args:
        checks: Pairs of a human-readable check name and a zero-argument callable that raises
            ``AssertionError`` (with its own detail, e.g. a failing seed) on failure.

    Raises:
        AssertionError: Listing every check that failed and its message, if at least one did.
            Passes silently if all checks succeeded.
    """
    failures = []
    for name, check in checks:
        try:
            check()
        except AssertionError as exc:
            failures.append(f"{name}: {exc}")
    if failures:
        raise AssertionError(
            f"{len(failures)} check(s) failed:\n" + "\n".join(failures)
        )
