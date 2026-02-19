import asyncio
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from merit.testing import Runner
from merit.testing.decorators import iter_case_groups, iter_cases
from merit.testing.models import (
    Case,
    CaseGroup,
    CaseGroupIterateModifier,
    CaseIterateModifier,
    TestItem,
)


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
    assert modifiers[0].min_passes == len(cases)


def test_iter_cases_decorator_with_min_passes():
    cases = [Case(sut_input_values={"x": 1}), Case(sut_input_values={"x": 2})]

    @iter_cases(*cases, min_passes=1)
    def my_test(case):
        pass

    modifiers = getattr(my_test, "__merit_modifiers__", [])
    assert len(modifiers) == 1
    assert isinstance(modifiers[0], CaseIterateModifier)
    assert modifiers[0].cases == tuple(cases)
    assert modifiers[0].min_passes == 1


def test_iter_cases_decorator_validation():
    cases = [
        Case(sut_input_values={"x": 1}),
        Case(sut_input_values={"x": 2}),
        Case(sut_input_values={"x": 3}),
    ]

    with pytest.raises(ValueError, match="min_passes must be >= 1"):

        @iter_cases(*cases, min_passes=0)
        def sample1(case):
            pass

    with pytest.raises(ValueError, match="min_passes .* cannot exceed cases count"):

        @iter_cases(*cases, min_passes=5)
        def sample2(case):
            pass


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
        modifiers=[CaseIterateModifier(cases=tuple(cases), min_passes=2)],
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


def test_runner_iter_cases_partial_pass_meets_min_passes(null_reporter):
    cases = [Case(sut_input_values={"x": i}) for i in range(1, 6)]

    def merit_partial_pass(case):
        if case.sut_input_values["x"] >= 4:
            raise AssertionError("fail")

    item = TestItem(
        name="merit_partial_pass",
        fn=merit_partial_pass,
        module_path=Path("sample.py"),
        is_async=False,
        params=["case"],
        modifiers=[CaseIterateModifier(cases=tuple(cases), min_passes=3)],
    )

    run_result = asyncio.run(Runner(reporters=[null_reporter]).run(items=[item]))
    parent_execution = run_result.result.executions[0]
    passed = sum(
        1 for sub in parent_execution.sub_executions if sub.result.status.value == "passed"
    )

    assert run_result.result.passed == 1
    assert len(parent_execution.sub_executions) == 5
    assert passed == 3
    assert parent_execution.result.status.value == "passed"


def test_runner_iter_cases_insufficient_passes(null_reporter):
    cases = [Case(sut_input_values={"x": i}) for i in range(1, 6)]

    def merit_mostly_fail(case):
        if case.sut_input_values["x"] > 2:
            raise AssertionError("fail")

    item = TestItem(
        name="merit_mostly_fail",
        fn=merit_mostly_fail,
        module_path=Path("sample.py"),
        is_async=False,
        params=["case"],
        modifiers=[CaseIterateModifier(cases=tuple(cases), min_passes=3)],
    )

    run_result = asyncio.run(Runner(reporters=[null_reporter]).run(items=[item]))
    parent_execution = run_result.result.executions[0]
    passed = sum(
        1 for sub in parent_execution.sub_executions if sub.result.status.value == "passed"
    )

    assert run_result.result.failed == 1
    assert len(parent_execution.sub_executions) == 5
    assert passed == 2
    assert parent_execution.result.status.value == "failed"


def test_runner_iter_cases_default_requires_all_passes(null_reporter):
    cases = [Case(sut_input_values={"x": i}) for i in range(1, 4)]

    def merit_one_fails(case):
        if case.sut_input_values["x"] == 2:
            raise AssertionError("fail")

    item = TestItem(
        name="merit_one_fails",
        fn=merit_one_fails,
        module_path=Path("sample.py"),
        is_async=False,
        params=["case"],
        modifiers=[CaseIterateModifier(cases=tuple(cases), min_passes=len(cases))],
    )

    run_result = asyncio.run(Runner(reporters=[null_reporter]).run(items=[item]))
    parent_execution = run_result.result.executions[0]

    assert run_result.result.failed == 1
    assert len(parent_execution.sub_executions) == 3
    assert parent_execution.result.status.value == "failed"


def test_iter_case_groups_decorator():
    groups = [
        CaseGroup(name="alpha", cases=[Case(sut_input_values={"x": 1})], min_passes=1),
        CaseGroup(name="beta", cases=[Case(sut_input_values={"x": 2})], min_passes=1),
    ]

    @iter_case_groups(*groups)
    def my_test(group, case):
        pass

    modifiers = getattr(my_test, "__merit_modifiers__", [])
    assert len(modifiers) == 1
    assert isinstance(modifiers[0], CaseGroupIterateModifier)
    assert modifiers[0].groups == tuple(groups)


