"""Main MeritAnalyzer class - the public API for Merit Analyzer."""

import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

try:
    from rich.console import Console  # type: ignore
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn  # type: ignore
    from rich.panel import Panel  # type: ignore
    from rich.table import Table  # type: ignore
    from rich import box  # type: ignore
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from ..models.test_result import TestResult, TestResultBatch
from ..models.report import AnalysisReport, ReportSummary, PatternSummary
from ..models.pattern import Pattern
from ..models.recommendation import Recommendation
from ..core.config import MeritConfig
from ..core.test_parser import TestParser
from ..core.pattern_detector import PatternDetector
from ..discovery.project_scanner import ProjectScanner
from ..discovery.framework_detector import FrameworkDetector
from ..discovery.code_mapper import CodeMapper
from ..analysis.claude_agent import MeritClaudeAgent
from ..analysis.root_cause import RootCauseAnalyzer
from ..analysis.comparative import ComparativeAnalyzer
from ..recommendations.generator import RecommendationGenerator
from ..recommendations.prioritizer import RecommendationPrioritizer
from ..recommendations.formatter import RecommendationFormatter


class MeritAnalyzer:
    """
    Main analyzer class - the public API for Merit Analyzer.
    
    This class orchestrates the entire analysis pipeline from test results
    to actionable recommendations.
    """

    def __init__(self, 
                 project_path: str,
                 api_key: str,
                 provider: str = "anthropic",
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize Merit Analyzer.

        Args:
            project_path: Path to the AI system codebase
            api_key: Anthropic API key or AWS credentials
            provider: "anthropic" or "bedrock"
            config: Optional configuration overrides
        """
        self.project_path = Path(project_path)
        
        # Create configuration
        config_dict = config or {}
        config_dict.update({
            "project_path": str(project_path),
            "api_key": api_key,
            "provider": provider
        })
        self.config = MeritConfig(**config_dict)
        
        # Initialize components
        self.test_parser = TestParser()
        self.claude_agent = MeritClaudeAgent(self.config)
        self.pattern_detector = PatternDetector(
            min_cluster_size=self.config.min_cluster_size,
            similarity_threshold=self.config.similarity_threshold,
            max_patterns=self.config.max_patterns,
            claude_agent=self.claude_agent
        )
        self.project_scanner = ProjectScanner(project_path)
        self.framework_detector = FrameworkDetector()
        self.code_mapper = CodeMapper(project_path)
        self.root_cause_analyzer = RootCauseAnalyzer()
        self.comparative_analyzer = ComparativeAnalyzer()
        self.recommendation_generator = RecommendationGenerator(self.claude_agent)
        self.recommendation_prioritizer = RecommendationPrioritizer()
        self.recommendation_formatter = RecommendationFormatter()
        
        # Cache for discovered architecture
        self._architecture_cache: Optional[Dict[str, Any]] = None
        self._scan_results_cache: Optional[Dict[str, Any]] = None

    def analyze(self, test_results: Union[List[TestResult], List[Dict], TestResultBatch]) -> AnalysisReport:
        """
        Main analysis method.

        Args:
            test_results: List of TestResult objects, dicts, or TestResultBatch

        Returns:
            AnalysisReport with patterns, recommendations, and action plan
        """
        start_time = time.time()
        
        if RICH_AVAILABLE:
            console = Console()
            console.print(Panel.fit(
                "[bold blue]🚀 Merit Analyzer SDK[/bold blue]\n"
                "[dim]Analyzing AI system test failures and generating actionable recommendations[/dim]",
                border_style="blue"
            ))
        else:
            print("🔍 Merit Analyzer - Starting analysis...")
        
        try:
            # Step 1: Validate and parse test results
            if RICH_AVAILABLE:
                with Progress(
                    SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console,
                ) as progress:
                    task = progress.add_task("Parsing test results...", total=None)
                    parsed_tests = self._parse_test_results(test_results)
                    progress.update(task, description=f"✅ Found {len(parsed_tests)} tests ({sum(1 for t in parsed_tests if t.status == 'failed')} failures)")
            else:
                print("\n📋 Parsing test results...")
                parsed_tests = self._parse_test_results(test_results)
                print(f"   Found {len(parsed_tests)} tests ({sum(1 for t in parsed_tests if t.status == 'failed')} failures)")
            
            if not parsed_tests:
                raise ValueError("No test results provided")
            
            # Step 2: Quick project scan
            if RICH_AVAILABLE:
                with Progress(
                    SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console,
                ) as progress:
                    task = progress.add_task("Scanning project structure...", total=None)
                    scan_results = self._get_or_scan_project()
                    progress.update(task, description=f"✅ Found {scan_results['file_count']} Python files, frameworks: {', '.join(scan_results.get('frameworks', {}).keys()) or 'None'}")
            else:
                print("\n🗂️  Scanning project structure...")
                scan_results = self._get_or_scan_project()
                print(f"   Found {scan_results['file_count']} Python files")
                print(f"   Detected frameworks: {', '.join(scan_results.get('frameworks', {}).keys()) or 'None'}")
            
            # Step 3: Detect failure patterns
            if RICH_AVAILABLE:
                with Progress(
                    SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console,
                ) as progress:
                    task = progress.add_task("Detecting failure patterns...", total=None)
                    patterns = self.pattern_detector.detect_patterns(parsed_tests)
                    if patterns:
                        pattern_info = ", ".join([f"{name}: {len(tests)} failures" for name, tests in patterns.items()])
                        progress.update(task, description=f"✅ Identified {len(patterns)} patterns: {pattern_info}")
                    else:
                        progress.update(task, description="⚠️ No failure patterns detected")
            else:
                print("\n🔎 Detecting failure patterns...")
                patterns = self.pattern_detector.detect_patterns(parsed_tests)
                print(f"   Identified {len(patterns)} patterns:")
                for pattern_name, tests in patterns.items():
                    print(f"      - {pattern_name}: {len(tests)} failures")
            
            if not patterns:
                if RICH_AVAILABLE:
                    console.print("\n[bold yellow]⚠️ No failure patterns detected[/bold yellow]")
                else:
                    print("   ⚠️  No failure patterns detected")
                return self._create_empty_report(parsed_tests, scan_results)
            
            # Step 4-8: Main analysis with status updates
            if RICH_AVAILABLE:
                console.print("\n[bold green]🔍 Starting Deep Analysis...[/bold green]")
                
                # Step 4: Discover system architecture
                with Progress(
                    SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console,
                ) as progress:
                    task = progress.add_task("Analyzing system architecture...", total=None)
                    architecture = self._get_or_discover_architecture(scan_results)
                    progress.update(task, description="✅ System architecture analyzed")
                
                # Step 5: Map patterns to code
                with Progress(
                    SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console,
                ) as progress:
                    task = progress.add_task("Mapping patterns to code locations...", total=None)
                    pattern_mappings = {}
                    for pattern_name, failing_tests in patterns.items():
                        code_locations = self.claude_agent.map_pattern_to_code(
                            pattern_name, 
                            failing_tests,
                            architecture
                        )
                        pattern_mappings[pattern_name] = code_locations
                    progress.update(task, description="✅ Patterns mapped to code")
                
                # Step 6: Analyze each pattern
                all_recommendations = []
                pattern_summaries = {}
                
                for i, (pattern_name, failing_tests) in enumerate(patterns.items(), 1):
                    with Progress(
                        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console,
                    ) as progress:
                        task = progress.add_task(f"Analyzing pattern {i}/{len(patterns)}: {pattern_name}...", total=None)
                        
                        # Get similar passing tests for comparison
                        passing_tests = self._find_similar_passing_tests(
                            failing_tests, 
                            [t for t in parsed_tests if t.status == "passed"]
                        )
                        
                        # Create pattern object
                        pattern = Pattern(
                            name=pattern_name,
                            test_results=failing_tests,
                            confidence=0.8,  # Default confidence
                            keywords=self._extract_pattern_keywords(failing_tests)
                        )
                        
                        # Analyze with Merit's AI engine
                        analysis = self.claude_agent.analyze_pattern(
                            pattern_name=pattern_name,
                            failing_tests=failing_tests,
                            passing_tests=passing_tests,
                            code_locations=pattern_mappings[pattern_name]
                        )
                        
                        # Root cause analysis
                        code_context = self._get_code_context(pattern_mappings[pattern_name])
                        root_cause_analysis = self.root_cause_analyzer.analyze_root_cause(
                            pattern, code_context, architecture
                        )
                        
                        # Generate recommendations
                        recommendations = self.recommendation_generator.generate_recommendations(
                            pattern=pattern,
                            root_cause=root_cause_analysis["root_cause"],
                            code_context=code_context,
                            architecture=architecture
                        )
                        
                        # Add quick fixes
                        quick_fixes = self.recommendation_generator.generate_quick_fixes(pattern)
                        recommendations.extend(quick_fixes)
                        
                        # Add preventive measures
                        preventive = self.recommendation_generator.generate_preventive_measures(pattern)
                        recommendations.extend(preventive)
                        
                        all_recommendations.extend(recommendations)
                        
                        # Create pattern summary
                        pattern_summaries[pattern_name] = PatternSummary(
                            name=pattern_name,
                            failure_count=len(failing_tests),
                            failure_rate=len(failing_tests) / len(parsed_tests),
                            example_tests=failing_tests[:3],
                            recommendations=recommendations,
                            root_cause=root_cause_analysis["root_cause"],
                            confidence=root_cause_analysis["confidence"],
                            keywords=pattern.keywords
                        )
                        
                        progress.update(task, description=f"✅ Pattern '{pattern_name}' analyzed")
                
                # Step 7: Prioritize all recommendations
                with Progress(
                    SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console,
                ) as progress:
                    task = progress.add_task("Prioritizing recommendations...", total=None)
                    prioritized_recommendations = self.recommendation_prioritizer.prioritize_recommendations(
                        all_recommendations, pattern_summaries
                    )
                    progress.update(task, description="✅ Recommendations prioritized")
                
                # Step 8: Generate report
                with Progress(
                    SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console,
                ) as progress:
                    task = progress.add_task("Generating final report...", total=None)
                    report = self._generate_report(
                        parsed_tests,
                        pattern_summaries,
                        prioritized_recommendations,
                        architecture,
                        scan_results,
                        time.time() - start_time
                    )
                    progress.update(task, description="✅ Report generated")
            else:
                # Fallback to simple print statements
                print("\n🏗️  Analyzing system architecture...")
                architecture = self._get_or_discover_architecture(scan_results)
                print("   Architecture mapped successfully")
                
                print("\n🗺️  Mapping patterns to code locations...")
                pattern_mappings = {}
                for pattern_name, failing_tests in patterns.items():
                    code_locations = self.claude_agent.map_pattern_to_code(
                        pattern_name, 
                        failing_tests,
                        architecture
                    )
                    pattern_mappings[pattern_name] = code_locations
                    print(f"   {pattern_name} → {len(code_locations)} relevant files")
                
                print("\n🧠 Analyzing patterns and generating recommendations...")
                all_recommendations = []
                pattern_summaries = {}
                
                for pattern_name, failing_tests in patterns.items():
                    print(f"   Analyzing {pattern_name}...")
                    
                    # Get similar passing tests for comparison
                    passing_tests = self._find_similar_passing_tests(
                        failing_tests, 
                        [t for t in parsed_tests if t.status == "passed"]
                    )
                    
                    # Create pattern object
                    pattern = Pattern(
                        name=pattern_name,
                        test_results=failing_tests,
                        confidence=0.8,  # Default confidence
                        keywords=self._extract_pattern_keywords(failing_tests)
                    )
                    
                    # Analyze with Merit's AI engine
                    analysis = self.claude_agent.analyze_pattern(
                        pattern_name=pattern_name,
                        failing_tests=failing_tests,
                        passing_tests=passing_tests,
                        code_locations=pattern_mappings[pattern_name]
                    )
                    
                    # Root cause analysis
                    code_context = self._get_code_context(pattern_mappings[pattern_name])
                    root_cause_analysis = self.root_cause_analyzer.analyze_root_cause(
                        pattern, code_context, architecture
                    )
                    
                    # Generate recommendations
                    recommendations = self.recommendation_generator.generate_recommendations(
                        pattern=pattern,
                        root_cause=root_cause_analysis["root_cause"],
                        code_context=code_context,
                        architecture=architecture
                    )
                    
                    # Add quick fixes
                    quick_fixes = self.recommendation_generator.generate_quick_fixes(pattern)
                    recommendations.extend(quick_fixes)
                    
                    # Add preventive measures
                    preventive = self.recommendation_generator.generate_preventive_measures(pattern)
                    recommendations.extend(preventive)
                    
                    all_recommendations.extend(recommendations)
                    
                    # Create pattern summary
                    pattern_summaries[pattern_name] = PatternSummary(
                        name=pattern_name,
                        failure_count=len(failing_tests),
                        failure_rate=len(failing_tests) / len(parsed_tests),
                        example_tests=failing_tests[:3],
                        recommendations=recommendations,
                        root_cause=root_cause_analysis["root_cause"],
                        confidence=root_cause_analysis["confidence"],
                        keywords=pattern.keywords
                    )
                
                print("\n📊 Prioritizing recommendations...")
                prioritized_recommendations = self.recommendation_prioritizer.prioritize_recommendations(
                    all_recommendations, pattern_summaries
                )
                print(f"   Prioritized {len(prioritized_recommendations)} recommendations")
                
                print("\n📊 Generating analysis report...")
                report = self._generate_report(
                    parsed_tests,
                    pattern_summaries,
                    prioritized_recommendations,
                    architecture,
                    scan_results,
                    time.time() - start_time
                )
            
            # Display results
            if RICH_AVAILABLE:
                self._display_rich_results(report, console)
            else:
                print("\n✅ Analysis complete!")
            
            return report
            
        except Exception as e:
            if RICH_AVAILABLE:
                console.print(f"\n[red]❌ Analysis failed: {e}[/red]")
            else:
                print(f"\n❌ Analysis failed: {e}")
            raise

    def _parse_test_results(self, test_results: Union[List[TestResult], List[Dict], TestResultBatch]) -> List[TestResult]:
        """Parse and validate test results."""
        if isinstance(test_results, TestResultBatch):
            return test_results.results
        elif isinstance(test_results, list):
            if all(isinstance(t, TestResult) for t in test_results):
                return test_results
            elif all(isinstance(t, dict) for t in test_results):
                return [TestResult(**t) for t in test_results]
            else:
                raise ValueError("Mixed types in test results list")
        else:
            raise ValueError(f"Invalid test results type: {type(test_results)}")

    def _get_or_scan_project(self) -> Dict[str, Any]:
        """Get cached scan results or perform new scan."""
        if self._scan_results_cache is None:
            scan_results = self.project_scanner.scan()
            frameworks = self.framework_detector.detect(self.project_scanner.python_files)
            scan_results['frameworks'] = frameworks
            self._scan_results_cache = scan_results
        return self._scan_results_cache

    def _get_or_discover_architecture(self, scan_results: Dict[str, Any]) -> Dict[str, Any]:
        """Get cached architecture or discover it."""
        if self._architecture_cache is None:
            self._architecture_cache = self.claude_agent.discover_system_architecture(scan_results)
        return self._architecture_cache

    def _find_similar_passing_tests(self, 
                                   failing_tests: List[TestResult],
                                   passing_tests: List[TestResult]) -> List[TestResult]:
        """Find passing tests similar to failing ones for comparison."""
        if not passing_tests:
            return []
        
        # Use simple keyword matching for now
        failing_keywords = set()
        for test in failing_tests:
            words = test.input.lower().split()
            failing_keywords.update(words)
        
        similar = []
        for test in passing_tests:
            test_words = set(test.input.lower().split())
            overlap = len(failing_keywords & test_words)
            if overlap >= 2:  # At least 2 keywords in common
                similar.append(test)
        
        return similar[:5]  # Return up to 5 similar passing tests

    def _extract_pattern_keywords(self, tests: List[TestResult]) -> List[str]:
        """Extract keywords from a pattern's tests."""
        keywords = set()
        for test in tests:
            if test.input:
                words = test.input.lower().split()
                keywords.update(words)
            if test.failure_reason:
                words = test.failure_reason.lower().split()
                keywords.update(words)
        
        # Filter out common words
        stop_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her',
                     'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its',
                     'may', 'new', 'now', 'old', 'see', 'two', 'way', 'who', 'boy', 'did', 'man',
                     'men', 'put', 'say', 'she', 'too', 'use', 'test', 'tests', 'testing', 'result',
                     'results', 'input', 'output', 'expected', 'actual', 'failure', 'failed',
                     'error', 'exception', 'message', 'string', 'value', 'values', 'data'}
        
        return [word for word in keywords if word not in stop_words][:10]

    def _get_code_context(self, file_paths: List[str]) -> Dict[str, str]:
        """Get code context for the given file paths."""
        context = {}
        for file_path in file_paths:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Truncate very long files
                    if len(content) > 10000:
                        content = content[:10000] + "\n... (truncated)"
                    context[file_path] = content
            except Exception as e:
                print(f"    ⚠️  Error reading {file_path}: {e}")
                context[file_path] = f"Error reading file: {e}"
        return context

    def _generate_report(self, 
                        test_results: List[TestResult],
                        pattern_summaries: Dict[str, PatternSummary],
                        recommendations: List[Recommendation],
                        architecture: Dict[str, Any],
                        scan_results: Dict[str, Any],
                        duration: float) -> AnalysisReport:
        """Generate final analysis report."""
        
        # Calculate summary statistics
        total_tests = len(test_results)
        passed = sum(1 for t in test_results if t.status == "passed")
        failed = sum(1 for t in test_results if t.status == "failed")
        error = sum(1 for t in test_results if t.status == "error")
        skipped = sum(1 for t in test_results if t.status == "skipped")
        
        # Generate prioritized action plan
        action_plan = self._generate_action_plan(pattern_summaries, recommendations)
        
        # Create report summary
        summary = ReportSummary(
            total_tests=total_tests,
            passed=passed,
            failed=failed,
            error=error,
            skipped=skipped,
            patterns_found=len(pattern_summaries),
            analysis_timestamp=datetime.now().isoformat(),
            analysis_duration_seconds=duration,
            project_path=str(self.project_path),
            frameworks_detected=list(scan_results.get('frameworks', {}).keys())
        )
        
        return AnalysisReport(
            summary=summary,
            patterns=pattern_summaries,
            action_plan=action_plan,
            architecture=architecture,
            recommendations=recommendations,
            metadata={
                "analyzer_version": "1.0.0",
                "config": self.config.model_dump(),
                "scan_results": scan_results
            }
        )

    def _generate_action_plan(self, 
                             pattern_summaries: Dict[str, PatternSummary],
                             recommendations: List[Recommendation]) -> List[str]:
        """Generate prioritized action plan."""
        # Sort patterns by impact (failure count)
        sorted_patterns = sorted(
            pattern_summaries.items(),
            key=lambda x: x[1].failure_count,
            reverse=True
        )
        
        plan = []
        
        # Add pattern-based actions
        for i, (pattern_name, pattern) in enumerate(sorted_patterns, 1):
            if pattern.recommendations:
                top_rec = pattern.recommendations[0]  # Get top recommendation
                plan.append(
                    f"{i}. [{top_rec.effort_estimate}] {top_rec.title} → "
                    f"fixes {pattern.failure_count} tests in {pattern_name}"
                )
        
        # Add quick wins
        quick_wins = self.recommendation_prioritizer.get_quick_wins(recommendations)
        if quick_wins:
            plan.append(f"\nQuick Wins ({len(quick_wins)} recommendations):")
            for i, rec in enumerate(quick_wins[:3], 1):  # Top 3 quick wins
                plan.append(f"  - {rec.title} ({rec.effort_estimate})")
        
        return plan

    def _create_empty_report(self, 
                           test_results: List[TestResult],
                           scan_results: Dict[str, Any]) -> AnalysisReport:
        """Create an empty report when no patterns are detected."""
        total_tests = len(test_results)
        passed = sum(1 for t in test_results if t.status == "passed")
        failed = sum(1 for t in test_results if t.status == "failed")
        error = sum(1 for t in test_results if t.status == "error")
        skipped = sum(1 for t in test_results if t.status == "skipped")
        
        summary = ReportSummary(
            total_tests=total_tests,
            passed=passed,
            failed=failed,
            error=error,
            skipped=skipped,
            patterns_found=0,
            analysis_timestamp=datetime.now().isoformat(),
            project_path=str(self.project_path),
            frameworks_detected=list(scan_results.get('frameworks', {}).keys())
        )
        
        return AnalysisReport(
            summary=summary,
            patterns={},
            action_plan=["No failure patterns detected - all tests are passing or have unique failures"],
            architecture={},
            recommendations=[],
            metadata={
                "analyzer_version": "1.0.0",
                "config": self.config.model_dump(),
                "scan_results": scan_results
            }
        )

    def save_report(self, report: AnalysisReport, output_path: str = "merit_analysis_output/merit_analysis_report.json"):
        """Save report to file."""
        # Create output directory if it doesn't exist
        from pathlib import Path
        output_dir = Path(output_path).parent
        output_dir.mkdir(exist_ok=True)
        
        report.save(output_path, "json")
        print(f"📄 Report saved to {output_path}")
        
        # Also save markdown version
        md_path = output_path.replace('.json', '.md')
        report.save(md_path, "markdown")
        print(f"📄 Markdown report saved to {md_path}")

    def export_recommendations(self, 
                             report: AnalysisReport,
                             output_path: str,
                             format_type: str = "markdown"):
        """Export recommendations to a file."""
        self.recommendation_formatter.export_to_file(
            report.recommendations,
            output_path,
            format_type,
            report.patterns
        )

    def get_quick_wins(self, report: AnalysisReport) -> List[Recommendation]:
        """Get quick win recommendations from the report."""
        return self.recommendation_prioritizer.get_quick_wins(report.recommendations)

    def create_implementation_plan(self, report: AnalysisReport) -> List[Dict[str, Any]]:
        """Create an implementation plan from the report."""
        return self.recommendation_prioritizer.create_implementation_plan(report.recommendations)

    def clear_cache(self):
        """Clear all caches."""
        self._architecture_cache = None
        self._scan_results_cache = None
        self.claude_agent.clear_cache()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        claude_stats = self.claude_agent.get_cache_stats()
        return {
            "claude_cache": claude_stats,
            "architecture_cached": self._architecture_cache is not None,
            "scan_results_cached": self._scan_results_cache is not None
        }

    def _display_rich_results(self, report: AnalysisReport, console: Console):
        """Display results using Rich formatting."""
        # Summary table
        table = Table(title="📊 Analysis Summary", box=box.ROUNDED)
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="bold")
        
        table.add_row("Total Tests", str(report.summary.total_tests))
        table.add_row("Passed", f"[green]{report.summary.passed}[/green]")
        table.add_row("Failed", f"[red]{report.summary.failed}[/red]")
        table.add_row("Error", f"[yellow]{report.summary.error}[/yellow]")
        table.add_row("Pass Rate", f"{report.summary.passed/report.summary.total_tests*100:.1f}%")
        table.add_row("Patterns Found", str(report.summary.patterns_found))
        table.add_row("Recommendations", str(len(report.recommendations)))
        table.add_row("Analysis Time", f"{report.summary.analysis_duration_seconds:.1f}s")
        
        console.print("\n")
        console.print(table)
        
        # Recommendations table
        if report.recommendations:
            rec_table = Table(title="🎯 Top Recommendations", box=box.ROUNDED)
            rec_table.add_column("Priority", style="bold", no_wrap=True)
            rec_table.add_column("Title", style="cyan")
            rec_table.add_column("Effort", style="yellow")
            rec_table.add_column("Impact", style="green")
            
            for rec in report.recommendations[:5]:  # Top 5
                priority_color = {
                    "HIGH": "red",
                    "MEDIUM": "yellow", 
                    "LOW": "green"
                }.get(rec.priority, "white")
                
                rec_table.add_row(
                    f"[{priority_color}]{rec.priority}[/{priority_color}]",
                    rec.title[:50] + "..." if len(rec.title) > 50 else rec.title,
                    rec.effort_estimate,
                    rec.expected_impact
                )
            
            console.print("\n")
            console.print(rec_table)
        
        # Patterns
        if report.patterns:
            console.print("\n[bold cyan]🔍 Detected Failure Patterns:[/bold cyan]")
            for i, (pattern_name, pattern) in enumerate(report.patterns.items(), 1):
                # Convert snake_case to readable format
                display_name = pattern_name.replace('_', ' ').title()
                
                console.print(f"  [bold]{i}.[/bold] [yellow]{display_name}[/yellow]")
                console.print(f"     Failures: [red]{pattern.failure_count}[/red] ({pattern.failure_rate*100:.1f}%)")
                if hasattr(pattern, 'root_cause') and pattern.root_cause:
                    console.print(f"     Root Cause: [dim]{pattern.root_cause}[/dim]")
                console.print()
        
        # Final success message
        console.print(Panel.fit(
            f"[bold green]✅ Analysis Complete![/bold green]\n\n"
            f"[cyan]Total recommendations:[/cyan] [bold]{len(report.recommendations)}[/bold]\n"
            f"[cyan]Patterns detected:[/cyan] [bold]{len(report.patterns)}[/bold]\n"
            f"[cyan]Analysis time:[/cyan] [bold]{report.summary.analysis_duration_seconds:.1f}s[/bold]",
            border_style="green"
        ))
