"""LLM-backed instruction-following assertion interface."""

from merit.assertions._base import AssertionInference, AssertionResult


class Instruction(AssertionInference):
    """Assert that a specific instruction is followed in the actual text.

    Uses an LLM to evaluate whether the actual text demonstrates adherence
    to the reference instruction.

    Parameters
    ----------
    reference_value : str
        Instruction text expected to be followed.

    Examples
    --------
    >>> assertion = Instruction("Respond in a formal tone.")
    >>> assertion.is_followed_in("Dear Sir, I am writing to...")  # passes
    """

    def __init__(self, reference_value: str):
        """Initialize the instruction assertion.

        Parameters
        ----------
        reference_value : str
            Instruction text expected to be followed.
        """
        super().__init__(reference_value)

    def __call__(self, actual_value: str) -> AssertionResult:
        """Evaluate the assertion by checking if instruction is followed.

        Parameters
        ----------
        actual_value : str
            The text to evaluate for instruction adherence.

        Returns
        -------
        AssertionResult
            Result of the instruction-following evaluation.

        Raises
        ------
        AssertionFailedError
            If the instruction is not followed.
        """
        return self.is_followed_in(actual_value)

    def is_followed_in(self, actual_value: str) -> AssertionResult:
        """Assert that the instruction appears to have been followed.

        Uses LLM evaluation to determine whether the actual text
        demonstrates adherence to the reference instruction.

        Parameters
        ----------
        actual_value : str
            The text to evaluate for instruction adherence.

        Returns
        -------
        AssertionResult
            Result with ``passed=True`` if the instruction is followed.

        Raises
        ------
        AssertionFailedError
            If the instruction is not followed in the actual text.
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
