"""Testing models - pure data classes."""

from merit.testing.models.definition import MeritTestDefinition
from merit.testing.models.modifiers import (
    CaseGroupIterateModifier,
    CaseIterateModifier,
    Modifier,
    ParameterSet,
    ParametrizeModifier,
    RepeatModifier,
)
from merit.testing.models.result import TestExecution, TestResult, TestStatus
from merit.testing.models.run import MeritRun, RunEnvironment, RunResult
from merit.testing.models.case import Case, CaseGroup


# Backwards compatibility alias
TestItem = MeritTestDefinition

__all__ = [
    "Case",
    "CaseGroup",
    "CaseGroupIterateModifier",
    "MeritRun",
    "MeritTestDefinition",
    "CaseIterateModifier",
    "Modifier",
    "ParameterSet",
    "ParametrizeModifier",
    "RepeatModifier",
    "RunEnvironment",
    "RunResult",
    "TestExecution",
    "TestItem",  # alias
    "TestResult",
    "TestStatus",
]
