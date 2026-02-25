"""Tests for merit.testing.runner module."""

import asyncio
import os
import time
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from merit.reports.base import Reporter
from merit.resources import clear_registry, resource
from merit.testing.environment import _filter_env_vars, capture_environment
from merit.testing.models import (
    Case,
    CaseGroup,
    CaseGroupIterateModifier,
    CaseIterateModifier,
    ParameterSet,
    ParametrizeModifier,
    RunEnvironment,
    RunResult,
    TestExecution,
    TestItem,
    TestResult,
    TestStatus,
)
from merit.testing.runner import Runner


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear the global registry before and after each test."""
    clear_registry()
    yield
    clear_registry()


def make_item(
    fn,
    name: str | None = None,
    is_async: bool = False,
    params: list[str] | None = None,
    skip_reason: str | None = None,
    xfail_reason: str | None = None,
    xfail_strict: bool = False,
    id_suffix: str | None = None,
) -> TestItem:
    """Helper to create TestItem for testing."""
    return TestItem(
        fn=fn,
        name=name or fn.__name__,
        module_path=Path("test_module.py"),
        is_async=is_async,
        params=params or [],
        class_name=None,
        modifiers=[],
        tags=set(),
        skip_reason=skip_reason,
        xfail_reason=xfail_reason,
        xfail_strict=xfail_strict,
        id_suffix=id_suffix,
    )


class EventReporter(Reporter):
    """Reporter that records event timing and sequencing."""

    def __init__(self) -> None:
        self.start_time = 0.0
        self.event_times: list[tuple[str, str, float]] = []
        self.event_order: list[tuple[str, str]] = []
        self.subtest_event_times: list[tuple[str, str, float]] = []
        self.run_complete_elapsed = 0.0

    async def on_no_tests_found(self) -> None:
        pass

    async def on_collection_complete(self, _items: list[TestItem]) -> None:
        self.start_time = time.perf_counter()

    async def on_test_start(self, item: TestItem) -> None:
        elapsed = time.perf_counter() - self.start_time
        self.event_times.append(("start", item.name, elapsed))
        self.event_order.append(("start", item.name))

    async def on_test_complete(self, execution: TestExecution) -> None:
        elapsed = time.perf_counter() - self.start_time
        self.event_times.append(("complete", execution.item.name, elapsed))
        self.event_order.append(("complete", execution.item.name))

    async def on_subtest_complete(self, parent: TestItem, sub_execution: TestExecution) -> None:
        elapsed = time.perf_counter() - self.start_time
        suffix = sub_execution.item.id_suffix or ""
        self.subtest_event_times.append((parent.name, suffix, elapsed))

    async def on_run_complete(self, _merit_run) -> None:
        self.run_complete_elapsed = time.perf_counter() - self.start_time

    async def on_run_stopped_early(self, failure_count: int) -> None:
        pass

    async def on_tracing_enabled(self, output_path: Path) -> None:
        pass


class TestRunResult:
    """Tests for RunResult dataclass."""

    def test_counts_passed(self):
        result = RunResult()
        items = [make_item(lambda: None) for _ in range(3)]
        result.executions = [
            TestExecution(
                definition=items[0],
                result=TestResult(status=TestStatus.PASSED, duration_ms=1),
            ),
            TestExecution(
                definition=items[1],
                result=TestResult(status=TestStatus.PASSED, duration_ms=1),
            ),
            TestExecution(
                definition=items[2],
                result=TestResult(status=TestStatus.FAILED, duration_ms=1),
            ),
        ]
        assert result.passed == 2
        assert result.failed == 1
        assert result.total == 3

    def test_counts_all_statuses(self):
        result = RunResult()
        items = [make_item(lambda: None) for _ in range(6)]
        result.executions = [
            TestExecution(
                definition=items[0],
                result=TestResult(status=TestStatus.PASSED, duration_ms=1),
            ),
            TestExecution(
                definition=items[1],
                result=TestResult(status=TestStatus.FAILED, duration_ms=1),
            ),
            TestExecution(
                definition=items[2],
                result=TestResult(status=TestStatus.ERROR, duration_ms=1),
            ),
            TestExecution(
                definition=items[3],
                result=TestResult(status=TestStatus.SKIPPED, duration_ms=1),
            ),
            TestExecution(
                definition=items[4],
                result=TestResult(status=TestStatus.XFAILED, duration_ms=1),
            ),
            TestExecution(
                definition=items[5],
                result=TestResult(status=TestStatus.XPASSED, duration_ms=1),
            ),
        ]
        assert result.passed == 1
        assert result.failed == 1
        assert result.errors == 1
        assert result.skipped == 1
        assert result.xfailed == 1
        assert result.xpassed == 1


class TestEnvironmentCapture:
    """Tests for environment capture functionality."""

    def test_filter_env_vars_masks_keys(self):
        """Test that sensitive keys are masked."""
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-1234567890abcdef",
                "ANTHROPIC_API_KEY": "sk-ant-1234567890abcdef",
                "MODEL_VENDOR": "openai",
                "RANDOM_VAR": "should_not_be_captured",
            },
            clear=True,
        ):
            captured = _filter_env_vars()

            assert captured["MODEL_VENDOR"] == "openai"
            assert "RANDOM_VAR" not in captured
            assert captured["OPENAI_API_KEY"] == "***cdef"
            assert captured["ANTHROPIC_API_KEY"] == "***cdef"

    def test_filter_env_vars_short_keys(self):
        """Test masking of short keys."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "123"}, clear=True):
            captured = _filter_env_vars()
            assert captured["OPENAI_API_KEY"] == "***"

    def test_capture_environment_structure(self):
        """Test that capture_environment returns a valid RunEnvironment."""
        env = capture_environment()
        assert isinstance(env, RunEnvironment)
        assert env.python_version is not None
        assert env.platform is not None
        assert env.merit_version is not None


