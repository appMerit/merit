from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
from typing import Sequence

os.environ["TOKENIZERS_PARALLELISM"] = "false"

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from ..engines.error_analyzer.driver import ErrorAnalyzer
from ..processors.clustering import cluster_failures
from ..processors.parse_test_cases import parse_test_cases_from_csv
from ..processors.report_formatter import format_analysis_results
from ..types import TestCase


class CLIApplication:
    """Top-level command router."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()
        self.parser = argparse.ArgumentParser(
            prog="merit-analyzer",
            description="Run error analysis on AI test results.",
        )
        subparsers = self.parser.add_subparsers(dest="command", required=True)
        analyze = subparsers.add_parser(
            "analyze",
            help="Cluster failures and generate a Markdown report.",
        )
        analyze.add_argument(
            "csv_path",
            help="CSV export containing case_input, reference_value, output_for_assertions, passed, error_message columns.",
        )
        analyze.add_argument(
            "--report",
            dest="report_path",
            default="merit_report.md",
            help="Where to write the Markdown report (default: merit_report.md)",
        )
        analyze.add_argument(
            "--model-vendor",
            dest="model_vendor",
            help="MODEL_VENDOR env override (e.g., openai, anthropic).",
        )
        analyze.add_argument(
            "--inference-vendor",
            dest="inference_vendor",
            help="INFERENCE_VENDOR env override (e.g., openai, aws, gcp).",
        )
        analyze.add_argument(
            "--cwd",
            dest="code_directory",
            help="Directory to search for code (defaults to current directory).",
        )

    def run(self, argv: Sequence[str] | None = None) -> int:
        args = self.parser.parse_args(argv)
        AnalyzeCommand(self.console, args).run()
        return 0


class AnalyzeCommand:
    """Pipeline driver for `merit-analyzer analyze`."""

    def __init__(self, console: Console, args: argparse.Namespace) -> None:
        self.console = console
        self.csv_path = Path(args.csv_path).expanduser()
        self.report_path = Path(args.report_path).expanduser()
        self.model_vendor = args.model_vendor
        self.inference_vendor = args.inference_vendor
        self.code_directory = Path(args.code_directory).expanduser() if args.code_directory else None
        self.analyzer = ErrorAnalyzer()

    def run(self) -> None:
        if self.model_vendor:
            os.environ["MODEL_VENDOR"] = self.model_vendor
        if self.inference_vendor:
            os.environ["INFERENCE_VENDOR"] = self.inference_vendor
        asyncio.run(self.execute())

    async def execute(self) -> None:
        self.console.print(f"Parsing test cases from {self.csv_path}...", style="bold cyan")
        test_cases = parse_test_cases_from_csv(str(self.csv_path))
        failed_cases = [
            case for case in test_cases if not case.assertions_result or not case.assertions_result.passed
        ]
        if not failed_cases:
            format_analysis_results([], str(self.report_path))
            self.console.print("No failing tests found. Blank report generated.", style="bold green")
            return

        cases_needing_errors = [
            case for case in failed_cases 
            if not case.assertions_result or not case.assertions_result.errors
        ]
        
        if cases_needing_errors:
            self.console.print(
                f"Generating missing error descriptions for {len(cases_needing_errors)} test(s)...", 
                style="bold cyan"
            )
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=self.console,
            ) as progress:
                task = progress.add_task("[cyan]Generating descriptions...", total=len(cases_needing_errors))
                for idx, case in enumerate(cases_needing_errors, 1):
                    progress.update(task, description=f"[cyan]Generating error description {idx}/{len(cases_needing_errors)}...")
                    await case.generate_error_data()
                    progress.advance(task)

        self.console.print("Clustering failures...", style="bold cyan")
        groups = await cluster_failures(failed_cases)

        self.console.print("Running deep analysis per cluster...", style="bold cyan")
        if self.code_directory:
            self.console.print(f"  Searching code in: {self.code_directory}", style="dim")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task("[cyan]Analyzing clusters...", total=len(groups))
            for idx, group in enumerate(groups, 1):
                progress.update(task, description=f"[cyan]Analyzing cluster {idx}/{len(groups)}: {group.metadata.name[:50]}...")
                group.error_analysis = await self.analyzer.run(group, self.code_directory)
                progress.advance(task)

        format_analysis_results(groups, str(self.report_path))
        self.console.print(f"Report saved to {self.report_path}", style="bold green")
