"""CLI registration and dispatch for analysis commands."""

from __future__ import annotations

import argparse
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast

from .error_analysis.cli import register_error_commands


def register_analysis_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register top-level `analyze` command and its shared options."""
    parser = subparsers.add_parser("analyze", help="AI-powered analysis of test results")

    parser.add_argument(
        "--server-url",
        default=os.getenv("MERIT_API_BASE_URL", "https://api.appmerit.com"),
        help="Analysis server URL (env: MERIT_API_BASE_URL)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("MERIT_API_KEY"),
        help="API key for authentication (env: MERIT_API_KEY)",
    )
    parser.add_argument(
        "--output",
        choices=["table", "json", "markdown"],
        default="table",
        help="Output format",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Additional exclude patterns for codebase packaging",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Codebase root path (default: auto-detect)",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to the Merit SQLite database",
    )

    analysis_subparsers = parser.add_subparsers(dest="analysis_type", required=True)
    register_error_commands(analysis_subparsers)


async def run_analysis_command(args: argparse.Namespace) -> int:
    """Run the selected analysis subcommand."""
    analysis_func = cast("Callable[[argparse.Namespace], Awaitable[int]]", args.func)
    return await analysis_func(args)
