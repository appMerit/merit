"""Unit tests for markdown formatter processor."""

import pytest
import tempfile
import os
from merit_analyzer.processors.markdown_formatter import (
    format_analysis_results,
    save_markdown_report,
    _format_error_group
)
from merit_analyzer.engines.code_analyzer import AnalysisResult


@pytest.fixture
def sample_results():
    """Create sample analysis results for testing."""
    return [
        AnalysisResult(
            group_name="PRICE_CALCULATION_ERROR",
            group_description="Price calculations return incorrect values when quantity > 10",
            root_cause="calculator.py:45 - Using wrong multiplication factor",
            problematic_code="price = quantity * 2  # Should be * unit_price",
            recommendations=[
                {
                    "type": "code",
                    "title": "Fix price calculation formula",
                    "description": "Change line 45 from `price = quantity * 2` to `price = quantity * unit_price`. The hardcoded multiplier causes incorrect pricing for bulk orders.",
                    "priority": "high",
                    "effort": "low"
                },
                {
                    "type": "config",
                    "title": "Add validation for price bounds",
                    "description": "Add a check to ensure calculated prices are within expected ranges to catch similar issues early.",
                    "priority": "medium",
                    "effort": "medium"
                }
            ],
            relevant_tests=[
                "Input: quantity=15, Expected: $150, Got: $30",
                "Input: quantity=20, Expected: $200, Got: $40"
            ]
        ),
        AnalysisResult(
            group_name="DATE_FORMAT_ERROR",
            group_description="Dates are formatted incorrectly in CSV exports",
            root_cause="formatter.py:23 - Missing date format string",
            problematic_code="date_str = str(date)  # Should use strftime",
            recommendations=[
                {
                    "type": "code",
                    "title": "Use proper date formatting",
                    "description": "Replace `str(date)` with `date.strftime('%Y-%m-%d')` to ensure consistent date format.",
                    "priority": "high",
                    "effort": "low"
                }
            ],
            relevant_tests=[
                "Input: 2024-01-15, Expected: '2024-01-15', Got: '2024-01-15 00:00:00'"
            ]
        )
    ]


def test_format_error_group(sample_results):
    """Test formatting a single error group."""
    result = sample_results[0]
    markdown = _format_error_group(1, result)
    
    # Check header
    assert "## 1. PRICE_CALCULATION_ERROR" in markdown
    
    # Check sections
    assert "### Problematic Behavior" in markdown
    assert "Price calculations return incorrect values" in markdown
    
    assert "### Root Cause" in markdown
    assert "calculator.py:45" in markdown
    
    assert "### Problematic Code" in markdown
    assert "price = quantity * 2" in markdown
    
    assert "### Recommended Fixes" in markdown
    assert "Fix price calculation formula" in markdown
    assert "Priority: HIGH" in markdown
    assert "Effort: low" in markdown
    
    assert "### Relevant Test Results" in markdown
    assert "Input: quantity=15" in markdown


def test_format_analysis_results(sample_results):
    """Test formatting complete analysis results."""
    markdown = format_analysis_results(sample_results)
    
    # Check title
    assert "# Test Failure Analysis Report" in markdown
    assert "**Total Error Groups:** 2" in markdown
    
    # Check both groups are present
    assert "PRICE_CALCULATION_ERROR" in markdown
    assert "DATE_FORMAT_ERROR" in markdown
    
    # Check structure - each group has numbered heading (## 1. and ## 2.)
    assert markdown.count("## 1.") == 1
    assert markdown.count("## 2.") == 1
    assert markdown.count("### Problematic Behavior") == 2
    assert markdown.count("### Root Cause") == 2
    assert markdown.count("### Problematic Code") == 2
    assert markdown.count("### Recommended Fixes") == 2
    assert markdown.count("### Relevant Test Results") == 2


def test_format_analysis_results_empty():
    """Test formatting with no results."""
    markdown = format_analysis_results([])
    
    assert "# Test Failure Analysis Report" in markdown
    assert "**Total Error Groups:** 0" in markdown


def test_save_markdown_report(sample_results):
    """Test saving markdown report to file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "test_report.md")
        
        save_markdown_report(sample_results, output_path)
        
        # Verify file exists
        assert os.path.exists(output_path)
        
        # Verify content
        with open(output_path, 'r') as f:
            content = f.read()
        
        assert "# Test Failure Analysis Report" in content
        assert "PRICE_CALCULATION_ERROR" in content
        assert "DATE_FORMAT_ERROR" in content


def test_markdown_format_with_special_characters(sample_results):
    """Test markdown formatting handles special characters correctly."""
    # Modify a result to have special characters
    sample_results[0].problematic_code = "price = quantity * 2  # <-- Wrong!"
    sample_results[0].group_description = "Prices are wrong & broken"
    
    markdown = format_analysis_results(sample_results)
    
    # Should preserve special characters
    assert "<-- Wrong!" in markdown
    assert "& broken" in markdown


def test_recommendation_priority_formatting(sample_results):
    """Test that priority is correctly formatted in uppercase."""
    markdown = format_analysis_results(sample_results)
    
    # Priorities should be uppercase
    assert "Priority: HIGH" in markdown
    assert "Priority: MEDIUM" in markdown


def test_multiple_recommendations_formatting():
    """Test formatting when a group has multiple recommendations."""
    result = AnalysisResult(
        group_name="MULTI_REC_ERROR",
        group_description="Test error with multiple fixes",
        root_cause="test.py:1 - Issue",
        problematic_code="bad code",
        recommendations=[
            {
                "type": "code",
                "title": "Fix 1",
                "description": "First fix",
                "priority": "high",
                "effort": "low"
            },
            {
                "type": "code",
                "title": "Fix 2",
                "description": "Second fix",
                "priority": "medium",
                "effort": "medium"
            },
            {
                "type": "config",
                "title": "Fix 3",
                "description": "Third fix",
                "priority": "low",
                "effort": "high"
            }
        ],
        relevant_tests=[]
    )
    
    markdown = format_analysis_results([result])
    
    # Check all recommendations are present
    assert "**1. Fix 1**" in markdown
    assert "**2. Fix 2**" in markdown
    assert "**3. Fix 3**" in markdown
    assert "First fix" in markdown
    assert "Second fix" in markdown
    assert "Third fix" in markdown