class TestRunner:
    """Tests for Runner class."""

    @pytest.mark.asyncio
    async def test_runs_passing_test(self, null_reporter):
        def passing_test():
            assert True

        item = make_item(passing_test)
        runner = Runner(reporters=[null_reporter])
        result = await runner.run(items=[item])

        assert result.result.passed == 1
        assert result.result.failed == 0

    @pytest.mark.asyncio
    async def test_runs_failing_test(self, null_reporter):
        def failing_test():
            assert False, "expected failure"

        item = make_item(failing_test)
        runner = Runner(reporters=[null_reporter])
        result = await runner.run(items=[item])

        assert result.result.failed == 1
        assert "expected failure" in str(result.result.executions[0].result.error)

    @pytest.mark.asyncio
    async def test_runs_async_test(self, null_reporter):
        async def async_test():
            await asyncio.sleep(0.001)
            assert True

        item = make_item(async_test, is_async=True)
        runner = Runner(reporters=[null_reporter])
        result = await runner.run(items=[item])

        assert result.result.passed == 1

    @pytest.mark.asyncio
    async def test_handles_exception_as_error(self, null_reporter):
        def error_test():
            raise RuntimeError("something broke")

        item = make_item(error_test)
        runner = Runner(reporters=[null_reporter])
        result = await runner.run(items=[item])

        assert result.result.errors == 1
        assert isinstance(result.result.executions[0].result.error, RuntimeError)

    @pytest.mark.asyncio
    async def test_skipped_test(self, null_reporter):
        def skipped_test():
            pass

        item = make_item(skipped_test, skip_reason="not ready")
        runner = Runner(reporters=[null_reporter])
        result = await runner.run(items=[item])

        assert result.result.skipped == 1

    @pytest.mark.asyncio
    async def test_xfail_test_fails_as_expected(self, null_reporter):
        def xfail_test():
            assert False

        item = make_item(xfail_test, xfail_reason="known bug")
        runner = Runner(reporters=[null_reporter])
        result = await runner.run(items=[item])

        assert result.result.xfailed == 1

    @pytest.mark.asyncio
    async def test_xfail_test_passes_unexpectedly(self, null_reporter):
        def xpass_test():
            pass

        item = make_item(xpass_test, xfail_reason="expected to fail")
        runner = Runner(reporters=[null_reporter])
        result = await runner.run(items=[item])

        assert result.result.xpassed == 1

    @pytest.mark.asyncio
    async def test_xfail_strict_fails_on_pass(self, null_reporter):
        def strict_xfail_test():
            pass

        item = make_item(strict_xfail_test, xfail_reason="must fail", xfail_strict=True)
        runner = Runner(reporters=[null_reporter])
        result = await runner.run(items=[item])

        assert result.result.failed == 1


