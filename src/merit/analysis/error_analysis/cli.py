"""CLI commands for error analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import UUID

from rich.console import Console

from merit.analysis.client import AnalysisClient
from merit.analysis.display import ResultDisplay
from merit.analysis.error_analysis.collector import ErrorDataCollector
from merit.analysis.error_analysis.dependency_scope import DependencyScopeBuilder
from merit.analysis.packager import CodebasePackager
from merit.analysis.types import (
    AnalysisContext,
    Guardrails,
    GuardrailViolationError,
    ServerConfig,
)
from merit.storage.sqlite.store import DEFAULT_DB_NAME, find_project_root


def register_error_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the `errors` analysis command."""
    parser = subparsers.add_parser("errors", help="Analyze failed/error test executions")
    parser.add_argument(
        "--run-id",
        help="Specific run ID to analyze (default: latest run)",
    )
    parser.set_defaults(func=run_error_analysis_command)


async def run_error_analysis_command(args: argparse.Namespace) -> int:
    """Execute async error analysis flow."""
    console = Console()
    guardrails = Guardrails()

    project_root = find_project_root()
    codebase_path = args.path or project_root
    db_path = args.db_path or (project_root / DEFAULT_DB_NAME)

    collector = ErrorDataCollector(Path(db_path))
    exit_code = 0
    zip_path: Path | None = None

    try:
        run_id = await _resolve_run_id(args.run_id, collector)
        context = AnalysisContext(
            run_id=run_id,
            db_path=Path(db_path),
            codebase_path=Path(codebase_path),
            exclude_patterns=list(args.exclude),
        )

        run_data = await collector.get_run(run_id)
        console.print(
            "[blue]"
            f"Analyzing run {run_data['run_id']} "
            f"(failed={run_data['summary']['failed']}, errors={run_data['summary']['errors']})"
            "[/blue]"
        )

        failure_signatures = await collector.get_failure_signatures(
            run_id,
            run_timestamp=str(run_data["start_time"]),
            max_failed_tests=guardrails.max_failed_tests,
            max_traceback_chars=guardrails.max_traceback_chars,
        )

        if not failure_signatures:
            console.print("[green]No failed/error executions to analyze.[/green]")
            return 0

        _validate_failure_signatures_size(
            failure_signatures,
            guardrails.max_failure_signatures_bytes,
        )

        dependency_paths = DependencyScopeBuilder(context.codebase_path).build_include_paths(
            failure_signatures
        )
        console.print("[blue]Packaging codebase...[/blue]")
        packager = CodebasePackager(
            root_path=context.codebase_path,
            guardrails=guardrails,
            extra_excludes=context.exclude_patterns,
            include_paths=dependency_paths,
        )
        zip_path, stats = await packager.create_zip()
        console.print(
            f"  {stats.file_count} files, {stats.total_bytes / (1024 * 1024):.1f} MB (raw)"
        )

        console.print("[blue]Submitting analysis...[/blue]")
        client = AnalysisClient(ServerConfig(base_url=args.server_url, api_key=args.api_key))
        try:
            result = await client.analyze_errors(failure_signatures, zip_path)
        finally:
            await client.aclose()

        status = str(result.get("status", "")).lower()
        if status == "failed":
            raise RuntimeError(_build_failed_job_message(result))

        display = ResultDisplay(console)
        await display.display(result, args.output)
    except (GuardrailViolationError, RuntimeError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        exit_code = 1
    finally:
        if zip_path is not None and zip_path.exists():
            zip_path.unlink()

    return exit_code


async def _resolve_run_id(run_id_arg: str | None, collector: ErrorDataCollector) -> UUID:
    if run_id_arg is not None:
        return UUID(run_id_arg)

    latest_run_id = await collector.get_latest_run_id()
    if latest_run_id is None:
        msg = "No test runs found in database."
        raise ValueError(msg)

    return latest_run_id


def _validate_failure_signatures_size(
    failure_signatures: list[dict[str, object]],
    max_failure_signatures_bytes: int,
) -> None:
    size = len(json.dumps(failure_signatures).encode("utf-8"))
    if size > max_failure_signatures_bytes:
        msg = (
            "failure_signatures exceeds max_failure_signatures_bytes "
            f"({max_failure_signatures_bytes})"
        )
        raise GuardrailViolationError(msg)


def _build_failed_job_message(result: dict[str, object]) -> str:
    error = result.get("error")
    if isinstance(error, dict) and "message" in error:
        return f"Analysis failed: {error['message']}"
    return "Analysis failed"
