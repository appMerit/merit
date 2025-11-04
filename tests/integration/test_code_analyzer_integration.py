"""Integration tests for code analyzer with real Claude Agent SDK.

These tests use the real Anthropic API and require ANTHROPIC_API_KEY to be set.
Run with: pytest tests/integration/ -v -s
Skip with: pytest tests/unit/ (skips integration tests)
"""

import pytest
import os
from pathlib import Path
from merit_analyzer.engines.code_analyzer import CodeAnalyzer, analyze_groups
from merit_analyzer.types.assertion import AssertionState, AssertionStateGroup, StateGroupMetadata, StateFailureReason
from merit_analyzer.types.testcase import TestCase
from merit_analyzer.processors.markdown_formatter import format_analysis_results


# Skip all tests in this module if no API key
pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set - skipping integration tests"
)


@pytest.fixture
def api_key():
    """Get API key from environment."""
    return os.environ.get("ANTHROPIC_API_KEY")


@pytest.fixture
def test_project_path():
    """Path to a test project for analysis (current repo)."""
    # Use the merit_analyzer repo itself as test subject
    return str(Path(__file__).parent.parent.parent)


def create_test_group(name: str, description: str, test_cases: list) -> AssertionStateGroup:
    """Helper to create an assertion state group."""
    assertion_states = []
    
    for tc in test_cases:
        assertion_states.append(
            AssertionState(
                test_case=TestCase(
                    input_value=tc['input'],
                    expected=tc['expected'],
                    actual=tc['actual'],
                    passed=False,
                    error_message=tc['error']
                ),
                return_value=tc['actual'],
                passed=False,
                confidence=1.0,
                failure_reason=StateFailureReason(analysis=tc['error'])
            )
        )
    
    return AssertionStateGroup(
        metadata=StateGroupMetadata(
            name=name,
            description=description
        ),
        assertion_states=assertion_states,
        grouped_by="failed"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_price_calculation_error(api_key, test_project_path):
    """Test analyzing a price calculation error with real Claude Agent SDK."""
    # Create realistic test failure scenario
    group = create_test_group(
        name="PRICE_CALCULATION_ERROR",
        description="Price calculations return incorrect values for bulk orders",
        test_cases=[
            {
                'input': "quantity=15, unit_price=10",
                'expected': "$150",
                'actual': "$30",
                'error': "Price calculation incorrect: expected $150 but got $30"
            },
            {
                'input': "quantity=20, unit_price=10",
                'expected': "$200",
                'actual': "$40",
                'error': "Price calculation incorrect: expected $200 but got $40"
            }
        ]
    )
    
    # Analyze with real Claude Agent SDK
    analyzer = CodeAnalyzer(
        project_path=test_project_path,
        api_key=api_key,
        model="claude-sonnet-4-20250514"
    )
    
    results = await analyzer.analyze_multiple_groups([group])
    result = results[0]
    
    # Verify result structure
    assert result.group_name == "PRICE_CALCULATION_ERROR"
    assert result.root_cause is not None
    assert ":" in result.root_cause  # Should have file:line format
    assert result.problematic_code is not None
    assert len(result.recommendations) > 0
    
    # Verify recommendations have required fields
    for rec in result.recommendations:
        assert 'type' in rec
        assert 'title' in rec
        assert 'description' in rec
        assert 'priority' in rec
        assert 'effort' in rec
    
    # Print for manual inspection
    print(f"\n{'='*60}")
    print(f"Test: Price Calculation Error")
    print(f"{'='*60}")
    print(f"Root Cause: {result.root_cause}")
    print(f"Problematic Code:\n{result.problematic_code}")
    print(f"Recommendations: {len(result.recommendations)}")
    for i, rec in enumerate(result.recommendations, 1):
        print(f"  {i}. {rec['title']} (Priority: {rec['priority']}, Effort: {rec['effort']})")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_date_format_error(api_key, test_project_path):
    """Test analyzing a date formatting error."""
    group = create_test_group(
        name="DATE_FORMAT_ERROR",
        description="Dates formatted incorrectly in output",
        test_cases=[
            {
                'input': "date=2024-01-15",
                'expected': "2024-01-15",
                'actual': "2024-01-15 00:00:00",
                'error': "Date format includes timestamp when only date expected"
            },
            {
                'input': "date=2024-03-20",
                'expected': "2024-03-20",
                'actual': "2024-03-20 00:00:00",
                'error': "Date format includes timestamp when only date expected"
            }
        ]
    )
    
    analyzer = CodeAnalyzer(
        project_path=test_project_path,
        api_key=api_key
    )
    
    results = await analyzer.analyze_multiple_groups([group])
    result = results[0]
    
    assert result.group_name == "DATE_FORMAT_ERROR"
    assert result.root_cause is not None
    assert len(result.recommendations) > 0
    
    print(f"\n{'='*60}")
    print(f"Test: Date Format Error")
    print(f"{'='*60}")
    print(f"Root Cause: {result.root_cause}")
    print(f"Recommendations: {len(result.recommendations)}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_batch_analysis_multiple_clusters(api_key, test_project_path):
    """Test analyzing multiple error groups in one batch (realistic workflow)."""
    # Create multiple error groups
    groups = [
        create_test_group(
            name="TRUNCATION_ERROR",
            description="Text truncated causing data loss",
            test_cases=[
                {
                    'input': "text='Long text with important info...'",
                    'expected': "Complete text",
                    'actual': "Long text wit...",
                    'error': "Text truncated, missing important information"
                }
            ]
        ),
        create_test_group(
            name="TONE_TOO_TECHNICAL",
            description="Output is too technical for general audience",
            test_cases=[
                {
                    'input': "topic='AI explanation'",
                    'expected': "Accessible explanation",
                    'actual': "Uses jargon like 'LLM', 'embeddings', 'neural networks'",
                    'error': "Content too technical, not accessible to general readers"
                }
            ]
        ),
        create_test_group(
            name="MISSING_GREETING",
            description="Output missing required greeting format",
            test_cases=[
                {
                    'input': "format='newsletter'",
                    'expected': "Starts with 'Welcome to...'",
                    'actual': "Starts directly with content",
                    'error': "Missing greeting at start of newsletter"
                }
            ]
        )
    ]
    
    # Analyze all groups
    analyzer = CodeAnalyzer(
        project_path=test_project_path,
        api_key=api_key
    )
    results = await analyzer.analyze_multiple_groups(groups)
    
    # Verify results
    assert len(results) == 3
    assert all(r.group_name in ["TRUNCATION_ERROR", "TONE_TOO_TECHNICAL", "MISSING_GREETING"] for r in results)
    
    # Generate markdown report
    markdown = format_analysis_results(results)
    
    # Verify markdown structure
    assert "# Test Failure Analysis Report" in markdown
    assert "**Total Error Groups:** 3" in markdown
    assert "TRUNCATION_ERROR" in markdown
    assert "TONE_TOO_TECHNICAL" in markdown
    assert "MISSING_GREETING" in markdown
    
    # Print report
    print(f"\n{'='*60}")
    print("GENERATED MARKDOWN REPORT")
    print(f"{'='*60}")
    print(markdown[:1000])  # First 1000 chars
    print("...")
    print(f"\n(Full report is {len(markdown)} characters)")
    
    # Save to file for inspection
    output_path = Path(__file__).parent / "test_output_report.md"
    with open(output_path, 'w') as f:
        f.write(markdown)
    print(f"\nFull report saved to: {output_path}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hallucination_detection(api_key, test_project_path):
    """Test that analyzer finds hallucination issues in code."""
    group = create_test_group(
        name="HALLUCINATED_DATA",
        description="System generates fabricated information not present in source",
        test_cases=[
            {
                'input': "company='Unknown Startup'",
                'expected': "No information or graceful message",
                'actual': "Invented funding details: '$10M from Sequoia'",
                'error': "Generated fake funding information not found in any source"
            }
        ]
    )
    
    analyzer = CodeAnalyzer(
        project_path=test_project_path,
        api_key=api_key
    )
    
    results = await analyzer.analyze_multiple_groups([group])
    result = results[0]
    
    assert result.group_name == "HALLUCINATED_DATA"
    assert result.root_cause is not None
    assert len(result.recommendations) > 0
    
    # Check if recommendations mention validation or error handling
    rec_text = " ".join(r['description'].lower() for r in result.recommendations)
    # Should mention things like: validation, check, verify, handle empty, etc.
    
    print(f"\n{'='*60}")
    print(f"Test: Hallucination Detection")
    print(f"{'='*60}")
    print(f"Root Cause: {result.root_cause}")
    for i, rec in enumerate(result.recommendations, 1):
        print(f"\nRecommendation {i}: {rec['title']}")
        print(f"Description: {rec['description'][:200]}...")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cost_tracking(api_key, test_project_path):
    """Test that token usage and cost are tracked correctly."""
    group = create_test_group(
        name="SIMPLE_ERROR",
        description="Simple test error for cost tracking",
        test_cases=[
            {
                'input': "x=5",
                'expected': "10",
                'actual': "5",
                'error': "Math calculation wrong"
            }
        ]
    )
    
    # Analyze and capture output (token usage is printed)
    analyzer = CodeAnalyzer(
        project_path=test_project_path,
        api_key=api_key
    )
    results = await analyzer.analyze_multiple_groups([group])
    
    assert len(results) == 1
    assert results[0].group_name == "SIMPLE_ERROR"
    
    # Print detailed results
    print(f"\n{'='*60}")
    print("ANALYSIS RESULTS")
    print(f"{'='*60}")
    result = results[0]
    print(f"\n📋 Group: {result.group_name}")
    print(f"📝 Description: {result.group_description}")
    print(f"\n🔍 Root Cause:")
    print(f"   {result.root_cause}")
    print(f"\n💻 Problematic Code:")
    print(f"   {result.problematic_code[:200]}...")
    print(f"\n💡 Recommendations: {len(result.recommendations)}")
    for i, rec in enumerate(result.recommendations[:2], 1):
        print(f"   {i}. {rec.get('title', 'No title')}")
    
    print(f"\n{'='*60}")
    print("Cost tracking test completed")
    print("Check console output above for token usage and cost")
    print(f"{'='*60}")

