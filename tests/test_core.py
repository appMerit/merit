"""Tests for core components."""

import pytest
from unittest.mock import Mock, patch
from merit_analyzer.core.test_parser import TestParser
from merit_analyzer.core.pattern_detector import PatternDetector
from merit_analyzer.models.test_result import TestResult


class TestTestParser:
    """Test TestParser class."""
    
    def test_parse_from_list(self):
        """Test parsing from list of TestResult objects."""
        parser = TestParser()
        
        tests = [
            TestResult(test_id="test_001", input="input1", actual_output="output1", status="passed"),
            TestResult(test_id="test_002", input="input2", actual_output="output2", status="failed")
        ]
        
        batch = parser.parse(tests)
        
        assert len(batch.results) == 2
        assert batch.results[0].test_id == "test_001"
        assert batch.results[1].test_id == "test_002"
    
    def test_parse_from_dict_list(self):
        """Test parsing from list of dictionaries."""
        parser = TestParser()
        
        test_dicts = [
            {
                "test_id": "test_001",
                "input": "input1",
                "actual_output": "output1",
                "status": "passed"
            },
            {
                "test_id": "test_002",
                "input": "input2",
                "actual_output": "output2",
                "status": "failed"
            }
        ]
        
        batch = parser.parse(test_dicts)
        
        assert len(batch.results) == 2
        assert batch.results[0].test_id == "test_001"
        assert batch.results[1].test_id == "test_002"
    
    def test_validate_test_results(self):
        """Test test result validation."""
        parser = TestParser()
        
        # Valid tests
        valid_tests = [
            TestResult(test_id="test_001", input="input1", actual_output="output1", status="passed"),
            TestResult(test_id="test_002", input="input2", actual_output="output2", status="failed")
        ]
        
        batch = parser.parse(valid_tests)
        issues = parser.validate_test_results(batch)
        
        assert len(issues) == 0
        
        # Invalid tests
        invalid_tests = [
            TestResult(test_id="", input="input1", actual_output="output1", status="passed"),  # Missing test_id
            TestResult(test_id="test_002", input="", actual_output="output2", status="failed"),  # Missing input
            TestResult(test_id="test_003", input="input3", actual_output="", status="failed"),  # Missing actual_output
            TestResult(test_id="test_004", input="input4", actual_output="output4", status="invalid")  # Invalid status
        ]
        
        batch = parser.parse(invalid_tests)
        issues = parser.validate_test_results(batch)
        
        assert len(issues) > 0
        assert any("Missing test_id" in issue for issue in issues)
        assert any("Missing input" in issue for issue in issues)
        assert any("Missing actual_output" in issue for issue in issues)
        assert any("Invalid status" in issue for issue in issues)
    
    def test_get_summary_stats(self):
        """Test summary statistics generation."""
        parser = TestParser()
        
        tests = [
            TestResult(test_id="test_001", input="input1", actual_output="output1", status="passed", execution_time_ms=1000),
            TestResult(test_id="test_002", input="input2", actual_output="output2", status="failed", execution_time_ms=2000),
            TestResult(test_id="test_003", input="input3", actual_output="output3", status="error", execution_time_ms=1500)
        ]
        
        batch = parser.parse(tests)
        summary = parser.get_summary_stats(batch)
        
        assert summary["total"] == 3
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["error"] == 1
        assert summary["pass_rate"] == 1/3
        assert summary["failure_rate"] == 1/3
        assert summary["error_rate"] == 1/3
        assert summary["avg_execution_time_ms"] == 1500