class TestRunId:
    @pytest.mark.asyncio
    async def test_constructor_run_id_used_when_run_id_not_passed(self, null_reporter):
        run_id = uuid4()
        runner = Runner(reporters=[null_reporter], run_id=run_id, save_to_db=False)

        result = await runner.run(items=[make_item(lambda: None)])

        assert result.run_id == run_id

    @pytest.mark.asyncio
    async def test_run_run_id_overrides_constructor_run_id(self, null_reporter):
        constructor_run_id = uuid4()
        run_level_run_id = uuid4()
        runner = Runner(reporters=[null_reporter], run_id=constructor_run_id, save_to_db=False)

        result = await runner.run(items=[make_item(lambda: None)], run_id=run_level_run_id)

        assert result.run_id == run_level_run_id

    @pytest.mark.asyncio
    async def test_run_id_string_is_accepted_and_normalized(self, null_reporter):
        run_id = uuid4()
        runner = Runner(reporters=[null_reporter], run_id=str(run_id), save_to_db=False)

        result = await runner.run(items=[make_item(lambda: None)])

        assert isinstance(result.run_id, UUID)
        assert result.run_id == run_id

    def test_invalid_constructor_run_id_raises_value_error(self, null_reporter):
        with pytest.raises(ValueError, match="Invalid run_id"):
            Runner(reporters=[null_reporter], run_id="not-a-uuid", save_to_db=False)

    @pytest.mark.asyncio
    async def test_invalid_run_level_run_id_raises_value_error(self, null_reporter):
        runner = Runner(reporters=[null_reporter], save_to_db=False)

        with pytest.raises(ValueError, match="Invalid run_id"):
            await runner.run(items=[make_item(lambda: None)], run_id="not-a-uuid")

    @pytest.mark.asyncio
    async def test_reused_constructor_run_id_fails_on_second_run_when_db_enabled(
        self, null_reporter, tmp_path: Path
    ):
        run_id = uuid4()
        runner = Runner(reporters=[null_reporter], db_path=tmp_path / "merit.db", run_id=run_id)

        first_result = await runner.run(items=[make_item(lambda: None)])
        assert first_result.run_id == run_id

        with pytest.raises(ValueError, match="already exists"):
            await runner.run(items=[make_item(lambda: None)])

    @pytest.mark.asyncio
    async def test_reused_constructor_run_id_allowed_when_db_disabled(self, null_reporter):
        run_id = uuid4()
        runner = Runner(reporters=[null_reporter], run_id=run_id, save_to_db=False)

        first_result = await runner.run(items=[make_item(lambda: None)])
        second_result = await runner.run(items=[make_item(lambda: None)])

        assert first_result.run_id == run_id
        assert second_result.run_id == run_id


class TestResourceInjection:
    """Tests for resource injection in runner."""

    @pytest.mark.asyncio
    async def test_injects_resource(self, null_reporter):
        @resource
        def injected():
            return "injected_value"

        captured = []

        def test_with_resource(injected):
            captured.append(injected)

        item = make_item(test_with_resource, params=["injected"])
        runner = Runner(reporters=[null_reporter])
        await runner.run(items=[item])

        assert captured == ["injected_value"]

    @pytest.mark.asyncio
    async def test_trace_context_requires_trace_flag(self, null_reporter):
        def test_needs_trace(trace_context):
            pass

        item = make_item(test_needs_trace, params=["trace_context"])
        runner = Runner(reporters=[null_reporter])
        result = await runner.run(items=[item])

        assert result.result.errors == 1
        assert "Tracing is not enabled" in str(result.result.executions[0].result.error)

    @pytest.mark.asyncio
    async def test_ignores_unknown_params(self, null_reporter):
        def test_unknown(unknown_param):
            pass

        item = make_item(test_unknown, params=["unknown_param"])
        runner = Runner(reporters=[null_reporter])
        result = await runner.run(items=[item])

        # Should error because unknown_param is not provided
        assert result.result.errors == 1


