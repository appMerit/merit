"""Tests for merit.reports.console module."""

import io
from pathlib import Path

import pytest
from rich.console import Console

from merit.reports.console import ConsoleReporter
from merit.testing.models import MeritRun, TestExecution, TestItem, TestResult, TestStatus


class FakeLive:
    """Minimal stand-in for rich.live.Live used by unit tests."""

    instances: list["FakeLive"] = []

    def __init__(
        self,
        renderable,
        *,
        console: Console,
        auto_refresh: bool,
        refresh_per_second: int,
        transient: bool,
        redirect_stdout: bool = True,
        redirect_stderr: bool = True,
    ) -> None:
        self.console = console
        self.auto_refresh = auto_refresh
        self.refresh_per_second = refresh_per_second
        self.transient = transient
        self.redirect_stdout = redirect_stdout
        self.redirect_stderr = redirect_stderr
        self.started = False
        self.stopped = False
        self.renderables = [renderable]
        self.instances.append(self)

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def update(self, renderable, *, refresh: bool = False) -> None:
        _ = refresh
        self.renderables.append(renderable)


def make_item(
    name: str,
    module_path: str,
    *,
    id_suffix: str | None = None,
) -> TestItem:
    return TestItem(
        name=name,
        fn=lambda: None,
        module_path=Path(module_path),
        is_async=False,
        params=[],
        class_name=None,
        modifiers=[],
        tags=set(),
        id_suffix=id_suffix,
    )


def make_execution(
    item: TestItem,
    status: TestStatus,
    duration_ms: float,
    *,
    error: Exception | None = None,
    sub_executions: list[TestExecution] | None = None,
) -> TestExecution:
    return TestExecution(
        definition=item,
        result=TestResult(status=status, duration_ms=duration_ms, error=error),
        sub_executions=sub_executions or [],
    )


def render_to_text(renderable) -> str:
    output = io.StringIO()
    console = Console(file=output, force_terminal=False, color_system=None, width=120)
    console.print(renderable)
    return output.getvalue()


@pytest.mark.asyncio
async def test_verbose_live_output_grouped_by_file(monkeypatch):
    monkeypatch.setattr("merit.reports.console.Live", FakeLive)
    FakeLive.instances.clear()

    output = io.StringIO()
    console = Console(file=output, force_terminal=True, color_system=None, width=120)
    reporter = ConsoleReporter(console=console, verbosity=1)

    auth_login = make_item("test_login", "tests/test_auth.py")
    auth_logout = make_item("test_logout", "tests/test_auth.py")
    users_create = make_item("test_create", "tests/test_users.py")

    await reporter.on_collection_complete([auth_login, auth_logout, users_create])
    await reporter.on_test_start(auth_login)
    await reporter.on_test_start(users_create)
    await reporter.on_test_complete(make_execution(users_create, TestStatus.PASSED, 45.1))
    await reporter.on_test_complete(
        make_execution(auth_login, TestStatus.FAILED, 120.3, error=AssertionError("boom"))
    )
    await reporter.on_test_start(auth_logout)
    await reporter.on_test_complete(make_execution(auth_logout, TestStatus.PASSED, 22.0))

    assert FakeLive.instances
    assert FakeLive.instances[-1].redirect_stdout is False
    assert FakeLive.instances[-1].redirect_stderr is False
    text = render_to_text(FakeLive.instances[-1].renderables[-1])

    assert text.count("tests/test_auth.py") == 1
    assert text.count("tests/test_users.py") == 1
    assert "test_auth::test_login" in text
    assert "test_auth::test_logout" in text
    assert "test_users::test_create" in text
    assert "FAILED" in text


@pytest.mark.asyncio
async def test_compact_live_symbols_replace_running_marker(monkeypatch):
    monkeypatch.setattr("merit.reports.console.Live", FakeLive)
    FakeLive.instances.clear()

    output = io.StringIO()
    console = Console(file=output, force_terminal=True, color_system=None, width=120)
    reporter = ConsoleReporter(console=console, verbosity=0)

    item = make_item("test_login", "tests/test_auth.py")

    await reporter.on_collection_complete([item])
    await reporter.on_test_start(item)
    running_text = render_to_text(FakeLive.instances[-1].renderables[-1])
    assert "⋯" in running_text

    await reporter.on_test_complete(make_execution(item, TestStatus.PASSED, 15.0))
    done_text = render_to_text(FakeLive.instances[-1].renderables[-1])
    assert "✓" in done_text


@pytest.mark.asyncio
async def test_quiet_live_progress_counter(monkeypatch):
    monkeypatch.setattr("merit.reports.console.Live", FakeLive)
    FakeLive.instances.clear()

    output = io.StringIO()
    console = Console(file=output, force_terminal=True, color_system=None, width=120)
    reporter = ConsoleReporter(console=console, verbosity=-1)

    first = make_item("test_one", "tests/test_progress.py")
    second = make_item("test_two", "tests/test_progress.py")

    await reporter.on_collection_complete([first, second])
    text = render_to_text(FakeLive.instances[-1].renderables[-1])
    assert "0/2 complete" in text

    await reporter.on_test_start(first)
    await reporter.on_test_complete(make_execution(first, TestStatus.PASSED, 5.0))
    text = render_to_text(FakeLive.instances[-1].renderables[-1])
    assert "1/2 complete" in text

    await reporter.on_test_start(second)
    await reporter.on_test_complete(make_execution(second, TestStatus.PASSED, 6.0))
    text = render_to_text(FakeLive.instances[-1].renderables[-1])
    assert "2/2 complete" in text


