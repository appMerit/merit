from typing import Any, Callable
from typing_extensions import TypeVar

from merit.testing.models import Case, CaseGroup, CaseGroupIterateModifier, CaseIterateModifier


RefsT = TypeVar("RefsT", default=dict[str, Any])


def iter_cases(
    *cases: Case[RefsT],
    min_passes: int | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to run a test function for each case in the provided sequence.

    Parameters
    ----------
    cases : Sequence[Case]
        The sequence of test cases to iterate over.
    min_passes : int | None
        Minimum passed case executions required for parent test to pass.
        Defaults to all cases.

    Returns:
    -------
    Callable
        A decorator that applies parametrization to the target function.
    """
    cases_list = list(cases)

    # backwards compatibility with old API
    if len(cases_list) == 1 and isinstance(cases_list[0], (list, tuple)):
        cases_list = list(cases_list[0])

    definition_error = None if cases_list else "iter_cases requires at least one case"
    actual_min_passes = len(cases_list)

    if cases_list:
        actual_min_passes = min_passes if min_passes is not None else len(cases_list)

        if actual_min_passes < 1:
            raise ValueError(f"min_passes must be >= 1, got {actual_min_passes}")

        if actual_min_passes > len(cases_list):
            raise ValueError(
                f"min_passes ({actual_min_passes}) cannot exceed cases count ({len(cases_list)})"
            )

    modifier = (
        CaseIterateModifier(cases=tuple(cases_list), min_passes=actual_min_passes)
        if cases_list
        else None
    )

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if definition_error:
            fn.__merit_definition_error__ = definition_error  # type: ignore[attr-defined]
            return fn

        if modifier is None:
            return fn

        modifiers: list[Any] = getattr(fn, "__merit_modifiers__", [])
        modifiers.append(modifier)
        fn.__merit_modifiers__ = modifiers  # type: ignore[attr-defined]
        return fn

    return decorator


def iter_case_groups(
    *groups: CaseGroup[Any, Any],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to run a test function for each case group."""
    groups_list = list(groups)

    definition_error = None if groups_list else "iter_case_groups requires at least one case group"
    modifier = CaseGroupIterateModifier(groups=tuple(groups_list)) if groups_list else None

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if definition_error:
            fn.__merit_definition_error__ = definition_error  # type: ignore[attr-defined]
            return fn

        if modifier is None:
            return fn

        modifiers: list[Any] = getattr(fn, "__merit_modifiers__", [])
        modifiers.append(modifier)
        fn.__merit_modifiers__ = modifiers  # type: ignore[attr-defined]
        return fn

    return decorator
