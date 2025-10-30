"""Test result data models."""

from pydantic import BaseModel, Field  # type: ignore
from typing import Optional, Dict, Any, Literal


class TestResult(BaseModel):
    """Schema for a single test result."""

    test_id: str = Field(..., description="Unique identifier for the test")
    test_name: Optional[str] = Field(None, description="Human-readable test name")

    # Test execution details
    input: str = Field(..., description="Input to the AI system")
    expected_output: Optional[str] = Field(None, description="Expected response")
    actual_output: str = Field(..., description="Actual response from system")

    # Status and categorization
    status: Literal["passed", "failed", "error", "skipped"] = Field(
        ..., description="Test result status"
    )
    failure_reason: Optional[str] = Field(None, description="Why the test failed")

    # Additional context
    category: Optional[str] = Field(None, description="Test category (e.g., 'pricing', 'support')")
    tags: Optional[list[str]] = Field(default_factory=list, description="Tags for grouping")

    # Metadata
    execution_time_ms: Optional[int] = Field(None, description="Test execution time")
    timestamp: Optional[str] = Field(None, description="ISO timestamp")
    trace: Optional[Dict[str, Any]] = Field(None, description="Execution trace/logs")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata"
    )

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            # Add any custom encoders here if needed
        }


class TestResultBatch(BaseModel):
    """Collection of test results."""

    results: list[TestResult]
    batch_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    def __len__(self) -> int:
        """Return number of test results."""
        return len(self.results)

    def __iter__(self):
        """Iterate over test results."""
        return iter(self.results)

    def get_failed_tests(self) -> list[TestResult]:
        """Get all failed tests."""
        return [t for t in self.results if t.status == "failed"]

    def get_passed_tests(self) -> list[TestResult]:
        """Get all passed tests."""
        return [t for t in self.results if t.status == "passed"]

    def get_error_tests(self) -> list[TestResult]:
        """Get all error tests."""
        return [t for t in self.results if t.status == "error"]

    def get_skipped_tests(self) -> list[TestResult]:
        """Get all skipped tests."""
        return [t for t in self.results if t.status == "skipped"]

    def get_summary(self) -> Dict[str, int]:
        """Get summary statistics."""
        summary = {"total": len(self.results)}
        for status in ["passed", "failed", "error", "skipped"]:
            summary[status] = sum(1 for t in self.results if t.status == status)
        return summary