class TestPatternDetector:
    """Test PatternDetector class."""
    
    def test_detect_patterns_empty(self):
        """Test pattern detection with empty input."""
        detector = PatternDetector()
        
        patterns = detector.detect_patterns([])
        
        assert len(patterns) == 0
    
    def test_detect_patterns_single_failure(self):
        """Test pattern detection with single failure."""
        detector = PatternDetector(min_cluster_size=1)
        
        tests = [
            TestResult(test_id="test_001", input="input1", actual_output="output1", status="failed")
        ]
        
        patterns = detector.detect_patterns(tests)
        
        assert len(patterns) == 1
        assert "uncategorized" in patterns
    
    def test_detect_patterns_multiple_failures(self):
        """Test pattern detection with multiple failures."""
        detector = PatternDetector(min_cluster_size=2)
        
        tests = [
            TestResult(test_id="test_001", input="pricing question", actual_output="vague response", status="failed"),
            TestResult(test_id="test_002", input="cost inquiry", actual_output="unclear answer", status="failed"),
            TestResult(test_id="test_003", input="support question", actual_output="helpful response", status="passed")
        ]
        
        patterns = detector.detect_patterns(tests)
        
        # Should group similar failures together
        assert len(patterns) >= 1
        assert any(len(pattern_tests) >= 2 for pattern_tests in patterns.values())
    
    def test_analyze_pattern_similarity(self):
        """Test pattern similarity analysis."""
        detector = PatternDetector()
        
        pattern1 = [
            TestResult(test_id="test_001", input="pricing question", actual_output="vague response", status="failed"),
            TestResult(test_id="test_002", input="cost inquiry", actual_output="unclear answer", status="failed")
        ]
        
        pattern2 = [
            TestResult(test_id="test_003", input="pricing inquiry", actual_output="ambiguous response", status="failed"),
            TestResult(test_id="test_004", input="price question", actual_output="vague answer", status="failed")
        ]
        
        similarity = detector.analyze_pattern_similarity(pattern1, pattern2)
        
        assert 0.0 <= similarity <= 1.0
        # These patterns should be similar since they're all about pricing
        assert similarity > 0.3
    
    def test_get_pattern_insights(self):
        """Test pattern insights generation."""
        detector = PatternDetector()
        
        tests = [
            TestResult(
                test_id="test_001", 
                input="pricing question", 
                actual_output="vague response", 
                status="failed",
                failure_reason="Response too vague",
                category="pricing",
                tags=["pricing", "vague"],
                execution_time_ms=1000
            ),
            TestResult(
                test_id="test_002", 
                input="cost inquiry", 
                actual_output="unclear answer", 
                status="failed",
                failure_reason="Response too vague",
                category="pricing",
                tags=["pricing", "unclear"],
                execution_time_ms=1200
            )
        ]
        
        pattern = Pattern(name="pricing_vague", test_results=tests)
        insights = detector.get_pattern_insights(pattern.name, pattern.test_results)
        
        assert insights["name"] == "pricing_vague"
        assert insights["test_count"] == 2
        assert insights["failure_count"] == 2
        assert insights["failure_rate"] == 1.0
        assert "pricing" in insights["common_failure_reasons"][0]["reason"]
        assert insights["avg_execution_time"] == 1100
        assert "pricing" in insights["categories"][0]["category"]
        assert "pricing" in insights["tags"][0]["tag"]
    
    def test_merge_similar_patterns(self):
        """Test merging similar patterns."""
        detector = PatternDetector()
        
        patterns = {
            "pattern1": [
                TestResult(test_id="test_001", input="pricing question", actual_output="vague response", status="failed"),
                TestResult(test_id="test_002", input="cost inquiry", actual_output="unclear answer", status="failed")
            ],
            "pattern2": [
                TestResult(test_id="test_003", input="pricing inquiry", actual_output="ambiguous response", status="failed"),
                TestResult(test_id="test_004", input="price question", actual_output="vague answer", status="failed")
            ]
        }
        
        merged = detector.merge_similar_patterns(patterns, similarity_threshold=0.7)
        
        # Should merge similar patterns
        assert len(merged) <= len(patterns)
        # All tests should still be present
        total_tests = sum(len(tests) for tests in merged.values())
        original_tests = sum(len(tests) for tests in patterns.values())
        assert total_tests == original_tests