class TestMaxfail:
    """Tests for maxfail functionality."""

    @pytest.mark.asyncio
    async def test_stops_after_maxfail(self, null_reporter):
        fail_count = 0

        def failing():
            nonlocal fail_count
            fail_count += 1
            assert False

        items = [make_item(failing, name=f"fail_{i}") for i in range(5)]
        runner = Runner(reporters=[null_reporter], maxfail=2)
        result = await runner.run(items=items)

        assert result.result.failed == 2
        assert result.result.stopped_early
        assert fail_count == 2

    @pytest.mark.asyncio
    async def test_maxfail_counts_errors_too(self, null_reporter):
        def error_test():
            raise RuntimeError

        items = [make_item(error_test, name=f"err_{i}") for i in range(5)]
        runner = Runner(reporters=[null_reporter], maxfail=1)
        result = await runner.run(items=items)

        assert result.result.errors == 1
        assert result.result.stopped_early


class TestConcurrency:
    """Tests for concurrent test execution."""

    @staticmethod
    def _make_parametrized_item(
        *,
        name: str,
        parameter_sets: tuple[ParameterSet, ...],
    ) -> TestItem:
        async def parametrized_case(delay: float) -> None:
            await asyncio.sleep(delay)

        return TestItem(
            fn=parametrized_case,
            name=name,
            module_path=Path("test_module.py"),
            is_async=True,
            params=["delay"],
            class_name=None,
            modifiers=[ParametrizeModifier(parameter_sets=parameter_sets)],
            tags=set(),
        )

    @staticmethod
    def _make_case_iterated_item(
        *,
        name: str,
        cases: tuple[Case[dict[str, float]], ...],
        min_passes: int,
    ) -> TestItem:
        async def case_iterated_test(case) -> None:
            await asyncio.sleep(case.sut_input_values["delay"])

        return TestItem(
            fn=case_iterated_test,
            name=name,
            module_path=Path("test_module.py"),
            is_async=True,
            params=["case"],
            class_name=None,
            modifiers=[CaseIterateModifier(cases=cases, min_passes=min_passes)],
            tags=set(),
        )

    @staticmethod
    def _make_case_group_iterated_item(
        *,
        name: str,
        groups: tuple[CaseGroup[dict[str, float], dict[str, float]], ...],
    ) -> TestItem:
        async def case_group_iterated_test(group, case) -> None:
            _ = group
            await asyncio.sleep(case.sut_input_values["delay"])

        return TestItem(
            fn=case_group_iterated_test,
            name=name,
            module_path=Path("test_module.py"),
            is_async=True,
            params=["group", "case"],
            class_name=None,
            modifiers=[CaseGroupIterateModifier(groups=groups)],
            tags=set(),
        )

    @pytest.mark.asyncio
    async def test_concurrent_execution(self, null_reporter):
        start_times = []

        async def slow_test():
            start_times.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.1)

        items = [make_item(slow_test, name=f"slow_{i}", is_async=True) for i in range(3)]
        runner = Runner(reporters=[null_reporter], concurrency=3)
        result = await runner.run(items=items)

        assert result.result.passed == 3
        # All should start within a small window (concurrent)
        assert max(start_times) - min(start_times) < 0.05

    @pytest.mark.asyncio
    async def test_concurrent_callbacks_stream_before_run_complete(self):
        items = []
        delays = [0.25, 0.05, 0.1]
        for idx, delay in enumerate(delays):

            async def test_fn(d=delay):
                await asyncio.sleep(d)

            items.append(make_item(test_fn, name=f"test_{idx}", is_async=True))

        reporter = EventReporter()
        runner = Runner(reporters=[reporter], concurrency=3, save_to_db=False)
        await runner.run(items=items)

        complete_times = [
            elapsed for kind, _name, elapsed in reporter.event_times if kind == "complete"
        ]
        assert complete_times
        assert min(complete_times) < 0.15
        assert min(complete_times) < reporter.run_complete_elapsed

    @pytest.mark.asyncio
    async def test_on_test_start_precedes_on_test_complete_per_item(self):
        items = []
        delays = [0.05, 0.1, 0.02]
        for idx, delay in enumerate(delays):

            async def test_fn(d=delay):
                await asyncio.sleep(d)

            items.append(make_item(test_fn, name=f"test_{idx}", is_async=True))

        reporter = EventReporter()
        runner = Runner(reporters=[reporter], concurrency=3, save_to_db=False)
        await runner.run(items=items)

        started = {name for kind, name in reporter.event_order if kind == "start"}
        completed = {name for kind, name in reporter.event_order if kind == "complete"}
        assert started == completed == {item.name for item in items}

        for item in items:
            start_idx = reporter.event_order.index(("start", item.name))
            complete_idx = reporter.event_order.index(("complete", item.name))
            assert start_idx < complete_idx

    @pytest.mark.asyncio
    async def test_concurrent_raises_when_on_test_start_fails(self):
        async def test_fn():
            await asyncio.sleep(0.01)

        class StartFailureReporter(EventReporter):
            async def on_test_start(self, item: TestItem) -> None:
                raise RuntimeError("start callback failed")

        runner = Runner(
            reporters=[StartFailureReporter()],
            concurrency=2,
            save_to_db=False,
        )
        with pytest.raises(RuntimeError, match="start callback failed"):
            await runner.run(items=[make_item(test_fn, name="test_start", is_async=True)])

    @pytest.mark.asyncio
    async def test_concurrent_raises_when_on_test_complete_fails(self):
        async def test_fn():
            await asyncio.sleep(0.01)

        class CompleteFailureReporter(EventReporter):
            async def on_test_complete(self, execution: TestExecution) -> None:
                raise RuntimeError("complete callback failed")

        runner = Runner(
            reporters=[CompleteFailureReporter()],
            concurrency=2,
            save_to_db=False,
        )
        with pytest.raises(RuntimeError, match="complete callback failed"):
            await runner.run(items=[make_item(test_fn, name="test_complete", is_async=True)])

    @pytest.mark.asyncio
    async def test_subtest_callbacks_stream_before_parent_completion(self):
        item = self._make_parametrized_item(
            name="test_parametrized",
            parameter_sets=(
                ParameterSet(values={"delay": 0.2}, id_suffix="slow"),
                ParameterSet(values={"delay": 0.01}, id_suffix="fast"),
                ParameterSet(values={"delay": 0.05}, id_suffix="mid"),
            ),
        )

        reporter = EventReporter()
        runner = Runner(reporters=[reporter], concurrency=3, save_to_db=False)
        await runner.run(items=[item])

        assert len(reporter.subtest_event_times) == 3
        parent_complete_elapsed = next(
            elapsed
            for kind, name, elapsed in reporter.event_times
            if kind == "complete" and name == item.name
        )
        assert max(elapsed for _parent, _suffix, elapsed in reporter.subtest_event_times) <= (
            parent_complete_elapsed
        )

    @pytest.mark.asyncio
    async def test_subtest_callback_count_matches_and_order_is_deterministic(self):
        parameter_sets = (
            ParameterSet(values={"delay": 0.15}, id_suffix="first"),
            ParameterSet(values={"delay": 0.01}, id_suffix="second"),
            ParameterSet(values={"delay": 0.05}, id_suffix="third"),
        )
        item = self._make_parametrized_item(
            name="test_parametrized_order", parameter_sets=parameter_sets
        )

        reporter = EventReporter()
        runner = Runner(reporters=[reporter], concurrency=3, save_to_db=False)
        merit_run = await runner.run(items=[item])

        assert len(reporter.subtest_event_times) == len(parameter_sets)
        execution = merit_run.result.executions[0]
        assert [sub.item.id_suffix for sub in execution.sub_executions] == [
            "first",
            "second",
            "third",
        ]

    @pytest.mark.asyncio
    async def test_case_iterated_callbacks_stream_and_order_is_deterministic(self):
        cases = (
            Case(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                sut_input_values={"delay": 0.15},
            ),
            Case(
                id=UUID("00000000-0000-0000-0000-000000000002"),
                sut_input_values={"delay": 0.01},
            ),
            Case(
                id=UUID("00000000-0000-0000-0000-000000000003"),
                sut_input_values={"delay": 0.05},
            ),
        )
        item = self._make_case_iterated_item(
            name="test_case_iterated_order",
            cases=cases,
            min_passes=len(cases),
        )

        reporter = EventReporter()
        runner = Runner(reporters=[reporter], concurrency=3, save_to_db=False)
        merit_run = await runner.run(items=[item])

        assert len(reporter.subtest_event_times) == len(cases)
        parent_complete_elapsed = next(
            elapsed
            for kind, name, elapsed in reporter.event_times
            if kind == "complete" and name == item.name
        )
        assert max(elapsed for _parent, _suffix, elapsed in reporter.subtest_event_times) <= (
            parent_complete_elapsed
        )

        execution = merit_run.result.executions[0]
        assert [sub.item.id_suffix for sub in execution.sub_executions] == [
            str(case.id) for case in cases
        ]

    @pytest.mark.asyncio
    async def test_case_group_iterated_callbacks_stream_and_order_is_deterministic(self):
        groups = (
            CaseGroup(
                name="alpha",
                cases=[
                    Case(
                        id=UUID("00000000-0000-0000-0000-000000000011"),
                        sut_input_values={"delay": 0.15},
                    )
                ],
                min_passes=1,
            ),
            CaseGroup(
                name="beta",
                cases=[
                    Case(
                        id=UUID("00000000-0000-0000-0000-000000000012"),
                        sut_input_values={"delay": 0.01},
                    )
                ],
                min_passes=1,
            ),
            CaseGroup(
                name="gamma",
                cases=[
                    Case(
                        id=UUID("00000000-0000-0000-0000-000000000013"),
                        sut_input_values={"delay": 0.05},
                    )
                ],
                min_passes=1,
            ),
        )
        item = self._make_case_group_iterated_item(
            name="test_case_group_iterated_order",
            groups=groups,
        )

        reporter = EventReporter()
        runner = Runner(reporters=[reporter], concurrency=3, save_to_db=False)
        merit_run = await runner.run(items=[item])

        group_names = {group.name for group in groups}
        group_events = [event for event in reporter.subtest_event_times if event[1] in group_names]
        assert len(group_events) == len(groups)
        parent_complete_elapsed = next(
            elapsed
            for kind, name, elapsed in reporter.event_times
            if kind == "complete" and name == item.name
        )
        assert max(elapsed for _parent, _suffix, elapsed in group_events) <= (
            parent_complete_elapsed
        )

        execution = merit_run.result.executions[0]
        assert [sub.item.id_suffix for sub in execution.sub_executions] == [
            group.name for group in groups
        ]

    @pytest.mark.asyncio
    async def test_sequential_execution(self, null_reporter):
        execution_order = []

        async def ordered_test(idx):
            execution_order.append(idx)
            await asyncio.sleep(0.01)

        items = []
        for i in range(3):

            async def test_fn(i=i):
                execution_order.append(i)
                await asyncio.sleep(0.01)

            items.append(make_item(test_fn, name=f"test_{i}", is_async=True))

        runner = Runner(reporters=[null_reporter], concurrency=1)
        result = await runner.run(items=items)

        assert result.result.passed == 3
        # Should execute in order
        assert execution_order == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_concurrency_zero_caps_at_default(self, null_reporter):
        runner = Runner(reporters=[null_reporter], concurrency=0)
        assert runner.concurrency == Runner.DEFAULT_MAX_CONCURRENCY

    @pytest.mark.asyncio
    async def test_concurrent_maxfail(self, null_reporter):
        fail_count = 0

        async def failing():
            nonlocal fail_count
            fail_count += 1
            await asyncio.sleep(0.01)
            assert False

        items = [make_item(failing, name=f"fail_{i}", is_async=True) for i in range(10)]
        runner = Runner(reporters=[null_reporter], concurrency=5, maxfail=2)
        result = await runner.run(items=items)

        assert result.result.stopped_early
        # May have more than 2 due to concurrent execution, but should stop
        assert result.result.failed >= 2


