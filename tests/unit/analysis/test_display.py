from __future__ import annotations

import pytest
from rich.console import Console

from merit.analysis.display import ResultDisplay


@pytest.mark.asyncio
async def test_display_table_renders_summary_clusters_and_top_fix() -> None:
    console = Console(record=True, force_terminal=False, width=200)
    display = ResultDisplay(console)

    await display.display(
        {
            "job_id": "job-123",
            "status": "completed",
            "progress": {"current_step": "completed", "percent_complete": 100},
            "result": {
                "failed_test_cases": 8,
                "clusters_found": 2,
                "successful_analyses": 2,
                "failed_analyses": 0,
                "report_url": "/api/v1/error-analyzer/jobs/job-123/report",
                "report_data": {
                    "clusters": [
                        {
                            "id": "1",
                            "name": "SCHEMA_MISMATCH",
                            "failureCount": 5,
                            "problematicBehavior": "Response misses required field",
                            "recommendedFixes": [{"title": "Add required key"}],
                        },
                        {
                            "id": "2",
                            "name": "TIMEOUT_PATH",
                            "failureCount": 3,
                            "problematicBehavior": "Slow path timeout",
                            "recommendedFixes": [],
                        },
                    ]
                },
            },
        },
        "table",
    )

    output = console.export_text()
    assert "Error Analysis" in output
    assert "job-123" in output
    assert "SCHEMA_MISMATCH" in output
    assert "Add required key" in output
    assert "TIMEOUT_PATH" in output


@pytest.mark.asyncio
async def test_display_markdown_is_deterministic() -> None:
    console = Console(record=True, force_terminal=False, width=200)
    display = ResultDisplay(console)

    await display.display(
        {
            "job_id": "job-123",
            "status": "completed",
            "result": {
                "failed_test_cases": 2,
                "clusters_found": 1,
                "successful_analyses": 1,
                "failed_analyses": 0,
                "report_url": "/api/v1/error-analyzer/jobs/job-123/report",
                "report_data": {
                    "clusters": [
                        {
                            "id": "1",
                            "name": "PARSER_FAIL",
                            "failureCount": 2,
                            "problematicBehavior": "Parser rejects JSON",
                            "recommendedFixes": [
                                {
                                    "title": "Relax parser",
                                    "file": "src/parser.py",
                                    "lines": "20-31",
                                }
                            ],
                        }
                    ]
                },
            },
        },
        "markdown",
    )

    output = console.export_text()
    assert "# Error Analysis Report" in output
    assert "## Summary" in output
    assert "### 1. PARSER_FAIL" in output
    assert "Relax parser (src/parser.py:20-31)" in output


@pytest.mark.asyncio
async def test_display_table_handles_empty_clusters() -> None:
    console = Console(record=True, force_terminal=False, width=200)
    display = ResultDisplay(console)

    await display.display(
        {
            "job_id": "job-123",
            "status": "completed",
            "result": {
                "clusters_found": 0,
                "report_data": {"clusters": []},
            },
        },
        "table",
    )

    output = console.export_text()
    assert "No clusters available in report_data." in output
