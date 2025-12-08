"""Base assertion classes and result types."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel


class AssertionMetadata(BaseModel):
    """Metadata for an assertion.

    Attributes
    ----------
    name : str
        Human-readable assertion identifier.
    uuid : UUID
        Unique identifier for this evaluation instance.
    timestamp : datetime
        UTC timestamp when the assertion was evaluated.
    reference : Any
        Reference value the assertion compares against.
    actual : Any
        Actual value produced by the system under test.
    """
    name: str
    uuid: UUID
    timestamp: datetime
    reference: Any
    actual: Any


class AssertionResult(BaseModel):
    """Result of evaluating an assertion on a test case.

    Attributes:
    ----------
    metadata : AssertionMetadata
        Contextual details about the evaluated assertion.
    assertion_name : str
        Name of the assertion that was evaluated
    passed : bool
        Whether the assertion passed
    score : float | None
        Numerical score (0.0 to 1.0), optional
    confidence : float | None
        Confidence level (0.0 to 1.0), optional
    message : str | None
        Optional message explaining the result
    """

    metadata: AssertionMetadata
    passed: bool
    score: float | None = None
    confidence: float | None = None
    message: str | None = None


class AssertionFailedError(AssertionError):
    """AssertionError with attached AssertionResult."""

    def __init__(self, result: AssertionResult):
        self.assertion_result = result
        message = f"{result.metadata.name} failed"
        if result.message:
            message += f": {result.message}"
        super().__init__(message)


class AssertionInference(ABC):
    """Base class for test assertions.

    Attributes
    ----------
    name : str
        Identifier used in assertion results; defaults to the subclass name.
    reference_value : Any
        Reference value provided during initialization for comparison.

    Notes
    -----
    Subclasses implement ``__call__`` to return an AssertionResult and must
    raise AssertionFailedError when the assertion fails.
    """

    def __init_subclass__(cls, **kwargs):
        """Auto-generate name from class name if not provided."""
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "name"):
            cls.name = cls.__name__

    def __init__(self, reference_value: Any, actual_value_path: str | None = None):
        """Initialize assertion with a reference value.

        Parameters
        ----------
        reference_value : Any
            Reference value used for evaluation.
        actual_value_path : str or None
            Path to the actual value. Used if assertion called from a Case object.
        """
        self.reference_value = reference_value
        self.actual_value_path = actual_value_path

    def _build_result(
        self,
        *,
        actual: Any,
        passed: bool,
        score: float | None,
        confidence: float | None,
        message: str | None,
    ) -> AssertionResult:
        """Create an assertion result and raise on failure.

        Parameters
        ----------
        actual : Any
            The actual value that was evaluated.
        passed : bool
            Whether the assertion passed.
        score : float or None
            Numerical score for the assertion (0.0 to 1.0).
        confidence : float or None
            Confidence level for the assertion (0.0 to 1.0).
        message : str or None
            Message explaining the result, typically set on failure.

        Returns
        -------
        AssertionResult
            The constructed assertion result.

        Raises
        ------
        AssertionFailedError
            If the assertion fails (``passed=False``).
        """
        metadata = AssertionMetadata(
            name=self.name,
            uuid=uuid4(),
            timestamp=datetime.now(timezone.utc),
            reference=self.reference_value,
            actual=actual,
        )
        result = AssertionResult(
            metadata=metadata,
            passed=passed,
            score=score,
            confidence=confidence,
            message=message,
        )
        if not passed:
            raise AssertionFailedError(result)
        return result

    @abstractmethod
    def __call__(self, actual_value: Any) -> AssertionResult:
        """Evaluate the assertion and raise on failure.

        Parameters
        ----------
        actual_value : Any
            The actual output from the system under test.

        Returns:
        -------
        AssertionResult
            Result of the assertion evaluation.

        Raises
        ------
        AssertionFailedError
            If the assertion fails (passed=False).
        """