class TestTimeout:
    """Tests for run-level timeout."""

    @pytest.mark.asyncio
    async def test_timeout_stops_new_starts(self, null_reporter):
        async def slow_test():
            await asyncio.sleep(0.1)

        async def quick_test():
            await asyncio.sleep(0.01)

        items = [
            make_item(quick_test, name="quick", is_async=True),
            make_item(slow_test, name="slow", is_async=True),
        ]
        runner = Runner(reporters=[null_reporter], concurrency=1, timeout=0.05)
        result = await runner.run(items=items)

        assert result.result.stopped_early
        assert result.result.passed == 1
        assert result.result.skipped == 0
        assert result.result.total == 1

    @pytest.mark.asyncio
    async def test_no_timeout_by_default(self, null_reporter):
        async def quick_test():
            await asyncio.sleep(0.01)

        item = make_item(quick_test, is_async=True)
        runner = Runner(reporters=[null_reporter], concurrency=2)
        # timeout is None by default
        assert runner.timeout is None

        result = await runner.run(items=[item])
        assert result.result.passed == 1


class TestResultOrdering:
    """Tests for result ordering in concurrent execution."""

    @pytest.mark.asyncio
    async def test_results_ordered_by_discovery(self, null_reporter):
        async def varying_speed(delay):
            await asyncio.sleep(delay)

        items = []
        delays = [0.05, 0.01, 0.03]  # Different completion order
        for i, delay in enumerate(delays):

            async def test_fn(d=delay):
                await asyncio.sleep(d)

            items.append(make_item(test_fn, name=f"test_{i}", is_async=True))

        runner = Runner(reporters=[null_reporter], concurrency=3)
        result = await runner.run(items=items)

        # Results should be in discovery order, not completion order
        names = [r.item.name for r in result.result.executions]
        assert names == ["test_0", "test_1", "test_2"]


