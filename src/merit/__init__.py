"""Merit - Testing framework for AI agents."""

from .metrics import AverageScore, Metric, PassRate
from .testing import Case, iter_cases, parametrize, resource, tag
from .testing.sut import sut
from .tracing import init_tracing, trace_step
from .version import __version__
from .checkers import checker


__all__ = [
    # Checkers
    "checker",
    # Core testing
    "Case",
    "iter_cases",
    "parametrize",
    "tag",
    "resource",
    "sut",
    # Assertions
    "Assertion",
    "AssertionFailedError",
    "AssertionResult",
    "Contains",
    "ExactMatch",
    "StartsWith",
    # Metrics
    "Metric",
    "PassRate",
    "AverageScore",
    # Tracing
    "init_tracing",
    "trace_step",
]
