"""Test invocation protocols and implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from merit.testing.models import MeritTestDefinition


class TestInvoker(Protocol):
    """Protocol for invoking test functions."""

    async def invoke(self, definition: MeritTestDefinition, kwargs: dict[str, Any]) -> None:
        """Invoke the test function with the given arguments."""
        ...


@dataclass
class DefaultTestInvoker:
    """Default test invoker that handles sync and async functions."""

    async def invoke(self, definition: MeritTestDefinition, kwargs: dict[str, Any]) -> None:
        """Invoke the test function with the given arguments."""
        fn = definition.fn
        if definition.is_async:
            await fn(**kwargs)
        else:
            fn(**kwargs)
