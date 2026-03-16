"""Shared types for analysis flows."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID


class AnalysisError(RuntimeError):
    """Base error for analysis failures."""


class GuardrailViolationError(AnalysisError):
    """Raised when analysis payload guardrails are violated."""


@dataclass(slots=True, frozen=True)
class Guardrails:
    """Payload and packaging limits for analysis requests."""

    max_file_bytes: int = 10 * 1024 * 1024
    max_zip_bytes: int = 100 * 1024 * 1024
    max_zip_files: int = 10_000
    max_failed_tests: int = 10_000
    max_failure_signatures_bytes: int = 10 * 1024 * 1024
    max_traceback_chars: int = 20_000


@dataclass(slots=True, frozen=True)
class ServerConfig:
    """Server connection configuration for analysis APIs."""

    base_url: str
    api_key: str | None = None
    timeout_s: float = 120.0
    poll_interval_s: float = 2.0
    poll_max_attempts: int = 1800
    retry_max_attempts: int = 4
    retry_base_delay_s: float = 0.1
    retry_max_delay_s: float = 1.5


@dataclass(slots=True, frozen=True)
class AnalysisContext:
    """Execution context for a single analysis request."""

    run_id: UUID
    db_path: Path
    codebase_path: Path
    exclude_patterns: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class PackagingStats:
    """Statistics for packaged codebase archives."""

    file_count: int
    total_bytes: int
    zip_bytes: int


MetadataPayload = dict[str, Any]
AnalysisResponse = dict[str, Any]
