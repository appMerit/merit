"""Parametrized test execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from typing import Any
from uuid import uuid4

from merit.context import get_runner
from merit.resources import ResourceResolver
from merit.testing.execution.interfaces import MeritTest, TestFactory
from merit.testing.models import (
    MeritTestDefinition,
    ParameterSet,
    ParametrizeModifier,
    TestExecution,
    TestResult,
    TestStatus,
)


@dataclass
class ParametrizedMeritTest(MeritTest):
    """Executes test for each parameter set, aggregates results."""

    definition: MeritTestDefinition
    params: dict[str, Any]
    parameter_sets: tuple[ParameterSet, ...]
    factory: TestFactory

    def __post_init__(self) -> None:
        """Validate that the first modifier is ParametrizeModifier."""
        if not self.definition.modifiers or not isinstance(
            self.definition.modifiers[0], ParametrizeModifier
        ):
            raise ValueError("ParametrizedMeritTest requires ParametrizeModifier as first modifier")

    async def execute(self, resolver: ResourceResolver) -> TestExecution:
        """Execute test for each parameter set and aggregate results."""

        async def run_child(index: int, parameter_set: ParameterSet) -> tuple[int, TestExecution]:
            child_def = replace(
                self.definition,
                modifiers=self.definition.modifiers[1:],
                id_suffix=parameter_set.id_suffix,
            )
            child_params = {**self.params, **parameter_set.values}
            child = self.factory.build(child_def, child_params)
            execution = await child.execute(resolver)
            return index, execution

        tasks: list[asyncio.Task[tuple[int, TestExecution]]] = []
        for index, ps in enumerate(self.parameter_sets):
            tasks.append(asyncio.create_task(run_child(index, ps)))

        sub_executions: list[TestExecution | None] = [None] * len(self.parameter_sets)
        runner = get_runner()
        for completed_task in asyncio.as_completed(tasks):
            index, sub_execution = await completed_task
            sub_executions[index] = sub_execution
            if runner:
                await runner.notify_subtest_complete(self.definition, sub_execution)

        ordered_sub_executions = [
            execution for execution in sub_executions if execution is not None
        ]

        has_failure = any(e.result.status.is_failure for e in ordered_sub_executions)
        status = TestStatus.FAILED if has_failure else TestStatus.PASSED
        duration = sum(e.result.duration_ms for e in ordered_sub_executions)

        return TestExecution(
            definition=self.definition,
            result=TestResult(status=status, duration_ms=duration),
            execution_id=uuid4(),
            sub_executions=ordered_sub_executions,
        )
