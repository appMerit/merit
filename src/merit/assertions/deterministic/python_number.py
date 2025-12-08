"""Assertions for numeric values."""

from merit.assertions._base import AssertionInference, AssertionResult


class PythonNumber(AssertionInference):
    """Assertions for numeric values.

    Provides comparison operations for integers and floats against a
    reference value.

    Parameters
    ----------
    reference_value : int | float
        The numeric value used for comparisons.

    Examples
    --------
    >>> assertion = PythonNumber(10)
    >>> assertion.equals(10)  # passes
    >>> assertion.gt(5)       # passes (10 > 5)
    """

    def __init__(self, reference_value: int | float):
        """Initialize the numeric assertion.

        Parameters
        ----------
        reference_value : int | float
            The numeric value used for comparisons.
        """
        super().__init__(reference_value)

    def __call__(self, actual_value: int | float) -> AssertionResult:
        """Evaluate the assertion using equality check.

        Parameters
        ----------
        actual_value : int | float
            The numeric value to compare against the reference.

        Returns
        -------
        AssertionResult
            Result of the equality evaluation.

        Raises
        ------
        AssertionFailedError
            If the values are not equal.
        """
        return self.equals(actual_value)

    def equals(self, actual_value: int | float) -> AssertionResult:
        """Check numeric equality.

        Parameters
        ----------
        actual_value : int | float
            The numeric value to compare against the reference.

        Returns
        -------
        AssertionResult
            Result with ``passed=True`` if values are equal.

        Raises
        ------
        AssertionFailedError
            If the values are not equal.
        """
        passed = actual_value == self.reference_value
        message = None if passed else f"Expected {self.reference_value!r}, got {actual_value!r}"
        return self._build_result(
            actual=actual_value,
            passed=passed,
            score=1.0 if passed else 0.0,
            confidence=1.0,
            message=message,
        )

    def gt(self, actual_value: int | float) -> AssertionResult:
        """Check that reference value is greater than actual value.

        Parameters
        ----------
        actual_value : int | float
            The numeric value to compare.

        Returns
        -------
        AssertionResult
            Result with ``passed=True`` if ``actual_value < reference_value``.

        Raises
        ------
        AssertionFailedError
            If ``actual_value`` is not greater than ``reference_value``.
        """
        passed = actual_value < self.reference_value
        message = None if passed else f"Expected {actual_value!r} < {self.reference_value!r}"
        return self._build_result(
            actual=actual_value,
            passed=passed,
            score=1.0 if passed else 0.0,
            confidence=1.0,
            message=message,
        )

    def ge(self, actual_value: int | float) -> AssertionResult:
        """Check that reference value is greater than or equal to actual.

        Parameters
        ----------
        actual_value : int | float
            The numeric value to compare.

        Returns
        -------
        AssertionResult
            Result with ``passed=True`` if ``reference_value >= actual_value``.

        Raises
        ------
        AssertionFailedError
            If ``actual_value`` is less than ``reference_value``.
        """
        passed = self.reference_value >= actual_value
        message = None if passed else f"Expected {self.reference_value!r} >= {actual_value!r}"
        return self._build_result(
            actual=actual_value,
            passed=passed,
            score=1.0 if passed else 0.0,
            confidence=1.0,
            message=message,
        )

    def lt(self, actual_value: int | float) -> AssertionResult:
        """Check that reference value is less than actual.

        Parameters
        ----------
        actual_value : int | float
            The numeric value to compare.

        Returns
        -------
        AssertionResult
            Result with ``passed=True`` if ``reference_value < actual_value``.

        Raises
        ------
        AssertionFailedError
            If ``actual_value`` is not less than ``reference_value``.
        """
        passed = self.reference_value < actual_value
        message = None if passed else f"Expected {self.reference_value!r} < {actual_value!r}"
        return self._build_result(
            actual=actual_value,
            passed=passed,
            score=1.0 if passed else 0.0,
            confidence=1.0,
            message=message,
        )

    def le(self, actual_value: int | float) -> AssertionResult:
        """Check that reference value is less than or equal to actual.

        Parameters
        ----------
        actual_value : int | float
            The numeric value to compare.

        Returns
        -------
        AssertionResult
            Result with ``passed=True`` if ``reference_value <= actual_value``.

        Raises
        ------
        AssertionFailedError
            If ``actual_value`` is greater than ``reference_value``.
        """
        passed = self.reference_value <= actual_value
        message = None if passed else f"Expected {self.reference_value!r} <= {actual_value!r}"
        return self._build_result(
            actual=actual_value,
            passed=passed,
            score=1.0 if passed else 0.0,
            confidence=1.0,
            message=message,
        )