class TestResourceTeardown:
    """Tests for resource teardown during test runs."""

    @pytest.mark.asyncio
    async def test_case_resources_torn_down_between_tests(self, null_reporter):
        teardown_count = 0

        @resource(scope="case")
        def case_res():
            yield "value"
            nonlocal teardown_count
            teardown_count += 1

        def test_with_case(case_res):
            assert case_res == "value"

        items = [
            make_item(test_with_case, name="test_1", params=["case_res"]),
            make_item(test_with_case, name="test_2", params=["case_res"]),
        ]

        runner = Runner(reporters=[null_reporter])
        result = await runner.run(items=items)

        assert result.result.passed == 2
        assert teardown_count == 2

    @pytest.mark.asyncio
    async def test_suite_resources_shared(self, null_reporter):
        create_count = 0

        @resource(scope="suite")
        def suite_res():
            nonlocal create_count
            create_count += 1
            return f"suite_{create_count}"

        captured = []

        def test_suite(suite_res):
            captured.append(suite_res)

        items = [
            make_item(test_suite, name="test_1", params=["suite_res"]),
            make_item(test_suite, name="test_2", params=["suite_res"]),
        ]

        runner = Runner(reporters=[null_reporter])
        await runner.run(items=items)

        assert create_count == 1
        assert captured == ["suite_1", "suite_1"]

    @pytest.mark.asyncio
    async def test_session_resource_created_once_under_concurrency(self, null_reporter):
        create_count = 0
        teardown_count = 0

        @resource(scope="session")
        async def session_res():
            nonlocal create_count, teardown_count
            create_count += 1
            await asyncio.sleep(0.02)
            yield f"session_{create_count}"
            teardown_count += 1

        async def test_with_session(session_res):
            assert session_res == "session_1"

        items = [
            make_item(test_with_session, name=f"test_{i}", is_async=True, params=["session_res"])
            for i in range(8)
        ]

        runner = Runner(reporters=[null_reporter], concurrency=4)
        result = await runner.run(items=items)

        assert result.result.passed == len(items)
        assert create_count == 1
        assert teardown_count == 1


