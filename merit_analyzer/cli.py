"""Command-line interface for Merit Analyzer."""

import click  # type: ignore
import json
import os
from pathlib import Path
from typing import Optional

from .core.analyzer import MeritAnalyzer
from .core.config import MeritConfig
from .core.test_parser import TestParser


@click.command()
@click.option('--project-path', 
              default=".", 
              help='Path to AI system codebase',
              type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--test-results', 
              required=True, 
              help='Path to test results file (JSON, CSV, or pytest JSON)',
              type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.option('--api-key', 
              envvar='ANTHROPIC_API_KEY', 
              help='Anthropic API key (or set ANTHROPIC_API_KEY env var)')
@click.option('--provider', 
              default='anthropic', 
              help='API provider (anthropic/bedrock)',
              type=click.Choice(['anthropic', 'bedrock']))
@click.option('--output', 
              default='merit_report.json', 
              help='Output report path')
@click.option('--format', 
              'output_format',
              default='json', 
              help='Output format (json/markdown/html)',
              type=click.Choice(['json', 'markdown', 'html']))
@click.option('--config', 
              help='Path to configuration file',
              type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.option('--verbose', 
              is_flag=True, 
              help='Enable verbose output')
@click.option('--quick', 
              is_flag=True, 
              help='Quick analysis mode (skip some detailed analysis)')
@click.option('--export-recommendations', 
              help='Export recommendations to separate file',
              type=click.Path())
@click.option('--recommendations-format',
              default='markdown',
              help='Format for recommendations export',
              type=click.Choice(['markdown', 'html', 'json', 'text']))
def main(project_path: str,
         test_results: str,
         api_key: Optional[str],
         provider: str,
         output: str,
         output_format: str,
         config: Optional[str],
         verbose: bool,
         quick: bool,
         export_recommendations: Optional[str],
         recommendations_format: str):
    """
    Merit Analyzer CLI - Analyze AI system test failures and generate recommendations.
    
    This tool analyzes test failures in AI systems and provides specific,
    actionable recommendations for fixing them.
    
    Examples:
    
    \b
    # Basic usage
    merit-analyze --test-results test_results.json --api-key sk-ant-...
    
    \b
    # With custom project path and output
    merit-analyze --project-path ./my-ai-app --test-results results.json --output analysis.json
    
    \b
    # Export recommendations separately
    merit-analyze --test-results results.json --export-recommendations recs.md
    
    \b
    # Using configuration file
    merit-analyze --config config.yaml --test-results results.json
    """
    
    # Validate API key
    if not api_key:
        click.echo("❌ Error: API key is required. Set ANTHROPIC_API_KEY environment variable or use --api-key", err=True)
        raise click.Abort()
    
    # Load configuration if provided
    config_dict = {}
    if config:
        try:
            config_obj = MeritConfig.from_file(config)
            config_dict = config_obj.model_dump()
        except Exception as e:
            click.echo(f"❌ Error loading config file: {e}", err=True)
            raise click.Abort()
    
    # Override with CLI options
    config_dict.update({
        "project_path": project_path,
        "api_key": api_key,
        "provider": provider,
        "verbose": verbose,
    })
    
    if quick:
        config_dict.update({
            "max_patterns": 5,
            "min_cluster_size": 3,
        })
    
    try:
        # Initialize analyzer
        click.echo("🚀 Initializing Merit Analyzer...")
        analyzer = MeritAnalyzer(
            project_path=project_path,
            api_key=api_key,
            provider=provider,
            config=config_dict
        )
        
        # Load test results
        click.echo(f"📋 Loading test results from {test_results}...")
        test_parser = TestParser()
        test_batch = test_parser.parse(test_results)
        
        if not test_batch.results:
            click.echo("❌ No test results found in file", err=True)
            raise click.Abort()
        
        # Validate test results
        issues = test_parser.validate_test_results(test_batch)
        if issues:
            click.echo("⚠️  Validation issues found:", err=True)
            for issue in issues:
                click.echo(f"   - {issue}", err=True)
        
        # Run analysis
        click.echo("🔍 Starting analysis...")
        report = analyzer.analyze(test_batch.results)
        
        # Display summary
        click.echo("\n" + "="*60)
        click.echo("📊 ANALYSIS SUMMARY")
        click.echo("="*60)
        click.echo(f"Total tests: {report.summary.total_tests}")
        click.echo(f"Passed: {report.summary.passed}")
        click.echo(f"Failed: {report.summary.failed}")
        click.echo(f"Error: {report.summary.error}")
        click.echo(f"Skipped: {report.summary.skipped}")
        click.echo(f"Pass rate: {report.summary.pass_rate:.1%}")
        click.echo(f"Patterns found: {report.summary.patterns_found}")
        click.echo(f"Recommendations: {len(report.recommendations)}")
        click.echo(f"Analysis time: {report.summary.analysis_duration_seconds:.1f}s")
        
        if report.summary.frameworks_detected:
            click.echo(f"Frameworks: {', '.join(report.summary.frameworks_detected)}")
        
        # Display patterns
        if report.patterns:
            click.echo("\n🔍 FAILURE PATTERNS")
            click.echo("-" * 40)
            for pattern_name, pattern in report.patterns.items():
                click.echo(f"{pattern_name}: {pattern.failure_count} failures ({pattern.failure_rate:.1%})")
                if pattern.root_cause:
                    click.echo(f"  Root cause: {pattern.root_cause}")
        
        # Display top recommendations
        if report.recommendations:
            click.echo("\n💡 TOP RECOMMENDATIONS")
            click.echo("-" * 40)
            high_priority = [r for r in report.recommendations if r.priority.value == "high"]
            for i, rec in enumerate(high_priority[:5], 1):
                click.echo(f"{i}. {rec.title}")
                click.echo(f"   Type: {rec.type.value.title()}")
                click.echo(f"   Effort: {rec.effort_estimate}")
                click.echo(f"   Location: {rec.location}")
                click.echo()
        
        # Save report
        click.echo(f"💾 Saving report to {output}...")
        analyzer.save_report(report, output)
        
        # Export recommendations if requested
        if export_recommendations:
            click.echo(f"📄 Exporting recommendations to {export_recommendations}...")
            analyzer.export_recommendations(report, export_recommendations, recommendations_format)
        
        # Display action plan
        if report.action_plan:
            click.echo("\n📋 ACTION PLAN")
            click.echo("-" * 40)
            for action in report.action_plan[:10]:  # Show top 10 actions
                click.echo(f"• {action}")
        
        click.echo("\n✅ Analysis complete!")
        click.echo(f"📊 View detailed report: {output}")
        
        if export_recommendations:
            click.echo(f"💡 View recommendations: {export_recommendations}")
        
    except Exception as e:
        click.echo(f"❌ Analysis failed: {e}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc(), err=True)
        raise click.Abort()


@click.group()
def cli():
    """Merit Analyzer - AI system test failure analysis and recommendations."""
    pass


@cli.command()
@click.option('--project-path', 
              default=".", 
              help='Path to AI system codebase',
              type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option('--output', 
              default='project_scan.json', 
              help='Output file for scan results')
def scan(project_path: str, output: str):
    """Scan project structure and detect frameworks."""
    from .discovery.project_scanner import ProjectScanner
    from .discovery.framework_detector import FrameworkDetector
    
    click.echo("🔍 Scanning project structure...")
    
    scanner = ProjectScanner(project_path)
    scan_results = scanner.scan()
    
    detector = FrameworkDetector()
    frameworks = detector.detect(scanner.python_files)
    scan_results['frameworks'] = frameworks
    
    # Save results
    with open(output, 'w') as f:
        json.dump(scan_results, f, indent=2)
    
    click.echo(f"✅ Project scan complete! Results saved to {output}")
    click.echo(f"📁 Found {scan_results['file_count']} Python files")
    click.echo(f"🔧 Detected frameworks: {', '.join(frameworks.keys()) or 'None'}")


@cli.command()
@click.option('--test-results', 
              required=True, 
              help='Path to test results file',
              type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.option('--output', 
              default='test_analysis.json', 
              help='Output file for analysis')
def validate(test_results: str, output: str):
    """Validate test results file."""
    click.echo(f"📋 Validating test results from {test_results}...")
    
    parser = TestParser()
    test_batch = parser.parse(test_results)
    
    # Validate
    issues = parser.validate_test_results(test_batch)
    
    # Get summary
    summary = parser.get_summary_stats(test_batch)
    
    # Save validation results
    validation_results = {
        "valid": len(issues) == 0,
        "issues": issues,
        "summary": summary,
        "test_count": len(test_batch.results)
    }
    
    with open(output, 'w') as f:
        json.dump(validation_results, f, indent=2)
    
    if issues:
        click.echo(f"⚠️  Found {len(issues)} validation issues:")
        for issue in issues:
            click.echo(f"   - {issue}")
    else:
        click.echo("✅ Test results are valid!")
    
    click.echo(f"📊 Summary: {summary['total']} tests, {summary['pass_rate']:.1%} pass rate")
    click.echo(f"💾 Validation results saved to {output}")


@cli.command()
@click.option('--config-template', 
              default='merit_config.yaml', 
              help='Output file for configuration template')
def init_config(config_template: str):
    """Generate a configuration template file."""
    config = MeritConfig(
        project_path=".",
        api_key="your-api-key-here",
        provider="anthropic"
    )
    
    config.save(config_template)
    click.echo(f"📄 Configuration template created: {config_template}")
    click.echo("Edit the file with your settings and use with --config option")


# Add commands to main CLI
cli.add_command(main, name='analyze')
cli.add_command(scan)
cli.add_command(validate)
cli.add_command(init_config)


if __name__ == '__main__':
    cli()
