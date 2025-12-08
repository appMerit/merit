"""LLM-backed behavior detection assertion interface."""

from merit.assertions._base import AssertionInference, AssertionResult


class Behavior(AssertionInference):
    """Check for described behavior in the actual text.

    Parameters
    ----------
    reference_value : str
        Text describing the expected behavior.
    """

    def __init__(self, reference_value: str):
        """Initialize the behavior assertion.

        Parameters
        ----------
        reference_value : str
            Text describing the expected behavior.
        """
        super().__init__(reference_value)

    def __call__(self, actual_value: str) -> AssertionResult:
        """Evaluate the assertion by checking if the behavior appears.

        Parameters
        ----------
        actual_value : str
            The text to evaluate for the described behavior.

        Returns
        -------
        AssertionResult
            Result of the behavior detection evaluation.

        Raises
        ------
        AssertionFailedError
            If the behavior does not appear.
        """
        return self.appears_in(actual_value)

    def absent_in(self, actual_value: str) -> AssertionResult:
        """Assert the described behavior is absent from the text.

        Parameters
        ----------
        actual_value : str
            The text to check for absence of the behavior.

        Returns
        -------
        AssertionResult
            Result with ``passed=True`` when the behavior is absent.

        Raises
        ------
        AssertionFailedError
            If the behavior is detected in the text.
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

    def appears_in(self, actual_value: str) -> AssertionResult:
        """Assert the described behavior appears in the text.

        Parameters
        ----------
        actual_value : str
            The text to evaluate for the described behavior.

        Returns
        -------
        AssertionResult
            Result with ``passed=True`` when the behavior appears.

        Raises
        ------
        AssertionFailedError
            If the behavior is not detected in the text.
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
