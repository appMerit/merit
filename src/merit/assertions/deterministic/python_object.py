"""Assertions for dict objects."""

from typing import Any

from merit.assertions._base import AssertionInference, AssertionResult


class PythonObject(AssertionInference):
    """Assertions for dictionary objects.

    Provides equality and key-based comparison operations for dictionaries
    against a reference value.

    Parameters
    ----------
    reference_value : dict[str, Any]
        The dictionary used for comparisons.

    Examples
    --------
    >>> assertion = PythonObject({"name": "Alice", "age": 30})
    >>> assertion.equals({"name": "Alice", "age": 30})  # passes
    >>> assertion.keys_include({"name": "Alice", "age": 30, "city": "NYC"})  # passes
    """

    def __init__(self, reference_value: dict[str, Any]):
        """Initialize the dictionary assertion.

        Parameters
        ----------
        reference_value : dict[str, Any]
            The dictionary used for comparisons.
        """
        super().__init__(reference_value)

    def __call__(self, actual_value: dict[str, Any]) -> AssertionResult:
        """Evaluate the assertion using equality check.

        Parameters
        ----------
        actual_value : dict[str, Any]
            The dictionary to compare against the reference.

        Returns
        -------
        AssertionResult
            Result of the equality evaluation.

        Raises
        ------
        AssertionFailedError
            If the dictionaries are not equal.
        """
        return self.equals(actual_value)

    def equals(self, actual_value: dict[str, Any]) -> AssertionResult:
        """Check shallow dictionary equality.

        Compares all keys and values in both dictionaries. Nested structures
        are compared by reference equality, not deep equality.

        Parameters
        ----------
        actual_value : dict[str, Any]
            The dictionary to compare against the reference.

        Returns
        -------
        AssertionResult
            Result with ``passed=True`` if dictionaries are equal.

        Raises
        ------
        AssertionFailedError
            If the dictionaries are not equal.
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

