"""LLM-backed factual assertion interface."""

from merit.assertions._base import AssertionInference, AssertionResult


class Facts(AssertionInference):
    """Assert textual facts via LLM comparison.

    Uses an LLM to evaluate whether the actual text contains, implies,
    or contradicts the reference facts.

    Parameters
    ----------
    reference_value : str
        Reference facts as plain text.

    Examples
    --------
    >>> assertion = Facts("The capital of France is Paris.")
    >>> assertion.explicit_in("Paris is the capital of France.")  # passes
    """

    def __init__(self, reference_value: str):
        """Initialize the facts assertion.

        Parameters
        ----------
        reference_value : str
            Reference facts as plain text.
        """
        super().__init__(reference_value)

    def __call__(self, actual_value: str) -> AssertionResult:
        """Evaluate the assertion using explicit containment check.

        Default behavior allows extra facts in the actual text.

        Parameters
        ----------
        actual_value : str
            The text to evaluate against the reference facts.

        Returns
        -------
        AssertionResult
            Result of the factual evaluation.

        Raises
        ------
        AssertionFailedError
            If the reference facts are not explicitly present.
        """
        return self.explicit_in(actual_value)

    def not_contradicted_by(self, actual_value: str) -> AssertionResult:
        """Assert reference facts are not contradicted by the actual text.

        Checks that the actual text does not contain statements that
        directly contradict the reference facts. The actual text may
        contain additional or unrelated information.

        Parameters
        ----------
        actual_value : str
            The text to check for contradictions.

        Returns
        -------
        AssertionResult
            Result with ``passed=True`` if no contradictions are found.

        Raises
        ------
        AssertionFailedError
            If the actual text contradicts the reference facts.
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

    def explicit_in(self, actual_value: str) -> AssertionResult:
        """Assert reference facts appear explicitly in the actual text.

        Checks that all reference facts are explicitly stated in the actual
        text. Extra facts in the actual text are allowed.

        Parameters
        ----------
        actual_value : str
            The text that should contain the reference facts.

        Returns
        -------
        AssertionResult
            Result with ``passed=True`` if all facts are explicitly present.

        Raises
        ------
        AssertionFailedError
            If any reference fact is not explicitly stated.
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

    def implicit_in(self, actual_value: str) -> AssertionResult:
        """Assert reference facts are present explicitly or implicitly.

        Checks that all reference facts can be inferred from the actual text,
        either through direct statement or logical implication.

        Parameters
        ----------
        actual_value : str
            The text that should contain or imply the reference facts.

        Returns
        -------
        AssertionResult
            Result with ``passed=True`` if all facts are present or implied.

        Raises
        ------
        AssertionFailedError
            If any reference fact cannot be inferred from the actual text.
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

    def exactly_match_facts_in(self, actual_value: str) -> AssertionResult:
        """Assert actual facts are limited strictly to the reference facts,
        and all reference facts are present in the actual text.

        Checks that the actual text contains exactly the reference facts
        and no additional factual information.

        Parameters
        ----------
        actual_value : str
            The text that should contain only the reference facts.

        Returns
        -------
        AssertionResult
            Result with ``passed=True`` if facts match exactly.

        Raises
        ------
        AssertionFailedError
            If the actual text contains extra facts or is missing reference facts.
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
