"""Tests for run_inline decorator and threaded sync execution."""

import asyncio
import threading
from pathlib import Path

from merit.testing import Runner, run_inline
from merit.testing.models import RepeatModifier, TestItem


def test_run_inline_decorator_sets_attribute():
    @run_inline
    def sample():
        pass

    assert getattr(sample, "__merit_run_inline__", False) is True


def test_undecorated_function_has_no_attribute():
    def sample():
        pass

    assert getattr(sample, "__merit_run_inline__", False) is False


def test_sync_test_runs_in_worker_thread(null_reporter):
    runner = Runner(reporters=[null_reporter])
    observed_thread = None

    def merit_check_thread():
        nonlocal observed_thread
        observed_thread = threading.current_thread()

    item = TestItem(
        name="merit_check_thread",
        fn=merit_check_thread,
        module_path=Path("sample.py"),
        is_async=False,
        params=[],
    )

    asyncio.run(runner.run(items=[item]))

    assert observed_thread is not None
    assert observed_thread is not threading.main_thread()


def test_run_inline_test_runs_on_main_thread(null_reporter):
    runner = Runner(reporters=[null_reporter])
    observed_thread = None

    @run_inline
    def merit_inline():
        nonlocal observed_thread
        observed_thread = threading.current_thread()

    item = TestItem(
        name="merit_inline",
        fn=merit_inline,
        module_path=Path("sample.py"),
        is_async=False,
        params=[],
        run_inline=True,
    )

    asyncio.run(runner.run(items=[item]))

    assert observed_thread is not None
    assert observed_thread is threading.main_thread()


def test_async_test_unaffected(null_reporter):
    runner = Runner(reporters=[null_reporter])
    observed_thread = None

    async def merit_async():
        nonlocal observed_thread
        observed_thread = threading.current_thread()

    item = TestItem(
        name="merit_async",
        fn=merit_async,
        module_path=Path("sample.py"),
        is_async=True,
        params=[],
    )

    asyncio.run(runner.run(items=[item]))

    assert observed_thread is not None
    assert observed_thread is threading.main_thread()


def test_sync_exception_propagates(null_reporter):
    runner = Runner(reporters=[null_reporter])

    def merit_raise():
        raise ValueError("sync boom")

    item = TestItem(
        name="merit_raise",
        fn=merit_raise,
        module_path=Path("sample.py"),
        is_async=False,
        params=[],
    )

    run_result = asyncio.run(runner.run(items=[item]))

    assert run_result.result.failed == 0
    assert run_result.result.errors == 1
    execution = run_result.result.executions[0]
    assert isinstance(execution.result.error, ValueError)
    assert "sync boom" in str(execution.result.error)


def test_run_inline_propagates_through_repeat(null_reporter):
    runner = Runner(reporters=[null_reporter])
    threads: list[threading.Thread] = []

    @run_inline
    def merit_inline_repeat():
        threads.append(threading.current_thread())

    item = TestItem(
        name="merit_inline_repeat",
        fn=merit_inline_repeat,
        module_path=Path("sample.py"),
        is_async=False,
        params=[],
        run_inline=True,
        modifiers=[RepeatModifier(count=3, min_passes=3)],
    )

    asyncio.run(runner.run(items=[item]))

    assert len(threads) == 3
    assert all(t is threading.main_thread() for t in threads)


def test_sync_repeat_uses_threads_by_default(null_reporter):
    runner = Runner(reporters=[null_reporter])
    threads: list[threading.Thread] = []

    def merit_threaded_repeat():
        threads.append(threading.current_thread())

    item = TestItem(
        name="merit_threaded_repeat",
        fn=merit_threaded_repeat,
        module_path=Path("sample.py"),
        is_async=False,
        params=[],
        modifiers=[RepeatModifier(count=3, min_passes=3)],
    )

    asyncio.run(runner.run(items=[item]))

    assert len(threads) == 3
    assert all(t is not threading.main_thread() for t in threads)
