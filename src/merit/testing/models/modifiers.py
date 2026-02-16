"""Test modifiers - pure data classes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from merit.testing.models.case import Case


@dataclass(frozen=True)
class ParameterSet:
    """Concrete parameter combination for an individual test run."""

    values: dict[str, Any]
    id_suffix: str


@dataclass(frozen=True)
class RepeatModifier:
    """Repeat the inner execution N times."""

    count: int
    min_passes: int


@dataclass(frozen=True)
class ParametrizeModifier:
    """Run the inner execution for each parameter set."""

    parameter_sets: tuple[ParameterSet, ...]


@dataclass(frozen=True)
class CaseIterateModifier:
    """Run the inner execution for each case."""

    cases: tuple[Case[Any], ...]


Modifier = RepeatModifier | ParametrizeModifier | CaseIterateModifier
