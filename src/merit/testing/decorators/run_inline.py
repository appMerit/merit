"""Run-inline decorator for merit tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def run_inline(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Mark a sync test to run inline on the event loop instead of in a thread.

    By default, sync merit tests are offloaded to a thread via ``asyncio.to_thread``
    so the event loop stays responsive (e.g. for live console updates).  Apply this
    decorator when a test must execute on the main thread.

    Example::

        @merit.run_inline
        def merit_thread_sensitive(): ...
    """
    fn.__merit_run_inline__ = True
    return fn


__all__ = ["run_inline"]
