"""Codebase packaging for analysis uploads."""

from __future__ import annotations

import asyncio
import os
import tempfile
import zipfile
from pathlib import Path

from .types import Guardrails, GuardrailViolationError, PackagingStats


try:
    import pathspec
except ImportError:  # pragma: no cover - exercised only without analyze extras
    pathspec = None  # type: ignore[assignment]


class CodebasePackager:
    """Packages source files into a ZIP archive with guardrail enforcement."""

    DEFAULT_EXCLUDES = {
        ".git",
        "__pycache__",
        "*.pyc",
        ".venv",
        "venv",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
        "*.egg-info",
        "dist",
        "build",
        ".tox",
        ".merit",
    }

    def __init__(
        self,
        root_path: Path,
        guardrails: Guardrails,
        extra_excludes: list[str] | None = None,
        include_paths: list[Path] | None = None,
    ) -> None:
        if pathspec is None:
            msg = "analysis extra is required. Install with: uv sync --extra analyze"
            raise RuntimeError(msg)

        self._root_path = root_path.resolve()
        self._guardrails = guardrails
        self._extra_excludes = set(extra_excludes or [])
        self._include_paths = include_paths
        self._spec = self._build_spec()

    async def create_zip(self) -> tuple[Path, PackagingStats]:
        """Create a zip archive and return path + packaging stats."""
        return await asyncio.to_thread(self._create_zip_sync)

    def _create_zip_sync(self) -> tuple[Path, PackagingStats]:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            zip_path = Path(tmp.name)

        included_files = self._iter_included_files()
        if len(included_files) > self._guardrails.max_zip_files:
            msg = f"Archive exceeds max_zip_files ({self._guardrails.max_zip_files})"
            zip_path.unlink(missing_ok=True)
            raise GuardrailViolationError(msg)

        file_count = 0
        total_bytes = 0

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for relative_path in included_files:
                file_size = (self._root_path / relative_path).stat().st_size
                if file_size > self._guardrails.max_file_bytes:
                    msg = (
                        f"File exceeds max_file_bytes ({self._guardrails.max_file_bytes}): "
                        f"{relative_path}"
                    )
                    zip_path.unlink(missing_ok=True)
                    raise GuardrailViolationError(msg)

                archive.write(self._root_path / relative_path, relative_path)
                file_count += 1
                total_bytes += file_size

        zip_bytes = zip_path.stat().st_size
        if zip_bytes > self._guardrails.max_zip_bytes:
            msg = f"Archive exceeds max_zip_bytes ({self._guardrails.max_zip_bytes})"
            zip_path.unlink(missing_ok=True)
            raise GuardrailViolationError(msg)

        stats = PackagingStats(
            file_count=file_count,
            total_bytes=total_bytes,
            zip_bytes=zip_bytes,
        )
        return zip_path, stats

    def _build_spec(self) -> pathspec.PathSpec:
        patterns: list[str] = sorted(self.DEFAULT_EXCLUDES)
        gitignore_path = self._root_path / ".gitignore"

        if gitignore_path.exists():
            with gitignore_path.open(encoding="utf-8") as handle:
                for line in handle:
                    pattern = line.strip()
                    if pattern and not pattern.startswith("#"):
                        patterns.append(pattern)

        patterns.extend(sorted(self._extra_excludes))
        return pathspec.PathSpec.from_lines("gitignore", patterns)

    def _iter_included_files(self) -> list[Path]:
        if self._include_paths is not None:
            return self._iter_selected_files()

        included: list[Path] = []

        for root, dirs, files in os.walk(self._root_path):
            root_path = Path(root)
            relative_root = root_path.relative_to(self._root_path)

            dirs[:] = [d for d in dirs if self._should_include(relative_root / d)]

            for name in files:
                file_path = root_path / name
                relative_path = file_path.relative_to(self._root_path)
                if self._should_include(relative_path):
                    included.append(relative_path)

        return included

    def _iter_selected_files(self) -> list[Path]:
        included: set[Path] = set()

        for include_path in self._include_paths or []:
            normalized = self._normalize_include_path(include_path)
            if normalized is None:
                continue
            if self._should_include(normalized):
                included.add(normalized)

        return sorted(included)

    def _normalize_include_path(self, include_path: Path) -> Path | None:
        absolute_path = (
            include_path.resolve()
            if include_path.is_absolute()
            else (self._root_path / include_path).resolve()
        )
        if not absolute_path.is_file():
            return None
        if not absolute_path.is_relative_to(self._root_path):
            return None
        return absolute_path.relative_to(self._root_path)

    def _should_include(self, relative_path: Path) -> bool:
        normalized = str(relative_path).replace(os.sep, "/")
        return not self._spec.match_file(normalized)
