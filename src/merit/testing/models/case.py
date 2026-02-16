"""Test case definitions and decorators."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Generic
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import TypeVar


RefsT = TypeVar("RefsT", default=dict[str, Any])


# Data model for case values


class Case(BaseModel, Generic[RefsT]):
    """Container for a single test case inputs and references.

    Attributes:
    ----------
    id : UUID
        Unique identifier for the test case, defaults to a new UUID.
    tags : set[str]
        Set of tags for filtering or categorization of the test case.
    metadata : dict[str, str | int | float | bool | None]
        Arbitrary key-value pairs for additional context or reporting.
    references : RefsT,
        Reference data used for validation or comparison during testing.
    sut_input_values : dict[str, Any]
        Input arguments to be passed to the System Under Test (SUT).
    """

    model_config = ConfigDict(validate_default=True)

    id: UUID = Field(default_factory=uuid4)
    tags: set[str] = Field(default_factory=set)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    references: RefsT = Field(default_factory=dict)  # type: ignore[assignment]
    sut_input_values: dict[str, Any] = Field(default_factory=dict)


class CaseGroup(BaseModel, Generic[RefsT]):
    """Container for a group of test cases."""

    name: str
    cases: list[Case[RefsT]] = Field(default_factory=list)
    min_passes: int = Field(default=1)
