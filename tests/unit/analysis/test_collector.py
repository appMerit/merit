from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from merit.analysis.error_analysis.collector import ErrorDataCollector
from merit.analysis.types import GuardrailViolationError
from merit.assertions.base import AssertionRepr, AssertionResult
from merit.predicates.base import PredicateResult
from merit.storage.sqlite import SQLiteStore
from merit.testing.models.definition import MeritTestDefinition
from merit.testing.models.result import TestExecution, TestResult, TestStatus
from merit.testing.models.run import MeritRun, RunEnvironment, RunResult


def _dummy() -> None:
    return None


def _build_failure_exception() -> Exception:
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        return exc


def _build_execution(name: str, status: TestStatus, *, with_assertions: bool) -> TestExecution:
    assertion_results: list[AssertionResult] = []

    if with_assertions:
        assertion_results = [
            AssertionResult(
                expression_repr=AssertionRepr(
                    expr="a == b",
                    lines_above="value = 42",
                    lines_below="return value",
                    resolved_args={"a": "'A'", "b": "'B'"},
                ),
                passed=False,
                error_message="boom",
                predicate_results=[
                    PredicateResult(
                        actual="A",
                        reference="B",
                        name="facts_supported",
                        strict=True,
                        value=False,
                        confidence=0.4,
                        message="mismatch",
                    )
                ],
            ),
            AssertionResult(
                expression_repr=AssertionRepr(
                    expr="len(items) == 1",
                    lines_above="items = [1]",
                    lines_below="return items",
                    resolved_args={"items": "[1]"},
                ),
                passed=True,
                error_message=None,
                predicate_results=[],
            ),
        ]

    definition = MeritTestDefinition(
        name=name,
        fn=_dummy,
        module_path=Path("tests/test_file.py"),
        is_async=False,
    )

    result = TestResult(
        status=status,
        duration_ms=12.0,
        error=_build_failure_exception()
        if status in {TestStatus.FAILED, TestStatus.ERROR}
        else None,
        assertion_results=assertion_results,
    )

    return TestExecution(definition=definition, result=result)


@pytest.mark.asyncio
async def test_collector_builds_failure_signatures_with_cluster_key_and_traceback(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "merit.db")
    failed = _build_execution("test_fail", TestStatus.FAILED, with_assertions=True)
    passed = _build_execution("test_pass", TestStatus.PASSED, with_assertions=False)

    run = MeritRun(
        run_id=uuid4(),
        start_time=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
        end_time=datetime(2024, 1, 1, 12, 5, tzinfo=UTC),
        environment=RunEnvironment(merit_version="1.0.0"),
        result=RunResult(executions=[failed, passed], total_duration_ms=10.0),
    )
    store.save_run(run)

    collector = ErrorDataCollector(tmp_path / "merit.db")
    latest = await collector.get_latest_run_id()

    assert latest == run.run_id

    run_data = await collector.get_run(run.run_id)
    assert run_data["summary"]["failed"] == 1

    signatures = await collector.get_failure_signatures(
        run.run_id,
        run_timestamp=run_data["start_time"],
        max_failed_tests=10,
        max_traceback_chars=50000,
    )

    assert len(signatures) == 1

    signature = signatures[0]
    assert signature["case_id"]
    assert signature["timestamp"] == run_data["start_time"]
    assert signature["test_name"] == "test_fail"
    assert signature["test_module"] == "tests/test_file.py"
    assert "ASSERTION 1" in signature["cluster_key"]
    assert "status=passed" in signature["cluster_key"]
    assert "predicate=facts_supported" in signature["cluster_key"]

    fix_context = signature["fix_context"]
    assert fix_context["error_message"] == "boom"
    assert fix_context["test_file"] == "tests/test_file.py"
    assert len(fix_context["failed_assertions"]) == 1
    assert fix_context["failed_assertions"][0]["expression"] == "a == b"
    assert "assert a == b" in fix_context["failed_assertions"][0]["pretty"]

    assert len(fix_context["code_locations"]) > 0
    assert fix_context["code_locations"][0]["function"]


@pytest.mark.asyncio
async def test_collector_fails_when_failed_count_exceeds_guardrail(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "merit.db")
    run = MeritRun(
        run_id=uuid4(),
        start_time=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
        environment=RunEnvironment(merit_version="1.0.0"),
        result=RunResult(
            executions=[
                _build_execution("test_fail_1", TestStatus.FAILED, with_assertions=False),
                _build_execution("test_fail_2", TestStatus.ERROR, with_assertions=False),
            ]
        ),
    )
    store.save_run(run)

    collector = ErrorDataCollector(tmp_path / "merit.db")
    run_data = await collector.get_run(run.run_id)

    with pytest.raises(GuardrailViolationError):
        await collector.get_failure_signatures(
            run.run_id,
            run_timestamp=run_data["start_time"],
            max_failed_tests=1,
            max_traceback_chars=50000,
        )
