"""Dependency-based scope builder for error-analysis code packaging."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from merit.analysis.types import GuardrailViolationError
from merit.testing.sut.dep_collector import (
    DependencyCollectionMode,
    DependencyCollector,
)


class DependencyScopeBuilder:
    """Build deterministic include paths from failed test modules."""

    def __init__(self, root_path: Path) -> None:
        self._root_path = root_path.resolve()

    def build_include_paths(self, failure_signatures: list[dict[str, Any]]) -> list[Path]:
        """Resolve and collect dependency files for failed test modules."""
        seed_paths = self._resolve_seed_paths(failure_signatures)
        if not seed_paths:
            msg = "No valid dependency seeds resolved from failure_signatures.test_module"
            raise GuardrailViolationError(msg)

        collector = DependencyCollector(self._root_path)
        include_paths: set[Path] = set()

        for seed_path in seed_paths:
            seed_module = self._to_module_name(seed_path)
            dependency_entries = collector.collect(
                seed_module=seed_module,
                seed_file=self._root_path / seed_path,
                mode=DependencyCollectionMode.MODULE,
            )
            for entry in dependency_entries:
                if entry.file_path.is_file() and entry.file_path.is_relative_to(self._root_path):
                    include_paths.add(entry.file_path.relative_to(self._root_path))

        resolved = sorted(include_paths)
        if not resolved:
            msg = "Dependency collection produced no packageable files"
            raise GuardrailViolationError(msg)
        return resolved

    def _resolve_seed_paths(self, failure_signatures: list[dict[str, Any]]) -> list[Path]:
        seed_paths: set[Path] = set()

        for signature in failure_signatures:
            test_module = signature.get("test_module")
            if not isinstance(test_module, str) or not test_module.strip():
                continue

            resolved = self._resolve_test_module_path(test_module.strip())
            if resolved is None:
                continue

            seed_paths.add(resolved.relative_to(self._root_path))

        return sorted(seed_paths)

    def _resolve_test_module_path(self, test_module: str) -> Path | None:
        module_path = Path(test_module)
        absolute_path = (
            module_path.resolve()
            if module_path.is_absolute()
            else (self._root_path / module_path).resolve()
        )

        if not absolute_path.is_file() or absolute_path.suffix != ".py":
            return None
        if not absolute_path.is_relative_to(self._root_path):
            return None
        return absolute_path

    @staticmethod
    def _to_module_name(seed_path: Path) -> str:
        no_suffix = seed_path.with_suffix("")
        if seed_path.name == "__init__.py":
            parts = no_suffix.parts[:-1]
            if parts:
                return ".".join(parts)
            return "__init__"
        return ".".join(no_suffix.parts)
