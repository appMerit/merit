"""Markdown formatter for analysis results."""

from typing import List
from ..engines.code_analyzer import AnalysisResult


def format_analysis_results(results: List[AnalysisResult]) -> str:
    """
    Format analysis results into markdown.
    
    Structure: error group name > problematic behavior > problematic code > relevant test results
    
    Args:
        results: List of analysis results from CodeAnalyzer
        
    Returns:
        Markdown formatted string
    """
    markdown_sections = []
    
    # Title
    markdown_sections.append("# Test Failure Analysis Report\n")
    markdown_sections.append(f"**Total Error Groups:** {len(results)}\n")
    markdown_sections.append("---\n")
    
    # Each error group
    for idx, result in enumerate(results, 1):
        section = _format_error_group(idx, result)
        markdown_sections.append(section)
    
    return "\n".join(markdown_sections)


def _format_error_group(idx: int, result: AnalysisResult) -> str:
    """Format a single error group section."""
    lines = []
    
    # Header
    lines.append(f"## {idx}. {result.group_name}\n")
    
    # Problematic Behavior
    lines.append("### Problematic Behavior\n")
    lines.append(f"{result.group_description}\n")
    
    # Root Cause
    lines.append("### Root Cause\n")
    lines.append(f"```\n{result.root_cause}\n```\n")
    
    # Problematic Code
    lines.append("### Problematic Code\n")
    lines.append(f"```python\n{result.problematic_code}\n```\n")
    
    # Recommendations
    if result.recommendations:
        lines.append("### Recommended Fixes\n")
        for rec_idx, rec in enumerate(result.recommendations, 1):
            lines.append(f"**{rec_idx}. {rec.get('title', 'Fix')}** "
                        f"(Priority: {rec.get('priority', 'medium').upper()}, "
                        f"Effort: {rec.get('effort', 'medium')})\n")
            lines.append(f"{rec.get('description', 'No description')}\n")
    
    # Relevant Test Results
    lines.append("### Relevant Test Results\n")
    for test in result.relevant_tests:
        lines.append(f"- {test}\n")
    
    lines.append("---\n")
    
    return "\n".join(lines)


def save_markdown_report(results: List[AnalysisResult], output_path: str) -> None:
    """
    Save analysis results to a markdown file.
    
    Args:
        results: Analysis results
        output_path: Path to save the markdown file
    """
    markdown_content = format_analysis_results(results)
    
    with open(output_path, 'w') as f:
        f.write(markdown_content)