def test_iter_case_groups_validation():
    with pytest.raises(ValueError, match="at least 1 item"):
        bad_empty = CaseGroup(name="empty", cases=[], min_passes=1)

        @iter_case_groups(bad_empty)
        def merit_empty(group, case):
            pass

    with pytest.raises(ValueError, match="greater than or equal to 1"):
        bad_low = CaseGroup(name="low", cases=[Case(sut_input_values={"x": 1})], min_passes=0)

        @iter_case_groups(bad_low)
        def merit_low(group, case):
            pass

    with pytest.raises(ValueError, match="cannot exceed cases count"):
        bad_high = CaseGroup(
            name="high",
            cases=[Case(sut_input_values={"x": 1}), Case(sut_input_values={"x": 2})],
            min_passes=3,
        )

        @iter_case_groups(bad_high)
        def merit_high(group, case):
            pass


def test_iter_case_groups_empty_is_deferred_to_execution():
    @iter_case_groups()
    def my_test(group, case):
        pass

    modifiers = getattr(my_test, "__merit_modifiers__", [])
    assert modifiers == []
    assert getattr(my_test, "__merit_definition_error__", None) == (
        "iter_case_groups requires at least one case group"
    )


def test_runner_iter_case_groups_injects_group_and_case_and_nests(null_reporter):
    g1_cases = [Case(sut_input_values={"x": 1}), Case(sut_input_values={"x": 2})]
    g2_cases = [Case(sut_input_values={"x": 3})]
    groups = [
        CaseGroup(name="alpha", cases=g1_cases, min_passes=1),
        CaseGroup(name="beta", cases=g2_cases, min_passes=1),
    ]
    seen_pairs: list[tuple[str, Any]] = []

    def merit_collect_group_case(group, case):
        seen_pairs.append((group.name, case.id))

    item = TestItem(
        name="merit_collect_group_case",
        fn=merit_collect_group_case,
        module_path=Path("sample.py"),
        is_async=False,
        params=["group", "case"],
        modifiers=[CaseGroupIterateModifier(groups=tuple(groups))],
    )

    run_result = asyncio.run(Runner(reporters=[null_reporter]).run(items=[item]))
    parent_execution = run_result.result.executions[0]

    assert run_result.result.passed == 1
    assert len(seen_pairs) == 3
    assert len(parent_execution.sub_executions) == 2
    assert [sub.definition.id_suffix for sub in parent_execution.sub_executions] == [
        "alpha",
        "beta",
    ]
    assert len(parent_execution.sub_executions[0].sub_executions) == 2
    assert len(parent_execution.sub_executions[1].sub_executions) == 1
    assert [
        sub.definition.id_suffix for sub in parent_execution.sub_executions[0].sub_executions
    ] == [str(case.id) for case in g1_cases]
    assert [
        sub.definition.id_suffix for sub in parent_execution.sub_executions[1].sub_executions
    ] == [str(case.id) for case in g2_cases]


def test_runner_iter_case_groups_uses_group_min_passes_and_all_groups_must_pass(
    null_reporter,
):
    groups = [
        CaseGroup(
            name="alpha",
            cases=[
                Case(sut_input_values={"x": 1}),
                Case(sut_input_values={"x": 2}),
                Case(sut_input_values={"x": 3}),
            ],
            min_passes=2,
        ),
        CaseGroup(
            name="beta",
            cases=[Case(sut_input_values={"x": 1}), Case(sut_input_values={"x": 2})],
            min_passes=2,
        ),
    ]

    def merit_group_threshold(group, case):
        if group.name == "alpha" and case.sut_input_values["x"] == 3:
            raise AssertionError("alpha fail")
        if group.name == "beta" and case.sut_input_values["x"] == 2:
            raise AssertionError("beta fail")

    item = TestItem(
        name="merit_group_threshold",
        fn=merit_group_threshold,
        module_path=Path("sample.py"),
        is_async=False,
        params=["group", "case"],
        modifiers=[CaseGroupIterateModifier(groups=tuple(groups))],
    )

    run_result = asyncio.run(Runner(reporters=[null_reporter]).run(items=[item]))
    parent_execution = run_result.result.executions[0]
    group_statuses = [sub.result.status.value for sub in parent_execution.sub_executions]

    assert run_result.result.failed == 1
    assert parent_execution.result.status.value == "failed"
    assert group_statuses == ["passed", "failed"]