@pytest.mark.asyncio
async def test_non_terminal_fallback_uses_static_output():
    output = io.StringIO()
    console = Console(file=output, force_terminal=False, color_system=None, width=120)
    reporter = ConsoleReporter(console=console, verbosity=0)

    item = make_item("test_login", "tests/test_auth.py")
    execution = make_execution(item, TestStatus.PASSED, 20.0)

    await reporter.on_collection_complete([item])
    await reporter.on_test_start(item)
    await reporter.on_test_complete(execution)

    merit_run = MeritRun()
    merit_run.result.executions = [execution]
    await reporter.on_run_complete(merit_run)

    text = output.getvalue()
    assert "Collected 1 tests" in text
    assert "tests/test_auth.py" in text
    assert "SUMMARY" in text


@pytest.mark.asyncio
async def test_failures_collected_and_rendered_on_run_complete():
    output = io.StringIO()
    console = Console(file=output, force_terminal=False, color_system=None, width=120)
    reporter = ConsoleReporter(console=console, verbosity=1)

    item = make_item("test_failure", "tests/test_failures.py")
    execution = make_execution(
        item,
        TestStatus.FAILED,
        10.0,
        error=AssertionError("expected failure"),
    )

    await reporter.on_collection_complete([item])
    await reporter.on_test_complete(execution)

    merit_run = MeritRun()
    merit_run.result.executions = [execution]
    await reporter.on_run_complete(merit_run)

    text = output.getvalue()
    assert "FAILURES" in text
    assert "expected failure" in text


@pytest.mark.asyncio
async def test_verbose_live_renders_sub_executions(monkeypatch):
    monkeypatch.setattr("merit.reports.console.Live", FakeLive)
    FakeLive.instances.clear()

    output = io.StringIO()
    console = Console(file=output, force_terminal=True, color_system=None, width=120)
    reporter = ConsoleReporter(console=console, verbosity=1)

    parent = make_item("test_matrix", "tests/test_matrix.py")
    case_one = make_item("test_matrix", "tests/test_matrix.py", id_suffix="case=1")
    case_two = make_item("test_matrix", "tests/test_matrix.py", id_suffix="case=2")

    sub_executions = [
        make_execution(case_one, TestStatus.PASSED, 8.0),
        make_execution(case_two, TestStatus.FAILED, 12.0, error=AssertionError("bad case")),
    ]
    execution = make_execution(
        parent,
        TestStatus.FAILED,
        20.0,
        sub_executions=sub_executions,
    )

    await reporter.on_collection_complete([parent])
    await reporter.on_test_start(parent)
    await reporter.on_test_complete(execution)

    text = render_to_text(FakeLive.instances[-1].renderables[-1])
    assert "case=1" in text
    assert "case=2" in text
    assert "FAILED" in text
    assert "↳" not in text
    assert "2/2 passed" not in text


@pytest.mark.asyncio
async def test_verbose_live_streams_subtests_before_parent_completion(monkeypatch):
    monkeypatch.setattr("merit.reports.console.Live", FakeLive)
    FakeLive.instances.clear()

    output = io.StringIO()
    console = Console(file=output, force_terminal=True, color_system=None, width=120)
    reporter = ConsoleReporter(console=console, verbosity=1)

    parent = make_item("test_matrix", "tests/test_matrix.py")
    case_one = make_item("test_matrix", "tests/test_matrix.py", id_suffix="case=1")
    sub_execution = make_execution(case_one, TestStatus.PASSED, 8.0)

    await reporter.on_collection_complete([parent])
    await reporter.on_test_start(parent)
    await reporter.on_subtest_complete(parent, sub_execution)

    text = render_to_text(FakeLive.instances[-1].renderables[-1])
    assert "test_matrix::test_matrix" in text
    assert "running" in text
    assert "case=1" in text
    assert "↳" not in text


@pytest.mark.asyncio
async def test_verbose_non_terminal_subexecutions_have_no_arrow():
    output = io.StringIO()
    console = Console(file=output, force_terminal=False, color_system=None, width=120)
    reporter = ConsoleReporter(console=console, verbosity=1)

    parent = make_item("test_matrix", "tests/test_matrix.py")
    case_one = make_item("test_matrix", "tests/test_matrix.py", id_suffix="case=1")
    case_two = make_item("test_matrix", "tests/test_matrix.py", id_suffix="case=2")
    execution = make_execution(
        parent,
        TestStatus.FAILED,
        20.0,
        sub_executions=[
            make_execution(case_one, TestStatus.PASSED, 8.0),
            make_execution(case_two, TestStatus.FAILED, 12.0, error=AssertionError("bad case")),
        ],
    )

    await reporter.on_collection_complete([parent])
    await reporter.on_test_complete(execution)
    text = output.getvalue()
    assert "↳" not in text
    assert "2/2 passed" not in text
