from typing import Any, Callable

from merit.testing.models import Case, CaseIterateModifier


def iter_cases(*cases: Case) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to run a test function for each case in the provided sequence.

    Parameters
    ----------
    cases : Sequence[Case]
        The sequence of test cases to iterate over.

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
    modifier = CaseIterateModifier(cases=tuple(cases_list)) if cases_list else None

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