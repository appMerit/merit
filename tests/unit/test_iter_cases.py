import asyncio
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from merit.testing import Runner
from merit.testing.decorators import iter_cases
from merit.testing.models import Case, CaseIterateModifier, TestItem, validate_cases_for_sut


def test_case_generic_dict():
    """Test Case with dict as references."""
    case = Case[dict[str, Any]](
        references={"expected": "value"}, sut_input_values={"input": "data"}
    )
    assert case.references == {"expected": "value"}
    assert case.sut_input_values == {"input": "data"}


def test_case_generic_basemodel():
    """Test Case with BaseModel as references."""

    class MyRefs(BaseModel):
        expected: str
        score: float

    case = Case[MyRefs](
        references=MyRefs(expected="value", score=1.0), sut_input_values={"input": "data"}
    )
    assert isinstance(case.references, MyRefs)
    assert case.references.expected == "value"
    assert case.references.score == 1.0


def test_validate_cases_for_sut_valid():
    """Test validate_cases_for_sut with valid inputs."""

    def my_sut(name: str, age: int, *args, **kwargs):
        pass

    cases = [
        Case(sut_input_values={"name": "Alice", "age": 30}),
        Case(sut_input_values={"name": "Bob", "age": 25}),
    ]

    assert validate_cases_for_sut(cases, my_sut) == cases


def test_validate_cases_for_sut_invalid():
    """Test validate_cases_for_sut with invalid inputs."""

    def my_sut(name: str, age: int):
        pass

    # age should be int, but we provide str
    cases = [Case(sut_input_values={"name": "Alice", "age": "not-an-int"})]

    with pytest.raises(ValidationError):
        validate_cases_for_sut(cases, my_sut)


def test_iter_cases_decorator():
    """Test iter_cases decorator attaches cases correctly."""
    cases = [Case(sut_input_values={"x": 1}), Case(sut_input_values={"x": 2})]

    @iter_cases(*cases)
    def my_test(case):
        pass

    modifiers = getattr(my_test, "__merit_modifiers__", [])
    assert len(modifiers) == 1
    assert isinstance(modifiers[0], CaseIterateModifier)
    assert modifiers[0].cases == tuple(cases)


def test_iter_cases_empty_is_deferred_to_execution():
    @iter_cases()
    def my_test(case):
        pass

    modifiers = getattr(my_test, "__merit_modifiers__", [])
    assert modifiers == []
    assert getattr(my_test, "__merit_definition_error__", None) == (
        "iter_cases requires at least one case"
    )


def test_runner_iter_cases_injects_case_and_sets_suffix(null_reporter):
    seen_cases: list[Case[Any]] = []
    cases = [Case(sut_input_values={"x": 1}), Case(sut_input_values={"x": 2})]

    def merit_collect_case(case):
        seen_cases.append(case)

    item = TestItem(
        name="merit_collect_case",
        fn=merit_collect_case,
        module_path=Path("sample.py"),
        is_async=False,
        params=["case"],
        modifiers=[CaseIterateModifier(cases=tuple(cases))],
    )

    run_result = asyncio.run(Runner(reporters=[null_reporter]).run(items=[item]))
    parent_execution = run_result.result.executions[0]

    assert run_result.result.passed == 1
    assert seen_cases == cases
    assert len(parent_execution.sub_executions) == 2
    assert [sub.definition.id_suffix for sub in parent_execution.sub_executions] == [
        str(cases[0].id),
        str(cases[1].id),
    ]
