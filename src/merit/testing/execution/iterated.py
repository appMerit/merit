"""Iterated test execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from typing import Any
from uuid import uuid4

from merit.resources import ResourceResolver
from merit.testing.execution.interfaces import MeritTest, TestFactory
from merit.testing.models import (
    Case,
    CaseIterateModifier,
    MeritTestDefinition,
    TestExecution,
    TestResult,
    TestStatus,
)


@dataclass
class CaseIteratedMeritTest(MeritTest):
    """Executes test for each case, aggregates results."""

    definition: MeritTestDefinition
    params: dict[str, Any]
    cases: tuple[Case[Any], ...]
    factory: TestFactory

    def __post_init__(self) -> None:
        """Validate that the first modifier is CaseIterateModifier."""
        if not self.definition.modifiers or not isinstance(
            self.definition.modifiers[0], CaseIterateModifier
        ):
            raise ValueError("CaseIteratedMeritTest requires CaseIterateModifier as first modifier")

    async def execute(self, resolver: ResourceResolver) -> TestExecution:
        """Execute test for each case and aggregate results."""
        tasks: list[asyncio.Task[TestExecution]] = []
        for case in self.cases:
            child_def = replace(
                self.definition,
                modifiers=self.definition.modifiers[1:],
                id_suffix=str(case.id),
            )
            child_params = {**self.params, "case": case}
            child = self.factory.build(child_def, child_params)
            tasks.append(asyncio.create_task(child.execute(resolver)))

        sub_executions = await asyncio.gather(*tasks)

        has_failure = any(e.result.status.is_failure for e in sub_executions)
        status = TestStatus.FAILED if has_failure else TestStatus.PASSED
        duration = sum(e.result.duration_ms for e in sub_executions)

        return TestExecution(
            definition=self.definition,
            result=TestResult(status=status, duration_ms=duration),
            execution_id=uuid4(),
            sub_executions=sub_executions,
        )
