"""Assertions for string values."""

from merit.assertions._base import AssertionInference, AssertionResult


class PythonString(AssertionInference):
    """Assertions for string values.

    Provides string comparison operations with optional case-insensitive
    matching against a reference value.

    Parameters
    ----------
    reference_value : str
        The string used for comparisons.
    ignore_case : bool, optional
        If True, comparisons are case-insensitive by default. Default is False.

    Examples
    --------
    >>> assertion = PythonString("Hello")
    >>> assertion.equals("Hello")  # passes
    >>> assertion.contains("Hello World")  # passes
    >>> PythonString("hello", ignore_case=True).equals("HELLO")  # passes
    """

    def __init__(self, reference_value: str, ignore_case: bool = False):
        """Initialize the string assertion.

        Parameters
        ----------
        reference_value : str
            The string used for comparisons.
        ignore_case : bool, optional
            If True, comparisons are case-insensitive by default.
            Default is False.
        """
        super().__init__(reference_value)
        self.ignore_case = ignore_case

    def __call__(self, actual_value: str) -> AssertionResult:
        """Evaluate the assertion using equality check.

        Parameters
        ----------
        actual_value : str
            The string to compare against the reference.

        Returns
        -------
        AssertionResult
            Result of the equality evaluation.

        Raises
        ------
        AssertionFailedError
            If the strings are not equal.
        """
        return self.equals(actual_value)

    def equals(self, actual_value: str, ignore_case: bool | None = None) -> AssertionResult:
        """Check string equality with optional case folding.

        Parameters
        ----------
        actual_value : str
            The string to compare against the reference.
        ignore_case : bool or None, optional
            If True, perform case-insensitive comparison. If None, use the
            instance-level ``ignore_case`` setting. Default is None.

        Returns
        -------
        AssertionResult
            Result with ``passed=True`` if strings are equal.

        Raises
        ------
        AssertionFailedError
            If the strings are not equal.
        """
        ref_cmp = self.reference_value
        act_cmp = actual_value
        if ignore_case or (ignore_case is None and self.ignore_case):
            ref_cmp = ref_cmp.lower()
            act_cmp = act_cmp.lower()
        passed = act_cmp == ref_cmp
        message = None if passed else f"Expected {ref_cmp!r}, got {act_cmp!r}"
        return self._build_result(
            actual=actual_value,
            passed=passed,
            score=1.0 if passed else 0.0,
            confidence=1.0,
            message=message,
        )

    def is_substring_of(self, actual_value: str, ignore_case: bool | None = None) -> AssertionResult:
        """Check that reference string is a substring of actual.

        Parameters
        ----------
        actual_value : str
            The substring that should be contained in the reference.
        ignore_case : bool or None, optional
            If True, perform case-insensitive comparison. If None, use the
            instance-level ``ignore_case`` setting. Default is None.

        Returns
        -------
        AssertionResult
            Result with ``passed=True`` if actual is found in reference.

        Raises
        ------
        AssertionFailedError
            If the actual substring is not found in reference.
        """
        ref_cmp = self.reference_value
        act_cmp = actual_value
        if ignore_case or (ignore_case is None and self.ignore_case):
            ref_cmp = ref_cmp.lower()
            act_cmp = act_cmp.lower()
        passed = ref_cmp in act_cmp
        message = None if passed else f"Expected {self.reference_value!r} to be in {actual_value!r}"
        return self._build_result(
            actual=actual_value,
            passed=passed,
            score=1.0 if passed else 0.0,
            confidence=1.0,
            message=message,
        )

    def is_prefix_of(self, actual_value: str, ignore_case: bool | None = None) -> AssertionResult:
        """Check that reference string is a prefix of actual.

        Parameters
        ----------
        actual_value : str
            The string that the reference should be a prefix of.
        ignore_case : bool or None, optional
            If True, perform case-insensitive comparison. If None, use the
            instance-level ``ignore_case`` setting. Default is None.

        Returns
        -------
        AssertionResult
            Result with ``passed=True`` if reference is a prefix of actual.

        Raises
        ------
        AssertionFailedError
            If the reference string does not start with actual.
        """
        ref_cmp = self.reference_value
        act_cmp = actual_value
        if ignore_case or (ignore_case is None and self.ignore_case):
            ref_cmp = ref_cmp.lower()
            act_cmp = act_cmp.lower()
        passed = act_cmp.startswith(ref_cmp)
        message = (
            None if passed else f"Expected {actual_value!r} to start with {self.reference_value!r}"
        )
        return self._build_result(
            actual=actual_value,
            passed=passed,
            score=1.0 if passed else 0.0,
            confidence=1.0,
            message=message,
        )

    def is_suffix_of(self, actual_value: str, ignore_case: bool | None = None) -> AssertionResult:
        """Check that reference string is a suffix of actual.

        Parameters
        ----------
        actual_value : str
            The string that the reference should be a suffix of.
        ignore_case : bool or None, optional
            If True, perform case-insensitive comparison. If None, use the
            instance-level ``ignore_case`` setting. Default is None.

        Returns
        -------
        AssertionResult
            Result with ``passed=True`` if reference is a suffix of actual.

        Raises
        ------
        AssertionFailedError
            If the reference string does not end with actual.
        """
        ref_cmp = self.reference_value
        act_cmp = actual_value
        if ignore_case or (ignore_case is None and self.ignore_case):
            ref_cmp = ref_cmp.lower()
            act_cmp = act_cmp.lower()
        passed = act_cmp.endswith(ref_cmp)
        message = (
            None if passed else f"Expected {actual_value!r} to end with {self.reference_value!r}"
        )
        return self._build_result(
            actual=actual_value,
            passed=passed,
            score=1.0 if passed else 0.0,
            confidence=1.0,
            message=message,
        )

