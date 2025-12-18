"""Testing framework for AI agents.

Provides pytest-like test discovery and resource injection.
"""

from .case import Case, CaseDecorator, iter_cases
from .discovery import TestItem, collect
from .parametrize import parametrize
from .resources import ResourceResolver, Scope, resource
from .runner import RunEnvironment, Runner, RunResult, TestResult, TestStatus, run
from .tags import tag


__all__ = [
    "Case",
    "CaseDecorator",
    "ResourceResolver",
    "RunEnvironment",
    "RunResult",
    "Runner",
    "Scope",
    "TestItem",
    "TestResult",
    "TestStatus",
    "collect",
    "iter_cases",
    "parametrize",
    "resource",
    "run",
    "tag",
]
