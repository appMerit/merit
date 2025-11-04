"""Unit tests for code analyzer engine."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from merit_analyzer.engines.code_analyzer import CodeAnalyzer, AnalysisResult
from merit_analyzer.types.assertion import AssertionState, AssertionStateGroup, StateGroupMetadata, StateFailureReason
from merit_analyzer.types.testcase import TestCase


@pytest.fixture
def sample_group():
    """Create a sample assertion state group for testing."""
    test_cases = [
        AssertionState(
            test_case=TestCase(
                input_value="test input 1",
                expected="expected output",
                actual="wrong output",
                passed=False,
                error_message="Price calculation incorrect"
            ),
            return_value="wrong output",
            passed=False,
            confidence=1.0,
            failure_reason=StateFailureReason(analysis="Price calculation incorrect")
        ),
        AssertionState(
            test_case=TestCase(
                input_value="test input 2",
                expected="expected output",
                actual="wrong output",
                passed=False,
                error_message="Price calculation incorrect"
            ),
            return_value="wrong output",
            passed=False,
            confidence=1.0,
            failure_reason=StateFailureReason(analysis="Price calculation incorrect")
        )
    ]
    
    return AssertionStateGroup(
        metadata=StateGroupMetadata(
            name="PRICE_CALCULATION_ERROR",
            description="Price calculations are returning incorrect values"
        ),
        assertion_states=test_cases,
        grouped_by="failed"
    )


def test_code_analyzer_initialization():
    """Test CodeAnalyzer initializes correctly."""
    analyzer = CodeAnalyzer(
        project_path="/test/project",
        api_key="test_key",
        model="claude-sonnet-4-20250514"
    )
    
    assert analyzer.project_path.as_posix() == "/test/project"
    assert analyzer.api_key == "test_key"
    assert analyzer.model == "claude-sonnet-4-20250514"


def test_build_minimal_prompt(sample_group):
    """Test minimal prompt building."""
    analyzer = CodeAnalyzer(
        project_path="/test/project",
        api_key="test_key"
    )
    
    prompt = analyzer._build_minimal_prompt(sample_group)
    
    assert "PRICE_CALCULATION_ERROR" in prompt
    assert "2 tests" in prompt
    assert "Price calculation incorrect" in prompt
    assert "Use Grep/Read" in prompt


@pytest.mark.asyncio
async def test_analyze_error_group():
    """Test analyzing a single error group returns AnalysisResult."""
    analyzer = CodeAnalyzer(
        project_path="/test/project",
        api_key="test_key"
    )
    
    # Create mock block with proper attributes
    mock_block = MagicMock()
    mock_block.type = 'tool_use'
    mock_block.name = 'submit_analysis'
    mock_block.input = {
        'root_cause': 'calculator.py:45 - Wrong formula used',
        'problematic_code': 'price = quantity * 2',
        'recommendations': [
            {
                'type': 'code',
                'title': 'Fix calculation',
                'description': 'Use correct formula',
                'priority': 'high',
                'effort': 'low'
            }
        ]
    }
    
    # Mock the Claude SDK query
    mock_message = MagicMock()
    mock_message.content = [mock_block]
    mock_message.usage = {'input_tokens': 100, 'output_tokens': 50}
    mock_message.subtype = 'success'
    
    async def mock_query(*args, **kwargs):
        yield mock_message
    
    with patch.object(analyzer, '_lazy_import_sdk'):
        analyzer._claude_query = mock_query
        analyzer._ClaudeAgentOptions = MagicMock()
        
        test_group = AssertionStateGroup(
            metadata=StateGroupMetadata(
                name="TEST_ERROR",
                description="Test error description"
            ),
            assertion_states=[
                AssertionState(
                    test_case=TestCase(
                        input_value="test",
                        expected="expected",
                        actual="wrong",
                        passed=False,
                        error_message="Test error"
                    ),
                    return_value="wrong",
                    passed=False,
                    confidence=1.0,
                    failure_reason=StateFailureReason(analysis="Test error")
                )
            ],
            grouped_by="failed"
        )
        
        result = await analyzer.analyze_error_group(test_group)
        
        # Just verify it returns an AnalysisResult (mocking full flow is complex)
        assert isinstance(result, AnalysisResult)
        assert result.group_name == "TEST_ERROR"
        assert result.group_description == "Test error description"
        assert len(result.relevant_tests) > 0


@pytest.mark.asyncio
async def test_analyze_multiple_groups():
    """Test analyzing multiple error groups."""
    analyzer = CodeAnalyzer(
        project_path="/test/project",
        api_key="test_key"
    )
    
    # Mock the Claude SDK query
    mock_message = MagicMock()
    mock_message.content = [
        MagicMock(
            type='tool_use',
            name='submit_analysis',
            input={
                'root_cause': 'test.py:1 - Test issue',
                'problematic_code': 'test code',
                'recommendations': [
                    {
                        'type': 'code',
                        'title': 'Fix it',
                        'description': 'Fix description',
                        'priority': 'high',
                        'effort': 'low'
                    }
                ]
            }
        )
    ]
    mock_message.usage = {'input_tokens': 100, 'output_tokens': 50}
    mock_message.subtype = 'success'
    
    async def mock_query(*args, **kwargs):
        yield mock_message
    
    with patch.object(analyzer, '_lazy_import_sdk'):
        with patch.object(analyzer, '_claude_query', mock_query):
            analyzer._ClaudeAgentOptions = MagicMock()
            
            groups = [
                AssertionStateGroup(
                    metadata=StateGroupMetadata(
                        name=f"ERROR_{i}",
                        description=f"Error {i} description"
                    ),
                    assertion_states=[
                        AssertionState(
                            test_case=TestCase(
                                input_value="test",
                                expected="expected",
                                actual="wrong",
                                passed=False,
                                error_message="Test error"
                            ),
                            return_value="wrong",
                            passed=False,
                            confidence=1.0,
                            failure_reason=StateFailureReason(analysis="Test error")
                        )
                    ],
                    grouped_by="failed"
                )
                for i in range(3)
            ]
            
            results = await analyzer.analyze_multiple_groups(groups)
            
            assert len(results) == 3
            assert all(isinstance(r, AnalysisResult) for r in results)
            assert results[0].group_name == "ERROR_0"
            assert results[1].group_name == "ERROR_1"
            assert results[2].group_name == "ERROR_2"


def test_parse_response():
    """Test parsing Claude's response text."""
    analyzer = CodeAnalyzer(
        project_path="/test/project",
        api_key="test_key"
    )
    
    # Test with valid response
    response = "Some text before\nThis is the code\nMore text"
    result = analyzer._parse_response(response)
    
    assert 'root_cause' in result
    assert 'problematic_code' in result
    assert 'recommendations' in result

