"""Tests for data models."""

import pytest
from merit_analyzer.models.test_result import TestResult, TestResultBatch
from merit_analyzer.models.pattern import Pattern
from merit_analyzer.models.recommendation import Recommendation, PriorityLevel, RecommendationType
from merit_analyzer.models.report import AnalysisReport, ReportSummary, PatternSummary


class TestTestResult:
    """Test TestResult model."""
    
    def test_test_result_creation(self):
        """Test creating a TestResult."""
        test = TestResult(
            test_id="test_001",
            input="test input",
            actual_output="test output",
            status="failed"
        )
        
        assert test.test_id == "test_001"
        assert test.input == "test input"
        assert test.actual_output == "test output"
        assert test.status == "failed"
        assert test.tags == []
    
    def test_test_result_with_optional_fields(self):
        """Test TestResult with optional fields."""
        test = TestResult(
            test_id="test_002",
            test_name="test name",
            input="test input",
            expected_output="expected output",
            actual_output="actual output",
            status="passed",
            failure_reason="test reason",
            category="test_category",
            tags=["tag1", "tag2"],
            execution_time_ms=1000,
            timestamp="2024-01-01T00:00:00Z"
        )
        
        assert test.test_name == "test name"
        assert test.expected_output == "expected output"
        assert test.failure_reason == "test reason"
        assert test.category == "test_category"
        assert test.tags == ["tag1", "tag2"]
        assert test.execution_time_ms == 1000
        assert test.timestamp == "2024-01-01T00:00:00Z"


class TestTestResultBatch:
    """Test TestResultBatch model."""
    
    def test_batch_creation(self):
        """Test creating a TestResultBatch."""
        tests = [
            TestResult(test_id="test_001", input="input1", actual_output="output1", status="passed"),
            TestResult(test_id="test_002", input="input2", actual_output="output2", status="failed")
        ]
        
        batch = TestResultBatch(results=tests)
        
        assert len(batch) == 2
        assert batch.get_failed_tests() == [tests[1]]
        assert batch.get_passed_tests() == [tests[0]]
    
    def test_batch_summary(self):
        """Test batch summary statistics."""
        tests = [
            TestResult(test_id="test_001", input="input1", actual_output="output1", status="passed"),
            TestResult(test_id="test_002", input="input2", actual_output="output2", status="failed"),
            TestResult(test_id="test_003", input="input3", actual_output="output3", status="error"),
            TestResult(test_id="test_004", input="input4", actual_output="output4", status="skipped")
        ]
        
        batch = TestResultBatch(results=tests)
        summary = batch.get_summary()
        
        assert summary["total"] == 4
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["error"] == 1
        assert summary["skipped"] == 1


class TestPattern:
    """Test Pattern model."""
    
    def test_pattern_creation(self):
        """Test creating a Pattern."""
        tests = [
            TestResult(test_id="test_001", input="input1", actual_output="output1", status="failed"),
            TestResult(test_id="test_002", input="input2", actual_output="output2", status="failed")
        ]
        
        pattern = Pattern(
            name="test_pattern",
            test_results=tests,
            confidence=0.8,
            keywords=["test", "pattern"]
        )
        
        assert pattern.name == "test_pattern"
        assert pattern.failure_count == 2
        assert pattern.failure_rate == 1.0
        assert pattern.confidence == 0.8
        assert pattern.keywords == ["test", "pattern"]
    
    def test_pattern_properties(self):
        """Test Pattern properties."""
        tests = [
            TestResult(test_id="test_001", input="input1", actual_output="output1", status="failed"),
            TestResult(test_id="test_002", input="input2", actual_output="output2", status="passed")
        ]
        
        pattern = Pattern(
            name="mixed_pattern",
            test_results=tests
        )
        
        assert pattern.failure_count == 2
        assert pattern.failure_rate == 0.5  # 1 failed out of 2


