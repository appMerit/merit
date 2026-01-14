"""Execution protocols."""

from __future__ import annotations

from typing import Any, Protocol

from merit.resources import ResourceResolver
from merit.testing.models import MeritTestDefinition, TestResult


class MeritTest(Protocol):
    """Executable test - single, repeated, or parametrized."""

    async def execute(self, resolver: ResourceResolver) -> TestResult:
        """Execute the test and return result."""
        ...


class TestFactory(Protocol):
    """Creates MeritTest instances from definitions."""

    def build(
        self,
        definition: MeritTestDefinition,
        params: dict[str, Any] | None = None,
    ) -> MeritTest:
        """Build appropriate executable test from definition."""
        ...
