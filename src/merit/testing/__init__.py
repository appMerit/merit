"""Testing framework for AI agents."""

from merit.resources import ResourceResolver, Scope, resource
from merit.testing.decorators import (
    iter_case_groups,
    iter_cases,
    parametrize,
    repeat,
    run_inline,
    tag,
)
from merit.testing.discovery import collect
from merit.testing.environment import capture_environment
from merit.testing.execution import (
    DefaultTestFactory,
    MeritTest,
    ParametrizedMeritTest,
    RepeatedMeritTest,
    ResultBuilder,
    SingleMeritTest,
    TestFactory,
    TestTracer,
)
from merit.testing.models import (
    Case,
    CaseGroup,
    CaseGroupIterateModifier,
    MeritRun,
    MeritTestDefinition,
    CaseIterateModifier,
    Modifier,
    ParameterSet,
    ParametrizeModifier,
    RepeatModifier,
    RunEnvironment,
    RunResult,
    TestExecution,
    TestResult,
    TestStatus,
)
from merit.testing.outcomes import FailTest, SkipTest, XFailTest, fail, skip, xfail
from merit.testing.runner import Runner


# Backwards compatibility alias
TestItem = MeritTestDefinition

__all__ = [
    "Case",
    "CaseGroup",
    "CaseGroupIterateModifier",
    "CaseIterateModifier",
    "DefaultTestFactory",
    "FailTest",
    "MeritRun",
    "MeritTest",
    "MeritTestDefinition",
    "Modifier",
    "ParameterSet",
    "ParametrizeModifier",
    "ParametrizedMeritTest",
    "RepeatModifier",
    "RepeatedMeritTest",
    "ResourceResolver",
    "ResultBuilder",
    "RunEnvironment",
    "RunResult",
    "Runner",
    "Scope",
    "SingleMeritTest",
    "SkipTest",
    "TestExecution",
    "TestFactory",
    "TestItem",  # alias
    "TestResult",
    "TestStatus",
    "TestTracer",
    "XFailTest",
    "capture_environment",
    "collect",
    "fail",
    "iter_cases",
    "iter_case_groups",
    "parametrize",
    "repeat",
    "resource",
    "run_inline",
    "skip",
    "tag",
    "xfail",
]
