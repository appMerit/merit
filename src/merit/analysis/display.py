"""Result formatting for analysis responses."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table


class ResultDisplay:
    """Display analysis results in table, JSON, or markdown formats."""

    def __init__(self, console: Console | None = None) -> None:
        self._console = console or Console()

    async def display(self, result: dict[str, Any], format_type: str) -> None:
        """Render response using the requested output format."""
        if format_type == "json":
            self._display_json(result)
            return

        if format_type == "markdown":
            self._display_markdown(result)
            return

        self._display_table(result)

    def _display_json(self, result: dict[str, Any]) -> None:
        self._console.print(json.dumps(result, indent=2))

    def _display_table(self, result: dict[str, Any]) -> None:
        self._console.print("\n[bold]Error Analysis[/bold]\n")

        summary_table = Table(show_header=False, box=None)
        summary_table.add_column("Field", style="cyan")
        summary_table.add_column("Value", style="white")

        summary_table.add_row("Job ID", str(result.get("job_id", "N/A")))
        summary_table.add_row("Status", str(result.get("status", "unknown")))

        progress = result.get("progress") if isinstance(result.get("progress"), dict) else {}
        summary_table.add_row("Step", str(progress.get("current_step", "N/A")))
        summary_table.add_row("Progress", f"{progress.get('percent_complete', 0)}%")

        result_data = result.get("result") if isinstance(result.get("result"), dict) else {}
        summary_table.add_row(
            "Failed tests",
            str(result_data.get("failed_test_cases", result_data.get("total_test_cases", "N/A"))),
        )
        summary_table.add_row("Clusters", str(result_data.get("clusters_found", "N/A")))
        summary_table.add_row(
            "Successful analyses", str(result_data.get("successful_analyses", "N/A"))
        )
        summary_table.add_row("Failed analyses", str(result_data.get("failed_analyses", "N/A")))

        if isinstance(result_data.get("report_url"), str):
            summary_table.add_row("Report URL", str(result_data.get("report_url")))

        self._console.print(summary_table)

        report_data = result_data.get("report_data") if isinstance(result_data, dict) else None
        clusters = report_data.get("clusters", []) if isinstance(report_data, dict) else []
        if not clusters:
            self._console.print("\n[yellow]No clusters available in report_data.[/yellow]")
            return

        clusters_table = Table(title="Clusters")
        clusters_table.add_column("Cluster", style="cyan")
        clusters_table.add_column("Failures", style="magenta")
        clusters_table.add_column("Behavior", style="white")
        clusters_table.add_column("Top Fix", style="green")

        for cluster in clusters:
            recommended = (
                cluster.get("recommendedFixes", [])
                if isinstance(cluster.get("recommendedFixes"), list)
                else []
            )
            top_fix = "N/A"
            if recommended:
                first_fix = recommended[0]
                if isinstance(first_fix, dict):
                    top_fix = str(first_fix.get("title", "N/A"))

            clusters_table.add_row(
                str(cluster.get("name", cluster.get("id", "Unknown"))),
                str(cluster.get("failureCount", cluster.get("totalFailures", "N/A"))),
                str(cluster.get("problematicBehavior", ""))[:120],
                top_fix[:80],
            )

        self._console.print(clusters_table)

    def _display_markdown(self, result: dict[str, Any]) -> None:
        status = str(result.get("status", "unknown"))
        result_data = result.get("result") if isinstance(result.get("result"), dict) else {}
        report_data = result_data.get("report_data") if isinstance(result_data, dict) else None
        clusters = report_data.get("clusters", []) if isinstance(report_data, dict) else []

        self._console.print("# Error Analysis Report\n")
        self._console.print("## Summary")
        self._console.print(f"- Job ID: {result.get('job_id', 'N/A')}")
        self._console.print(f"- Status: {status}")
        self._console.print(
            f"- Failed Test Cases: {result_data.get('failed_test_cases', result_data.get('total_test_cases', 'N/A'))}"
        )
        self._console.print(f"- Clusters Found: {result_data.get('clusters_found', 'N/A')}")
        self._console.print(
            f"- Successful Analyses: {result_data.get('successful_analyses', 'N/A')}"
        )
        self._console.print(f"- Failed Analyses: {result_data.get('failed_analyses', 'N/A')}")

        report_url = result_data.get("report_url")
        if isinstance(report_url, str) and report_url:
            self._console.print(f"- Report URL: {report_url}")

        self._console.print("\n## Clusters")
        if not clusters:
            self._console.print("No clusters available in report_data.")
            return

        for index, cluster in enumerate(clusters, start=1):
            self._console.print(f"### {index}. {cluster.get('name', cluster.get('id', 'Unknown'))}")
            self._console.print(
                f"- Failure Count: {cluster.get('failureCount', cluster.get('totalFailures', 'N/A'))}"
            )
            self._console.print(
                f"- Problematic Behavior: {cluster.get('problematicBehavior', 'N/A')}"
            )

            recommended = (
                cluster.get("recommendedFixes", [])
                if isinstance(cluster.get("recommendedFixes"), list)
                else []
            )
            if not recommended:
                self._console.print("- Recommended Fixes: none")
                continue

            self._console.print("- Recommended Fixes:")
            for fix in recommended:
                if not isinstance(fix, dict):
                    continue
                self._console.print(
                    f"  - {fix.get('title', 'Untitled')}"
                    f" ({fix.get('file', 'unknown')}:{fix.get('lines', 'n/a')})"
                )
