"""Test runner for executing discovered tests."""

from __future__ import annotations

import asyncio
import re
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from merit.context import (
    metric_results_collector,
    runner_scope,
)
from merit.context.output_capture import sys_output_capture
from merit.metrics_.base import MetricResult
from merit.predicates import (
    close_predicate_api_client,
    create_predicate_api_client,
)
from merit.reports.base import Reporter
from merit.resources import ResourceResolver, get_registry
from merit.storage import SQLiteStore
from merit.testing.discovery import collect
from merit.testing.environment import capture_environment
from merit.testing.execution import DefaultTestFactory, ResultBuilder, TestTracer
from merit.testing.models import (
    MeritRun,
    MeritTestDefinition,
    TestExecution,
    TestResult,
    TestStatus,
)
from merit.tracing import clear_traces, get_span_collector, init_tracing

UUID_STRING_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class Runner:
    """Executes discovered tests with resource injection.

    Args:
        reporters: At least one reporter is required.

    Examples:
        from merit.reports import ConsoleReporter

        # Sequential execution (default)
        runner = Runner(reporters=[ConsoleReporter()])
        result = await runner.run(path="tests/")

        # Concurrent execution with 5 workers
        runner = Runner(reporters=[ConsoleReporter()], concurrency=5)
        result = await runner.run(path="tests/")
    """

    DEFAULT_MAX_CONCURRENCY = 10

    def __init__(
        self,
        *,
        reporters: list[Reporter],
        maxfail: int | None = None,
        fail_fast: bool = False,
        verbosity: int = 0,
        concurrency: int = 1,
        timeout: float | None = None,
        enable_tracing: bool = False,
        trace_output: Path | str | None = None,
        capture_output: bool = True,
        save_to_db: bool = True,
        db_path: Path | str | None = None,
        run_id: UUID | str | None = None,
    ) -> None:
        if not reporters:
            msg = "At least one reporter is required"
            raise ValueError(msg)

        self.reporters = reporters

        self.maxfail = maxfail if maxfail and maxfail > 0 else None
        self.fail_fast = fail_fast
        self.verbosity = verbosity
        self.timeout = timeout
        self.concurrency = concurrency if concurrency > 0 else self.DEFAULT_MAX_CONCURRENCY
        self.enable_tracing = enable_tracing
        self.trace_output = Path(trace_output) if trace_output else Path(".merit/traces.jsonl")
        self.capture_output = capture_output
        self.save_to_db = save_to_db
        self.db_path = Path(db_path) if db_path else None
        self._default_run_id = self._normalize_run_id(run_id)

        self._tracer = TestTracer(enabled=enable_tracing)
        self._result_builder = ResultBuilder()
        self._factory = DefaultTestFactory(
            tracer=self._tracer,
            result_builder=self._result_builder,
        )

        # Used in single.py test execution through run_context
        self.semaphore: asyncio.Semaphore | None = None
        self.stop_flag: bool = False

        self.merit_run: MeritRun | None = None
        self._store: SQLiteStore | None = None

    async def _notify_no_tests_found(self) -> None:
        await asyncio.gather(*[r.on_no_tests_found() for r in self.reporters])

    async def _notify_collection_complete(self, items: list[MeritTestDefinition]) -> None:
        await asyncio.gather(*[r.on_collection_complete(items) for r in self.reporters])

    async def _notify_test_complete(self, execution: TestExecution) -> None:
        await asyncio.gather(*[r.on_test_complete(execution) for r in self.reporters])

    async def _notify_run_complete(self, merit_run: MeritRun) -> None:
        await asyncio.gather(*[r.on_run_complete(merit_run) for r in self.reporters])

    async def _notify_run_stopped_early(self, failure_count: int) -> None:
        await asyncio.gather(*[r.on_run_stopped_early(failure_count) for r in self.reporters])

    async def _notify_tracing_enabled(self, output_path: Path) -> None:
        await asyncio.gather(*[r.on_tracing_enabled(output_path) for r in self.reporters])

    def _ensure_db_ready(self) -> None:
        """Initialize DB and run migrations. Raises MigrationError if not possible."""
        self._store = SQLiteStore(self.db_path)

    @staticmethod
    def _normalize_run_id(run_id: UUID | str | None) -> UUID | None:
        if run_id is None:
            return None
        if isinstance(run_id, UUID):
            return run_id
        if isinstance(run_id, str) and UUID_STRING_PATTERN.fullmatch(run_id):
            return UUID(run_id)
        msg = f"Invalid run_id '{run_id}'. Expected UUID string."
        raise ValueError(msg)

    def _resolve_run_id(self, run_id: UUID | str | None) -> UUID | None:
        normalized_run_id = self._normalize_run_id(run_id)
        if normalized_run_id is not None:
            return normalized_run_id
        return self._default_run_id

    def run_id_exists(self, run_id: UUID | str) -> bool:
        """Return True when run_id already exists in configured SQLite storage."""
        normalized_run_id = self._normalize_run_id(run_id)
        if normalized_run_id is None:
            msg = "run_id cannot be None."
            raise ValueError(msg)
        if self._store is None:
            self._ensure_db_ready()
        return self._store is not None and self._store.get_run(normalized_run_id) is not None

    async def run(
        self,
        items: list[MeritTestDefinition] | None = None,
        path: str | None = None,
        run_id: UUID | str | None = None,
    ) -> MeritRun:
        """Run tests and return results.

        Args:
            items: Pre-collected test items, or None to discover.
            path: Path to discover tests from if items not provided.
            run_id: Optional UUID for this run. Overrides constructor-level run_id.

        Returns:
            MeritRun with environment, results, and test executions.
        """
        selected_run_id = self._resolve_run_id(run_id)

        if self.save_to_db:
            self._ensure_db_ready()
            if selected_run_id and self.run_id_exists(selected_run_id):
                msg = f"run_id '{selected_run_id}' already exists"
                raise ValueError(msg)

        environment = capture_environment()
        if selected_run_id is None:
            self.merit_run = MeritRun(environment=environment)
        else:
            self.merit_run = MeritRun(environment=environment, run_id=selected_run_id)

        create_predicate_api_client()

        if self.enable_tracing:
            init_tracing(output_path=self.trace_output)
            clear_traces()

        if items is None:
            items = collect(path)

        if not items:
            await self._notify_no_tests_found()
            self.merit_run.end_time = datetime.now(UTC)
            return self.merit_run

        if self.fail_fast:
            for item in items:
                item.fail_fast = True

        metric_results: list[MetricResult] = []
        start = time.perf_counter()

        with (
            runner_scope(self),
            sys_output_capture(swallow=self.capture_output),
            metric_results_collector(metric_results),
        ):
            await self._notify_collection_complete(items)

            resolver = ResourceResolver(get_registry())

            self.semaphore = asyncio.Semaphore(self.concurrency)
            self.stop_flag = False

            execution = self._execute_run(
                items=items,
                resolver=resolver,
                merit_run=self.merit_run,
            )

            run_task = asyncio.create_task(execution)

            try:
                if self.timeout:
                    await asyncio.wait_for(run_task, timeout=self.timeout)
                else:
                    await run_task
            except TimeoutError:
                self.merit_run.result.stopped_early = True
                self.stop_flag = True

        await close_predicate_api_client()

        self.merit_run.result.total_duration_ms = (time.perf_counter() - start) * 1000
        self.merit_run.result.metric_results = metric_results.copy()
        self.merit_run.end_time = datetime.now(UTC)

        await self._notify_run_complete(self.merit_run)

        if self.enable_tracing:
            await self._notify_tracing_enabled(self.trace_output)

        if self.save_to_db and self._store:
            try:
                self._store.save_run(self.merit_run)
                if self.enable_tracing:
                    collector = get_span_collector()
                    if collector:
                        self._store.save_trace_spans(self.merit_run, collector)
            except Exception as e:
                warnings.warn(f"Failed to persist run to database: {e}", stacklevel=2)

        return self.merit_run

    async def _execute_run(
        self,
        *,
        items: list[MeritTestDefinition],
        resolver: ResourceResolver,
        merit_run: MeritRun,
    ) -> None:
        """Execute the test run with the given items and resolver."""
        try:
            if self.concurrency == 1:
                await self._run_sequential(items, resolver, merit_run)
            else:
                await self._run_concurrent(items, resolver, merit_run)
        finally:
            await resolver.teardown()

    async def _execute_item(
        self, item: MeritTestDefinition, resolver: ResourceResolver
    ) -> TestExecution:
        """Execute a single test with error handling."""
        test = self._factory.build(item)
        t_start = time.perf_counter()

        try:
            execution = await test.execute(resolver)
        except Exception as e:
            duration = (time.perf_counter() - t_start) * 1000
            return TestExecution(
                definition=item,
                result=TestResult(status=TestStatus.ERROR, duration_ms=duration, error=e),
                execution_id=uuid4(),
            )

        return execution

    async def _run_sequential(
        self, items: list[MeritTestDefinition], resolver: ResourceResolver, merit_run: MeritRun
    ) -> None:
        """Run tests sequentially."""
        failures = 0

        for item in items:
            if self.stop_flag:
                break
            execution = await self._execute_item(item, resolver)
            await self._notify_test_complete(execution)

            merit_run.result.executions.append(execution)

            if execution.result.status.is_failure:
                failures += 1
                if self.maxfail and failures >= self.maxfail:
                    merit_run.result.stopped_early = True
                    self.stop_flag = True
                    await self._notify_run_stopped_early(self.maxfail)
                    break

    async def _run_concurrent(
        self, items: list[MeritTestDefinition], resolver: ResourceResolver, merit_run: MeritRun
    ) -> None:
        """Run tests concurrently."""
        lock = asyncio.Lock()
        failures = 0
        results: list[TestExecution | None] = [None] * len(items)

        async def run_one(idx: int, item: MeritTestDefinition) -> None:
            nonlocal failures

            if self.stop_flag:
                return

            execution = await self._execute_item(item, resolver)

            if execution.result.status.is_failure:
                async with lock:
                    failures += 1
                    if self.maxfail and failures >= self.maxfail:
                        self.stop_flag = True
                        merit_run.result.stopped_early = True

            results[idx] = execution

        await asyncio.gather(
            *[run_one(i, item) for i, item in enumerate(items)], return_exceptions=True
        )

        for execution in results:
            if execution is not None:
                merit_run.result.executions.append(execution)
                await self._notify_test_complete(execution)

        if merit_run.result.stopped_early and self.maxfail:
            await self._notify_run_stopped_early(self.maxfail)