class TestResourceResolutionErrors:
    """Tests to ensure resource resolution errors are properly surfaced through the runner."""

    @pytest.mark.asyncio
    async def test_unknown_resource_param_causes_error(self, null_reporter):
        """Test that an unknown resource parameter results in an error."""

        def test_with_unknown(unknown_resource):
            pass

        item = make_item(test_with_unknown, params=["unknown_resource"])
        runner = Runner(reporters=[null_reporter])
        result = await runner.run(items=[item])

        assert result.result.errors == 1
        error = result.result.executions[0].result.error
        assert error is not None
        assert "Unknown resource" in str(error) or "unknown_resource" in str(error)

    @pytest.mark.asyncio
    async def test_resource_teardown_error_does_not_mask_test_error(self, null_reporter):
        """Test that resource teardown errors are surfaced but don't mask test errors."""

        @resource
        def resource_with_teardown_error():
            yield "value"
            raise RuntimeError("Teardown failed")

        def test_that_fails(resource_with_teardown_error):
            assert False, "Test assertion failed"

        item = make_item(test_that_fails, params=["resource_with_teardown_error"])
        runner = Runner(reporters=[null_reporter])
        result = await runner.run(items=[item])

        # Test should fail due to assertion, not error
        assert result.result.failed == 1

    @pytest.mark.asyncio
    async def test_resource_resolution_error_in_sequential_mode(self, null_reporter):
        """Test that resource resolution errors are surfaced in sequential execution mode."""

        @resource
        def sequential_resource():
            raise RuntimeError("Sequential resource error")

        def test_with_resource(sequential_resource):
            pass

        items = [
            make_item(test_with_resource, name="test_1", params=["sequential_resource"]),
            make_item(lambda: None, name="test_2"),
        ]
        runner = Runner(reporters=[null_reporter], concurrency=1)
        result = await runner.run(items=items)

        assert result.result.errors == 1
        assert result.result.executions[0].result.error is not None
        assert "Sequential resource error" in str(result.result.executions[0].result.error)

    @pytest.mark.asyncio
    async def test_resource_resolution_error_in_concurrent_mode(self, null_reporter):
        """Test that resource resolution errors are surfaced in concurrent execution mode."""

        @resource
        def concurrent_resource():
            raise RuntimeError("Concurrent resource error")

        def test_with_resource(concurrent_resource):
            pass

        items = [
            make_item(test_with_resource, name="test_1", params=["concurrent_resource"]),
            make_item(lambda: None, name="test_2"),
        ]
        runner = Runner(reporters=[null_reporter], concurrency=2)
        result = await runner.run(items=items)

        assert result.result.errors == 1
        # Find the errored execution
        errored = [e for e in result.result.executions if e.result.status == TestStatus.ERROR]
        assert len(errored) == 1
        assert "Concurrent resource error" in str(errored[0].result.error)

    @pytest.mark.asyncio
    async def test_suite_scope_resource_error_affects_subsequent_tests(self, null_reporter):
        """Test that errors in suite-scope resources affect all subsequent tests."""

        @resource(scope="suite")
        def suite_resource():
            raise RuntimeError("Suite resource failed")

        def test_with_suite(suite_resource):
            pass

        items = [
            make_item(test_with_suite, name="test_1", params=["suite_resource"]),
            make_item(test_with_suite, name="test_2", params=["suite_resource"]),
        ]
        runner = Runner(reporters=[null_reporter])
        result = await runner.run(items=items)

        # Both tests should error due to suite resource failure
        assert result.result.errors == 2
