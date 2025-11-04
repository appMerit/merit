"""Command-line interface for Merit Analyzer."""

import os
import csv
import asyncio
from pathlib import Path
from typing import List
import click

from .types import TestCase, AssertionState, StateFailureReason
from .processors import cluster_failures, save_markdown_report
from .engines import analyze_groups, llm_client


def parse_csv_to_testcases(csv_path: str) -> List[AssertionState]:
    """
    Parse CSV file into AssertionState objects.
    
    Expected CSV columns:
    - input_value: Test input (any)
    - expected: Expected output (any)
    - actual: Actual output (any)
    - passed: True/False
    - error_message: Error message (optional)
    - additional_context: Additional context (optional)
    
    Args:
        csv_path: Path to CSV file
        
    Returns:
        List of AssertionState objects
    """
    assertion_states = []
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # Parse passed as boolean
            passed = row.get('passed', '').lower() in ['true', 'yes', '1']
            
            # Create TestCase
            test_case = TestCase(
                input_value=row.get('input_value', ''),
                expected=row.get('expected', ''),
                actual=row.get('actual', ''),
                passed=passed,
                error_message=row.get('error_message'),
                additional_context=row.get('additional_context')
            )
            
            # Create failure reason if failed
            failure_reason = None
            if not passed:
                error_msg = row.get('error_message') or 'Test failed'
                failure_reason = StateFailureReason(analysis=error_msg)
            
            # Create AssertionState
            assertion_state = AssertionState(
                test_case=test_case,
                return_value=row.get('actual', ''),
                passed=passed,
                confidence=1.0,  # Default confidence
                failure_reason=failure_reason
            )
            
            assertion_states.append(assertion_state)
    
    return assertion_states


@click.command()
@click.argument('csv_file', type=click.Path(exists=True))
@click.option('--project-path', '-p', default='.', help='Path to project to analyze')
@click.option('--output', '-o', default='analysis_report.md', help='Output markdown file')
@click.option('--api-key', envvar='ANTHROPIC_API_KEY', help='Anthropic API key')
@click.option('--model', default='claude-sonnet-4-20250514', help='Claude model to use')
def main(csv_file: str, project_path: str, output: str, api_key: str, model: str):
    """
    Merit Analyzer - AI System Test Failure Analysis
    
    Analyzes test failures from a CSV file and generates a detailed markdown report.
    
    Example:
        merit analyze tests.csv -p ./my_project -o report.md
    """
    if not api_key:
        click.echo("Error: ANTHROPIC_API_KEY not found. Set it as an environment variable or use --api-key", err=True)
        return 1
    
    click.echo(f"📊 Loading test results from {csv_file}...")
    
    # Parse CSV
    assertion_states = parse_csv_to_testcases(csv_file)
    total_tests = len(assertion_states)
    failed_tests = [a for a in assertion_states if not a.passed]
    
    click.echo(f"   Total tests: {total_tests}")
    click.echo(f"   Failed tests: {len(failed_tests)}")
    
    if not failed_tests:
        click.echo("✅ No failures to analyze!")
        return 0
    
    # Cluster failures
    click.echo("\n🔍 Clustering failures...")
    
    async def run_clustering():
        return await cluster_failures(failed_tests)
    
    clusters = asyncio.run(run_clustering())
    click.echo(f"   Found {len(clusters)} error groups")
    
    # Analyze each cluster
    click.echo("\n🤖 Analyzing error groups with Claude Agent SDK...")
    click.echo(f"   Project: {project_path}")
    
    results = analyze_groups(clusters, project_path, api_key, model)
    
    click.echo(f"   Analyzed {len(results)} error groups")
    
    # Generate markdown report
    click.echo(f"\n📝 Generating report: {output}")
    save_markdown_report(results, output)
    
    click.echo(f"\n✅ Analysis complete! Report saved to {output}")
    return 0


if __name__ == '__main__':
    main()

