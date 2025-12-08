"""Merit - Testing framework for AI agents."""

from .assertions import (
    AssertionFailedError,
    AssertionInference,
    AssertionResult,
    PythonArray,
    PythonNumber,
    PythonObject,
    PythonString,
)
from .metrics import AverageScore, Metric, PassRate
from .testing import Case, Suite, parametrize, resource, tag
from .version import __version__


__all__ = [
    # Core testing
    "Case",
    "Suite",
    "parametrize",
    "tag",
    "resource",
    # Assertions
    "AssertionInference",
    "AssertionFailedError",
    "AssertionResult",
    "PythonString",
    "PythonNumber",
    "PythonArray",
    "PythonObject",
    # Metrics
    "Metric",
    "PassRate",
    "AverageScore",
]
