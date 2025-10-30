"""Pattern detection data models."""

from pydantic import BaseModel, Field  # type: ignore
from typing import List, Dict, Any, Optional
from .test_result import TestResult


class Pattern(BaseModel):
    """A detected pattern of test failures."""

    name: str = Field(..., description="Pattern identifier")
    description: Optional[str] = Field(None, description="Human-readable description")
    test_results: List[TestResult] = Field(..., description="Tests that match this pattern")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Pattern confidence score")
    keywords: List[str] = Field(default_factory=list, description="Key terms in this pattern")
    root_cause: Optional[str] = Field(None, description="Identified root cause")
    affected_components: List[str] = Field(
        default_factory=list, description="Code components affected by this pattern"
    )

    @property
    def failure_count(self) -> int:
        """Number of failures in this pattern."""
        return len(self.test_results)

    @property
    def failure_rate(self) -> float:
        """Failure rate for this pattern."""
        if not self.test_results:
            return 0.0
        return sum(1 for t in self.test_results if t.status == "failed") / len(self.test_results)

    def get_example_tests(self, count: int = 3) -> List[TestResult]:
        """Get example tests from this pattern."""
        return self.test_results[:count]

    def add_test_result(self, test_result: TestResult) -> None:
        """Add a test result to this pattern."""
        self.test_results.append(test_result)

    def remove_test_result(self, test_id: str) -> bool:
        """Remove a test result by ID."""
        for i, test in enumerate(self.test_results):
            if test.test_id == test_id:
                del self.test_results[i]
                return True
        return False

    def merge_with(self, other: "Pattern") -> "Pattern":
        """Merge this pattern with another pattern."""
        merged = Pattern(
            name=f"{self.name}_merged_{other.name}",
            description=f"Merged pattern: {self.description} + {other.description}",
            test_results=self.test_results + other.test_results,
            confidence=min(self.confidence, other.confidence),
            keywords=list(set(self.keywords + other.keywords)),
            root_cause=self.root_cause or other.root_cause,
            affected_components=list(set(self.affected_components + other.affected_components)),
        )
        return merged