class TestRecommendation:
    """Test Recommendation model."""
    
    def test_recommendation_creation(self):
        """Test creating a Recommendation."""
        rec = Recommendation(
            priority=PriorityLevel.HIGH,
            type=RecommendationType.CODE,
            title="Fix validation",
            description="Add input validation",
            location="src/validator.py:45",
            implementation="Add if statement",
            expected_impact="Fixes 5 tests",
            effort_estimate="30 minutes"
        )
        
        assert rec.priority == PriorityLevel.HIGH
        assert rec.type == RecommendationType.CODE
        assert rec.title == "Fix validation"
        assert rec.get_priority_score() == 3  # High priority = 3
    
    def test_recommendation_markdown(self):
        """Test Recommendation to_markdown method."""
        rec = Recommendation(
            priority=PriorityLevel.HIGH,
            type=RecommendationType.CODE,
            title="Fix validation",
            description="Add input validation",
            location="src/validator.py:45",
            implementation="Add if statement",
            expected_impact="Fixes 5 tests",
            effort_estimate="30 minutes",
            rationale="This will prevent validation errors"
        )
        
        md = rec.to_markdown()
        assert "## Fix validation" in md
        assert "**Priority:** High" in md
        assert "**Type:** Code" in md
        assert "**Location:** `src/validator.py:45`" in md


class TestReportSummary:
    """Test ReportSummary model."""
    
    def test_report_summary_creation(self):
        """Test creating a ReportSummary."""
        summary = ReportSummary(
            total_tests=100,
            passed=80,
            failed=20,
            patterns_found=3,
            analysis_timestamp="2024-01-01T00:00:00Z"
        )
        
        assert summary.total_tests == 100
        assert summary.passed == 80
        assert summary.failed == 20
        assert summary.pass_rate == 0.8
        assert summary.failure_rate == 0.2
        assert summary.patterns_found == 3
    
    def test_report_summary_rates(self):
        """Test ReportSummary rate calculations."""
        summary = ReportSummary(
            total_tests=0,
            passed=0,
            failed=0,
            patterns_found=0,
            analysis_timestamp="2024-01-01T00:00:00Z"
        )
        
        assert summary.pass_rate == 0.0
        assert summary.failure_rate == 0.0
        assert summary.error_rate == 0.0


class TestAnalysisReport:
    """Test AnalysisReport model."""
    
    def test_analysis_report_creation(self):
        """Test creating an AnalysisReport."""
        summary = ReportSummary(
            total_tests=10,
            passed=8,
            failed=2,
            patterns_found=1,
            analysis_timestamp="2024-01-01T00:00:00Z"
        )
        
        report = AnalysisReport(
            summary=summary,
            patterns={},
            action_plan=["Fix issue 1", "Fix issue 2"],
            architecture={}
        )
        
        assert report.summary.total_tests == 10
        assert len(report.action_plan) == 2
        assert report.total_recommendations == 0
        assert report.high_priority_count == 0
    
    def test_analysis_report_properties(self):
        """Test AnalysisReport properties."""
        summary = ReportSummary(
            total_tests=10,
            passed=8,
            failed=2,
            patterns_found=1,
            analysis_timestamp="2024-01-01T00:00:00Z"
        )
        
        recommendations = [
            Recommendation(
                priority=PriorityLevel.HIGH,
                type=RecommendationType.CODE,
                title="Fix 1",
                description="Description 1",
                location="file1.py",
                implementation="Implementation 1",
                expected_impact="Impact 1",
                effort_estimate="1 hour"
            ),
            Recommendation(
                priority=PriorityLevel.MEDIUM,
                type=RecommendationType.PROMPT,
                title="Fix 2",
                description="Description 2",
                location="file2.py",
                implementation="Implementation 2",
                expected_impact="Impact 2",
                effort_estimate="30 minutes"
            )
        ]
        
        report = AnalysisReport(
            summary=summary,
            patterns={},
            action_plan=[],
            architecture={},
            recommendations=recommendations
        )
        
        assert report.total_recommendations == 2
        assert report.high_priority_count == 1
        
        by_priority = report.get_recommendations_by_priority()
        assert len(by_priority["high"]) == 1
        assert len(by_priority["medium"]) == 1
        assert len(by_priority["low"]) == 0
        
        by_type = report.get_recommendations_by_type()
        assert len(by_type["code"]) == 1
        assert len(by_type["prompt"]) == 1
