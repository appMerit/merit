"""Test factory for creating executable tests."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from merit.testing.execution.result_builder import ResultBuilder
from merit.testing.execution.tracer import TestTracer
from merit.testing.models import (
    MeritTestDefinition,
    ParametrizeModifier,
    RepeatModifier,
)


if TYPE_CHECKING:
    from merit.testing.execution.protocol import MeritTest


@dataclass
class DefaultTestFactory:
    """Creates test instances with shared collaborators."""

    tracer: TestTracer
    result_builder: ResultBuilder

    def build(
        self,
        definition: MeritTestDefinition,
        params: dict[str, Any] | None = None,
    ) -> MeritTest:
        """Build appropriate executable test from definition."""
        # Import here to avoid circular imports at runtime
        from merit.testing.execution import parametrized, repeated, single  # noqa: PLC0415

        params = params or {}

        if not definition.modifiers:
            return single.SingleMeritTest(
                definition=definition,
                params=params,
                tracer=self.tracer,
                result_builder=self.result_builder,
            )

        mod = definition.modifiers[0]
        if isinstance(mod, RepeatModifier):
            return repeated.RepeatedMeritTest(
                definition=definition,
                params=params,
                count=mod.count,
                min_passes=mod.min_passes,
                factory=self,
            )
        if isinstance(mod, ParametrizeModifier):
            return parametrized.ParametrizedMeritTest(
                definition=definition,
                params=params,
                parameter_sets=mod.parameter_sets,
                factory=self,
            )

        return self.build(
            replace(definition, modifiers=definition.modifiers[1:]),
            params,
        )
