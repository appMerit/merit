from typing import Any, Callable
from typing_extensions import TypeVar

from merit.testing.decorators import parametrize
from merit.testing.models import Case

RefsT = TypeVar("RefsT", default=dict[str, Any])


def iter_cases(*cases: Case[RefsT]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to run a test function for each case in the provided sequence.

    Parameters
    ----------
    cases : Sequence[Case[RefsT]]
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

    ids = [str(c.id) for c in cases_list]
    return parametrize("case", cases_list, ids=ids)