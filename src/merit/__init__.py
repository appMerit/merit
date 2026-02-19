"""Merit - Testing framework for AI agents."""

from .context import metrics
from .metrics_ import Metric, metric
from .predicates import Predicate, PredicateResult, predicate
from .reports import Reporter, reporter
from .testing import (
    Case,
    CaseGroup,
    fail,
    iter_case_groups,
    iter_cases,
    parametrize,
    repeat,
    resource,
    skip,
    tag,
    xfail,
)
from .testing.sut import sut
from .tracing import TraceContext, init_tracing, trace_step


__all__ = [
    # Core testing
    "Case",
    "CaseGroup",
    "iter_case_groups",
    "iter_cases",
    "parametrize",
    "repeat",
    "tag",
    "resource",
    "skip",
    "fail",
    "xfail",
    "sut",
    # Predicates
    "predicate",
    "PredicateResult",
    "Predicate",
    # Metrics
    "Metric",
    "metric",
    "metrics",
    # Reporters
    "Reporter",
    "reporter",
    # Tracing
    "init_tracing",
    "trace_step",
    "TraceContext",
]
