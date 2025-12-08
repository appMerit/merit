"""LLM-backed style assertion interface."""

from merit.assertions._base import AssertionInference, AssertionResult


class Style(AssertionInference):
    """Assert stylistic similarity between reference and actual text.

    Uses an LLM to evaluate whether the actual text matches the writing
    style demonstrated in the reference text.

    Parameters
    ----------
    reference_value : str
        Text whose style will be used as the reference.

    Examples
    --------
    >>> assertion = Style("Short. Punchy. Direct.")
    >>> assertion.equals("Quick. Sharp. Clear.")  # passes
    """

    def __init__(self, reference_value: str):
        """Initialize the style assertion.

        Parameters
        ----------
        reference_value : str
            Text whose style will be used as the reference.
        """
        super().__init__(reference_value)

    def __call__(self, actual_value: str) -> AssertionResult:
        """Evaluate the assertion using style match check.

        Parameters
        ----------
        actual_value : str
            The text to evaluate for style similarity.

        Returns
        -------
        AssertionResult
            Result of the style evaluation.

        Raises
        ------
        AssertionFailedError
            If the styles do not match.
        """
        return self.equals(actual_value)

    def equals(self, actual_value: str) -> AssertionResult:
        """Assert that actual text matches the reference style.

        Uses LLM evaluation to compare the stylistic characteristics
        of both texts, including tone, sentence structure, vocabulary,
        and rhetorical patterns.

        Parameters
        ----------
        actual_value : str
            The text to evaluate for style similarity.

        Returns
        -------
        AssertionResult
            Result with ``passed=True`` if styles match.

        Raises
        ------
        AssertionFailedError
            If the actual text style does not match the reference.
        """
        passed, confidence, message = mock_llm_request(
            actual_text=actual_value,
            reference_text=self.reference_value,
        )
        return self._build_result(
            actual=actual_value,
            passed=passed,
            score=confidence,
            confidence=confidence,
            message=message,
        )


def mock_llm_request(
    *,
    actual_text: str,
    reference_text: str,
) -> tuple[bool, float | None, str | None]:
    """Placeholder for LLM integration.

    This function should call the configured model with the provided texts and
    return a boolean pass flag, an optional confidence score, and an optional
    message describing any failures.
    """
    raise NotImplementedError("LLM evaluation must be implemented.")
