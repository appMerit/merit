from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from merit.analysis.error_analysis.dependency_scope import DependencyScopeBuilder
from merit.analysis.types import GuardrailViolationError
from merit.testing.sut.dep_collector import (
    DependencyCollectionMode,
    DependencyEntry,
)


def _signature(test_module: str) -> dict[str, Any]:
    return {"test_module": test_module}


def test_dependency_scope_resolves_absolute_relative_dedupes_and_sorts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path
    (root / "b.py").write_text("VALUE = 2\n", encoding="utf-8")
    (root / "a.py").write_text("VALUE = 1\n", encoding="utf-8")
    calls: list[Path] = []

    def fake_collect(
        self: Any,
        *,
        seed_module: str,
        seed_file: Path,
        mode: DependencyCollectionMode,
        seed_symbol: str | None = None,
    ) -> list[DependencyEntry]:
        calls.append(seed_file)
        return [DependencyEntry(module_name=seed_module, file_path=seed_file)]

    monkeypatch.setattr(
        "merit.analysis.error_analysis.dependency_scope.DependencyCollector.collect",
        fake_collect,
    )

    include_paths = DependencyScopeBuilder(root).build_include_paths(
        [
            _signature(str((root / "b.py").resolve())),
            _signature("a.py"),
            _signature("a.py"),
        ]
    )

    assert include_paths == [Path("a.py"), Path("b.py")]
    assert calls == [root / "a.py", root / "b.py"]


def test_dependency_scope_builds_module_names_for_module_and_init(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path
    (root / "pkg").mkdir()
    (root / "pkg" / "__init__.py").write_text("from .mod import VALUE\n", encoding="utf-8")
    (root / "pkg" / "mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    calls: list[tuple[str, DependencyCollectionMode]] = []

    def fake_collect(
        self: Any,
        *,
        seed_module: str,
        seed_file: Path,
        mode: DependencyCollectionMode,
        seed_symbol: str | None = None,
    ) -> list[DependencyEntry]:
        calls.append((seed_module, mode))
        return [DependencyEntry(module_name=seed_module, file_path=seed_file)]

    monkeypatch.setattr(
        "merit.analysis.error_analysis.dependency_scope.DependencyCollector.collect",
        fake_collect,
    )

    include_paths = DependencyScopeBuilder(root).build_include_paths(
        [
            _signature("pkg/mod.py"),
            _signature("pkg/__init__.py"),
        ]
    )

    assert include_paths == [Path("pkg/__init__.py"), Path("pkg/mod.py")]
    assert ("pkg", DependencyCollectionMode.MODULE) in calls
    assert ("pkg.mod", DependencyCollectionMode.MODULE) in calls


def test_dependency_scope_raises_when_no_valid_seed_paths(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("not python\n", encoding="utf-8")

    with pytest.raises(GuardrailViolationError, match="No valid dependency seeds"):
        DependencyScopeBuilder(tmp_path).build_include_paths(
            [
                _signature(""),
                _signature("notes.txt"),
                _signature("/tmp/not-in-root.py"),
            ]
        )
