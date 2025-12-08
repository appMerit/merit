"""Assertions for list-like values."""

from collections import Counter
from typing import Any

from merit.assertions._base import AssertionInference, AssertionResult


class PythonArray(AssertionInference):
    """Assertions for list-like values.

    Provides equality, containment, and length comparison operations
    for lists against a reference value.

    Parameters
    ----------
    reference_value : list[Any]
        The list used for comparisons.

    Examples
    --------
    >>> assertion = PythonArray([1, 2, 3])
    >>> assertion.equals([1, 2, 3])  # passes
    >>> assertion.contains([1, 2, 3, 4])  # passes (ref is in actual)
    """

    def __init__(self, reference_value: list[Any]):
        """Initialize the list assertion.

        Parameters
        ----------
        reference_value : list[Any]
            The list used for comparisons.
        """
        super().__init__(reference_value)

    def __call__(self, actual_value: list[Any]) -> AssertionResult:
        """Evaluate the assertion using equality check.

        Parameters
        ----------
        actual_value : list[Any]
            The list to compare against the reference.

        Returns
        -------
        AssertionResult
            Result of the equality evaluation.

        Raises
        ------
        AssertionFailedError
            If the lists are not equal.
        """
        return self.equals(actual_value)

    def equals(self, actual_value: list[Any], ignore_order: bool = False) -> AssertionResult:
        """
        Check list equality with optional reordering.

        Parameters
        ----------
        actual_value : list[Any]
            Runtime list to compare against the reference.
        ignore_order : bool or None, optional
            Whether to sort both lists before comparison. If None, use the
            instance-level setting.

        Returns
        -------
        AssertionResult
            Evaluation result for equality.
        """
        ref_cmp = self.reference_value
        act_cmp = actual_value
        if ignore_order:
            ref_cmp = sorted(ref_cmp)
            act_cmp = sorted(act_cmp)
        passed = act_cmp == ref_cmp
        message = None if passed else f"Expected {ref_cmp!r}, got {act_cmp!r}"
        return self._build_result(
            actual=actual_value,
            passed=passed,
            score=1.0 if passed else 0.0,
            confidence=1.0,
            message=message,
        )

    def contains(self, actual_value: list[Any]) -> AssertionResult:
        """
        Check that the actual list is contained within the reference list.

        Parameters
        ----------
        actual_value : list[Any]
            Candidate list expected to be fully contained in the reference list.

        Returns
        -------
        AssertionResult
            Result with ``passed=True`` if all elements of ``actual_value`` are
            present in the reference list with at least the same multiplicity.
        """
        ref_counts = Counter(self.reference_value)
        act_counts = Counter(actual_value)
        passed = all(ref_counts.get(item, 0) >= count for item, count in act_counts.items())
        message = (
            None
            if passed
            else f"Expected {actual_value!r} to be contained within {self.reference_value!r}"
        )
        return self._build_result(
            actual=actual_value,
            passed=passed,
            score=1.0 if passed else 0.0,
            confidence=1.0,
            message=message,
        )

    def is_subset_of(self, actual_value: list[Any]) -> AssertionResult:
        """
        Check that the reference list is a subset of the actual list.

        Parameters
        ----------
        actual_value : list[Any]
            Candidate list that should contain all reference elements.

        Returns
        -------
        AssertionResult
            Evaluation result for subset containment.
        """
        ref_counts = Counter(self.reference_value)
        act_counts = Counter(actual_value)
        passed = all(act_counts.get(item, 0) >= count for item, count in ref_counts.items())
        message = (
            None if passed else f"Expected {self.reference_value!r} to be subset of {actual_value!r}"
        )
        return self._build_result(
            actual=actual_value,
            passed=passed,
            score=1.0 if passed else 0.0,
            confidence=1.0,
            message=message,
        )

    def has_same_length_as(self, actual_value: list[Any]) -> AssertionResult:
        """
        Check whether the list length matches the reference length.

        Parameters
        ----------
        actual_value : list[Any]
            Candidate list whose length is compared.

        Returns
        -------
        AssertionResult
            Evaluation result for length equality.
        """
        passed = len(actual_value) == len(self.reference_value)
        message = None if passed else f"Expected length {len(self.reference_value)}, got {len(actual_value)}"
        return self._build_result(
            actual=actual_value,
            passed=passed,
            score=1.0 if passed else 0.0,
            confidence=1.0,
            message=message,
        )

