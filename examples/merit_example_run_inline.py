"""Example demonstrating sync test threading and @merit.run_inline.

By default, sync merit tests run in a worker thread so the event loop
stays responsive (e.g. for live console updates).  Use @merit.run_inline
when a test must execute on the main thread.

    merit test examples/merit_example_run_inline.py -v
"""

import threading
import time

import merit


def merit_sync_default():
    """This sync test runs in a worker thread (default behavior)."""
    time.sleep(0.2)
    assert threading.current_thread() is not threading.main_thread()


@merit.run_inline
def merit_sync_inline():
    """This sync test runs inline on the event loop thread."""
    assert threading.current_thread() is threading.main_thread()


async def merit_async_unaffected():
    """Async tests are always awaited on the event loop — no change."""
    assert threading.current_thread() is threading.main_thread()


@merit.repeat(3)
def merit_sync_repeated():
    """Repeated sync tests also run in worker threads by default."""
    time.sleep(0.1)
    assert threading.current_thread() is not threading.main_thread()


@merit.run_inline
@merit.repeat(3)
def merit_inline_repeated():
    """Repeated sync tests with @run_inline stay on the main thread."""
    time.sleep(0.1)
    assert threading.current_thread() is threading.main_thread()
